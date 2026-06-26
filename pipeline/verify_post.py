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


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify post(s) against the transcript.")
    ap.add_argument("paths", nargs="*", help="Post .md path(s).")
    ap.add_argument("--all", action="store_true", help="Check every post in src/content/blog.")
    args = ap.parse_args()

    if args.all:
        paths = sorted(BLOG_DIR.glob("*.md"))
    else:
        paths = [Path(p) for p in args.paths]
    if not paths:
        print("No posts to verify.")
        return 0

    total_errors = 0
    for p in paths:
        if not p.exists():
            print(f"✗ {p}: file not found")
            total_errors += 1
            continue
        errors, warnings = verify_file(p)
        status = "✓ PASS" if not errors else "✗ FAIL"
        print(f"\n{status}  {p.name}")
        for w in warnings:
            print(f"    ⚠️  {w}")
        for e in errors:
            print(f"    ✗  {e}")
        total_errors += len(errors)

    print("\n" + ("All posts passed." if total_errors == 0
                  else f"{total_errors} error(s) found."))
    return 1 if total_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
