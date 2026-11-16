"""Dean agent for academic calendar responses."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi.concurrency import run_in_threadpool

from ..langchain.tools.academic_calendar import get_academic_calendar
from ..langchain.tools.password_reset import reset_password
from .base import AgentResult, BaseAgent

logger = logging.getLogger(__name__)


class DeanCalendarAgent(BaseAgent):
    """Returns academic calendar details for dean workflows."""

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        intents = payload.get("intents") or []
        telegram_id = payload.get("telegram_id") or payload.get("user_id")
        # Password help must work for users who cannot log in.
        if "password_reset" in intents:
            reset_data = reset_password(str(payload.get("person_id") or telegram_id or ""))
            return AgentResult(
                answer=reset_data["message"],
                intent="password_reset",
                tool_data={key: value for key, value in reset_data.items() if key != "message"},
                direct_response=True,
            )

        if not telegram_id:
            answer = (
                "Для этого запроса нужен авторизованный доступ. "
                "Войдите через Telegram, чтобы получить персональный календарь, "
                "статусы и другие данные из внутренних систем."
            )
            return AgentResult(
                answer=answer,
                intent="calendar",
                tool_data={"status": "auth_required"},
                context=[{"content": answer, "metadata": {"source_path": "auth_guard"}}],
                direct_response=True,
            )

        logger.info("DeanCalendarAgent calendar request for telegram_id=%s", telegram_id)
        calendar = await run_in_threadpool(get_academic_calendar, telegram_id)
        logger.info("DeanCalendarAgent calendar status=%s", calendar.get("status"))
        answer = _format_calendar(calendar)
        context = _build_calendar_context(calendar, answer)
        return AgentResult(
            answer=answer,
            intent="calendar",
            tool_data=calendar,
            context=context,
        )


CALENDAR_STATUS_MESSAGES = {
    "missing_person_id": "К вашему профилю не привязана учётная запись Platonus, поэтому персональный календарь недоступен. Войдите через логин и пароль Platonus.",
    "user_not_found": "Профиль не найден. Пожалуйста, войдите в систему заново.",
    "missing_telegram_id": "Для просмотра календаря нужно войти в систему.",
    "platonus_api_error": "Platonus сейчас не отвечает. Попробуйте позже или уточните даты в деканате.",
}


def _format_calendar(calendar: Dict[str, Any]) -> str:
    status = calendar.get("status")
    if status != "ok":
        return CALENDAR_STATUS_MESSAGES.get(
            str(status),
            "Не удалось получить академический календарь из Platonus. Попробуйте позже или обратитесь в деканат.",
        )

    calendar_data = calendar.get("calendar") or {}
    title = calendar_data.get("title") or "Академический календарь"
    sections = calendar_data.get("sections") or []

    lines = [title]
    for section in sections:
        section_title = section.get("title") or "Раздел"
        lines.append(f"\n{section_title}")
        for item in section.get("items") or []:
            name = item.get("name") or "-"
            period = item.get("period") or "-"
            lines.append(f"- {name}: {period}")
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

