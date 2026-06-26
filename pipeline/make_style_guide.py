#!/usr/bin/env python3
"""make_style_guide.py (PRD §7.5)

One-time / occasional: synthesize the HOST's reusable editorial voice into
style-guide.md from 3-4 diarized transcripts.

Usage:
  python pipeline/make_style_guide.py <id1> <id2> <id3> [<id4>]
  python pipeline/make_style_guide.py --auto      # longest 3-4 transcribed
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import llm, prompts, state  # noqa: E402
from lib.config import REPO_ROOT  # noqa: E402

TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"
STYLE_GUIDE_PATH = REPO_ROOT / "style-guide.md"


def _ms(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def transcript_to_text(data: dict) -> str:
    header = f"### Transcript: {data.get('title', data['video_id'])}\n"
    lines = [
        f"[{_ms(seg['start_ms'])}] {seg['speaker']}: {seg['text']}"
        for seg in data["segments"]
    ]
    return header + "\n".join(lines)


def auto_select(limit: int = 4) -> list[str]:
    """Pick the longest 3-4 transcribed videos by transcript duration."""
    items = []
    for p in TRANSCRIPTS_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            items.append((d.get("duration_sec", 0), d["video_id"]))
        except Exception:
            continue
    items.sort(reverse=True)
    return [vid for _, vid in items[:limit]]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate style-guide.md.")
    parser.add_argument("ids", nargs="*", help="3-4 transcript video ids.")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-pick the longest 3-4 transcribed.")
    args = parser.parse_args()

    ids = auto_select() if args.auto else args.ids
    if not ids:
        print("ERROR: provide 3-4 transcript ids or use --auto.", file=sys.stderr)
        return 1
    if len(ids) < 3:
        print(f"WARNING: only {len(ids)} transcript(s); 3-4 recommended for a stable "
              "voice profile.", file=sys.stderr)

    blocks = []
    for vid in ids:
        p = TRANSCRIPTS_DIR / f"{vid}.json"
        if not p.exists():
            print(f"ERROR: transcript not found: {p}", file=sys.stderr)
            return 1
        blocks.append(transcript_to_text(json.loads(p.read_text(encoding="utf-8"))))

    prompt = prompts.style_guide_prompt(transcripts="\n\n".join(blocks))
    print(f"Synthesizing style guide from {len(ids)} transcript(s)…")
    try:
        guide = llm.complete(prompt, max_tokens=3000, temperature=0.4)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    STYLE_GUIDE_PATH.write_text(guide.strip() + "\n", encoding="utf-8")
    print(f"Wrote {STYLE_GUIDE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
