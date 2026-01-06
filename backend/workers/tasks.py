"""Celery worker configuration and ingestion tasks."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from celery import Celery

from ..rag.service import rag_service
from ..db import rag_documents

BROKER_URL = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "academic_question_bot",
    broker=BROKER_URL,
    backend=BROKER_URL,
)


@celery_app.task(name="workers.ingest_documents")
def ingest_documents(
    path: Optional[str] = None,
    *,
    metadata: Optional[Dict[str, Any]] = None,
    document_id: Optional[str] = None,
    stored_file: Optional[str] = None,
    job_id: Optional[str] = None,
    file_id: Optional[str] = None,
    db_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Ingest a saved document into the vector store."""
    if not path:
        return {"status": "error", "detail": "path is required"}
    file_path = Path(path)
    if not file_path.exists():
        return {"status": "error", "detail": f"path not found: {path}"}

    rag_documents.ensure_tables()
    if job_id:
        rag_documents.update_job_status(job_id=job_id, status="processing", started=True)

    try:
        result = rag_service.ingest_path(
            file_path,
            metadata=metadata,
            document_id=document_id,
            register=True,
            stored_file=stored_file,
        )
        if document_id and file_id:
            rag_documents.create_document(
                document_id=document_id,
                file_id=file_id,
                job_id=job_id,
                chunks=result.get("chunks", 0),
                size_bytes=file_path.stat().st_size,
                metadata=db_metadata,
            )
        if job_id:
            rag_documents.update_job_status(job_id=job_id, status="ingested", finished=True)
        return {"status": "ingested", **result}
    except Exception as exc:  # pragma: no cover - Celery will log
        if job_id:
            rag_documents.update_job_status(
                job_id=job_id,
                status="failed",
                error=str(exc),
                finished=True,
            )
        raise
