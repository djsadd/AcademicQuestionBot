"""Admin endpoints for operational tasks."""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from ...db import admission_applications, chat_analytics
from ...services.admission_admin import (
    get_data_path,
    load_admission_info_for_admin,
    save_admission_info_for_admin,
)
from ...services.platonus_client import (
    fetch_platonus_session_status,
    fetch_student_academic_calendar,
)
from ...services.permissions import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


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


@router.get("/chat-analytics/sessions/{session_key}")
async def get_chat_analytics_session_events(session_key: str) -> dict[str, Any]:
    return chat_analytics.get_session_events(session_key)
