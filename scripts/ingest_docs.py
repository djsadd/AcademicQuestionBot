"""CLI: bulk-load documents into the knowledge base.

Usage:
    python -m scripts.ingest_docs path/to/file.pdf path/to/folder [--category regulation] [--audience students]

Files are registered in Postgres exactly like UI uploads, then indexed
synchronously, so they appear in the admin "База знаний" page.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from backend.db import rag_documents
from backend.rag.loader import SUPPORTED_SUFFIXES
from backend.services import knowledge_base as kb


def iter_files(paths: list[str]):
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            yield from sorted(p for p in path.rglob("*") if p.suffix.lower() in SUPPORTED_SUFFIXES)
        elif path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--category", default="other")
    parser.add_argument("--audience", default="all")
    args = parser.parse_args()
    rag_documents.ensure_tables()

    for path in iter_files(args.paths):
        try:
            registered = kb.register_upload(
                filename=path.name,
                content_type=None,
                data=path.read_bytes(),
                metadata={"category": args.category, "audience": args.audience},
            )
        except kb.DuplicateDocumentError as exc:
            print(f"skip  {path.name}: уже загружен ({exc.existing.get('document_id')})")
            continue
        result = kb.index_document(registered["document_id"])
        print(f"{result['status']:<6} {path.name}: {result.get('chunks', 0)} фрагментов {result.get('error') or ''}")


if __name__ == "__main__":
    main()
