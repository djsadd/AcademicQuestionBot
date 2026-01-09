"""Telegram auth endpoints."""
import logging
import os

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from ...db.telegram_users import get_or_create_user, set_platonus_auth, upsert_user_profile
from ...services.platonus_client import authenticate_platonus_user
from ...services.telegram_login import verify_login_payload
from ...services.telegram_webapp import extract_telegram_id

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = logging.getLogger("telegram_auth")


class TelegramAuthPayload(BaseModel):
    telegram_id: int | None = None
    init_data: str | None = None
    login: str
    password: str
    agreed: bool


class TelegramLoginPayload(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


@router.post("/auth")
async def telegram_auth(payload: TelegramAuthPayload) -> dict:
    if not payload.agreed:
        raise HTTPException(status_code=400, detail="Agreement required.")
    if not payload.login.strip() or not payload.password.strip():
        raise HTTPException(status_code=400, detail="Login and password required.")

    telegram_id = payload.telegram_id
    if telegram_id is None and payload.init_data:
        telegram_id = extract_telegram_id(payload.init_data)
    if telegram_id is None:
        raise HTTPException(status_code=400, detail="Telegram user id not found.")

    user = get_or_create_user(
        telegram_id=telegram_id,
        username=None,
        first_name=None,
        last_name=None,
    )
    if user["platonus_auth"]:
        return {
            "status": "already_authorized",
            "telegram_id": telegram_id,
            "person_id": user.get("platonus_person_id"),
            "iin": user.get("platonus_iin"),
            "role": user.get("platonus_role"),
        }

    try:
        result = await run_in_threadpool(
            authenticate_platonus_user, payload.login, payload.password
        )
    except RuntimeError as exc:
        detail = str(exc)
        status = 500 if "PLATONUS_API_URL" in detail else 401
        raise HTTPException(status_code=status, detail=detail) from exc
    except Exception as exc:
        logger.exception("Platonus auth failed: %s", exc)
        raise HTTPException(status_code=500, detail="Platonus auth failed.") from exc

    set_platonus_auth(
        telegram_id,
        True,
        role=result.get("role"),
        person_id=result.get("person_id"),
        iin=result.get("iin"),
    )
    return {
        "status": "ok",
        "telegram_id": telegram_id,
        "person_id": result.get("person_id"),
        "iin": result.get("iin"),
        "role": result.get("role"),
    }


@router.post("/login")
async def telegram_login(payload: TelegramLoginPayload) -> dict:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN is not configured.")

    max_age_raw = os.getenv("TELEGRAM_LOGIN_MAX_AGE", "").strip()
    if max_age_raw:
        try:
            max_age = int(max_age_raw)
        except ValueError:
            max_age = 86400
    else:
        max_age = 86400
    max_age = None if max_age and max_age <= 0 else max_age

    if not verify_login_payload(payload.model_dump(), bot_token, max_age=max_age):
        raise HTTPException(status_code=401, detail="Telegram login validation failed.")

    user = upsert_user_profile(
        payload.id,
        payload.username,
        payload.first_name,
        payload.last_name,
    )
    return {
        "status": "ok",
        "telegram_id": user["telegram_id"],
        "username": payload.username,
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "platonus_auth": user["platonus_auth"],
        "role": user["platonus_role"],
        "person_id": user["platonus_person_id"],
        "iin": user["platonus_iin"],
    }
