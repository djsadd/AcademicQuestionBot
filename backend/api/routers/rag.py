"""Endpoints for uploading documents, querying, and managing RAG storage."""
from __future__ import annotations

import json
from typing import Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ...rag.service import rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
) -> Dict[str, object]:
    """Handle file uploads and ingest them into the vector store."""
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        parsed_metadata = _parse_metadata(metadata)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ingestion_result = rag_service.ingest_upload(
        filename=file.filename,
        data=contents,
        metadata=parsed_metadata,
    )
    return {"status": "ingested", **ingestion_result}


@router.get("/documents")
async def list_documents() -> Dict[str, object]:
    """List all ingested documents."""
    return {"documents": rag_service.list_documents()}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str) -> Dict[str, object]:
    """Delete the stored file and remove its vectors."""
    try:
        deleted = rag_service.delete_document(document_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted", "document": deleted}


@router.get("/documents/search")
async def search_documents(query: str, top_k: int = 3) -> Dict[str, object]:
    """Return the most relevant chunks for the provided query."""
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required.")

    results = rag_service.search(query, top_k=top_k)
    return {"query": query, "results": results}


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
