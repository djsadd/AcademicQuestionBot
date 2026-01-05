"""Validator agent stub."""
from typing import Any, Dict

from .base import AgentResult, BaseAgent


class ValidatorAgent(BaseAgent):
    """Validates responses before they go back to the user."""

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        return AgentResult(is_valid=True, issues=[])
