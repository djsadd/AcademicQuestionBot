"""Deterministic slot collection for admission requests."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
from typing import Any

from ..langchain.tools.admission_info import extract_level, extract_program, load_admission_data
from .profile_subjects import PROFILE_SUBJECT_1, PROFILE_SUBJECT_2, ProfileSubjectAgent


SLOT_CONFIG: dict[str, dict[str, Any]] = {
    "tuition": {
        "required": ["program"],
    },
    "competition": {
        "required": ["program"],
    },
    "international": {
        "required": ["citizenship", "degree"],
        "conditional": [
            {
                "when": {"slot": "citizenship", "operator": "is_foreign"},
                "required": ["language"],
            }
        ],
    },
    "eligibility": {
        "required": ["education_level"],
    },
}

CARRY_FORWARD_SLOTS = {
    "year",
    "degree",
    "program",
    "citizenship",
    "language",
    "education_level",
    PROFILE_SUBJECT_1,
    PROFILE_SUBJECT_2,
}

PROFILE_SLOT_KEYS = {
    *CARRY_FORWARD_SLOTS,
    "ent_score",
    "full_name",
}

SLOT_QUESTIONS: dict[str, dict[str, str]] = {
    "degree": {
        "ru": "Какой уровень обучения вас интересует: бакалавриат, магистратура или докторантура?",
        "kk": "Сізді қай оқу деңгейі қызықтырады: бакалавриат, магистратура әлде докторантура?",
        "en": "Which degree level are you interested in: bachelor's, master's, or doctorate?",
    },
    "program": {
        "ru": "Для какой образовательной программы вам нужна информация?",
        "kk": "Сізге қай білім беру бағдарламасы бойынша ақпарат қажет?",
        "en": "Which educational program do you need information about?",
    },
    "ent_score": {
        "ru": "Какой у вас балл ЕНТ или вступительного теста?",
        "kk": "ҰБТ немесе қабылдау тестінен қанша балл жинадыңыз?",
        "en": "What is your UNT or entrance test score?",
    },
    "citizenship": {
        "ru": "Укажите, пожалуйста, ваше гражданство.",
        "kk": "Азаматтығыңызды көрсетіңіз.",
        "en": "Please specify your citizenship.",
    },
    "language": {
        "ru": "На каком языке вы планируете обучаться: русском, казахском или английском?",
        "kk": "Қай тілде оқуды жоспарлайсыз: қазақ, орыс әлде ағылшын тілінде?",
        "en": "Which language do you plan to study in: Kazakh, Russian, or English?",
    },
    "education_level": {
        "ru": "Какое у вас текущее образование: школа, колледж, бакалавриат или магистратура?",
        "kk": "Қазіргі біліміңіз қандай: мектеп, колледж, бакалавриат әлде магистратура?",
        "en": "What is your current education level: school, college, bachelor's, or master's?",
    },
    PROFILE_SUBJECT_1: {
        "ru": "Напишите первый профильный предмет ЕНТ.",
        "kk": "ҰБТ бойынша бірінші бейіндік пәнді жазыңыз.",
        "en": "Please enter your first UNT profile subject.",
    },
    PROFILE_SUBJECT_2: {
        "ru": "Напишите второй профильный предмет ЕНТ.",
        "kk": "ҰБТ бойынша екінші бейіндік пәнді жазыңыз.",
        "en": "Please enter your second UNT profile subject.",
    },
}

COUNTRY_ALIASES: dict[str, set[str]] = {
    "Kazakhstan": {"казахстан", "қазақстан", "kazakhstan", "рк"},
    "China": {"китай", "китая", "кнр", "қытай", "china", "chinese"},
    "Russia": {"россия", "россии", "рф", "ресей", "russia", "russian"},
    "Uzbekistan": {"узбекистан", "узбекистана", "өзбекстан", "uzbekistan"},
    "Kyrgyzstan": {"кыргызстан", "киргизия", "қырғызстан", "kyrgyzstan"},
    "Ukraine": {"украина", "украины", "україна", "ukraine"},
    "Belarus": {"беларусь", "белоруссия", "belarus"},
    "Mongolia": {"монголия", "моңғолия", "mongolia"},
    "India": {"индия", "үндістан", "india"},
    "Turkey": {"турция", "түркия", "turkey", "türkiye"},
}

EDUCATION_LEVEL_ALIASES: dict[str, set[str]] = {
    "school": {"школа", "школы", "школу", "после школы", "11 класс", "мектеп", "school", "high school"},
    "college": {"колледж", "колледжа", "после колледжа", "на базе колледжа", "колледжді", "college", "technical school"},
    "bachelor": {"бакалавр", "бакалавриат", "высшее", "жоғары білім", "bachelor"},
    "master": {"магистр", "магистратура", "master"},
}

LANGUAGE_ALIASES: dict[str, set[str]] = {
    "kk": {"казахский", "казахском", "қазақ", "қазақша", "kazakh"},
    "ru": {"русский", "русском", "орыс", "орысша", "russian"},
    "en": {"английский", "английском", "ағылшын", "english"},
}

PROGRAM_ALIASES: dict[str, set[str]] = {
    "AI": {"ai", "ии", "искусственный интеллект", "artificial intelligence"},
}


def new_admission_state(domain: str, subdomain: str) -> dict[str, Any]:
    return {
        "domain": domain,
        "subdomain": subdomain,
        "slots": {"year": datetime.now().year},
        "required": [],
        "missing": [],
        "status": "collecting",
        "last_requested_slot": None,
    }


def normalize_admission_state(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    domain = str(value.get("domain") or "").strip().lower()
    subdomain = str(value.get("subdomain") or "").strip().lower()
    if not domain or not subdomain:
        return None

    state = new_admission_state(domain, subdomain)
    slots = value.get("slots")
    if isinstance(slots, dict):
        for key, item in slots.items():
            if item is not None and str(item).strip():
                state["slots"][str(key)] = item
    state["required"] = _string_list(value.get("required"))
    state["missing"] = _string_list(value.get("missing"))
    state["status"] = str(value.get("status") or "collecting")
    last_requested_slot = value.get("last_requested_slot")
    state["last_requested_slot"] = str(last_requested_slot) if last_requested_slot else None
    return state


def normalize_admission_profile(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    slots = value.get("slots")
    if not isinstance(slots, dict):
        return None

    normalized_slots: dict[str, Any] = {}
    for key, item in slots.items():
        slot = str(key)
        if slot not in PROFILE_SLOT_KEYS or _is_missing(item):
            continue
        normalized_slots[slot] = item
    if not normalized_slots:
        return None

    profile = {
        "domain": "admissions",
        "status": str(value.get("status") or "active"),
        "slots": normalized_slots,
        "updated_fields": _string_list(value.get("updated_fields")),
    }
    return profile


def active_admission_state(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    state = contextual_admission_state(payload)
    if state and state.get("status") == "awaiting_slots":
        return state
    return None


def contextual_admission_state(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    source = payload or {}
    candidates = [
        source.get("admission_state"),
        (source.get("context") or {}).get("admission_state")
        if isinstance(source.get("context"), dict)
        else None,
        (source.get("metadata") or {}).get("admission_state")
        if isinstance(source.get("metadata"), dict)
        else None,
    ]
    for candidate in candidates:
        state = normalize_admission_state(candidate)
        if state:
            return state
    return None


def contextual_admission_profile(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    source = payload or {}
    candidates = [
        source.get("admission_profile"),
        (source.get("context") or {}).get("admission_profile")
        if isinstance(source.get("context"), dict)
        else None,
        (source.get("metadata") or {}).get("admission_profile")
        if isinstance(source.get("metadata"), dict)
        else None,
    ]
    for candidate in candidates:
        profile = normalize_admission_profile(candidate)
        if profile:
            return profile
    return None


def build_admission_profile(
    *,
    query: str,
    previous_profile: dict[str, Any] | None = None,
    admission_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = normalize_admission_profile(previous_profile) or {
        "domain": "admissions",
        "status": "active",
        "slots": {},
        "updated_fields": [],
    }
    slots = dict(profile.get("slots") or {})
    before = dict(slots)

    extracted = extract_slots(
        query,
        expected_slots=sorted(PROFILE_SLOT_KEYS),
        accept_freeform_program=False,
    )
    extracted_name = _extract_full_name(query)
    if extracted_name:
        extracted["full_name"] = extracted_name
    slots.update(
        {
            key: value
            for key, value in extracted.items()
            if key in PROFILE_SLOT_KEYS and not _is_missing(value)
        }
    )

    state_slots = (admission_state or {}).get("slots")
    if isinstance(state_slots, dict):
        slots.update(
            {
                key: value
                for key, value in state_slots.items()
                if key in PROFILE_SLOT_KEYS and not _is_missing(value)
            }
        )

    updated_fields = sorted(
        key
        for key, value in slots.items()
        if key not in before or before.get(key) != value
    )
    return {
        "domain": "admissions",
        "status": "active",
        "slots": slots,
        "updated_fields": updated_fields,
    }


def extract_slots(
    query: str,
    *,
    expected_slots: list[str] | None = None,
    accept_freeform_program: bool = False,
) -> dict[str, Any]:
    text = str(query or "").strip()
    normalized = _normalize(text)
    if not normalized:
        return {}

    expected = set(expected_slots or [])
    result: dict[str, Any] = {}
    degree = extract_level(text)
    if degree:
        result["degree"] = degree

    profile_agent = ProfileSubjectAgent()
    profile_subject_expected = PROFILE_SUBJECT_1 in expected or PROFILE_SUBJECT_2 in expected
    profile_subject_context = profile_subject_expected or profile_agent.looks_like_request(text)
    if profile_subject_context:
        profile_subjects = profile_agent.extract(text)
        target_slots = [
            slot
            for slot in (PROFILE_SUBJECT_1, PROFILE_SUBJECT_2)
            if slot in expected
        ] or [PROFILE_SUBJECT_1, PROFILE_SUBJECT_2]
        for subject, slot in zip(profile_subjects, target_slots):
            result[slot] = subject

    data = load_admission_data()
    program = extract_program(text, data=data)
    if not program:
        program = _match_alias(normalized, PROGRAM_ALIASES)
    filled_other_expected_slot = any(
        slot in result for slot in expected if slot != "program"
    )
    if (
        not program
        and accept_freeform_program
        and "program" in expected
        and not filled_other_expected_slot
        and _looks_like_freeform_value(text)
    ):
        program = text
    if program:
        result["program"] = program

    citizenship = _match_alias(normalized, COUNTRY_ALIASES)
    if citizenship:
        result["citizenship"] = citizenship

    language = _match_alias(normalized, LANGUAGE_ALIASES)
    if language and ("language" in expected or not profile_subject_context):
        result["language"] = language

    education_level = _match_alias(normalized, EDUCATION_LEVEL_ALIASES)
    if education_level and ("education_level" in expected or not degree):
        result["education_level"] = education_level

    score = _extract_score(text, expected)
    if score is not None:
        result["ent_score"] = score

    year_match = re.search(r"\b(20\d{2})\b", text)
    if year_match:
        result["year"] = int(year_match.group(1))
    return result


def analyze_slots(
    *,
    domain: str,
    subdomain: str,
    query: str,
    previous_state: dict[str, Any] | None = None,
    admission_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    same_pending_dialogue = (
        previous_state
        and previous_state.get("domain") == domain
        and previous_state.get("subdomain") == subdomain
        and previous_state.get("status") == "awaiting_slots"
    )
    state = (
        deepcopy(previous_state)
        if same_pending_dialogue
        else new_admission_state(domain, subdomain)
    )
    if previous_state and not same_pending_dialogue:
        _carry_forward_slots(state, previous_state)
    _carry_forward_profile_slots(state, admission_profile)

    config = SLOT_CONFIG.get(subdomain, {})
    skip_conditionals = subdomain == "international" and _is_direct_international_rule_query(query)
    required = _required_slots_for(subdomain=subdomain, query=query, config=config)
    if same_pending_dialogue:
        for slot in _string_list(state.get("required")):
            if slot not in required:
                required.append(slot)
    if subdomain == "programs":
        profile_agent = ProfileSubjectAgent()
        profile_analysis = profile_agent.analyze(query, slots=state["slots"])
        if profile_analysis.active:
            state["slots"].update(profile_analysis.slots)
            for slot in (PROFILE_SUBJECT_1, PROFILE_SUBJECT_2):
                if slot not in required:
                    required.append(slot)
    for slot in required:
        state["slots"].setdefault(slot, None)
    previous_missing = _string_list(state.get("missing"))
    extracted = extract_slots(
        query,
        expected_slots=previous_missing or required,
        accept_freeform_program=bool(previous_state),
    )
    state["slots"].update(extracted)

    for condition in [] if skip_conditionals else config.get("conditional") or []:
        if _condition_matches(condition.get("when"), state["slots"]):
            for slot in condition.get("required") or []:
                if slot not in required:
                    required.append(slot)
                state["slots"].setdefault(slot, None)

    missing = [slot for slot in required if _is_missing(state["slots"].get(slot))]
    state["required"] = required
    state["missing"] = missing
    state["status"] = "awaiting_slots" if missing else "ready"
    state["last_requested_slot"] = missing[0] if missing else None
    return state


def should_continue_dialogue(query: str, state: dict[str, Any] | None) -> bool:
    if not state or state.get("status") != "awaiting_slots":
        return False
    missing = _string_list(state.get("missing"))
    extracted = extract_slots(
        query,
        expected_slots=missing,
        accept_freeform_program=True,
    )
    return any(slot in extracted for slot in missing)


def build_follow_up(state: dict[str, Any], language: str) -> str:
    missing = _string_list(state.get("missing"))
    if not missing:
        return ""
    slot = missing[0]
    questions = SLOT_QUESTIONS.get(slot) or {}
    return questions.get(language) or questions.get("ru") or f"Please provide {slot}."


def mark_state_completed(state: dict[str, Any]) -> dict[str, Any]:
    completed = deepcopy(state)
    completed["status"] = "completed"
    completed["missing"] = []
    completed["last_requested_slot"] = None
    return completed


def _condition_matches(condition: Any, slots: dict[str, Any]) -> bool:
    if not isinstance(condition, dict):
        return False
    slot = str(condition.get("slot") or "")
    operator = str(condition.get("operator") or "")
    value = slots.get(slot)
    if operator == "is_foreign":
        return bool(value) and value != "Kazakhstan"
    if operator == "equals":
        return value == condition.get("value")
    return False


def _required_slots_for(
    *,
    subdomain: str,
    query: str,
    config: dict[str, Any],
) -> list[str]:
    if subdomain == "international" and _is_direct_international_rule_query(query):
        return []
    if subdomain == "eligibility" and _is_direct_exam_rule_query(query):
        return []
    return list(config.get("required") or [])


def _carry_forward_slots(state: dict[str, Any], previous_state: dict[str, Any]) -> None:
    previous_slots = previous_state.get("slots")
    if not isinstance(previous_slots, dict):
        return
    for slot in CARRY_FORWARD_SLOTS:
        value = previous_slots.get(slot)
        if _is_missing(value) or not _is_missing(state["slots"].get(slot)):
            continue
        state["slots"][slot] = value


def _carry_forward_profile_slots(state: dict[str, Any], profile: dict[str, Any] | None) -> None:
    normalized_profile = normalize_admission_profile(profile)
    if not normalized_profile:
        return
    slots = normalized_profile.get("slots") or {}
    if not isinstance(slots, dict):
        return
    for slot in CARRY_FORWARD_SLOTS | {"ent_score"}:
        value = slots.get(slot)
        if _is_missing(value) or not _is_missing(state["slots"].get(slot)):
            continue
        state["slots"][slot] = value


def _is_direct_international_rule_query(query: str) -> bool:
    normalized = _normalize(query)
    if not normalized:
        return False
    direct_terms = {
        "ент",
        "ұбт",
        "вступительн",
        "экзамен",
        "тест",
        "сдавать",
        "нужно ли",
        "нужен ли",
        "надо ли",
        "правил",
        "услов",
        "документ",
    }
    return any(term in normalized for term in direct_terms)


def _is_direct_exam_rule_query(query: str) -> bool:
    normalized = _normalize(query)
    if not normalized:
        return False
    exam_terms = {"ент", "ұбт", "вступительн", "экзамен", "тест", "сдавать"}
    requirement_terms = {"нужно ли", "нужен ли", "надо ли", "должен ли", "обязательно", "требуется"}
    return any(term in normalized for term in exam_terms) and (
        any(term in normalized for term in requirement_terms)
        or "?" in str(query or "")
    )


def _extract_score(text: str, expected: set[str]) -> int | None:
    normalized = _normalize(text)
    score_context = "ent_score" in expected or any(
        marker in normalized for marker in {"ент", "ұбт", "балл", "score", "point"}
    )
    if not score_context:
        return None
    for match in re.findall(r"\b\d{1,3}\b", text):
        value = int(match)
        if 0 <= value <= 200 and not 2000 <= value <= 2099:
            return value
    return None


def _extract_full_name(text: str) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    patterns = [
        (
            r"\bменя зовут\s+([A-Za-zА-Яа-яЁёӘәІіҢңҒғҮүҰұҚқӨөҺһ][A-Za-zА-Яа-яЁёӘәІіҢңҒғҮүҰұҚқӨөҺһ' -]{1,80})",
            re.IGNORECASE,
        ),
        (
            r"\bмо[её]\s+имя\s+([A-Za-zА-Яа-яЁёӘәІіҢңҒғҮүҰұҚқӨөҺһ][A-Za-zА-Яа-яЁёӘәІіҢңҒғҮүҰұҚқӨөҺһ' -]{1,80})",
            re.IGNORECASE,
        ),
        (
            r"\bя\s+([A-ZА-ЯЁӘІҢҒҮҰҚӨҺ][A-Za-zА-Яа-яЁёӘәІіҢңҒғҮүҰұҚқӨөҺһ' -]{2,80})",
            0,
        ),
    ]
    for pattern, flags in patterns:
        match = re.search(pattern, value, flags=flags)
        if not match:
            continue
        name = _clean_full_name(match.group(1))
        if name:
            return name
    return None


def _clean_full_name(value: str) -> str | None:
    name = re.split(r"[,.;!?]|\s+(?:и|из|с|хочу|планирую|интересует|поступ)", value.strip(), maxsplit=1)[0]
    name = re.sub(r"\s+", " ", name).strip(" -'")
    if len(name) < 2 or len(name) > 80:
        return None
    lowered = name.casefold()
    blocked = {"гражданин", "гражданка", "из", "после", "бакалавриат", "магистратура"}
    if lowered in blocked:
        return None
    return name


def _match_alias(normalized: str, aliases: dict[str, set[str]]) -> str | None:
    for canonical, variants in aliases.items():
        if any(_contains_term(normalized, variant) for variant in variants):
            return canonical
    return None


def _contains_term(text: str, term: str) -> bool:
    normalized_term = _normalize(term)
    return bool(
        re.search(
            rf"(?<![\w]){re.escape(normalized_term)}(?![\w])",
            text,
            flags=re.UNICODE,
        )
    )


def _looks_like_freeform_value(value: str) -> bool:
    text = value.strip()
    if not text or len(text) > 100 or text.endswith("?"):
        return False
    return len(text.split()) <= 8


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())
