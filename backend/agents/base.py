"""Abstract building blocks for concrete agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class AgentResult(Dict[str, Any]):
    """Typed dict substitute for quick prototyping."""


class BaseAgent(ABC):
    """Defines the envelope every agent adheres to."""

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        """Execute the agent's core logic."""

    async def format_response(self, result: AgentResult) -> AgentResult:
        """Hook for post-processing responses before returning upstream."""
        return result
