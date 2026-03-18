"""Admission agent backed by structured admission tools."""
from __future__ import annotations

import re
from typing import Any, Dict

from ..db import admission_applications
from ..langchain.tools.admission_info import (
    build_context_entries,
    detect_requested_tool,
    extract_level,
    extract_program,
    format_admission_tool_result,
    get_admission_contacts,
    get_available_programs,
    get_current_prices,
    get_passing_scores,
    get_required_documents,
    get_study_durations,
    load_admission_data,
)
from .base import AgentResult, BaseAgent


class AdmissionAgent(BaseAgent):
    """Answers about enrollment rules and admission requirements."""

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        query = str(payload.get("message") or payload.get("question") or "").strip()
        application_result = _maybe_handle_application_flow(payload, query)
        if application_result is not None:
            return application_result

        data = load_admission_data()
        level = payload.get("level") or extract_level(query)
        program = payload.get("program") or extract_program(query, data=data)
        requested_tool = detect_requested_tool(query)

        if requested_tool == "programs":
            result = get_available_programs(level=level)
        elif requested_tool == "prices":
            result = get_current_prices(program=program, level=level)
        elif requested_tool == "passing_scores":
            result = get_passing_scores(program=program, level=level)
        elif requested_tool == "documents":
            result = get_required_documents(level=level)
        elif requested_tool == "contacts":
            result = get_admission_contacts()
        elif requested_tool == "durations":
            result = get_study_durations(program=program, level=level)
        else:
            result = _build_overview(program=program, level=level)

        return AgentResult(
            answer=format_admission_tool_result(result),
            intent="admission",
            tool_data=result,
            context=build_context_entries(result),
        )


def _build_overview(*, program: str | None, level: str | None) -> Dict[str, Any]:
    programs = get_available_programs(level=level)
    prices = get_current_prices(program=program, level=level)
    scores = get_passing_scores(program=program, level=level)
    durations = get_study_durations(program=program, level=level)
    contacts = get_admission_contacts()

    answer = "\n\n".join(
        [
            "Информация приемной комиссии:",
            format_admission_tool_result(programs),
            format_admission_tool_result(prices),
            format_admission_tool_result(scores),
            format_admission_tool_result(durations),
            format_admission_tool_result(contacts),
        ]
    )
    return {
        "status": "ok",
        "tool": "overview",
        "answer": answer,
        "source_path": prices.get("source_path") or contacts.get("source_path"),
        "data_updated_at": prices.get("data_updated_at") or contacts.get("data_updated_at"),
    }


APPLICATION_FIELDS: list[dict[str, str]] = [
    {"key": "full_name", "label": "ФИО", "question": "Укажите ФИО полностью."},
    {"key": "iin", "label": "ИИН", "question": "Укажите ИИН (12 цифр)."},
    {"key": "birth_date", "label": "Дата рождения", "question": "Укажите дату рождения в формате ДД.ММ.ГГГГ."},
    {"key": "phone", "label": "Телефон", "question": "Укажите номер телефона для связи."},
    {"key": "email", "label": "Email", "question": "Укажите email."},
    {"key": "education_level", "label": "Уровень обучения", "question": "На какой уровень хотите поступать: бакалавриат, магистратура, докторантура или второе высшее?"},
    {"key": "program", "label": "Образовательная программа", "question": "На какую образовательную программу хотите подать заявку?"},
    {"key": "study_language", "label": "Язык обучения", "question": "Укажите предпочитаемый язык обучения."},
    {"key": "study_format", "label": "Форма обучения", "question": "Укажите форму обучения, если знаете: очная, дистанционная и т.д."},
    {"key": "comment", "label": "Комментарий", "question": "Если есть комментарий или вопрос для приемной комиссии, напишите его. Если нет, напишите \"нет\"."},
]

APPLICATION_TRIGGER_TERMS = (
    "подать заявку",
    "оставить заявку",
    "создать заявку",
    "оформить заявку",
    "заявка на поступление",
    "хочу поступить",
    "хочу подать документы",
    "хочу подать заявку",
    "поступить к вам",
)

CONFIRM_TERMS = {"да", "подтверждаю", "подтвердить", "верно", "согласен", "ок", "ok", "yes"}
CANCEL_TERMS = {"нет", "отмена", "отменить", "не подтверждаю", "stop", "cancel"}


def _maybe_handle_application_flow(payload: Dict[str, Any], query: str) -> AgentResult | None:
    history = payload.get("history")
    if not _should_run_application_flow(query, history):
        return None

    state = _reconstruct_application_state(history, query)

    if state["saved"]:
        result = {
            "status": "already_saved",
            "tool": "application_form",
            "answer": "Заявка уже была сформирована в этом диалоге. Если нужна новая, начните новый чат и напишите, что хотите подать заявку на поступление.",
        }
        return AgentResult(
            answer=result["answer"],
            intent="admission",
            tool_data=result,
            context=build_context_entries(result),
        )

    pending_key = state["pending_field"]
    if pending_key:
        field_config = _field_config(pending_key)
        answer = (
            "Принято. Продолжим оформление заявки.\n"
            f"{field_config['question']}"
        )
        result = {
            "status": "collecting",
            "tool": "application_form",
            "stage": pending_key,
            "collected_fields": state["collected"],
            "answer": answer,
        }
        return AgentResult(
            answer=answer,
            intent="admission",
            tool_data=result,
            context=build_context_entries(result),
        )

    if not state["awaiting_confirmation"]:
        summary = _format_application_summary(state["collected"])
        answer = (
            "Черновик заявки готов.\n"
            f"{summary}\n\n"
            "Если всё верно, напишите \"да\". Если хотите отменить, напишите \"нет\"."
        )
        result = {
            "status": "awaiting_confirmation",
            "tool": "application_form",
            "collected_fields": state["collected"],
            "answer": answer,
        }
        return AgentResult(
            answer=answer,
            intent="admission",
            tool_data=result,
            context=build_context_entries(result),
        )

    normalized_query = _normalize_text(query)
    if normalized_query in CANCEL_TERMS:
        answer = "Оформление заявки отменено. Если захотите начать заново, напишите, что хотите подать заявку на поступление."
        result = {
            "status": "cancelled",
            "tool": "application_form",
            "collected_fields": state["collected"],
            "answer": answer,
        }
        return AgentResult(
            answer=answer,
            intent="admission",
            tool_data=result,
            context=build_context_entries(result),
        )

    if normalized_query not in CONFIRM_TERMS:
        answer = "Проверьте данные и напишите \"да\" для сохранения заявки или \"нет\" для отмены."
        result = {
            "status": "awaiting_confirmation",
            "tool": "application_form",
            "collected_fields": state["collected"],
            "answer": answer,
        }
        return AgentResult(
            answer=answer,
            intent="admission",
            tool_data=result,
            context=build_context_entries(result),
        )

    created = admission_applications.create_application(
        telegram_id=_safe_int(payload.get("telegram_id") or payload.get("user_id")),
        person_id=_safe_str(payload.get("person_id")),
        channel=_extract_channel(payload),
        full_name=state["collected"]["full_name"],
        iin=state["collected"].get("iin"),
        birth_date=state["collected"].get("birth_date"),
        phone=state["collected"]["phone"],
        email=state["collected"].get("email"),
        education_level=state["collected"]["education_level"],
        program=state["collected"]["program"],
        study_language=state["collected"].get("study_language"),
        study_format=state["collected"].get("study_format"),
        comment=state["collected"].get("comment"),
        payload={
            "source_query": query,
            "history_size": len(history) if isinstance(history, list) else 0,
            "collected_fields": state["collected"],
        },
    )
    answer = (
        "Заявка сохранена в базе.\n"
        f"Номер заявки: {created['id']}\n"
        f"{_format_application_summary(state['collected'])}"
    )
    result = {
        "status": "saved",
        "tool": "application_form",
        "application_id": created["id"],
        "created_at": created.get("created_at"),
        "collected_fields": state["collected"],
        "answer": answer,
    }
    return AgentResult(
        answer=answer,
        intent="admission",
        tool_data=result,
        context=build_context_entries(result),
    )


def _should_run_application_flow(query: str, history: Any) -> bool:
    normalized_query = _normalize_text(query)
    if any(term in normalized_query for term in APPLICATION_TRIGGER_TERMS):
        return True

    if not isinstance(history, list):
        return False

    for item in history[-12:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").lower()
        content = str(item.get("content") or "")
        normalized_content = _normalize_text(content)
        if role == "assistant" and "оформление заявки" in normalized_content:
            return True
        if role == "assistant" and "черновик заявки готов" in normalized_content:
            return True
    return False


def _reconstruct_application_state(history: Any, current_query: str) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if isinstance(history, list):
        for item in history:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").lower()
            content = str(item.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
    if current_query.strip():
        messages.append({"role": "user", "content": current_query.strip()})

    collected: dict[str, str] = {}
    current_field_index = 0
    awaiting_confirmation = False
    saved = False

    for message in messages:
        role = message["role"]
        content = message["content"]
        normalized = _normalize_text(content)

        if role == "assistant":
            if "заявка сохранена в базе" in normalized:
                saved = True
            if "черновик заявки готов" in normalized:
                awaiting_confirmation = True
            continue

        if current_field_index == 0 and any(term in normalized for term in APPLICATION_TRIGGER_TERMS):
            continue

        if awaiting_confirmation:
            continue

        if current_field_index >= len(APPLICATION_FIELDS):
            continue

        field_key = APPLICATION_FIELDS[current_field_index]["key"]
        value = _extract_field_value(field_key, content)
        if value is None:
            continue
        collected[field_key] = value
        current_field_index += 1

    pending_field = None
    if not awaiting_confirmation and current_field_index < len(APPLICATION_FIELDS):
        pending_field = APPLICATION_FIELDS[current_field_index]["key"]

    return {
        "collected": collected,
        "pending_field": pending_field,
        "awaiting_confirmation": awaiting_confirmation,
        "saved": saved,
    }


def _extract_field_value(field_key: str, content: str) -> str | None:
    text = content.strip()
    normalized = _normalize_text(text)
    if not text:
        return None

    if field_key == "full_name":
        if len(text.split()) < 2 or len(text) < 5:
            return None
        return text
    if field_key == "iin":
        digits = re.sub(r"\D", "", text)
        return digits if len(digits) == 12 else None
    if field_key == "birth_date":
        match = re.search(r"\b(\d{2}[./-]\d{2}[./-]\d{4})\b", text)
        return match.group(1).replace("/", ".").replace("-", ".") if match else None
    if field_key == "phone":
        digits = re.sub(r"\D", "", text)
        return text if len(digits) >= 10 else None
    if field_key == "email":
        match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
        return match.group(0) if match else None
    if field_key == "education_level":
        level = extract_level(text)
        if level == "bachelor":
            return "bachelor"
        if level == "master":
            return "master"
        if level == "doctorate":
            return "doctorate"
        if level == "second_higher":
            return "second_higher"
        return None
    if field_key == "program":
        return text if len(text) >= 3 else None
    if field_key == "study_language":
        return text if len(text) >= 2 else None
    if field_key == "study_format":
        return text if len(text) >= 2 else None
    if field_key == "comment":
        return "" if normalized in {"нет", "без комментария", "none", "-"} else text
    return text


def _format_application_summary(collected: dict[str, str]) -> str:
    level_map = {
        "bachelor": "бакалавриат",
        "master": "магистратура",
        "doctorate": "докторантура",
        "second_higher": "второе высшее",
    }
    lines = ["Данные заявки:"]
    for field in APPLICATION_FIELDS:
        key = field["key"]
        value = collected.get(key)
        if value is None or value == "":
            continue
        display_value = level_map.get(value, value) if key == "education_level" else value
        lines.append(f"- {field['label']}: {display_value}")
    return "\n".join(lines)


def _field_config(field_key: str) -> dict[str, str]:
    for field in APPLICATION_FIELDS:
        if field["key"] == field_key:
            return field
    raise KeyError(field_key)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _extract_channel(payload: Dict[str, Any]) -> str | None:
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        channel = metadata.get("channel")
        if channel is not None:
            return str(channel)
    return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
