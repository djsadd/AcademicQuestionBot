"""Intent Router Agent.

Two-tier classification:
1. Deterministic keyword rules (free, ~0 ms) for unambiguous requests.
2. LLM classification returning JSON with up to two intents, so mixed
   questions ("как поднять GPA и не вылететь?") can fan out to several agents.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from fastapi.concurrency import run_in_threadpool

from ..core.config import get_settings
from ..langchain.llm import llm_client
from ..langchain.tools.admission_info import extract_program
from .base import AgentResult, BaseAgent

MAX_INTENTS = 2

INTENT_DESCRIPTIONS: Dict[str, str] = {
    "password_reset": "не может войти, забыл пароль/логин, доступ заблокирован",
    "calendar": "академический календарь, даты сессии, каникулы, расписание периодов",
    "deadline": "дедлайны, сроки сдачи, последние даты подачи заявлений",
    "documents": "справки, заявления, приказы, документы студента",
    "gpa": "GPA, оценки, кредиты, пересдачи, отчисление, академическая задолженность",
    "admission": "поступление, абитуриенты, программы, стоимость, гранты, ЕНТ",
    "study": "учебный процесс, объяснение тем, подготовка к экзаменам",
    "general": "всё остальное",
}
ALLOWED_INTENTS = set(INTENT_DESCRIPTIONS)

INTENT_PROMPT = (
    "Ты классификатор запросов для чат-бота университета.\n"
    "Выбери от 1 до 2 intent из списка (первый — главный):\n"
    + "\n".join(f"- {key} — {value}" for key, value in INTENT_DESCRIPTIONS.items())
    + "\n\nПримеры:\n"
    '"Я не могу войти в систему" → {{"intents": ["password_reset"]}}\n'
    '"Когда начинается сессия?" → {{"intents": ["calendar"]}}\n'
    '"Как поднять GPA и не вылететь?" → {{"intents": ["gpa", "study"]}}\n\n'
    "История диалога:\n{history}\n\n"
    'Верни ТОЛЬКО JSON вида {{"intents": ["..."]}}.\n\n'
    "Запрос: {query}"
)

ADMISSION_KEYWORDS = (
    "поступ", "абитури", "прием", "приём", "специальност", "програм", "магистрат",
    "бакалав", "докторант", "грант", "ент", "ұбт", "цена", "стоимост", "сколько стоит", "оплата",
    "tuition", "price", "cost", "проходной балл", "академическая мобильность",
    "академическое сотрудничество", "двудипломное", "double degree", "түсу", "талапкер",
)

def _word_start_pattern(keywords: tuple[str, ...] | set[str]) -> re.Pattern[str]:
    """Match keywords only at the start of a word: "ент" must not hit "студент"."""
    alternatives = "|".join(sorted((re.escape(k) for k in keywords), key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternatives})", re.IGNORECASE)


ADMISSION_PATTERN = _word_start_pattern(ADMISSION_KEYWORDS)

RULES: List[tuple[str, tuple[str, ...]]] = [
    ("password_reset", ("забыл пароль", "сбросить пароль", "сброс пароля", "восстановить пароль",
                        "не могу войти", "неверный пароль", "забыл логин", "заблокирован",
                        "reset password", "forgot password", "құпия сөз")),
    ("calendar", ("академический календарь", "академ календарь", "когда сессия", "когда начинается сессия",
                  "начало семестра", "каникулы", "academic calendar", "күнтізбе")),
    ("documents", ("справк", "заявлени", "приказ", "академическ отпуск", "академический отпуск")),
    ("gpa", ("gpa", "джипиэй", "пересдач", "отчисл", "академическая задолж", "академической задолж", "кредит")),
]
RULE_PATTERNS = [(intent, _word_start_pattern(keywords)) for intent, keywords in RULES]
FOLLOWUP_PATTERN = _word_start_pattern({
    "документ", "құжат", "стоим", "стоит", "цена", "оплат", "срок", "длительность",
    "балл", "проход", "грант", "предмет", "ент", "ұбт", "форма", "очно", "контакт",
    "прием", "приём", "поступ", "documents", "tuition", "price", "duration", "score", "grant",
})


class IntentRouterAgent(BaseAgent):
    """Classifies incoming messages into one or more intents."""

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.default_intent = "general"

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        text = (payload.get("message") or "").strip()
        rule_intent = self._detect_intent_by_keywords(text, payload=payload)
        if rule_intent:
            intents, source = [rule_intent], "rules"
        else:
            intents, llm_ok = await self._classify_intent(text, payload.get("history"))
            source = "llm" if llm_ok else "default"
        priority = "high" if "password_reset" in intents else "medium"
        return AgentResult(intents=intents, priority=priority, source=source)

    async def _classify_intent(self, text: str, history: Any = None) -> tuple[List[str], bool]:
        if not text or not llm_client.is_configured:
            return [self.default_intent], False
        prompt = INTENT_PROMPT.format(query=text, history=self._format_history(history))
        data = await run_in_threadpool(
            llm_client.chat_json,
            [{"role": "user", "content": prompt}],
            max_tokens=40,
            model=get_settings().fast_model,
        )
        return self._parse_intents(data), data is not None

    def _parse_intents(self, data: Any) -> List[str]:
        raw = data.get("intents") if isinstance(data, dict) else None
        if isinstance(raw, str):
            raw = [raw]
        intents: List[str] = []
        for item in raw or []:
            value = str(item).strip().lower()
            if value in ALLOWED_INTENTS and value not in intents:
                intents.append(value)
        intents = intents[:MAX_INTENTS]
        if len(intents) > 1 and "general" in intents:
            intents.remove("general")
        return intents or [self.default_intent]

    def _detect_intent_by_keywords(self, text: str, *, payload: Dict[str, Any] | None = None) -> str | None:
        normalized = text.lower().strip()
        if not normalized:
            return None
        for intent, pattern in RULE_PATTERNS[:2]:  # access & calendar are unambiguous
            if pattern.search(normalized):
                return intent
        if extract_program(text):
            return "admission"
        if self._has_admission_context(payload) and self._looks_like_admission_followup(normalized):
            return "admission"
        if ADMISSION_PATTERN.search(normalized):
            return "admission"
        for intent, pattern in RULE_PATTERNS[2:]:
            if pattern.search(normalized):
                return intent
        return None

    def _has_admission_context(self, payload: Dict[str, Any] | None) -> bool:
        if not isinstance(payload, dict):
            return False
        for source in (
            payload,
            payload.get("context") if isinstance(payload.get("context"), dict) else None,
            payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
        ):
            if not isinstance(source, dict):
                continue
            if isinstance(source.get("admission_profile"), dict) or isinstance(source.get("admission_state"), dict):
                return True
            snapshot = source.get("context_snapshot")
            if isinstance(snapshot, dict) and (
                isinstance(snapshot.get("admission_profile"), dict)
                or isinstance(snapshot.get("admission_state"), dict)
            ):
                return True
        return False

    def _looks_like_admission_followup(self, normalized: str) -> bool:
        return bool(FOLLOWUP_PATTERN.search(normalized))

    def _format_history(self, history: Any) -> str:
        if not isinstance(history, list) or not history:
            return "- no previous messages"
        lines: list[str] = []
        for item in history[-6:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "user").strip().lower()
            if role == "bot":
                role = "assistant"
            content = " ".join(str(item.get("content") or "").split())
            if content:
                lines.append(f"- {role}: {content[:300]}")
        return "\n".join(lines) if lines else "- no previous messages"
