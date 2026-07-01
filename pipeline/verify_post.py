#!/usr/bin/env python3
"""verify_post.py — automate the machine-checkable parts of the review checklist.

Turns these PR-checklist items into a hard gate:
  - Every quoted sentence is verbatim from the transcript   (fail on fabrication)
  - No invented quotes                                       (fail)
  - Frontmatter contract: title/description(<=155)/4-6 tags/heroClip/guest/bio
  - Guest video link correct: videoUrl matches videoId, no PLACEHOLDER
  - Hero clip present, silent (no audio stream), and < ~2 MB
  - Speaker mapping confidence surfaced (warns if 'low')

Items a human must still judge (NOT gated here): whether HOST/GUEST is actually
correct, whether a paraphrase invents a *fact*, whether the clip moment is right.

Usage:
  python pipeline/verify_post.py <path-to-post.md> [...]
  python pipeline/verify_post.py --all          # every post in src/content/blog
Exit code 0 if all pass, 1 if any hard error.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import REPO_ROOT  # noqa: E402

BLOG_DIR = REPO_ROOT / "src" / "content" / "blog"
TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"
PUBLIC_DIR = REPO_ROOT / "public"

MAX_MP4_BYTES = int(2.2 * 1024 * 1024)  # ~2 MB target, small slack
MIN_QUOTE_WORDS = 3  # ignore trivial 1-2 word quotes (common words match anything)


# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #
def normalize(s: str) -> str:
    s = (
        s.replace("’", "'").replace("‘", "'")
        .replace("“", '"').replace("”", '"')
        .replace("—", " ").replace("–", " ")
    )
    s = s.lower()
    s = re.sub(r"[^a-z0-9' ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def is_subsequence(words: list[str], hay: str) -> bool:
    """True if `words` appear in order within hay (i.e. only filler was removed)."""
    i = 0
    for w in hay.split():
        if i < len(words) and w == words[i]:
            i += 1
    return i == len(words)


def split_frontmatter(text: str) -> tuple[dict | None, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not m:
        return None, text
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None, m.group(2)
    return (fm if isinstance(fm, dict) else None), m.group(2)


# --------------------------------------------------------------------------- #
# Individual checks (append to errors / warnings)
# --------------------------------------------------------------------------- #
def check_frontmatter(fm: dict, errors: list, warnings: list) -> None:
    required = ["title", "description", "pubDate", "guest", "guestBio",
               "videoId", "videoUrl", "tags", "heroClip"]
    for k in required:
        if k not in fm or fm.get(k) in (None, ""):
            errors.append(f"frontmatter: missing/empty '{k}'")

    desc = fm.get("description", "")
    if isinstance(desc, str) and len(desc) > 155:
        errors.append(f"frontmatter: description is {len(desc)} chars (max 155)")

    tags = fm.get("tags")
    if not isinstance(tags, list) or not (4 <= len(tags) <= 6):
        errors.append(f"frontmatter: tags must be 4-6 (got {len(tags) if isinstance(tags, list) else 'none'})")

    hero = fm.get("heroClip")
    if not isinstance(hero, dict) or not all(k in hero for k in ("mp4", "webm", "poster", "alt")):
        errors.append("frontmatter: heroClip must have mp4/webm/poster/alt")

    if not fm.get("interviewDate"):
        warnings.append(
            "frontmatter: interviewDate (video publish date) missing — run "
            "`make refresh-meta` then regenerate, or `make patch-dates`."
        )


def check_video_link(fm: dict, errors: list) -> None:
    vid = str(fm.get("videoId", ""))
    url = str(fm.get("videoUrl", ""))
    if "PLACEHOLDER" in vid or "PLACEHOLDER" in url:
        errors.append("video link: PLACEHOLDER value not replaced")
        return
    if not url.startswith(("http://", "https://")):
        errors.append(f"video link: videoUrl is not a URL ({url!r})")
    if vid and vid not in url:
        errors.append(f"video link: videoUrl does not contain videoId ({vid!r})")


def check_hero_clip(fm: dict, public_dir: Path, errors: list, warnings: list) -> None:
    hero = fm.get("heroClip")
    if not isinstance(hero, dict):
        return
    for key in ("mp4", "webm", "poster"):
        rel = str(hero.get(key, "")).lstrip("/")
        f = public_dir / rel
        if not f.exists():
            errors.append(f"hero clip: file missing ({hero.get(key)})")
            continue
        if key == "mp4":
            size = f.stat().st_size
            if size > MAX_MP4_BYTES:
                warnings.append(f"hero clip: mp4 is {size/1048576:.2f} MB (>2 MB target)")
            _check_silent(f, errors, warnings)


def _check_silent(mp4: Path, errors: list, warnings: list) -> None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", str(mp4)],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        warnings.append("hero clip: ffprobe not found — skipped silent-audio check")
        return
    if out.stdout.strip():
        errors.append(f"hero clip: {mp4.name} has an AUDIO stream (must be silent)")


def check_quotes(body: str, transcript: dict, errors: list, warnings: list) -> None:
    full = normalize(" ".join(s["text"] for s in transcript["segments"]))
    quotes = re.findall(r'"([^"\n]+)"', body.replace("“", '"').replace("”", '"'))
    checked = 0
    for q in quotes:
        nq = normalize(q)
        words = nq.split()
        if len(words) < MIN_QUOTE_WORDS:
            continue
        checked += 1
        if nq in full:
            continue
        if is_subsequence(words, full):
            warnings.append(f"quote: filler removed inside quotes — not strictly verbatim: \"{q[:70]}…\"")
        else:
            errors.append(f"quote NOT FOUND in transcript (possible fabrication): \"{q[:80]}…\"")
    if checked == 0:
        warnings.append("quotes: no multi-word quotes found to verify")


def check_mapping(transcript: dict, warnings: list) -> None:
    if transcript.get("mapping_confidence") == "low":
        warnings.append("speaker mapping confidence is LOW — confirm HOST/GUEST not flipped")
    if transcript.get("speakers_detected") not in (2, None):
        warnings.append(f"speakers_detected = {transcript.get('speakers_detected')} (expected 2)")


# --------------------------------------------------------------------------- #
# Per-file driver
# --------------------------------------------------------------------------- #
def verify_file(path: Path) -> tuple[list, list]:
    errors: list[str] = []
    warnings: list[str] = []
    text = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if fm is None:
        return [f"{path.name}: no valid YAML frontmatter"], []

    # Resolve transcript/clip dirs relative to THIS post's repo root
    # (src/content/blog/<x>.md -> root), so the verifier works in worktrees too.
    try:
        root = path.resolve().parents[3]
    except IndexError:
        root = REPO_ROOT
    transcripts_dir = root / "transcripts"
    public_dir = root / "public"

    if "PLACEHOLDER" in text:
        errors.append("contains PLACEHOLDER token(s)")

    check_frontmatter(fm, errors, warnings)
    check_video_link(fm, errors)
    check_hero_clip(fm, public_dir, errors, warnings)

    vid = str(fm.get("videoId", ""))
    tpath = transcripts_dir / f"{vid}.json"
    if "PLACEHOLDER" in vid or not vid:
        errors.append("cannot verify quotes: videoId unset/placeholder")
    elif not tpath.exists():
        errors.append(f"cannot verify quotes: transcript missing ({tpath.name})")
    else:
        transcript = json.loads(tpath.read_text(encoding="utf-8"))
        check_quotes(body, transcript, errors, warnings)
        check_mapping(transcript, warnings)

    return errors, warnings


# --------------------------------------------------------------------------- #
# Reporting (shared by generate.py's PR body and CI's PR comment)
# --------------------------------------------------------------------------- #
def fix_hint(msg: str) -> str:
    """Return a one-line suggested fix for a given error/warning message."""
    m = msg.lower()
    if "not found" in m and "quote" in m:
        return ("Quote only words that appear verbatim in the transcript, or "
                "rewrite the sentence as paraphrase (no quotation marks).")
    if "filler removed" in m:
        return ("Restore the exact transcript wording inside the quotes, or drop "
                "the quotation marks and present it as paraphrase.")
    if "placeholder" in m:
        return "Replace the PLACEHOLDER value with the real one."
    if "video link" in m or "videourl" in m:
        return "Set videoId to the YouTube id and videoUrl to the matching watch URL."
    if "hero clip" in m and "audio" in m:
        return "Re-cut the clip with audio stripped: pipeline/clip.py always uses -an."
    if "hero clip" in m and "missing" in m:
        return "Run pipeline/clip.py to (re)generate the clip files for this slug."
    if "frontmatter" in m:
        return "Fix the frontmatter field to satisfy the schema in src/content/config.ts."
    if "transcript missing" in m:
        return "Commit transcripts/<videoId>.json (run pipeline/transcribe.py)."
    if "mapping confidence is low" in m:
        return "Confirm HOST/GUEST aren't flipped; `make remap` re-runs the mapping."
    return "Review against the transcript and the frontmatter contract."


def build_report(results: list[tuple]) -> tuple[str, bool]:
    """results: list of (path, errors, warnings). Returns (markdown, has_errors)."""
    total_err = sum(len(e) for _, e, _ in results)
    total_warn = sum(len(w) for _, _, w in results)
    lines = ["## 🔍 Content check", ""]
    if not results:
        return "## 🔍 Content check\n\nNo posts to verify.\n", False
    if total_err == 0 and total_warn == 0:
        lines.append("✅ All quotes are verbatim and the frontmatter/clip checks pass.")
        return "\n".join(lines) + "\n", False

    lines.append(
        f"Found **{total_err} error(s)** and **{total_warn} warning(s)**. "
        "Errors should be fixed before publishing; warnings are advisory."
    )
    for path, errors, warnings in results:
        if not errors and not warnings:
            continue
        lines.append(f"\n### `{Path(path).name}`")
        if errors:
            lines.append("\n**❌ Errors (must fix)**")
            for e in errors:
                lines.append(f"- {e}\n  - _Fix:_ {fix_hint(e)}")
        if warnings:
            lines.append("\n**⚠️ Warnings (review)**")
            for w in warnings:
                lines.append(f"- {w}\n  - _Fix:_ {fix_hint(w)}")
    return "\n".join(lines) + "\n", total_err > 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify post(s) against the transcript.")
    ap.add_argument("paths", nargs="*", help="Post .md path(s).")
    ap.add_argument("--all", action="store_true", help="Check every post in src/content/blog.")
    ap.add_argument("--md", metavar="FILE", help="Write a Markdown report to FILE.")
    ap.add_argument("--no-fail", action="store_true",
                    help="Always exit 0 (advisory mode); still reports.")
    args = ap.parse_args()

    if args.all:
        paths = sorted(BLOG_DIR.glob("*.md"))
    else:
        paths = [Path(p) for p in args.paths]
    if not paths:
        print("No posts to verify.")
        if args.md:
            Path(args.md).write_text("## 🔍 Content check\n\nNo posts to verify.\n")
        return 0

    results = []
    for p in paths:
        if not p.exists():
            results.append((p, [f"file not found: {p}"], []))
            continue
        errors, warnings = verify_file(p)
        results.append((p, errors, warnings))

    # Human-readable console output.
    for p, errors, warnings in results:
        status = "✓ PASS" if not errors else "✗ FAIL"
        print(f"\n{status}  {Path(p).name}")
        for w in warnings:
            print(f"    ⚠️  {w}")
        for e in errors:
            print(f"    ✗  {e}")

    md, has_errors = build_report(results)
    if args.md:
        Path(args.md).write_text(md, encoding="utf-8")

    total_errors = sum(len(e) for _, e, _ in results)
    print("\n" + ("All posts passed." if total_errors == 0
                  else f"{total_errors} error(s) found."))
    if args.no_fail:
        return 0
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
