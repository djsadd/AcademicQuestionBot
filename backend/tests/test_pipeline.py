from __future__ import annotations

import asyncio
import time
import unittest
from typing import Any, Dict

from backend.agents.base import AgentResult, BaseAgent
from backend.agents.intent import IntentRouterAgent
from backend.agents.validator import ValidatorAgent
from backend.orchestrator.aggregator import ResponseAggregator
from backend.orchestrator.graph import OrchestratorGraph
from backend.orchestrator.pipeline import AgentPipeline


class FixedIntent(IntentRouterAgent):
    def __init__(self, intents: list[str]) -> None:
        super().__init__(name="intent")
        self._intents = intents

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        return AgentResult(intents=self._intents, priority="medium")


class SleepyAgent(BaseAgent):
    def __init__(self, name: str, *, delay: float = 0.0, answer: str = "", direct: bool = False, fail: bool = False) -> None:
        super().__init__(name=name)
        self.delay, self.answer, self.direct, self.fail = delay, answer, direct, fail
        self.calls = 0

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        self.calls += 1
        await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("boom")
        return AgentResult(answer=self.answer or f"{self.name} answer", direct_response=self.direct)


def build_pipeline(intents: list[str], registry: Dict[str, BaseAgent]) -> AgentPipeline:
    return AgentPipeline(
        intent_agent=FixedIntent(intents),
        registry=registry,
        graph=OrchestratorGraph(),
        aggregator=ResponseAggregator(),
        validator=ValidatorAgent(name="validator"),
    )


async def collect(pipeline: AgentPipeline, message: str = "вопрос") -> list[dict]:
    return [event async for event in pipeline.stream({"message": message})]


class GraphTests(unittest.TestCase):
    def test_multi_intent_plan_is_deduplicated_and_ends_with_validator(self) -> None:
        plan = OrchestratorGraph().plan({"intents": ["gpa", "study"]})
        self.assertEqual([step.key for step in plan], ["policy", "tutor", "validator"])

    def test_unknown_intent_uses_default_agent(self) -> None:
        plan = OrchestratorGraph().plan({"intents": ["weather"]})
        self.assertEqual([step.key for step in plan], ["policy", "validator"])


class PipelineTests(unittest.TestCase):
    def test_independent_agents_run_concurrently(self) -> None:
        registry = {
            "policy": SleepyAgent("policy", delay=0.3),
            "tutor": SleepyAgent("tutor", delay=0.3),
        }
        pipeline = build_pipeline(["gpa"], registry)
        started = time.perf_counter()
        result = asyncio.run(pipeline.run({"message": "Как поднять GPA?"}))
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 0.55, "agents should not run sequentially")
        self.assertIn("policy answer", result["final_answer"])
        self.assertIn("tutor answer", result["final_answer"])
        self.assertEqual([item["key"] for item in result["trace"]], ["intent", "policy", "tutor", "validator"])

    def test_direct_response_of_primary_agent_is_returned_verbatim(self) -> None:
        registry = {"admission": SleepyAgent("admission", answer="<p>Готовый ответ</p>", direct=True)}
        result = asyncio.run(build_pipeline(["admission"], registry).run({"message": "поступление"}))
        self.assertEqual(result["final_answer"], "<p>Готовый ответ</p>")
        self.assertFalse(result["llm"]["used"])

    def test_failing_agent_does_not_break_the_request(self) -> None:
        registry = {
            "policy": SleepyAgent("policy", fail=True),
            "tutor": SleepyAgent("tutor"),
        }
        result = asyncio.run(build_pipeline(["gpa"], registry).run({"message": "GPA"}))
        statuses = {item["key"]: item["status"] for item in result["trace"]}
        self.assertEqual(statuses["policy"], "error")
        self.assertIn("tutor answer", result["final_answer"])

    def test_stream_emits_progress_deltas_and_done(self) -> None:
        registry = {"policy": SleepyAgent("policy", answer="Ответ " * 60)}
        events = asyncio.run(collect(build_pipeline(["documents"], registry)))
        kinds = [event["type"] for event in events]
        self.assertEqual(kinds[0], "stage")
        self.assertIn("plan", kinds)
        self.assertGreater(kinds.count("delta"), 1)
        self.assertEqual(kinds[-1], "done")
        streamed = "".join(event["delta"] for event in events if event["type"] == "delta")
        self.assertEqual(streamed.strip(), events[-1]["result"]["final_answer"].strip())
        stages = [(e["stage"], e["status"]) for e in events if e["type"] == "stage"]
        self.assertIn(("validator", "done"), stages)


class IntentRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = IntentRouterAgent(name="intent")

    def detect(self, text: str) -> str | None:
        return self.agent._detect_intent_by_keywords(text, payload={})

    def test_word_student_is_not_routed_to_admission(self) -> None:
        # "студент" / "документ" contain the substring "ент" (ЕНТ exam).
        self.assertNotEqual(self.detect("Я студент второго курса, где взять документ?"), "admission")

    def test_ent_exam_is_admission(self) -> None:
        self.assertEqual(self.detect("Нужен ли ЕНТ для поступления?"), "admission")

    def test_password_reset_rule(self) -> None:
        self.assertEqual(self.detect("Забыл пароль от Platonus"), "password_reset")

    def test_llm_payload_parsing_is_strict(self) -> None:
        self.assertEqual(self.agent._parse_intents({"intents": ["gpa", "hack", "study", "calendar"]}), ["gpa", "study"])
        self.assertEqual(self.agent._parse_intents({"intents": ["general", "gpa"]}), ["gpa"])
        self.assertEqual(self.agent._parse_intents(None), ["general"])


class ProgramInflectionTests(unittest.TestCase):
    def test_inflected_program_names_are_recognised(self) -> None:
        from backend.langchain.tools.admission_info import extract_program

        self.assertEqual(extract_program("Сколько стоит обучение на Психологии?"), "Психология")
        self.assertEqual(extract_program("Как поступить на юриспруденцию?"), "Юриспруденция")
        self.assertIsNone(extract_program("Я студент, где взять справку?"))


if __name__ == "__main__":
    unittest.main()
