"""JWT helpers for Telegram auth."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        raise RuntimeError("JWT_SECRET is not configured.")
    return secret


def _get_access_ttl_minutes() -> int:
    raw = os.getenv("JWT_ACCESS_TTL_MINUTES", "30").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 30
    return max(1, value)


def _get_refresh_ttl_days() -> int:
    raw = os.getenv("JWT_REFRESH_TTL_DAYS", "14").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 14
    return max(1, value)


def build_access_token(subject: str, claims: dict[str, Any] | None = None) -> dict[str, Any]:
    ttl_minutes = _get_access_ttl_minutes()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
    }
    if claims:
        payload.update(claims)
    token = jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")
    return {"token": token, "expires_in": ttl_minutes * 60}


def build_refresh_ttl_seconds() -> int:
    return _get_refresh_ttl_days() * 24 * 60 * 60


def decode_access_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("Invalid token type.")
    return payload
