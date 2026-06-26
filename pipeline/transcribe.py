#!/usr/bin/env python3
"""transcribe.py (PRD §7.2)

<video_id> (or --next) -> diarized transcript JSON in transcripts/<id>.json.

Steps:
  1. Download audio with yt-dlp (mp3) into work/.
  2. Transcribe via AssemblyAI with speaker_labels=true, speakers_expected=2.
  3. Normalize to the §6.2 schema, mapping raw A/B -> HOST/GUEST via heuristic.
  4. Save transcript; advance status to 'transcribed'.

On any download/API failure: leave status 'pending', exit non-zero, print an
actionable message, and do NOT write a partial transcript.

Usage:
  python pipeline/transcribe.py <video_id>
  python pipeline/transcribe.py --next
  python pipeline/transcribe.py <video_id> --force
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import assemblyai, state  # noqa: E402
from lib.config import REPO_ROOT  # noqa: E402

WORK_DIR = REPO_ROOT / "work"
TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"

# Words that signal an interviewer question — used in the HOST heuristic.
QUESTION_WORDS = (
    "who", "what", "when", "where", "why", "how", "tell me", "tell us",
    "can you", "could you", "what's", "how's", "do you", "did you",
    "would you", "talk to me", "walk me through", "describe",
)


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def download_audio(video_id: str) -> Path:
    """Download audio as mp3 into work/<id>.mp3. Raises on failure."""
    WORK_DIR.mkdir(exist_ok=True)
    out_tmpl = str(WORK_DIR / f"{video_id}.%(ext)s")
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format",
        "mp3",
        "-o",
        out_tmpl,
        watch_url(video_id),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("yt-dlp is not installed. Run: pip install yt-dlp") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Audio download failed (video may be private, age-restricted, or "
            f"removed).\n  stderr: {exc.stderr.strip()}"
        ) from exc

    mp3 = WORK_DIR / f"{video_id}.mp3"
    if not mp3.exists():
        raise RuntimeError(f"Expected audio file not found: {mp3}")
    return mp3


def _question_score(text: str) -> float:
    """Heuristic: how question-like a chunk of speech is (0..1-ish)."""
    t = text.lower()
    marks = t.count("?")
    starts = sum(t.count(w) for w in QUESTION_WORDS)
    return marks * 1.5 + starts * 0.5


def map_speakers(utterances: list[assemblyai.Utterance]) -> tuple[dict[str, str], str]:
    """Map raw speaker labels -> HOST/GUEST.

    Heuristic (PRD §3 / §14): the host typically speaks first and asks the
    questions. Combine 'who spoke first' with 'who asks more questions'.
    Returns (mapping, confidence) where confidence is 'high' | 'low'.
    """
    raw_labels = []
    for u in utterances:
        if u.speaker not in raw_labels:
            raw_labels.append(u.speaker)

    # Aggregate a question score per raw speaker.
    scores: dict[str, float] = {lbl: 0.0 for lbl in raw_labels}
    for u in utterances:
        scores[u.speaker] = scores.get(u.speaker, 0.0) + _question_score(u.text)

    first_speaker = utterances[0].speaker

    # Exactly two speakers is the expected case.
    if len(raw_labels) == 2:
        a, b = raw_labels[0], raw_labels[1]
        question_host = max(scores, key=scores.get)
        # Agreement between the two signals => high confidence.
        if first_speaker == question_host:
            host_raw = first_speaker
            confidence = "high"
        else:
            # Signals disagree: default to first-speaker = HOST, flag low.
            host_raw = first_speaker
            confidence = "low"
        guest_raw = b if host_raw == a else a
        return {host_raw: "HOST", guest_raw: "GUEST"}, confidence

    # Not exactly two speakers: keep transcript but flag loudly.
    mapping: dict[str, str] = {}
    host_raw = first_speaker
    mapping[host_raw] = "HOST"
    for lbl in raw_labels:
        if lbl != host_raw:
            mapping[lbl] = "GUEST"  # collapse extras into GUEST; human fixes in PR
    return mapping, "low"


def build_transcript_json(
    video_id: str,
    title: str,
    tr: assemblyai.Transcription,
) -> dict:
    mapping, confidence = map_speakers(tr.utterances)
    segments = [
        {
            "speaker": mapping.get(u.speaker, "GUEST"),
            "raw_speaker": u.speaker,
            "start_ms": u.start_ms,
            "end_ms": u.end_ms,
            "text": u.text,
        }
        for u in tr.utterances
    ]
    return {
        "video_id": video_id,
        "title": title,
        "duration_sec": tr.audio_duration_sec,
        "speakers_detected": tr.speakers_detected,
        "segments": segments,
        "mapping_confidence": confidence,
        "candidate_clip_windows": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe + diarize one video.")
    parser.add_argument("video_id", nargs="?", help="YouTube video id.")
    parser.add_argument("--next", action="store_true", help="Pick first 'pending'.")
    parser.add_argument("--force", action="store_true", help="Re-transcribe.")
    args = parser.parse_args()

    st = state.load()

    if args.next:
        video_id = state.next_with_status(st, "pending")
        if not video_id:
            print("No videos with status 'pending'. Nothing to do.")
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

    TRANSCRIPTS_DIR.mkdir(exist_ok=True)
    out_path = TRANSCRIPTS_DIR / f"{video_id}.json"

    if out_path.exists() and not args.force:
        print(f"Transcript already exists: {out_path} (use --force to redo). Skipping.")
        # Ensure status is at least 'transcribed'.
        if state.status_rank(video["status"]) < state.status_rank("transcribed"):
            state.set_status(st, video_id, "transcribed")
            state.save(st)
        return 0

    print(f"Transcribing {video_id} — {video.get('title', '')}")
    try:
        audio = download_audio(video_id)
        tr = assemblyai.transcribe_file(audio, speakers_expected=2)
    except SystemExit:
        # Missing required env var (config.require already printed the reason).
        print("Status left at 'pending'. No transcript written.", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Status left at 'pending'. No transcript written.", file=sys.stderr)
        return 1

    data = build_transcript_json(video_id, video.get("title", ""), tr)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    if args.force:
        # A forced re-transcribe changes content; reset downstream status so the
        # post is re-drafted and re-reviewed rather than silently diverging.
        state.update_video(st, video_id, status="transcribed")
    else:
        state.set_status(st, video_id, "transcribed")
    state.save(st)

    print(f"Wrote {out_path}")
    print(f"  speakers detected: {data['speakers_detected']}")
    print(f"  mapping confidence: {data['mapping_confidence']}")
    if data["mapping_confidence"] == "low":
        print("  WARNING: HOST/GUEST mapping is LOW confidence — verify in the PR.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
