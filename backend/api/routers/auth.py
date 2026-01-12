"""Telegram-based auth endpoints."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...db import auth_tokens
from ...db.telegram_users import upsert_user_profile
from ...services.auth_tokens import (
    build_access_token,
    build_refresh_ttl_seconds,
)
from ...services.permissions import get_current_user
from ...services.telegram_login import verify_login_payload

router = APIRouter(prefix="/auth", tags=["auth"])


class TelegramLoginPayload(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class RefreshPayload(BaseModel):
    refresh_token: str


def _get_bot_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN is not configured.")
    return token


def _get_login_max_age() -> int | None:
    raw = os.getenv("TELEGRAM_LOGIN_MAX_AGE", "").strip()
    if not raw:
        return 86400
    try:
        value = int(raw)
    except ValueError:
        value = 86400
    return None if value <= 0 else value


@router.post("/telegram")
async def telegram_login(payload: TelegramLoginPayload) -> dict:
    if not verify_login_payload(payload.model_dump(), _get_bot_token(), _get_login_max_age()):
        raise HTTPException(status_code=401, detail="Telegram login validation failed.")

    user = upsert_user_profile(
        payload.id,
        payload.username,
        payload.first_name,
        payload.last_name,
    )
    access_payload = build_access_token(
        str(user["telegram_id"]),
        {
            "username": payload.username,
            "first_name": payload.first_name,
            "last_name": payload.last_name,
        },
    )
    refresh_ttl = build_refresh_ttl_seconds()
    refresh_payload = auth_tokens.issue_refresh_token(user["telegram_id"], refresh_ttl)

    return {
        "status": "ok",
        "access_token": access_payload["token"],
        "refresh_token": refresh_payload["token"],
        "token_type": "bearer",
        "expires_in": access_payload["expires_in"],
        "refresh_expires_in": refresh_ttl,
        "user": {
            "telegram_id": user["telegram_id"],
            "username": payload.username,
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "platonus_auth": user["platonus_auth"],
            "role": user["platonus_role"],
            "person_id": user["platonus_person_id"],
            "iin": user["platonus_iin"],
            "fullname": user.get("platonus_fullname"),
            "statusName": user.get("platonus_status_name"),
            "email": user.get("platonus_email"),
            "birthDate": user.get("platonus_birth_date"),
        },
    }


@router.post("/refresh")
async def refresh_token(payload: RefreshPayload) -> dict:
    if not payload.refresh_token.strip():
        raise HTTPException(status_code=400, detail="Refresh token required.")

    rotated = auth_tokens.rotate_refresh_token(payload.refresh_token)
    if not rotated:
        raise HTTPException(status_code=401, detail="Refresh token invalid or expired.")

    access_payload = build_access_token(str(rotated["telegram_id"]))
    refresh_ttl = build_refresh_ttl_seconds()
    refresh_payload = auth_tokens.issue_refresh_token(rotated["telegram_id"], refresh_ttl)
    return {
        "status": "ok",
        "access_token": access_payload["token"],
        "refresh_token": refresh_payload["token"],
        "token_type": "bearer",
        "expires_in": access_payload["expires_in"],
        "refresh_expires_in": refresh_ttl,
    }


@router.post("/logout")
async def logout(payload: RefreshPayload) -> dict:
    if not payload.refresh_token.strip():
        raise HTTPException(status_code=400, detail="Refresh token required.")
    revoked = auth_tokens.revoke_refresh_token(payload.refresh_token)
    if not revoked:
        raise HTTPException(status_code=404, detail="Refresh token not found.")
    return {"status": "ok"}


@router.get("/me")
async def auth_me(user: dict = Depends(get_current_user)) -> dict:
    return {
        "status": "ok",
        "user": {
            "telegram_id": user["telegram_id"],
            "platonus_auth": user["platonus_auth"],
            "role": user["platonus_role"],
            "person_id": user["platonus_person_id"],
            "iin": user["platonus_iin"],
            "fullname": user.get("platonus_fullname"),
            "statusName": user.get("platonus_status_name"),
            "email": user.get("platonus_email"),
            "birthDate": user.get("platonus_birth_date"),
        },
    }
