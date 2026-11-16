"""Knowledge-base (RAG) administration API."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ...db import rag_documents
from ...rag.loader import SUPPORTED_SUFFIXES, DocumentParseError
from ...rag.service import rag_service
from ...services import knowledge_base as kb
from ...services.permissions import require_admin
from ...workers.tasks import celery_app

router = APIRouter(prefix="/rag", tags=["rag"], dependencies=[Depends(require_admin)])

ALLOWED_EXTENSIONS = SUPPORTED_SUFFIXES
MAX_UPLOAD_BYTES = int(os.getenv("RAG_MAX_UPLOAD_MB", "50")) * 1024 * 1024


class MetadataPatch(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    audience: Optional[str] = None
    description: Optional[str] = None


# ----------------------------------------------------------------- overview
@router.get("/stats")
def knowledge_base_stats() -> Dict[str, Any]:
    """Registry counters + vector index health (dimension mismatch, points)."""
    return {
        "registry": rag_documents.stats(),
        "index": rag_service.index_info(),
        "categories": kb.CATEGORIES,
        "audiences": kb.AUDIENCES,
        "limits": {"max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024), "extensions": sorted(ALLOWED_EXTENSIONS)},
    }


# ------------------------------------------------------------------ upload
@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    audience: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    allow_duplicate: bool = Form(False),
) -> Dict[str, Any]:
    """Validate the upload, register it and queue indexing."""
    filename = Path(file.filename or "").name
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Неподдерживаемый формат. Допустимо: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Файл пустой.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Файл больше {MAX_UPLOAD_BYTES // (1024 * 1024)} МБ.")
    try:
        extra = _parse_metadata(metadata)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    fields = {**extra, "title": title, "category": category, "audience": audience, "description": description}

    def _register() -> Dict[str, Any]:
        registered = kb.register_upload(
            filename=filename,
            content_type=file.content_type,
            data=contents,
            metadata={key: value for key, value in fields.items() if value},
            allow_duplicate=allow_duplicate,
        )
        task_id = kb.enqueue_index(registered["document_id"])
        return {"status": "queued", "task_id": task_id, **registered}

    try:
        return await run_in_threadpool(_register)
    except kb.DuplicateDocumentError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Этот файл уже загружен как «{exc.existing.get('title')}».",
        ) from exc
    except DocumentParseError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc


# --------------------------------------------------------------- documents
@router.get("/documents")
def list_documents() -> Dict[str, Any]:
    return {"documents": rag_documents.list_documents()}


@router.get("/documents/search")
def search_documents(
    query: str = Query(..., min_length=1, max_length=500),
    top_k: int = Query(5, ge=1, le=20),
    compress: bool = False,
    hybrid: bool = True,
) -> Dict[str, Any]:
    """Retrieval playground: exactly what agents receive for this query."""
    results = rag_service.search(query, top_k=top_k, compress=compress, hybrid=hybrid)
    return {"query": query, "results": results}


@router.get("/documents/{document_id}")
def get_document(document_id: str) -> Dict[str, Any]:
    record = rag_documents.get_document_detail(document_id)
    if not record:
        raise HTTPException(status_code=404, detail="Документ не найден.")
    return {"document": record}


@router.patch("/documents/{document_id}")
def update_document(document_id: str, payload: MetadataPatch) -> Dict[str, Any]:
    patch = kb.clean_metadata(payload.model_dump(exclude_none=True))
    if not patch:
        raise HTTPException(status_code=400, detail="Нет полей для обновления.")
    record = rag_documents.update_metadata(document_id, patch)
    if not record:
        raise HTTPException(status_code=404, detail="Документ не найден.")
    return {"document": record, "reindex_recommended": "title" in patch}


@router.get("/documents/{document_id}/chunks")
def list_document_chunks(document_id: str, limit: int = Query(500, ge=1, le=2000)) -> Dict[str, Any]:
    if not rag_documents.get_document_detail(document_id):
        raise HTTPException(status_code=404, detail="Документ не найден.")
    chunks = rag_service.list_document_chunks(document_id, limit=limit)
    return {"document_id": document_id, "chunks": chunks}


@router.get("/documents/{document_id}/file")
def download_document(document_id: str) -> FileResponse:
    record = rag_documents.get_document_detail(document_id)
    if not record:
        raise HTTPException(status_code=404, detail="Документ не найден.")
    path = rag_service.file_path(record["stored_file"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл отсутствует в хранилище.")
    return FileResponse(path, filename=record["original_file"], media_type=record.get("content_type") or None)


@router.post("/documents/{document_id}/reindex")
def reindex_document(document_id: str) -> Dict[str, Any]:
    if not rag_documents.get_document_detail(document_id):
        raise HTTPException(status_code=404, detail="Документ не найден.")
    return {"status": "queued", "task_id": kb.enqueue_index(document_id)}


@router.delete("/documents/{document_id}")
def delete_document(document_id: str) -> Dict[str, Any]:
    record = kb.delete_document(document_id)
    if not record:
        raise HTTPException(status_code=404, detail="Документ не найден.")
    return {"status": "deleted", "document": record}


@router.post("/reindex-all")
def reindex_all(recreate_collection: bool = False) -> Dict[str, Any]:
    """Re-index every document (optionally recreating the collection after an embeddings model change)."""
    queued = kb.reindex_all(recreate_collection=recreate_collection)
    return {"status": "queued", "documents": len(queued)}


# -------------------------------------------------------------------- jobs
@router.get("/jobs")
def list_jobs() -> Dict[str, Any]:
    return {"jobs": rag_documents.list_jobs()}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    job = rag_documents.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    return {"job": job}


@router.get("/tasks/{task_id}")
def task_status(task_id: str) -> Dict[str, Any]:
    if task_id.startswith("local-"):
        record = rag_documents.get_document_detail(task_id.removeprefix("local-"))
        status = (record or {}).get("status") or "PENDING"
        return {"task_id": task_id, "status": {"ingested": "SUCCESS", "failed": "FAILURE"}.get(status, "PENDING")}
    result = celery_app.AsyncResult(task_id)
    payload: Dict[str, Any] = {"task_id": task_id, "status": result.status}
    if result.successful():
        payload["result"] = result.result
    elif result.failed():
        payload["error"] = str(result.result)
    return payload


def _parse_metadata(metadata: Optional[str]) -> Dict[str, Any]:
    if not metadata:
        return {}
    try:
        parsed = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise ValueError("metadata должен быть корректным JSON-объектом") from exc
    if not isinstance(parsed, dict):
        raise ValueError("metadata должен быть JSON-объектом")
    return parsed
