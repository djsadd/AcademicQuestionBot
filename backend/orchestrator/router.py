"""Agent router that wires requests through the orchestrator graph."""
from typing import Any, Dict, List

from ..agents.admission import AdmissionAgent
from ..agents.dean import DeanCalendarAgent
from ..agents.intent import IntentRouterAgent
from ..agents.policy import AcademicPolicyAgent
from ..agents.tutor import AcademicTutorAgent
from ..agents.validator import ValidatorAgent
from .aggregator import ResponseAggregator
from .graph import AgentPlanStep, OrchestratorGraph


class AgentRouter:
    """Coordinates the multi-agent flow defined in README."""

    def __init__(self) -> None:
        self.intent_agent = IntentRouterAgent(name="intent-router")
        self.tutor_agent = AcademicTutorAgent(name="academic-tutor")
        self.policy_agent = AcademicPolicyAgent(name="academic-policy")
        self.admission_agent = AdmissionAgent(name="admission-agent")
        self.dean_agent = DeanCalendarAgent(name="dean-calendar")
        self.validator_agent = ValidatorAgent(name="validator")
        self.graph = OrchestratorGraph()
        self.aggregator = ResponseAggregator()
        self.agent_registry = {
            "tutor": self.tutor_agent,
            "policy": self.policy_agent,
            "admission": self.admission_agent,
            "dean": self.dean_agent,
            "validator": self.validator_agent,
        }
        self.intent_step = AgentPlanStep(
            key="intent", description="Intent Router Agent"
        )

    async def route(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        intents = await self.intent_agent.run(payload)
        plan_steps = self.graph.plan(intents)
        full_plan: List[AgentPlanStep] = [self.intent_step, *plan_steps]
        shared_context: Dict[str, Any] = {
            **payload,
            "intents": intents.get("intents", []),
        }
        execution_trace: List[Dict[str, Any]] = [
            {
                "key": "intent",
                "name": self.intent_agent.name,
                "description": self.intent_step.description,
                "output": intents,
            }
        ]

        for step in plan_steps:
            agent = self.agent_registry.get(step.key)
            if not agent:
                execution_trace.append(
                    {
                        "key": step.key,
                        "name": "unregistered",
                        "description": step.description,
                        "output": {"error": "agent is not registered"},
                    }
                )
                continue

            agent_payload = {
                **shared_context,
                "agent_history": execution_trace,
            }
            result = await agent.run(agent_payload)
            shared_context.update(result)
            execution_trace.append(
                {
                    "key": step.key,
                    "name": agent.name,
                    "description": step.description,
                    "output": result,
                }
            )

        return self.aggregator.aggregate(
            user_payload=payload,
            intents=intents,
            plan=full_plan,
            trace=execution_trace,
        )
