"""Anthropic (Claude) wrapper (PRD §7.4 / §7.5).

Thin client around the Anthropic Messages API. Model is configurable via
ANTHROPIC_MODEL (defaults to claude-sonnet-4-6).
"""

from __future__ import annotations

from . import config


def complete(prompt: str, *, max_tokens: int = 8000, temperature: float = 0.7) -> str:
    """Run a single-turn completion and return the text content.

    Raises RuntimeError on API failure so callers can fail without opening a PR.
    """
    api_key = config.require(
        "ANTHROPIC_API_KEY",
        hint="Create a key at https://console.anthropic.com/settings/keys",
    )
    model = config.anthropic_model()

    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The 'anthropic' package is not installed. Run: pip install anthropic"
        ) from exc

    client = anthropic.Anthropic(api_key=api_key)
    params = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        resp = client.messages.create(**params)
    except Exception as exc:  # surface API errors with context
        msg = str(exc)
        # Some newer models (e.g. claude-opus-4-8) reject `temperature`. Drop it
        # and retry once so the pipeline stays model-agnostic.
        if "temperature" in msg and ("deprecated" in msg or "unsupported" in msg):
            params.pop("temperature", None)
            try:
                resp = client.messages.create(**params)
            except Exception as exc2:
                raise RuntimeError(
                    f"Anthropic API call failed ({model}): {exc2}"
                ) from exc2
        else:
            raise RuntimeError(f"Anthropic API call failed ({model}): {exc}") from exc

    # Concatenate any text blocks in the response.
    parts = [block.text for block in resp.content if getattr(block, "type", "") == "text"]
    text = "".join(parts).strip()
    if not text:
        raise RuntimeError("Anthropic returned an empty response.")
    return text
