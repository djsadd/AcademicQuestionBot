"""Postgres registry of knowledge-base documents, their files and ingestion jobs.

One uploaded file ↔ one job row ↔ (after successful indexing) one document row.
Re-indexing reuses the same job row, so a document never appears twice.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from .session import get_connection

_get_connection = get_connection

DOCUMENT_SELECT = """
    SELECT
        j.document_id,
        f.original_name,
        f.stored_name,
        COALESCE(d.size_bytes, f.size_bytes),
        COALESCE(d.chunks, 0),
        COALESCE(d.uploaded_at, j.created_at),
        COALESCE(d.metadata, j.metadata, '{}'::jsonb),
        j.id,
        j.status,
        j.error,
        f.id,
        f.content_type,
        f.content_hash,
        j.updated_at,
        j.finished_at
    FROM rag_jobs j
    JOIN rag_files f ON f.id = j.file_id
    LEFT JOIN rag_documents d ON d.document_id = j.document_id
"""


def _row_to_document(row: tuple) -> Dict[str, Any]:
    metadata = row[6] or {}
    return {
        "document_id": row[0],
        "original_file": row[1],
        "stored_file": row[2],
        "size_bytes": row[3],
        "chunks": row[4],
        "uploaded_at": row[5].isoformat() if row[5] else None,
        "metadata": metadata,
        "title": metadata.get("title") or row[1],
        "category": metadata.get("category"),
        "audience": metadata.get("audience"),
        "job_id": row[7],
        "status": row[8],
        "error": row[9],
        "file_id": row[10],
        "content_type": row[11],
        "content_hash": row[12],
        "updated_at": row[13].isoformat() if row[13] else None,
        "indexed_at": row[14].isoformat() if row[14] else None,
    }


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
        cursor.execute("ALTER TABLE rag_files ADD COLUMN IF NOT EXISTS content_hash TEXT;")
        cursor.execute("CREATE INDEX IF NOT EXISTS rag_files_content_hash_idx ON rag_files (content_hash);")
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
        # Metadata entered at upload time lives on the job until indexing succeeds.
        cursor.execute("ALTER TABLE rag_jobs ADD COLUMN IF NOT EXISTS metadata JSONB;")
        cursor.execute("CREATE INDEX IF NOT EXISTS rag_jobs_document_id_idx ON rag_jobs (document_id);")
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


# ------------------------------------------------------------------ writes
def create_file(
    *,
    original_name: str,
    stored_name: str,
    content_type: Optional[str],
    size_bytes: int,
    content_hash: Optional[str] = None,
) -> str:
    file_id = uuid.uuid4().hex
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO rag_files (id, original_name, stored_name, content_type, size_bytes, content_hash)
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            (file_id, original_name, stored_name, content_type, size_bytes, content_hash),
        )
        conn.commit()
    return file_id


def create_job(
    *,
    file_id: str,
    document_id: str,
    status: str = "queued",
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    job_id = uuid.uuid4().hex
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO rag_jobs (id, file_id, document_id, status, metadata)
            VALUES (%s, %s, %s, %s, %s::jsonb);
            """,
            (job_id, file_id, document_id, status, json.dumps(metadata or {}, ensure_ascii=False)),
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
    reset: bool = False,
) -> None:
    clauses = []
    if started:
        clauses.append("started_at = NOW()")
    elif reset:
        clauses.append("started_at = NULL")
    if finished:
        clauses.append("finished_at = NOW()")
    elif reset or started:
        clauses.append("finished_at = NULL")
    extra = (", " + ", ".join(clauses)) if clauses else ""
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            f"UPDATE rag_jobs SET status = %s, error = %s, updated_at = NOW(){extra} WHERE id = %s;",
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
            (document_id, file_id, job_id, chunks, size_bytes, json.dumps(metadata or {}, ensure_ascii=False)),
        )
        conn.commit()


def update_metadata(document_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Merge ``patch`` into the document (and job) metadata."""
    payload = json.dumps(patch, ensure_ascii=False)
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE rag_documents SET metadata = metadata || %s::jsonb WHERE document_id = %s;",
            (payload, document_id),
        )
        cursor.execute(
            "UPDATE rag_jobs SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb, updated_at = NOW() WHERE document_id = %s;",
            (payload, document_id),
        )
        conn.commit()
    return get_document_detail(document_id)


def delete_document_full(document_id: str) -> Optional[Dict[str, Any]]:
    """Remove every row of a document, including failed or still-queued uploads."""
    record = get_document_detail(document_id)
    if not record:
        return None
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute("DELETE FROM rag_documents WHERE document_id = %s;", (document_id,))
        cursor.execute("DELETE FROM rag_jobs WHERE document_id = %s;", (document_id,))
        if record.get("file_id"):
            cursor.execute("DELETE FROM rag_files WHERE id = %s;", (record["file_id"],))
        conn.commit()
    return record


# ------------------------------------------------------------------- reads
def list_documents() -> List[Dict[str, Any]]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(DOCUMENT_SELECT + " ORDER BY COALESCE(d.uploaded_at, j.created_at) DESC;")
        rows = cursor.fetchall()
    return [_row_to_document(row) for row in rows]


def get_document_detail(document_id: str) -> Optional[Dict[str, Any]]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            DOCUMENT_SELECT + " WHERE j.document_id = %s ORDER BY j.created_at DESC LIMIT 1;",
            (document_id,),
        )
        row = cursor.fetchone()
    return _row_to_document(row) if row else None


# Backwards compatible name.
get_document = get_document_detail


def find_by_hash(content_hash: str) -> Optional[Dict[str, Any]]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            DOCUMENT_SELECT + " WHERE f.content_hash = %s ORDER BY j.created_at DESC LIMIT 1;",
            (content_hash,),
        )
        row = cursor.fetchone()
    return _row_to_document(row) if row else None


def stats() -> Dict[str, Any]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT j.status, COUNT(*), COALESCE(SUM(d.chunks), 0), COALESCE(SUM(f.size_bytes), 0)
            FROM rag_jobs j
            JOIN rag_files f ON f.id = j.file_id
            LEFT JOIN rag_documents d ON d.document_id = j.document_id
            GROUP BY j.status;
            """
        )
        rows = cursor.fetchall()
    by_status = {row[0]: int(row[1]) for row in rows}
    return {
        "documents": sum(by_status.values()),
        "by_status": by_status,
        "chunks": int(sum(row[2] for row in rows)),
        "size_bytes": int(sum(row[3] for row in rows)),
    }


def _row_to_job(row: tuple) -> Dict[str, Any]:
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


JOB_SELECT = """
    SELECT j.id, j.document_id, j.status, j.error, j.created_at, j.updated_at,
           j.started_at, j.finished_at, f.original_name, f.stored_name, f.size_bytes
    FROM rag_jobs j
    JOIN rag_files f ON f.id = j.file_id
"""


def list_jobs(limit: int = 200) -> List[Dict[str, Any]]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(JOB_SELECT + " ORDER BY j.updated_at DESC LIMIT %s;", (limit,))
        rows = cursor.fetchall()
    return [_row_to_job(row) for row in rows]


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(JOB_SELECT + " WHERE j.id = %s;", (job_id,))
        row = cursor.fetchone()
    return _row_to_job(row) if row else None
