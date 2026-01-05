"""FastAPI entrypoint for the Academic Question Bot backend."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import admin, chat, rag

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
    return None


app.include_router(chat.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
