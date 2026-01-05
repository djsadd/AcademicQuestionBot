"""CLI helper for ingesting docs into the vector store."""
from pathlib import Path

from backend.rag.service import RAGService


def ingest(path: str) -> None:
    service = RAGService()
    file_path = Path(path)
    data = file_path.read_bytes()
    result = service.ingest_upload(filename=file_path.name, data=data)
    print(
        f"Ingested {result['chunks']} chunks from {result['file_name']} "
        f"(document_id={result['document_id']})"
    )


if __name__ == "__main__":
    ingest("data/sample.txt")
