"""Platonus API wrappers using stored token/session."""
from __future__ import annotations

import re
from typing import Any

import requests

from .platonus_calendar import parse_calendar_html
from .platonus_session import token_manager


def fetch_student_academic_calendar(person_id: str, lang: str = "ru") -> dict:
    snapshot = token_manager.snapshot()
    token = snapshot.get("token")
    if not token:
        return {"status": "missing_token"}

    headers = {
        "accept": "application/json",
        "accept-language": lang,
        "token": token,
        "sid": snapshot.get("sid", ""),
        "cookie": snapshot.get("cookie", ""),
        "user-agent": snapshot.get("user_agent", ""),
    }
    url = (
        f"https://platonus.tau-edu.kz/rest/academicCalendar/studentCard/{person_id}/{lang}"
    )
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"status": "error", "detail": str(exc)}

    try:
        payload: Any = response.json()
    except ValueError:
        return {"status": "invalid_json", "raw": response.text}

    if not isinstance(payload, dict):
        return {"status": "unexpected_payload", "data": payload}

    view_link = str(payload.get("view_link", "")).strip()
    match = re.search(r"/calendar/edit/(\d+)", view_link)
    if not match:
        payload["status"] = "missing_calendar_id"
        return payload

    calendar_id = match.group(1)
    calendar_url = (
        f"https://platonus.tau-edu.kz/calendarview?calendarID={calendar_id}&print=1"
    )
    try:
        calendar_response = requests.get(calendar_url, headers=headers, timeout=30)
        calendar_response.raise_for_status()
        payload["calendar_id"] = calendar_id
        payload["calendar_html"] = calendar_response.text
        payload["calendar_data"] = parse_calendar_html(calendar_response.text)
        payload["status"] = "ok"
    except requests.RequestException as exc:
        payload["calendar_id"] = calendar_id
        payload["calendar_error"] = str(exc)
        payload["status"] = "calendar_error"
    return payload
