"""Chat endpoints for orchestrating academic conversations."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ...db import chat_analytics
from ...db.telegram_users import get_user
from ...services.auth_tokens import decode_access_token

from ...orchestrator.router import AgentRouter

router = APIRouter(prefix="/chat", tags=["chat"])
agent_router = AgentRouter()
logger = logging.getLogger("chat")


class ChatPayload(BaseModel):
    user_id: int | None = None
    telegram_id: int | None = None
    person_id: str | None = None
    message: str
    language: str | None = "ru"
    context: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


@router.post("/")
async def handle_chat(payload: ChatPayload, authorization: str | None = Header(default=None)) -> dict:
    token = _extract_bearer(authorization)
    telegram_id = payload.telegram_id or payload.user_id
    if telegram_id is None and token:
        try:
            decoded = decode_access_token(token)
        except Exception:
            decoded = None
        if decoded:
            sub = decoded.get("sub")
            try:
                telegram_id = int(sub) if sub is not None else None
            except (TypeError, ValueError):
                telegram_id = None

    person_id = payload.person_id
    if telegram_id is not None and not person_id:
        user = get_user(telegram_id)
        if user:
            person_id = user.get("platonus_person_id")

    metadata = payload.metadata or {}
    session_id = metadata.get("session_id") or metadata.get("session") or None
    channel = metadata.get("channel") or "web"

    router_payload = payload.model_dump()
    if telegram_id is not None:
        router_payload["telegram_id"] = telegram_id
        router_payload["user_id"] = telegram_id
    if person_id:
        router_payload["person_id"] = person_id
    if session_id:
        router_payload["history"] = chat_analytics.fetch_session_history(session_id)

    response = await agent_router.route(router_payload)

    try:
        chat_analytics.save_chat_event(
            session_id=session_id,
            telegram_id=telegram_id,
            person_id=person_id,
            channel=str(channel) if channel is not None else None,
            query=response.get("query"),
            response=response.get("final_answer"),
            llm_model=(response.get("llm") or {}).get("model"),
            llm_used=(response.get("llm") or {}).get("used"),
            llm_error=(response.get("llm") or {}).get("error"),
            intents=response.get("intents"),
            agents=response.get("plan"),
            trace=response.get("trace"),
            metadata=metadata,
        )
    except Exception as exc:
        logger.exception("Chat analytics failed: %s", exc)

    return {"result": response}


@router.get("/history")
async def get_chat_history(authorization: str | None = Header(default=None)) -> dict:
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token.")
    try:
        decoded = decode_access_token(token)
    except Exception:
        decoded = None
    if not decoded:
        raise HTTPException(status_code=401, detail="Invalid access token.")
    sub = decoded.get("sub")
    try:
        telegram_id = int(sub) if sub is not None else None
    except (TypeError, ValueError):
        telegram_id = None
    if telegram_id is None:
        raise HTTPException(status_code=401, detail="Telegram ID missing.")

    history = chat_analytics.fetch_chat_history(telegram_id)
    return {"sessions": history}
