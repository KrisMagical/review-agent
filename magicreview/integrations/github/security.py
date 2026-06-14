"""Webhook signature verification helpers."""

from __future__ import annotations

import hashlib
import hmac


def compute_signature(payload: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_signature(payload: bytes, signature_header: str | None, secret: str) -> bool:
    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    return hmac.compare_digest(compute_signature(payload, secret), signature_header)
