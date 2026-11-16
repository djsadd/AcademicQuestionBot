"""Multi-agent pipeline with concurrent execution and event streaming.

Flow::

    intent ─► plan ─► retrieval (once, shared) ─► agents (concurrently)
           ─► synthesis (streamed LLM) ─► validator ─► done

``stream()`` yields JSON-serialisable events consumed by the SSE endpoint:

* ``{"type": "stage", "stage": ..., "status": "running|done|error", ...}`` –
  progress the UI can display ("Ищу в документах…").
* ``{"type": "delta", "delta": "..."}`` – answer tokens.
* ``{"type": "done", "result": {...}}`` – the full response (same shape the
  non-streaming endpoint returns).

``run()`` drains the stream and returns only the final result, so the web,
streaming and Telegram transports share exactly one implementation.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Optional

from fastapi.concurrency import run_in_threadpool

from ..agents.admission import detect_question_language
from ..agents.base import BaseAgent
from ..agents.intent import IntentRouterAgent
from ..agents.validator import ValidatorAgent
from ..core.config import get_settings
from ..langchain.llm import llm_client
from ..rag.service import rag_service
from .aggregator import AggregationArtifacts, ResponseAggregator
from .graph import AgentPlanStep, OrchestratorGraph

logger = logging.getLogger(__name__)

Event = Dict[str, Any]
STREAM_CHUNK = 160


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


async def iterate_in_thread(factory: Callable[[], Iterator[str]]) -> AsyncIterator[str]:
    """Consume a blocking iterator in a worker thread without one hop per token."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Any] = asyncio.Queue()
    sentinel = object()
    cancelled = threading.Event()

    def _worker() -> None:
        try:
            for item in factory():
                if cancelled.is_set():
                    break
                loop.call_soon_threadsafe(queue.put_nowait, item)
        except Exception as exc:  # pragma: no cover - surfaced to the consumer
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    worker = loop.run_in_executor(None, _worker)
    try:
        while True:
            item = await queue.get()
            if item is sentinel:
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        cancelled.set()
        await asyncio.shield(worker)


class AgentPipeline:
    def __init__(
        self,
        *,
        intent_agent: IntentRouterAgent,
        registry: Dict[str, BaseAgent],
        graph: OrchestratorGraph,
        aggregator: ResponseAggregator,
        validator: ValidatorAgent,
    ) -> None:
        self.intent_agent = intent_agent
        self.registry = registry
        self.graph = graph
        self.aggregator = aggregator
        self.validator = validator

    # ------------------------------------------------------------------ API
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        async for event in self.stream(payload):
            if event["type"] == "done":
                result = event["result"]
        return result

    async def stream(self, payload: Dict[str, Any]) -> AsyncIterator[Event]:
        settings = get_settings()
        started_total = time.perf_counter()
        timings: Dict[str, float] = {}
        payload = dict(payload)
        payload["language"] = detect_question_language(str(payload.get("message") or ""), fallback=payload.get("language"))

        # 1. Intent ----------------------------------------------------------
        yield self._stage("intent", "running")
        started = time.perf_counter()
        try:
            intents = await self.intent_agent.run(payload)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Intent agent failed")
            intents = {"intents": ["general"], "priority": "medium", "source": "error"}
        timings["intent"] = _ms(started)
        yield self._stage("intent", "done", detail={"intents": intents.get("intents", [])}, duration_ms=timings["intent"])

        # 2. Plan ------------------------------------------------------------
        plan_steps = self.graph.plan(intents)
        agent_steps = [step for step in plan_steps if step.key != "validator"]
        full_plan = [AgentPlanStep("intent", self.graph.describe("intent")), *plan_steps]
        shared: Dict[str, Any] = {**payload, "intents": intents.get("intents", [])}
        trace: List[Dict[str, Any]] = [self._trace("intent", self.intent_agent.name, intents, timings["intent"])]
        yield {"type": "plan", "plan": [{"agent": s.key, "description": s.description} for s in full_plan]}

        # 3. Shared retrieval -------------------------------------------------
        if any(getattr(self.registry.get(step.key), "uses_rag", False) for step in agent_steps):
            yield self._stage("retrieval", "running")
            started = time.perf_counter()
            documents = await run_in_threadpool(
                rag_service.search,
                str(payload.get("message") or ""),
                top_k=settings.rag_top_k,
                compress=True,
                min_score=settings.rag_min_score,
            )
            timings["retrieval"] = _ms(started)
            shared["retrieved_context"] = documents
            yield self._stage("retrieval", "done", detail={"documents": len(documents)}, duration_ms=timings["retrieval"])

        # 4. Agents (concurrently) ---------------------------------------------
        results: Dict[str, Dict[str, Any]] = {}
        durations: Dict[str, int] = {}
        for step in agent_steps:
            yield self._stage(step.key, "running", label=step.description)

        async def _run(step: AgentPlanStep) -> tuple[str, Dict[str, Any], int]:
            agent = self.registry.get(step.key)
            t0 = time.perf_counter()
            if agent is None:
                return step.key, {"error": "agent is not registered"}, 0
            try:
                output = await asyncio.wait_for(agent.run(dict(shared)), timeout=settings.agent_timeout_seconds)
                return step.key, dict(output or {}), _ms(t0)
            except asyncio.TimeoutError:
                logger.warning("Agent %s timed out", step.key)
                return step.key, {"error": "timeout"}, _ms(t0)
            except Exception as exc:
                logger.exception("Agent %s failed", step.key)
                return step.key, {"error": str(exc)}, _ms(t0)

        for task in asyncio.as_completed([_run(step) for step in agent_steps]):
            key, output, duration = await task
            results[key] = output
            durations[key] = duration
            status = "error" if output.get("error") else "done"
            yield self._stage(key, status, label=self.graph.describe(key), duration_ms=duration)

        for step in agent_steps:  # keep trace in plan order for analytics
            agent = self.registry.get(step.key)
            trace.append(self._trace(step.key, getattr(agent, "name", "unregistered"), results.get(step.key, {}), durations.get(step.key, 0), step.description))
        timings["agents"] = max(durations.values(), default=0)

        primary = agent_steps[0].key if agent_steps else None
        artifacts = self.aggregator.collect_artifacts(trace, primary_agent=primary)

        # 5. Synthesis -----------------------------------------------------------
        llm_used, llm_error = False, None
        streamed: List[str] = []
        started = time.perf_counter()
        if artifacts.direct_response:
            final_answer = artifacts.direct_response
            async for event in self._emit_text(final_answer):
                yield event
        elif self.aggregator.should_synthesize(artifacts):
            yield self._stage("synthesis", "running")
            messages = self.aggregator.build_messages(user_payload=shared, intents=intents, artifacts=artifacts)
            error_box: Dict[str, Optional[str]] = {"error": None}

            def _factory() -> Iterator[str]:
                iterator = llm_client.chat_stream(messages)
                yield from iterator
                error_box["error"] = llm_client.last_error

            async for token in iterate_in_thread(_factory):
                streamed.append(token)
                yield {"type": "delta", "delta": token}
            final_answer = "".join(streamed).strip()
            llm_used = bool(final_answer)
            llm_error = error_box["error"]
            if not final_answer:
                final_answer = self.aggregator.fallback_answer(artifacts.answers)
                async for event in self._emit_text(final_answer):
                    yield event
            timings["synthesis"] = _ms(started)
            yield self._stage("synthesis", "done" if llm_used else "error", duration_ms=timings["synthesis"])
        else:
            final_answer = self.aggregator.fallback_answer(artifacts.answers)
            async for event in self._emit_text(final_answer):
                yield event

        # 6. Validation -----------------------------------------------------------
        started = time.perf_counter()
        validation = self.validator.validate(
            answer=final_answer,
            evidence=artifacts.evidence,
            has_context=bool(artifacts.context or artifacts.citations),
            synthesized=llm_used,
            language=str(payload.get("language") or "ru"),
        )
        final_answer = validation.pop("final_answer")
        timings["validator"] = _ms(started)
        trace.append(self._trace("validator", self.validator.name, validation, timings["validator"], self.graph.describe("validator")))
        artifacts.validator = validation
        yield self._stage("validator", "done", detail={"issues": validation["issues"]}, duration_ms=timings["validator"])

        timings["total"] = _ms(started_total)
        result = self.aggregator.build_response(
            user_payload=shared,
            intents=intents,
            plan=full_plan,
            trace=trace,
            artifacts=artifacts,
            final_answer=final_answer,
            llm_used=llm_used,
            llm_error=llm_error,
            timings=timings,
        )
        logger.info(
            "pipeline intents=%s agents=%s llm=%s issues=%s total=%sms",
            intents.get("intents"),
            [s.key for s in agent_steps],
            llm_used,
            validation["issues"],
            timings["total"],
        )
        yield {"type": "done", "result": result}

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _stage(stage: str, status: str, *, label: str | None = None, detail: Dict[str, Any] | None = None, duration_ms: int | None = None) -> Event:
        event: Event = {"type": "stage", "stage": stage, "status": status}
        if label:
            event["label"] = label
        if detail:
            event["detail"] = detail
        if duration_ms is not None:
            event["duration_ms"] = duration_ms
        return event

    @staticmethod
    def _trace(key: str, name: str, output: Dict[str, Any], duration_ms: float, description: str | None = None) -> Dict[str, Any]:
        return {
            "key": key,
            "name": name,
            "description": description or key,
            "output": output,
            "duration_ms": duration_ms,
            "status": "error" if isinstance(output, dict) and output.get("error") else "ok",
        }

    @staticmethod
    async def _emit_text(text: str) -> AsyncIterator[Event]:
        for idx in range(0, len(text), STREAM_CHUNK):
            yield {"type": "delta", "delta": text[idx : idx + STREAM_CHUNK]}
            await asyncio.sleep(0)


__all__ = ["AgentPipeline", "AggregationArtifacts", "iterate_in_thread"]
