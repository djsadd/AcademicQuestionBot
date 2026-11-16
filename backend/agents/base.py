"""Abstract building blocks for concrete agents.

Contract
--------
* ``run(payload)`` receives the shared request context and returns an
  ``AgentResult`` (a dict). Conventional keys:

  - ``answer``          – evidence or a ready answer (str)
  - ``context``         – list of ``{"content", "metadata", "score"}`` chunks
  - ``citations``       – list of ``{"file_name", "source_path", "chunk_index"}``
  - ``direct_response`` – True when ``answer`` is final and must bypass synthesis
  - ``tool_data``       – raw structured data for analytics / UI

* ``uses_rag`` tells the pipeline to retrieve documents once, up-front, and
  share them through ``payload["retrieved_context"]`` so several agents never
  hit the vector store for the same query.
* Agents must be side-effect free with respect to each other: the pipeline runs
  independent agents concurrently.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class AgentResult(Dict[str, Any]):
    """Dict subclass so results stay JSON-serialisable."""


class BaseAgent(ABC):
    """Defines the envelope every agent adheres to."""

    name: str
    uses_rag: bool = False

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    async def run(self, payload: Dict[str, Any]) -> AgentResult:
        """Execute the agent's core logic."""

    async def format_response(self, result: AgentResult) -> AgentResult:
        """Hook for post-processing responses before returning upstream."""
        return result


def shared_context(payload: Dict[str, Any]) -> List[Dict[str, Any]] | None:
    """Return documents pre-fetched by the pipeline, or None when not available."""
    value = payload.get("retrieved_context")
    return value if isinstance(value, list) else None


def citations_from_context(context: List[Dict[str, Any]], limit: int = 4) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for item in context:
        metadata = item.get("metadata") or {}
        key = (metadata.get("file_name") or metadata.get("original_file"), metadata.get("chunk_index"))
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "file_name": metadata.get("file_name") or metadata.get("original_file"),
                "source_path": metadata.get("source_path"),
                "chunk_index": metadata.get("chunk_index"),
                "score": item.get("score"),
            }
        )
        if len(citations) >= limit:
            break
    return citations
