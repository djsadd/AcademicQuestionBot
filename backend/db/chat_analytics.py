"""Chat analytics persistence for web/API chat."""
from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2


@contextmanager
def _get_connection() -> Iterator[psycopg2.extensions.connection]:
    dsn = os.getenv("POSTGRES_DSN", "").strip()
    if not dsn:
        raise SystemExit("POSTGRES_DSN is not set.")
    conn = psycopg2.connect(dsn)
    try:
        yield conn
    finally:
        conn.close()


def ensure_tables() -> None:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_analytics (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                telegram_id BIGINT,
                person_id TEXT,
                channel TEXT,
                query TEXT,
                response TEXT,
                llm_model TEXT,
                llm_used BOOLEAN,
                llm_error TEXT,
                intents JSONB,
                agents JSONB,
                trace JSONB,
                metadata JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_analytics_session
            ON chat_analytics (session_id, created_at DESC);
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_analytics_telegram
            ON chat_analytics (telegram_id, created_at DESC);
            """
        )
        conn.commit()


def save_chat_event(
    *,
    session_id: str | None,
    telegram_id: int | None,
    person_id: str | None,
    channel: str | None,
    query: str | None,
    response: str | None,
    llm_model: str | None,
    llm_used: bool | None,
    llm_error: str | None,
    intents: Any,
    agents: Any,
    trace: Any,
    metadata: dict[str, Any] | None,
) -> str:
    event_id = uuid.uuid4().hex
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chat_analytics (
                id,
                session_id,
                telegram_id,
                person_id,
                channel,
                query,
                response,
                llm_model,
                llm_used,
                llm_error,
                intents,
                agents,
                trace,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                event_id,
                session_id,
                telegram_id,
                person_id,
                channel,
                query,
                response,
                llm_model,
                llm_used,
                llm_error,
                json.dumps(intents, ensure_ascii=False),
                json.dumps(agents, ensure_ascii=False),
                json.dumps(trace, ensure_ascii=False),
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        conn.commit()
    return event_id


def fetch_chat_history(telegram_id: int) -> list[dict[str, Any]]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT session_id, query, response, created_at
            FROM chat_analytics
            WHERE telegram_id = %s AND session_id IS NOT NULL
            ORDER BY created_at ASC;
            """,
            (telegram_id,),
        )
        rows = cursor.fetchall()

    sessions: dict[str, dict[str, Any]] = {}
    for session_id, query, response, created_at in rows:
        if session_id not in sessions:
            sessions[session_id] = {
                "session_id": session_id,
                "title": "",
                "created_at": created_at.isoformat(),
                "updated_at": created_at.isoformat(),
                "messages": [],
            }
        session = sessions[session_id]
        session["updated_at"] = created_at.isoformat()
        if query:
            session["messages"].append(
                {
                    "id": uuid.uuid4().hex,
                    "role": "user",
                    "content": query,
                    "created_at": created_at.isoformat(),
                }
            )
            if not session["title"]:
                session["title"] = query
        if response:
            session["messages"].append(
                {
                    "id": uuid.uuid4().hex,
                    "role": "bot",
                    "content": response,
                    "created_at": created_at.isoformat(),
                }
            )

    sessions_list = list(sessions.values())
    sessions_list.sort(key=lambda item: item["updated_at"], reverse=True)
    return sessions_list
