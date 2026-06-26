"""AssemblyAI transcription + diarization wrapper (PRD §7.2).

Transcribes an audio file with speaker labels on and speakers pinned to 2,
then exposes the raw utterances for normalization in transcribe.py.

Uses the `assemblyai` SDK if installed; otherwise falls back to the REST API
via `requests` so the pipeline does not hard-depend on the SDK version.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from . import config


@dataclass
class Utterance:
    speaker: str  # raw AssemblyAI label, e.g. "A" / "B"
    start_ms: int
    end_ms: int
    text: str


@dataclass
class Transcription:
    utterances: List[Utterance]
    audio_duration_sec: int
    speakers_detected: int


def transcribe_file(audio_path: Path, *, speakers_expected: int = 2) -> Transcription:
    """Upload + transcribe a local audio file with 2-speaker diarization.

    Raises RuntimeError with an actionable message on API failure so the caller
    can leave the video status at 'pending'.
    """
    api_key = config.require(
        "ASSEMBLYAI_API_KEY",
        hint="Create a key at https://www.assemblyai.com/app/account",
    )

    try:
        return _transcribe_with_sdk(api_key, audio_path, speakers_expected)
    except ImportError:
        return _transcribe_with_rest(api_key, audio_path, speakers_expected)


def _transcribe_with_sdk(
    api_key: str, audio_path: Path, speakers_expected: int
) -> Transcription:
    import assemblyai as aai  # may raise ImportError -> REST fallback

    aai.settings.api_key = api_key
    cfg = aai.TranscriptionConfig(
        speaker_labels=True,
        speakers_expected=speakers_expected,
    )
    transcript = aai.Transcriber().transcribe(str(audio_path), config=cfg)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI transcription failed: {transcript.error}")

    utterances = [
        Utterance(
            speaker=str(u.speaker),
            start_ms=int(u.start),
            end_ms=int(u.end),
            text=u.text.strip(),
        )
        for u in (transcript.utterances or [])
    ]
    if not utterances:
        raise RuntimeError(
            "AssemblyAI returned no speaker utterances. Diarization may have failed."
        )
    duration = int(getattr(transcript, "audio_duration", 0) or 0)
    speakers = len({u.speaker for u in utterances})
    return Transcription(utterances, duration, speakers)


def _transcribe_with_rest(
    api_key: str, audio_path: Path, speakers_expected: int
) -> Transcription:
    """Minimal REST implementation (upload -> create -> poll)."""
    import time

    import requests

    base = "https://api.assemblyai.com/v2"
    headers = {"authorization": api_key}

    # 1. Upload the audio bytes.
    with audio_path.open("rb") as fh:
        up = requests.post(f"{base}/upload", headers=headers, data=fh, timeout=600)
    up.raise_for_status()
    upload_url = up.json()["upload_url"]

    # 2. Request transcription with diarization pinned to 2 speakers.
    create = requests.post(
        f"{base}/transcript",
        headers=headers,
        json={
            "audio_url": upload_url,
            "speaker_labels": True,
            "speakers_expected": speakers_expected,
        },
        timeout=60,
    )
    create.raise_for_status()
    tid = create.json()["id"]

    # 3. Poll until complete.
    while True:
        poll = requests.get(f"{base}/transcript/{tid}", headers=headers, timeout=60)
        poll.raise_for_status()
        body = poll.json()
        status = body["status"]
        if status == "completed":
            break
        if status == "error":
            raise RuntimeError(f"AssemblyAI transcription failed: {body.get('error')}")
        time.sleep(5)

    utterances = [
        Utterance(
            speaker=str(u["speaker"]),
            start_ms=int(u["start"]),
            end_ms=int(u["end"]),
            text=(u.get("text") or "").strip(),
        )
        for u in (body.get("utterances") or [])
    ]
    if not utterances:
        raise RuntimeError(
            "AssemblyAI returned no speaker utterances. Diarization may have failed."
        )
    duration = int(body.get("audio_duration") or 0)
    speakers = len({u.speaker for u in utterances})
    return Transcription(utterances, duration, speakers)
