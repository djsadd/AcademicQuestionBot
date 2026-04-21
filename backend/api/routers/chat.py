"""Chat endpoints for orchestrating academic conversations."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ...db import chat_analytics
from ...langchain.llm import llm_client
from ...langchain.tools.admission_info import (
    build_minimal_admission_overview,
    build_context_entries,
    detect_requested_tool,
    extract_level,
    extract_program,
    extract_programs,
    format_admission_tool_result,
    get_academic_cooperation,
    get_admission_contacts,
    get_available_programs,
    get_current_prices,
    get_management,
    get_passing_scores,
    get_required_documents,
    get_scholarships,
    get_study_durations,
    load_admission_data,
    normalize_language,
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
    uuid: str | None = None
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


def _compact_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            compacted = _compact_metadata(item)
            if compacted is None:
                continue
            if isinstance(compacted, (dict, list)) and not compacted:
                continue
            result[str(key)] = compacted
        return result
    if isinstance(value, list):
        result_list = []
        for item in value:
            compacted = _compact_metadata(item)
            if compacted is None:
                continue
            if isinstance(compacted, (dict, list)) and not compacted:
                continue
            result_list.append(compacted)
        return result_list
    if value is None:
        return None
    return value


def _build_analytics_metadata(
    *,
    payload: ChatPayload,
    channel: str,
    endpoint: str,
    chat_mode: str,
    auth_mode: str,
    user: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str | None]:
    metadata = dict(payload.metadata or {})
    session_id_raw = metadata.get("session_id") or metadata.get("session") or payload.uuid
    session_id = str(session_id_raw).strip() if session_id_raw else None

    request_meta = metadata.get("request")
    if not isinstance(request_meta, dict):
        request_meta = {}
    request_meta.update(
        {
            "source": request_meta.get("source") or "academiq-question-web",
            "origin": request_meta.get("origin") or "website",
            "endpoint": endpoint,
            "transport": "sse" if endpoint.endswith("/stream") else "http",
            "chat_mode": chat_mode,
            "auth_mode": auth_mode,
            "is_authenticated": auth_mode == "authenticated",
        }
    )

    metadata["session_id"] = session_id
    metadata["channel"] = channel
    metadata["request"] = request_meta

    context_snapshot = metadata.get("context_snapshot")
    if not isinstance(context_snapshot, dict):
        context_snapshot = {}
    context_snapshot.update(payload.context or {})
    if context_snapshot:
        metadata["context_snapshot"] = context_snapshot

    user_meta = metadata.get("user")
    if not isinstance(user_meta, dict):
        user_meta = {}

    if user:
        user_meta.update(
            {
                "kind": "authenticated",
                "telegram_id": user.get("telegram_id"),
                "person_id": payload.person_id or user.get("platonus_person_id"),
                "role": user.get("platonus_role"),
                "platonus_auth": user.get("platonus_auth"),
                "fullname": user.get("platonus_fullname"),
                "status_name": user.get("platonus_status_name"),
                "email": user.get("platonus_email"),
            }
        )
    else:
        user_meta.setdefault("kind", "anonymous")

    metadata["user"] = user_meta
    return _compact_metadata(metadata) or {}, session_id


def _build_request_log_payload(
    *,
    payload: ChatPayload,
    router_payload: dict[str, Any],
    metadata: dict[str, Any],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "message": payload.message,
        "uuid": payload.uuid,
        "language": payload.language,
        "context": payload.context or {},
        "history": router_payload.get("history") or [],
        "metadata": metadata,
        "telegram_id": router_payload.get("telegram_id"),
        "user_id": router_payload.get("user_id"),
        "person_id": router_payload.get("person_id"),
        "user": user or None,
    }


def _redact_public_request_payload(request_payload: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(request_payload.get("metadata") or {})
    user_meta = dict(metadata.get("user") or {})
    if user_meta:
        user_meta = {
            "kind": user_meta.get("kind"),
        }
        metadata["user"] = user_meta

    history = request_payload.get("history") or []
    history_size = len(history) if isinstance(history, list) else 0

    return {
        "message": request_payload.get("message"),
        "language": request_payload.get("language"),
        "uuid": request_payload.get("uuid"),
        "history_size": history_size,
        "metadata": metadata,
    }


def _print_public_request(endpoint: str, request_payload: dict[str, Any]) -> None:
    safe_payload = _redact_public_request_payload(request_payload)
    try:
        print(
            f"[public-request] {endpoint} :: "
            f"{json.dumps(safe_payload, ensure_ascii=False, default=str)}",
            flush=True,
        )
    except Exception:
        print(f"[public-request] {endpoint} :: {safe_payload}", flush=True)


def _synthesize_public_admission_answer(
    *,
    payload: ChatPayload,
    tool_result: dict[str, Any],
    fallback_answer: str,
    history: list[dict[str, Any]] | None = None,
) -> tuple[str, dict[str, Any]]:
    language = normalize_language(payload.language)
    context_entries = build_context_entries(tool_result, language=language)
    if not llm_client.is_configured:
        return fallback_answer, {"used": False, "model": None, "error": None, "raw_request": None}

    prompt = agent_router.aggregator._render_prompt(
        user_payload={
            **payload.model_dump(),
            "history": history or payload.history or [],
        },
        intents={"intents": ["admission"]},
        answers=[fallback_answer],
        context=context_entries,
        citations=[],
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    llm_answer = llm_client.chat(messages)
    if llm_answer:
        return llm_answer, {
            "used": True,
            "model": getattr(llm_client, "model", None),
            "error": getattr(llm_client, "last_error", None),
            "raw_request": None,
        }
    return fallback_answer, {
        "used": False,
        "model": getattr(llm_client, "model", None),
        "error": getattr(llm_client, "last_error", None),
        "raw_request": {
            "intents": ["admission"],
            "plan": ["admission"],
        },
    }


def _build_public_admission_response(
    *,
    payload: ChatPayload,
    history: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], str]:
    query = payload.message.strip()
    language = normalize_language(payload.language)
    data = load_admission_data()
    level = extract_level(query)
    program = extract_program(query, data=data)
    programs = extract_programs(query, data=data)
    requested_tool = detect_requested_tool(query)

    if requested_tool == "programs":
        tool_result = get_available_programs(level=level, language=language)
    elif requested_tool == "prices":
        tool_result = get_current_prices(program=program, level=level, language=language)
    elif requested_tool == "passing_scores":
        tool_result = get_passing_scores(program=program, level=level, language=language)
    elif requested_tool == "documents":
        tool_result = get_required_documents(level=level, language=language)
    elif requested_tool == "contacts":
        tool_result = get_admission_contacts(language=language)
    elif requested_tool == "durations":
        tool_result = get_study_durations(program=program, level=level, language=language)
    elif requested_tool == "academic_cooperation":
        tool_result = get_academic_cooperation(program=program, query=query, language=language)
    elif requested_tool == "scholarships":
        tool_result = get_scholarships(language=language)
    elif requested_tool == "management":
        tool_result = get_management(language=language)
    else:
        requested_programs = [item for item in programs if item]
        if program and program not in requested_programs:
            requested_programs.insert(0, program)
        tool_result = build_minimal_admission_overview(
            programs=requested_programs,
            level=level,
            language=language,
        )

    fallback_answer = format_admission_tool_result(tool_result, language=language)
    return tool_result, fallback_answer


def _assemble_public_admission_response(
    *,
    payload: ChatPayload,
    tool_result: dict[str, Any],
    final_answer: str,
    llm_info: dict[str, Any],
) -> dict[str, Any]:
    return {
        "query": payload.message.strip(),
        "language": payload.language,
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
        "context": build_context_entries(tool_result, language=normalize_language(payload.language)),
        "llm": llm_info,
        "final_answer": final_answer,
        "tool_data": tool_result,
    }


def _run_public_admission_chat(
    payload: ChatPayload,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    tool_result, fallback_answer = _build_public_admission_response(
        payload=payload,
        history=history,
    )
    final_answer, llm_info = _synthesize_public_admission_answer(
        payload=payload,
        tool_result=tool_result,
        fallback_answer=fallback_answer,
        history=history,
    )
    return _assemble_public_admission_response(
        payload=payload,
        tool_result=tool_result,
        final_answer=final_answer,
        llm_info=llm_info,
    )


def _save_public_admission_analytics(
    *,
    response: dict[str, Any],
    metadata: dict[str, Any],
    session_id: str | None,
    channel: str | None,
    request_payload: dict[str, Any] | None = None,
) -> None:
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
            request_payload=request_payload,
            response_payload=response,
        )
    except Exception as exc:
        logger.exception("Public admission analytics failed: %s", exc)


def _prepare_public_router_payload(
    payload: ChatPayload,
    *,
    endpoint: str,
) -> tuple[dict[str, Any], dict[str, Any], str | None, str]:
    metadata, session_id = _build_analytics_metadata(
        payload=payload,
        channel=str((payload.metadata or {}).get("channel") or "public_web"),
        endpoint=endpoint,
        chat_mode="public_admission",
        auth_mode="anonymous",
        user=None,
    )
    channel = str(metadata.get("channel") or "public_web")
    stored_history: list[dict[str, Any]] = []
    if session_id:
        stored_history = chat_analytics.fetch_public_session_history(session_id)

    router_payload = payload.model_dump()
    router_payload["history"] = _merge_history(payload.history, stored_history)
    if router_payload.get("metadata") is None:
        router_payload["metadata"] = metadata
    else:
        router_payload["metadata"] = metadata
    return router_payload, metadata, session_id, channel


@router.post("/")
async def handle_chat(payload: ChatPayload, user: dict = Depends(require_user)) -> dict:
    telegram_id = user["telegram_id"]
    person_id = payload.person_id or user.get("platonus_person_id")
    metadata, session_id = _build_analytics_metadata(
        payload=payload,
        channel=str((payload.metadata or {}).get("channel") or "web"),
        endpoint="/chat/",
        chat_mode="private",
        auth_mode="authenticated",
        user=user,
    )
    channel = str(metadata.get("channel") or "web")

    router_payload = payload.model_dump()
    router_payload["telegram_id"] = telegram_id
    router_payload["user_id"] = telegram_id
    if person_id:
        router_payload["person_id"] = person_id
    router_payload["metadata"] = metadata
    stored_history: list[dict[str, Any]] = []
    if session_id:
        stored_history = chat_analytics.fetch_session_history(session_id)
    router_payload["history"] = _merge_history(payload.history, stored_history)

    response = await agent_router.route(router_payload)
    request_payload = _build_request_log_payload(
        payload=payload,
        router_payload=router_payload,
        metadata=metadata,
        user=user,
    )

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
            request_payload=request_payload,
            response_payload=response,
        )
    except Exception as exc:
        logger.exception("Chat analytics failed: %s", exc)

    return {"result": response}


@router.post("/public/admission")
async def handle_public_admission_chat(payload: ChatPayload) -> dict:
    router_payload, metadata, session_id, channel = _prepare_public_router_payload(
        payload,
        endpoint="/chat/public/admission",
    )
    public_payload = payload.model_copy(update={"history": router_payload.get("history") or []})
    response = _run_public_admission_chat(public_payload, history=router_payload.get("history"))
    request_payload = _build_request_log_payload(
        payload=payload,
        router_payload=router_payload,
        metadata=metadata,
    )
    _print_public_request("/chat/public/admission", request_payload)
    _save_public_admission_analytics(
        response=response,
        metadata=metadata,
        session_id=session_id,
        channel=channel,
        request_payload=request_payload,
    )
    return {"result": response}

@router.post("/public/admission/stream")
async def handle_public_admission_chat_stream(payload: ChatPayload) -> StreamingResponse:
    router_payload, metadata, session_id, channel = _prepare_public_router_payload(
        payload,
        endpoint="/chat/public/admission/stream",
    )
    request_payload = _build_request_log_payload(
        payload=payload,
        router_payload=router_payload,
        metadata=metadata,
    )
    _print_public_request("/chat/public/admission/stream", request_payload)

    async def event_stream():
        final_answer_parts: list[str] = []
        try:
            public_payload = payload.model_copy(update={"history": router_payload.get("history") or []})
            response = _run_public_admission_chat(
                public_payload,
                history=router_payload.get("history"),
            )
            final_answer = str(response.get("final_answer") or "")
            for idx in range(0, len(final_answer), 140):
                chunk = final_answer[idx: idx + 140]
                if not chunk:
                    continue
                final_answer_parts.append(chunk)
                yield _sse("delta", {"delta": chunk})
                await asyncio.sleep(0)

            _save_public_admission_analytics(
                response=response,
                metadata=metadata,
                session_id=session_id,
                channel=channel,
                request_payload=request_payload,
            )
            yield _sse("done", {"result": response})
        except Exception as exc:
            logger.exception("Public admission streaming failed: %s", exc)
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


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def handle_chat_stream(payload: ChatPayload, user: dict = Depends(require_user)) -> StreamingResponse:
    telegram_id = user["telegram_id"]
    person_id = payload.person_id or user.get("platonus_person_id")
    metadata, session_id = _build_analytics_metadata(
        payload=payload,
        channel=str((payload.metadata or {}).get("channel") or "web"),
        endpoint="/chat/stream",
        chat_mode="private",
        auth_mode="authenticated",
        user=user,
    )
    channel = str(metadata.get("channel") or "web")

    router_payload = payload.model_dump()
    router_payload["telegram_id"] = telegram_id
    router_payload["user_id"] = telegram_id
    if person_id:
        router_payload["person_id"] = person_id
    router_payload["metadata"] = metadata
    stored_history: list[dict[str, Any]] = []
    if session_id:
        stored_history = chat_analytics.fetch_session_history(session_id)
    router_payload["history"] = _merge_history(payload.history, stored_history)
    request_payload = _build_request_log_payload(
        payload=payload,
        router_payload=router_payload,
        metadata=metadata,
        user=user,
    )

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
                    request_payload=request_payload,
                    response_payload=response_obj,
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


@router.get("/public/history/{session_id}")
async def get_public_chat_history(session_id: str) -> dict:
    normalized_session_id = session_id.strip()
    if not normalized_session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    session = chat_analytics.fetch_public_chat_session(normalized_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Public chat session not found")

    return {"session": session}
