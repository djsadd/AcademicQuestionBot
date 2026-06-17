"""Admission classifier and structured request orchestrator."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any, Dict

from ..langchain.llm import llm_client
from ..langchain.tools.admission_info import (
    build_context_entries,
    build_minimal_admission_overview,
    extract_level,
    extract_program_with_history,
    extract_programs_with_history,
    format_admission_tool_result,
    get_admission_address,
    get_admission_contacts,
    get_admission_exams,
    get_available_programs,
    get_current_prices,
    get_foreign_admission_info,
    get_passing_scores,
    get_required_documents,
    get_scholarships,
    get_student_house,
    get_study_durations,
    load_admission_data,
)
from .base import AgentResult, BaseAgent
from .admission_dialogue import (
    active_admission_state,
    analyze_slots,
    build_admission_profile,
    build_follow_up,
    contextual_admission_profile,
    contextual_admission_state,
    mark_state_completed,
    should_continue_dialogue,
)
from .profile_subjects import PROFILE_SUBJECT_1, PROFILE_SUBJECT_2, ProfileSubjectAgent


ADMISSION_HISTORY_LIMIT = 8
ADMISSION_HISTORY_CHARS = 500
ADMISSION_RENDER_CONTEXT_LIMIT = 6
ADMISSION_RENDER_CONTEXT_CHARS = 1200
ADMISSION_RENDER_TOOL_CHARS = 3500

ADMISSION_SUBDOMAINS = {
    "eligibility",
    "programs",
    "tuition",
    "international",
    "scholarships",
    "competition",
    "deadlines",
    "documents",
}
APPLICANT_SUBDOMAINS = {
    "application_status",
    "documents",
    "payments",
    "exams",
    "notifications",
}
GENERAL_INFO_SUBDOMAINS = {"contacts", "address", "student_house", "events", "faq"}


@dataclass(frozen=True)
class AdmissionIntent:
    domain: str
    subdomain: str
    requires_auth: bool
    confidence: float = 0.75
    source: str = "rules"


@dataclass(frozen=True)
class OrchestratorDecision:
    api: str
    tool: str
    requires_auth: bool = False
    executed: bool = True


class AdmissionAgent(BaseAgent):
    """Classifies admission requests and dispatches them to structured data tools."""

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        response = run_admission_pipeline(
            query=_payload_query(payload),
            history=payload.get("history"),
            language=payload.get("language"),
            payload=payload,
        )
        return AgentResult(
            answer=response["answer"],
            intent="admission",
            tool_data=response["tool_data"],
            context=response["context"],
            direct_response=True,
            classification=response["classification"],
            orchestration=response["orchestration"],
            admission_state=response["admission_state"],
            admission_profile=response["admission_profile"],
            llm=response["llm"],
        )


def run_admission_pipeline(
    *,
    query: str,
    history: Any = None,
    language: Any = None,
    payload: Dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify the request, select a structured source in code, and format the result."""
    resolved_query = str(query or "").strip()
    resolved_language = detect_question_language(resolved_query, fallback=language)
    request_payload = payload or {}
    active_state = active_admission_state(request_payload)
    context_state = contextual_admission_state(request_payload)
    context_profile = contextual_admission_profile(request_payload)
    classifier = AdmissionIntentClassifier()
    if should_continue_dialogue(resolved_query, active_state):
        classification = AdmissionIntent(
            domain=str(active_state["domain"]),
            subdomain=str(active_state["subdomain"]),
            requires_auth=False,
            confidence=1.0,
            source="dialogue_state",
        )
    else:
        classification = classifier.classify(
            resolved_query,
            history=history,
            authenticated=_is_authenticated_payload(request_payload),
        )

    slot_state = analyze_slots(
        domain=classification.domain,
        subdomain=classification.subdomain,
        query=resolved_query,
        previous_state=active_state if classification.source == "dialogue_state" else context_state,
        admission_profile=context_profile,
    )
    admission_profile = build_admission_profile(
        query=resolved_query,
        previous_profile=context_profile,
        admission_state=slot_state,
    )
    if slot_state["missing"]:
        follow_up = build_follow_up(slot_state, resolved_language)
        decision = OrchestratorDecision(
            api="dialogue_manager",
            tool="follow_up",
            executed=False,
        )
        tool_result = {
            "status": "needs_clarification",
            "tool": "dialogue_manager",
            "answer": follow_up,
            "missing_slots": slot_state["missing"],
            "required_slots": slot_state["required"],
            "slots": slot_state["slots"],
        }
        return _build_pipeline_response(
            query=resolved_query,
            history=history,
            language=resolved_language,
            classification=classification,
            decision=decision,
            tool_result=tool_result,
            admission_state=slot_state,
            admission_profile=admission_profile,
            context=[],
            mode="follow_up",
        )

    orchestrator = AdmissionRequestOrchestrator()
    decision, tool_result = orchestrator.dispatch(
        classification=classification,
        query=resolved_query,
        history=history,
        language=resolved_language,
        authenticated=_is_authenticated_payload(request_payload),
        slots=slot_state["slots"],
    )
    tool_result["request_slots"] = slot_state["slots"]
    completed_state = mark_state_completed(slot_state)
    completed_profile = build_admission_profile(
        query=resolved_query,
        previous_profile=admission_profile,
        admission_state=completed_state,
    )
    context = build_context_entries(tool_result, language=resolved_language)
    return _build_pipeline_response(
        query=resolved_query,
        history=history,
        language=resolved_language,
        classification=classification,
        decision=decision,
        tool_result=tool_result,
        admission_state=completed_state,
        admission_profile=completed_profile,
        context=context,
        mode="answer",
    )


def _build_pipeline_response(
    *,
    query: str,
    history: Any,
    language: str,
    classification: AdmissionIntent,
    decision: OrchestratorDecision,
    tool_result: dict[str, Any],
    admission_state: dict[str, Any],
    admission_profile: dict[str, Any],
    context: list[dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    fallback_answer = str(tool_result.get("answer") or "").strip() or format_admission_tool_result(
        tool_result,
        language=language,
    )
    rendered_answer, render_attempted = _render_admission_answer_with_llm(
        query=query,
        history=history,
        language=language,
        classification=classification,
        decision=decision,
        tool_result=tool_result,
        admission_state=admission_state,
        admission_profile=admission_profile,
        context=context,
        fallback_answer=fallback_answer,
        mode=mode,
    )
    answer = rendered_answer or fallback_answer
    llm_stages = []
    if classification.source == "llm":
        llm_stages.append("classification")
    if rendered_answer:
        llm_stages.append("response_render")
    return {
        "query": query,
        "language": language,
        "answer": answer,
        "classification": asdict(classification),
        "orchestration": asdict(decision),
        "tool_data": tool_result,
        "context": context,
        "admission_state": admission_state,
        "admission_profile": admission_profile,
        "llm": {
            "used": bool(llm_stages),
            "model": getattr(llm_client, "model", None) if llm_stages else None,
            "error": getattr(llm_client, "last_error", None) if render_attempted and not rendered_answer else None,
            "raw_request": {
                "stages": llm_stages,
                "render_mode": mode,
                "fallback_used": not bool(rendered_answer),
            }
            if llm_stages or render_attempted
            else None,
        },
    }


def _render_admission_answer_with_llm(
    *,
    query: str,
    history: Any,
    language: str,
    classification: AdmissionIntent,
    decision: OrchestratorDecision,
    tool_result: dict[str, Any],
    admission_state: dict[str, Any],
    admission_profile: dict[str, Any],
    context: list[dict[str, Any]],
    fallback_answer: str,
    mode: str,
) -> tuple[str, bool]:
    if not llm_client.is_configured:
        return "", False
    if mode == "follow_up" and any(
        slot in {PROFILE_SUBJECT_1, PROFILE_SUBJECT_2}
        for slot in tool_result.get("missing_slots") or []
    ):
        return "", False

    prompt = _build_admission_render_prompt(
        query=query,
        history=history,
        language=language,
        classification=classification,
        decision=decision,
        tool_result=tool_result,
        admission_state=admission_state,
        admission_profile=admission_profile,
        context=context,
        fallback_answer=fallback_answer,
        mode=mode,
    )
    max_tokens = 180 if mode == "follow_up" else 700
    answer = llm_client.chat(
        [
            {
                "role": "system",
                "content": (
                    "Ты ИИ-агент приемной комиссии. Формулируй ответы естественно, "
                    "но не меняй бизнес-логику и не добавляй факты вне контекста."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.25,
        max_tokens=max_tokens,
    ).strip()
    return answer, True


def _build_admission_render_prompt(
    *,
    query: str,
    history: Any,
    language: str,
    classification: AdmissionIntent,
    decision: OrchestratorDecision,
    tool_result: dict[str, Any],
    admission_state: dict[str, Any],
    admission_profile: dict[str, Any],
    context: list[dict[str, Any]],
    fallback_answer: str,
    mode: str,
) -> str:
    common = (
        "Ты пишешь финальный текст для абитуриента университета.\n"
        "Важное разделение ответственности:\n"
        "- Код уже определил intent, обязательные slots и route.\n"
        "- Не решай заново, хватает ли данных.\n"
        "- Не меняй missing_slots, slots, route и выбранный инструмент.\n"
        "- Не придумывай цены, сроки, экзамены, документы, контакты или условия.\n"
        "- Если точной информации нет в fallback/context, не добавляй ее.\n"
        "- Ответ должен быть на языке language.\n"
        "- Верни только текст ответа, без пояснений о промпте.\n\n"
        f"language: {language}\n"
        f"mode: {mode}\n"
        f"user_query: {query}\n"
        f"classification: {json.dumps(asdict(classification), ensure_ascii=False)}\n"
        f"orchestration: {json.dumps(asdict(decision), ensure_ascii=False)}\n"
        f"admission_state: {_json_for_prompt(admission_state, ADMISSION_RENDER_TOOL_CHARS)}\n"
        f"admission_profile: {_json_for_prompt(admission_profile, ADMISSION_RENDER_TOOL_CHARS)}\n"
        f"history:\n{_format_history(history)}\n\n"
    )
    if mode == "follow_up":
        return (
            common
            + "Задача: сформулировать один живой уточняющий вопрос.\n"
            "- Спрашивай только про first missing slot / last_requested_slot.\n"
            "- Не задавай сразу несколько разных вопросов.\n"
            "- Не отвечай на основной вопрос пользователя до заполнения slots.\n"
            "- Можно кратко объяснить, зачем это нужно.\n"
            "- Не используй Markdown.\n\n"
            f"deterministic_question: {fallback_answer}\n"
        )

    return (
        common
        + "Задача: естественно сформулировать ответ по результату API/RAG.\n"
        "- Используй fallback_answer как главный источник истины.\n"
        "- Context/tool_result можно использовать только для уточнения формулировки.\n"
        "- Сохраняй все конкретные цифры, названия программ, контакты и ограничения.\n"
        "- Если fallback_answer содержит контакты, не удаляй телефон/email.\n"
        "- Пиши кратко, по делу. Можно использовать HTML <br> и списки, если это уже уместно.\n\n"
        f"fallback_answer:\n{fallback_answer}\n\n"
        f"context:\n{_format_render_context(context)}\n\n"
        f"tool_result:\n{_json_for_prompt(tool_result, ADMISSION_RENDER_TOOL_CHARS)}\n"
    )


def generate_admission_ai_answer(
    *,
    query: str,
    history: Any = None,
    language: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Compatibility wrapper for public admission endpoints."""
    response = run_admission_pipeline(query=query, history=history, language=language)
    return response["answer"], response["llm"]


class AdmissionIntentClassifier:
    """Returns only the routing JSON. It does not answer user questions."""

    def classify(
        self,
        query: str,
        *,
        history: Any = None,
        authenticated: bool = False,
    ) -> AdmissionIntent:
        deterministic = self._classify_by_rules(query, authenticated=authenticated)
        if deterministic.confidence >= 0.9 or not llm_client.is_configured:
            return deterministic

        llm_intent = self._classify_with_llm(query, history=history, authenticated=authenticated)
        return llm_intent or deterministic

    def _classify_by_rules(self, query: str, *, authenticated: bool) -> AdmissionIntent:
        normalized = _normalize_text(query)
        if not normalized:
            return AdmissionIntent("general_info", "faq", False, confidence=0.6)

        if _has_any(normalized, {"моя заявка", "статус заявки", "где моя заявка", "application status", "my application"}):
            return AdmissionIntent("applicant", "application_status", True, confidence=0.95)
        if _has_any(normalized, {"мой платеж", "оплата", "payment", "invoice", "квитанц"}):
            return AdmissionIntent("applicant", "payments", True, confidence=0.9)
        if _has_any(normalized, {"уведомлен", "notification", "хабарлама"}):
            return AdmissionIntent("applicant", "notifications", True, confidence=0.9)

        if _mentions_foreign_applicant(normalized) and (
            _looks_like_ent_requirement_query(normalized)
            or _has_any(normalized, {"иностран", "шетел", "foreign", "visa", "виза", "гражданин", "гражданство"})
        ):
            return AdmissionIntent("admissions", "international", False, confidence=0.95)
        if _has_any(normalized, {"узбекистан", "иностран", "шетел", "foreign", "visa", "виза", "гражданин"}):
            return AdmissionIntent("admissions", "international", False, confidence=0.95)
        if _has_any(normalized, {"стоим", "стоит", "цена", "оплат", "рассроч", "скид", "tuition", "price", "cost", "installment", "ақы"}):
            return AdmissionIntent("admissions", "tuition", False, confidence=0.95)
        if _has_any(normalized, {"документ", "құжат", "documents", "справк"}):
            return AdmissionIntent("admissions", "documents", False, confidence=0.95)
        if _has_any(normalized, {"программ", "специальност", "мамандық", "program", "major", "профильн", "предмет"}):
            return AdmissionIntent("admissions", "programs", False, confidence=0.95)
        if _looks_like_ent_requirement_query(normalized) or _has_any(normalized, {"ент нужен", "нужна ли ент", "нужно ли ент", "ұбт қажет"}):
            return AdmissionIntent("admissions", "eligibility", False, confidence=0.95)
        if _has_any(normalized, {"проход", "балл", "конкурс", "вероятност", "competition", "score", "ұбт", "ент"}):
            return AdmissionIntent("admissions", "competition", False, confidence=0.95)
        if _has_any(normalized, {"грант", "стипенд", "льгот", "scholarship", "grant", "жеңілдік"}):
            return AdmissionIntent("admissions", "scholarships", False, confidence=0.95)
        if _has_any(normalized, {"дедлайн", "срок", "қашан", "deadline", "when", "прием заяв"}):
            return AdmissionIntent("admissions", "deadlines", False, confidence=0.9)
        if _has_any(normalized, {"после колледжа", "магистратур", "докторантур", "ент нужен", "могу ли", "eligibility"}):
            return AdmissionIntent("admissions", "eligibility", False, confidence=0.9)

        if _has_any(normalized, {"контакт", "телефон", "email", "почта", "байланыс", "contact"}):
            return AdmissionIntent("general_info", "contacts", False, confidence=0.95)
        if _has_any(normalized, {"адрес", "где находится", "location", "address", "мекенжай"}):
            return AdmissionIntent("general_info", "address", False, confidence=0.95)
        if _has_any(normalized, {"общежит", "жатақхана", "student house", "dorm", "hostel"}):
            return AdmissionIntent("general_info", "student_house", False, confidence=0.95)

        return AdmissionIntent("general_info", "faq", False, confidence=0.65)

    def _classify_with_llm(
        self,
        query: str,
        *,
        history: Any,
        authenticated: bool,
    ) -> AdmissionIntent | None:
        prompt = (
            "You are an intent classifier. Do not answer the user.\n"
            "Return only valid JSON with keys: domain, subdomain, requires_auth.\n\n"
            "Domains and subdomains:\n"
            "- admissions: eligibility, programs, tuition, international, scholarships, competition, deadlines, documents\n"
            "- applicant: application_status, documents, payments, exams, notifications\n"
            "- general_info: contacts, address, student_house, events, faq\n\n"
            "Applicant domain always requires_auth=true. Other domains require_auth=false.\n\n"
            f"Authenticated: {authenticated}\n"
            f"History:\n{_format_history(history)}\n\n"
            f"Question: {query}"
        )
        raw = llm_client.chat([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=80)
        try:
            payload = json.loads(_extract_json_object(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return _normalize_intent_payload(payload, source="llm")


class AdmissionRequestOrchestrator:
    """Backend service that maps classifier output to structured data sources."""

    def dispatch(
        self,
        *,
        classification: AdmissionIntent,
        query: str,
        history: Any,
        language: str,
        authenticated: bool,
        slots: dict[str, Any] | None = None,
    ) -> tuple[OrchestratorDecision, dict[str, Any]]:
        decision = self._decision_for(classification)
        if decision.requires_auth and not authenticated:
            return decision, _auth_required_result(classification, language)

        data = load_admission_data()
        resolved_slots = slots or {}
        level = resolved_slots.get("degree") or extract_level(query)
        program = resolved_slots.get("program") or extract_program_with_history(query, history=history, data=data)
        programs = extract_programs_with_history(query, history=history, data=data)
        profile_subject_agent = ProfileSubjectAgent(data)
        profile_subjects = profile_subject_agent.subjects_from_slots(resolved_slots)
        if profile_subjects and not level:
            level = "bachelor"

        if classification.domain == "applicant":
            return decision, _applicant_placeholder_result(classification, language)
        if classification.domain == "general_info":
            return decision, self._dispatch_general_info(classification.subdomain, language)
        return decision, self._dispatch_admissions(
            subdomain=classification.subdomain,
            query=query,
            language=language,
            level=level,
            program=program,
            programs=programs,
            profile_subjects=profile_subjects,
        )

    def _decision_for(self, classification: AdmissionIntent) -> OrchestratorDecision:
        table = {
            ("admissions", "eligibility"): OrchestratorDecision("eligibility_rules_api", "admission_exams"),
            ("admissions", "programs"): OrchestratorDecision("program_catalog_api", "programs"),
            ("admissions", "tuition"): OrchestratorDecision("pricing_api", "prices"),
            ("admissions", "international"): OrchestratorDecision("international_rules_api", "foreign_admission"),
            ("admissions", "scholarships"): OrchestratorDecision("scholarships_api", "scholarships"),
            ("admissions", "competition"): OrchestratorDecision("competition_api", "passing_scores"),
            ("admissions", "deadlines"): OrchestratorDecision("admission_rules_api", "admission_exams"),
            ("admissions", "documents"): OrchestratorDecision("admission_rules_api", "documents"),
            ("applicant", "application_status"): OrchestratorDecision("crm_api", "application_status", True),
            ("applicant", "documents"): OrchestratorDecision("document_service", "applicant_documents", True),
            ("applicant", "payments"): OrchestratorDecision("admission_system_api", "payments", True),
            ("applicant", "exams"): OrchestratorDecision("admission_system_api", "applicant_exams", True),
            ("applicant", "notifications"): OrchestratorDecision("crm_api", "notifications", True),
            ("general_info", "contacts"): OrchestratorDecision("admission_rules_api", "contacts"),
            ("general_info", "address"): OrchestratorDecision("admission_rules_api", "address"),
            ("general_info", "student_house"): OrchestratorDecision("admission_rules_api", "student_house"),
            ("general_info", "events"): OrchestratorDecision("admission_rules_api", "contacts"),
            ("general_info", "faq"): OrchestratorDecision("admission_rules_api", "overview"),
        }
        return table.get((classification.domain, classification.subdomain), OrchestratorDecision("admission_rules_api", "overview"))

    def _dispatch_admissions(
        self,
        *,
        subdomain: str,
        query: str,
        language: str,
        level: str | None,
        program: str | None,
        programs: list[str],
        profile_subjects: list[str],
    ) -> dict[str, Any]:
        if subdomain == "eligibility":
            return get_admission_exams(language=language, query=query)
        if subdomain == "programs":
            return get_available_programs(level=level, language=language, profile_subjects=profile_subjects)
        if subdomain == "tuition":
            return get_current_prices(program=program, level=level, language=language)
        if subdomain == "international":
            return get_foreign_admission_info(language=language)
        if subdomain == "scholarships":
            return get_scholarships(language=language, query=query)
        if subdomain == "competition":
            return get_passing_scores(program=program, level=level, language=language)
        if subdomain == "deadlines":
            return get_admission_exams(language=language, query=query)
        if subdomain == "documents":
            return get_required_documents(level=level, language=language)
        return build_minimal_admission_overview(programs=programs, level=level, language=language)

    def _dispatch_general_info(self, subdomain: str, language: str) -> dict[str, Any]:
        if subdomain == "contacts":
            return get_admission_contacts(language=language)
        if subdomain == "address":
            return get_admission_address(language=language)
        if subdomain == "student_house":
            return get_student_house(language=language)
        if subdomain == "events":
            return _events_placeholder_result(language)
        return build_minimal_admission_overview(programs=[], level=None, language=language)


def detect_question_language(query: str, *, fallback: Any = None) -> str:
    fallback_language = _normalize_language(fallback)
    text = str(query or "").strip()
    if not text:
        return fallback_language

    lowered = text.casefold()
    if any(char in set("әғқңөұүһі") for char in lowered):
        return "kk"
    words = set(re.findall(r"[\w]+", lowered, flags=re.UNICODE))
    if words & {"сәлем", "салем", "қай", "қанша", "қалай", "оқу", "оқуға", "түсу", "қабылдау", "мамандық", "бағдарлама", "құжат", "ұбт"}:
        return "kk"
    if len(re.findall(r"[a-z]", lowered)) >= 3 and not re.findall(r"[а-яё]", lowered):
        return "en"
    if re.findall(r"[а-яё]", lowered):
        return "ru"
    return fallback_language


def _normalize_intent_payload(payload: dict[str, Any], *, source: str) -> AdmissionIntent | None:
    domain = str(payload.get("domain") or "").strip().lower()
    subdomain = str(payload.get("subdomain") or "").strip().lower()
    if domain == "admissions" and subdomain in ADMISSION_SUBDOMAINS:
        return AdmissionIntent(domain, subdomain, False, confidence=0.85, source=source)
    if domain == "applicant" and subdomain in APPLICANT_SUBDOMAINS:
        return AdmissionIntent(domain, subdomain, True, confidence=0.85, source=source)
    if domain == "general_info" and subdomain in GENERAL_INFO_SUBDOMAINS:
        return AdmissionIntent(domain, subdomain, False, confidence=0.85, source=source)
    return None


def _auth_required_result(classification: AdmissionIntent, language: str) -> dict[str, Any]:
    messages = {
        "ru": "Для этого запроса нужна авторизация абитуриента.",
        "kk": "Бұл сұрау үшін талапкер ретінде авторизация қажет.",
        "en": "This request requires applicant authentication.",
    }
    return {
        "status": "auth_required",
        "tool": "auth_gate",
        "language": language,
        "domain": classification.domain,
        "subdomain": classification.subdomain,
        "answer": messages.get(language, messages["ru"]),
    }


def _applicant_placeholder_result(classification: AdmissionIntent, language: str) -> dict[str, Any]:
    messages = {
        "ru": "Запрос относится к личному кабинету абитуриента. Источник данных выбран, но интеграция CRM/системы приема пока не подключена.",
        "kk": "Сұрау талапкердің жеке кабинетіне жатады. Дерек көзі таңдалды, бірақ CRM/қабылдау жүйесі интеграциясы әзірге қосылмаған.",
        "en": "This request belongs to the applicant account. The data source is selected, but CRM/admission system integration is not connected yet.",
    }
    return {
        "status": "source_not_connected",
        "tool": "applicant_domain",
        "language": language,
        "domain": classification.domain,
        "subdomain": classification.subdomain,
        "answer": messages.get(language, messages["ru"]),
    }


def _events_placeholder_result(language: str) -> dict[str, Any]:
    messages = {
        "ru": "Информация о мероприятиях пока не выделена в структурированный источник. Можно уточнить актуальные мероприятия через контакты приемной комиссии.",
        "kk": "Іс-шаралар туралы ақпарат әзірге бөлек құрылымдалған дереккөзге шығарылмаған. Өзекті іс-шараларды қабылдау комиссиясынан нақтылауға болады.",
        "en": "Events are not yet available as a separate structured source. Current events can be clarified through the admissions office contacts.",
    }
    return {
        "status": "source_not_connected",
        "tool": "events",
        "language": language,
        "answer": messages.get(language, messages["ru"]),
    }


def _payload_query(payload: Dict[str, Any]) -> str:
    return str(payload.get("message") or payload.get("question") or "").strip()


def _is_authenticated_payload(payload: Dict[str, Any]) -> bool:
    if payload.get("person_id") or payload.get("telegram_id") or payload.get("user_id"):
        return True
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        user = metadata.get("user")
        if isinstance(user, dict):
            return str(user.get("kind") or "").lower() == "authenticated"
    return False


def _format_history(history: Any) -> str:
    if not isinstance(history, list) or not history:
        return "- no previous messages"
    lines: list[str] = []
    for item in history[-ADMISSION_HISTORY_LIMIT:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user").strip().lower()
        content = str(item.get("content") or "").strip()
        if content:
            lines.append(f"- {role}: {_truncate(content, ADMISSION_HISTORY_CHARS)}")
    return "\n".join(lines) if lines else "- no previous messages"


def _format_render_context(context: list[dict[str, Any]]) -> str:
    if not context:
        return "- no context"
    lines: list[str] = []
    for index, item in enumerate(context[:ADMISSION_RENDER_CONTEXT_LIMIT], 1):
        if not isinstance(item, dict):
            continue
        content = _truncate(str(item.get("content") or ""), ADMISSION_RENDER_CONTEXT_CHARS)
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        source = metadata.get("file_name") or metadata.get("source_path") or metadata.get("tool") or "admission_info"
        if content:
            lines.append(f"{index}. [{source}] {content}")
    return "\n".join(lines) if lines else "- no context"


def _json_for_prompt(value: Any, limit: int) -> str:
    try:
        rendered = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        rendered = str(value)
    return _truncate(rendered, limit)


def _extract_json_object(value: str) -> str:
    text = str(value or "").strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return match.group(0) if match else text


def _has_any(normalized_text: str, terms: set[str]) -> bool:
    return any(term in normalized_text for term in terms)


def _mentions_foreign_applicant(normalized_text: str) -> bool:
    foreign_terms = {
        "иностран",
        "шетел",
        "foreign",
        "гражданин",
        "гражданство",
        "рф",
        "росси",
        "узбекистан",
        "кыргызстан",
        "киргизия",
        "китай",
        "украин",
        "беларус",
        "монголи",
        "индия",
        "турци",
        "ресей",
    }
    return _has_any(normalized_text, foreign_terms)


def _looks_like_ent_requirement_query(normalized_text: str) -> bool:
    exam_terms = {"ент", "ұбт", "unt", "кт", "вступительн", "экзамен", "тест"}
    requirement_terms = {
        "нужно ли",
        "нужна ли",
        "нужен ли",
        "надо ли",
        "должен ли",
        "обязательно",
        "требуется",
        "сдавать",
        "сдать",
        "қажет",
    }
    return _has_any(normalized_text, exam_terms) and _has_any(normalized_text, requirement_terms)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().casefold())


def _truncate(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 3)].rstrip()}..."


def _normalize_language(language: Any) -> str:
    value = str(language or "ru").strip().lower()
    if "-" in value:
        value = value.split("-", 1)[0]
    return value if value in {"ru", "kk", "en"} else "ru"
