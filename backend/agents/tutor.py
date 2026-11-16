"""Academic tutor agent: study help grounded in the RAG knowledge base."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi.concurrency import run_in_threadpool

from ..core.config import get_settings
from ..rag.service import rag_service
from .base import AgentResult, BaseAgent, citations_from_context, shared_context


class AcademicTutorAgent(BaseAgent):
    """Collects study-related evidence; the synthesizer turns it into an explanation."""

    uses_rag = True

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        query = str(payload.get("message") or payload.get("topic") or "").strip()
        context = shared_context(payload)
        if context is None:
            settings = get_settings()
            context = await run_in_threadpool(
                rag_service.search,
                query,
                top_k=3,
                compress=True,
                min_score=settings.rag_min_score,
            )
        context = context[:3]
        return AgentResult(
            answer=_format_evidence(query, context),
            context=context,
            citations=citations_from_context(context, limit=3),
            intent="study",
        )


def _format_evidence(query: str, context: List[Dict[str, Any]]) -> str:
    if not context:
        return ""
    lines = [f"Учебные материалы по теме «{query}»:"]
    for item in context:
        source = (item.get("metadata") or {}).get("file_name") or "Документ"
        snippet = " ".join(str(item.get("content") or "").split())
        lines.append(f"- {source}: {snippet[:400]}")
    return "\n".join(lines)
