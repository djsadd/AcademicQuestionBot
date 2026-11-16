"""Academic policy agent."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from fastapi.concurrency import run_in_threadpool

from ..core.config import get_settings
from ..langchain.tools.admission_info import (
    build_context_entries,
    detect_requested_tool,
    format_admission_tool_result,
    get_academic_cooperation,
    normalize_language,
)
from ..rag.service import rag_service
from .base import AgentResult, BaseAgent, citations_from_context, shared_context


def validate_answer(answer: str, citations: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Validate that a policy answer is grounded in context/citations."""
    issues: List[str] = []

    if not citations:
        issues.append("missing_citations")

    speculative_markers = [
        "кажется",
        "вероятно",
        "думаю",
        "предполож",
        "возможно",
        "скорее всего",
    ]
    lowered_answer = answer.lower()
    if any(marker in lowered_answer for marker in speculative_markers):
        issues.append("speculative_language")

    mentioned_citations = [
        (cite.get("file_name") or "").lower()
        for cite in citations
        if cite.get("file_name")
    ]
    if mentioned_citations and not any(name in lowered_answer for name in mentioned_citations):
        issues.append("missing_attribution")

    return len(issues) == 0, issues


class AcademicPolicyAgent(BaseAgent):
    """Answers policy and regulation questions using RAG."""

    uses_rag = True

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.max_guidelines = 4

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        query = payload.get("message") or payload.get("policy") or "академическая политика"
        language = normalize_language(payload.get("language"))
        requested_tool = detect_requested_tool(str(query))
        if requested_tool == "academic_cooperation":
            result = get_academic_cooperation(query=str(query), language=language)
            return AgentResult(
                answer=format_admission_tool_result(result, language=language),
                context=build_context_entries(result, language=language),
                intent="policy",
                citations=[
                    {
                        "file_name": "admission_info.json",
                        "source_path": result.get("source_path"),
                        "chunk_index": 0,
                    }
                ],
                validation={"is_valid": True, "issues": []},
                tool_data=result,
            )

        related_context = shared_context(payload)
        if related_context is None:
            settings = get_settings()
            related_context = await run_in_threadpool(
                rag_service.search,
                str(query),
                top_k=settings.rag_top_k,
                compress=True,
                min_score=settings.rag_min_score,
            )
        if not related_context:
            # No evidence: return nothing so the synthesizer does not
            # receive (or echo) placeholder text.
            return AgentResult(answer="", context=[], intent="policy", citations=[], validation={"is_valid": False, "issues": ["no_context"]})
        guidelines = self._build_guidelines(related_context)
        citations = citations_from_context(related_context, limit=self.max_guidelines)
        explanation = self._compose_answer(query, guidelines, citations)
        is_valid, issues = validate_answer(explanation, citations)

        return AgentResult(
            answer=explanation,
            context=related_context,
            intent="policy",
            guidelines=guidelines,
            citations=citations,
            validation={"is_valid": is_valid, "issues": issues},
        )

    def _build_guidelines(self, context: List[Dict[str, Any]]) -> List[str]:
        guidelines: List[str] = []
        for item in context[: self.max_guidelines]:
            source = (item.get("metadata") or {}).get("file_name") or "Документ"
            snippet = " ".join(str(item.get("content") or "").split())
            guidelines.append(f"{source}: {snippet[:320]}")
        return guidelines

    def _compose_answer(
        self,
        query: str,
        guidelines: List[str],
        citations: List[Dict[str, Any]],
    ) -> str:
        bullet_points = "\n".join(f"- {point}" for point in guidelines) or "Контекст недоступен."
        policy_sources = ", ".join(filter(None, {cite.get("file_name") for cite in citations})) or "не указано"
        return (
            f"Регламент для запроса «{query}»:\n"
            f"{bullet_points}\n\n"
            f"Источники: {policy_sources}"
        )
