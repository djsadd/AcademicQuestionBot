"""Document loading and structure-aware chunking.

Pipeline: extract text *with structure* (pages for PDF, headings and tables
for DOCX, markdown headings for text) → normalise (hyphenation, broken PDF
lines, page numbers) → split into semantic chunks along paragraph and
sentence boundaries with sentence-level overlap.

Every chunk carries ``page``/``page_end``, ``section`` and ``chunk_index`` so
answers can cite "Положение о GPA, стр. 4, раздел 3". Chunk ids are
deterministic (uuid5 of document id + index), so re-indexing a document
overwrites its points instead of duplicating them.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .types import DocumentChunk

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "1100"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "180"))
MIN_CHUNK_CHARS = 40
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}

_CHUNK_NAMESPACE = uuid.UUID("6f1f6d1e-3c7b-4a8e-9c55-2a1d0b7f4e10")


class DocumentParseError(ValueError):
    """Raised with a human-readable reason when a document cannot be indexed."""


@dataclass
class Segment:
    text: str
    page: Optional[int] = None
    section: Optional[str] = None
    is_heading: bool = False


# --------------------------------------------------------------------- public
def load_file(
    path: Path,
    *,
    metadata: Optional[Dict[str, Any]] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[DocumentChunk]:
    """Load a file and split it into structure-aware chunks."""
    if not path.exists():
        raise FileNotFoundError(f"Document {path} not found")

    segments = extract_segments(path)
    base_metadata: Dict[str, Any] = {
        "file_name": path.name,
        "source_path": str(path),
        "suffix": path.suffix.lower(),
        **(metadata or {}),
    }
    chunks = chunk_segments(segments, base_metadata=base_metadata, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        raise DocumentParseError(
            "Не удалось извлечь текст из документа. Если это скан, включите OCR (OCR_ENABLED=true) "
            "или загрузите версию с текстовым слоем."
        )
    return chunks


def chunk_id(document_id: str, index: int) -> str:
    return str(uuid.uuid5(_CHUNK_NAMESPACE, f"{document_id}:{index}"))


# ----------------------------------------------------------------- extraction
def extract_segments(path: Path) -> List[Segment]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix in {".txt", ".md"}:
        return _extract_text(path.read_text(encoding="utf-8", errors="ignore"))
    raise DocumentParseError(f"Формат {suffix or 'без расширения'} не поддерживается. Используйте PDF, DOCX, TXT или MD.")


def _extract_pdf(path: Path) -> List[Segment]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - informative guard
        raise RuntimeError("pypdf is required to parse PDF files") from exc

    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise DocumentParseError(f"PDF повреждён или защищён паролем: {exc}") from exc

    pages: List[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # pragma: no cover - broken page
            pages.append("")

    if sum(len(text.strip()) for text in pages) < 50 and _ocr_enabled():
        logger.info("PDF %s has no text layer; running OCR", path.name)
        pages = _ocr_pdf_pages(path) or pages

    segments: List[Segment] = []
    for number, raw in enumerate(pages, start=1):
        for block in _split_blocks(_normalize_pdf_text(raw)):
            segments.append(Segment(text=block, page=number, is_heading=_looks_like_heading(block)))
    return segments


def _extract_docx(path: Path) -> List[Segment]:
    try:
        from docx import Document
        from docx.oxml.ns import qn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("python-docx is required to parse DOCX files") from exc

    try:
        document = Document(str(path))
    except Exception as exc:
        raise DocumentParseError(f"Не удалось открыть DOCX: {exc}") from exc

    segments: List[Segment] = []
    paragraphs = {p._p: p for p in document.paragraphs}
    tables = {t._tbl: t for t in document.tables}
    # Walk the body in order so tables stay next to the text that introduces them.
    for element in document.element.body.iterchildren():
        if element.tag == qn("w:p") and element in paragraphs:
            paragraph = paragraphs[element]
            text = _clean_spaces(paragraph.text)
            if not text:
                continue
            style = (paragraph.style.name or "").lower() if paragraph.style is not None else ""
            heading = style.startswith(("heading", "заголовок", "title")) or _looks_like_heading(text)
            segments.append(Segment(text=text, is_heading=heading))
        elif element.tag == qn("w:tbl") and element in tables:
            for row in tables[element].rows:
                cells: List[str] = []
                for cell in row.cells:
                    value = _clean_spaces(cell.text)
                    if value and (not cells or cells[-1] != value):  # merged cells repeat text
                        cells.append(value)
                if cells:
                    segments.append(Segment(text=" | ".join(cells)))
    return segments


def _extract_text(text: str) -> List[Segment]:
    segments: List[Segment] = []
    for block in _split_blocks(text):
        heading = block.lstrip().startswith("#")
        cleaned = block.lstrip("# ").strip() if heading else block
        segments.append(Segment(text=cleaned, is_heading=heading or _looks_like_heading(cleaned)))
    return segments


def _ocr_enabled() -> bool:
    return os.getenv("OCR_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _ocr_pdf_pages(path: Path) -> List[str]:
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        logger.warning("OCR requested but dependencies are missing (pdf2image, pytesseract).")
        return []
    lang = os.getenv("OCR_LANG", "rus+eng")
    try:
        images = convert_from_path(str(path))
    except Exception:
        logger.warning("OCR failed to render PDF for %s", path)
        return []
    pages: List[str] = []
    for image in images:
        try:
            pages.append(pytesseract.image_to_string(image, lang=lang))
        except Exception:
            pages.append("")
    return pages


# -------------------------------------------------------------- normalisation
_PAGE_NUMBER_LINE = re.compile(r"^\s*(стр\.?|page|бет)?\s*\d{1,4}\s*(из\s*\d+)?\s*$", re.IGNORECASE)
_SENTENCE_END = re.compile(r"[.!?:;»\")]$")


def _clean_spaces(text: str) -> str:
    return re.sub(r"[ \t ]+", " ", text or "").strip()


def _normalize_pdf_text(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # word hyphenation across lines
    lines = [_clean_spaces(line) for line in text.split("\n")]
    lines = [line for line in lines if not _PAGE_NUMBER_LINE.match(line)]
    merged: List[str] = []
    for line in lines:
        if not line:
            if merged and merged[-1] != "":
                merged.append("")
            continue
        previous = merged[-1] if merged else ""
        # PDF extraction breaks lines mid-sentence: glue them back unless the
        # next line looks like a new list item or heading.
        if (
            previous
            and not _SENTENCE_END.search(previous)
            and not _looks_like_list_item(line)
            and not _looks_like_heading(previous)
            and line[:1].islower()
        ):
            merged[-1] = f"{previous} {line}"
        else:
            merged.append(line)
    return "\n".join(merged)


def _split_blocks(text: str) -> List[str]:
    blocks: List[str] = []
    for raw in re.split(r"\n\s*\n|\n(?=\s*(?:\d+(?:\.\d+)*[.)]|[-•–]|Статья|Глава|Раздел)\s)", text or ""):
        block = _clean_spaces(raw.replace("\n", " "))
        if block:
            blocks.append(block)
    return blocks


def _looks_like_list_item(line: str) -> bool:
    return bool(re.match(r"^\s*(\d+(\.\d+)*[.)]|[-•–]|[а-яa-z]\))\s", line, re.IGNORECASE))


def _looks_like_heading(text: str) -> bool:
    candidate = text.strip()
    if not candidate or len(candidate) > 120:
        return False
    if re.match(r"^(глава|раздел|статья|часть|приложение|бөлім|тарау|chapter|section|article)\b", candidate, re.IGNORECASE):
        return True
    if re.match(r"^\d+(\.\d+)*\.?\s+[А-ЯЁA-ZӘІҢҒҮҰҚӨҺ]", candidate) and not _SENTENCE_END.search(candidate) and len(candidate) < 90:
        return True
    letters = [ch for ch in candidate if ch.isalpha()]
    return len(letters) >= 4 and all(ch.isupper() for ch in letters)


# ------------------------------------------------------------------- chunking
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[«\"(]?[А-ЯЁA-ZӘІҢҒҮҰҚӨҺ0-9])")


def _sentences(text: str, limit: int) -> List[str]:
    parts = [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]
    result: List[str] = []
    for part in parts:
        while len(part) > limit:  # pathological run-on text: hard split on a space
            cut = part.rfind(" ", 0, limit)
            cut = cut if cut > limit // 2 else limit
            result.append(part[:cut].strip())
            part = part[cut:].strip()
        if part:
            result.append(part)
    return result


def chunk_segments(
    segments: Iterable[Segment],
    *,
    base_metadata: Dict[str, Any],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[DocumentChunk]:
    document_id = str(base_metadata.get("document_id") or uuid.uuid4().hex)
    chunks: List[DocumentChunk] = []
    buffer: List[str] = []
    buffer_len = 0
    first_page: Optional[int] = None
    last_page: Optional[int] = None
    section: Optional[str] = None
    buffer_section: Optional[str] = None

    def flush(keep_overlap: bool) -> None:
        nonlocal buffer, buffer_len, first_page, buffer_section
        text = " ".join(buffer).strip()
        if len(text) >= MIN_CHUNK_CHARS or (text and not chunks):
            index = len(chunks)
            metadata = {**base_metadata, "chunk_index": index, "char_count": len(text)}
            if first_page is not None:
                metadata["page"] = first_page
                metadata["page_end"] = last_page
            if buffer_section:
                metadata["section"] = buffer_section
            chunks.append(DocumentChunk(id=chunk_id(document_id, index), content=text, metadata=metadata))
        overlap: List[str] = []
        if keep_overlap and chunk_overlap > 0:
            size = 0
            for sentence in reversed(buffer):
                if size + len(sentence) > chunk_overlap:
                    break
                overlap.insert(0, sentence)
                size += len(sentence) + 1
        buffer = overlap
        buffer_len = sum(len(item) + 1 for item in overlap)
        first_page = last_page if overlap else None
        buffer_section = section

    for segment in segments:
        if segment.is_heading:
            if buffer_len >= chunk_size * 0.35:
                flush(keep_overlap=False)
            section = segment.text[:150]
            if not buffer:
                buffer_section = section
        for sentence in _sentences(segment.text, chunk_size):
            if buffer_len + len(sentence) > chunk_size and buffer:
                flush(keep_overlap=True)
            if not buffer:
                buffer_section = section
            if first_page is None:
                first_page = segment.page
            if segment.page is not None:
                last_page = segment.page
            buffer.append(sentence)
            buffer_len += len(sentence) + 1
    if buffer:
        flush(keep_overlap=False)
    return chunks


def embedding_text(chunk: DocumentChunk) -> str:
    """Text actually embedded: document title and section give the vector context."""
    metadata = chunk.metadata or {}
    prefix = [str(value) for value in (metadata.get("title") or metadata.get("original_file"), metadata.get("section")) if value]
    return ("\n".join(prefix) + "\n" + chunk.content) if prefix else chunk.content
