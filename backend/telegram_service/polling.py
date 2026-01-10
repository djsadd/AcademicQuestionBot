"""Telegram long-polling worker (echo-only placeholder)."""
import asyncio
import logging
import os
import re
import time

import requests

from backend.db.chat_history import (
    ensure_tables as ensure_chat_tables,
    clear_history_if_limit,
    get_or_create_session,
    save_message,
    touch_session,
)
from backend.db import chat_analytics
from backend.db.telegram_users import ensure_table, get_or_create_user
from backend.orchestrator.router import AgentRouter


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _extract_message(update: dict) -> tuple[int | None, str | None, dict | None]:
    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return None, None, None
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    text = message.get("text")
    from_user = message.get("from") if isinstance(message.get("from"), dict) else None
    return chat_id, text, from_user


def _send_message(
    base_url: str,
    chat_id: int,
    text: str,
    reply_markup: dict | None = None,
    parse_mode: str | None = "HTML",
) -> None:
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    response = requests.post(
        f"{base_url}/sendMessage",
        json=payload,
        timeout=10,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise requests.HTTPError(f"{exc} | response={response.text}") from exc


def _normalize_telegram_html(text: str) -> str:
    if not text:
        return text
    normalized = text
    normalized = re.sub(r"<\s*br\s*/?>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/?p\s*>", "\n\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/?h[1-6]\s*>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*li\s*>", "- ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/\s*li\s*>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/?ul\s*>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/?ol\s*>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*strong\s*>", "<b>", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/\s*strong\s*>", "</b>", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*em\s*>", "<i>", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/\s*em\s*>", "</i>", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*blockquote\s*>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/\s*blockquote\s*>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*code\s*>", "<code>", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/\s*code\s*>", "</code>", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*pre\s*>", "<pre>", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/\s*pre\s*>", "</pre>", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*(table|thead|tbody|tr|th|td)[^>]*>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"</\s*(table|thead|tbody|tr|th|td)\s*>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"</?(span|div|section|article|header|footer|main)[^>]*>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"</?(?:a)[^>]*>", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<[^>]+>", "", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _build_ai_payload(message: str, telegram_id: int | None) -> dict:
    """Prepare minimal chat payload with only query content."""
    return {
        "message": message,
        "language": None,
        "topic": None,
        "policy": None,
        "program": None,
        "telegram_id": telegram_id,
    }


def _run_ai_chat(agent_router: AgentRouter, message: str, telegram_id: int | None) -> dict:
    payload = _build_ai_payload(message, telegram_id)
    return asyncio.run(agent_router.route(payload)) or {}


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set.")

    ensure_table()
    ensure_chat_tables()
    chat_analytics.ensure_tables()
    agent_router = AgentRouter()

    base_url = f"https://api.telegram.org/bot{token}"
    mini_app_url = os.getenv("TELEGRAM_MINI_APP_URL", "https://academiq.tau-edu.kz").strip()
    poll_timeout = _get_env_int("TELEGRAM_POLL_TIMEOUT", 20)
    poll_interval = _get_env_float("TELEGRAM_POLL_INTERVAL", 1.0)

    offset = 0
    logger = logging.getLogger("telegram")
    logger.info("Starting Telegram long-polling.")

    while True:
        try:
            response = requests.post(
                f"{base_url}/getUpdates",
                json={"timeout": poll_timeout, "offset": offset},
                timeout=poll_timeout + 5,
            )
            response.raise_for_status()
            data = response.json()
            updates = data.get("result") or []
            for update in updates:
                if not isinstance(update, dict):
                    continue
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1
                chat_id, text, from_user = _extract_message(update)
                if chat_id is None or not text:
                    continue
                telegram_id = None
                if isinstance(from_user, dict):
                    from_id = from_user.get("id")
                    if isinstance(from_id, int):
                        telegram_id = from_id
                if telegram_id is None:
                    telegram_id = chat_id

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

                user = get_or_create_user(
                    telegram_id=telegram_id,
                    username=from_user.get("username") if isinstance(from_user, dict) else None,
                    first_name=from_user.get("first_name") if isinstance(from_user, dict) else None,
                    last_name=from_user.get("last_name") if isinstance(from_user, dict) else None,
                )
                if not user["platonus_auth"]:
                    auth_text = "Authorization required. Please sign in via the mini app."
                    reply_markup = None
                    if mini_app_url:
                        if mini_app_url.startswith("https://"):
                            reply_markup = {
                                "inline_keyboard": [
                                    [
                                        {
                                            "text": "Open mini app",
                                            "web_app": {"url": mini_app_url},
                                        }
                                    ]
                                ]
                            }
                        else:
                            reply_markup = {
                                "inline_keyboard": [
                                    [
                                        {
                                            "text": "Open link",
                                            "url": mini_app_url,
                                        }
                                    ]
                                ]
                            }
                            auth_text = f"{auth_text}\n{mini_app_url}"
                            logger.warning(
                                "TELEGRAM_MINI_APP_URL is not https://; using url button fallback: %s",
                                mini_app_url,
                            )
                    save_message(
                        session_id=session_id,
                        telegram_id=telegram_id,
                        chat_id=chat_id,
                        role="assistant",
                        content=auth_text,
                    )
                    touch_session(session_id)
                    if clear_history_if_limit(session_id, limit=5):
                        _send_message(
                            base_url,
                            chat_id,
                            "История чата очищена.",
                            parse_mode=None,
                        )
                    try:
                        chat_analytics.save_chat_event(
                            session_id=session_id,
                            telegram_id=telegram_id,
                            person_id=user.get("platonus_person_id"),
                            channel="telegram",
                            query=text,
                            response=auth_text,
                            llm_model=None,
                            llm_used=False,
                            llm_error=None,
                            intents=[],
                            agents=[],
                            trace=[],
                            metadata={"chat_id": chat_id},
                        )
                    except Exception as exc:
                        logger.warning("Chat analytics failed: %s", exc)
                    _send_message(base_url, chat_id, auth_text, reply_markup, parse_mode=None)
                    continue

                try:
                    result = _run_ai_chat(agent_router, text, telegram_id)
                    answer = result.get("final_answer") or "Ответ временно недоступен."
                except Exception as exc:
                    logger.warning("AI chat failed: %s", exc)
                    answer = "Не удалось получить ответ. Попробуйте позже."
                    result = {
                        "query": text,
                        "final_answer": answer,
                        "intents": [],
                        "plan": [],
                        "trace": [],
                        "llm": {"model": None, "used": False, "error": str(exc)},
                    }
                save_message(
                    session_id=session_id,
                    telegram_id=telegram_id,
                    chat_id=chat_id,
                    role="assistant",
                    content=answer,
                )
                touch_session(session_id)
                if clear_history_if_limit(session_id, limit=5):
                    _send_message(
                        base_url,
                        chat_id,
                        "История чата очищена.",
                        parse_mode=None,
                    )
                try:
                    chat_analytics.save_chat_event(
                        session_id=session_id,
                        telegram_id=telegram_id,
                        person_id=user.get("platonus_person_id"),
                        channel="telegram",
                        query=text,
                        response=answer,
                        llm_model=(result.get("llm") or {}).get("model"),
                        llm_used=(result.get("llm") or {}).get("used"),
                        llm_error=(result.get("llm") or {}).get("error"),
                        intents=result.get("intents"),
                        agents=result.get("plan"),
                        trace=result.get("trace"),
                        metadata={"chat_id": chat_id},
                    )
                except Exception as exc:
                    logger.warning("Chat analytics failed: %s", exc)
                safe_answer = _normalize_telegram_html(answer)
                _send_message(base_url, chat_id, safe_answer, parse_mode="HTML")
        except Exception as exc:
            logger.warning("Telegram polling error: %s", exc)
            time.sleep(poll_interval)


if __name__ == "__main__":
    run()
