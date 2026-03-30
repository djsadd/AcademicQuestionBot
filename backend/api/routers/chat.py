"""Chat endpoints for orchestrating academic conversations."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ...db import chat_analytics
from ...langchain.llm import llm_client
from ...langchain.tools.admission_info import (
    build_context_entries,
    detect_requested_tool,
    extract_level,
    extract_program,
    format_admission_tool_result,
    get_admission_contacts,
    get_available_programs,
    get_current_prices,
    get_passing_scores,
    get_required_documents,
    get_study_durations,
    load_admission_data,
)
from ...services.permissions import require_user

from ...orchestrator.router import AgentRouter
from ...orchestrator.aggregator import SYSTEM_PROMPT

router = APIRouter(prefix="/chat", tags=["chat"])
agent_router = AgentRouter()
logger = logging.getLogger("chat")


class ChatPayload(BaseModel):
    user_id: int | None = None
    telegram_id: int | None = None
    person_id: str | None = None
    message: str
    language: str | None = "ru"
    context: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    history: list[dict[str, Any]] | None = None


PUBLIC_ADMISSION_PLAN = [
    {"agent": "admission", "description": "Admission Agent"},
]


def _normalize_history_item(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    content = str(item.get("content") or "").strip()
    if not content:
        return None
    role = str(item.get("role") or "user").strip().lower()
    if role == "bot":
        role = "assistant"
    if role not in {"user", "assistant", "system"}:
        role = "user"
    normalized = {"role": role, "content": content}
    created_at = item.get("created_at")
    if created_at:
        normalized["created_at"] = str(created_at)
    return normalized


def _merge_history(
    request_history: list[dict[str, Any]] | None,
    stored_history: list[dict[str, Any]] | None,
    limit: int = 20,
) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for raw_item in [*(stored_history or []), *(request_history or [])]:
        item = _normalize_history_item(raw_item)
        if not item:
            continue
        signature = (
            item["role"],
            item["content"],
            item.get("created_at", ""),
        )
        if signature in seen:
            continue
        seen.add(signature)
        merged.append(item)

    return merged[-limit:]


def _build_public_admission_overview(*, program: str | None, level: str | None) -> dict[str, Any]:
    programs = get_available_programs(level=level)
    prices = get_current_prices(program=program, level=level)
    scores = get_passing_scores(program=program, level=level)
    durations = get_study_durations(program=program, level=level)
    contacts = get_admission_contacts()

    answer = "\n\n".join(
        [
            "Информация приемной комиссии:",
            format_admission_tool_result(programs),
            format_admission_tool_result(prices),
            format_admission_tool_result(scores),
            format_admission_tool_result(durations),
            format_admission_tool_result(contacts),
        ]
    )
    return {
        "status": "ok",
        "tool": "overview",
        "answer": answer,
        "source_path": prices.get("source_path") or contacts.get("source_path"),
        "data_updated_at": prices.get("data_updated_at") or contacts.get("data_updated_at"),
    }


def _run_public_admission_chat(payload: ChatPayload) -> dict[str, Any]:
    query = payload.message.strip()
    data = load_admission_data()
    level = extract_level(query)
    program = extract_program(query, data=data)
    requested_tool = detect_requested_tool(query)

    if requested_tool == "programs":
        tool_result = get_available_programs(level=level)
    elif requested_tool == "prices":
        tool_result = get_current_prices(program=program, level=level)
    elif requested_tool == "passing_scores":
        tool_result = get_passing_scores(program=program, level=level)
    elif requested_tool == "documents":
        tool_result = get_required_documents(level=level)
    elif requested_tool == "contacts":
        tool_result = get_admission_contacts()
    elif requested_tool == "durations":
        tool_result = get_study_durations(program=program, level=level)
    else:
        tool_result = _build_public_admission_overview(program=program, level=level)

    final_answer = format_admission_tool_result(tool_result)
    return {
        "query": query,
        "intents": ["admission"],
        "plan": PUBLIC_ADMISSION_PLAN,
        "trace": [
            {
                "key": "admission",
                "name": "public-admission",
                "description": "Public Admission FAQ",
                "output": {
                    "intent": "admission",
                    "tool_data": tool_result,
                },
            }
        ],
        "context": build_context_entries(tool_result),
        "llm": {"used": False, "model": None, "error": None},
        "final_answer": final_answer,
        "tool_data": tool_result,
    }


@router.post("/")
async def handle_chat(payload: ChatPayload, user: dict = Depends(require_user)) -> dict:
    telegram_id = user["telegram_id"]
    person_id = payload.person_id or user.get("platonus_person_id")

    metadata = payload.metadata or {}
    session_id = metadata.get("session_id") or metadata.get("session") or None
    channel = metadata.get("channel") or "web"

    router_payload = payload.model_dump()
    router_payload["telegram_id"] = telegram_id
    router_payload["user_id"] = telegram_id
    if person_id:
        router_payload["person_id"] = person_id
    stored_history: list[dict[str, Any]] = []
    if session_id:
        stored_history = chat_analytics.fetch_session_history(session_id)
    router_payload["history"] = _merge_history(payload.history, stored_history)

    response = await agent_router.route(router_payload)

    try:
        chat_analytics.save_chat_event(
            session_id=session_id,
            telegram_id=telegram_id,
            person_id=person_id,
            channel=str(channel) if channel is not None else None,
            query=response.get("query"),
            response=response.get("final_answer"),
            llm_model=(response.get("llm") or {}).get("model"),
            llm_used=(response.get("llm") or {}).get("used"),
            llm_error=(response.get("llm") or {}).get("error"),
            intents=response.get("intents"),
            agents=response.get("plan"),
            trace=response.get("trace"),
            metadata=metadata,
        )
    except Exception as exc:
        logger.exception("Chat analytics failed: %s", exc)

    return {"result": response}


@router.post("/public/admission")
async def handle_public_admission_chat(payload: ChatPayload) -> dict:
    response = _run_public_admission_chat(payload)
    metadata = payload.metadata or {}
    session_id = metadata.get("session_id") or metadata.get("session") or None
    channel = metadata.get("channel") or "public_web"

    try:
        chat_analytics.save_chat_event(
            session_id=session_id,
            telegram_id=None,
            person_id=None,
            channel=str(channel) if channel is not None else None,
            query=response.get("query"),
            response=response.get("final_answer"),
            llm_model=(response.get("llm") or {}).get("model"),
            llm_used=(response.get("llm") or {}).get("used"),
            llm_error=(response.get("llm") or {}).get("error"),
            intents=response.get("intents"),
            agents=response.get("plan"),
            trace=response.get("trace"),
            metadata=metadata,
        )
    except Exception as exc:
        logger.exception("Public admission analytics failed: %s", exc)

    return {"result": response}


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def handle_chat_stream(payload: ChatPayload, user: dict = Depends(require_user)) -> StreamingResponse:
    telegram_id = user["telegram_id"]
    person_id = payload.person_id or user.get("platonus_person_id")

    metadata = payload.metadata or {}
    session_id = metadata.get("session_id") or metadata.get("session") or None
    channel = metadata.get("channel") or "web"

    router_payload = payload.model_dump()
    router_payload["telegram_id"] = telegram_id
    router_payload["user_id"] = telegram_id
    if person_id:
        router_payload["person_id"] = person_id
    stored_history: list[dict[str, Any]] = []
    if session_id:
        stored_history = chat_analytics.fetch_session_history(session_id)
    router_payload["history"] = _merge_history(payload.history, stored_history)

    async def event_stream():
        final_answer_parts: list[str] = []
        response_obj: dict | None = None
        try:
            intents = await agent_router.intent_agent.run(router_payload)
            plan_steps = agent_router.graph.plan(intents)
            full_plan = [agent_router.intent_step, *plan_steps]

            shared_context: dict[str, Any] = {
                **router_payload,
                "intents": intents.get("intents", []),
            }
            execution_trace: list[dict[str, Any]] = [
                {
                    "key": "intent",
                    "name": agent_router.intent_agent.name,
                    "description": agent_router.intent_step.description,
                    "output": intents,
                }
            ]

            for step in plan_steps:
                agent = agent_router.agent_registry.get(step.key)
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
                if result.get("direct_response"):
                    break

            artifacts = agent_router.aggregator._collect_artifacts(execution_trace)
            fallback_answer = agent_router.aggregator._fallback_answer(artifacts.answers)
            llm_answer = ""

            if artifacts.direct_response:
                for idx in range(0, len(artifacts.direct_response), 140):
                    chunk = artifacts.direct_response[idx: idx + 140]
                    if not chunk:
                        continue
                    final_answer_parts.append(chunk)
                    yield _sse("delta", {"delta": chunk})
                    await asyncio.sleep(0)
            elif llm_client.is_configured and artifacts.answers:
                prompt = agent_router.aggregator._render_prompt(
                    user_payload=router_payload,
                    intents=intents,
                    answers=artifacts.answers,
                    context=artifacts.context,
                    citations=artifacts.citations,
                )
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ]
                for chunk in llm_client.chat_stream(messages):
                    final_answer_parts.append(chunk)
                    yield _sse("delta", {"delta": chunk})
                    await asyncio.sleep(0)
                llm_answer = "".join(final_answer_parts).strip()
            else:
                for idx in range(0, len(fallback_answer), 140):
                    chunk = fallback_answer[idx: idx + 140]
                    if not chunk:
                        continue
                    final_answer_parts.append(chunk)
                    yield _sse("delta", {"delta": chunk})
                    await asyncio.sleep(0)

            final_answer = llm_answer or "".join(final_answer_parts).strip() or fallback_answer
            plan_view = [{"agent": step.key, "description": step.description} for step in full_plan]
            response_obj = {
                "query": router_payload.get("message"),
                "intents": intents.get("intents", []),
                "priority": intents.get("priority"),
                "plan": plan_view,
                "trace": execution_trace,
                "final_answer": final_answer,
                "validation": artifacts.validator,
                "citations": artifacts.citations,
                "supporting_context": artifacts.context,
                "llm": {
                    "model": getattr(llm_client, "model", None),
                    "used": bool(llm_answer),
                    "error": getattr(llm_client, "last_error", None),
                    "raw_request": {
                        "intents": intents.get("intents", []),
                        "plan": [step.key for step in full_plan],
                    } if not llm_answer else None,
                },
            }

            try:
                chat_analytics.save_chat_event(
                    session_id=session_id,
                    telegram_id=telegram_id,
                    person_id=person_id,
                    channel=str(channel) if channel is not None else None,
                    query=response_obj.get("query"),
                    response=response_obj.get("final_answer"),
                    llm_model=(response_obj.get("llm") or {}).get("model"),
                    llm_used=(response_obj.get("llm") or {}).get("used"),
                    llm_error=(response_obj.get("llm") or {}).get("error"),
                    intents=response_obj.get("intents"),
                    agents=response_obj.get("plan"),
                    trace=response_obj.get("trace"),
                    metadata=metadata,
                )
            except Exception as exc:
                logger.exception("Chat analytics failed: %s", exc)

            yield _sse("done", {"result": response_obj})
        except Exception as exc:
            logger.exception("Streaming chat failed: %s", exc)
            yield _sse("error", {"error": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history")
async def get_chat_history(user: dict = Depends(require_user)) -> dict:
    history = chat_analytics.fetch_chat_history(user["telegram_id"])
    return {"sessions": history}
