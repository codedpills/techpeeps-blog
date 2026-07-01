#!/usr/bin/env python3
"""generate.py (PRD §7.4)

<video_id> (or --next) -> feature-profile draft on a branch + PR.

Flow:
  1. Load transcripts/<id>.json + style-guide.md.
  2. Call the LLM with the feature-profile prompt (§9.1). Parse the article
     (frontmatter + body, above the delimiter) and the CLIP_CANDIDATES JSON
     (below). Validate; retry once with a stricter instruction on bad output.
  3. Create branch post/<slug>; write src/content/blog/<slug>.md on that branch.
  4. Cut the hero clip from candidate #1 via clip.py; inject heroClip paths.
  5. Commit, push, open a PR (Draft: <title>) with review checklist + clip
     candidates + speaker-mapping confidence. Store pr_url; set status 'drafted'.

GUARDRAILS: never writes to main; never marks anything 'published'.

Usage:
  python pipeline/generate.py <video_id>
  python pipeline/generate.py --next
  python pipeline/generate.py <video_id> --no-pr
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date as _date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clip as clip_mod  # noqa: E402
import verify_post  # noqa: E402
from lib import config, llm, prompts, state  # noqa: E402
from lib.config import REPO_ROOT  # noqa: E402

BLOG_DIR = REPO_ROOT / "src" / "content" / "blog"
TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"
STYLE_GUIDE_PATH = REPO_ROOT / "style-guide.md"

CLIP_DELIM = "<!-- CLIP_CANDIDATES -->"
REQUIRED_FM_KEYS = [
    "title", "description", "pubDate", "guest", "guestBio",
    "videoId", "videoUrl", "tags", "heroClip", "draft",
]


# --------------------------------------------------------------------------- #
# Transcript -> prompt text
# --------------------------------------------------------------------------- #
def _ms_to_timestamp(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def format_transcript(data: dict) -> str:
    lines = []
    for seg in data["segments"]:
        ts = _ms_to_timestamp(seg["start_ms"])
        lines.append(f"[{ts}] {seg['speaker']}: {seg['text']}")
    return "\n".join(lines)


def guess_guest(data: dict) -> str | None:
    """Best-effort: longest GUEST self-introduction is unreliable; leave to human.
    We surface null so the reviewer / model fills it. Returns None by default.
    """
    return None


# --------------------------------------------------------------------------- #
# LLM output parsing / validation
# --------------------------------------------------------------------------- #
def split_output(text: str) -> tuple[str, str]:
    """Return (article_markdown, candidates_raw)."""
    if CLIP_DELIM in text:
        article, _, rest = text.partition(CLIP_DELIM)
        return article.strip(), rest.strip()
    return text.strip(), ""


def parse_frontmatter(article: str) -> dict | None:
    """Parse the leading YAML frontmatter block. Returns dict or None if absent."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", article, re.DOTALL)
    if not m:
        return None
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return fm if isinstance(fm, dict) else None


def frontmatter_valid(fm: dict | None) -> bool:
    """Mirror the zod schema (src/content/config.ts) so bad output triggers the
    retry rather than opening a PR that later fails `astro build`."""
    if not isinstance(fm, dict):
        return False
    if not all(k in fm for k in REQUIRED_FM_KEYS):
        return False

    # Non-empty required strings.
    for k in ("title", "guest", "guestBio", "videoId"):
        if not isinstance(fm.get(k), str) or not fm[k].strip():
            return False

    # description: non-empty, <= 155 chars.
    desc = fm.get("description")
    if not isinstance(desc, str) or not (1 <= len(desc) <= 155):
        return False

    # videoUrl: must look like a URL (zod uses .url()).
    url = fm.get("videoUrl")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return False

    # heroClip: object with all four keys present.
    hero = fm.get("heroClip")
    if not isinstance(hero, dict) or not all(
        k in hero for k in ("mp4", "webm", "poster", "alt")
    ):
        return False

    # tags: 4-6 entries.
    if not isinstance(fm.get("tags"), list) or not (4 <= len(fm["tags"]) <= 6):
        return False

    return True


def parse_candidates(raw: str) -> list[dict] | None:
    """Parse the CLIP_CANDIDATES JSON array, tolerating code fences."""
    if not raw:
        return None
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    # Grab the first [...] block.
    m = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not m:
        return None
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(arr, list) or not arr:
        return None
    ok = [c for c in arr if isinstance(c, dict) and {"start", "end"} <= set(c)]
    return ok or None


def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s[:80].strip("-") or "untitled"


def body_after_frontmatter(article: str) -> str:
    m = re.match(r"^---\s*\n.*?\n---\s*\n", article, re.DOTALL)
    return article[m.end():] if m else article


# --------------------------------------------------------------------------- #
# Generation (with one stricter retry)
# --------------------------------------------------------------------------- #
def generate_article(prompt: str) -> tuple[dict, str, list[dict]]:
    """Return (frontmatter, body_markdown, candidates). Retries once on bad output."""
    for attempt in (1, 2):
        p = prompt if attempt == 1 else prompt + prompts.FEATURE_PROFILE_RETRY_SUFFIX
        out = llm.complete(p, max_tokens=8000, temperature=0.7)
        article, candidates_raw = split_output(out)
        fm = parse_frontmatter(article)
        candidates = parse_candidates(candidates_raw)
        if frontmatter_valid(fm) and candidates:
            return fm, body_after_frontmatter(article).strip(), candidates
        print(
            f"WARNING: LLM output failed validation (attempt {attempt}). "
            f"frontmatter_ok={frontmatter_valid(fm)} candidates_ok={bool(candidates)}",
            file=sys.stderr,
        )
    raise RuntimeError(
        "LLM returned malformed frontmatter or no CLIP_CANDIDATES after retry. "
        "No PR opened."
    )


# --------------------------------------------------------------------------- #
# Git / PR
# --------------------------------------------------------------------------- #
def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        check=check, capture_output=True, text=True,
    )


def current_branch() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def ensure_branch(branch: str, base: str) -> None:
    """Create or switch to `branch`, forked explicitly off `base`. Idempotent.

    Forking off `base` (not the current HEAD) guarantees the PR diff contains
    only this post, even if a prior run left HEAD on a stale post branch.
    """
    existing = _git("branch", "--list", branch).stdout.strip()
    if existing:
        _git("checkout", branch)
    else:
        # `checkout -b <branch> <base>` creates the branch from base directly.
        _git("checkout", "-b", branch, base)


def open_pr(branch: str, title: str, body: str, base: str) -> str | None:
    """Open a PR via gh CLI. Returns the PR URL or None if gh unavailable."""
    cmd = ["gh", "pr", "create", "--title", title, "--body", body,
           "--base", base, "--head", branch, "--draft"]
    repo = config.get("GITHUB_REPO")
    if repo:
        cmd += ["--repo", repo]
    try:
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    except FileNotFoundError:
        print(
            "WARNING: `gh` CLI not found — branch pushed but no PR opened. "
            "Install GitHub CLI (https://cli.github.com) or open the PR manually.",
            file=sys.stderr,
        )
        return None
    if proc.returncode != 0:
        print(f"WARNING: `gh pr create` failed:\n{proc.stderr.strip()}", file=sys.stderr)
        return None
    return proc.stdout.strip()


def pr_body(fm: dict, confidence: str, candidates: list[dict],
            report_md: str = "") -> str:
    flag = " ⚠️ **LOW CONFIDENCE — please verify/flip**" if confidence == "low" else ""
    cand_lines = "\n".join(
        f"- `{c['start']}`–`{c['end']}` — {c.get('reason', '')}" for c in candidates
    )
    report_section = f"\n{report_md}\n" if report_md else ""
    return f"""\
**Guest:** {fm.get('guest', 'TBD')}
**Speaker mapping confidence:** {confidence}{flag}
{report_section}
### Candidate hero-clip windows
{cand_lines}

> Hero clip currently cut from candidate #1. To change it, re-run:
> `python pipeline/clip.py {fm.get('videoId')} --start <MM:SS> --end <MM:SS> --slug <slug>`

### Review checklist
- [ ] Speaker mapping correct (HOST vs GUEST not flipped){' — **flagged: low confidence**' if confidence == 'low' else ''}
- [ ] Every quoted sentence is verbatim from the transcript
- [ ] No invented facts or quotes
- [ ] Hero clip is the right moment, silent, loops cleanly
- [ ] Title + description (≤155 chars) + 4–6 tags present
- [ ] Guest name/bio + video link correct

_Merging this PR publishes the post. Reverting unpublishes it._
"""


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a draft post + open a PR.")
    parser.add_argument("video_id", nargs="?")
    parser.add_argument("--next", action="store_true", help="First 'transcribed'.")
    parser.add_argument("--no-pr", action="store_true", help="Local branch only.")
    parser.add_argument("--force", action="store_true", help="Regenerate if drafted.")
    args = parser.parse_args()

    st = state.load()

    if args.next:
        video_id = state.next_with_status(st, "transcribed")
        if not video_id:
            print("No videos with status 'transcribed'. Nothing to do.")
            return 0
    elif args.video_id:
        video_id = args.video_id
    else:
        print("ERROR: provide a <video_id> or --next.", file=sys.stderr)
        return 1

    try:
        video = state.get(st, video_id)
    except KeyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if video["status"] == "drafted" and not args.force:
        print(f"{video_id} already drafted (PR: {video.get('pr_url')}). Use --force.")
        return 0

    tpath = TRANSCRIPTS_DIR / f"{video_id}.json"
    if not tpath.exists():
        print(f"ERROR: transcript missing: {tpath}. Run transcribe.py first.",
              file=sys.stderr)
        return 1
    transcript = json.loads(tpath.read_text(encoding="utf-8"))

    style_guide = (
        STYLE_GUIDE_PATH.read_text(encoding="utf-8")
        if STYLE_GUIDE_PATH.exists()
        else "(No style guide yet — write in a warm, narrative feature voice.)"
    )

    host_name = config.get("HOST_NAME", "the host")
    prompt = prompts.feature_profile_prompt(
        host_name=host_name,
        guest_name=video.get("guest") or "",
        guest_bio=None,
        style_guide=style_guide,
        transcript=format_transcript(transcript),
    )

    print(f"Generating feature profile for {video_id}…")
    try:
        fm, body, candidates = generate_article(prompt)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    slug = slugify(str(fm.get("title", video.get("title", video_id))))
    guest = fm.get("guest")

    # Guardrail: never operate on the base branch directly.
    base_branch = config.get("BASE_BRANCH", "main")
    starting_branch = current_branch()
    branch = f"post/{slug}"
    has_errors = False

    try:
        ensure_branch(branch, base_branch)

        # Cut the hero clip from candidate #1 (best effort; warn but continue).
        hero_paths = {
            "mp4": f"/clips/{slug}.mp4",
            "webm": f"/clips/{slug}.webm",
            "poster": f"/clips/{slug}.jpg",
        }
        try:
            top = candidates[0]
            hero_paths = clip_mod.make_clip(video_id, top["start"], top["end"], slug)
        except (RuntimeError, ValueError) as exc:
            print(f"WARNING: hero clip generation failed: {exc}", file=sys.stderr)
            print("  Frontmatter keeps placeholder clip paths; cut it during review.",
                  file=sys.stderr)

        # Inject the resolved hero paths, preserving the model's alt text.
        alt = ""
        if isinstance(fm.get("heroClip"), dict):
            alt = fm["heroClip"].get("alt", "")
        fm["heroClip"] = {**hero_paths, "alt": alt or f"Clip from the {guest} interview"}

        # Inject the REAL video id/url — never trust the model for these (it tends
        # to emit a placeholder). The pipeline knows the canonical value.
        fm["videoId"] = video_id
        fm["videoUrl"] = f"https://www.youtube.com/watch?v={video_id}"
        # Default pubDate to today rather than a model-hallucinated date.
        fm["pubDate"] = _date.today().isoformat()
        # The interview's YouTube publish date (captured at transcribe time).
        vpub = transcript.get("video_published_at")
        if vpub:
            fm["interviewDate"] = vpub
        else:
            fm.pop("interviewDate", None)

        # Write the draft on the branch.
        BLOG_DIR.mkdir(parents=True, exist_ok=True)
        out_md = BLOG_DIR / f"{slug}.md"
        front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
        out_md.write_text(f"---\n{front}\n---\n\n{body}\n", encoding="utf-8")
        print(f"Wrote draft: {out_md}")

        # Automated checks (PRD §8): verify quotes are verbatim, frontmatter is
        # valid, the video link is real, and the clip is present + silent. We do
        # NOT block on failure — the PR always opens so the post can be previewed
        # and reviewed; the findings are embedded in the PR body and CI repeats
        # them as a comment + a (red) check on hard errors.
        v_errors, v_warnings = verify_post.verify_file(out_md)
        report_md, has_errors = verify_post.build_report([(out_md, v_errors, v_warnings)])
        for w in v_warnings:
            print(f"  ⚠️  {w}")
        for e in v_errors:
            print(f"  ✗  {e}", file=sys.stderr)
        if has_errors:
            print("Content issues found — opening the PR anyway; see the PR body / "
                  "CI comment for details and fixes.", file=sys.stderr)

        # Stage ONLY this post's files (never `add -A`, which would sweep up
        # uncommitted transcripts/state into the draft commit).
        _git("add", str(out_md))
        clip_files = [
            REPO_ROOT / "public" / "clips" / f"{slug}.{ext}"
            for ext in ("mp4", "webm", "jpg")
        ]
        existing_clips = [str(p) for p in clip_files if p.exists()]
        if existing_clips:
            _git("add", *existing_clips)
        _git("commit", "-m", f"Draft: {fm.get('title', slug)}", check=False)

        pr_url = None
        if not args.no_pr:
            push = _git("push", "-u", "origin", branch, check=False)
            if push.returncode != 0:
                print(f"WARNING: git push failed:\n{push.stderr.strip()}",
                      file=sys.stderr)
            else:
                body_text = pr_body(
                    fm, transcript.get("mapping_confidence", "high"),
                    candidates, report_md,
                )
                pr_url = open_pr(
                    branch, f"Draft: {fm.get('title', slug)}", body_text, base_branch
                )
    finally:
        # Return to the original branch so the working tree is left clean.
        _git("checkout", starting_branch, check=False)
        # Guardrail check: confirm we are NOT left on the base branch with the
        # draft sitting in the working tree.
        if current_branch() == branch:
            print(
                f"WARNING: still on {branch} (checkout back to {starting_branch} "
                "failed). Resolve the working tree manually before re-running.",
                file=sys.stderr,
            )

    # Update state — status 'drafted' only; NEVER 'published'. The PR is opened
    # regardless of content findings; review (and the CI check) is the gate.
    state.update_video(
        st, video_id,
        guest=guest, slug=slug, pr_url=pr_url, status="drafted",
    )
    state.save(st)

    print(f"Status -> drafted. Branch: {branch}")
    if pr_url:
        print(f"PR: {pr_url}")
    elif not args.no_pr:
        print("No PR URL captured — open the PR manually from the pushed branch.")
    if has_errors:
        print("Note: content checks flagged hard errors — see the PR for details.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
