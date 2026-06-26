#!/usr/bin/env python3
"""clip.py (PRD §7.3)

Cut a short, silent, web-optimized hero clip from the source video.

  <video_id> --start <ms|timestamp> --end <ms|timestamp> --slug <slug>

Produces public/clips/<slug>.{mp4,webm,jpg}:
  - MP4  (H.264, +faststart, silent)
  - WebM (VP9, silent)
  - poster JPG (first frame)

Duration is capped (default 6s) and audio is always stripped. Width target 720px.
Runnable standalone or invoked by generate.py.

Usage:
  python pipeline/clip.py <id> --start 01:23 --end 01:28 --slug my-slug
  python pipeline/clip.py <id> --start 83000 --end 88000 --slug my-slug   # ms
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import REPO_ROOT  # noqa: E402

WORK_DIR = REPO_ROOT / "work"
CLIPS_DIR = REPO_ROOT / "public" / "clips"

MAX_DURATION_S = 6.0
TARGET_WIDTH = 720


def parse_time_to_seconds(value: str) -> float:
    """Accept milliseconds ('88000'), 'MM:SS', or 'HH:MM:SS' -> seconds (float)."""
    value = value.strip()
    if ":" in value:
        parts = [float(p) for p in value.split(":")]
        if len(parts) == 2:
            m, s = parts
            return m * 60 + s
        if len(parts) == 3:
            h, m, s = parts
            return h * 3600 + m * 60 + s
        raise ValueError(f"Unrecognized timestamp: {value!r}")
    # Bare number => milliseconds.
    return float(value) / 1000.0


def video_duration_seconds(video_id: str) -> float | None:
    """Best-effort source duration via yt-dlp; None if unavailable."""
    try:
        out = subprocess.run(
            ["yt-dlp", "--print", "%(duration)s", "--skip-download",
             f"https://www.youtube.com/watch?v={video_id}"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        return float(out) if out and out != "NA" else None
    except Exception:
        return None


def download_segment(video_id: str, start_s: float, end_s: float) -> Path:
    """Download just the needed segment with yt-dlp --download-sections."""
    WORK_DIR.mkdir(exist_ok=True)
    # Clear any stale segment from a prior run so the glob below is unambiguous.
    for stale in WORK_DIR.glob(f"{video_id}_clip.*"):
        stale.unlink()
    out_tmpl = str(WORK_DIR / f"{video_id}_clip.%(ext)s")
    section = f"*{start_s:.3f}-{end_s:.3f}"
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=1080]+bestaudio/best",
        "--download-sections", section,
        "--force-keyframes-at-cuts",
        "-o", out_tmpl,
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("yt-dlp is not installed. Run: pip install yt-dlp") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Segment download failed.\n  stderr: {exc.stderr.strip()}"
        ) from exc

    matches = [
        m for m in WORK_DIR.glob(f"{video_id}_clip.*")
        if m.suffix.lower() in (".mp4", ".mkv", ".webm")
    ]
    if not matches:
        raise RuntimeError("Downloaded segment file not found.")
    # Freshest file wins (handles muxed container variations).
    return max(matches, key=lambda p: p.stat().st_mtime)


def _run_ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-y", *args]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is not installed.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"ffmpeg failed.\n  command: {' '.join(cmd)}\n  stderr: {exc.stderr.strip()}"
        ) from exc


def encode_clips(src: Path, slug: str, duration_s: float) -> dict:
    """Encode silent MP4 + WebM + poster JPG from the downloaded segment."""
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    mp4 = CLIPS_DIR / f"{slug}.mp4"
    webm = CLIPS_DIR / f"{slug}.webm"
    poster = CLIPS_DIR / f"{slug}.jpg"

    scale = f"scale={TARGET_WIDTH}:-2"

    # MP4 (H.264), silent, faststart for progressive web playback.
    _run_ffmpeg([
        "-i", str(src),
        "-t", f"{duration_s:.3f}",
        "-an",
        "-vf", scale,
        "-c:v", "libx264",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-crf", "26",
        "-preset", "slow",
        "-movflags", "+faststart",
        str(mp4),
    ])

    # WebM (VP9), silent.
    _run_ffmpeg([
        "-i", str(src),
        "-t", f"{duration_s:.3f}",
        "-an",
        "-vf", scale,
        "-c:v", "libvpx-vp9",
        "-crf", "34",
        "-b:v", "0",
        "-row-mt", "1",
        str(webm),
    ])

    # Poster JPG from the first frame.
    _run_ffmpeg([
        "-i", str(src),
        "-vf", scale,
        "-frames:v", "1",
        "-q:v", "3",
        str(poster),
    ])

    return {"mp4": mp4, "webm": webm, "poster": poster}


def make_clip(video_id: str, start: str, end: str, slug: str) -> dict:
    """Public entry point used by generate.py. Returns frontmatter-relative paths."""
    start_s = parse_time_to_seconds(start)
    end_s = parse_time_to_seconds(end)

    if end_s <= start_s:
        raise ValueError(f"--end ({end_s}s) must be after --start ({start_s}s).")

    # Clamp against the source duration if we can determine it.
    src_dur = video_duration_seconds(video_id)
    if src_dur is not None:
        if start_s >= src_dur:
            raise ValueError(
                f"--start ({start_s}s) is past end of video ({src_dur}s)."
            )
        if end_s > src_dur:
            print(f"WARNING: clamping --end {end_s}s to video length {src_dur}s.")
            end_s = src_dur

    # Cap the duration.
    duration_s = end_s - start_s
    if duration_s > MAX_DURATION_S:
        print(f"WARNING: capping clip duration {duration_s:.1f}s -> {MAX_DURATION_S}s.")
        duration_s = MAX_DURATION_S
        end_s = start_s + duration_s

    src = download_segment(video_id, start_s, end_s)
    out = encode_clips(src, slug, duration_s)

    mp4_mb = out["mp4"].stat().st_size / 1_048_576
    print(f"Encoded hero clip for '{slug}' ({duration_s:.1f}s):")
    print(f"  {out['mp4'].name}  ({mp4_mb:.2f} MB)")
    print(f"  {out['webm'].name}")
    print(f"  {out['poster'].name}")
    if mp4_mb > 2.0:
        print(f"  WARNING: MP4 is {mp4_mb:.2f} MB (target < 2 MB).")

    return {
        "mp4": f"/clips/{slug}.mp4",
        "webm": f"/clips/{slug}.webm",
        "poster": f"/clips/{slug}.jpg",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Cut a silent web-optimized hero clip.")
    parser.add_argument("video_id")
    parser.add_argument("--start", required=True, help="ms or MM:SS / HH:MM:SS")
    parser.add_argument("--end", required=True, help="ms or MM:SS / HH:MM:SS")
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()

    try:
        make_clip(args.video_id, args.start, args.end, args.slug)
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
