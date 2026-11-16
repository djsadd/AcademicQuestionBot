"""High level RAG service used by agents, API endpoints and the Celery worker.

PostgreSQL (``backend.db.rag_documents``) is the single registry of uploaded
documents; this service owns the files on disk and the vectors in Qdrant.

Retrieval is *hybrid*: the vector index returns a wider candidate set which
is re-ranked with a lexical score (stemmed term overlap). Short, exact
queries such as "пересдача" or "приказ 123" benefit a lot from this compared
to pure semantic search.
"""
from __future__ import annotations

import hashlib
import logging

import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import embeddings, loader
from .compression import compress_context
from .embeddings import EmbeddingError
from .vector_store import VectorStore

logger = logging.getLogger(__name__)

VECTOR_WEIGHT = 0.75
LEXICAL_WEIGHT = 0.25
CANDIDATE_MULTIPLIER = 3
_WORD = re.compile(r"[0-9a-zа-яёәіңғүұқөһ]+", re.IGNORECASE)
_STOPWORDS = {
    "и", "в", "во", "на", "с", "со", "по", "к", "о", "об", "у", "за", "из", "от", "до", "для", "не", "ли", "а", "но",
    "как", "что", "это", "мне", "мой", "моя", "я", "ты", "вы", "он", "она", "они", "какой", "какие", "какая", "где",
    "когда", "можно", "нужно", "ли", "the", "a", "an", "of", "to", "in", "is", "for", "and", "or", "how", "what",
}


def _terms(text: str) -> List[str]:
    """Lower-cased, crudely stemmed content words."""
    terms: List[str] = []
    for word in _WORD.findall((text or "").lower()):
        if word in _STOPWORDS or len(word) < 2:
            continue
        terms.append(word[:-2] if len(word) >= 7 else word[:-1] if len(word) >= 5 else word)
    return terms


def lexical_score(query: str, content: str) -> float:
    query_terms = set(_terms(query))
    if not query_terms:
        return 0.0
    content_terms = _terms(content)
    if not content_terms:
        return 0.0
    content_set = set(content_terms)
    hits = sum(1 for term in query_terms if term in content_set or any(c.startswith(term) for c in content_set))
    return hits / len(query_terms)


class RAGService:
    """Files on disk + vectors in Qdrant."""

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        storage_root = storage_dir or os.getenv("RAG_STORAGE_PATH", "storage/documents")
        self.storage_dir = Path(storage_root)
        self._vector_store: Optional[VectorStore] = None
        self._store_lock = threading.Lock()

    @property
    def vector_store(self) -> VectorStore:
        """Connect to Qdrant lazily, on first use, instead of at import time."""
        if self._vector_store is None:
            with self._store_lock:
                if self._vector_store is None:
                    self._vector_store = VectorStore(
                        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
                        collection_name=os.getenv("QDRANT_COLLECTION", "academic_documents"),
                    )
        return self._vector_store

    # ------------------------------------------------------------ files
    def save_upload(self, filename: str, data: bytes) -> Path:
        """Persist uploaded bytes to disk (the client file name is never trusted as a path)."""
        base_name = Path(filename or "upload").name.replace("\\", "_") or "upload"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        destination = self.storage_dir / f"{uuid.uuid4().hex}_{base_name}"
        destination.write_bytes(data)
        return destination

    def file_path(self, stored_file: str) -> Path:
        path = (self.storage_dir / Path(stored_file).name).resolve()
        if self.storage_dir.resolve() not in path.parents:
            raise ValueError("Invalid stored file name")
        return path

    def remove_file(self, stored_file: Optional[str]) -> None:
        if not stored_file:
            return
        try:
            path = self.file_path(stored_file)
            if path.exists():
                path.unlink()
        except (OSError, ValueError):
            logger.warning("Could not remove stored file %s", stored_file, exc_info=True)

    @staticmethod
    def content_hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    # ---------------------------------------------------------- indexing
    def ingest_path(
        self,
        path: Path,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        """Parse, chunk, embed and (re)index a document. Idempotent per document_id."""
        doc_id = document_id or (metadata or {}).get("document_id") or uuid.uuid4().hex
        metadata_payload = {**(metadata or {}), "document_id": doc_id}
        chunks = loader.load_file(path, metadata=metadata_payload)
        vectors = embeddings.embed_texts([loader.embedding_text(chunk) for chunk in chunks])
        # Re-indexing: drop the old points first so shrinking documents leave no orphans.
        self.vector_store.delete_document(doc_id)
        self.vector_store.add_many(list(zip(chunks, vectors)))
        pages = {chunk.metadata.get("page_end") or chunk.metadata.get("page") for chunk in chunks}
        pages.discard(None)
        logger.info("Indexed %s chunks from %s", len(chunks), path.name)
        return {
            "document_id": doc_id,
            "chunks": len(chunks),
            "pages": max(pages) if pages else None,
            "characters": sum(len(chunk.content) for chunk in chunks),
            "file_name": path.name,
        }

    def delete_vectors(self, document_id: str) -> None:
        self.vector_store.delete_document(document_id)

    # ----------------------------------------------------------- search
    def search(
        self,
        query: str,
        *,
        top_k: int = 3,
        compress: bool = False,
        min_score: Optional[float] = None,
        hybrid: bool = True,
    ) -> List[Dict[str, Any]]:
        """Hybrid retrieval: vector candidates re-ranked with a lexical score."""
        query = (query or "").strip()
        if not query:
            return []
        candidates = top_k * CANDIDATE_MULTIPLIER if hybrid else top_k
        try:
            vector = embeddings.embed_text(query)
            results = self.vector_store.search(vector, top_k=max(candidates, top_k))
        except EmbeddingError as exc:
            logger.warning("RAG search skipped: %s", exc)
            return []
        except Exception as exc:  # pragma: no cover - infra failure
            logger.warning("RAG search failed: %s", exc)
            return []

        payload: List[Dict[str, Any]] = []
        seen_content: set[str] = set()
        for result in results:
            fingerprint = hashlib.sha1(result.chunk.content.encode("utf-8")).hexdigest()
            if fingerprint in seen_content:  # duplicate uploads / orphaned points
                continue
            seen_content.add(fingerprint)
            vector_score = float(result.score)
            if min_score is not None and vector_score < min_score:
                continue
            keyword = lexical_score(query, f"{result.chunk.metadata.get('section') or ''} {result.chunk.content}") if hybrid else 0.0
            payload.append(
                {
                    "content": result.chunk.content,
                    "score": round(VECTOR_WEIGHT * vector_score + LEXICAL_WEIGHT * keyword, 4) if hybrid else vector_score,
                    "vector_score": round(vector_score, 4),
                    "keyword_score": round(keyword, 4),
                    "metadata": result.chunk.metadata,
                }
            )
        payload.sort(key=lambda item: item["score"], reverse=True)
        payload = payload[:top_k]
        if compress:
            return compress_context(query, payload)
        return payload

    def list_document_chunks(self, document_id: str, *, limit: int = 500) -> List[Dict[str, Any]]:
        chunks = self.vector_store.list_document_chunks(document_id, limit=limit)
        return [{"id": chunk.id, "content": chunk.content, "metadata": chunk.metadata} for chunk in chunks]

    # ------------------------------------------------------------ stats
    def index_info(self) -> Dict[str, Any]:
        info = self.vector_store.info()
        info["embeddings"] = embeddings.embeddings_info()
        return info


rag_service = RAGService()

__all__ = ["RAGService", "rag_service", "lexical_score"]
