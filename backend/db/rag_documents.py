"""Postgres persistence for RAG documents, files, and ingestion jobs."""
from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

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
            CREATE TABLE IF NOT EXISTS rag_files (
                id TEXT PRIMARY KEY,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                content_type TEXT,
                size_bytes BIGINT NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_jobs (
                id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL REFERENCES rag_files(id) ON DELETE CASCADE,
                document_id TEXT,
                status TEXT NOT NULL,
                error TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                started_at TIMESTAMPTZ,
                finished_at TIMESTAMPTZ
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_documents (
                document_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL REFERENCES rag_files(id) ON DELETE CASCADE,
                job_id TEXT REFERENCES rag_jobs(id) ON DELETE SET NULL,
                chunks INTEGER NOT NULL DEFAULT 0,
                size_bytes BIGINT NOT NULL DEFAULT 0,
                uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb
            );
            """
        )
        conn.commit()


def create_file(
    *,
    original_name: str,
    stored_name: str,
    content_type: Optional[str],
    size_bytes: int,
) -> str:
    file_id = uuid.uuid4().hex
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO rag_files (id, original_name, stored_name, content_type, size_bytes)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (file_id, original_name, stored_name, content_type, size_bytes),
        )
        conn.commit()
    return file_id


def create_job(*, file_id: str, document_id: str, status: str = "queued") -> str:
    job_id = uuid.uuid4().hex
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO rag_jobs (id, file_id, document_id, status)
            VALUES (%s, %s, %s, %s);
            """,
            (job_id, file_id, document_id, status),
        )
        conn.commit()
    return job_id


def update_job_status(
    *,
    job_id: str,
    status: str,
    error: Optional[str] = None,
    started: bool = False,
    finished: bool = False,
) -> None:
    started_clause = ", started_at = COALESCE(started_at, NOW())" if started else ""
    finished_clause = ", finished_at = NOW()" if finished else ""
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE rag_jobs
            SET status = %s,
                error = %s,
                updated_at = NOW()
                {started_clause}
                {finished_clause}
            WHERE id = %s;
            """,
            (status, error, job_id),
        )
        conn.commit()


def create_document(
    *,
    document_id: str,
    file_id: str,
    job_id: Optional[str],
    chunks: int,
    size_bytes: int,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    payload = json.dumps(metadata or {})
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO rag_documents (document_id, file_id, job_id, chunks, size_bytes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (document_id) DO UPDATE
            SET file_id = EXCLUDED.file_id,
                job_id = EXCLUDED.job_id,
                chunks = EXCLUDED.chunks,
                size_bytes = EXCLUDED.size_bytes,
                metadata = EXCLUDED.metadata;
            """,
            (document_id, file_id, job_id, chunks, size_bytes, payload),
        )
        conn.commit()


def list_documents() -> List[Dict[str, Any]]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COALESCE(d.document_id, j.document_id) AS document_id,
                f.original_name,
                f.stored_name,
                COALESCE(d.size_bytes, f.size_bytes),
                COALESCE(d.chunks, 0),
                COALESCE(d.uploaded_at, j.created_at),
                COALESCE(d.metadata, '{}'::jsonb),
                j.id AS job_id,
                j.status,
                j.error
            FROM rag_jobs j
            JOIN rag_files f ON f.id = j.file_id
            LEFT JOIN rag_documents d ON d.document_id = j.document_id
            ORDER BY COALESCE(d.uploaded_at, j.created_at) DESC;
            """
        )
        rows = cursor.fetchall()
    return [
        {
            "document_id": row[0],
            "original_file": row[1],
            "stored_file": row[2],
            "size_bytes": row[3],
            "chunks": row[4],
            "uploaded_at": row[5].isoformat() if row[5] else None,
            "metadata": row[6],
            "job_id": row[7],
            "status": row[8],
            "error": row[9],
        }
        for row in rows
    ]


def get_document_detail(document_id: str) -> Optional[Dict[str, Any]]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COALESCE(d.document_id, j.document_id) AS document_id,
                f.original_name,
                f.stored_name,
                COALESCE(d.size_bytes, f.size_bytes),
                COALESCE(d.chunks, 0),
                COALESCE(d.uploaded_at, j.created_at),
                COALESCE(d.metadata, '{}'::jsonb),
                j.id AS job_id,
                j.status,
                j.error
            FROM rag_jobs j
            JOIN rag_files f ON f.id = j.file_id
            LEFT JOIN rag_documents d ON d.document_id = j.document_id
            WHERE COALESCE(d.document_id, j.document_id) = %s
            ORDER BY COALESCE(d.uploaded_at, j.created_at) DESC
            LIMIT 1;
            """,
            (document_id,),
        )
        row = cursor.fetchone()
    if not row:
        return None
    return {
        "document_id": row[0],
        "original_file": row[1],
        "stored_file": row[2],
        "size_bytes": row[3],
        "chunks": row[4],
        "uploaded_at": row[5].isoformat() if row[5] else None,
        "metadata": row[6],
        "job_id": row[7],
        "status": row[8],
        "error": row[9],
    }


def list_jobs() -> List[Dict[str, Any]]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                j.id,
                j.document_id,
                j.status,
                j.error,
                j.created_at,
                j.updated_at,
                j.started_at,
                j.finished_at,
                f.original_name,
                f.stored_name,
                f.size_bytes
            FROM rag_jobs j
            JOIN rag_files f ON f.id = j.file_id
            ORDER BY j.created_at DESC;
            """
        )
        rows = cursor.fetchall()
    return [
        {
            "job_id": row[0],
            "document_id": row[1],
            "status": row[2],
            "error": row[3],
            "created_at": row[4].isoformat() if row[4] else None,
            "updated_at": row[5].isoformat() if row[5] else None,
            "started_at": row[6].isoformat() if row[6] else None,
            "finished_at": row[7].isoformat() if row[7] else None,
            "original_file": row[8],
            "stored_file": row[9],
            "size_bytes": row[10],
        }
        for row in rows
    ]


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                j.id,
                j.document_id,
                j.status,
                j.error,
                j.created_at,
                j.updated_at,
                j.started_at,
                j.finished_at,
                f.original_name,
                f.stored_name,
                f.size_bytes
            FROM rag_jobs j
            JOIN rag_files f ON f.id = j.file_id
            WHERE j.id = %s;
            """,
            (job_id,),
        )
        row = cursor.fetchone()
    if not row:
        return None
    return {
        "job_id": row[0],
        "document_id": row[1],
        "status": row[2],
        "error": row[3],
        "created_at": row[4].isoformat() if row[4] else None,
        "updated_at": row[5].isoformat() if row[5] else None,
        "started_at": row[6].isoformat() if row[6] else None,
        "finished_at": row[7].isoformat() if row[7] else None,
        "original_file": row[8],
        "stored_file": row[9],
        "size_bytes": row[10],
    }


def get_document(document_id: str) -> Optional[Dict[str, Any]]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                d.document_id,
                f.id,
                f.stored_name,
                f.original_name,
                d.size_bytes,
                d.chunks,
                d.metadata,
                d.job_id
            FROM rag_documents d
            JOIN rag_files f ON f.id = d.file_id
            WHERE d.document_id = %s;
            """,
            (document_id,),
        )
        row = cursor.fetchone()
    if not row:
        return None
    return {
        "document_id": row[0],
        "file_id": row[1],
        "stored_file": row[2],
        "original_file": row[3],
        "size_bytes": row[4],
        "chunks": row[5],
        "metadata": row[6],
        "job_id": row[7],
    }


def delete_document_records(document_id: str) -> Optional[Dict[str, Any]]:
    record = get_document(document_id)
    if not record:
        return None
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM rag_documents WHERE document_id = %s;",
            (document_id,),
        )
        if record.get("job_id"):
            cursor.execute(
                "DELETE FROM rag_jobs WHERE id = %s;",
                (record["job_id"],),
            )
        cursor.execute(
            "DELETE FROM rag_files WHERE id = %s;",
            (record["file_id"],),
        )
        conn.commit()
    return record
