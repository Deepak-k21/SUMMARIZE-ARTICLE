"""Runtime configuration, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - misconfiguration
        raise ValueError(f"Environment variable {name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    model: str
    effort: str
    max_input_chars: int
    fetch_timeout_seconds: int
    fetch_max_bytes: int

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        model=os.getenv("SUMMARIZER_MODEL", "claude-opus-5-5"),
        effort=os.getenv("SUMMARIZER_EFFORT", "medium"),
        max_input_chars=_int("SUMMARIZER_MAX_INPUT_CHARS", 200_000),
        fetch_timeout_seconds=_int("SUMMARIZER_FETCH_TIMEOUT", 15),
        fetch_max_bytes=_int("SUMMARIZER_FETCH_MAX_BYTES", 5_000_000),
    )
