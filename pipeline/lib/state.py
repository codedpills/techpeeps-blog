"""Load / save / query the repo-level state.json (see PRD §6.1).

state.json is the single source of truth for per-video processing status.
Status transitions: pending -> transcribed -> drafted -> published.
Each pipeline step advances exactly one step and is idempotent.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Repo root = two levels up from this file (pipeline/lib/state.py -> repo/).
REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = REPO_ROOT / "state.json"

# Ordered status ladder. Index position = how far a video has progressed.
STATUS_ORDER = ["pending", "transcribed", "drafted", "published"]


def _now() -> str:
    """ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load() -> dict:
    """Load state.json, returning a default skeleton if it does not exist."""
    if not STATE_PATH.exists():
        return {"playlist_url": os.environ.get("YT_PLAYLIST_URL", ""), "videos": {}}
    with STATE_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("playlist_url", "")
    data.setdefault("videos", {})
    return data


def save(state: dict) -> None:
    """Write state.json atomically with stable key ordering."""
    tmp = STATE_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write("\n")
    tmp.replace(STATE_PATH)


def status_rank(status: str) -> int:
    """Return ladder position; unknown statuses rank below everything."""
    try:
        return STATUS_ORDER.index(status)
    except ValueError:
        return -1


def add_video(state: dict, video_id: str, title: str) -> bool:
    """Add a new video as 'pending'. Returns True if newly added.

    Never downgrades or overwrites an existing entry.
    """
    videos = state.setdefault("videos", {})
    if video_id in videos:
        # Refresh the title if it changed, but keep status/other fields.
        if title and videos[video_id].get("title") != title:
            videos[video_id]["title"] = title
            videos[video_id]["updated_at"] = _now()
        return False
    videos[video_id] = {
        "title": title,
        "status": "pending",
        "guest": None,
        "slug": None,
        "pr_url": None,
        "added_at": _now(),
        "updated_at": _now(),
    }
    return True


def set_status(state: dict, video_id: str, status: str) -> None:
    """Advance a video's status. Never downgrades (use --force at the call site
    to re-run a step; the script clears downstream state explicitly if needed).
    """
    if status not in STATUS_ORDER:
        raise ValueError(f"Unknown status: {status!r}")
    video = state["videos"][video_id]
    if status_rank(status) < status_rank(video.get("status", "pending")):
        # Caller is intentionally moving backwards (e.g. --force); allow it but
        # require it to be explicit by going through update_video instead.
        return
    video["status"] = status
    video["updated_at"] = _now()


def update_video(state: dict, video_id: str, **fields) -> None:
    """Patch arbitrary fields on a video entry and bump updated_at.

    Use force_status=True semantics by passing status here; this does NOT guard
    against downgrades (intended for --force re-runs).
    """
    video = state["videos"][video_id]
    video.update(fields)
    video["updated_at"] = _now()


def next_with_status(state: dict, status: str) -> Optional[str]:
    """Return the first video_id with the given status, ordered by added_at."""
    candidates = [
        (vid, v)
        for vid, v in state.get("videos", {}).items()
        if v.get("status") == status
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda kv: kv[1].get("added_at", ""))
    return candidates[0][0]


def get(state: dict, video_id: str) -> dict:
    """Return a video entry or raise a clear error."""
    videos = state.get("videos", {})
    if video_id not in videos:
        raise KeyError(
            f"Video {video_id!r} is not in state.json. Run fetch_playlist.py first."
        )
    return videos[video_id]
