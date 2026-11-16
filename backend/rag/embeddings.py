"""Embedding helpers.

* Documents are embedded in batches (one HTTP call per ``EMBED_BATCH_SIZE``
  chunks instead of one call per chunk), which makes ingestion an order of
  magnitude faster on large PDFs.
* Query embeddings are memoised with an LRU cache: repeated or popular
  questions skip the network round-trip entirely.
"""
from __future__ import annotations

import logging
import math
import os
import time
from functools import lru_cache
from typing import Iterable, List, Sequence

import requests

from .types import DocumentChunk

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("OPENAI_EMBEDDINGS_MODEL", "text-embedding-3-large")
MODEL_DIMENSIONS = {
    "text-embedding-ada-002": 1536,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
}
FALLBACK_VECTOR_SIZE = 64
EMBED_BATCH_SIZE = int(os.getenv("OPENAI_EMBEDDINGS_BATCH", "64"))
MAX_INPUT_CHARS = 24_000  # stay well below the 8k-token input limit

_embedding_model = DEFAULT_MODEL
_api_key = os.getenv("OPENAI_API_KEY")
_team = os.getenv("OPENAI_TEAM")
_embedding_dimension = int(
    os.getenv(
        "OPENAI_EMBEDDINGS_DIM",
        MODEL_DIMENSIONS.get(DEFAULT_MODEL, 1536),
    )
)
VECTOR_SIZE = _embedding_dimension if _api_key else FALLBACK_VECTOR_SIZE

_session = requests.Session()


def embed_documents(documents: Iterable[DocumentChunk]) -> List[List[float]]:
    """Generate embeddings for provided document chunks (batched)."""
    texts = [doc.content for doc in documents]
    return embed_texts(texts)


def embed_texts(texts: Sequence[str]) -> List[List[float]]:
    if not texts:
        return []
    if not _api_key:
        return [_local_embedding(text) for text in texts]

    vectors: List[List[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = [(text or " ")[:MAX_INPUT_CHARS] for text in texts[start : start + EMBED_BATCH_SIZE]]
        remote = _remote_embeddings(batch)
        if len(remote) != len(batch):
            logger.warning("Remote embeddings failed for batch at %s; using local fallback", start)
            remote = [_local_embedding(text) for text in batch]
        vectors.extend(remote)
    return vectors


def embed_text(text: str) -> List[float]:
    """Embed a single query (cached)."""
    return list(_cached_query_embedding((text or "").strip()))


@lru_cache(maxsize=1024)
def _cached_query_embedding(text: str) -> tuple[float, ...]:
    if _api_key:
        remote = _remote_embeddings([text or " "])
        if remote:
            return tuple(remote[0])
    return tuple(_local_embedding(text))


def _remote_embeddings(batch: List[str], *, attempts: int = 3) -> List[List[float]]:
    endpoint = os.getenv("OPENAI_EMBEDDINGS_URL", "https://api.openai.com/v1/embeddings")
    headers = {
        "Authorization": f"Bearer {_api_key}",
        "Content-Type": "application/json",
    }
    if _team:
        headers["OpenAI-Organization"] = _team
    payload = {"model": _embedding_model, "input": batch}
    for attempt in range(attempts):
        try:
            response = _session.post(endpoint, json=payload, headers=headers, timeout=60)
            if response.status_code in {429, 500, 502, 503, 504} and attempt + 1 < attempts:
                time.sleep(0.5 * (2**attempt))
                continue
            response.raise_for_status()
            data = sorted(response.json()["data"], key=lambda item: item.get("index", 0))
            return [list(item["embedding"]) for item in data]
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            if attempt + 1 < attempts:
                time.sleep(0.5 * (2**attempt))
                continue
            logger.warning("Embedding request failed: %s", exc)
    return []


def _local_embedding(text: str) -> List[float]:
    dimension = VECTOR_SIZE if _api_key else FALLBACK_VECTOR_SIZE
    vector = [0.0] * dimension
    for character in text.lower():
        index = ord(character) % len(vector)
        vector[index] += 1.0
    return _normalize(vector)


def _normalize(vector: List[float]) -> List[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
