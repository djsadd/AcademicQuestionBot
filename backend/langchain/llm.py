"""LLM client for OpenAI-compatible Chat Completions APIs.

Production notes:
* A pooled ``requests.Session`` reuses TLS connections between calls.
* Transient failures (429 / 5xx / connection resets) are retried with
  exponential backoff.
* ``last_error`` is stored per thread, so concurrent requests no longer
  overwrite each other's error state.
* ``OPENAI_BASE_URL`` lets you point the client at any OpenAI-compatible
  server (Azure gateway, vLLM, Ollama, LM Studio, ...).
"""
from __future__ import annotations

import json
import logging
import random
import threading
import time
from typing import Any, Dict, Iterator, List, Optional

import requests
from requests.adapters import HTTPAdapter

from ..core.config import get_settings

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class LLMClient:
    """Thin, thread-safe REST client for chat completions."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url
        self.model = settings.openai_model
        self.fast_model = settings.fast_model
        self.team = settings.openai_team
        self.default_max_tokens = settings.openai_max_tokens
        self.timeout = settings.openai_timeout
        self.max_retries = settings.openai_max_retries
        self._local = threading.local()
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=8, pool_maxsize=32)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    # ------------------------------------------------------------------ state
    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def last_error(self) -> Optional[str]:
        return getattr(self._local, "last_error", None)

    @last_error.setter
    def last_error(self, value: Optional[str]) -> None:
        self._local.last_error = value

    # ------------------------------------------------------------- public API
    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Send a chat completion request and return the assistant text ('' on failure)."""
        self.last_error = None
        if not self.api_key:
            self.last_error = "OPENAI_API_KEY is not configured"
            return ""
        payload = self._payload(messages, kwargs)
        started = time.perf_counter()
        response = self._post(payload, stream=False)
        if response is None:
            return ""
        raw_body = response.text
        try:
            data = response.json()
            message = data["choices"][0]["message"].get("content")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            self.last_error = f"Invalid response format: {exc}. Raw: {raw_body[:400]}"
            return ""
        logger.debug(
            "llm.chat model=%s tokens=%s %.0fms",
            payload["model"],
            (data.get("usage") or {}).get("total_tokens"),
            (time.perf_counter() - started) * 1000,
        )
        parsed = self._parse_message_content(message)
        if not parsed:
            self.last_error = f"LLM response did not contain text. Raw: {raw_body[:400]}"
        return parsed

    def chat_json(self, messages: List[Dict[str, str]], **kwargs: Any) -> Optional[Dict[str, Any]]:
        """Request a JSON object answer. Returns None when parsing fails."""
        kwargs.setdefault("temperature", 0.0)
        kwargs.setdefault("response_format", {"type": "json_object"})
        raw = self.chat(messages, **kwargs)
        if not raw and kwargs.get("response_format") and self.last_error and "response_format" in self.last_error:
            # Some OpenAI-compatible servers do not support response_format.
            kwargs.pop("response_format", None)
            raw = self.chat(messages, **kwargs)
        return extract_json_object(raw)

    def chat_stream(self, messages: List[Dict[str, str]], **kwargs: Any) -> Iterator[str]:
        """Stream completion tokens. Yields nothing (and sets last_error) on failure."""
        self.last_error = None
        if not self.api_key:
            self.last_error = "OPENAI_API_KEY is not configured"
            return iter(())
        payload = self._payload(messages, kwargs)
        payload["stream"] = True
        response = self._post(payload, stream=True)
        if response is None:
            return iter(())

        def _iter() -> Iterator[str]:
            try:
                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line or not raw_line.startswith("data:"):
                        continue
                    data_str = raw_line[5:].strip()
                    if not data_str or data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        choice = (data.get("choices") or [{}])[0] or {}
                        delta = (choice.get("delta") or {}).get("content") or (
                            (choice.get("message") or {}).get("content")
                        )
                    except (ValueError, AttributeError, IndexError, TypeError):
                        continue
                    if delta:
                        yield str(delta)
            except requests.RequestException as exc:  # pragma: no cover - network
                self.last_error = f"Stream interrupted: {exc}"
            finally:
                response.close()

        return _iter()

    # -------------------------------------------------------------- internals
    def _payload(self, messages: List[Dict[str, str]], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": kwargs.get("model") or self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.2),
            "max_tokens": kwargs.get("max_tokens", self.default_max_tokens),
        }
        if kwargs.get("response_format"):
            payload["response_format"] = kwargs["response_format"]
        return payload

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.team:
            headers["OpenAI-Organization"] = self.team
        return headers

    def _post(self, payload: Dict[str, Any], *, stream: bool) -> Optional[requests.Response]:
        url = f"{self.base_url}/chat/completions"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                response = self._session.post(
                    url,
                    headers=self._headers(),
                    data=body,
                    timeout=(10, self.timeout),
                    stream=stream,
                )
            except requests.RequestException as exc:
                self.last_error = f"Request error: {exc}"
                if attempt + 1 < attempts:
                    self._sleep(attempt)
                    continue
                logger.warning("LLM request failed: %s", exc)
                return None

            if response.status_code < 400:
                return response

            detail = response.text[:400]
            response.close()
            self.last_error = f"HTTP {response.status_code}: {detail}"
            if response.status_code in RETRYABLE_STATUS and attempt + 1 < attempts:
                retry_after = response.headers.get("Retry-After")
                self._sleep(attempt, retry_after)
                continue
            logger.warning("LLM request rejected: %s", self.last_error)
            return None
        return None

    @staticmethod
    def _sleep(attempt: int, retry_after: Optional[str] = None) -> None:
        try:
            delay = float(retry_after) if retry_after else 0.0
        except ValueError:
            delay = 0.0
        delay = delay or min(8.0, 0.5 * (2**attempt)) + random.uniform(0, 0.25)
        time.sleep(min(delay, 10.0))

    @staticmethod
    def _parse_message_content(content: object) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            pieces: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in {"text", "output_text"} and item.get("text"):
                    pieces.append(str(item["text"]))
                elif isinstance(item, str):
                    pieces.append(item)
            return "\n".join(piece.strip() for piece in pieces if piece).strip()
        if content is None:
            return ""
        return str(content).strip()


def extract_json_object(value: str | None) -> Optional[Dict[str, Any]]:
    """Parse the first JSON object found in an LLM answer (tolerates ```json fences)."""
    if not value:
        return None
    text = value.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


llm_client = LLMClient()
