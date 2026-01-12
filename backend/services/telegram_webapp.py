"""Telegram WebApp init data validation."""
from __future__ import annotations

import hashlib
import hmac
import os
from urllib.parse import parse_qsl


def parse_telegram_id(init_data: str) -> int | None:
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    user_json = data.get("user")
    if not user_json:
        return None
    try:
        import json

        user = json.loads(user_json)
    except Exception:
        return None
    user_id = user.get("id")
    return int(user_id) if isinstance(user_id, int) else None


def parse_telegram_user(init_data: str) -> dict | None:
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    user_json = data.get("user")
    if not user_json:
        return None
    try:
        import json

        user = json.loads(user_json)
    except Exception:
        return None
    if not isinstance(user, dict):
        return None
    user_id = user.get("id")
    if not isinstance(user_id, int):
        return None
    return {
        "id": int(user_id),
        "username": user.get("username"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
    }


def validate_init_data(init_data: str, bot_token: str) -> bool:
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = data.pop("hash", None)
    if not received_hash:
        return False

    pairs = [f"{key}={value}" for key, value in sorted(data.items())]
    data_check_string = "\n".join(pairs)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calculated_hash, received_hash)


def extract_telegram_id(init_data: str) -> int | None:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        return None
    if not validate_init_data(init_data, bot_token):
        return None
    return parse_telegram_id(init_data)


def extract_telegram_user(init_data: str) -> dict | None:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        return None
    if not validate_init_data(init_data, bot_token):
        return None
    return parse_telegram_user(init_data)
