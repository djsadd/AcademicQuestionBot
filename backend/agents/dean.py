"""Dean agent for academic calendar responses."""
from __future__ import annotations

from typing import Any, Dict

from ..langchain.tools.academic_calendar import get_academic_calendar
from ..langchain.tools.password_reset import reset_password
from .base import AgentResult, BaseAgent


class DeanCalendarAgent(BaseAgent):
    """Returns academic calendar details for dean workflows."""

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        message = (payload.get("message") or "").lower()
        intents = payload.get("intents") or []
        if "password_reset" in intents or _looks_like_password_reset(message):
            login = str(
                payload.get("login")
                or payload.get("username")
                or payload.get("user_id")
                or "unknown"
            )
            reset_data = reset_password(login)
            answer = _format_password_reset(reset_data)
            return AgentResult(answer=answer, intent="password_reset", tool_data=reset_data)

        calendar = get_academic_calendar()
        answer = _format_calendar(calendar)
        return AgentResult(answer=answer, intent="calendar")


def _format_calendar(calendar: Dict[str, Dict[str, str]]) -> str:
    lines = ["Академический календарь (временно):"]
    for section, items in calendar.items():
        lines.append(f"\n{section}")
        for label, value in items.items():
            lines.append(f"{label}\t{value}")
    return "\n".join(lines)


def _looks_like_password_reset(message: str) -> bool:
    keywords = (
        "reset password",
        "password reset",
        "password",
        "\u0441\u0431\u0440\u043e\u0441",
        "\u043f\u0430\u0440\u043e\u043b\u044c",
    )
    return any(keyword in message for keyword in keywords)


def _format_password_reset(reset_data: Dict[str, str]) -> str:
    return (
        "Password reset request received.\n"
        f"Login: {reset_data.get('login')}\n"
        f"Request ID: {reset_data.get('request_id')}\n"
        f"Temporary password: {reset_data.get('temporary_password')}\n"
        f"Expires in minutes: {reset_data.get('expires_in_minutes')}\n"
        f"Note: {reset_data.get('note')}"
    )
