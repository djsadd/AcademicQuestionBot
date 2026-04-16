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
DEFAULT_LANGUAGE = "ru"
SUPPORTED_LANGUAGES = {"ru", "kk", "en"}

TEXTS = {
    "ru": {
        "overview_title": "Информация приемной комиссии:",
        "missing_data_file": "Не найден файл данных для приемной комиссии: {data_path}.",
        "invalid_data_file": "Файл данных приемной комиссии поврежден или заполнен некорректно. Путь: {data_path}. Ошибка: {detail}.",
        "not_found": "Подходящие данные не найдены по указанным параметрам.",
        "not_found_contacts_hint": "Если вам нужна точная консультация, свяжитесь с приемной комиссией:",
        "available_levels": "Доступные уровни: {items}.",
        "available_programs": "Доступные программы: {items}.",
        "contacts_department_fallback": "Приемная комиссия",
        "contacts_postal_address": "Почтовый адрес:",
        "contacts_address": "Адрес: {value}",
        "contacts_bachelor": "Бакалавриат:",
        "contacts_graduate": "Магистратура и докторантура:",
        "contacts_schedule": "График работы: {value}",
        "contacts_label_fallback": "Контакт",
        "contacts_phone_missing": "не указан",
        "contacts_phones": "Телефоны: {value}",
        "contacts_emails": "Email: {value}",
        "contacts_working_hours": "Время работы: {value}",
        "contacts_website": "Сайт: {value}",
        "contacts_technical": "Технические специалисты:",
        "programs_title": "Доступные специальности:",
        "programs_level_bachelor": "Бакалавриат",
        "programs_level_master": "Магистратура",
        "programs_level_doctorate": "Докторантура",
        "programs_level_second_higher": "Второе высшее",
        "programs_level_other": "Другие программы",
        "source_label": "Источник",
        "prices_title": "Актуальные цены по обучению:",
        "not_specified": "не указано",
        "passing_scores_title": "Актуальные проходные баллы:",
        "passing_gop": "ГОП {value}",
        "passing_grant_full": "грант полный курс {value}",
        "passing_grant": "грант {value}",
        "passing_grant_short": "грант сокращенный курс {value}",
        "passing_grant_short_missing": "грант сокращенный курс нет данных",
        "passing_paid": "платное {value}",
        "passing_exam": "основание: {value}",
        "passing_notes": "Примечание: {value}",
        "documents_not_found": "Документы не найдены для уровня '{level}'.",
        "durations_title": "Сроки обучения:",
        "scholarships_title": "Стипендии и государственные гранты:",
        "management_title": "Руководство университета:",
        "fallback_answer": "Данные по поступлению загружены, но формат ответа для этого инструмента не настроен.",
    },
    "kk": {
        "overview_title": "Қабылдау комиссиясы туралы ақпарат:",
        "missing_data_file": "Қабылдау комиссиясы деректері файлы табылмады: {data_path}.",
        "invalid_data_file": "Қабылдау комиссиясы деректері файлы бүлінген немесе қате толтырылған. Жолы: {data_path}. Қате: {detail}.",
        "not_found": "Көрсетілген параметрлер бойынша деректер табылмады.",
        "not_found_contacts_hint": "Егер сізге нақты кеңес керек болса, қабылдау комиссиясымен байланысыңыз:",
        "available_levels": "Қолжетімді деңгейлер: {items}.",
        "available_programs": "Қолжетімді бағдарламалар: {items}.",
        "contacts_department_fallback": "Қабылдау комиссиясы",
        "contacts_postal_address": "Пошта мекенжайы:",
        "contacts_address": "Мекенжайы: {value}",
        "contacts_bachelor": "Бакалавриат:",
        "contacts_graduate": "Магистратура және докторантура:",
        "contacts_schedule": "Жұмыс кестесі: {value}",
        "contacts_label_fallback": "Байланыс",
        "contacts_phone_missing": "көрсетілмеген",
        "contacts_phones": "Телефондар: {value}",
        "contacts_emails": "Email: {value}",
        "contacts_working_hours": "Жұмыс уақыты: {value}",
        "contacts_website": "Сайт: {value}",
        "contacts_technical": "Техникалық мамандар:",
        "programs_title": "Қолжетімді мамандықтар:",
        "programs_level_bachelor": "Бакалавриат",
        "programs_level_master": "Магистратура",
        "programs_level_doctorate": "Докторантура",
        "programs_level_second_higher": "Екінші жоғары",
        "programs_level_other": "Басқа бағдарламалар",
        "source_label": "Анықтама",
        "prices_title": "Оқу құны:",
        "not_specified": "көрсетілмеген",
        "passing_scores_title": "Өту балдары:",
        "passing_gop": "ГОП {value}",
        "passing_grant_full": "толық курс гранты {value}",
        "passing_grant": "грант {value}",
        "passing_grant_short": "қысқартылған курс гранты {value}",
        "passing_grant_short_missing": "қысқартылған курс гранты бойынша дерек жоқ",
        "passing_paid": "ақылы {value}",
        "passing_exam": "негізі: {value}",
        "passing_notes": "Ескерту: {value}",
        "documents_not_found": "'{level}' деңгейі үшін құжаттар табылмады.",
        "durations_title": "Оқу мерзімдері:",
        "scholarships_title": "Стипендиялар және мемлекеттік гранттар:",
        "management_title": "Университет басшылығы:",
        "fallback_answer": "Оқуға түсу деректері жүктелді, бірақ бұл құрал үшін жауап форматы бапталмаған.",
    },
    "en": {
        "overview_title": "Admissions information:",
        "missing_data_file": "Admission data file not found: {data_path}.",
        "invalid_data_file": "Admission data file is invalid or corrupted. Path: {data_path}. Error: {detail}.",
        "not_found": "No matching data was found for the requested parameters.",
        "not_found_contacts_hint": "If you need an exact answer, contact the admissions office:",
        "available_levels": "Available levels: {items}.",
        "available_programs": "Available programs: {items}.",
        "contacts_department_fallback": "Admissions Office",
        "contacts_postal_address": "Postal address:",
        "contacts_address": "Address: {value}",
        "contacts_bachelor": "Bachelor programs:",
        "contacts_graduate": "Master's and doctoral programs:",
        "contacts_schedule": "Working hours: {value}",
        "contacts_label_fallback": "Contact",
        "contacts_phone_missing": "not specified",
        "contacts_phones": "Phones: {value}",
        "contacts_emails": "Email: {value}",
        "contacts_working_hours": "Working hours: {value}",
        "contacts_website": "Website: {value}",
        "contacts_technical": "Technical contacts:",
        "programs_title": "Available programs:",
        "programs_level_bachelor": "Bachelor",
        "programs_level_master": "Master",
        "programs_level_doctorate": "Doctorate",
        "programs_level_second_higher": "Second higher education",
        "programs_level_other": "Other programs",
        "source_label": "Source",
        "prices_title": "Current tuition fees:",
        "not_specified": "not specified",
        "passing_scores_title": "Current passing scores:",
        "passing_gop": "GOP {value}",
        "passing_grant_full": "full-course grant {value}",
        "passing_grant": "grant {value}",
        "passing_grant_short": "short-course grant {value}",
        "passing_grant_short_missing": "no short-course grant data",
        "passing_paid": "paid {value}",
        "passing_exam": "basis: {value}",
        "passing_notes": "Notes: {value}",
        "documents_not_found": "Documents not found for level '{level}'.",
        "durations_title": "Study durations:",
        "scholarships_title": "Scholarships and state grants:",
        "management_title": "University leadership:",
        "fallback_answer": "Admission data is loaded, but the response format for this tool is not configured.",
    },
}

LEVEL_ALIASES = {
    "bachelor": {"bachelor", "бакалав", "undergraduate"},
    "master": {"master", "магистр", "магистрат", "masters"},
    "doctorate": {"doctorate", "doctoral", "phd", "doctor", "докторант", "доктор"},
    "second_higher": {"second higher", "second degree", "второе высшее", "высшее образование"},
}

ADMISSION_CONTACTS = {
    "department": "Приёмная комиссия",
    "postal_address": [
        "010000",
        "г. Астана",
        "Республика Казахстан",
        "ул. Ы. Дукенулы, 29 (по 2ГИС: 29а)",
        "Корпус А",
        "Университет «Туран-Астана»",
        "Приёмная комиссия",
    ],
    "address": (
        "010000, г. Астана, Республика Казахстан, ул. Ы. Дукенулы, 29 "
        "(по 2ГИС: 29а), Корпус А, Университет «Туран-Астана», Приёмная комиссия"
    ),
    "bachelor_contacts": [
        {"phone": "+7 700 139 51 10", "label": "Приемная комиссия"},
        {"phone": "+7 702 912 39 97", "label": "Сауле Сенбековна"},
        {"phone": "+7 747 911 55 28", "label": "Татьяна Юрьевна"},
        {"phone": "+7 777 038 21 52", "label": "Талгат Амирханович"},
        {"phone": "+7 701 158 89 24", "label": "Алмаз Шаирбекович"},
    ],
    "graduate_contacts": [
        {"phone": "+7 702 912 39 97", "label": "Сауле Сенбековна"},
        {"phone": "+7 701 677 99 94", "label": "Алмас Маратбекович"},
    ],
    "working_hours": "Понедельник – Пятница: с 09:00 до 18:00. Обеденный перерыв: с 13:00 до 14:00.",
    "note": "Обращайтесь по любым вопросам — мы всегда готовы помочь!",
}

TOOL_TERMS = {
    "programs": {
        "специальност",
        "специальности",
        "образовательные программы",
        "программы",
        "направления",
        "какие есть программы",
        "какие есть специальности",
        "programs",
        "majors",
        "specialties",
        "degrees",
    },
    "prices": {"цена", "стоимость", "оплата", "tuition", "price", "cost"},
    "passing_scores": {"проход", "балл", "ент", "грант", "score", "scores"},
    "documents": {"документ", "справк", "что нужно", "что надо", "document", "documents"},
    "contacts": {"контакт", "телефон", "почта", "email", "адрес", "contact", "contacts", "phone", "mail"},
    "durations": {"срок", "длительность", "сколько уч", "duration", "study period", "how long"},
}

LEVEL_ALIASES["bachelor"].update({"бакалавриат", "бакалавр", "бакалаврият", "бакалавриатқа", "бакалавриатта"})
LEVEL_ALIASES["master"].update({"магистратура", "магистратураға", "магистратурада", "магистрлік"})
LEVEL_ALIASES["doctorate"].update({"докторантура", "докторантураға", "докторантурада", "докторлық"})
LEVEL_ALIASES["second_higher"].update({"екінші жоғары", "екінші білім", "екінші жоғары білім"})

TOOL_TERMS["programs"].update(
    {
        "бағдарлама",
        "бағдарламалар",
        "білім беру бағдарламалары",
        "мамандық",
        "мамандықтар",
        "қандай бағдарламалар бар",
        "қандай мамандықтар бар",
    }
)
TOOL_TERMS["prices"].update({"құны", "бағасы", "оқу ақысы"})
TOOL_TERMS["passing_scores"].update({"өту балы", "балл", "ұбт", "шекті балл"})
TOOL_TERMS["documents"].update({"құжат", "құжаттар", "не керек", "қандай құжаттар керек"})
TOOL_TERMS["contacts"].update({"байланыс", "телефон", "пошта", "мекенжай"})
TOOL_TERMS["durations"].update({"мерзім", "ұзақтығы", "қанша жыл", "оқу мерзімі"})


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


def normalize_language(language: Optional[str]) -> str:
    value = (language or DEFAULT_LANGUAGE).strip().lower()
    if "-" in value:
        value = value.split("-", 1)[0]
    return value if value in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def _text(language: Optional[str], key: str, **kwargs: Any) -> str:
    lang = normalize_language(language)
    template = TEXTS.get(lang, TEXTS[DEFAULT_LANGUAGE]).get(key) or TEXTS[DEFAULT_LANGUAGE][key]
    return template.format(**kwargs)


def _resolve_localized_value(value: Any, language: Optional[str]) -> Any:
    lang = normalize_language(language)
    if isinstance(value, dict):
        localized_keys = []
        for key in value.keys():
            if not isinstance(key, str):
                continue
            normalized_key = key.strip().lower()
            if "-" in normalized_key:
                normalized_key = normalized_key.split("-", 1)[0]
            if normalized_key in SUPPORTED_LANGUAGES:
                localized_keys.append(key)
        if localized_keys:
            for key in (lang, DEFAULT_LANGUAGE, "kk", "en"):
                if key in value and value.get(key) not in (None, "", [], {}):
                    return _resolve_localized_value(value[key], lang)
            for key in localized_keys:
                nested = value.get(key)
                if nested not in (None, "", [], {}):
                    return _resolve_localized_value(nested, lang)
        return {key: _resolve_localized_value(item, lang) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_localized_value(item, lang) for item in value]
    return value


def _as_text(value: Any, language: Optional[str]) -> str:
    resolved = _resolve_localized_value(value, language)
    if resolved is None:
        return ""
    return str(resolved)


def get_current_prices(
    *,
    program: Optional[str] = None,
    level: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    matches = _match_programs(data, program=program, level=level)
    if not matches:
        return _not_found("prices", data, level=level, program=program, language=lang)

    results = []
    for item in matches:
        tuition = item.get("tuition") or {}
        results.append(
            {
                "program": _program_display_name(item, language=lang),
                "level": item.get("level"),
                "amount": tuition.get("amount"),
                "currency": data.get("currency", "KZT"),
                "period": _resolve_localized_value(tuition.get("period"), lang),
                "updated_at": tuition.get("updated_at") or data.get("last_updated"),
            }
        )
    return {
        "status": "ok",
        "tool": "prices",
        "language": lang,
        "results": results,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_available_programs(*, level: Optional[str] = None, language: Optional[str] = None) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    matches = _match_programs(data, program=None, level=level)
    if not matches:
        return _not_found("programs", data, level=level, program=None, language=lang)

    results = []
    for item in matches:
        results.append(
            {
                "program": _program_display_name(item, language=lang),
                "level": item.get("level"),
                "duration": _resolve_localized_value(item.get("duration"), lang),
                "gop_code": (item.get("passing_score") or {}).get("gop_code"),
                "source": item.get("source"),
            }
        )
    return {
        "status": "ok",
        "tool": "programs",
        "language": lang,
        "results": results,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_passing_scores(
    *,
    program: Optional[str] = None,
    level: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    matches = _match_programs(data, program=program, level=level)
    if not level:
        meaningful_matches = [item for item in matches if _has_meaningful_passing_score(item)]
        if meaningful_matches:
            matches = meaningful_matches
    if not matches:
        return _not_found("passing_scores", data, level=level, program=program, language=lang)

    results = []
    for item in matches:
        score = item.get("passing_score") or {}
        results.append(
            {
                "program": _program_display_name(item, language=lang),
                "level": item.get("level"),
                "gop_code": score.get("gop_code"),
                "grant": score.get("grant"),
                "grant_full": score.get("grant_full"),
                "grant_short": score.get("grant_short"),
                "paid": score.get("paid"),
                "exam": _resolve_localized_value(score.get("exam"), lang),
                "notes": _resolve_localized_value(score.get("notes") or [], lang),
                "updated_at": score.get("updated_at") or data.get("last_updated"),
            }
        )
    return {
        "status": "ok",
        "tool": "passing_scores",
        "language": lang,
        "results": results,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def _has_meaningful_passing_score(program_item: Dict[str, Any]) -> bool:
    score = program_item.get("passing_score") or {}
    return any(
        score.get(field) not in (None, "", [], {})
        for field in ("grant", "grant_full", "grant_short", "paid", "exam", "gop_code")
    )


def get_required_documents(*, level: Optional[str] = None, language: Optional[str] = None) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    normalized_level = _normalize_level(level)
    documents = data.get("documents") or {}
    if normalized_level:
        doc_entry = documents.get(normalized_level)
        if not doc_entry:
            return {
                "status": "not_found",
                "tool": "documents",
                "language": lang,
                "message": _text(lang, "documents_not_found", level=normalized_level),
                "available_levels": sorted(documents.keys()),
                "source_path": _source_path(),
            }
        results = [{"level": normalized_level, **_resolve_localized_value(doc_entry, lang)}]
    else:
        results = [{"level": item_level, **_resolve_localized_value(entry, lang)} for item_level, entry in documents.items()]

    return {
        "status": "ok",
        "tool": "documents",
        "language": lang,
        "results": results,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_admission_contacts(*, language: Optional[str] = None) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    contacts = _resolve_localized_value(data.get("contacts") or {}, lang)
    return {
        "status": "ok",
        "tool": "contacts",
        "language": lang,
        "contacts": contacts,
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_study_durations(
    *,
    program: Optional[str] = None,
    level: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    normalized_level = _normalize_level(level)
    duration_rules = data.get("duration_rules") or {}

    if normalized_level and not program:
        rules = duration_rules.get(normalized_level)
        if rules:
            return {
                "status": "ok",
                "tool": "durations",
                "language": lang,
                "results": [],
                "duration_rules": [{"level": normalized_level, **_resolve_localized_value(rules, lang)}],
                "data_updated_at": data.get("last_updated"),
                "source_path": _source_path(),
            }

    matches = _match_programs(data, program=program, level=level)
    if not matches:
        return _not_found("durations", data, level=level, program=program, language=lang)

    results = []
    for item in matches:
        results.append(
            {
                "program": _program_display_name(item, language=lang),
                "level": item.get("level"),
                "duration": _resolve_localized_value(item.get("duration"), lang),
            }
        )
    return {
        "status": "ok",
        "tool": "durations",
        "language": lang,
        "results": results,
        "duration_rules": (
            [{"level": normalized_level, **_resolve_localized_value(duration_rules[normalized_level], lang)}]
            if normalized_level and normalized_level in duration_rules
            else []
        ),
        "data_updated_at": data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_scholarships(*, language: Optional[str] = None) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    scholarships = _resolve_localized_value(data.get("scholarships") or {}, lang)
    return {
        "status": "ok",
        "tool": "scholarships",
        "language": lang,
        "scholarships": scholarships,
        "data_updated_at": (
            scholarships.get("updated_at")
            if isinstance(scholarships, dict)
            else data.get("last_updated")
        ) or data.get("last_updated"),
        "source_path": _source_path(),
    }


def get_management(*, language: Optional[str] = None) -> Dict[str, Any]:
    data = load_admission_data()
    if data.get("status") in {"missing_data_file", "invalid_data_file"}:
        return data

    lang = normalize_language(language)
    management = _resolve_localized_value(data.get("management") or {}, lang)
    return {
        "status": "ok",
        "tool": "management",
        "language": lang,
        "management": management,
        "data_updated_at": (
            management.get("updated_at")
            if isinstance(management, dict)
            else data.get("last_updated")
        ) or data.get("last_updated"),
        "source_path": _source_path(),
    }


def detect_requested_tool(query: str) -> str:
    normalized_query = _normalize_text(query)
    raw_query = (query or "").casefold()
    scholarship_terms = {
        "стипенд",
        "стипендия",
        "стипендии",
        "гос стипендия",
        "государственная стипендия",
        "повышенная стипендия",
        "президентская стипендия",
        "scholarship",
        "stipend",
        "шәкіртақы",
    }
    if any(
        _term_matches_query(term, normalized_query)
        or _normalize_text(term) in normalized_query
        or term.casefold() in raw_query
        for term in scholarship_terms
    ):
        return "scholarships"

    management_terms = {
        "руководство",
        "руководящий состав",
        "состав руководства",
        "администрация университета",
        "ректор",
        "проректор",
        "first vice rector",
        "leadership",
        "management",
        "rector",
    }
    if any(
        _term_matches_query(term, normalized_query)
        or _normalize_text(term) in normalized_query
        or term.casefold() in raw_query
        for term in management_terms
    ):
        return "management"

    for tool_name in ("programs", "documents", "contacts", "prices", "passing_scores", "durations"):
        if any(
            _term_matches_query(term, normalized_query)
            or _normalize_text(term) in normalized_query
            or term.casefold() in raw_query
            for term in TOOL_TERMS[tool_name]
        ):
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
        variants = _program_candidates(program)
        for variant in variants:
            if not variant:
                continue
            normalized_variant = _normalize_text(variant)
            if _term_matches_query(normalized_variant, normalized_query):
                score = len(normalized_variant)
                canonical_name = _program_display_name(program)
                if canonical_name and (best_match is None or score > best_match[0]):
                    best_match = (score, canonical_name)
    return best_match[1] if best_match else None


def format_admission_tool_result(result: Dict[str, Any], language: Optional[str] = None) -> str:
    lang = normalize_language(language or result.get("language"))
    if result.get("tool") == "overview" and result.get("answer"):
        return str(result["answer"])
    if result.get("tool") == "application_form" and result.get("answer"):
        return str(result["answer"])
    if result.get("tool") == "contacts":
        contacts = result.get("contacts")
        if not isinstance(contacts, dict):
            return str(contacts or _text(lang, "not_specified"))

    status = result.get("status")
    if status == "missing_data_file":
        return _text(lang, "missing_data_file", data_path=result.get("data_path"))
    if status == "invalid_data_file":
        return _text(lang, "invalid_data_file", data_path=result.get("data_path"), detail=result.get("detail"))
    if status == "not_found":
        available_programs = result.get("available_programs") or []
        available_levels = result.get("available_levels") or []
        lines = [result.get("message") or _text(lang, "not_found")]
        if available_levels:
            lines.append(_text(lang, "available_levels", items=", ".join(available_levels)))
        if available_programs:
            lines.append(_text(lang, "available_programs", items=", ".join(available_programs)))
        contacts = result.get("contacts")
        if isinstance(contacts, dict) and contacts:
            lines.append("")
            lines.append(_text(lang, "not_found_contacts_hint"))
            lines.append(
                format_admission_tool_result(
                    {
                        "status": "ok",
                        "tool": "contacts",
                        "language": lang,
                        "contacts": contacts,
                    },
                    language=lang,
                )
            )
        return "\n".join(lines)

    tool = result.get("tool")
    if tool == "programs":
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for item in result.get("results") or []:
            level = str(item.get("level") or "other")
            grouped.setdefault(level, []).append(item)

        level_titles = {
            "bachelor": _text(lang, "programs_level_bachelor"),
            "master": _text(lang, "programs_level_master"),
            "doctorate": _text(lang, "programs_level_doctorate"),
            "second_higher": _text(lang, "programs_level_second_higher"),
            "other": _text(lang, "programs_level_other"),
        }

        lines = [_text(lang, "programs_title")]
        for level in ("bachelor", "master", "doctorate", "second_higher", "other"):
            items = grouped.get(level) or []
            if not items:
                continue
            lines.append(f"{level_titles.get(level, level)}:")
            for item in items:
                gop_code = item.get("gop_code")
                suffix = f" (GOP {gop_code})" if gop_code and lang == "en" else f" (ГОП {gop_code})" if gop_code else ""
                lines.append(f"- {item.get('program')}{suffix}")
                source = item.get("source")
                if source:
                    lines.append(f"  {_text(lang, 'source_label')}: {source}")
        return "\n".join(lines)

    if tool == "prices":
        lines = [_text(lang, "prices_title")]
        for item in result.get("results") or []:
            amount = item.get("amount")
            amount_text = f"{int(amount):,}".replace(",", " ") if isinstance(amount, (int, float)) else _text(lang, "not_specified")
            lines.append(
                f"- {item.get('program')} ({item.get('level')}): {amount_text} {item.get('currency')} {item.get('period') or ''}".rstrip()
            )
        return "\n".join(lines)

    if tool == "passing_scores":
        lines = [_text(lang, "passing_scores_title")]
        for item in result.get("results") or []:
            grant = item.get("grant")
            grant_full = item.get("grant_full")
            grant_short = item.get("grant_short")
            paid = item.get("paid")
            score_parts = []
            if item.get("gop_code"):
                score_parts.append(_text(lang, "passing_gop", value=item.get("gop_code")))
            if grant_full is not None:
                score_parts.append(_text(lang, "passing_grant_full", value=grant_full))
            elif grant is not None:
                score_parts.append(_text(lang, "passing_grant", value=grant))
            if grant_short is not None:
                score_parts.append(_text(lang, "passing_grant_short", value=grant_short))
            else:
                score_parts.append(_text(lang, "passing_grant_short_missing"))
            score_parts.append(_text(lang, "passing_paid", value=paid if paid is not None else _text(lang, "not_specified")))
            score_parts.append(_text(lang, "passing_exam", value=item.get("exam") or _text(lang, "not_specified")))
            line = f"- {item.get('program')} ({item.get('level')}): " + ", ".join(score_parts) + "."
            notes = item.get("notes") or []
            if notes:
                line += " " + _text(lang, "passing_notes", value=" ".join(str(note) for note in notes))
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
        phones = ", ".join(contacts.get("phone") or []) or _text(lang, "not_specified")
        emails = ", ".join(contacts.get("email") or []) or _text(lang, "not_specified")
        technical_contacts = contacts.get("technical_contacts") or []
        technical_lines = []
        for entry in technical_contacts:
            name = entry.get("name") or _text(lang, "contacts_label_fallback")
            phone = entry.get("phone") or _text(lang, "contacts_phone_missing")
            note = entry.get("note") or ""
            suffix = f" ({note})" if note else ""
            technical_lines.append(f"- {name}: {phone}{suffix}")
        technical_block = (
            "\n" + _text(lang, "contacts_technical") + "\n" + "\n".join(technical_lines)
            if technical_lines
            else ""
        )
        return (
            f"{contacts.get('department') or _text(lang, 'contacts_department_fallback')}\n"
            f"{_text(lang, 'contacts_phones', value=phones)}\n"
            f"{_text(lang, 'contacts_emails', value=emails)}\n"
            f"{_text(lang, 'contacts_address', value=contacts.get('address') or _text(lang, 'not_specified'))}\n"
            f"{_text(lang, 'contacts_working_hours', value=contacts.get('working_hours') or _text(lang, 'not_specified'))}\n"
            f"{_text(lang, 'contacts_website', value=contacts.get('website') or _text(lang, 'not_specified'))}"
            f"{technical_block}"
        )

    if tool == "durations":
        lines = [_text(lang, "durations_title")]
        for item in result.get("results") or []:
            lines.append(
                f"- {item.get('program')} ({item.get('level')}): {item.get('duration') or _text(lang, 'not_specified')}."
            )
        for rule in result.get("duration_rules") or []:
            lines.append(f"{rule.get('title')}:")
            for item in rule.get("items") or []:
                lines.append(f"- {item}")
        return "\n".join(lines)

    if tool == "scholarships":
        scholarships = result.get("scholarships") or {}
        if not isinstance(scholarships, dict):
            return str(scholarships or _text(lang, "not_specified"))

        lines = [_text(lang, "scholarships_title")]
        for section in scholarships.get("sections") or []:
            title = section.get("title")
            if title:
                lines.append(title)
            for note in section.get("notes") or []:
                lines.append(f"- {note}")
            for item in section.get("items") or []:
                lines.append(f"- {item}")
        return "\n".join(lines)

    if tool == "management":
        management = result.get("management") or {}
        if not isinstance(management, dict):
            return str(management or _text(lang, "not_specified"))

        lines = [_text(lang, "management_title")]
        rector = management.get("rector") or {}
        rector_name = rector.get("name")
        if rector_name:
            lines.append("Ректор:")
            lines.append(f"- {rector_name}")
            for item in rector.get("items") or []:
                lines.append(f"- {item}")

        leadership = management.get("leadership") or []
        if leadership:
            lines.append("Руководящий состав:")
            for entry in leadership:
                name = entry.get("name")
                if not name:
                    continue
                lines.append(f"- {name}")
                for item in entry.get("items") or []:
                    lines.append(f"- {item}")
        return "\n".join(lines)

    return _text(lang, "fallback_answer")


def build_context_entries(result: Dict[str, Any], language: Optional[str] = None) -> List[Dict[str, Any]]:
    lang = normalize_language(language or result.get("language"))
    content = format_admission_tool_result(result, language=lang)
    return [
        {
            "content": content,
            "metadata": {
                "source_path": result.get("source_path") or "backend/data/admission_info.json",
                "tool": result.get("tool") or "admission_info",
                "data_updated_at": result.get("data_updated_at"),
                "language": lang,
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
            candidates = _program_candidates(item)
            if not any(_program_matches(normalized_program, candidate) for candidate in candidates if candidate):
                continue
        matches.append(item)
    return matches


def _program_candidates(program: Dict[str, Any]) -> List[str]:
    candidates: List[Any] = [
        program.get("name"),
        program.get("name_ru"),
        program.get("name_kk"),
        program.get("name_en"),
    ]
    aliases = program.get("aliases")
    if isinstance(aliases, list):
        candidates.extend(aliases)
    elif aliases is not None:
        candidates.append(aliases)
    result: List[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = _resolve_localized_value(candidate, DEFAULT_LANGUAGE)
        values = resolved if isinstance(resolved, list) else [resolved]
        for value in values:
            normalized = _normalize_text(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(str(value))
    return result


def _program_display_name(program: Dict[str, Any], language: Optional[str] = None) -> str:
    lang = normalize_language(language)
    localized_name = _resolve_localized_value(program.get(f"name_{lang}"), lang)
    return str(
        localized_name
        or _resolve_localized_value(program.get("name_ru"), lang)
        or _resolve_localized_value(program.get("name"), lang)
        or _resolve_localized_value(program.get("name_kk"), lang)
        or _resolve_localized_value(program.get("name_en"), lang)
        or program.get("id")
        or ""
    )


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
    language: Optional[str],
) -> Dict[str, Any]:
    lang = normalize_language(language)
    return {
        "status": "not_found",
        "tool": tool,
        "language": lang,
        "message": _text(lang, "not_found"),
        "requested_level": _normalize_level(level),
        "requested_program": program,
        "contacts": _resolve_localized_value(data.get("contacts") or {}, lang),
        "available_programs": [
            _program_display_name(item, language=lang)
            for item in data.get("programs") or []
            if _program_display_name(item, language=lang)
        ],
        "available_levels": sorted({item.get("level") for item in data.get("programs") or [] if item.get("level")}),
        "source_path": _source_path(),
    }


def _source_path() -> str:
    configured_path = os.getenv("ADMISSION_DATA_PATH")
    path = Path(configured_path) if configured_path else DEFAULT_DATA_PATH
    return str(path)
