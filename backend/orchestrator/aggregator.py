"""Merge agent outputs into synthesis inputs and the final response object."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..langchain.llm import llm_client
from .graph import AgentPlanStep

PROMPT_PATH = Path(__file__).resolve().parents[1] / "langchain" / "prompts" / "final_answer.txt"
SYSTEM_PROMPT = (
    "Ты — официальный академический ИИ-ассистент университета Туран-Астана (TAU). "
    "Ты помогаешь студентам и абитуриентам, отвечаешь точно, вежливо и только по "
    "предоставленным материалам. Никогда не выдумывай факты."
)
MAX_CONTEXT_ITEMS = 8
CONTEXT_ITEM_CHARS = 900
ADMISSION_KEYS = ("classification", "orchestration", "admission_state", "admission_profile", "tool_data")


@dataclass
class AggregationArtifacts:
    answers: List[str] = field(default_factory=list)
    context: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    validator: Dict[str, Any] = field(default_factory=dict)
    direct_response: str = ""

    @property
    def evidence(self) -> List[str]:
        """Raw texts the validator checks the final answer against."""
        return [*self.answers, *(str(item.get("content") or "") for item in self.context)]


def _load_prompt_template() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:  # pragma: no cover - fallback for deployments
        return (
            "Вопрос: {question}\nИстория:\n{history}\nИнтенты: {intents}\n"
            "Ответы агентов: {agent_answers}\nКонтекст: {context}\nИсточники: {citations}\n"
            "Сформулируй итоговый ответ на языке вопроса."
        )


class ResponseAggregator:
    """Aggregates agent answers and context; renders the synthesis prompt."""

    def __init__(self) -> None:
        self.prompt_template = _load_prompt_template()

    # ----------------------------------------------------------- collection
    def collect_artifacts(self, trace: List[Dict[str, Any]], *, primary_agent: Optional[str] = None) -> AggregationArtifacts:
        artifacts = AggregationArtifacts()
        seen_context: set[str] = set()
        seen_citations: set[tuple[Any, Any]] = set()

        for item in trace:
            agent_key = item.get("key")
            output = item.get("output") or {}
            if not isinstance(output, dict) or agent_key in {"intent", "retrieval", "synthesis"}:
                continue
            if agent_key == "validator":
                artifacts.validator = output
                continue

            answer = output.get("answer")
            if answer:
                artifacts.answers.append(str(answer))
                is_primary = primary_agent is None or agent_key == primary_agent
                if output.get("direct_response") and is_primary and not artifacts.direct_response:
                    artifacts.direct_response = str(answer)

            for entry in output.get("context") or []:
                normalized = entry if isinstance(entry, dict) else {"content": str(entry), "metadata": {}}
                fingerprint = hashlib.sha1(str(normalized.get("content") or "").encode("utf-8")).hexdigest()
                if fingerprint in seen_context:
                    continue
                seen_context.add(fingerprint)
                artifacts.context.append(normalized)

            for cite in output.get("citations") or []:
                if not isinstance(cite, dict):
                    continue
                key = (cite.get("file_name"), cite.get("chunk_index"))
                if key in seen_citations:
                    continue
                seen_citations.add(key)
                artifacts.citations.append(cite)

        return artifacts

    def collect_admission_metadata(self, trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        for item in reversed(trace):
            if item.get("key") != "admission":
                continue
            output = item.get("output")
            if not isinstance(output, dict):
                return {}
            return {key: output[key] for key in ADMISSION_KEYS if key in output}
        return {}

    # ------------------------------------------------------------ synthesis
    def fallback_answer(self, answers: List[str]) -> str:
        if not answers:
            return (
                "К сожалению, я не нашёл информации по вашему вопросу. "
                "Попробуйте переформулировать его или обратитесь в деканат."
            )
        return "\n\n".join(answers)

    def should_synthesize(self, artifacts: AggregationArtifacts) -> bool:
        if artifacts.direct_response or not llm_client.is_configured or not artifacts.answers:
            return False
        if artifacts.citations or len(artifacts.answers) != 1:
            return True
        # A single, very long structured tool answer is already final.
        answer = artifacts.answers[0].strip()
        return not (len(answer) >= 5000 or answer.count("\n") >= 60)

    def build_messages(self, *, user_payload: Dict[str, Any], intents: Dict[str, Any], artifacts: AggregationArtifacts) -> List[Dict[str, str]]:
        prompt = self.prompt_template.format(
            question=user_payload.get("message", ""),
            history=self._format_history(user_payload.get("history")),
            intents=", ".join(intents.get("intents", []) or ["general"]),
            context=self._format_context(artifacts.context),
            agent_answers="\n---\n".join(artifacts.answers) or "нет промежуточных ответов",
            citations=self._format_citations(artifacts.citations),
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

    # ------------------------------------------------------------- response
    def build_response(
        self,
        *,
        user_payload: Dict[str, Any],
        intents: Dict[str, Any],
        plan: List[AgentPlanStep],
        trace: List[Dict[str, Any]],
        artifacts: AggregationArtifacts,
        final_answer: str,
        llm_used: bool,
        llm_error: Optional[str],
        timings: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        return {
            "query": user_payload.get("message"),
            "language": user_payload.get("language"),
            "intents": intents.get("intents", []),
            "priority": intents.get("priority"),
            "plan": [{"agent": step.key, "description": step.description} for step in plan],
            "trace": trace,
            "final_answer": final_answer,
            "validation": artifacts.validator,
            "citations": artifacts.citations,
            "supporting_context": artifacts.context,
            "timings_ms": timings or {},
            "llm": {
                "model": getattr(llm_client, "model", None),
                "used": llm_used,
                "error": llm_error,
                "raw_request": None if llm_used else {
                    "intents": intents.get("intents", []),
                    "plan": [step.key for step in plan],
                },
            },
            **self.collect_admission_metadata(trace),
        }

    # ----------------------------------------------------------- formatting
    def _format_history(self, history: Any) -> str:
        if not isinstance(history, list) or not history:
            return "- история диалога отсутствует"
        lines: List[str] = []
        for item in history[-8:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "user").strip().lower()
            role = "assistant" if role == "bot" else role
            content = " ".join(str(item.get("content") or "").split())
            if content:
                lines.append(f"- {role}: {content[:500]}")
        return "\n".join(lines) if lines else "- история диалога отсутствует"

    def _format_context(self, context: List[Dict[str, Any]]) -> str:
        if not context:
            return "документы не найдены"
        lines: List[str] = []
        for idx, item in enumerate(context[:MAX_CONTEXT_ITEMS], 1):
            metadata = item.get("metadata") or {}
            source = metadata.get("title") or metadata.get("original_file") or metadata.get("file_name") or "Источник"
            where = ", ".join(
                part for part in (
                    f"стр. {metadata['page']}" if metadata.get("page") else "",
                    str(metadata.get("section") or "")[:80],
                ) if part
            )
            content = " ".join(str(item.get("content") or "").split())
            lines.append(f"[{idx}] {source}{f' ({where})' if where else ''}: {content[:CONTEXT_ITEM_CHARS]}")
        return "\n".join(lines)

    def _format_citations(self, citations: List[Dict[str, Any]]) -> str:
        if not citations:
            return "- нет"
        names = list(dict.fromkeys(cite.get("title") or cite.get("file_name") or "Источник" for cite in citations))
        return "\n".join(f"- {name}" for name in names)

    # ------------------------------------------------- backwards compatibility
    _collect_artifacts = collect_artifacts
    _collect_admission_metadata = collect_admission_metadata
    _fallback_answer = fallback_answer
