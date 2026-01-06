"""Contextual compression helpers for RAG results."""
from __future__ import annotations

import os
from typing import Any, Dict, List

from ..langchain.llm import llm_client

DEFAULT_MAX_CHARS = int(os.getenv("RAG_COMPRESSION_MAX_CHARS", "1800"))
DEFAULT_MAX_TOKENS = int(os.getenv("RAG_COMPRESSION_MAX_TOKENS", "180"))

SYSTEM_PROMPT = (
    "You are a retrieval compressor. Extract only the minimal text spans that "
    "directly answer the query. If the passage is not relevant, return an empty string. "
    "Do not add new information."
)


def compress_context(
    query: str,
    context: List[Dict[str, Any]],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> List[Dict[str, Any]]:
    """Compress retrieved chunks down to query-relevant spans."""
    if not context or not llm_client.is_configured:
        return context

    compressed: List[Dict[str, Any]] = []
    for item in context:
        content = str(item.get("content") or "")
        if not content.strip():
            continue
        snippet = content[:max_chars]
        compressed_text = _compress_text(query, snippet, max_tokens=max_tokens)
        if not compressed_text:
            continue
        updated = dict(item)
        updated["content"] = compressed_text
        metadata = dict(updated.get("metadata") or {})
        metadata.setdefault("compressed", True)
        metadata.setdefault("compression_method", "llm")
        metadata.setdefault("compression_original_length", len(content))
        updated["metadata"] = metadata
        compressed.append(updated)

    return compressed or context


def _compress_text(query: str, passage: str, *, max_tokens: int) -> str:
    prompt = (
        "Query:\n"
        f"{query}\n\n"
        "Passage:\n"
        f"{passage}\n\n"
        "Return only the exact, minimal spans that answer the query."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    response = llm_client.chat(messages, temperature=0.0, max_tokens=max_tokens)
    cleaned = _normalize_response(response)
    return cleaned


def _normalize_response(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if lowered in {"not relevant", "irrelevant", "n/a", "none"}:
        return ""
    return cleaned
