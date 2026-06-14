"""Authentication helpers for the magicreview dashboard."""

from __future__ import annotations

import base64
import hmac
from dataclasses import dataclass
from urllib.parse import quote

from magicreview.config.env import env_bool, get_env


AUTH_SESSION_KEY = "magicreview_authenticated"
AUTH_USER_KEY = "magicreview_username"


@dataclass(frozen=True)
class AuthConfig:
    enabled: bool
    admin_username: str
    admin_password: str
    session_secret: str
    api_keys: tuple[str, ...]
    cookie_secure: bool
    basic_auth_enabled: bool


def load_auth_config() -> AuthConfig:
    keys = tuple(
        key.strip()
        for key in (get_env("API_KEYS", "") or "").split(",")
        if key.strip()
    )
    return AuthConfig(
        enabled=env_bool("AUTH_ENABLED", False),
        admin_username=get_env("ADMIN_USERNAME", "admin") or "admin",
        admin_password=get_env("ADMIN_PASSWORD", "") or "",
        session_secret=get_env("SESSION_SECRET", "") or "",
        api_keys=keys,
        cookie_secure=env_bool("COOKIE_SECURE", False),
        basic_auth_enabled=env_bool("BASIC_AUTH_ENABLED", False),
    )


def session_secret() -> str:
    configured = get_env("SESSION_SECRET", "") or ""
    return configured or "magicreview-local-session-secret-change-me"


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
