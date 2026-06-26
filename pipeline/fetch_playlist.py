#!/usr/bin/env python3
"""fetch_playlist.py (PRD §7.1)

Enumerate a YouTube playlist with `yt-dlp --flat-playlist` (no YouTube Data API)
and add any new video IDs to state.json as 'pending'. Never downgrades existing
statuses. Idempotent.

Usage:
  python pipeline/fetch_playlist.py [--playlist URL]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config, state  # noqa: E402


def enumerate_playlist(url: str) -> list[tuple[str, str]]:
    """Return [(video_id, title), ...] using yt-dlp flat enumeration."""
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print",
        "%(id)s\t%(title)s",
        url,
    ]
    try:
        out = subprocess.run(
            cmd, check=True, capture_output=True, text=True
        ).stdout
    except FileNotFoundError:
        print(
            "ERROR: yt-dlp is not installed. Run: pip install yt-dlp", file=sys.stderr
        )
        raise SystemExit(1)
    except subprocess.CalledProcessError as exc:
        print(
            "ERROR: yt-dlp failed to enumerate the playlist.\n"
            f"  command: {' '.join(cmd)}\n"
            f"  stderr: {exc.stderr.strip()}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    rows: list[tuple[str, str]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        vid, _, title = line.partition("\t")
        rows.append((vid.strip(), title.strip()))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh state.json from a playlist.")
    parser.add_argument("--playlist", help="Playlist URL (overrides state/env).")
    args = parser.parse_args()

    st = state.load()
    url = (
        args.playlist
        or st.get("playlist_url")
        or config.get("YT_PLAYLIST_URL")
    )
    if not url:
        print(
            "ERROR: no playlist URL. Pass --playlist, set YT_PLAYLIST_URL in .env, "
            "or populate playlist_url in state.json.",
            file=sys.stderr,
        )
        return 1

    st["playlist_url"] = url
    rows = enumerate_playlist(url)
    if not rows:
        print("WARNING: playlist enumeration returned no videos.", file=sys.stderr)

    new, known = 0, 0
    for vid, title in rows:
        if state.add_video(st, vid, title):
            new += 1
        else:
            known += 1

    state.save(st)
    print(f"Playlist: {url}")
    print(f"  {new} new video(s) added as 'pending'")
    print(f"  {known} already tracked")
    print(f"  {len(st['videos'])} total in state.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
