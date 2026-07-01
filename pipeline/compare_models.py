#!/usr/bin/env python3
"""compare_models.py — A/B two LLMs on the SAME transcript for prose comparison.

Generates the feature-profile article from a transcript with two models and
writes each result to work/compare/ so you can read them side by side. Does NOT
touch git, does NOT cut a clip, does NOT open a PR — it's purely for choosing a
model. Nothing it writes is committed (work/ is gitignored).

Usage:
  python pipeline/compare_models.py <video_id>
  python pipeline/compare_models.py <video_id> --models claude-opus-4-8,claude-sonnet-4-6
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate  # reuse transcript formatting + output splitting  # noqa: E402
from lib import config, llm, prompts, state  # noqa: E402
from lib.config import REPO_ROOT  # noqa: E402

TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"
STYLE_GUIDE_PATH = REPO_ROOT / "style-guide.md"
OUT_DIR = REPO_ROOT / "work" / "compare"

DEFAULT_MODELS = ["claude-opus-4-8", "claude-sonnet-4-6"]


def main() -> int:
    ap = argparse.ArgumentParser(description="A/B two models on one transcript.")
    ap.add_argument("video_id")
    ap.add_argument("--models", help="Comma-separated model ids (default opus,sonnet).")
    args = ap.parse_args()

    if not args.video_id:
        print("ERROR: provide a <video_id>.", file=sys.stderr)
        return 1
    models = (
        [m.strip() for m in args.models.split(",")] if args.models else DEFAULT_MODELS
    )

    tpath = TRANSCRIPTS_DIR / f"{args.video_id}.json"
    if not tpath.exists():
        print(f"ERROR: transcript missing: {tpath}. Run transcribe first.",
              file=sys.stderr)
        return 1
    transcript = json.loads(tpath.read_text(encoding="utf-8"))

    style_guide = (
        STYLE_GUIDE_PATH.read_text(encoding="utf-8")
        if STYLE_GUIDE_PATH.exists()
        else "(No style guide yet.)"
    )

    st = state.load()
    guest = ""
    try:
        guest = state.get(st, args.video_id).get("guest") or ""
    except KeyError:
        pass

    prompt = prompts.feature_profile_prompt(
        host_name=config.get("HOST_NAME", "the host"),
        guest_name=guest,
        guest_bio=None,
        style_guide=style_guide,
        transcript=generate.format_transcript(transcript),
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for model in models:
        print(f"Generating with {model}…")
        try:
            out = llm.complete(prompt, model=model, max_tokens=8000, temperature=0.7)
        except RuntimeError as exc:
            print(f"  ERROR ({model}): {exc}", file=sys.stderr)
            continue
        # Keep just the article (frontmatter + body), drop the CLIP_CANDIDATES JSON.
        article, _ = generate.split_output(out)
        safe_model = model.replace("/", "_")
        path = OUT_DIR / f"{args.video_id}__{safe_model}.md"
        path.write_text(article + "\n", encoding="utf-8")
        written.append(path)
        print(f"  wrote {path}")

    if not written:
        print("No outputs produced.", file=sys.stderr)
        return 1

    print("\nCompare the files above side by side. Nothing was committed or pushed.")
    print("To use a model for real runs, set ANTHROPIC_MODEL in .env and run "
          "`make generate ID=<id> FORCE=1`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
