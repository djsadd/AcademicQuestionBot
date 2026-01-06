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
            "password_reset": (
                "password reset",
                "reset password",
                "password",
                "\u0441\u0431\u0440\u043e\u0441",
                "\u043f\u0430\u0440\u043e\u043b\u044c",
            ),
            "calendar": (
                "calendar",
                "academic calendar",
                "kalendar",
                "\u043a\u0430\u043b\u0435\u043d\u0434\u0430\u0440",
                "\u0430\u043a\u0430\u0434\u0435\u043c\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u043a\u0430\u043b\u0435\u043d\u0434\u0430\u0440\u044c",
                "\u0434\u0435\u043a\u0430\u043d",
                "\u0434\u0435\u043a\u0430\u043d\u0430\u0442",
            ),
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













