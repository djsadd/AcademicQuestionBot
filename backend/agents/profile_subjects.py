"""Profile subject collection and normalization for admission program matching."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from ..langchain.tools.admission_info import load_admission_data


PROFILE_SUBJECT_1 = "profile_subject_1"
PROFILE_SUBJECT_2 = "profile_subject_2"
PROFILE_SUBJECT_SLOTS = (PROFILE_SUBJECT_1, PROFILE_SUBJECT_2)

PROFILE_SUBJECT_CONTEXT_TERMS = {
    "профиль",
    "профильные",
    "предмет",
    "предметы",
    "ент",
    "ұбт",
    "комбинация",
    "сдаю",
    "сдал",
    "сдала",
    "profile subject",
    "profile subjects",
    "unt",
}

EXTRA_PROFILE_SUBJECT_ALIASES: dict[str, set[str]] = {
    "Иностранный язык": {
        "английский",
        "английский язык",
        "english",
        "foreign language",
    },
    "Всемирная история": {
        "мировая история",
        "world history",
    },
    "Основы права": {
        "право",
        "law",
        "law basics",
    },
}


@dataclass(frozen=True)
class ProfileSubjectAnalysis:
    active: bool
    subjects: list[str]
    missing: list[str]
    slots: dict[str, Any]


class ProfileSubjectAgent:
    """Collects the two UNT profile subjects and returns exact catalog values."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = data or load_admission_data()
        self.subjects = self._catalog_subjects(self.data)
        self.aliases = self._build_aliases(self.subjects)

    def analyze(
        self,
        query: str,
        *,
        slots: dict[str, Any] | None = None,
        force_active: bool = False,
    ) -> ProfileSubjectAnalysis:
        next_slots = dict(slots or {})
        extracted = self.extract(query)
        active = force_active or self.looks_like_request(query) or bool(self.subjects_from_slots(next_slots))

        missing_slots = [slot for slot in PROFILE_SUBJECT_SLOTS if _is_missing(next_slots.get(slot))]
        target_slots = missing_slots or list(PROFILE_SUBJECT_SLOTS)
        for subject, slot in zip(extracted, target_slots):
            if not _is_missing(next_slots.get(slot)) and next_slots.get(slot) != subject:
                continue
            next_slots[slot] = subject

        subjects = self.subjects_from_slots(next_slots)
        missing = []
        if active and len(subjects) < 2:
            missing = [slot for slot in PROFILE_SUBJECT_SLOTS if _is_missing(next_slots.get(slot))]
        return ProfileSubjectAnalysis(
            active=active,
            subjects=subjects,
            missing=missing,
            slots=next_slots,
        )

    def looks_like_request(self, query: str) -> bool:
        normalized = _normalize(query)
        if not normalized:
            return False
        return any(_term_matches(term, normalized) for term in PROFILE_SUBJECT_CONTEXT_TERMS)

    def extract(self, query: str) -> list[str]:
        normalized = _normalize(query)
        if not normalized:
            return []

        matches: list[tuple[int, str]] = []
        seen: set[str] = set()
        for alias, subject in self.aliases.items():
            if not _term_matches(alias, normalized):
                continue
            position = normalized.find(_normalize(alias))
            if position < 0:
                position = len(normalized)
            if subject in seen:
                continue
            seen.add(subject)
            matches.append((position, subject))

        matches.sort(key=lambda item: item[0])
        return [subject for _, subject in matches[:2]]

    def subjects_from_slots(self, slots: dict[str, Any] | None) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for slot in PROFILE_SUBJECT_SLOTS:
            subject = self.canonicalize((slots or {}).get(slot))
            if not subject or subject in seen:
                continue
            seen.add(subject)
            result.append(subject)
        return result

    def canonicalize(self, value: Any) -> str:
        normalized = _normalize(str(value or ""))
        if not normalized:
            return ""
        return self.aliases.get(normalized, str(value or "").strip())

    @staticmethod
    def _catalog_subjects(data: dict[str, Any]) -> list[str]:
        subjects: list[str] = []
        seen: set[str] = set()
        for program in data.get("programs") or []:
            if not isinstance(program, dict):
                continue
            for key in PROFILE_SUBJECT_SLOTS:
                value = str(program.get(key) or "").strip()
                if not value or value in seen:
                    continue
                seen.add(value)
                subjects.append(value)
        return subjects

    @staticmethod
    def _build_aliases(subjects: list[str]) -> dict[str, str]:
        aliases: dict[str, str] = {}
        available = set(subjects)
        for subject in subjects:
            aliases[_normalize(subject)] = subject
        for subject, variants in EXTRA_PROFILE_SUBJECT_ALIASES.items():
            if subject not in available:
                continue
            for variant in variants:
                aliases[_normalize(variant)] = subject
        return aliases


def _term_matches(term: str, normalized_query: str) -> bool:
    normalized_term = _normalize(term)
    if not normalized_term:
        return False
    if " " in normalized_term:
        return normalized_term in normalized_query
    return bool(re.search(rf"(?<![\w]){re.escape(normalized_term)}(?![\w])", normalized_query))


def _normalize(value: str) -> str:
    cleaned = re.sub(r"[^\w\s]+", " ", str(value or "").casefold())
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())
