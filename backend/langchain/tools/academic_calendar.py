"""Academic calendar tool for dean workflow."""
from __future__ import annotations

from typing import Any, Dict

from ...db.telegram_users import get_user
from ...services.platonus_client import fetch_student_academic_calendar


def get_academic_calendar(telegram_id: int | None) -> Dict[str, Any]:
    if telegram_id is None:
        return {"status": "missing_telegram_id"}

    user = get_user(telegram_id)
    if not user:
        return {"status": "user_not_found"}

    person_id = user.get("platonus_person_id")
    if not person_id:
        return {"status": "missing_person_id"}

    try:
        result = fetch_student_academic_calendar(str(person_id), "ru")
    except RuntimeError as exc:
        return {"status": "platonus_api_error", "detail": str(exc)}
    if result.get("status") != "ok":
        return {"status": result.get("status", "error"), "detail": result}

    calendar_data = result.get("calendar_data")
    if not isinstance(calendar_data, dict):
        return {"status": "missing_calendar_data"}

    return {"status": "ok", "calendar": calendar_data}
