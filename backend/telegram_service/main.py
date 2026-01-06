"""Telegram webhook microservice (echo-only placeholder)."""
from fastapi import FastAPI

from backend.db.chat_history import (
    ensure_tables as ensure_chat_tables,
    get_or_create_session,
    save_message,
    touch_session,
)

app = FastAPI(title="Academic Question Bot Telegram Service")


def _extract_message(payload: dict) -> tuple[int | None, int | None, str | None]:
    message = payload.get("message") or payload.get("edited_message")
    if not isinstance(message, dict):
        return None, None, None
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    text = message.get("text")
    from_user = message.get("from") if isinstance(message.get("from"), dict) else None
    telegram_id = None
    if isinstance(from_user, dict):
        from_id = from_user.get("id")
        if isinstance(from_id, int):
            telegram_id = from_id
    if telegram_id is None:
        telegram_id = chat_id
    return chat_id, telegram_id, text


@app.on_event("startup")
async def startup_event() -> None:
    ensure_chat_tables()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(payload: dict) -> dict:
    """Temporary echo handler for Telegram updates."""
    chat_id, telegram_id, text = _extract_message(payload)
    if not text:
        return {"status": "ignored", "reason": "no_text", "chat_id": chat_id}
    if chat_id is not None and telegram_id is not None:
        session_id = get_or_create_session(
            telegram_id=telegram_id,
            chat_id=chat_id,
        )
        save_message(
            session_id=session_id,
            telegram_id=telegram_id,
            chat_id=chat_id,
            role="user",
            content=text,
        )
        touch_session(session_id)
    return {"status": "ok", "chat_id": chat_id, "echo": text}
