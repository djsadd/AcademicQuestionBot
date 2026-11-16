"""Knowledge-base workflows: upload → register → index, re-index, delete.

Shared by the HTTP API, the Celery worker and the CLI script so every path
keeps Postgres (registry), disk (files) and Qdrant (vectors) consistent.
"""
from __future__ import annotations

import logging
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..db import rag_documents
from ..rag.embeddings import EmbeddingError
from ..rag.loader import SUPPORTED_SUFFIXES, DocumentParseError
from ..rag.service import rag_service

logger = logging.getLogger(__name__)

CATEGORIES = {
    "regulation": "Положение / регламент",
    "order": "Приказ",
    "curriculum": "Учебный план / ОП",
    "schedule": "Календарь / расписание",
    "admission": "Приём",
    "faq": "FAQ / инструкция",
    "other": "Другое",
}
AUDIENCES = {"all": "Все", "students": "Студенты", "applicants": "Абитуриенты", "staff": "Сотрудники"}
EDITABLE_FIELDS = {"title", "category", "audience", "description"}


class DuplicateDocumentError(Exception):
    def __init__(self, existing: Dict[str, Any]) -> None:
        super().__init__("duplicate document")
        self.existing = existing


def clean_metadata(raw: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key in EDITABLE_FIELDS:
        value = raw.get(key)
        if value is None:
            continue
        value = str(value).strip()[:500]
        if key == "category" and value not in CATEGORIES:
            value = "other"
        if key == "audience" and value not in AUDIENCES:
            value = "all"
        if value:
            result[key] = value
    return result


# ------------------------------------------------------------------ upload
def register_upload(
    *,
    filename: str,
    content_type: Optional[str],
    data: bytes,
    metadata: Optional[Dict[str, Any]] = None,
    allow_duplicate: bool = False,
) -> Dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise DocumentParseError(f"Формат {suffix or '—'} не поддерживается.")
    content_hash = rag_service.content_hash(data)
    if not allow_duplicate:
        existing = rag_documents.find_by_hash(content_hash)
        if existing:
            raise DuplicateDocumentError(existing)

    document_id = uuid.uuid4().hex
    meta = clean_metadata(metadata or {})
    meta.setdefault("title", Path(filename).stem.replace("_", " ").strip() or filename)
    stored_path = rag_service.save_upload(filename, data)
    file_id = rag_documents.create_file(
        original_name=filename,
        stored_name=stored_path.name,
        content_type=content_type,
        size_bytes=len(data),
        content_hash=content_hash,
    )
    job_id = rag_documents.create_job(file_id=file_id, document_id=document_id, status="queued", metadata=meta)
    return {"document_id": document_id, "job_id": job_id, "file_id": file_id, "stored_file": stored_path.name, "file_name": filename}


# ------------------------------------------------------------------ indexing
def index_document(document_id: str) -> Dict[str, Any]:
    """Synchronously (re)index a registered document. Records status in Postgres."""
    record = rag_documents.get_document_detail(document_id)
    if not record:
        raise KeyError(f"document {document_id} not found")
    job_id = record["job_id"]
    rag_documents.update_job_status(job_id=job_id, status="processing", started=True, reset=True)
    metadata = {key: value for key, value in (record.get("metadata") or {}).items() if key in EDITABLE_FIELDS}
    try:
        path = rag_service.file_path(record["stored_file"])
        if not path.exists():
            raise DocumentParseError("Исходный файл не найден в хранилище. Загрузите документ заново.")
        result = rag_service.ingest_path(
            path,
            document_id=document_id,
            metadata={
                **metadata,
                "original_file": record["original_file"],
                "file_name": record["original_file"],
                "stored_file": record["stored_file"],
            },
        )
        rag_documents.create_document(
            document_id=document_id,
            file_id=record["file_id"],
            job_id=job_id,
            chunks=result["chunks"],
            size_bytes=record["size_bytes"] or 0,
            metadata={**metadata, "pages": result.get("pages"), "characters": result.get("characters")},
        )
        rag_documents.update_job_status(job_id=job_id, status="ingested", finished=True)
        return {"status": "ingested", **result}
    except (DocumentParseError, EmbeddingError) as exc:
        rag_documents.update_job_status(job_id=job_id, status="failed", error=str(exc), finished=True)
        return {"status": "failed", "document_id": document_id, "error": str(exc)}
    except Exception as exc:
        logger.exception("Indexing failed for %s", document_id)
        rag_documents.update_job_status(job_id=job_id, status="failed", error=f"Внутренняя ошибка: {exc}"[:500], finished=True)
        raise


def _broker_reachable(timeout: float = 1.0) -> bool:
    """Cheap TCP probe so a dead broker costs ~1 s instead of Celery's long reconnect loop."""
    import socket
    from urllib.parse import urlparse

    from ..workers.tasks import BROKER_URL

    parsed = urlparse(BROKER_URL)
    try:
        with socket.create_connection((parsed.hostname or "localhost", parsed.port or 6379), timeout=timeout):
            return True
    except OSError:
        return False


def enqueue_index(document_id: str) -> str:
    """Queue indexing in Celery; fall back to a background thread if the broker is down."""
    record = rag_documents.get_document_detail(document_id)
    if record:
        rag_documents.update_job_status(job_id=record["job_id"], status="queued", reset=True)
    try:
        if not _broker_reachable():
            raise ConnectionError("broker is unreachable")
        from ..workers.tasks import index_document_task

        # Fail fast when the broker is down instead of blocking the HTTP request
        # through Celery's default publish retries.
        return index_document_task.apply_async(
            args=[document_id],
            retry=True,
            retry_policy={"max_retries": 1, "interval_start": 0, "interval_step": 0.5, "timeout": 3},
            ignore_result=False,
        ).id
    except Exception as exc:  # broker unavailable
        logger.warning("Celery unavailable (%s); indexing %s in-process", exc, document_id)
        thread = threading.Thread(target=_safe_index, args=(document_id,), name=f"index-{document_id[:8]}", daemon=True)
        thread.start()
        return f"local-{document_id}"


def _safe_index(document_id: str) -> None:
    try:
        index_document(document_id)
    except Exception:
        logger.exception("Background indexing failed for %s", document_id)


def reindex_all(*, recreate_collection: bool = False) -> List[str]:
    if recreate_collection:
        rag_service.vector_store.recreate()
    queued: List[str] = []
    for document in rag_documents.list_documents():
        if document.get("document_id"):
            enqueue_index(document["document_id"])
            queued.append(document["document_id"])
    return queued


# ------------------------------------------------------------------- delete
def delete_document(document_id: str) -> Optional[Dict[str, Any]]:
    record = rag_documents.get_document_detail(document_id)
    if not record:
        return None
    try:
        rag_service.delete_vectors(document_id)
    except Exception:
        logger.warning("Vector cleanup failed for %s", document_id, exc_info=True)
    rag_service.remove_file(record.get("stored_file"))
    rag_documents.delete_document_full(document_id)
    return record
