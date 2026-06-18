"""LLM-backed admission question classifier with deterministic fallback."""
from __future__ import annotations

import re
from typing import Any

from ..langchain.llm import llm_client
from ..langchain.tools.admission_info import detect_requested_tool


ADMISSION_TOOL_LABELS = {
    "overview",
    "programs",
    "prices",
    "passing_scores",
    "documents",
    "address",
    "contacts",
    "durations",
    "academic_mobility",
    "academic_cooperation",
    "scholarships",
    "admission_exams",
    "foreign_admission",
    "management",
    "student_house",
    "study_formats",
}

ADMISSION_CLASSIFIER_HISTORY_LIMIT = 6
ADMISSION_CLASSIFIER_HISTORY_CHARS = 180

ADMISSION_CLASSIFIER_PROMPT = """You classify user questions for an admissions chatbot.

Return exactly one label from this list:
- overview: broad admission question or unclear admission topic
- programs: available majors/programs/specialties
- prices: tuition fees, payment, cost
- passing_scores: passing scores, threshold scores, grant scores, UNT score, profile subjects
- documents: required documents
- address: admissions office address or location
- contacts: phone, email, work schedule, website, how to contact admissions
- durations: study duration
- academic_mobility: academic mobility, exchange, partner universities for mobility
- academic_cooperation: academic partnerships, double degree, cooperation agreements
- scholarships: grants, scholarships, stipends, financial aid, but not score thresholds
- admission_exams: UNT/CT/doctoral entrance exams and exam rules, but not score thresholds
- foreign_admission: admission for foreign citizens, applicants from another country, visa/adaptation
- management: university leadership, rector, administration
- student_house: dormitory, student house, housing
- study_formats: study format/mode, full-time/offline, distance/online/remote learning availability

Priority rules:
- If the question asks about grant/UNT/passing points or threshold scores, use passing_scores.
- If the question asks whether distance, online, remote, full-time or offline study is available, use study_formats.
- If it asks whether a foreign applicant needs UNT/CT or how foreigners apply, use foreign_admission.
- If it asks for contact details, use contacts even if admissions office is mentioned.
- If the topic is broad or not enough information is available, use overview.

Conversation history:
{history}

Question: {query}

Return one label only."""


def classify_admission_tool(query: str, history: Any = None) -> str:
    """Classify an admission query into a structured tool label."""
    fallback_tool = _normalize_tool_label(detect_requested_tool(query)) or "overview"
    if fallback_tool != "overview":
        return fallback_tool
    if not str(query or "").strip() or not llm_client.is_configured:
        return fallback_tool

    prompt = ADMISSION_CLASSIFIER_PROMPT.format(
        history=_format_classifier_history(history),
        query=str(query).strip(),
    )
    response = llm_client.chat(
        [{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=16,
    )
    return _normalize_tool_label(response) or fallback_tool


def _normalize_tool_label(value: str | None) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    text = text.strip("`'\" \t\r\n")
    if text in ADMISSION_TOOL_LABELS:
        return text
    for label in sorted(ADMISSION_TOOL_LABELS, key=len, reverse=True):
        if re.search(rf"(?<![a-z_]){re.escape(label)}(?![a-z_])", text):
            return label
    match = re.search(r"[a-z_]+", text)
    if match and match.group(0) in ADMISSION_TOOL_LABELS:
        return match.group(0)
    return None


def _format_classifier_history(history: Any) -> str:
    if not isinstance(history, list) or not history:
        return "- no previous messages"

    lines: list[str] = []
    for item in history[-ADMISSION_CLASSIFIER_HISTORY_LIMIT:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user").strip().lower()
        if role == "bot":
            role = "assistant"
        if role not in {"user", "assistant", "system"}:
            role = "user"
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"- {role}: {_truncate(content, ADMISSION_CLASSIFIER_HISTORY_CHARS)}")
    return "\n".join(lines) if lines else "- no previous messages"


def _truncate(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 3)].rstrip()}..."
