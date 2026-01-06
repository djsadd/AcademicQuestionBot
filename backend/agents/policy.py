"""Academic policy agent."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..rag.service import rag_service
from .base import AgentResult, BaseAgent


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

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.max_guidelines = 4

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        query = payload.get("message") or payload.get("policy") or "академическая политика"
        related_context = rag_service.search(query, top_k=5, compress=True)
        guidelines = self._build_guidelines(related_context)
        citations = self._build_citations(related_context)
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
            source = item["metadata"].get("file_name", "Документ")
            snippet = item["content"].strip().replace("\n", " ")
            guidelines.append(f"{source}: {snippet[:320]}")
        return guidelines

    def _build_citations(self, context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        citations: List[Dict[str, Any]] = []
        for item in context[: self.max_guidelines]:
            metadata = item["metadata"]
            citations.append(
                {
                    "file_name": metadata.get("file_name"),
                    "source_path": metadata.get("source_path"),
                    "chunk_index": metadata.get("chunk_index"),
                }
            )
        return citations

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
