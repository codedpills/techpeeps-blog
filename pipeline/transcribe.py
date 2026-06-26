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
from lib import assemblyai, config, state  # noqa: E402
from lib.config import REPO_ROOT  # noqa: E402

WORK_DIR = REPO_ROOT / "work"
TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"

# Words that signal an interviewer question — used in the HOST heuristic.
QUESTION_WORDS = (
    "who", "what", "when", "where", "why", "how", "tell me", "tell us",
    "can you", "could you", "what's", "how's", "do you", "did you",
    "would you", "talk to me", "walk me through", "describe",
)

# Phrases the HOST uses to frame/open the show (strong HOST signal).
HOST_INTRO_MARKERS = (
    "welcome to", "welcome back", "another episode", "on this show",
    "on the show", "today we have", "today i have", "today my guest",
    "today on the", "joining me", "joining us", "my guest", "our guest",
    "tell us about yourself", "introduce yourself", "tech peeps diaspora",
    "conversations with", "tuning in", "let's get into", "let's dive in",
    "let's jump in",
)

# Phrases the GUEST uses (strong GUEST signal -> the OTHER speaker is HOST).
GUEST_MARKERS = (
    "for having me", "having me on", "pleasure to be here", "happy to be here",
    "glad to be here", "excited to be here", "thanks for having",
    "thank you for having",
)


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def download_audio(video_id: str) -> Path:
    """Download audio as mp3 into work/<id>.mp3. Raises on failure."""
    WORK_DIR.mkdir(exist_ok=True)
    out_tmpl = str(WORK_DIR / f"{video_id}.%(ext)s")
    cmd = [
        *config.ytdlp_cmd(),
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


def _question_signal(text: str) -> float:
    """Question-ness of a chunk: '?' marks plus a light weight on question words
    (helps when the ASR drops question marks)."""
    t = text.lower()
    return t.count("?") * 1.0 + sum(t.count(w) for w in QUESTION_WORDS) * 0.3


def _count_markers(text: str, markers: tuple[str, ...]) -> int:
    t = text.lower()
    return sum(t.count(m) for m in markers)


def map_speakers(utterances: list[assemblyai.Utterance]) -> tuple[dict[str, str], str]:
    """Map raw speaker labels -> HOST/GUEST.

    Heuristic (PRD §3 / §14). Critically, the interviewer (HOST) speaks *less*
    overall but asks proportionally more questions, and frames the show with
    intro phrases ("welcome to ... on this show"), while the GUEST gives long
    answers and says things like "thank you for having me". We therefore weigh
    several length-normalized signals rather than raw counts or first-speaker
    (which fails on cold-open teaser clips of the guest):

      - question DENSITY (questions per word)   -> higher = HOST
      - total words                              -> fewer  = HOST
      - host intro markers                       -> more   = HOST   (strong)
      - guest markers                            -> more   = GUEST  (strong)

    Confidence is 'high' only when a strong content marker (intro or guest
    phrase) is present AND the combined vote margin is decisive; otherwise
    'low' so a human confirms/flips it during review.
    """
    raw_labels: list[str] = []
    for u in utterances:
        if u.speaker not in raw_labels:
            raw_labels.append(u.speaker)

    first_speaker = utterances[0].speaker

    # Not exactly two speakers: keep transcript but flag loudly.
    if len(raw_labels) != 2:
        mapping = {first_speaker: "HOST"}
        for lbl in raw_labels:
            mapping.setdefault(lbl, "GUEST")  # collapse extras into GUEST
        return mapping, "low"

    a, b = raw_labels
    words: dict[str, int] = {a: 0, b: 0}
    qsig: dict[str, float] = {a: 0.0, b: 0.0}
    intro: dict[str, int] = {a: 0, b: 0}
    guest: dict[str, int] = {a: 0, b: 0}
    for u in utterances:
        sp = u.speaker
        words[sp] += len(u.text.split())
        qsig[sp] += _question_signal(u.text)
        intro[sp] += _count_markers(u.text, HOST_INTRO_MARKERS)
        guest[sp] += _count_markers(u.text, GUEST_MARKERS)

    density = {sp: qsig[sp] / max(words[sp], 1) for sp in raw_labels}

    # Weighted votes toward each speaker being HOST.
    votes: dict[str, float] = {a: 0.0, b: 0.0}
    # 1. Question density (interviewer asks proportionally more).
    votes[max(raw_labels, key=lambda s: density[s])] += 1.5
    # 2. Fewer words (interviewer speaks less).
    votes[min(raw_labels, key=lambda s: words[s])] += 1.0
    # 3. Host intro markers (strong).
    has_intro = intro[a] != intro[b]
    if has_intro:
        votes[max(raw_labels, key=lambda s: intro[s])] += 3.0
    # 4. Guest markers (strong) -> the OTHER speaker is HOST.
    has_guest = guest[a] != guest[b]
    if has_guest:
        guesty = max(raw_labels, key=lambda s: guest[s])
        votes[b if guesty == a else a] += 3.0

    host_raw = max(raw_labels, key=lambda s: votes[s])
    guest_raw = b if host_raw == a else a

    strong = has_intro or has_guest
    margin = abs(votes[a] - votes[b])
    confidence = "high" if (strong and margin >= 2.0) else "low"

    return {host_raw: "HOST", guest_raw: "GUEST"}, confidence


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


def remap_transcript(path: Path) -> tuple[str, str, str]:
    """Re-run the HOST/GUEST heuristic on an EXISTING transcript JSON (no audio
    download, no API). Rewrites the file in place. Returns (host_raw, guest_raw,
    confidence)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    utts = [
        assemblyai.Utterance(
            speaker=s["raw_speaker"],
            start_ms=s["start_ms"],
            end_ms=s["end_ms"],
            text=s["text"],
        )
        for s in data["segments"]
    ]
    mapping, confidence = map_speakers(utts)
    for s in data["segments"]:
        s["speaker"] = mapping.get(s["raw_speaker"], "GUEST")
    data["mapping_confidence"] = confidence
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    host_raw = next((r for r, lab in mapping.items() if lab == "HOST"), "?")
    guest_raw = next((r for r, lab in mapping.items() if lab == "GUEST"), "?")
    return host_raw, guest_raw, confidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe + diarize one video.")
    parser.add_argument("video_id", nargs="?", help="YouTube video id.")
    parser.add_argument("--next", action="store_true", help="Pick first 'pending'.")
    parser.add_argument("--force", action="store_true", help="Re-transcribe.")
    parser.add_argument(
        "--remap", action="store_true",
        help="Re-run HOST/GUEST mapping on existing transcript(s); no API cost. "
        "With no video_id, remaps every transcript in transcripts/.",
    )
    args = parser.parse_args()

    if args.remap:
        if args.video_id:
            paths = [TRANSCRIPTS_DIR / f"{args.video_id}.json"]
        else:
            paths = sorted(TRANSCRIPTS_DIR.glob("*.json"))
        if not paths or (args.video_id and not paths[0].exists()):
            print("ERROR: no transcript(s) found to remap.", file=sys.stderr)
            return 1
        for p in paths:
            if not p.exists():
                print(f"  skip (missing): {p}")
                continue
            host, guest, conf = remap_transcript(p)
            flag = "  ⚠️ verify" if conf == "low" else ""
            print(f"  {p.stem}: HOST={host} GUEST={guest} confidence={conf}{flag}")
        return 0

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
