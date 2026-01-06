"""Academic tutor agent."""
from typing import Any, Dict, List

from ..rag.service import rag_service
from .base import AgentResult, BaseAgent


class AcademicTutorAgent(BaseAgent):
    """Provides study help using RAG context."""

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        query = payload.get("message") or payload.get("topic") or "учебный вопрос"
        related_context = rag_service.search(query, top_k=3, compress=True)
        context_text = _format_context(related_context)
        answer = (
            f"Рекомендации по теме «{query}».\n\n"
            f"Контекст:\n{context_text or 'Контекст пока недоступен.'}"
        )
        return AgentResult(answer=answer, context=related_context)


def _format_context(context: List[Dict[str, Any]]) -> str:
    lines = []
    for item in context:
        source = item["metadata"].get("file_name")
        lines.append(f"- {source}: {item['content'][:400]}")
    return "\n".join(lines)
