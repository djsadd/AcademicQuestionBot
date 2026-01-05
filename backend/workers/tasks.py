"""Celery worker configuration and sample tasks."""
from __future__ import annotations

import os
from typing import Optional

from celery import Celery

BROKER_URL = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "academic_question_bot",
    broker=BROKER_URL,
    backend=BROKER_URL,
)


@celery_app.task(name="workers.ingest_documents")
def ingest_documents(path: Optional[str] = None) -> str:
    """Placeholder ingestion task."""
    _ = path
    return "ingestion scheduled"
