"""Environment variable helpers for MagicReview."""

from __future__ import annotations

import os


NEW_PREFIX = "MGREVIEW_"


def get_env(name: str, default: str | None = None) -> str | None:
    """Return a MagicReview environment variable."""

    suffix = name.removeprefix(NEW_PREFIX)
    return os.getenv(f"{NEW_PREFIX}{suffix}", default)


def env_bool(name: str, default: bool = False) -> bool:
    value = get_env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = get_env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default
