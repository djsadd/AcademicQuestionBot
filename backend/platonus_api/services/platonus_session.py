"""Background Platonus token refresh."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

from fastapi.concurrency import run_in_threadpool

from .platonus_auth import fetch_token

logger = logging.getLogger("platonus_token")


def _load_credentials() -> tuple[str, str]:
    login = (
        os.getenv("PLATONUS_LOGIN")
        or os.getenv("PLATONUS_ADMIN_LOGIN")
        or os.getenv("platonus_admin_login")
        or ""
    ).strip()
    password = (
        os.getenv("PLATONUS_PASSWORD")
        or os.getenv("PLATONUS_ADMIN_PASSWORD")
        or os.getenv("platonus_admin_password")
        or ""
    ).strip()
    return login, password


class PlatonusTokenManager:
    def __init__(self, refresh_seconds: int = 1800) -> None:
        self._refresh_seconds = refresh_seconds
        self._task: Optional[asyncio.Task] = None
        self._token = ""
        self._cookie = ""
        self._sid = ""
        self._user_agent = ""
        self._last_login = 0.0

    def snapshot(self) -> dict:
        return {
            "token": self._token,
            "cookie": self._cookie,
            "sid": self._sid,
            "user_agent": self._user_agent,
            "last_login": self._last_login,
        }

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name="platonus-token-refresh")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        while True:
            await self._refresh_once()
            await asyncio.sleep(self._refresh_seconds)

    async def _refresh_once(self) -> None:
        login, password = _load_credentials()
        if not login or not password:
            logger.warning("Platonus credentials missing; token refresh skipped.")
            return
        try:
            result = await run_in_threadpool(fetch_token, login, password)
        except Exception:
            logger.exception("Platonus token refresh failed.")
            return

        token = str(result.get("token", "")).strip()
        if not token:
            logger.warning("Platonus token was empty after login.")
            return

        self._token = token
        self._cookie = str(result.get("cookie", "")).strip()
        self._sid = str(result.get("sid", "")).strip()
        self._user_agent = str(result.get("user_agent", "")).strip()
        self._last_login = time.time()
        logger.info("Platonus token refreshed.")


token_manager = PlatonusTokenManager()


def get_platonus_token() -> str:
    return token_manager.snapshot().get("token", "")
