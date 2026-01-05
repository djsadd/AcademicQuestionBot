"""Vector store abstraction backed by Qdrant."""
from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import (
    ResponseHandlingException,
    UnexpectedResponse,
)

from .embeddings import VECTOR_SIZE
from .types import DocumentChunk

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    chunk: DocumentChunk
    score: float


class VectorStoreUnavailableError(RuntimeError):
    """Raised when Qdrant is unreachable and fallback is disabled."""


class _InMemoryVectorStore:
    """Minimal in-memory fallback used when Qdrant is unavailable."""

    def __init__(self) -> None:
        self._points: Dict[str, tuple[DocumentChunk, List[float]]] = {}

    def add(self, chunk: DocumentChunk, embedding: Sequence[float]) -> None:
        self._points[chunk.id] = (chunk, list(embedding))

    def search(
        self, query_embedding: Sequence[float], *, top_k: int = 3
    ) -> List[VectorSearchResult]:
        if not self._points:
            return []
        normalized_query = list(query_embedding)
        query_norm = _vector_norm(normalized_query)
        if not query_norm:
            return []
        scores: List[VectorSearchResult] = []
        for chunk, vector in self._points.values():
            score = _cosine_similarity(vector, normalized_query, query_norm)
            scores.append(VectorSearchResult(chunk=chunk, score=score))
        scores.sort(key=lambda item: item.score, reverse=True)
        return scores[:top_k]

    def delete_document(self, document_id: str) -> None:
        if not document_id:
            return
        to_remove = [
            chunk_id
            for chunk_id, (chunk, _) in self._points.items()
            if chunk.metadata.get("document_id") == document_id
        ]
        for chunk_id in to_remove:
            self._points.pop(chunk_id, None)


def _vector_norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _cosine_similarity(
    a_vector: Sequence[float],
    b_vector: Sequence[float],
    b_norm: float,
) -> float:
    a_norm = _vector_norm(a_vector)
    if not a_norm or not b_norm:
        return 0.0
    dot = sum(x * y for x, y in zip(a_vector, b_vector))
    return dot / (a_norm * b_norm)


class VectorStore:
    """Stores embeddings using Qdrant."""

    def __init__(
        self,
        *,
        url: str = "http://localhost:6333",
        collection_name: str = "academic_documents",
    ) -> None:
        self.collection_name = collection_name
        self.client = QdrantClient(url=url)
        self.retry_base_delay = float(os.getenv("QDRANT_RETRY_DELAY", "0.2"))
        self.retry_max_delay = float(os.getenv("QDRANT_RETRY_MAX_DELAY", "2.0"))
        self.operation_retry_attempts = int(os.getenv("QDRANT_RETRY_ATTEMPTS", "15"))
        allow_fallback = os.getenv("QDRANT_FALLBACK_ENABLED", "false").lower() in {
            "1",
            "true",
            "yes",
        }
        self._fallback_allowed = allow_fallback
        self._use_fallback = False
        self._fallback_store: _InMemoryVectorStore | None = None
        self._collection_ready = False
        # Don't block backend startup if Qdrant is still booting — retry lazily later.
        self._ensure_collection(
            raise_on_failure=False,
            max_attempts=1,
            allow_fallback=False,
        )

    def _ensure_collection(
        self,
        *,
        raise_on_failure: bool = True,
        max_attempts: int | None = None,
        allow_fallback: bool = True,
    ) -> None:
        """Ensure the collection exists without accidentally dropping data."""
        if self._collection_ready and not self._use_fallback:
            return
        attempts = max(1, max_attempts or self.operation_retry_attempts)
        if self._use_fallback:
            # When operating on the fallback store we still probe Qdrant, but
            # keep retries short to avoid adding noticeable latency.
            attempts = min(attempts, 2)
        delay_seconds = max(0.05, self.retry_base_delay)
        for attempt in range(attempts):
            try:
                self.client.get_collection(self.collection_name)
                self._mark_primary_ready()
                return
            except UnexpectedResponse as exc:
                status = getattr(exc, "status_code", None)
                # Qdrant returns 404 if the collection has never been created.
                if status == 404:
                    self._create_collection()
                    self._mark_primary_ready()
                    return
            except ResponseHandlingException:
                pass
            except Exception:
                # Covers connection errors while Qdrant container is still booting.
                pass
            if attempt < attempts - 1:
                time.sleep(delay_seconds)
                delay_seconds = min(delay_seconds * 1.5, self.retry_max_delay)
        if self._use_fallback and allow_fallback:
            # We are already serving requests via the fallback store; keep using it.
            self._collection_ready = True
            return
        if self._fallback_allowed and allow_fallback:
            self._switch_to_fallback(attempts)
            return
        if raise_on_failure:
            raise VectorStoreUnavailableError(
                f"Unable to verify Qdrant collection '{self.collection_name}'. "
                "Ensure the qdrant service is reachable or adjust "
                "QDRANT_RETRY_ATTEMPTS/QDRANT_RETRY_DELAY."
            )

    def _create_collection(self) -> None:
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(
                size=VECTOR_SIZE,
                distance=qmodels.Distance.COSINE,
            ),
        )

    def add(self, chunk: DocumentChunk, embedding: Sequence[float]) -> None:
        self._ensure_collection(max_attempts=self.operation_retry_attempts)
        if self._use_fallback and self._fallback_store:
            self._fallback_store.add(chunk, embedding)
            return
        payload = {
            "content": chunk.content,
            "metadata": chunk.metadata,
        }
        point = qmodels.PointStruct(id=chunk.id, vector=embedding, payload=payload)
        self.client.upsert(collection_name=self.collection_name, points=[point])

    def search(
        self,
        query_embedding: Sequence[float],
        *,
        top_k: int = 3,
    ) -> List[VectorSearchResult]:
        """Return the most relevant chunks."""
        self._ensure_collection(max_attempts=self.operation_retry_attempts)
        if self._use_fallback and self._fallback_store:
            return self._fallback_store.search(query_embedding, top_k=top_k)
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
        )

        formatted_results: List[VectorSearchResult] = []
        for result in results:
            payload = result.payload or {}
            metadata = payload.get("metadata") or {}
            chunk = DocumentChunk(
                id=str(result.id),
                content=payload.get("content", ""),
                metadata=metadata,
            )
            formatted_results.append(
                VectorSearchResult(chunk=chunk, score=result.score or 0.0)
            )
        return formatted_results

    def delete_document(self, document_id: str) -> None:
        """Delete all vectors associated with a specific document."""
        if not document_id:
            return
        self._ensure_collection(max_attempts=self.operation_retry_attempts)
        if self._use_fallback and self._fallback_store:
            self._fallback_store.delete_document(document_id)
            return
        condition = qmodels.FieldCondition(
            key="metadata.document_id",
            match=qmodels.MatchValue(value=document_id),
        )
        filter_selector = qmodels.FilterSelector(
            filter=qmodels.Filter(must=[condition])
        )
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=filter_selector,
        )

    def _mark_primary_ready(self) -> None:
        if self._use_fallback:
            logger.info("Qdrant connection restored; using primary vector store.")
        self._use_fallback = False
        self._collection_ready = True

    def _switch_to_fallback(self, attempts: int) -> None:
        if not self._use_fallback:
            logger.warning(
                "Qdrant unavailable after %s attempts. "
                "Falling back to in-memory vector store.",
                attempts,
            )
        self._use_fallback = True
        if not self._fallback_store:
            self._fallback_store = _InMemoryVectorStore()
        self._collection_ready = True
