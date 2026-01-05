"""High level RAG service used by agents and API endpoints."""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import embeddings, loader, retriever
from .vector_store import VectorStore


@dataclass
class DocumentRecord:
    document_id: str
    original_file: str
    stored_file: str
    size_bytes: int
    chunks: int
    uploaded_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "original_file": self.original_file,
            "stored_file": self.stored_file,
            "size_bytes": self.size_bytes,
            "chunks": self.chunks,
            "uploaded_at": self.uploaded_at,
            "metadata": self.metadata,
        }


class RAGService:
    """Wraps loader, embeddings, vector store, and document registry."""

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        storage_root = storage_dir or os.getenv("RAG_STORAGE_PATH", "storage/documents")
        self.storage_dir = Path(storage_root)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.storage_dir / "manifest.json"
        self._manifest: List[DocumentRecord] = self._load_manifest()
        self.vector_store = VectorStore(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            collection_name=os.getenv("QDRANT_COLLECTION", "academic_documents"),
        )

    def ingest_path(
        self,
        path: Path,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[str] = None,
        register: bool = False,
        stored_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Load a file from disk, chunk it and add to the store."""
        doc_id = document_id or (metadata or {}).get("document_id") or uuid.uuid4().hex
        metadata_payload = dict(metadata or {})
        metadata_payload.setdefault("document_id", doc_id)
        if stored_file:
            metadata_payload.setdefault("stored_file", stored_file)
        document_chunks = loader.load_file(path, metadata=metadata_payload)
        vectors = embeddings.embed_documents(document_chunks)
        for chunk, vector in zip(document_chunks, vectors):
            self.vector_store.add(chunk, vector)
        result = {
            "document_id": doc_id,
            "chunks": len(document_chunks),
            "file_name": path.name,
        }
        if register:
            self._register_document(
                document_id=doc_id,
                original_file=metadata_payload.get("original_file", path.name),
                stored_file=stored_file or metadata_payload.get("stored_file") or path.name,
                chunk_count=len(document_chunks),
                size_bytes=path.stat().st_size if path.exists() else 0,
                metadata={
                    k: v
                    for k, v in metadata_payload.items()
                    if k not in {"stored_file", "document_id"}
                },
            )
        return result

    def save_upload(self, filename: str, data: bytes) -> Path:
        """Persist uploaded bytes to disk."""
        safe_name = f"{uuid.uuid4().hex}_{filename}"
        destination = self.storage_dir / safe_name
        destination.write_bytes(data)
        return destination

    def ingest_upload(
        self,
        *,
        filename: str,
        data: bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist the uploaded file and ingest it into the vector store."""
        stored_path = self.save_upload(filename, data)
        document_id = uuid.uuid4().hex
        upload_metadata = {
            "original_file": filename,
            "stored_file": stored_path.name,
            "document_id": document_id,
            **(metadata or {}),
        }
        result = self.ingest_path(
            stored_path,
            metadata=upload_metadata,
            document_id=document_id,
            register=True,
            stored_file=stored_path.name,
        )
        return {**result, "stored_file": stored_path.name}

    def list_documents(self) -> List[Dict[str, Any]]:
        """Return information about ingested documents."""
        return [record.to_dict() for record in sorted(self._manifest, key=lambda x: x.uploaded_at, reverse=True)]

    def delete_document(self, document_id: str) -> Dict[str, Any]:
        """Delete stored file and remove vectors from the store."""
        record = self._find_document(document_id)
        if not record:
            raise KeyError(f"document {document_id} not found")
        stored_file = record.stored_file
        file_path = self.storage_dir / stored_file
        if file_path.exists():
            file_path.unlink()
        self.vector_store.delete_document(document_id)
        self._manifest = [doc for doc in self._manifest if doc.document_id != document_id]
        self._save_manifest()
        return record.to_dict()

    def search(self, query: str, *, top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks for the provided query."""
        results = retriever.retrieve(query, self.vector_store, top_k=top_k)
        return [
            {
                "content": result.chunk.content,
                "score": result.score,
                "metadata": result.chunk.metadata,
            }
            for result in results
        ]

    def _register_document(
        self,
        *,
        document_id: str,
        original_file: str,
        stored_file: str,
        chunk_count: int,
        size_bytes: int,
        metadata: Dict[str, Any],
    ) -> None:
        record = DocumentRecord(
            document_id=document_id,
            original_file=original_file,
            stored_file=stored_file,
            size_bytes=size_bytes,
            chunks=chunk_count,
            uploaded_at=datetime.utcnow().isoformat() + "Z",
            metadata=metadata,
        )
        self._manifest = [doc for doc in self._manifest if doc.document_id != document_id]
        self._manifest.append(record)
        self._save_manifest()

    def _find_document(self, document_id: str) -> Optional[DocumentRecord]:
        for record in self._manifest:
            if record.document_id == document_id:
                return record
        return None

    def _load_manifest(self) -> List[DocumentRecord]:
        if not self.manifest_path.exists():
            return []
        try:
            raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        records: List[DocumentRecord] = []
        for item in raw:
            try:
                records.append(
                    DocumentRecord(
                        document_id=item["document_id"],
                        original_file=item.get("original_file", ""),
                        stored_file=item.get("stored_file", ""),
                        size_bytes=item.get("size_bytes", 0),
                        chunks=item.get("chunks", 0),
                        uploaded_at=item.get("uploaded_at", ""),
                        metadata=item.get("metadata", {}),
                    )
                )
            except KeyError:
                continue
        return records

    def _save_manifest(self) -> None:
        serialized = [record.to_dict() for record in self._manifest]
        self.manifest_path.write_text(json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8")


rag_service = RAGService()
