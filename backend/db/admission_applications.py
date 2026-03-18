"""Persistence for admission applications created by the admission agent."""
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
            CREATE TABLE IF NOT EXISTS admission_applications (
                id TEXT PRIMARY KEY,
                telegram_id BIGINT,
                person_id TEXT,
                channel TEXT,
                full_name TEXT NOT NULL,
                iin TEXT,
                birth_date TEXT,
                phone TEXT NOT NULL,
                email TEXT,
                education_level TEXT NOT NULL,
                program TEXT NOT NULL,
                study_language TEXT,
                study_format TEXT,
                comment TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                source TEXT NOT NULL DEFAULT 'admission_agent',
                payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_admission_applications_telegram
            ON admission_applications (telegram_id, created_at DESC);
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_admission_applications_status
            ON admission_applications (status, created_at DESC);
            """
        )
        conn.commit()


def create_application(
    *,
    telegram_id: int | None,
    person_id: str | None,
    channel: str | None,
    full_name: str,
    iin: str | None,
    birth_date: str | None,
    phone: str,
    email: str | None,
    education_level: str,
    program: str,
    study_language: str | None,
    study_format: str | None,
    comment: str | None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    application_id = uuid.uuid4().hex
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO admission_applications (
                id,
                telegram_id,
                person_id,
                channel,
                full_name,
                iin,
                birth_date,
                phone,
                email,
                education_level,
                program,
                study_language,
                study_format,
                comment,
                payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, status, created_at;
            """,
            (
                application_id,
                telegram_id,
                person_id,
                channel,
                full_name,
                iin,
                birth_date,
                phone,
                email,
                education_level,
                program,
                study_language,
                study_format,
                comment,
                json.dumps(payload or {}, ensure_ascii=False),
            ),
        )
        row = cursor.fetchone()
        conn.commit()
    return {
        "id": row[0],
        "status": row[1],
        "created_at": row[2].isoformat() if row and row[2] else None,
    }
