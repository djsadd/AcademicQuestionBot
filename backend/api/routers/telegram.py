"""Telegram auth endpoints."""
import logging
import os

import requests
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from ...db.telegram_users import set_platonus_auth, upsert_user_profile
from ...services.platonus_client import authenticate_platonus_user
from ...services.telegram_login import verify_login_payload
from ...services.telegram_webapp import extract_telegram_user

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


def _is_active_student(status_name: str | None) -> bool:
    if not status_name:
        return False
    return status_name.strip().lower() == "обучающийся"


def _send_telegram_message(telegram_id: int, message: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN is not configured; skipping Telegram notify.")
        return
    base_url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(
            base_url,
            json={"chat_id": telegram_id, "text": message},
            timeout=10,
        )
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Failed to notify Telegram user %s: %s", telegram_id, exc)


@router.post("/auth")
async def telegram_auth(payload: TelegramAuthPayload) -> dict:
    if not payload.agreed:
        raise HTTPException(status_code=400, detail="Agreement required.")
    if not payload.login.strip() or not payload.password.strip():
        raise HTTPException(status_code=400, detail="Login and password required.")

    telegram_id = payload.telegram_id
    telegram_user = None
    if payload.init_data:
        telegram_user = extract_telegram_user(payload.init_data)
        if telegram_id is None:
            telegram_id = telegram_user.get("id") if telegram_user else None
    if telegram_id is None:
        raise HTTPException(status_code=400, detail="Telegram user id not found.")

    username = None
    first_name = None
    last_name = None
    if telegram_user:
        username = telegram_user.get("username")
        first_name = telegram_user.get("first_name")
        last_name = telegram_user.get("last_name")

    user = upsert_user_profile(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )
    if user["platonus_auth"]:
        return {
            "status": "already_authorized",
            "telegram_id": telegram_id,
            "person_id": user.get("platonus_person_id"),
            "iin": user.get("platonus_iin"),
            "fullname": user.get("platonus_fullname"),
            "statusName": user.get("platonus_status_name"),
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

    status_name = result.get("statusName")
    if not _is_active_student(status_name):
        raise HTTPException(status_code=403, detail="Student status required.")

    set_platonus_auth(
        telegram_id,
        True,
        role=result.get("role"),
        person_id=result.get("person_id"),
        iin=result.get("iin"),
        fullname=result.get("fullname"),
        status_name=status_name,
        email=result.get("email"),
        birth_date=result.get("birthDate"),
    )
    notify_text = (
        "Успешно авторизовано. Вам доступен бот и сайт: https://academiq.tau-edu.kz/"
    )
    _send_telegram_message(telegram_id, notify_text)
    return {
        "status": "ok",
        "telegram_id": telegram_id,
        "person_id": result.get("person_id"),
        "iin": result.get("iin"),
        "fullname": result.get("fullname"),
        "statusName": result.get("statusName"),
        "email": result.get("email"),
        "birthDate": result.get("birthDate"),
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
        "fullname": user.get("platonus_fullname"),
        "statusName": user.get("platonus_status_name"),
        "email": user.get("platonus_email"),
        "birthDate": user.get("platonus_birth_date"),
    }
