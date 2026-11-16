"""Celery worker configuration and knowledge-base indexing tasks."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from celery import Celery
from celery.signals import worker_process_init

from ..db import rag_documents

BROKER_URL = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery("academic_question_bot", broker=BROKER_URL, backend=BROKER_URL)
celery_app.conf.update(
    task_acks_late=True,  # a crashed worker does not lose the indexing job
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=60 * 30,
    task_soft_time_limit=60 * 25,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=3,
    redis_socket_connect_timeout=3,
    redis_socket_timeout=5,
    result_expires=60 * 60 * 24,
)


@worker_process_init.connect
def _init_worker(**_: Any) -> None:
    try:
        rag_documents.ensure_tables()
    except Exception:  # pragma: no cover - logged by celery
        pass


@celery_app.task(name="workers.index_document")
def index_document_task(document_id: str) -> Dict[str, Any]:
    from ..services.knowledge_base import index_document

    return index_document(document_id)


@celery_app.task(name="workers.ingest_documents")
def ingest_documents(path: Optional[str] = None, *, document_id: Optional[str] = None, **_: Any) -> Dict[str, Any]:
    """Legacy task name kept so messages queued before the upgrade still run."""
    if not document_id:
        return {"status": "error", "detail": "document_id is required"}
    return index_document_task(document_id)
