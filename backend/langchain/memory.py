"""Conversation memory skeleton."""
from typing import Dict, List


class ConversationMemory:
    """Stores simple chat history in memory."""

    def __init__(self) -> None:
        self.messages: List[Dict[str, str]] = []

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def dump(self) -> List[Dict[str, str]]:
        return self.messages
