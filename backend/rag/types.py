"""Common dataclasses describing RAG artifacts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class DocumentChunk:
    """Chunk of text extracted from a document."""

    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
