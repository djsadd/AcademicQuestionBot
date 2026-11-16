"""Endpoints for uploading documents, querying, and managing RAG storage."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from ...rag.service import rag_service
from ...db import rag_documents
from ...workers.tasks import celery_app, ingest_documents
from ...services.permissions import require_admin

router = APIRouter(prefix="/rag", tags=["rag"], dependencies=[Depends(require_admin)])


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_UPLOAD_BYTES = int(os.getenv("RAG_MAX_UPLOAD_MB", "50")) * 1024 * 1024


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
) -> Dict[str, object]:
    """Validate the upload, persist it and queue ingestion in the Celery worker."""
    filename = Path(file.filename or "").name
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large.")
    try:
        parsed_metadata = _parse_metadata(metadata)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await run_in_threadpool(_store_and_enqueue, filename, file.content_type, contents, parsed_metadata)


def _store_and_enqueue(
    filename: str,
    content_type: Optional[str],
    contents: bytes,
    parsed_metadata: Dict[str, object],
) -> Dict[str, object]:
    stored_path = rag_service.save_upload(filename, contents)
    document_id = uuid.uuid4().hex
    file_id = rag_documents.create_file(
        original_name=filename,
        stored_name=stored_path.name,
        content_type=content_type,
        size_bytes=len(contents),
    )
    job_id = rag_documents.create_job(file_id=file_id, document_id=document_id, status="queued")
    upload_metadata = {
        "original_file": filename,
        "file_name": filename,
        "stored_file": stored_path.name,
        "document_id": document_id,
        **parsed_metadata,
    }
    try:
        task = ingest_documents.delay(
            str(stored_path),
            metadata=upload_metadata,
            document_id=document_id,
            stored_file=stored_path.name,
            job_id=job_id,
            file_id=file_id,
            db_metadata=parsed_metadata,
        )
    except Exception as exc:
        rag_documents.update_job_status(job_id=job_id, status="failed", error=str(exc), finished=True)
        raise HTTPException(status_code=503, detail="Failed to enqueue ingestion.") from exc

    return {
        "status": "queued",
        "task_id": task.id,
        "document_id": document_id,
        "stored_file": stored_path.name,
        "file_name": filename,
        "job_id": job_id,
    }


@router.get("/documents")
def list_documents() -> Dict[str, object]:
    """List all ingested documents."""
    return {"documents": rag_documents.list_documents()}


@router.get("/documents/search")
def search_documents(query: str, top_k: int = 3) -> Dict[str, object]:
    """Return the most relevant chunks for the provided query."""
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required.")

    results = rag_service.search(query, top_k=max(1, min(top_k, 20)))
    return {"query": query, "results": results}


@router.get("/documents/{document_id}")
def get_document(document_id: str) -> Dict[str, object]:
    """Return metadata for a single document."""
    record = rag_documents.get_document_detail(document_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"document {document_id} not found")
    return {"document": record}


@router.get("/documents/{document_id}/chunks")
def list_document_chunks(document_id: str, limit: int = 200) -> Dict[str, object]:
    """Return raw chunks stored in the vector index for a document."""
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be greater than 0")
    record = rag_documents.get_document_detail(document_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"document {document_id} not found")
    chunks = rag_service.list_document_chunks(document_id, limit=limit)
    return {"document_id": document_id, "chunks": chunks}


@router.get("/jobs")
def list_jobs() -> Dict[str, object]:
    """List all ingestion jobs."""
    return {"jobs": rag_documents.list_jobs()}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, object]:
    """Return a single ingestion job."""
    job = rag_documents.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    return {"job": job}


@router.delete("/documents/{document_id}")
def delete_document(document_id: str) -> Dict[str, object]:
    """Delete the stored file and remove its vectors."""
    record = rag_documents.get_document(document_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"document {document_id} not found")
    try:
        deleted = rag_service.delete_document(document_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rag_documents.delete_document_records(document_id)
    return {"status": "deleted", "document": deleted, "db_record": record}




@router.get("/tasks/{task_id}")
def task_status(task_id: str) -> Dict[str, object]:
    """Return Celery task status for document ingestion."""
    result = celery_app.AsyncResult(task_id)
    payload: Dict[str, object] = {"task_id": task_id, "status": result.status}
    if result.successful():
        payload["result"] = result.result
    elif result.failed():
        payload["error"] = str(result.result)
    return payload


def _parse_metadata(metadata: Optional[str]) -> Dict[str, object]:
    if not metadata:
        return {}
    try:
        parsed = json.loads(metadata)
    except json.JSONDecodeError as exc:  # pragma: no cover - FastAPI handles
        raise ValueError("metadata must be a valid JSON object") from exc
    if not isinstance(parsed, dict):
        raise ValueError("metadata must be a JSON object")
    return parsed
