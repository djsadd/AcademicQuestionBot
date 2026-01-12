"""Chat endpoints for orchestrating academic conversations."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...db import chat_analytics
from ...services.permissions import require_user

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


@router.post("/")
async def handle_chat(payload: ChatPayload, user: dict = Depends(require_user)) -> dict:
    telegram_id = user["telegram_id"]
    person_id = payload.person_id or user.get("platonus_person_id")

    metadata = payload.metadata or {}
    session_id = metadata.get("session_id") or metadata.get("session") or None
    channel = metadata.get("channel") or "web"

    router_payload = payload.model_dump()
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
async def get_chat_history(user: dict = Depends(require_user)) -> dict:
    history = chat_analytics.fetch_chat_history(user["telegram_id"])
    return {"sessions": history}
