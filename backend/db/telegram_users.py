"""Minimal Postgres access for Telegram users."""
from __future__ import annotations

import os
from contextlib import contextmanager
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
            CREATE TABLE IF NOT EXISTS telegram_users (
                telegram_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                platonus_auth BOOLEAN NOT NULL DEFAULT FALSE,
                platonus_role TEXT,
                platonus_person_id TEXT,
                platonus_iin TEXT,
                platonus_fullname TEXT,
                platonus_status_name TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cursor.execute(
            """
            ALTER TABLE telegram_users
                ADD COLUMN IF NOT EXISTS platonus_role TEXT,
                ADD COLUMN IF NOT EXISTS platonus_person_id TEXT,
                ADD COLUMN IF NOT EXISTS platonus_iin TEXT,
                ADD COLUMN IF NOT EXISTS platonus_fullname TEXT,
                ADD COLUMN IF NOT EXISTS platonus_status_name TEXT;
            """
        )
        conn.commit()


def get_or_create_user(
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> dict:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT telegram_id, platonus_auth, platonus_role, platonus_person_id, platonus_iin,
                   platonus_fullname, platonus_status_name
            FROM telegram_users
            WHERE telegram_id = %s;
            """,
            (telegram_id,),
        )
        row = cursor.fetchone()
        if row:
            return {
                "telegram_id": row[0],
                "platonus_auth": row[1],
                "platonus_role": row[2],
                "platonus_person_id": row[3],
                "platonus_iin": row[4],
                "platonus_fullname": row[5],
                "platonus_status_name": row[6],
            }

        cursor.execute(
            """
            INSERT INTO telegram_users (telegram_id, username, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            RETURNING telegram_id, platonus_auth, platonus_role, platonus_person_id, platonus_iin,
                      platonus_fullname, platonus_status_name;
            """,
            (telegram_id, username, first_name, last_name),
        )
        row = cursor.fetchone()
        conn.commit()
        return {
            "telegram_id": row[0],
            "platonus_auth": row[1],
            "platonus_role": row[2],
            "platonus_person_id": row[3],
            "platonus_iin": row[4],
            "platonus_fullname": row[5],
            "platonus_status_name": row[6],
        }


def upsert_user_profile(
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> dict:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO telegram_users (telegram_id, username, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (telegram_id) DO UPDATE
            SET username = COALESCE(EXCLUDED.username, telegram_users.username),
                first_name = COALESCE(EXCLUDED.first_name, telegram_users.first_name),
                last_name = COALESCE(EXCLUDED.last_name, telegram_users.last_name),
                updated_at = NOW()
            RETURNING telegram_id, platonus_auth, platonus_role, platonus_person_id, platonus_iin,
                      platonus_fullname, platonus_status_name;
            """,
            (telegram_id, username, first_name, last_name),
        )
        row = cursor.fetchone()
        conn.commit()
        return {
            "telegram_id": row[0],
            "platonus_auth": row[1],
            "platonus_role": row[2],
            "platonus_person_id": row[3],
            "platonus_iin": row[4],
            "platonus_fullname": row[5],
            "platonus_status_name": row[6],
        }


def get_user(telegram_id: int) -> dict | None:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT telegram_id, platonus_auth, platonus_role, platonus_person_id, platonus_iin,
                   platonus_fullname, platonus_status_name
            FROM telegram_users
            WHERE telegram_id = %s;
            """,
            (telegram_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "telegram_id": row[0],
            "platonus_auth": row[1],
            "platonus_role": row[2],
            "platonus_person_id": row[3],
            "platonus_iin": row[4],
            "platonus_fullname": row[5],
            "platonus_status_name": row[6],
        }


def set_platonus_auth(
    telegram_id: int,
    value: bool,
    role: str | None = None,
    person_id: str | None = None,
    iin: str | None = None,
    fullname: str | None = None,
    status_name: str | None = None,
) -> None:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE telegram_users
            SET platonus_auth = %s,
                platonus_role = %s,
                platonus_person_id = %s,
                platonus_iin = %s,
                platonus_fullname = %s,
                platonus_status_name = %s,
                updated_at = NOW()
            WHERE telegram_id = %s;
            """,
            (value, role, person_id, iin, fullname, status_name, telegram_id),
        )
        conn.commit()
