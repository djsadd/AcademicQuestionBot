"""Admission agent backed by structured admission tools."""
from __future__ import annotations

import re
from typing import Any, Dict

from ..db import admission_applications
from ..langchain.llm import llm_client
from ..langchain.tools.admission_info import (
    build_minimal_admission_overview,
    build_context_entries,
    detect_requested_tool,
    extract_level,
    extract_program_with_history,
    extract_programs_with_history,
    format_admission_tool_result,
    get_admission_address,
    get_academic_mobility,
    get_academic_cooperation,
    get_admission_contacts,
    get_admission_exams,
    get_available_programs,
    get_current_prices,
    get_foreign_admission_info,
    get_management,
    get_passing_scores,
    get_required_documents,
    get_scholarships,
    get_study_durations,
    load_admission_data,
    normalize_language,
)
from .base import AgentResult, BaseAgent


class AdmissionAgent(BaseAgent):
    """Answers about enrollment rules and admission requirements."""

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        query = str(payload.get("message") or payload.get("question") or "").strip()
        language = normalize_language(payload.get("language"))
        application_result = _maybe_handle_application_flow(payload, query, language)
        if application_result is not None:
            return application_result

        data = load_admission_data()
        level = payload.get("level") or extract_level(query)
        history = payload.get("history")
        program = payload.get("program") or extract_program_with_history(query, history=history, data=data)
        programs = extract_programs_with_history(query, history=history, data=data)
        requested_tool = detect_requested_tool(query)
        force_ai_answer = _should_force_grant_ai_answer(query)

        if requested_tool == "programs":
            result = get_available_programs(level=level, language=language)
        elif requested_tool == "prices":
            result = get_current_prices(program=program, level=level, language=language)
        elif requested_tool == "passing_scores":
            result = get_passing_scores(program=program, level=level, language=language)
        elif requested_tool == "documents":
            result = get_required_documents(level=level, language=language)
        elif requested_tool == "address":
            result = get_admission_address(language=language)
        elif requested_tool == "contacts":
            result = get_admission_contacts(language=language)
        elif requested_tool == "durations":
            result = get_study_durations(program=program, level=level, language=language)
        elif requested_tool == "academic_mobility":
            result = get_academic_mobility(program=program, query=query, language=language)
        elif requested_tool == "academic_cooperation":
            result = get_academic_cooperation(program=program, query=query, language=language)
        elif requested_tool == "scholarships":
            result = get_scholarships(language=language, query=query)
        elif requested_tool == "admission_exams":
            result = get_admission_exams(language=language, query=query)
        elif requested_tool == "foreign_admission":
            result = get_foreign_admission_info(language=language)
        elif requested_tool == "management":
            result = get_management(language=language)
        else:
            if force_ai_answer:
                result = get_scholarships(language=language, query=query)
            else:
                result = _build_overview(program=program, programs=programs, level=level, language=language)

        context_entries = build_context_entries(result, language=language)
        fallback_answer = format_admission_tool_result(result, language=language)
        answer = _render_admission_answer(
            query=query,
            history=payload.get("history"),
            result=result,
            language=language,
            fallback_answer=fallback_answer,
            grant_only=force_ai_answer,
        )
        return AgentResult(
            answer=answer,
            intent="admission",
            tool_data=result,
            context=context_entries,
            direct_response=llm_client.is_configured,
        )


def _build_overview(
    *,
    program: str | None,
    programs: list[str] | None,
    level: str | None,
    language: str,
) -> Dict[str, Any]:
    requested_programs = [item for item in (programs or []) if item]
    if program and program not in requested_programs:
        requested_programs.insert(0, program)
    return build_minimal_admission_overview(
        programs=requested_programs,
        level=level,
        language=language,
    )


def _should_force_grant_ai_answer(query: str) -> bool:
    normalized = _normalize_text(query)
    if not normalized:
        return False
    terms = {"грант", "гранты", "госгрант", "гос грант", "grant", "grants"}
    return any(term in normalized for term in terms)


from datetime import datetime


def _generate_grant_ai_answer(
    *,
    query: str,
    history: Any,
    context_entries: list[dict[str, Any]],
    language: str,
) -> str:
    if not llm_client.is_configured:
        return ""

    history_text = _format_llm_history(history)
    context_text = _format_llm_context(context_entries)
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    prompt = (
"Ты ИИ-агент приёмной комиссии университета Туран-Астана (Астана, Казахстан).\n\n"

"ТИПЫ АБИТУРИЕНТОВ:\n"
"— граждане Казахстана\n"
"— иностранные абитуриенты (РФ, Украина, Беларусь, Узбекистан, Кыргызстан, Китай, Монголия и др.)\n\n"

"ОСНОВНАЯ ЦЕЛЬ:\n"
"Давать понятные, точные и полезные ответы о поступлении, опираясь ТОЛЬКО на предоставленный контекст.\n\n"

"━━━━━━━━━━━━━━━━━━\n"
"ЖЁСТКИЕ ПРАВИЛА\n"
"━━━━━━━━━━━━━━━━━━\n"
"1. Используй ТОЛЬКО предоставленный контекст.\n"
"2. Не придумывай факты, экзамены, условия или требования.\n"
"3. Если информация есть в контексте — отвечай строго по ней.\n"
"4. Не используй фразы типа: 'нет информации', 'неизвестно', 'не найдено'.\n"
"5. Не оставляй вопрос без ответа.\n\n"

"━━━━━━━━━━━━━━━━━━\n"
"ЛОГИКА ОПРЕДЕЛЕНИЯ\n"
"━━━━━━━━━━━━━━━━━━\n"
"— Если указана страна, отличная от Казахстана → это иностранный абитуриент\n"
"— Если страна не указана → считать гражданином Казахстана\n\n"

"━━━━━━━━━━━━━━━━━━\n"
"ПРАВИЛА ОТВЕТОВ\n"
"━━━━━━━━━━━━━━━━━━\n"

"1. Вопросы о поступлении:\n"
"   Граждане Казахстана:\n"
"   — если в контексте есть ЕНТ → используй это\n"
"   — если нет → дай общий корректный ответ: поступление обычно проходит через ЕНТ\n\n"

"   Иностранные абитуриенты:\n"
"   — НЕ утверждай, что ЕНТ обязателен\n"
"   — используй только контекст\n"
"   — если данных нет → опиши, что условия поступления для иностранных студентов могут отличаться\n\n"

"2. Вопросы о грантах:\n"
"   — объясняй только то, что есть в контексте\n"
"   — можно кратко упомянуть виды грантов, если они присутствуют в данных\n\n"

"3. Если информации недостаточно:\n"
"   — НЕ говори, что ничего нет\n"
"   — дай наиболее вероятный или общий корректный ответ на основе типичной практики\n"
"   — при необходимости в конце можно добавить мягкую рекомендацию уточнить детали у приёмной комиссии\n"
"   — НЕ делай это обязательной фразой\n\n"

"━━━━━━━━━━━━━━━━━━\n"
"СТИЛЬ ПОВЕДЕНИЯ\n"
"━━━━━━━━━━━━━━━━━━\n"
"— Отвечай прямо, по делу\n"
"— Не переспрашивай, если программа уже есть в истории\n"
"— Не уходи в канцелярит\n"
"— Не перекладывай ответ на пользователя\n\n"

"━━━━━━━━━━━━━━━━━━\n"
"ЗАПРЕЩЕНО\n"
"━━━━━━━━━━━━━━━━━━\n"
"— Придумывать условия поступления\n"
"— Утверждать про ЕНТ для иностранцев без контекста\n"
"— Использовать отказ вместо ответа\n\n"

"━━━━━━━━━━━━━━━━━━\n"
"ФОРМАТ ОТВЕТА\n"
"━━━━━━━━━━━━━━━━━━\n"
"— Коротко и понятно\n"
"— Можно списки\n"
"— Без Markdown\n\n"

f"Язык ответа: {language}\n"
f"Вопрос пользователя: {query}\n\n"
f"История:\n{history_text}\n\n"
f"Контекст:\n{context_text}\n\n"
f"Дата и время: {now}\n"
)

    messages = [
        {"role": "system", "content": "Ты помощник приёмной комиссии. Отвечай строго по правилам."},
        {"role": "user", "content": prompt},
    ]

    return llm_client.chat(messages).strip()


def _should_use_admission_ai_answer(*, tool_result: dict[str, Any], fallback_answer: str) -> bool:
    return llm_client.is_configured


def _generate_admission_ai_answer(
    *,
    query: str,
    history: Any,
    context_entries: list[dict[str, Any]],
    language: str,
    grant_only: bool = False,
) -> str:
    if not llm_client.is_configured:
        return ""

    prompt = _build_admission_ai_prompt(
        query=query,
        history=history,
        context_entries=context_entries,
        language=language,
        grant_only=grant_only,
    )
    messages = [
        {"role": "system", "content": "You are an admissions assistant. Answer only from the provided context."},
        {"role": "user", "content": prompt},
    ]
    return llm_client.chat(messages).strip()


def _render_admission_answer(
    *,
    query: str,
    history: Any,
    result: dict[str, Any],
    language: str,
    fallback_answer: str | None = None,
    grant_only: bool = False,
) -> str:
    context_entries = build_context_entries(result, language=language)
    resolved_fallback = fallback_answer or format_admission_tool_result(result, language=language)
    if _should_skip_admission_llm(result):
        return resolved_fallback
    if not llm_client.is_configured:
        return _grant_ai_unavailable_message(language) if grant_only else resolved_fallback

    ai_answer = _generate_admission_ai_answer(
        query=query,
        history=history,
        context_entries=context_entries,
        language=language,
        grant_only=grant_only,
    )
    if ai_answer:
        return ai_answer
    return _grant_ai_unavailable_message(language) if grant_only else resolved_fallback


def _should_skip_admission_llm(result: dict[str, Any]) -> bool:
    return str(result.get("tool") or "") in {"contacts", "address"}


def _build_admission_ai_prompt(
    *,
    query: str,
    history: Any,
    context_entries: list[dict[str, Any]],
    language: str,
    grant_only: bool = False,
) -> str:
    history_text = _format_llm_history(history)
    context_text = _format_llm_context(context_entries)
    clarification_contacts = format_admission_tool_result(
        get_admission_contacts(language=language),
        language=language,
    )
    scope = (
        "The question is specifically about scholarships or grants."
        if grant_only
        else "The question is about admission."
    )
    return (
        "Write a concise and natural reply for a prospective student.\n"
        f"{scope}\n"
        "Use only the context below.\n"
        "Strict rule for missing information:\n"
        "- If the context does not contain enough information to answer the user's question, do not invent facts.\n"
        "- Never write phrases like 'there is no information', 'not specified', 'no data', 'I do not know', or similar wording.\n"
        "- In that case, immediately route the user to the admissions office: give the admissions contacts below and say that they can clarify this question there.\n"
        "- The final answer must sound like a referral to the admissions office, not like a refusal or a negative answer.\n"
        "Do not copy template headings. Do not reproduce the tool output mechanically.\n"
        "For short direct questions, start with a direct answer in the first sentence.\n"
        "Example style: 'Да, для этой программы нужен ЕНТ.' or 'Нет, здесь нужно комплексное тестирование.'\n"
        "If the question is broad, answer the main point first and then suggest what to clarify for a more exact answer.\n"
        "Response format: short HTML fragment without Markdown.\n\n"
        "If the user question is ambiguous or missing key details (program, level, format):"
        " Ask a short clarification question instead of answering."
        "- Do not guess."
        "- Do not generate a full answer."
        f"Response language: {language}\n"
        f"User question: {query}\n"
        f"History:\n{history_text}\n\n"
        f"Context:\n{context_text}\n\n"
        f"Admissions contacts for clarification:\n{clarification_contacts}"
    )


def _format_llm_history(history: Any) -> str:
    if not isinstance(history, list) or not history:
        return "- нет истории"

    lines: list[str] = []
    for item in history[-8:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user").strip().lower()
        if role == "bot":
            role = "assistant"
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"- {role}: {content[:300]}")
    return "\n".join(lines) if lines else "- нет истории"


def _format_llm_context(context_entries: list[dict[str, Any]]) -> str:
    if not context_entries:
        return "- контекст отсутствует"

    lines: list[str] = []
    for item in context_entries[:12]:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"- {content[:4000]}")
    return "\n".join(lines) if lines else "- контекст отсутствует"


def _grant_ai_unavailable_message(language: str) -> str:
    messages = {
        "ru": "Не удалось сформировать ответ через ИИ. Попробуйте повторить запрос.",
        "kk": "ЖИ арқылы жауап құрастыру мүмкін болмады. Сұрауды қайта жіберіп көріңіз.",
        "en": "Could not generate an AI answer. Please try again.",
    }
    return messages.get(language, messages["ru"])


APP_TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "overview_title": "Информация приемной комиссии:",
        "already_saved": "Заявка уже была сформирована в этом диалоге. Если нужна новая, начните новый чат и напишите, что хотите подать заявку на поступление.",
        "collecting_prefix": "Принято. Продолжим оформление заявки.",
        "draft_ready": "Черновик заявки готов.",
        "draft_confirm": 'Если всё верно, напишите "да". Если хотите отменить, напишите "нет".',
        "cancelled": "Оформление заявки отменено. Если захотите начать заново, напишите, что хотите подать заявку на поступление.",
        "confirm_required": 'Проверьте данные и напишите "да" для сохранения заявки или "нет" для отмены.',
        "saved": "Заявка сохранена в базе.",
        "application_number": "Номер заявки: {value}",
        "summary_title": "Данные заявки:",
    },
    "kk": {
        "overview_title": "Қабылдау комиссиясы туралы ақпарат:",
        "already_saved": "Бұл диалогта өтініш бұрыннан жасалған. Егер жаңа өтініш керек болса, жаңа чат бастап, оқуға түсуге өтініш бергіңіз келетінін жазыңыз.",
        "collecting_prefix": "Қабылданды. Өтінішті рәсімдеуді жалғастырамыз.",
        "draft_ready": "Өтініштің қара жобасы дайын.",
        "draft_confirm": 'Барлығы дұрыс болса, "да" деп жазыңыз. Болдырмау үшін "нет" деп жазыңыз.',
        "cancelled": "Өтінішті рәсімдеу тоқтатылды. Қайта бастау үшін оқуға түсуге өтініш бергіңіз келетінін жазыңыз.",
        "confirm_required": 'Өтінішті сақтау үшін "да", болдырмау үшін "нет" деп жазыңыз.',
        "saved": "Өтініш базаға сақталды.",
        "application_number": "Өтініш нөмірі: {value}",
        "summary_title": "Өтініш деректері:",
    },
    "en": {
        "overview_title": "Admissions information:",
        "already_saved": "An application has already been created in this dialog. If you need a new one, start a new chat and say that you want to submit an admission application.",
        "collecting_prefix": "Accepted. Let's continue the application.",
        "draft_ready": "The application draft is ready.",
        "draft_confirm": 'If everything is correct, reply "yes". If you want to cancel, reply "no".',
        "cancelled": "The application flow has been cancelled. If you want to start over, say that you want to submit an admission application.",
        "confirm_required": 'Check the data and reply "yes" to save the application or "no" to cancel.',
        "saved": "The application has been saved.",
        "application_number": "Application number: {value}",
        "summary_title": "Application data:",
    },
}
APPLICATION_FIELD_ORDER = [
    "full_name",
    "iin",
    "birth_date",
    "phone",
    "email",
    "education_level",
    "program",
    "study_language",
    "study_format",
    "comment",
]

APPLICATION_FIELD_TEXTS: dict[str, dict[str, dict[str, str]]] = {
    "full_name": {
        "ru": {"label": "ФИО", "question": "Укажите ФИО полностью."},
        "kk": {"label": "Аты-жөні", "question": "Толық аты-жөніңізді көрсетіңіз."},
        "en": {"label": "Full name", "question": "Please provide your full name."},
    },
    "iin": {
        "ru": {"label": "ИИН", "question": "Укажите ИИН (12 цифр)."},
        "kk": {"label": "ЖСН", "question": "ЖСН-ді көрсетіңіз (12 сан)."},
        "en": {"label": "IIN", "question": "Please provide your IIN (12 digits)."},
    },
    "birth_date": {
        "ru": {"label": "Дата рождения", "question": "Укажите дату рождения в формате ДД.ММ.ГГГГ."},
        "kk": {"label": "Туған күні", "question": "Туған күніңізді КК.АА.ЖЖЖЖ форматында көрсетіңіз."},
        "en": {"label": "Birth date", "question": "Please provide your birth date in DD.MM.YYYY format."},
    },
    "phone": {
        "ru": {"label": "Телефон", "question": "Укажите номер телефона для связи."},
        "kk": {"label": "Телефон", "question": "Байланыс телефон нөмірін көрсетіңіз."},
        "en": {"label": "Phone", "question": "Please provide your phone number."},
    },
    "email": {
        "ru": {"label": "Email", "question": "Укажите email."},
        "kk": {"label": "Email", "question": "Email көрсетіңіз."},
        "en": {"label": "Email", "question": "Please provide your email."},
    },
    "education_level": {
        "ru": {"label": "Уровень обучения", "question": "На какой уровень хотите поступать: бакалавриат, магистратура, докторантура или второе высшее?"},
        "kk": {"label": "Оқу деңгейі", "question": "Қай деңгейге түскіңіз келеді: бакалавриат, магистратура, докторантура немесе екінші жоғары?"},
        "en": {"label": "Study level", "question": "Which level are you applying for: bachelor, master, doctorate, or second higher education?"},
    },
    "program": {
        "ru": {"label": "Образовательная программа", "question": "На какую образовательную программу хотите подать заявку?"},
        "kk": {"label": "Білім беру бағдарламасы", "question": "Қай білім беру бағдарламасына өтініш бергіңіз келеді?"},
        "en": {"label": "Program", "question": "Which academic program would you like to apply for?"},
    },
    "study_language": {
        "ru": {"label": "Язык обучения", "question": "Укажите предпочитаемый язык обучения."},
        "kk": {"label": "Оқу тілі", "question": "Қалаған оқу тілін көрсетіңіз."},
        "en": {"label": "Study language", "question": "Please provide your preferred study language."},
    },
    "study_format": {
        "ru": {"label": "Форма обучения", "question": "Укажите форму обучения, если знаете: очная, дистанционная и т.д."},
        "kk": {"label": "Оқу форматы", "question": "Білсеңіз, оқу форматын көрсетіңіз: күндізгі, қашықтан және т.б."},
        "en": {"label": "Study format", "question": "If you know it, please specify the study format: full-time, online, etc."},
    },
    "comment": {
        "ru": {"label": "Комментарий", "question": 'Если есть комментарий или вопрос для приемной комиссии, напишите его. Если нет, напишите "нет".'},
        "kk": {"label": "Түсініктеме", "question": 'Егер қабылдау комиссиясына арналған түсініктеме немесе сұрақ болса, жазыңыз. Егер жоқ болса, "жоқ" деп жазыңыз.'},
        "en": {"label": "Comment", "question": 'If you have a comment or question for the admissions office, write it. If not, write "no".'},
    },
}

APPLICATION_TRIGGER_TERMS = {
    "подать заявку",
    "оставить заявку",
    "создать заявку",
    "оформить заявку",
    "заявка на поступление",
    "хочу поступить",
    "хочу подать документы",
    "хочу подать заявку",
    "поступить к вам",
    "өтініш беру",
    "өтініш қалдыру",
    "оқуға түскім келеді",
    "құжат тапсырғым келеді",
    "submit application",
    "apply for admission",
    "i want to apply",
    "i want to enroll",
}

CONFIRM_TERMS = {"да", "подтверждаю", "подтвердить", "верно", "согласен", "ок", "ok", "yes", "иә", "ия", "растау"}
CANCEL_TERMS = {"нет", "отмена", "отменить", "не подтверждаю", "stop", "cancel", "no", "жоқ"}


def _maybe_handle_application_flow(payload: Dict[str, Any], query: str, language: str) -> AgentResult | None:
    history = payload.get("history")
    if not _should_run_application_flow(query, history):
        return None

    state = _reconstruct_application_state(history, query)

    if state["saved"]:
        result = {
            "status": "already_saved",
            "tool": "application_form",
            "language": language,
            "answer": _app_text(language, "already_saved"),
        }
        return AgentResult(
            answer=_render_admission_answer(
                query=query,
                history=history,
                result=result,
                language=language,
                fallback_answer=result["answer"],
            ),
            intent="admission",
            tool_data=result,
            context=build_context_entries(result, language=language),
            direct_response=True,
        )

    pending_key = state["pending_field"]
    if pending_key:
        field_config = _field_config(pending_key, language)
        answer = (
            f"{_app_text(language, 'collecting_prefix')}\n"
            f"{field_config['question']}"
        )
        result = {
            "status": "collecting",
            "tool": "application_form",
            "language": language,
            "stage": pending_key,
            "collected_fields": state["collected"],
            "answer": answer,
        }
        return AgentResult(
            answer=_render_admission_answer(
                query=query,
                history=history,
                result=result,
                language=language,
                fallback_answer=answer,
            ),
            intent="admission",
            tool_data=result,
            context=build_context_entries(result, language=language),
            direct_response=True,
        )

    if not state["awaiting_confirmation"]:
        summary = _format_application_summary(state["collected"], language)
        answer = (
            f"{_app_text(language, 'draft_ready')}\n"
            f"{summary}\n\n"
            f"{_app_text(language, 'draft_confirm')}"
        )
        result = {
            "status": "awaiting_confirmation",
            "tool": "application_form",
            "language": language,
            "collected_fields": state["collected"],
            "answer": answer,
        }
        return AgentResult(
            answer=_render_admission_answer(
                query=query,
                history=history,
                result=result,
                language=language,
                fallback_answer=answer,
            ),
            intent="admission",
            tool_data=result,
            context=build_context_entries(result, language=language),
            direct_response=True,
        )

    normalized_query = _normalize_text(query)
    if normalized_query in CANCEL_TERMS:
        answer = _app_text(language, "cancelled")
        result = {
            "status": "cancelled",
            "tool": "application_form",
            "language": language,
            "collected_fields": state["collected"],
            "answer": answer,
        }
        return AgentResult(
            answer=_render_admission_answer(
                query=query,
                history=history,
                result=result,
                language=language,
                fallback_answer=answer,
            ),
            intent="admission",
            tool_data=result,
            context=build_context_entries(result, language=language),
            direct_response=True,
        )

    if normalized_query not in CONFIRM_TERMS:
        answer = _app_text(language, "confirm_required")
        result = {
            "status": "awaiting_confirmation",
            "tool": "application_form",
            "language": language,
            "collected_fields": state["collected"],
            "answer": answer,
        }
        return AgentResult(
            answer=_render_admission_answer(
                query=query,
                history=history,
                result=result,
                language=language,
                fallback_answer=answer,
            ),
            intent="admission",
            tool_data=result,
            context=build_context_entries(result, language=language),
            direct_response=True,
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
        f"{_app_text(language, 'saved')}\n"
        f"{_app_text(language, 'application_number', value=created['id'])}\n"
        f"{_format_application_summary(state['collected'], language)}"
    )
    result = {
        "status": "saved",
        "tool": "application_form",
        "language": language,
        "application_id": created["id"],
        "created_at": created.get("created_at"),
        "collected_fields": state["collected"],
        "answer": answer,
    }
    return AgentResult(
        answer=_render_admission_answer(
            query=query,
            history=history,
            result=result,
            language=language,
            fallback_answer=answer,
        ),
        intent="admission",
        tool_data=result,
        context=build_context_entries(result, language=language),
        direct_response=True,
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
        if role == "assistant" and any(marker in normalized_content for marker in _application_history_markers("collecting")):
            return True
        if role == "assistant" and any(marker in normalized_content for marker in _application_history_markers("draft_ready")):
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
    if current_query.strip() and not (
        messages
        and messages[-1].get("role") == "user"
        and messages[-1].get("content") == current_query.strip()
    ):
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
            if any(marker in normalized for marker in _application_history_markers("saved")):
                saved = True
            if any(marker in normalized for marker in _application_history_markers("draft_ready")):
                awaiting_confirmation = True
            continue

        if current_field_index == 0 and any(term in normalized for term in APPLICATION_TRIGGER_TERMS):
            continue

        if awaiting_confirmation:
            continue

        if current_field_index >= len(APPLICATION_FIELD_ORDER):
            continue

        field_key = APPLICATION_FIELD_ORDER[current_field_index]
        value = _extract_field_value(field_key, content)
        if value is None:
            continue
        collected[field_key] = value
        current_field_index += 1

    pending_field = None
    if not awaiting_confirmation and current_field_index < len(APPLICATION_FIELD_ORDER):
        pending_field = APPLICATION_FIELD_ORDER[current_field_index]

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
        return "" if normalized in {"нет", "без комментария", "none", "no", "жоқ", "-"} else text
    return text


def _format_application_summary(collected: dict[str, str], language: str) -> str:
    level_map = {
        "ru": {
            "bachelor": "бакалавриат",
            "master": "магистратура",
            "doctorate": "докторантура",
            "second_higher": "второе высшее",
        },
        "kk": {
            "bachelor": "бакалавриат",
            "master": "магистратура",
            "doctorate": "докторантура",
            "second_higher": "екінші жоғары",
        },
        "en": {
            "bachelor": "bachelor",
            "master": "master",
            "doctorate": "doctorate",
            "second_higher": "second higher education",
        },
    }
    lines = [_app_text(language, "summary_title")]
    for key in APPLICATION_FIELD_ORDER:
        field = _field_config(key, language)
        value = collected.get(key)
        if value is None or value == "":
            continue
        display_value = level_map.get(language, level_map["ru"]).get(value, value) if key == "education_level" else value
        lines.append(f"- {field['label']}: {display_value}")
    return "\n".join(lines)


def _field_config(field_key: str, language: str) -> dict[str, str]:
    localized = APPLICATION_FIELD_TEXTS.get(field_key, {})
    return localized.get(language) or localized.get("ru") or {"label": field_key, "question": field_key}


def _app_text(language: str, key: str, **kwargs: Any) -> str:
    template = (APP_TEXTS.get(language) or APP_TEXTS["ru"]).get(key) or APP_TEXTS["ru"][key]
    return template.format(**kwargs)


def _application_history_markers(kind: str) -> set[str]:
    keys = {
        "collecting": {"collecting_prefix"},
        "draft_ready": {"draft_ready"},
        "saved": {"saved"},
    }.get(kind, set())
    values: set[str] = set()
    for language in APP_TEXTS:
        for key in keys:
            values.add(_normalize_text(_app_text(language, key)))
    return values


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
