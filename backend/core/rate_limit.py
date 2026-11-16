"""Small in-process sliding-window rate limiter used as a FastAPI dependency.

It protects the LLM budget from abusive clients on public endpoints. The state
is per process; behind several API replicas put a shared limiter (nginx
``limit_req`` or Redis) in front as well.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable

from fastapi import HTTPException, Request

from .config import get_settings


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0, max_keys: int = 50_000) -> None:
        self.limit = limit
        self.window = window_seconds
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> tuple[bool, float]:
        """Register a hit. Returns (allowed, retry_after_seconds)."""
        if self.limit <= 0:
            return True, 0.0
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            bucket = self._hits.get(key)
            if bucket is None:
                if len(self._hits) >= self.max_keys:
                    self._evict(cutoff)
                bucket = self._hits[key] = deque()
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False, max(0.0, bucket[0] + self.window - now)
            bucket.append(now)
            return True, 0.0

    def _evict(self, cutoff: float) -> None:
        stale = [key for key, bucket in self._hits.items() if not bucket or bucket[-1] <= cutoff]
        for key in stale:
            del self._hits[key]
        if len(self._hits) >= self.max_keys:  # still full: drop oldest half
            for key in list(self._hits)[: self.max_keys // 2]:
                del self._hits[key]


def client_ip(request: Request) -> str:
    # X-Real-IP is set by our nginx from the TCP peer and cannot be forged by
    # the client; the left-most X-Forwarded-For entry can.
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, limit_getter: Callable[[], int]) -> Callable[[Request], None]:
    limiter: SlidingWindowLimiter | None = None

    def dependency(request: Request) -> None:
        nonlocal limiter
        if limiter is None:
            limiter = SlidingWindowLimiter(limit_getter())
        allowed, retry_after = limiter.hit(f"{scope}:{client_ip(request)}")
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Слишком много запросов. Попробуйте чуть позже.",
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

    return dependency


public_chat_limit = rate_limit("public", lambda: get_settings().public_rate_limit_per_minute)
private_chat_limit = rate_limit("private", lambda: get_settings().chat_rate_limit_per_minute)
