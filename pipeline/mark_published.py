#!/usr/bin/env python3
"""mark_published.py (PRD §7.6)

Post-merge state update: flip a video to 'published'. Run after the PR is
merged (or wire into a `make publish ID=<video_id>`).

Usage:
  python pipeline/mark_published.py <video_id>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import state  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Mark a video published.")
    parser.add_argument("video_id")
    args = parser.parse_args()

    st = state.load()
    try:
        video = state.get(st, args.video_id)
    except KeyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if video["status"] != "drafted":
        print(f"WARNING: {args.video_id} status is '{video['status']}', not 'drafted'. "
              "Marking published anyway.", file=sys.stderr)

    state.update_video(st, args.video_id, status="published")
    state.save(st)
    print(f"{args.video_id} -> published.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
