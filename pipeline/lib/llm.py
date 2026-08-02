"""LLM wrapper (PRD §7.4 / §7.5) — provider-agnostic.

Supports multiple providers behind one `complete()` call:
  - anthropic (Claude)  -> ANTHROPIC_API_KEY / ANTHROPIC_MODEL
  - openai   (GPT)      -> OPENAI_API_KEY   / OPENAI_MODEL

Which provider is used is resolved (in priority order) from:
  1. an explicit `provider=` argument,
  2. a `provider:model` model spec (e.g. "openai:gpt-4o", "anthropic:claude-opus-4-8"),
  3. inference from the model name (gpt*/o1*/o3* -> openai, claude* -> anthropic),
  4. the LLM_PROVIDER env var (default "anthropic").

Callers (generate.py, make_style_guide.py) need no changes: with no model/provider
they get the configured default provider + model.
"""

from __future__ import annotations

from . import config

PROVIDERS = ("anthropic", "openai")


def _infer_provider(model: str) -> str:
    """Guess the provider from a bare model name; fall back to the env default."""
    m = model.lower()
    if m.startswith(("gpt", "o1", "o3", "o4", "chatgpt", "text-", "davinci")):
        return "openai"
    if m.startswith("claude"):
        return "anthropic"
    return config.llm_provider()


def resolve_provider_model(
    model: str | None = None, provider: str | None = None
) -> tuple[str, str]:
    """Return (provider, model_id) from an optional model/provider.

    A model may be written as "provider:model" to force a provider explicitly.
    """
    # 1. Explicit "provider:model" spec wins.
    if model and ":" in model:
        head, _, tail = model.partition(":")
        if head.lower() in PROVIDERS and tail:
            return head.lower(), tail

    # 2. Explicit provider arg, else infer from model name, else env default.
    if provider:
        prov = provider.lower()
    elif model:
        prov = _infer_provider(model)
    else:
        prov = config.llm_provider()

    if prov not in PROVIDERS:
        raise RuntimeError(
            f"Unknown LLM provider {prov!r}. Supported: {', '.join(PROVIDERS)}."
        )

    # 3. Default model for the provider when none was given.
    if not model:
        model = config.openai_model() if prov == "openai" else config.anthropic_model()
    return prov, model


def complete(
    prompt: str,
    *,
    model: str | None = None,
    provider: str | None = None,
    max_tokens: int = 8000,
    temperature: float = 0.7,
) -> str:
    """Run a single-turn completion and return the text content.

    `model`/`provider` override the env defaults (used by the A/B compare tool
    and for per-call switching). Raises RuntimeError on failure so callers can
    fail without opening a PR.
    """
    prov, model = resolve_provider_model(model, provider)
    if prov == "openai":
        return _complete_openai(prompt, model, max_tokens, temperature)
    return _complete_anthropic(prompt, model, max_tokens, temperature)


# --------------------------------------------------------------------------- #
# Anthropic
# --------------------------------------------------------------------------- #
def _complete_anthropic(prompt: str, model: str, max_tokens: int, temperature: float) -> str:
    api_key = config.require(
        "ANTHROPIC_API_KEY",
        hint="Create a key at https://console.anthropic.com/settings/keys",
    )
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
    except Exception as exc:
        msg = str(exc)
        # Some newer models (e.g. claude-opus-4-8) reject `temperature`. Drop it
        # and retry once so the pipeline stays model-agnostic.
        if "temperature" in msg and ("deprecated" in msg or "unsupported" in msg):
            params.pop("temperature", None)
            try:
                resp = client.messages.create(**params)
            except Exception as exc2:
                raise RuntimeError(f"Anthropic API call failed ({model}): {exc2}") from exc2
        else:
            raise RuntimeError(f"Anthropic API call failed ({model}): {exc}") from exc

    parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
    text = "".join(parts).strip()
    if not text:
        raise RuntimeError("Anthropic returned an empty response.")
    return text


# --------------------------------------------------------------------------- #
# OpenAI
# --------------------------------------------------------------------------- #
def _complete_openai(prompt: str, model: str, max_tokens: int, temperature: float) -> str:
    api_key = config.require(
        "OPENAI_API_KEY",
        hint="Create a key at https://platform.openai.com/api-keys",
    )
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The 'openai' package is not installed. Run: pip install openai"
        ) from exc

    client = OpenAI(api_key=api_key)
    # The reasoning models (o1/o3/o4, gpt-5 family) use `max_completion_tokens`
    # and reject a custom `temperature`; we retry adapting to those constraints.
    params = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }

    def _call(p: dict):
        return client.chat.completions.create(**p)

    try:
        resp = _call(params)
    except Exception as exc:
        msg = str(exc).lower()
        changed = False
        if "max_tokens" in msg and "max_completion_tokens" in msg:
            params["max_completion_tokens"] = params.pop("max_tokens")
            changed = True
        if "temperature" in msg and ("unsupported" in msg or "does not support" in msg):
            params.pop("temperature", None)
            changed = True
        if not changed:
            raise RuntimeError(f"OpenAI API call failed ({model}): {exc}") from exc
        try:
            resp = _call(params)
        except Exception as exc2:
            raise RuntimeError(f"OpenAI API call failed ({model}): {exc2}") from exc2

    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("OpenAI returned an empty response.")
    return text
