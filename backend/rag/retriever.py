"""Retriever utilities."""
from __future__ import annotations

from typing import List

from . import embeddings
from .vector_store import VectorSearchResult, VectorStore


def retrieve(
    query: str,
    store: VectorStore,
    *,
    top_k: int = 3,
) -> List[VectorSearchResult]:
    """Search the vector store for the most relevant chunks."""
    query_embedding = embeddings.embed_text(query)
    return store.search(query_embedding, top_k=top_k)
