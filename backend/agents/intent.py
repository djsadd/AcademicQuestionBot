"""Intent Router Agent."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .base import AgentResult, BaseAgent


class IntentRouterAgent(BaseAgent):
    """Classifies incoming messages into intents."""

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.intent_keywords: Dict[str, Tuple[str, ...]] = {
            "gpa": ("gpa", "average", "успеваемость", "средний бал"),
            "study": ("study", "exam", "учеб", "подготовка", "курс"),
            "policy": ("policy", "rule", "правил", "регламент", "академ"),
            "documents": ("document", "справк", "документ", "паспорт"),
            "admission": ("admission", "enroll", "поступл"),
            "deadline": ("deadline", "дедлайн", "срок", "крайний срок"),
        }

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        text = (payload.get("message") or "").lower()
        intents: List[str] = []
        for intent, keywords in self.intent_keywords.items():
            if any(keyword in text for keyword in keywords):
                intents.append(intent)
        if not intents and text:
            intents.append("general")
        priority = "high" if "deadline" in intents else "medium"
        return AgentResult(intents=intents or ["general"], priority=priority)
