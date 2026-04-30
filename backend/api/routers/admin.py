"""Admin endpoints for operational tasks."""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError

from ...db import admission_applications, chat_analytics, telegram_users
from ...services.admission_admin import (
    get_data_path,
    list_admission_programs_for_admin,
    load_admission_info_for_admin,
    save_admission_info_for_admin,
)
from ...services.platonus_client import (
    fetch_platonus_session_status,
    fetch_student_academic_calendar,
)
from ...services.permissions import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class UserRoleUpdatePayload(BaseModel):
    role: str | None = None


@router.get("/health")
async def healthcheck() -> dict:
    """Simple readiness check used by Docker/K8s probes."""
    return {"status": "ok"}


@router.get("/platonus/session")
async def platonus_session_status() -> dict:
    return fetch_platonus_session_status()


@router.get("/platonus/student-academic-calendar/{person_id}")
async def platonus_student_academic_calendar(person_id: str, lang: str = "ru") -> Any:
    return fetch_student_academic_calendar(person_id, lang)


@router.get("/admission-applications")
async def get_admission_applications(page: int = 1, per_page: int = 20) -> dict[str, Any]:
    return admission_applications.list_applications(page=page, per_page=per_page)


@router.get("/admission-info")
async def get_admission_info() -> dict[str, Any]:
    try:
        payload = load_admission_info_for_admin()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Admission data file not found: {get_data_path()}") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Admission data JSON is invalid: {exc}") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=exc.errors(include_url=False)) from exc
    return {"status": "ok", "source_path": str(get_data_path()), "data": payload}


@router.get("/admission-programs")
async def get_admission_programs(
    search: str = "",
    level: str = "all",
    page: int = 1,
    per_page: int = 10,
) -> dict[str, Any]:
    try:
        payload = list_admission_programs_for_admin(
            search=search,
            level=level,
            page=page,
            per_page=per_page,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Admission data file not found: {get_data_path()}") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Admission data JSON is invalid: {exc}") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=exc.errors(include_url=False)) from exc
    return {"status": "ok", **payload}


@router.put("/admission-info")
async def update_admission_info(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        saved = save_admission_info_for_admin(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "source_path": str(get_data_path()), "data": saved}


@router.get("/chat-analytics/summary")
async def get_chat_analytics_summary() -> dict[str, Any]:
    return chat_analytics.fetch_admin_summary()


@router.get("/chat-analytics/sessions")
async def get_chat_analytics_sessions(
    page: int = 1,
    per_page: int = 20,
    auth_mode: str = "all",
    search: str = "",
) -> dict[str, Any]:
    return chat_analytics.list_chat_sessions(
        page=page,
        per_page=per_page,
        auth_mode=auth_mode,
        search=search,
    )


@router.get("/chat-analytics/users")
async def get_chat_analytics_users(limit: int = 100) -> dict[str, Any]:
    return chat_analytics.list_chat_users(limit=limit)


@router.get("/chat-analytics/admission-contacts")
async def get_chat_analytics_admission_contacts(limit: int = 100) -> dict[str, Any]:
    return chat_analytics.list_admission_contacts(limit=limit)


@router.get("/users")
async def get_users(limit: int = 100) -> dict[str, Any]:
    return {"items": telegram_users.list_users(limit=limit), "limit": max(1, min(limit, 500))}


@router.put("/users/{telegram_id}/role")
async def update_user_role(telegram_id: int, payload: UserRoleUpdatePayload) -> dict[str, Any]:
    user = telegram_users.update_user_role(telegram_id, payload.role)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"status": "ok", "user": user}


@router.get("/chat-analytics/sessions/{session_key}")
async def get_chat_analytics_session_events(session_key: str) -> dict[str, Any]:
    return chat_analytics.get_session_events(session_key)


@router.get("/agents/overview")
async def get_agents_overview(days: int = 30) -> dict[str, Any]:
    return chat_analytics.fetch_agent_overview(days=days)
