"""LLM client helpers for final response synthesis."""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

import requests


class LLMClient:
    """Lightweight REST client calling the OpenAI Chat API."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        self.team = os.getenv("OPENAI_TEAM")
        self.last_error: Optional[str] = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send chat completion request and return the assistant message."""
        self.last_error = None
        if not self.api_key:
            self.last_error = "OPENAI_API_KEY is not configured"
            return ""
        temperature = kwargs.get("temperature", 0.2)
        max_tokens = kwargs.get("max_tokens", 600)
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.team:
            headers["OpenAI-Organization"] = self.team
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                data=json.dumps(payload).encode("utf-8"),
                timeout=30,
            )
            raw_body = response.text
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:  # pragma: no cover - network errors
            self.last_error = f"Request error: {exc}"
            return ""
        except json.JSONDecodeError as exc:
            self.last_error = f"Invalid JSON response: {exc}"
            return ""

        try:
            choice = data["choices"][0]
            message = choice["message"].get("content")
        except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover
            self.last_error = f"Invalid response format: {exc}. Raw: {raw_body[:400]}"
            return ""

        parsed = self._parse_message_content(message)
        if parsed:
            return parsed

        self.last_error = f"LLM response did not contain text. Raw: {raw_body[:400]}"
        return ""

    def _parse_message_content(self, content: object) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            pieces: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") in {"text", "output_text"}:
                        text = item.get("text")
                        if text:
                            pieces.append(str(text))
                    elif item.get("type") == "tool_call":
                        call = item.get("content") or item.get("id")
                        if call:
                            pieces.append(str(call))
                elif isinstance(item, str):
                    pieces.append(item)
            return "\n".join(piece.strip() for piece in pieces if piece).strip()
        if content is None:
            return ""
        return str(content).strip()


llm_client = LLMClient()
