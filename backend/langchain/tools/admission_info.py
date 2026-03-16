"""Structured admission tools backed by a local JSON knowledge file."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "admission_info.json"
)

LEVEL_ALIASES = {
    "bachelor": {"bachelor", "бакалав", "undergraduate"},
    "master": {"master", "магистр", "магистрат", "masters"},
    "doctorate": {"doctorate", "doctoral", "phd", "doctor", "докторант", "доктор"},
    "second_higher": {"second higher", "second degree", "второе высшее", "высшее образование"},
}

TOOL_TERMS = {
    "prices": {"цена", "стоимость", "оплата", "tuition", "price", "cost"},
    "passing_scores": {"проход", "балл", "ент", "грант", "score", "scores"},
    "documents": {"документ", "справк", "что нужно", "что надо", "document", "documents"},
    "contacts": {"контакт", "телефон", "почта", "email", "адрес", "contact", "contacts", "phone", "mail"},
    "durations": {"срок", "длительность", "сколько уч", "duration", "study period", "how long"},
}


def load_admission_data() -> Dict[str, Any]:
    """Load structured admission data from JSON."""
    configured_path = os.getenv("ADMISSION_DATA_PATH")
    data_path = Path(configured_path) if configured_path else DEFAULT_DATA_PATH
    try:
        return json.loads(data_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"status": "missing_data_file", "data_path": str(data_path)}
    except json.JSONDecodeError as exc:
        return {
            "status": "invalid_data_file",
            "data_path": str(data_path),
            "detail": str(exc),
        }


def get_current_prices(
    *,
    program: Optional[str] = None,
    level: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    matches = _match_programs(data, program=program, level=level)
    if not matches:
        return _not_found("prices", data, level=level, program=program)

    results = []
    for item in matches:
        tuition = item.get("tuition") or {}
        results.append(
            {
                "program": item.get("name"),
                "level": item.get("level"),
                "amount": tuition.get("amount"),
                "currency": data.get("currency", "KZT"),
                "period": tuition.get("period"),
                "updated_at": tuition.get("updated_at") or data.get("last_updated"),
            }
        )
    return {
        "status": "ok",
        "tool": "prices",
        "results": results,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_passing_scores(
    *,
    program: Optional[str] = None,
    level: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    matches = _match_programs(data, program=program, level=level)
    if not matches:
        return _not_found("passing_scores", data, level=level, program=program)

    results = []
    for item in matches:
        score = item.get("passing_score") or {}
        results.append(
            {
                "program": item.get("name"),
                "level": item.get("level"),
                "gop_code": score.get("gop_code"),
                "grant": score.get("grant"),
                "grant_full": score.get("grant_full"),
                "grant_short": score.get("grant_short"),
                "paid": score.get("paid"),
                "exam": score.get("exam"),
                "notes": score.get("notes") or [],
                "updated_at": score.get("updated_at") or data.get("last_updated"),
            }
        )
    return {
        "status": "ok",
        "tool": "passing_scores",
        "results": results,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_required_documents(*, level: Optional[str] = None) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    normalized_level = _normalize_level(level)
    documents = data.get("documents") or {}
    if normalized_level:
        doc_entry = documents.get(normalized_level)
        if not doc_entry:
            return {
                "status": "not_found",
                "tool": "documents",
                "message": f"Documents not found for level '{normalized_level}'.",
                "available_levels": sorted(documents.keys()),
                "source_path": _source_path(),
            }
        results = [{"level": normalized_level, **doc_entry}]
    else:
        results = [{"level": item_level, **entry} for item_level, entry in documents.items()]

    return {
        "status": "ok",
        "tool": "documents",
        "results": results,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_admission_contacts() -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    contacts = data.get("contacts") or {}
    if not contacts:
        return {
            "status": "not_found",
            "tool": "contacts",
            "message": "Admission contacts are not configured.",
            "source_path": _source_path(),
        }

    return {
        "status": "ok",
        "tool": "contacts",
        "contacts": contacts,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_study_durations(
    *,
    program: Optional[str] = None,
    level: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    matches = _match_programs(data, program=program, level=level)
    if not matches:
        return _not_found("durations", data, level=level, program=program)

    results = []
    for item in matches:
        results.append(
            {
                "program": item.get("name"),
                "level": item.get("level"),
                "duration": item.get("duration"),
            }
        )
    return {
        "status": "ok",
        "tool": "durations",
        "results": results,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def detect_requested_tool(query: str) -> str:
    normalized_query = _normalize_text(query)
    for tool_name in ("documents", "contacts", "prices", "passing_scores", "durations"):
        if any(_term_matches_query(term, normalized_query) for term in TOOL_TERMS[tool_name]):
            return tool_name
    return "overview"


def extract_level(query: str) -> Optional[str]:
    normalized_query = _normalize_text(query)
    for normalized, variants in LEVEL_ALIASES.items():
        if any(_term_matches_query(variant, normalized_query) for variant in variants):
            return normalized
    return None


def extract_program(query: str, *, data: Optional[Dict[str, Any]] = None) -> Optional[str]:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return None

    source = data if data is not None else load_admission_data()
    best_match: tuple[int, str] | None = None
    for program in source.get("programs") or []:
        variants = [program.get("name", ""), *(program.get("aliases") or [])]
        for variant in variants:
            if not variant:
                continue
            normalized_variant = _normalize_text(variant)
            if _term_matches_query(normalized_variant, normalized_query):
                score = len(normalized_variant)
                canonical_name = program.get("name")
                if canonical_name and (best_match is None or score > best_match[0]):
                    best_match = (score, canonical_name)
    return best_match[1] if best_match else None


def format_admission_tool_result(result: Dict[str, Any]) -> str:
    if result.get("tool") == "overview" and result.get("answer"):
        return str(result["answer"])

    status = result.get("status")
    if status == "missing_data_file":
        return f"Не найден файл данных для приемной комиссии: {result.get('data_path')}."
    if status == "invalid_data_file":
        return (
            "Файл данных приемной комиссии поврежден или заполнен некорректно. "
            f"Путь: {result.get('data_path')}. Ошибка: {result.get('detail')}."
        )
    if status == "not_found":
        available_programs = result.get("available_programs") or []
        available_levels = result.get("available_levels") or []
        lines = [result.get("message") or "Данные не найдены."]
        if available_levels:
            lines.append(f"Доступные уровни: {', '.join(available_levels)}.")
        if available_programs:
            lines.append(f"Доступные программы: {', '.join(available_programs)}.")
        return "\n".join(lines)

    tool = result.get("tool")
    if tool == "prices":
        lines = ["Актуальные цены по обучению:"]
        for item in result.get("results") or []:
            amount = item.get("amount")
            amount_text = f"{int(amount):,}".replace(",", " ") if isinstance(amount, (int, float)) else "не указано"
            lines.append(
                f"- {item.get('program')} ({item.get('level')}): {amount_text} {item.get('currency')} {item.get('period') or ''}".rstrip()
            )
        return "\n".join(lines)

    if tool == "passing_scores":
        lines = ["Актуальные проходные баллы:"]
        for item in result.get("results") or []:
            grant = item.get("grant")
            grant_full = item.get("grant_full")
            grant_short = item.get("grant_short")
            paid = item.get("paid")
            score_parts = []
            if item.get("gop_code"):
                score_parts.append(f"ГОП {item.get('gop_code')}")
            if grant_full is not None:
                score_parts.append(f"грант полный курс {grant_full}")
            elif grant is not None:
                score_parts.append(f"грант {grant}")
            if grant_short is not None:
                score_parts.append(f"грант сокращенный курс {grant_short}")
            else:
                score_parts.append("грант сокращенный курс нет данных")
            score_parts.append(f"платное {paid if paid is not None else 'нет данных'}")
            score_parts.append(f"основание: {item.get('exam') or 'не указано'}")
            line = f"- {item.get('program')} ({item.get('level')}): " + ", ".join(score_parts) + "."
            notes = item.get("notes") or []
            if notes:
                line += " Примечание: " + " ".join(notes)
            lines.append(line)
        return "\n".join(lines)

    if tool == "documents":
        lines = []
        for entry in result.get("results") or []:
            lines.append(f"{entry.get('title')}:")
            for note in entry.get("notes") or []:
                lines.append(f"- {note}")
            for item in entry.get("items") or []:
                lines.append(f"- {item}")
            for variant in entry.get("variants") or []:
                lines.append(f"{variant.get('title')}:")
                for note in variant.get("notes") or []:
                    lines.append(f"- {note}")
                for item in variant.get("items") or []:
                    lines.append(f"- {item}")
        return "\n".join(lines)

    if tool == "contacts":
        contacts = result.get("contacts") or {}
        phones = ", ".join(contacts.get("phone") or []) or "не указаны"
        emails = ", ".join(contacts.get("email") or []) or "не указаны"
        return (
            f"{contacts.get('department') or 'Приемная комиссия'}\n"
            f"Телефоны: {phones}\n"
            f"Email: {emails}\n"
            f"Адрес: {contacts.get('address') or 'не указан'}\n"
            f"Время работы: {contacts.get('working_hours') or 'не указано'}\n"
            f"Сайт: {contacts.get('website') or 'не указан'}"
        )

    if tool == "durations":
        lines = ["Сроки обучения:"]
        for item in result.get("results") or []:
            lines.append(
                f"- {item.get('program')} ({item.get('level')}): {item.get('duration') or 'не указано'}."
            )
        return "\n".join(lines)

    return "Данные по поступлению загружены, но формат ответа для этого инструмента не настроен."


def build_context_entries(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    content = format_admission_tool_result(result)
    return [
        {
            "content": content,
            "metadata": {
                "source_path": result.get("source_path") or "backend/data/admission_info.json",
                "tool": result.get("tool") or "admission_info",
                "data_updated_at": result.get("data_updated_at"),
            },
        }
    ]


def _match_programs(
    data: Dict[str, Any],
    *,
    program: Optional[str],
    level: Optional[str],
) -> List[Dict[str, Any]]:
    programs = data.get("programs") or []
    normalized_level = _normalize_level(level)
    normalized_program = _normalize_text(program)
    matches: List[Dict[str, Any]] = []
    for item in programs:
        if normalized_level and item.get("level") != normalized_level:
            continue
        if normalized_program:
            candidates = [item.get("name", ""), *(item.get("aliases") or [])]
            if not any(_program_matches(normalized_program, candidate) for candidate in candidates if candidate):
                continue
        matches.append(item)
    return matches


def _normalize_level(level: Optional[str]) -> Optional[str]:
    if not level:
        return None
    level_text = level.lower().strip()
    for normalized, variants in LEVEL_ALIASES.items():
        if level_text in variants:
            return normalized
    return level_text


def _normalize_text(text: Optional[str]) -> str:
    raw = (text or "").lower().strip()
    cleaned = re.sub(r"[^\w\s]+", " ", raw)
    return re.sub(r"\s+", " ", cleaned).strip()


def _program_matches(requested_program: str, candidate: str) -> bool:
    normalized_candidate = _normalize_text(candidate)
    return (
        normalized_candidate == requested_program
        or _term_matches_query(normalized_candidate, requested_program)
        or _term_matches_query(requested_program, normalized_candidate)
    )


def _term_matches_query(term: str, normalized_query: str) -> bool:
    normalized_term = _normalize_text(term)
    if not normalized_term:
        return False
    if " " in normalized_term:
        return normalized_term in normalized_query

    query_words = normalized_query.split()
    return any(
        word == normalized_term or word.startswith(normalized_term)
        for word in query_words
    )


def _not_found(
    tool: str,
    data: Dict[str, Any],
    *,
    level: Optional[str],
    program: Optional[str],
) -> Dict[str, Any]:
    return {
        "status": "not_found",
        "tool": tool,
        "message": "Подходящие данные не найдены по указанным параметрам.",
        "requested_level": _normalize_level(level),
        "requested_program": program,
        "available_programs": [item.get("name") for item in data.get("programs") or [] if item.get("name")],
        "available_levels": sorted({item.get("level") for item in data.get("programs") or [] if item.get("level")}),
        "source_path": _source_path(),
    }


def _source_path() -> str:
    configured_path = os.getenv("ADMISSION_DATA_PATH")
    path = Path(configured_path) if configured_path else DEFAULT_DATA_PATH
    return str(path)
