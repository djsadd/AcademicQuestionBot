"""Telegram auth endpoints."""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from ...db.telegram_users import get_or_create_user, set_platonus_auth
from ...services.platonus_auth import auth as platonus_auth
from ...services.telegram_webapp import extract_telegram_id

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = logging.getLogger("telegram_auth")


class TelegramAuthPayload(BaseModel):
    telegram_id: int | None = None
    init_data: str | None = None
    login: str
    password: str
    agreed: bool


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
        result = await run_in_threadpool(platonus_auth, payload.login, payload.password)
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
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
