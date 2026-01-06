"""FastAPI entrypoint for the Academic Question Bot backend."""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

if load_dotenv:
    load_dotenv()
else:
    logging.getLogger(__name__).warning("python-dotenv is not installed; .env not loaded.")

from .routers import admin, chat, rag, telegram
from ..db import rag_documents

app = FastAPI(title="Academic Question Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    """Placeholder for DB sessions, telemetry, etc."""
    # Start DB connections, load orchestrator, etc.
    rag_documents.ensure_tables()
    logger = logging.getLogger("rag")
    logger.info(
        "RAG config: QDRANT_URL=%s QDRANT_COLLECTION=%s RAG_STORAGE_PATH=%s "
        "QDRANT_STRICT=%s QDRANT_FALLBACK_ENABLED=%s",
        os.getenv("QDRANT_URL"),
        os.getenv("QDRANT_COLLECTION"),
        os.getenv("RAG_STORAGE_PATH"),
        os.getenv("QDRANT_STRICT"),
        os.getenv("QDRANT_FALLBACK_ENABLED"),
    )
    return None


app.include_router(chat.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(telegram.router, prefix="/api")
