"""Admission and enrollment agent stub."""
from typing import Any, Dict

from .base import AgentResult, BaseAgent


class AdmissionAgent(BaseAgent):
    """Answers about enrollment rules and admission requirements."""

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        program = payload.get("program", "выбранная программа")
        return AgentResult(answer=f"Информация по поступлению на {program}")
