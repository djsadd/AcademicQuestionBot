"""Utilities to merge agent outputs into a single response."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from ..langchain.llm import llm_client
from .graph import AgentPlanStep


PROMPT_PATH = Path(__file__).resolve().parents[1] / "langchain" / "prompts" / "final_answer.txt"
SYSTEM_PROMPT = "Ты академический ассистент университета. Собери ответ, сохраняя тон и безопасность."


@dataclass
class AggregationArtifacts:
    answers: List[str]
    context: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    validator: Dict[str, Any]


def _load_prompt_template() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:  # pragma: no cover - fallback for deployments
        return (
            "Вопрос: {question}\n"
            "Ответы агентов: {agent_answers}\n"
            "Контекст: {context}\n"
            "Сформулируй итоговый ответ на языке {language}."
        )


class ResponseAggregator:
    """Aggregates agent answers, query context and generates the final response."""

    def __init__(self) -> None:
        self.prompt_template = _load_prompt_template()

    def aggregate(
        self,
        *,
        user_payload: Dict[str, Any],
        intents: Dict[str, Any],
        plan: List[AgentPlanStep],
        trace: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        artifacts = self._collect_artifacts(trace)
        fallback_answer = self._fallback_answer(artifacts.answers)
        llm_answer = self._synthesize_final_answer(
            user_payload=user_payload,
            intents=intents,
            answers=artifacts.answers,
            context=artifacts.context,
            citations=artifacts.citations,
        )

        final_answer = llm_answer or fallback_answer
        plan_view = [
            {"agent": step.key, "description": step.description} for step in plan
        ]

        return {
            "query": user_payload.get("message"),
            "intents": intents.get("intents", []),
            "priority": intents.get("priority"),
            "plan": plan_view,
            "trace": trace,
            "final_answer": final_answer,
            "validation": artifacts.validator,
            "citations": artifacts.citations,
            "supporting_context": artifacts.context,
            "llm": {
                "model": getattr(llm_client, "model", None),
                "used": bool(llm_answer),
                "error": getattr(llm_client, "last_error", None),
                "raw_request": {
                    "intents": intents.get("intents", []),
                    "plan": [step.key for step in plan],
                } if not llm_answer else None,
            },
        }

    def _collect_artifacts(self, trace: List[Dict[str, Any]]) -> AggregationArtifacts:
        answers: List[str] = []
        context: List[Dict[str, Any]] = []
        citations: List[Dict[str, Any]] = []
        validator: Dict[str, Any] = {}

        for item in trace:
            agent_key = item["key"]
            output = item.get("output", {}) or {}
            if agent_key == "validator":
                validator = output
                continue

            answer = output.get("answer")
            if answer:
                answers.append(str(answer))

            context_items = output.get("context")
            if isinstance(context_items, list):
                for entry in context_items:
                    if isinstance(entry, dict):
                        context.append(entry)
                    else:
                        context.append({"content": str(entry), "metadata": {}})

            citation_items = output.get("citations")
            if isinstance(citation_items, list):
                citations.extend(
                    entry
                    for entry in citation_items
                    if isinstance(entry, dict)
                )

        return AggregationArtifacts(
            answers=answers,
            context=context,
            citations=citations,
            validator=validator,
        )

    def _fallback_answer(self, answers: List[str]) -> str:
        if not answers:
            return "Нет ответа."
        return "\n\n".join(answers)

    def _synthesize_final_answer(
        self,
        *,
        user_payload: Dict[str, Any],
        intents: Dict[str, Any],
        answers: List[str],
        context: List[Dict[str, Any]],
        citations: List[Dict[str, Any]],
    ) -> str:
        if not llm_client.is_configured or not answers:
            return ""

        formatted_prompt = self._render_prompt(
            user_payload=user_payload,
            intents=intents,
            answers=answers,
            context=context,
            citations=citations,
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": formatted_prompt},
        ]
        return llm_client.chat(messages)

    def _render_prompt(
        self,
        *,
        user_payload: Dict[str, Any],
        intents: Dict[str, Any],
        answers: List[str],
        context: List[Dict[str, Any]],
        citations: List[Dict[str, Any]],
    ) -> str:
        language = user_payload.get("language") or "ru"
        context_text = self._format_context(context)
        citations_text = self._format_citations(citations)
        answers_text = "\n---\n".join(answers) or "нет промежуточных ответов"
        intents_text = ", ".join(intents.get("intents", []) or ["general"])

        return self.prompt_template.format(
            question=user_payload.get("message", ""),
            language=language,
            intents=intents_text,
            context=context_text,
            agent_answers=answers_text,
            citations=citations_text,
        )

    def _format_context(self, context: List[Dict[str, Any]]) -> str:
        if not context:
            return "  • контекст недоступен"
        lines: List[str] = []
        for idx, item in enumerate(context, 1):
            content = item.get("content") or ""
            metadata = item.get("metadata") or {}
            source = metadata.get("file_name") or metadata.get("source_path") or "Источник"
            score = item.get("score")
            prefix = f"  {idx}. [{source}]"
            if isinstance(score, (int, float)):
                prefix += f" (score={float(score):.2f})"
            lines.append(f"{prefix} {content[:400].strip()}")
        return "\n".join(lines)

    def _format_citations(self, citations: List[Dict[str, Any]]) -> str:
        if not citations:
            return "- нет ссылок"
        lines: List[str] = []
        for cite in citations:
            file_name = cite.get("file_name") or "Источник"
            chunk_index = cite.get("chunk_index")
            chunk_suffix = f", chunk {chunk_index}" if chunk_index is not None else ""
            lines.append(f"- {file_name}{chunk_suffix}")
        return "\n".join(lines)
