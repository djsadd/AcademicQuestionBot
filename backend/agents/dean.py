"""Dean agent for academic calendar responses."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..langchain.tools.academic_calendar import get_academic_calendar
from ..langchain.tools.password_reset import reset_password
from .base import AgentResult, BaseAgent

logger = logging.getLogger(__name__)


class DeanCalendarAgent(BaseAgent):
    """Returns academic calendar details for dean workflows."""

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        intents = payload.get("intents") or []
        if "password_reset" in intents:
            login = str(
                payload.get("login")
                or payload.get("username")
                or payload.get("user_id")
                or "unknown"
            )
            reset_data = reset_password(login)
            answer = _format_password_reset(reset_data)
            return AgentResult(answer=answer, intent="password_reset", tool_data=reset_data)

        telegram_id = payload.get("telegram_id") or payload.get("user_id")
        logger.info("DeanCalendarAgent calendar request for telegram_id=%s", telegram_id)
        calendar = get_academic_calendar(telegram_id)
        logger.info("DeanCalendarAgent calendar status=%s", calendar.get("status"))
        answer = _format_calendar(calendar)
        context = _build_calendar_context(calendar, answer)
        return AgentResult(
            answer=answer,
            intent="calendar",
            tool_data=calendar,
            context=context,
        )


def _format_calendar(calendar: Dict[str, Any]) -> str:
    status = calendar.get("status")
    if status != "ok":
        return (
            "Failed to get academic calendar.\n"
            f"Status: {status or 'unknown'}"
        )

    calendar_data = calendar.get("calendar") or {}
    title = calendar_data.get("title") or "Academic calendar"
    sections = calendar_data.get("sections") or []

    lines = [title]
    for section in sections:
        section_title = section.get("title") or "Section"
        lines.append(f"\n{section_title}")
        for item in section.get("items") or []:
            name = item.get("name") or "-"
            period = item.get("period") or "-"
            lines.append(f"{name}\t{period}")
    return "\n".join(lines)


def _build_calendar_context(
    calendar: Dict[str, Any],
    formatted_answer: str,
) -> List[Dict[str, Any]]:
    status = calendar.get("status")
    if status != "ok":
        detail = calendar.get("detail") or calendar
        detail_text = str(detail)
        if len(detail_text) > 400:
            detail_text = f"{detail_text[:400]}..."
        content = (
            f"Academic calendar fetch failed. Status: {status or 'unknown'}. "
            f"Detail: {detail_text}"
        )
        return [{"content": content, "metadata": {"source_path": "platonus_calendar"}}]

    return [{"content": formatted_answer, "metadata": {"source_path": "platonus_calendar"}}]


def _format_password_reset(reset_data: Dict[str, str]) -> str:
    return (
        "Password reset request received.\n"
        f"Login: {reset_data.get('login')}\n"
        f"Request ID: {reset_data.get('request_id')}\n"
        f"Temporary password: {reset_data.get('temporary_password')}\n"
        f"Expires in minutes: {reset_data.get('expires_in_minutes')}\n"
        f"Note: {reset_data.get('note')}"
    )
