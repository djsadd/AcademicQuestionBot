"""Postgres persistence for Telegram chat sessions and history."""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

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
            CREATE TABLE IF NOT EXISTS telegram_sessions (
                id TEXT PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES telegram_sessions(id) ON DELETE CASCADE,
                telegram_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_telegram_sessions_lookup
            ON telegram_sessions (telegram_id, chat_id, last_message_at DESC);
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_telegram_messages_session
            ON telegram_messages (session_id, created_at);
            """
        )
        conn.commit()


def get_latest_session(telegram_id: int, chat_id: int) -> Optional[str]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM telegram_sessions
            WHERE telegram_id = %s AND chat_id = %s
            ORDER BY last_message_at DESC
            LIMIT 1;
            """,
            (telegram_id, chat_id),
        )
        row = cursor.fetchone()
    return row[0] if row else None


def create_session(telegram_id: int, chat_id: int) -> str:
    session_id = uuid.uuid4().hex
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO telegram_sessions (id, telegram_id, chat_id)
            VALUES (%s, %s, %s);
            """,
            (session_id, telegram_id, chat_id),
        )
        conn.commit()
    return session_id


def get_or_create_session(telegram_id: int, chat_id: int) -> str:
    session_id = get_latest_session(telegram_id, chat_id)
    if session_id:
        return session_id
    return create_session(telegram_id, chat_id)


def touch_session(session_id: str) -> None:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE telegram_sessions
            SET last_message_at = NOW()
            WHERE id = %s;
            """,
            (session_id,),
        )
        conn.commit()


def save_message(
    *,
    session_id: str,
    telegram_id: int,
    chat_id: int,
    role: str,
    content: str,
) -> str:
    message_id = uuid.uuid4().hex
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO telegram_messages (id, session_id, telegram_id, chat_id, role, content)
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            (message_id, session_id, telegram_id, chat_id, role, content),
        )
        conn.commit()
    return message_id


def clear_history_if_limit(session_id: str, limit: int = 5) -> bool:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM telegram_messages
            WHERE session_id = %s;
            """,
            (session_id,),
        )
        count = cursor.fetchone()[0]
        if count < limit:
            return False
        cursor.execute(
            """
            DELETE FROM telegram_messages
            WHERE session_id = %s;
            """,
            (session_id,),
        )
        conn.commit()
    return True
