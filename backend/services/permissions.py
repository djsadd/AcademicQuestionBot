"""Permissions helpers for access tokens and role checks."""
from __future__ import annotations

import os
from functools import lru_cache

from fastapi import Depends, Header, HTTPException

from ..db.telegram_users import get_user
from .auth_tokens import decode_access_token


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing.")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header.")
    return parts[1]


def _get_telegram_id_from_token(token: str) -> int:
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Access token invalid.")
    telegram_id = payload.get("sub")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Access token invalid.")
    try:
        return int(telegram_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Access token invalid.")


@lru_cache(maxsize=1)
def _admin_roles() -> set[str]:
    raw = os.getenv("ADMIN_ROLES", "admin,administrator,superuser,staff,dean,deanery").strip()
    roles = {role.strip().lower() for role in raw.split(",") if role.strip()}
    return roles


@lru_cache(maxsize=1)
def _bootstrap_admins() -> set[str]:
    """Logins / Telegram ids that are always admins (ADMIN_LOGINS) — bootstraps the first admin."""
    raw = os.getenv("ADMIN_LOGINS", "")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def is_admin(user: dict | None) -> bool:
    if not user:
        return False
    role = str(user.get("platonus_role") or "").strip().lower()
    if role and role in _admin_roles():
        return True
    identities = {str(user.get("username") or "").strip().lower(), str(user.get("telegram_id") or "").strip()}
    identities.discard("")
    return bool(identities & _bootstrap_admins())


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    token = _extract_bearer_token(authorization)
    telegram_id = _get_telegram_id_from_token(token)
    user = get_user(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


def require_user(user: dict = Depends(get_current_user)) -> dict:
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Нужны права администратора.")
    return user


def can_access_feature(user_role: str, feature: str) -> bool:
    if feature == "admin":
        return user_role.strip().lower() in _admin_roles()
    return True
