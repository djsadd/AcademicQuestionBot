"""Chat endpoints for orchestrating academic conversations."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ...agents.admission import (
    detect_question_language,
    run_admission_pipeline,
)
from ...db import chat_analytics
from ...langchain.llm import llm_client
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
    language: str | None = None
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
    current_message: str | None = None,
    limit: int = 20,
) -> list[dict[str, str]]:
    stored_items = [
        item
        for item in (_normalize_history_item(raw_item) for raw_item in (stored_history or []))
        if item
    ]
    request_items = [
        item
        for item in (_normalize_history_item(raw_item) for raw_item in (request_history or []))
        if item
    ]

    merged: list[dict[str, str]] = []
    request_signatures = {
        (item["role"], item["content"])
        for item in request_items
    }

    for item in stored_items:
        if (item["role"], item["content"]) in request_signatures:
            continue
        merged.append(item)

    merged.extend(request_items)

    current_text = (current_message or "").strip()
    if current_text:
        merged = [
            item
            for item in merged
            if not (item.get("role") == "user" and item.get("content") == current_text)
        ]
        merged.append({"role": "user", "content": current_text})

    compacted: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in merged:
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
        compacted.append(item)

    return compacted[-limit:]


def _attach_admission_state(
    router_payload: dict[str, Any],
    session_id: str | None,
) -> None:
    context = dict(router_payload.get("context") or {})
    if session_id:
        if not isinstance(context.get("admission_state"), dict):
            state = chat_analytics.fetch_latest_admission_state(session_id)
            if state:
                context["admission_state"] = state
        if not isinstance(context.get("admission_profile"), dict):
            profile = chat_analytics.fetch_latest_admission_profile(session_id)
            if profile:
                context["admission_profile"] = profile
    router_payload["context"] = context


def _sync_admission_context_snapshot(metadata: dict[str, Any], response: dict[str, Any]) -> None:
    context_snapshot = dict(metadata.get("context_snapshot") or {})
    state = response.get("admission_state")
    if isinstance(state, dict):
        context_snapshot["admission_state"] = state
    profile = response.get("admission_profile")
    if isinstance(profile, dict):
        context_snapshot["admission_profile"] = profile
    if context_snapshot:
        metadata["context_snapshot"] = context_snapshot


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


def _assemble_public_admission_response(
    *,
    payload: ChatPayload,
    pipeline: dict[str, Any],
) -> dict[str, Any]:
    language = str(pipeline.get("language") or detect_question_language(payload.message, fallback=payload.language))
    tool_result = pipeline.get("tool_data") or {}
    context_entries = pipeline.get("context") or []
    final_answer = str(pipeline.get("answer") or "")
    return {
        "query": payload.message.strip(),
        "language": language,
        "intents": ["admission"],
        "plan": PUBLIC_ADMISSION_PLAN,
        "trace": [
            {
                "key": "admission",
                "name": "public-admission",
                "description": "Public Admission FAQ",
                "output": {
                    "intent": "admission",
                    "answer": final_answer,
                    "tool_data": tool_result,
                    "context": context_entries,
                    "classification": pipeline.get("classification"),
                    "orchestration": pipeline.get("orchestration"),
                    "admission_state": pipeline.get("admission_state"),
                    "admission_profile": pipeline.get("admission_profile"),
                },
            }
        ],
        "context": context_entries,
        "supporting_context": context_entries,
        "llm": pipeline.get("llm") or {},
        "final_answer": final_answer,
        "tool_data": tool_result,
        "classification": pipeline.get("classification"),
        "orchestration": pipeline.get("orchestration"),
        "admission_state": pipeline.get("admission_state"),
        "admission_profile": pipeline.get("admission_profile"),
    }


def _run_public_admission_chat(
    payload: ChatPayload,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    pipeline = run_admission_pipeline(
        query=payload.message.strip(),
        history=history or payload.history or [],
        language=payload.language,
        payload=payload.model_dump(),
    )
    return _assemble_public_admission_response(
        payload=payload,
        pipeline=pipeline,
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
        _sync_admission_context_snapshot(metadata, response)
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
    router_payload["history"] = _merge_history(
        payload.history,
        stored_history,
        current_message=payload.message,
    )
    _attach_admission_state(router_payload, session_id)
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
    router_payload["history"] = _merge_history(
        payload.history,
        stored_history,
        current_message=payload.message,
    )
    _attach_admission_state(router_payload, session_id)

    response = await agent_router.route(router_payload)
    request_payload = _build_request_log_payload(
        payload=payload,
        router_payload=router_payload,
        metadata=metadata,
        user=user,
    )

    try:
        _sync_admission_context_snapshot(metadata, response)
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
    public_payload = payload.model_copy(
        update={
            "history": router_payload.get("history") or [],
            "context": router_payload.get("context") or {},
        }
    )
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
            public_payload = payload.model_copy(
                update={
                    "history": router_payload.get("history") or [],
                    "context": router_payload.get("context") or {},
                }
            )
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
    router_payload["history"] = _merge_history(
        payload.history,
        stored_history,
        current_message=payload.message,
    )
    _attach_admission_state(router_payload, session_id)
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
                **agent_router.aggregator._collect_admission_metadata(execution_trace),
            }

            try:
                _sync_admission_context_snapshot(metadata, response_obj)
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
