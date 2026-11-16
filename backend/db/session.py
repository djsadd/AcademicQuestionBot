"""Shared PostgreSQL connection pool.

Before this module every DB helper opened a brand-new TCP connection (plus
auth handshake) for each query. A thread-safe pool removes that overhead; all
``backend.db.*`` modules borrow connections through ``get_connection()``.
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2 import pool as pg_pool

from ..core.config import get_settings

logger = logging.getLogger(__name__)

_pool: pg_pool.ThreadedConnectionPool | None = None
_pool_slots: threading.BoundedSemaphore | None = None
_pool_lock = threading.Lock()
POOL_WAIT_SECONDS = 15.0


def _get_pool() -> pg_pool.ThreadedConnectionPool:
    global _pool, _pool_slots
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            settings = get_settings()
            if not settings.postgres_dsn:
                raise RuntimeError("POSTGRES_DSN is not set.")
            max_conn = max(settings.db_pool_min, settings.db_pool_max)
            # psycopg2 pools raise instead of waiting when exhausted; the
            # semaphore makes callers queue for a free connection.
            _pool_slots = threading.BoundedSemaphore(max_conn)
            _pool = pg_pool.ThreadedConnectionPool(
                settings.db_pool_min,
                max_conn,
                settings.postgres_dsn,
                connect_timeout=5,
            )
            logger.info("PostgreSQL pool created (max=%s)", settings.db_pool_max)
    return _pool


@contextmanager
def get_connection() -> Iterator[psycopg2.extensions.connection]:
    """Borrow a pooled connection. Uncommitted work is rolled back on return."""
    pool = _get_pool()
    slots = _pool_slots
    if slots is not None and not slots.acquire(timeout=POOL_WAIT_SECONDS):
        raise RuntimeError("Database connection pool exhausted.")
    try:
        conn = pool.getconn()
    except Exception:
        if slots is not None:
            slots.release()
        raise
    broken = False
    try:
        yield conn
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        broken = True
        raise
    finally:
        if not conn.closed and not broken:
            try:
                conn.rollback()  # end any read transaction; no-op after commit
            except psycopg2.Error:
                broken = True
        pool.putconn(conn, close=broken or bool(conn.closed))
        if slots is not None:
            slots.release()


def ping() -> bool:
    """Lightweight readiness probe."""
    try:
        with get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
    except Exception:  # pragma: no cover - depends on infra
        return False


def close_pool() -> None:
    global _pool, _pool_slots
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None
            _pool_slots = None


# Backwards compatible alias for older imports.
get_session = get_connection
