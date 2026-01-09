"""Telegram Login Widget validation."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Mapping


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in payload.items():
        if key == "hash" or value is None:
            continue
        normalized[key] = str(value)
    return normalized


def verify_login_payload(
    payload: Mapping[str, Any],
    bot_token: str,
    max_age: int | None = 86400,
) -> bool:
    provided_hash = str(payload.get("hash", "")).strip()
    if not bot_token or not provided_hash:
        return False

    auth_date = payload.get("auth_date")
    try:
        auth_date_int = int(auth_date)
    except (TypeError, ValueError):
        return False

    if max_age:
        if auth_date_int < 0:
            return False
        if int(time.time()) - auth_date_int > max_age:
            return False

    normalized = _normalize_payload(payload)
    data_check_string = "\n".join(
        f"{key}={normalized[key]}" for key in sorted(normalized.keys())
    )
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(calculated_hash, provided_hash)
