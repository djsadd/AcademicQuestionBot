"""Embedding helpers."""
from __future__ import annotations

import math
import os
from typing import Iterable, List

import requests

from .types import DocumentChunk

DEFAULT_MODEL = os.getenv("OPENAI_EMBEDDINGS_MODEL", "text-embedding-3-large")
MODEL_DIMENSIONS = {
    "text-embedding-ada-002": 1536,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
}
FALLBACK_VECTOR_SIZE = 64

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


def embed_documents(documents: Iterable[DocumentChunk]) -> List[List[float]]:
    """Generate embeddings for provided document chunks."""
    return [embed_text(doc.content) for doc in documents]


def embed_text(text: str) -> List[float]:
    """Create embeddings using OpenAI (with deterministic fallback)."""
    if _api_key:
        remote_vector = _remote_embedding(text)
        if remote_vector:
            return remote_vector
    return _local_embedding(text)


def _remote_embedding(text: str) -> List[float]:
    endpoint = os.getenv("OPENAI_EMBEDDINGS_URL", "https://api.openai.com/v1/embeddings")
    headers = {
        "Authorization": f"Bearer {_api_key}",
        "Content-Type": "application/json",
    }
    if _team:
        headers["OpenAI-Organization"] = _team
    payload = {
        "model": _embedding_model,
        "input": text or " ",
    }
    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return list(data["data"][0]["embedding"])
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
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
