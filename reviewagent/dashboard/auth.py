"""Authentication helpers for the ReviewAgent dashboard."""

from __future__ import annotations

import base64
import hmac
import os
from dataclasses import dataclass
from urllib.parse import quote


AUTH_SESSION_KEY = "reviewagent_authenticated"
AUTH_USER_KEY = "reviewagent_username"


@dataclass(frozen=True)
class AuthConfig:
    enabled: bool
    admin_username: str
    admin_password: str
    session_secret: str
    api_keys: tuple[str, ...]
    cookie_secure: bool
    basic_auth_enabled: bool


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_auth_config() -> AuthConfig:
    keys = tuple(
        key.strip()
        for key in os.getenv("REVIEWAGENT_API_KEYS", "").split(",")
        if key.strip()
    )
    return AuthConfig(
        enabled=_env_bool("REVIEWAGENT_AUTH_ENABLED", False),
        admin_username=os.getenv("REVIEWAGENT_ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("REVIEWAGENT_ADMIN_PASSWORD", ""),
        session_secret=os.getenv("REVIEWAGENT_SESSION_SECRET", ""),
        api_keys=keys,
        cookie_secure=_env_bool("REVIEWAGENT_COOKIE_SECURE", False),
        basic_auth_enabled=_env_bool("REVIEWAGENT_BASIC_AUTH_ENABLED", False),
    )


def session_secret() -> str:
    configured = os.getenv("REVIEWAGENT_SESSION_SECRET", "")
    return configured or "reviewagent-local-session-secret-change-me"


def is_valid_login(username: str, password: str, config: AuthConfig | None = None) -> bool:
    cfg = config or load_auth_config()
    if not cfg.admin_password:
        return False
    return hmac.compare_digest(username, cfg.admin_username) and hmac.compare_digest(
        password,
        cfg.admin_password,
    )


def is_valid_api_key(token: str, config: AuthConfig | None = None) -> bool:
    cfg = config or load_auth_config()
    return any(hmac.compare_digest(token, configured) for configured in cfg.api_keys)


def parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def parse_basic_auth(authorization: str | None) -> tuple[str, str] | None:
    if not authorization:
        return None
    scheme, _, encoded = authorization.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return None
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except Exception:
        return None
    username, sep, password = decoded.partition(":")
    if not sep:
        return None
    return username, password


def login_url_for(path: str) -> str:
    if not path or path == "/login":
        return "/login"
    return f"/login?next={quote(path)}"
