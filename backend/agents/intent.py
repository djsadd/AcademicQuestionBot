"""Intent Router Agent."""
from __future__ import annotations

from typing import Any, Dict

from ..langchain.llm import llm_client
from .base import AgentResult, BaseAgent


INTENT_PROMPT = (
    "\u0422\u044b \u043a\u043b\u0430\u0441\u0441\u0438\u0444\u0438\u043a\u0430\u0442\u043e\u0440 "
    "\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c\u0441\u043a\u0438\u0445 "
    "\u0437\u0430\u043f\u0440\u043e\u0441\u043e\u0432 \u0434\u043b\u044f "
    "\u0443\u043d\u0438\u0432\u0435\u0440\u0441\u0438\u0442\u0435\u0442\u0441\u043a\u043e\u0433\u043e "
    "\u0431\u043e\u0442\u0430.\n\n"
    "\u0412\u044b\u0431\u0435\u0440\u0438 \u041e\u0414\u0418\u041d intent \u0438\u0437 "
    "\u0441\u043f\u0438\u0441\u043a\u0430:\n\n"
    "- password_reset \u2014 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c "
    "\u043d\u0435 \u043c\u043e\u0436\u0435\u0442 \u0432\u043e\u0439\u0442\u0438, "
    "\u0437\u0430\u0431\u044b\u043b \u043f\u0430\u0440\u043e\u043b\u044c, "
    "\u0434\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u0430\u043d\n"
    "- calendar \u2014 \u0432\u043e\u043f\u0440\u043e\u0441\u044b \u043f\u0440\u043e "
    "\u0430\u043a\u0430\u0434\u0435\u043c\u0438\u0447\u0435\u0441\u043a\u0438\u0439 "
    "\u043a\u0430\u043b\u0435\u043d\u0434\u0430\u0440\u044c\n"
    "- documents \u2014 \u0441\u043f\u0440\u0430\u0432\u043a\u0438, \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u044b\n"
    "- admission \u2014 \u043f\u043e\u0441\u0442\u0443\u043f\u043b\u0435\u043d\u0438\u0435\n"
    "- study \u2014 \u0443\u0447\u0435\u0431\u043d\u044b\u0439 \u043f\u0440\u043e\u0446\u0435\u0441\u0441\n"
    "- general \u2014 \u0432\u0441\u0451 \u043e\u0441\u0442\u0430\u043b\u044c\u043d\u043e\u0435\n\n"
    "\u041f\u0440\u0438\u043c\u0435\u0440\u044b:\n"
    "\"\u042f \u043d\u0435 \u043c\u043e\u0433\u0443 \u0432\u043e\u0439\u0442\u0438 \u0432 "
    "\u0441\u0438\u0441\u0442\u0435\u043c\u0443\" \u2192 password_reset\n"
    "\"\u0421\u0430\u0439\u0442 \u043f\u0438\u0448\u0435\u0442 \u043d\u0435\u0432\u0435\u0440\u043d\u044b\u0439 "
    "\u043f\u0430\u0440\u043e\u043b\u044c\" \u2192 password_reset\n"
    "\"\u0417\u0430\u0431\u044b\u043b \u043b\u043e\u0433\u0438\u043d \u0438 "
    "\u043f\u0430\u0440\u043e\u043b\u044c\" \u2192 password_reset\n"
    "\"\u041a\u043e\u0433\u0434\u0430 \u043d\u0430\u0447\u0438\u043d\u0430\u0435\u0442\u0441\u044f "
    "\u0441\u0435\u0441\u0441\u0438\u044f?\" \u2192 calendar\n\n"
    "\u0412\u0435\u0440\u043d\u0438 \u0422\u041e\u041b\u042c\u041a\u041e "
    "\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 intent.\n\n"
    "\u0417\u0430\u043f\u0440\u043e\u0441: {query}"
)

ALLOWED_INTENTS = {
    "password_reset",
    "calendar",
    "documents",
    "admission",
    "study",
    "general",
}


class IntentRouterAgent(BaseAgent):
    """Classifies incoming messages into intents."""

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.default_intent = "general"

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        text = (payload.get("message") or "").strip()
        intent = await self._classify_intent(text)
        priority = "high" if intent in {"password_reset"} else "medium"
        return AgentResult(intents=[intent], priority=priority)

    async def _classify_intent(self, text: str) -> str:
        if not text:
            return self.default_intent
        if not llm_client.is_configured:
            return self.default_intent

        prompt = INTENT_PROMPT.format(query=text)
        messages = [{"role": "user", "content": prompt}]
        response = llm_client.chat(messages, temperature=0.0, max_tokens=10)
        intent = (response or "").strip().lower().splitlines()[0]
        if intent not in ALLOWED_INTENTS:
            return self.default_intent
        return intent
