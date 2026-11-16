"""Execution planner: maps detected intents to the agents that should run.

The plan is a flat list of independent agent steps — the pipeline executes them
concurrently — followed by the validator, which always runs last on the
synthesized answer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence


@dataclass
class AgentPlanStep:
    """Represents a single agent execution in the plan."""

    key: str
    description: str


INTENT_TO_AGENTS: Dict[str, Sequence[str]] = {
    "gpa": ("policy", "tutor"),
    "study": ("tutor",),
    "documents": ("policy",),
    "admission": ("admission",),
    "deadline": ("dean",),
    "password_reset": ("dean",),
    "calendar": ("dean",),
    "general": ("policy",),
}

AGENT_DESCRIPTIONS: Dict[str, str] = {
    "intent": "Intent Router Agent",
    "retrieval": "RAG Retrieval",
    "tutor": "Academic Tutor Agent",
    "policy": "Academic Policy Agent",
    "admission": "Admission Agent",
    "dean": "Dean Calendar Agent",
    "synthesis": "Answer Synthesizer",
    "validator": "Validator Agent",
}


class OrchestratorGraph:
    """Builds an execution plan based on detected intents."""

    def __init__(self) -> None:
        self.intent_to_agents = dict(INTENT_TO_AGENTS)
        self.agent_descriptions = dict(AGENT_DESCRIPTIONS)
        self.default_agents: Sequence[str] = ("policy",)

    def plan(self, context: Dict[str, List[str]]) -> List[AgentPlanStep]:
        """Return the ordered, de-duplicated agent steps for the given intents."""
        intents = context.get("intents") or ["general"]
        agent_keys: List[str] = []
        for intent in intents:
            for key in self.intent_to_agents.get(intent, self.default_agents):
                if key not in agent_keys:
                    agent_keys.append(key)
        agent_keys.append("validator")
        return [AgentPlanStep(key=key, description=self.describe(key)) for key in agent_keys]

    def describe(self, key: str) -> str:
        return self.agent_descriptions.get(key, key)
