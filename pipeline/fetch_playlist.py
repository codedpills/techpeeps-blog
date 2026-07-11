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
        *config.ytdlp_cmd(),
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
    parser = argparse.ArgumentParser(
        description="Refresh state.json from all registered playlists."
    )
    parser.add_argument(
        "--playlist",
        help="Register a new playlist URL, then refresh all. Omit to refresh "
        "the playlists already in state.json.",
    )
    args = parser.parse_args()

    st = state.load()

    # Register a newly provided playlist (from --playlist or, first run, env).
    if args.playlist:
        if state.add_playlist(st, args.playlist):
            print(f"Registered new playlist: {args.playlist}")
    elif not st.get("playlists"):
        seed = config.get("YT_PLAYLIST_URL")
        if seed:
            state.add_playlist(st, seed)

    playlists = st.get("playlists", [])
    if not playlists:
        print(
            "ERROR: no playlists registered. Pass --playlist <url>, set "
            "YT_PLAYLIST_URL in .env, or add one to state.json's 'playlists'.",
            file=sys.stderr,
        )
        return 1

    grand_new = grand_known = 0
    for url in playlists:
        rows = enumerate_playlist(url)
        if not rows:
            print(f"WARNING: no videos from {url}", file=sys.stderr)
        new = known = 0
        for vid, title in rows:
            if state.add_video(st, vid, title, playlist=url):
                new += 1
            else:
                known += 1
        grand_new += new
        grand_known += known
        print(f"Playlist: {url}\n  {new} new, {known} already tracked")

    state.save(st)
    print(f"\n{len(playlists)} playlist(s) · {grand_new} new · "
          f"{grand_known} known · {len(st['videos'])} total videos in state.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
