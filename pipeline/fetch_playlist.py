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


def _watch_url(ref: str) -> str:
    """Accept a full YouTube URL or a bare 11-char video id; return a watch URL."""
    ref = ref.strip()
    if ref.startswith(("http://", "https://")):
        return ref
    return f"https://www.youtube.com/watch?v={ref}"


def add_standalone_videos(st: dict, refs: list[str]) -> int:
    """Add one-off videos (not part of any playlist) to state.json.

    Each ref is a watch URL or a bare video id. The video is enumerated with the
    same flat print as a playlist (a single video URL yields one row), and stored
    with playlist=None so it is NEVER re-scanned by `make fetch`.
    """
    added = 0
    for ref in refs:
        rows = enumerate_playlist(_watch_url(ref))
        if not rows:
            print(f"WARNING: no video found for {ref!r}", file=sys.stderr)
            continue
        for vid, title in rows:  # normally exactly one
            if state.add_video(st, vid, title):  # playlist defaults to None
                print(f"Added standalone video: {vid}  ({title})")
                added += 1
            else:
                print(f"Already tracked: {vid}  ({title})")
    return added


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh state.json from registered playlists, or add "
        "standalone videos that don't belong to a playlist."
    )
    parser.add_argument(
        "--playlist",
        help="Register a new playlist URL, then refresh all. Omit to refresh "
        "the playlists already in state.json.",
    )
    parser.add_argument(
        "--video",
        action="append",
        metavar="URL_OR_ID",
        help="Add a standalone video (watch URL or bare id) with no playlist. "
        "Repeatable, or pass a comma-separated list. Does not register a playlist.",
    )
    args = parser.parse_args()

    st = state.load()

    # Standalone video(s): add them and stop — no playlist refresh required.
    if args.video:
        refs = [r for item in args.video for r in item.split(",") if r.strip()]
        added = add_standalone_videos(st, refs)
        state.save(st)
        print(f"\n{added} new standalone video(s) added · "
              f"{len(st['videos'])} total videos in state.json")
        return 0

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
