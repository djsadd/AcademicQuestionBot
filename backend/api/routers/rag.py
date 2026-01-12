"""Endpoints for uploading documents, querying, and managing RAG storage."""
from __future__ import annotations

import json
import uuid
from typing import Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ...rag.service import rag_service
from ...db import rag_documents
from ...workers.tasks import celery_app, ingest_documents
from ...services.permissions import require_admin

router = APIRouter(prefix="/rag", tags=["rag"], dependencies=[Depends(require_admin)])


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
) -> Dict[str, object]:
    """Handle file uploads and ingest them into the vector store."""
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    rag_documents.ensure_tables()
    try:
        parsed_metadata = _parse_metadata(metadata)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stored_path = rag_service.save_upload(file.filename, contents)
    document_id = uuid.uuid4().hex
    file_id = rag_documents.create_file(
        original_name=file.filename,
        stored_name=stored_path.name,
        content_type=file.content_type,
        size_bytes=len(contents),
    )
    job_id = rag_documents.create_job(file_id=file_id, document_id=document_id, status="queued")
    upload_metadata = {
        "original_file": file.filename,
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
        raise HTTPException(status_code=503, detail=f"Failed to enqueue ingestion: {exc}") from exc

    return {
        "status": "queued",
        "task_id": task.id,
        "document_id": document_id,
        "stored_file": stored_path.name,
        "file_name": file.filename,
        "job_id": job_id,
    }


@router.get("/documents")
async def list_documents() -> Dict[str, object]:
    """List all ingested documents."""
    return {"documents": rag_documents.list_documents()}


@router.get("/documents/{document_id}")
async def get_document(document_id: str) -> Dict[str, object]:
    """Return metadata for a single document."""
    rag_documents.ensure_tables()
    record = rag_documents.get_document_detail(document_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"document {document_id} not found")
    return {"document": record}


@router.get("/documents/{document_id}/chunks")
async def list_document_chunks(document_id: str, limit: int = 200) -> Dict[str, object]:
    """Return raw chunks stored in the vector index for a document."""
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be greater than 0")
    rag_documents.ensure_tables()
    record = rag_documents.get_document_detail(document_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"document {document_id} not found")
    chunks = rag_service.list_document_chunks(document_id, limit=limit)
    return {"document_id": document_id, "chunks": chunks}


@router.get("/jobs")
async def list_jobs() -> Dict[str, object]:
    """List all ingestion jobs."""
    rag_documents.ensure_tables()
    return {"jobs": rag_documents.list_jobs()}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> Dict[str, object]:
    """Return a single ingestion job."""
    rag_documents.ensure_tables()
    job = rag_documents.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    return {"job": job}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str) -> Dict[str, object]:
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


@router.get("/documents/search")
async def search_documents(query: str, top_k: int = 3) -> Dict[str, object]:
    """Return the most relevant chunks for the provided query."""
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required.")

    results = rag_service.search(query, top_k=top_k)
    return {"query": query, "results": results}


@router.get("/tasks/{task_id}")
async def task_status(task_id: str) -> Dict[str, object]:
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
