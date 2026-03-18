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


def list_applications(
    *,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    normalized_page = max(page, 1)
    normalized_per_page = min(max(per_page, 1), 100)
    offset = (normalized_page - 1) * normalized_per_page

    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM admission_applications;")
        total = int(cursor.fetchone()[0])
        cursor.execute(
            """
            SELECT
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
                status,
                source,
                payload,
                created_at,
                updated_at
            FROM admission_applications
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s;
            """,
            (normalized_per_page, offset),
        )
        rows = cursor.fetchall()

    items = [
        {
            "id": row[0],
            "telegram_id": row[1],
            "person_id": row[2],
            "channel": row[3],
            "full_name": row[4],
            "iin": row[5],
            "birth_date": row[6],
            "phone": row[7],
            "email": row[8],
            "education_level": row[9],
            "program": row[10],
            "study_language": row[11],
            "study_format": row[12],
            "comment": row[13],
            "status": row[14],
            "source": row[15],
            "payload": row[16] if isinstance(row[16], dict) else {},
            "created_at": row[17].isoformat() if row[17] else None,
            "updated_at": row[18].isoformat() if row[18] else None,
        }
        for row in rows
    ]
    pages = (total + normalized_per_page - 1) // normalized_per_page if total else 0
    return {
        "items": items,
        "page": normalized_page,
        "per_page": normalized_per_page,
        "total": total,
        "pages": pages,
    }
