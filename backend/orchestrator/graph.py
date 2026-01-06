"""Workflow planner for orchestrating agents."""
from dataclasses import dataclass
from typing import Dict, List, Sequence


@dataclass
class AgentPlanStep:
    """Represents a single agent execution in the plan."""

    key: str
    description: str


class OrchestratorGraph:
    """Builds an execution plan based on detected intents."""

    def __init__(self) -> None:
        self.intent_to_agents: Dict[str, Sequence[str]] = {
            "gpa": ("policy", "tutor"),
            "study": ("tutor",),
            "documents": ("policy",),
            "admission": ("admission", "policy"),
            "deadline": ("tutor",),
            "password_reset": ("dean",),
            "calendar": ("dean",),
        }
        self.agent_descriptions: Dict[str, str] = {
            "tutor": "Academic Tutor Agent",
            "policy": "Academic Policy Agent",
            "admission": "Admission Agent",
            "dean": "Dean Calendar Agent",
            "validator": "Validator Agent",
        }
        self.default_agents: Sequence[str] = ("tutor",)

    def plan(self, context: Dict[str, List[str]]) -> List[AgentPlanStep]:
        """Return AgentPlanStep list derived from intents."""
        intents = context.get("intents") or []
        agent_keys: List[str] = []
        seen = set()

        for intent in intents or ["general"]:
            candidates = self.intent_to_agents.get(intent, self.default_agents)
            for key in candidates:
                if key not in seen:
                    agent_keys.append(key)
                    seen.add(key)

        if "validator" not in seen:
            agent_keys.append("validator")

        return [
            AgentPlanStep(key=key, description=self.agent_descriptions.get(key, key))
            for key in agent_keys
        ]
