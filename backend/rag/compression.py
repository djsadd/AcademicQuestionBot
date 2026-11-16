"""Contextual compression helpers for RAG results.

Each retrieved chunk is reduced to the spans that actually answer the query.
Chunks are compressed concurrently (previously sequentially — N chunks meant
N back-to-back LLM round-trips on the request's critical path).
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from ..core.config import get_settings
from ..langchain.llm import llm_client

DEFAULT_MAX_CHARS = int(os.getenv("RAG_COMPRESSION_MAX_CHARS", "1800"))
DEFAULT_MAX_TOKENS = int(os.getenv("RAG_COMPRESSION_MAX_TOKENS", "180"))
MIN_CHARS_TO_COMPRESS = 400  # short chunks are cheaper to pass through verbatim

SYSTEM_PROMPT = (
    "You are a retrieval compressor. Extract only the minimal text spans that "
    "directly answer the query. Keep the original language and wording. "
    "If the passage is not relevant, return exactly: NOT_RELEVANT. "
    "Do not add new information."
)

_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=get_settings().rag_compression_workers,
            thread_name_prefix="rag-compress",
        )
    return _executor


def compress_context(
    query: str,
    context: List[Dict[str, Any]],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> List[Dict[str, Any]]:
    """Compress retrieved chunks down to query-relevant spans (in parallel)."""
    if not context or not llm_client.is_configured or not get_settings().rag_compression_enabled:
        return context

    items = [item for item in context if str(item.get("content") or "").strip()]

    def _work(item: Dict[str, Any]) -> Dict[str, Any] | None:
        content = str(item.get("content") or "")
        if len(content) < MIN_CHARS_TO_COMPRESS:
            return item
        compressed_text = _compress_text(query, content[:max_chars], max_tokens=max_tokens)
        if compressed_text is None:  # LLM failure: keep the original chunk
            return item
        if not compressed_text:  # judged irrelevant
            return None
        metadata = dict(item.get("metadata") or {})
        metadata.setdefault("compressed", True)
        metadata.setdefault("compression_method", "llm")
        metadata.setdefault("compression_original_length", len(content))
        return {**item, "content": compressed_text, "metadata": metadata}

    results = list(_get_executor().map(_work, items))
    compressed = [item for item in results if item]
    return compressed or context


def _compress_text(query: str, passage: str, *, max_tokens: int) -> str | None:
    prompt = (
        f"Query:\n{query}\n\n"
        f"Passage:\n{passage}\n\n"
        "Return only the exact, minimal spans that answer the query."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    response = llm_client.chat(
        messages,
        temperature=0.0,
        max_tokens=max_tokens,
        model=get_settings().fast_model,
    )
    if not response and llm_client.last_error:
        return None
    return _normalize_response(response)


def _normalize_response(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    lowered = cleaned.lower().strip(".")
    if lowered in {"not_relevant", "not relevant", "irrelevant", "n/a", "none"}:
        return ""
    return cleaned
