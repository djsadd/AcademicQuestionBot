"""Admission agent backed by structured admission tools."""
from __future__ import annotations

from typing import Any, Dict

from ..langchain.tools.admission_info import (
    build_context_entries,
    detect_requested_tool,
    extract_level,
    extract_program,
    format_admission_tool_result,
    get_admission_contacts,
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
        data = load_admission_data()
        level = payload.get("level") or extract_level(query)
        program = payload.get("program") or extract_program(query, data=data)
        requested_tool = detect_requested_tool(query)

        if requested_tool == "prices":
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
    prices = get_current_prices(program=program, level=level)
    scores = get_passing_scores(program=program, level=level)
    durations = get_study_durations(program=program, level=level)
    contacts = get_admission_contacts()

    answer = "\n\n".join(
        [
            "Информация приемной комиссии:",
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
