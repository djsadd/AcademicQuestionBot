"""Agent router: wires concrete agents into the shared pipeline.

Kept as a thin façade so existing callers (HTTP API, Telegram bot) keep using
``AgentRouter().route(payload)``; streaming callers use ``stream(payload)``.
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Dict

from ..agents.admission import AdmissionAgent
from ..agents.dean import DeanCalendarAgent
from ..agents.intent import IntentRouterAgent
from ..agents.policy import AcademicPolicyAgent
from ..agents.tutor import AcademicTutorAgent
from ..agents.validator import ValidatorAgent
from .aggregator import ResponseAggregator
from .graph import AgentPlanStep, OrchestratorGraph
from .pipeline import AgentPipeline


class AgentRouter:
    """Coordinates the multi-agent flow."""

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
        }
        self.intent_step = AgentPlanStep(key="intent", description="Intent Router Agent")
        self.pipeline = AgentPipeline(
            intent_agent=self.intent_agent,
            registry=self.agent_registry,
            graph=self.graph,
            aggregator=self.aggregator,
            validator=self.validator_agent,
        )

    async def route(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.pipeline.run(payload)

    def stream(self, payload: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        return self.pipeline.stream(payload)
