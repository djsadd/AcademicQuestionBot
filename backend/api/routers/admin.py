"""Admin endpoints for operational tasks."""
from typing import Any

from fastapi import APIRouter, Depends

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
