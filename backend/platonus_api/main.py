"""FastAPI microservice exposing Platonus endpoints."""
from __future__ import annotations

import logging
import time

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

from .services.platonus_api import fetch_student_academic_calendar
from .services.platonus_auth import auth as platonus_auth
from .services.platonus_session import token_manager

if load_dotenv:
    load_dotenv()
else:
    logging.getLogger(__name__).warning("python-dotenv is not installed; .env not loaded.")

app = FastAPI(title="Platonus API")


class PlatonusAuthPayload(BaseModel):
    login: str
    password: str


@app.on_event("startup")
async def startup_event() -> None:
    await token_manager.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await token_manager.stop()


@app.get("/health")
async def healthcheck() -> dict:
    return {"status": "ok"}


@app.get("/session")
async def platonus_session_status() -> dict:
    snapshot = token_manager.snapshot()
    last_login = snapshot.get("last_login") or 0.0
    now = time.time()
    age_seconds = int(max(0.0, now - last_login)) if last_login else None
    return {
        "token_present": bool(snapshot.get("token")),
        "cookie_present": bool(snapshot.get("cookie")),
        "sid_present": bool(snapshot.get("sid")),
        "user_agent_present": bool(snapshot.get("user_agent")),
        "last_login": int(last_login) if last_login else None,
        "age_seconds": age_seconds,
        "refresh_seconds": 1800,
    }


@app.get("/student-academic-calendar/{person_id}")
async def student_academic_calendar(person_id: str, lang: str = "ru") -> dict:
    return fetch_student_academic_calendar(person_id, lang)


@app.post("/auth")
async def authenticate(payload: PlatonusAuthPayload) -> dict:
    if not payload.login.strip() or not payload.password.strip():
        raise HTTPException(status_code=400, detail="Login and password required.")
    try:
        result = await run_in_threadpool(platonus_auth, payload.login, payload.password)
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        logging.getLogger(__name__).exception("Platonus auth failed: %s", exc)
        raise HTTPException(status_code=500, detail="Platonus auth failed.") from exc

    return {
        "status": "ok",
        "role": result.get("role"),
        "person_id": result.get("person_id"),
        "iin": result.get("iin"),
    }
