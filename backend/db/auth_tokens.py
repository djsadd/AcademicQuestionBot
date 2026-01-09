"""Refresh token storage for Telegram auth."""
from __future__ import annotations

import hashlib
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

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


def ensure_table() -> None:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_refresh_tokens (
                token_hash TEXT PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                revoked_at TIMESTAMPTZ
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_telegram_refresh_tokens_user
            ON telegram_refresh_tokens (telegram_id);
            """
        )
        conn.commit()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_refresh_token(telegram_id: int, ttl_seconds: int) -> dict:
    token = secrets.token_urlsafe(48)
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO telegram_refresh_tokens (token_hash, telegram_id, expires_at)
            VALUES (%s, %s, %s);
            """,
            (token_hash, telegram_id, expires_at),
        )
        conn.commit()
    return {"token": token, "expires_at": expires_at}


def rotate_refresh_token(token: str) -> dict | None:
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT telegram_id, expires_at, revoked_at
            FROM telegram_refresh_tokens
            WHERE token_hash = %s;
            """,
            (token_hash,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        telegram_id, expires_at, revoked_at = row
        if revoked_at is not None or expires_at <= now:
            return None
        cursor.execute(
            """
            UPDATE telegram_refresh_tokens
            SET revoked_at = NOW()
            WHERE token_hash = %s;
            """,
            (token_hash,),
        )
        conn.commit()
    return {"telegram_id": telegram_id}


def revoke_refresh_token(token: str) -> bool:
    token_hash = _hash_token(token)
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE telegram_refresh_tokens
            SET revoked_at = NOW()
            WHERE token_hash = %s AND revoked_at IS NULL;
            """,
            (token_hash,),
        )
        changed = cursor.rowcount > 0
        conn.commit()
    return changed
