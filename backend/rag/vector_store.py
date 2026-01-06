"""Vector store implementations backed by Qdrant with an in-memory fallback."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import UnexpectedResponse

from . import embeddings
from .types import DocumentChunk

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    chunk: DocumentChunk
    score: float


class InMemoryVectorStore:
    """Simple in-memory vector store used as a fallback."""

    def __init__(self, vector_size: int) -> None:
        self._vector_size = vector_size
        self._items: List[tuple[DocumentChunk, List[float]]] = []

    def add(self, chunk: DocumentChunk, vector: List[float]) -> None:
        normalized = _normalize(_coerce_vector(vector, self._vector_size))
        self._items.append((chunk, normalized))

    def search(self, vector: List[float], *, top_k: int = 3) -> List[VectorSearchResult]:
        if not self._items:
            return []
        query_vector = _normalize(_coerce_vector(vector, self._vector_size))
        results = [
            VectorSearchResult(chunk=item[0], score=_dot(query_vector, item[1]))
            for item in self._items
        ]
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]

    def delete_document(self, document_id: str) -> None:
        self._items = [
            (chunk, vector)
            for chunk, vector in self._items
            if chunk.metadata.get("document_id") != document_id
        ]

    def list_document_chunks(
        self,
        document_id: str,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> List[DocumentChunk]:
        if limit <= 0:
            return []
        filtered = [
            chunk
            for chunk, _ in self._items
            if chunk.metadata.get("document_id") == document_id
        ]
        filtered.sort(key=_chunk_sort_key)
        return filtered[offset : offset + limit]


class VectorStore:
    """Vector store that prefers Qdrant with an optional in-memory fallback."""

    def __init__(self, *, url: str, collection_name: str) -> None:
        self._collection_name = collection_name
        self._url = url
        self._vector_size = embeddings.VECTOR_SIZE
        self._api_key = os.getenv("QDRANT_API_KEY") or None
        self._strict = _parse_bool(os.getenv("QDRANT_STRICT", "false"), default=False)
        self._fallback_enabled = _parse_bool(
            os.getenv("QDRANT_FALLBACK_ENABLED", "true"), default=True
        )
        if self._strict:
            self._fallback_enabled = False
        self._retry_attempts = int(os.getenv("QDRANT_RETRY_ATTEMPTS", "5"))
        self._retry_delay = float(os.getenv("QDRANT_RETRY_DELAY", "0.2"))
        self._retry_max_delay = float(os.getenv("QDRANT_RETRY_MAX_DELAY", "2.0"))

        self._client: Optional[QdrantClient] = None
        self._fallback_store = (
            InMemoryVectorStore(self._vector_size) if self._fallback_enabled else None
        )

        self._init_qdrant()

    def add(self, chunk: DocumentChunk, vector: List[float]) -> None:
        payload = {"content": chunk.content, **chunk.metadata}
        vector_payload = _coerce_vector(vector, self._vector_size)

        if self._client is None:
            self._init_qdrant()
        if self._client is None and self._strict:
            raise RuntimeError("Qdrant is unavailable; strict mode enabled.")
        if self._client:
            try:
                point = qdrant_models.PointStruct(
                    id=chunk.id,
                    vector=vector_payload,
                    payload=payload,
                )
                self._with_retry(
                    lambda: self._client.upsert(
                        collection_name=self._collection_name,
                        points=[point],
                    )
                )
                return
            except Exception:
                if self._try_reconnect():
                    return self.add(chunk, vector_payload)
                if not self._fallback_enabled:
                    raise
        if self._fallback_store:
            self._fallback_store.add(chunk, vector_payload)

    def search(self, vector: List[float], *, top_k: int = 3) -> List[VectorSearchResult]:
        vector_payload = _coerce_vector(vector, self._vector_size)
        if self._client is None:
            self._init_qdrant()
        if self._client is None and self._strict:
            raise RuntimeError("Qdrant is unavailable; strict mode enabled.")
        if self._client:
            try:
                hits = self._with_retry(
                    lambda: self._client.search(
                        collection_name=self._collection_name,
                        query_vector=vector_payload,
                        limit=top_k,
                        with_payload=True,
                    )
                )
                return [_to_search_result(hit) for hit in hits]
            except Exception:
                if self._try_reconnect():
                    return self.search(vector_payload, top_k=top_k)
                if not self._fallback_enabled:
                    raise
        if self._fallback_store:
            return self._fallback_store.search(vector_payload, top_k=top_k)
        return []

    def delete_document(self, document_id: str) -> None:
        if self._client is None:
            self._init_qdrant()
        if self._client is None and self._strict:
            raise RuntimeError("Qdrant is unavailable; strict mode enabled.")
        if self._client:
            try:
                filter_payload = qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="document_id",
                            match=qdrant_models.MatchValue(value=document_id),
                        )
                    ]
                )
                self._with_retry(
                    lambda: self._client.delete(
                        collection_name=self._collection_name,
                        points_selector=filter_payload,
                    )
                )
            except Exception:
                if self._try_reconnect():
                    return self.delete_document(document_id)
                if not self._fallback_enabled:
                    raise
        if self._fallback_store:
            self._fallback_store.delete_document(document_id)

    def list_document_chunks(self, document_id: str, *, limit: int = 200) -> List[DocumentChunk]:
        if limit <= 0:
            return []
        if self._client is None:
            self._init_qdrant()
        if self._client is None and self._strict:
            raise RuntimeError("Qdrant is unavailable; strict mode enabled.")
        if self._client:
            try:
                filter_payload = qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="document_id",
                            match=qdrant_models.MatchValue(value=document_id),
                        )
                    ]
                )
                collected: List[DocumentChunk] = []
                next_offset = None
                while len(collected) < limit:
                    page_limit = min(200, limit - len(collected))
                    points, next_offset = self._with_retry(
                        lambda: self._client.scroll(
                            collection_name=self._collection_name,
                            scroll_filter=filter_payload,
                            limit=page_limit,
                            with_payload=True,
                            offset=next_offset,
                        )
                    )
                    if not points:
                        break
                    collected.extend(_to_document_chunk(point) for point in points)
                    if not next_offset:
                        break
                collected.sort(key=_chunk_sort_key)
                return collected
            except Exception:
                if self._try_reconnect():
                    return self.list_document_chunks(document_id, limit=limit)
                if not self._fallback_enabled:
                    raise
        if self._fallback_store:
            return self._fallback_store.list_document_chunks(document_id, limit=limit)
        return []

    def _init_qdrant(self) -> None:
        for attempt in range(self._retry_attempts):
            try:
                client = QdrantClient(url=self._url, api_key=self._api_key)
                client.get_collections()
                self._ensure_collection(client)
                self._client = client
                logger.info(
                    "Qdrant connected: url=%s collection=%s vector_size=%s strict=%s fallback=%s",
                    self._url,
                    self._collection_name,
                    self._vector_size,
                    self._strict,
                    self._fallback_enabled,
                )
                return
            except Exception:
                if attempt == self._retry_attempts - 1:
                    if self._strict or not self._fallback_enabled:
                        raise
                    logger.warning(
                        "Qdrant unavailable; using fallback store: url=%s collection=%s",
                        self._url,
                        self._collection_name,
                    )
                    return
                time.sleep(_next_delay(self._retry_delay, self._retry_max_delay, attempt))

    def _try_reconnect(self) -> bool:
        if self._client is not None:
            self._client = None
        self._init_qdrant()
        return self._client is not None

    def _ensure_collection(self, client: QdrantClient) -> None:
        try:
            exists = client.collection_exists(collection_name=self._collection_name)
        except Exception:
            exists = False
        if exists:
            return
        try:
            client.create_collection(
                collection_name=self._collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=self._vector_size,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )
            logger.info("Qdrant collection created: %s", self._collection_name)
        except UnexpectedResponse as exc:
            if exc.status_code == 409:
                logger.info("Qdrant collection already exists: %s", self._collection_name)
                return
            raise

    def _with_retry(self, operation):
        for attempt in range(self._retry_attempts):
            try:
                return operation()
            except Exception:
                if attempt == self._retry_attempts - 1:
                    raise
                time.sleep(_next_delay(self._retry_delay, self._retry_max_delay, attempt))


def _to_search_result(hit) -> VectorSearchResult:
    payload = hit.payload or {}
    content = payload.get("content", "")
    metadata = {key: value for key, value in payload.items() if key != "content"}
    return VectorSearchResult(
        chunk=DocumentChunk(id=str(hit.id), content=content, metadata=metadata),
        score=float(getattr(hit, "score", 0.0)),
    )


def _to_document_chunk(point) -> DocumentChunk:
    payload = point.payload or {}
    content = payload.get("content", "")
    metadata = {key: value for key, value in payload.items() if key != "content"}
    return DocumentChunk(id=str(point.id), content=content, metadata=metadata)


def _chunk_sort_key(chunk: DocumentChunk) -> tuple[int, int, str]:
    index = chunk.metadata.get("chunk_index")
    offset = chunk.metadata.get("offset")
    safe_index = int(index) if isinstance(index, int) or (isinstance(index, str) and index.isdigit()) else 0
    safe_offset = int(offset) if isinstance(offset, int) or (isinstance(offset, str) and offset.isdigit()) else 0
    return safe_index, safe_offset, chunk.id


def _coerce_vector(vector: Iterable[float], size: int) -> List[float]:
    result = list(vector)
    if size <= 0:
        return result
    if len(result) < size:
        result.extend([0.0] * (size - len(result)))
    if len(result) > size:
        result = result[:size]
    return result


def _dot(left: List[float], right: List[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _normalize(vector: List[float]) -> List[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _next_delay(delay: float, max_delay: float, attempt: int) -> float:
    return min(max_delay, delay * (2**attempt))


def _parse_bool(value: str, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default
