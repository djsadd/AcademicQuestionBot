"""Document loading utilities."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .types import DocumentChunk


def load_file(
    path: Path,
    *,
    metadata: Optional[Dict[str, Any]] = None,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> List[DocumentChunk]:
    """Load a file, normalize text and split it into chunks."""
    if not path.exists():
        raise FileNotFoundError(f"Document {path} not found")

    text = _extract_text(path)
    base_metadata = {
        "file_name": path.name,
        "source_path": str(path),
        "suffix": path.suffix.lower(),
    }
    if metadata:
        base_metadata.update(metadata)

    return _chunk_text(
        text=text,
        base_metadata=base_metadata,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - informative guard
            raise RuntimeError("pypdf is required to parse PDF files") from exc
        reader = PdfReader(str(path))
        return "\n".join(filter(None, (page.extract_text() or "" for page in reader.pages)))
    if suffix in {".docx", ".doc"}:
        try:
            from docx import Document
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("python-docx is required to parse DOCX files") from exc
        document = Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    # fallback - treat as text
    return path.read_text(encoding="utf-8", errors="ignore")


def _chunk_text(
    *,
    text: str,
    base_metadata: Dict[str, Any],
    chunk_size: int,
    chunk_overlap: int,
) -> List[DocumentChunk]:
    text = text.strip()
    if not text:
        return []

    chunks: List[DocumentChunk] = []
    step = max(1, chunk_size - chunk_overlap)
    for index, start in enumerate(range(0, len(text), step)):
        chunk_text = text[start : start + chunk_size].strip()
        if not chunk_text:
            continue
        chunk_metadata = {
            **base_metadata,
            "chunk_index": index,
            "offset": start,
        }
        # Qdrant requires IDs to be UUIDs or integers, so use a uuid per chunk.
        chunk_id = str(uuid.uuid4())
        chunks.append(DocumentChunk(id=chunk_id, content=chunk_text, metadata=chunk_metadata))
    return chunks
