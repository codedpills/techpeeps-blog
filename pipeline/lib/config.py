"""Environment / secret loading (PRD §10).

Secrets are read from env only. Loads a .env at repo root if python-dotenv is
available, then exposes a `require()` helper that fails with a clear, actionable
message when a key is missing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Load .env at repo root if python-dotenv is installed. The pipeline still works
# if vars are exported directly into the environment.
try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass


class ConfigError(SystemExit):
    """Raised (as a clean exit) when required configuration is missing."""


def require(key: str, *, hint: str = "") -> str:
    """Return env[key] or exit(1) with an actionable message."""
    val = os.environ.get(key, "").strip()
    if not val:
        msg = f"ERROR: required environment variable {key} is not set."
        if hint:
            msg += f"\n  -> {hint}"
        msg += "\n  See .env.example and copy it to .env."
        print(msg, file=sys.stderr)
        raise ConfigError(1)
    return val


def get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip() or default


def anthropic_model() -> str:
    return get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
