"""Validator / critic agent.

Runs *after* answer synthesis and performs cheap, deterministic checks:

* **HTML safety** – the answer is rendered as HTML in the web UI and Telegram,
  so only an allow-list of tags survives; scripts, styles and attributes are
  stripped.
* **Grounding** – numbers in the answer (prices, scores, dates, phone numbers)
  must appear in the evidence the agents collected. Ungrounded figures are the
  most harmful kind of hallucination for a university assistant, so the answer
  gets a short, localized caution note.
* **Coverage** – flags answers produced without any supporting context.
"""
from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List

from .base import AgentResult, BaseAgent

ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li", "h2", "h3", "h4",
    "table", "thead", "tbody", "tr", "th", "td", "blockquote", "code", "pre", "a", "hr",
}
VOID_TAGS = {"br", "hr"}
DROP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "noscript", "template"}

NUMBER_RE = re.compile(r"\d[\d\s.,:/\-]*\d|\d")

CAUTION = {
    "ru": "Часть цифр не найдена в официальных источниках — пожалуйста, уточните их в деканате или приёмной комиссии.",
    "kk": "Кейбір сандар ресми дереккөздерден табылмады — оларды деканаттан немесе қабылдау комиссиясынан нақтылаңыз.",
    "en": "Some figures could not be verified against official sources — please double-check them with the dean's office or admissions.",
}


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._drop_depth = 0

    def handle_starttag(self, tag: str, attrs: List[tuple[str, str | None]]) -> None:
        if tag in DROP_CONTENT_TAGS:
            self._drop_depth += 1
            return
        if self._drop_depth or tag not in ALLOWED_TAGS:
            return
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if re.match(r"^(https?:|mailto:|tel:)", href.strip(), re.IGNORECASE):
                self.parts.append(f'<a href="{escape(href.strip(), quote=True)}" target="_blank" rel="noopener noreferrer">')
            else:
                self.parts.append("<a>")
            return
        self.parts.append(f"<{tag}>")

    def handle_startendtag(self, tag: str, attrs: List[tuple[str, str | None]]) -> None:
        if not self._drop_depth and tag in VOID_TAGS:
            self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in DROP_CONTENT_TAGS:
            self._drop_depth = max(0, self._drop_depth - 1)
            return
        if self._drop_depth or tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._drop_depth:
            self.parts.append(escape(data, quote=False))


def sanitize_html(value: str) -> str:
    """Keep only allow-listed tags; plain text passes through (escaped)."""
    if not value or "<" not in value:
        return value or ""
    parser = _Sanitizer()
    parser.feed(value)
    parser.close()
    return "".join(parser.parts).strip()


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def find_ungrounded_numbers(answer: str, evidence: Iterable[str], *, min_digits: int = 3) -> List[str]:
    """Return numbers (>= ``min_digits`` digits) present in the answer but absent in the evidence."""
    plain_answer = re.sub(r"<[^>]+>", " ", answer or "")
    evidence_digits = " ".join(_digits(chunk) + " " + " ".join(_digits(m) for m in NUMBER_RE.findall(chunk)) for chunk in evidence)
    missing: List[str] = []
    for match in NUMBER_RE.findall(plain_answer):
        digits = _digits(match)
        if len(digits) < min_digits:
            continue
        if digits in evidence_digits:
            continue
        missing.append(match.strip())
    return list(dict.fromkeys(missing))


class ValidatorAgent(BaseAgent):
    """Validates the synthesized answer before it reaches the user."""

    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        return AgentResult(
            self.validate(
                answer=str(payload.get("final_answer") or ""),
                evidence=payload.get("evidence") or [],
                has_context=bool(payload.get("has_context")),
                synthesized=bool(payload.get("synthesized")),
                language=str(payload.get("language") or "ru"),
            )
        )

    def validate(
        self,
        *,
        answer: str,
        evidence: List[str],
        has_context: bool,
        synthesized: bool,
        language: str = "ru",
    ) -> Dict[str, Any]:
        issues: List[str] = []
        sanitized = sanitize_html(answer)
        if sanitized != (answer or "").strip() and "<" in (answer or ""):
            issues.append("html_sanitized")

        if not sanitized.strip():
            issues.append("empty_answer")

        if synthesized and not has_context:
            issues.append("no_supporting_context")

        ungrounded: List[str] = []
        if synthesized and evidence:
            ungrounded = find_ungrounded_numbers(sanitized, evidence)
            if ungrounded:
                issues.append("ungrounded_numbers")
                note = CAUTION.get(language, CAUTION["ru"])
                sanitized = f"{sanitized}\n<p><em>{escape(note)}</em></p>"

        blocking = {"empty_answer", "ungrounded_numbers"}
        return {
            "is_valid": not (blocking & set(issues)),
            "issues": issues,
            "ungrounded_numbers": ungrounded,
            "final_answer": sanitized,
        }
