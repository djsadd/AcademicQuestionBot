"""Chat analytics persistence for web/API chat."""
from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2


@contextmanager
def _get_connection() -> Iterator[psycopg2.extensions.connection]:
    dsn = os.getenv("POSTGRES_DSN", "").strip()
    if not dsn:
        raise SystemExit("POSTGRES_DSN is not set.")
    conn = psycopg2.connect(dsn)
    try:
        yield conn
    finally:
        conn.close()


def ensure_tables() -> None:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_analytics (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                telegram_id BIGINT,
                person_id TEXT,
                channel TEXT,
                query TEXT,
                response TEXT,
                llm_model TEXT,
                llm_used BOOLEAN,
                llm_error TEXT,
                intents JSONB,
                agents JSONB,
                trace JSONB,
                metadata JSONB,
                request_payload JSONB,
                response_payload JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cursor.execute(
            """
            ALTER TABLE chat_analytics
            ADD COLUMN IF NOT EXISTS request_payload JSONB;
            """
        )
        cursor.execute(
            """
            ALTER TABLE chat_analytics
            ADD COLUMN IF NOT EXISTS response_payload JSONB;
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_analytics_session
            ON chat_analytics (session_id, created_at DESC);
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_analytics_telegram
            ON chat_analytics (telegram_id, created_at DESC);
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_analytics_person
            ON chat_analytics (person_id, created_at DESC);
            """
        )
        conn.commit()


def save_chat_event(
    *,
    session_id: str | None,
    telegram_id: int | None,
    person_id: str | None,
    channel: str | None,
    query: str | None,
    response: str | None,
    llm_model: str | None,
    llm_used: bool | None,
    llm_error: str | None,
    intents: Any,
    agents: Any,
    trace: Any,
    metadata: dict[str, Any] | None,
    request_payload: dict[str, Any] | None = None,
    response_payload: dict[str, Any] | None = None,
) -> str:
    event_id = uuid.uuid4().hex
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chat_analytics (
                id,
                session_id,
                telegram_id,
                person_id,
                channel,
                query,
                response,
                llm_model,
                llm_used,
                llm_error,
                intents,
                agents,
                trace,
                metadata,
                request_payload,
                response_payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                event_id,
                session_id,
                telegram_id,
                person_id,
                channel,
                query,
                response,
                llm_model,
                llm_used,
                llm_error,
                json.dumps(intents, ensure_ascii=False),
                json.dumps(agents, ensure_ascii=False),
                json.dumps(trace, ensure_ascii=False),
                json.dumps(metadata or {}, ensure_ascii=False),
                json.dumps(request_payload or {}, ensure_ascii=False),
                json.dumps(response_payload or {}, ensure_ascii=False),
            ),
        )
        conn.commit()
    return event_id


def _auth_mode_sql() -> str:
    return """
        COALESCE(
            NULLIF(metadata->'request'->>'auth_mode', ''),
            CASE
                WHEN telegram_id IS NOT NULL OR person_id IS NOT NULL THEN 'authenticated'
                ELSE 'anonymous'
            END
        )
    """


def _build_admin_filters(
    *,
    auth_mode: str | None = None,
    search: str | None = None,
) -> tuple[str, list[Any]]:
    filters: list[str] = []
    params: list[Any] = []

    auth_mode_value = (auth_mode or "").strip().lower()
    if auth_mode_value in {"anonymous", "authenticated"}:
        filters.append(f"{_auth_mode_sql()} = %s")
        params.append(auth_mode_value)

    search_value = (search or "").strip()
    if search_value:
        like = f"%{search_value}%"
        filters.append(
            """
            (
                COALESCE(query, '') ILIKE %s
                OR COALESCE(response, '') ILIKE %s
                OR COALESCE(person_id, '') ILIKE %s
                OR COALESCE(channel, '') ILIKE %s
                OR COALESCE(metadata->'user'->>'fullname', '') ILIKE %s
                OR COALESCE(metadata->'user'->>'email', '') ILIKE %s
                OR COALESCE(session_id, '') ILIKE %s
                OR COALESCE(telegram_id::text, '') ILIKE %s
            )
            """
        )
        params.extend([like, like, like, like, like, like, like, like])

    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
    return where_sql, params


def fetch_admin_summary() -> dict[str, Any]:
    auth_mode_sql = _auth_mode_sql()
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                COUNT(*) AS total_events,
                COUNT(DISTINCT COALESCE(NULLIF(session_id, ''), id)) AS total_sessions,
                COUNT(*) FILTER (WHERE {auth_mode_sql} = 'anonymous') AS anonymous_events,
                COUNT(*) FILTER (WHERE {auth_mode_sql} = 'authenticated') AS authenticated_events,
                COUNT(DISTINCT COALESCE(NULLIF(session_id, ''), id))
                    FILTER (WHERE {auth_mode_sql} = 'anonymous') AS anonymous_sessions,
                COUNT(DISTINCT COALESCE(NULLIF(session_id, ''), id))
                    FILTER (WHERE {auth_mode_sql} = 'authenticated') AS authenticated_sessions,
                COUNT(DISTINCT COALESCE(telegram_id::text, person_id))
                    FILTER (WHERE {auth_mode_sql} = 'authenticated') AS unique_users,
                MAX(created_at) AS last_event_at
            FROM chat_analytics;
            """
        )
        row = cursor.fetchone()

    if not row:
        return {
            "total_events": 0,
            "total_sessions": 0,
            "anonymous_events": 0,
            "authenticated_events": 0,
            "anonymous_sessions": 0,
            "authenticated_sessions": 0,
            "unique_users": 0,
            "last_event_at": None,
        }

    return {
        "total_events": row[0] or 0,
        "total_sessions": row[1] or 0,
        "anonymous_events": row[2] or 0,
        "authenticated_events": row[3] or 0,
        "anonymous_sessions": row[4] or 0,
        "authenticated_sessions": row[5] or 0,
        "unique_users": row[6] or 0,
        "last_event_at": row[7].isoformat() if row[7] else None,
    }


def list_chat_sessions(
    *,
    page: int = 1,
    per_page: int = 20,
    auth_mode: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    safe_page = max(page, 1)
    safe_per_page = max(1, min(per_page, 100))
    offset = (safe_page - 1) * safe_per_page
    where_sql, params = _build_admin_filters(auth_mode=auth_mode, search=search)

    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            f"""
            WITH grouped AS (
                SELECT
                    COALESCE(NULLIF(session_id, ''), id) AS session_key,
                    MAX(session_id) AS session_id,
                    MAX(channel) AS channel,
                    MAX(telegram_id) AS telegram_id,
                    MAX(person_id) AS person_id,
                    MAX(metadata->'user'->>'fullname') AS full_name,
                    MAX(metadata->'user'->>'email') AS email,
                    {_auth_mode_sql()} AS auth_mode,
                    COUNT(*) AS event_count,
                    MIN(created_at) AS started_at,
                    MAX(created_at) AS updated_at,
                    (ARRAY_REMOVE(ARRAY_AGG(query ORDER BY created_at DESC), NULL))[1] AS last_query,
                    (ARRAY_REMOVE(ARRAY_AGG(response ORDER BY created_at DESC), NULL))[1] AS last_response,
                    COALESCE(
                        JSON_AGG(
                            JSON_BUILD_OBJECT(
                                'query', query,
                                'created_at', created_at
                            )
                            ORDER BY created_at DESC
                        ) FILTER (WHERE query IS NOT NULL AND query <> ''),
                        '[]'::json
                    ) AS questions
                FROM chat_analytics
                {where_sql}
                GROUP BY COALESCE(NULLIF(session_id, ''), id), {_auth_mode_sql()}
            )
            SELECT
                session_key,
                session_id,
                channel,
                telegram_id,
                person_id,
                full_name,
                email,
                auth_mode,
                event_count,
                started_at,
                updated_at,
                last_query,
                last_response,
                questions
            FROM grouped
            ORDER BY updated_at DESC
            LIMIT %s OFFSET %s;
            """,
            [*params, safe_per_page, offset],
        )
        rows = cursor.fetchall()

        cursor.execute(
            f"""
            SELECT COUNT(*) FROM (
                SELECT 1
                FROM chat_analytics
                {where_sql}
                GROUP BY COALESCE(NULLIF(session_id, ''), id), {_auth_mode_sql()}
            ) AS grouped_count;
            """,
            params,
        )
        total = cursor.fetchone()[0] or 0

    items = []
    for row in rows:
        items.append(
            {
                "session_key": row[0],
                "session_id": row[1] or row[0],
                "channel": row[2],
                "telegram_id": row[3],
                "person_id": row[4],
                "full_name": row[5],
                "email": row[6],
                "auth_mode": row[7],
                "event_count": row[8],
                "started_at": row[9].isoformat() if row[9] else None,
                "updated_at": row[10].isoformat() if row[10] else None,
                "last_query": row[11],
                "last_response": row[12],
                "questions": row[13] or [],
            }
        )

    pages = (total + safe_per_page - 1) // safe_per_page if total else 0
    return {
        "items": items,
        "page": safe_page,
        "per_page": safe_per_page,
        "total": total,
        "pages": pages,
    }


def list_chat_users(*, limit: int = 100) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 200))

    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                COALESCE(telegram_id::text, person_id, metadata->'user'->>'email', metadata->'user'->>'fullname', id) AS user_key,
                MAX(telegram_id) AS telegram_id,
                MAX(person_id) AS person_id,
                MAX(metadata->'user'->>'fullname') AS full_name,
                MAX(metadata->'user'->>'email') AS email,
                MAX(metadata->'user'->>'role') AS role,
                COUNT(*) AS event_count,
                COUNT(DISTINCT COALESCE(NULLIF(session_id, ''), id)) AS session_count,
                MIN(created_at) AS first_seen,
                MAX(created_at) AS last_seen,
                (ARRAY_REMOVE(ARRAY_AGG(query ORDER BY created_at DESC), NULL))[1] AS last_query,
                COALESCE(
                    JSON_AGG(
                        JSON_BUILD_OBJECT(
                            'query', query,
                            'created_at', created_at
                        )
                        ORDER BY created_at DESC
                    ) FILTER (WHERE query IS NOT NULL AND query <> ''),
                    '[]'::json
                ) AS recent_queries
            FROM chat_analytics
            WHERE {_auth_mode_sql()} = 'authenticated'
            GROUP BY COALESCE(telegram_id::text, person_id, metadata->'user'->>'email', metadata->'user'->>'fullname', id)
            ORDER BY last_seen DESC
            LIMIT %s;
            """,
            (safe_limit,),
        )
        rows = cursor.fetchall()

    items = []
    for row in rows:
        items.append(
            {
                "user_key": row[0],
                "telegram_id": row[1],
                "person_id": row[2],
                "full_name": row[3],
                "email": row[4],
                "role": row[5],
                "event_count": row[6],
                "session_count": row[7],
                "first_seen": row[8].isoformat() if row[8] else None,
                "last_seen": row[9].isoformat() if row[9] else None,
                "last_query": row[10],
                "recent_queries": row[11] or [],
            }
        )

    return {"items": items, "limit": safe_limit}


def get_session_events(session_key: str) -> dict[str, Any]:
    normalized_key = (session_key or "").strip()
    if not normalized_key:
        return {"session_key": session_key, "items": []}

    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                id,
                COALESCE(NULLIF(session_id, ''), id) AS session_key,
                session_id,
                channel,
                telegram_id,
                person_id,
                {_auth_mode_sql()} AS auth_mode,
                query,
                response,
                llm_model,
                llm_used,
                llm_error,
                intents,
                agents,
                trace,
                metadata,
                request_payload,
                response_payload,
                created_at
            FROM chat_analytics
            WHERE COALESCE(NULLIF(session_id, ''), id) = %s
            ORDER BY created_at DESC;
            """,
            (normalized_key,),
        )
        rows = cursor.fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "id": row[0],
                "session_key": row[1],
                "session_id": row[2] or row[1],
                "channel": row[3],
                "telegram_id": row[4],
                "person_id": row[5],
                "auth_mode": row[6],
                "query": row[7],
                "response": row[8],
                "llm_model": row[9],
                "llm_used": row[10],
                "llm_error": row[11],
                "intents": row[12] or [],
                "agents": row[13] or [],
                "trace": row[14] or [],
                "metadata": row[15] or {},
                "request_payload": row[16] or {},
                "response_payload": row[17] or {},
                "created_at": row[18].isoformat() if row[18] else None,
            }
        )

    return {"session_key": normalized_key, "items": items}


def fetch_chat_history(telegram_id: int) -> list[dict[str, Any]]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT session_id, query, response, created_at
            FROM chat_analytics
            WHERE telegram_id = %s AND session_id IS NOT NULL
            ORDER BY created_at ASC;
            """,
            (telegram_id,),
        )
        rows = cursor.fetchall()

    sessions: dict[str, dict[str, Any]] = {}
    for session_id, query, response, created_at in rows:
        if session_id not in sessions:
            sessions[session_id] = {
                "session_id": session_id,
                "title": "",
                "created_at": created_at.isoformat(),
                "updated_at": created_at.isoformat(),
                "messages": [],
            }
        session = sessions[session_id]
        session["updated_at"] = created_at.isoformat()
        if query:
            session["messages"].append(
                {
                    "id": uuid.uuid4().hex,
                    "role": "user",
                    "content": query,
                    "created_at": created_at.isoformat(),
                }
            )
            if not session["title"]:
                session["title"] = query
        if response:
            session["messages"].append(
                {
                    "id": uuid.uuid4().hex,
                    "role": "bot",
                    "content": response,
                    "created_at": created_at.isoformat(),
                }
            )

    sessions_list = list(sessions.values())
    sessions_list.sort(key=lambda item: item["updated_at"], reverse=True)
    return sessions_list


def fetch_session_history(session_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT query, response, created_at
            FROM chat_analytics
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s;
            """,
            (session_id, limit),
        )
        rows = cursor.fetchall()

    rows.reverse()
    history: list[dict[str, Any]] = []
    for query, response, created_at in rows:
        timestamp = created_at.isoformat()
        if query:
            history.append(
                {"role": "user", "content": query, "created_at": timestamp}
            )
        if response:
            history.append(
                {"role": "assistant", "content": response, "created_at": timestamp}
            )
    return history


def fetch_public_chat_session(session_id: str) -> dict[str, Any] | None:
    with _get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT query, response, created_at
            FROM chat_analytics
            WHERE session_id = %s
              AND telegram_id IS NULL
              AND person_id IS NULL
              AND (
                    channel = 'public_web'
                    OR (metadata->'request'->>'auth_mode') = 'anonymous'
                  )
            ORDER BY created_at ASC;
            """,
            (session_id,),
        )
        rows = cursor.fetchall()

    if not rows:
        return None

    first_created_at = rows[0][2]
    last_created_at = rows[-1][2]
    session: dict[str, Any] = {
        "session_id": session_id,
        "title": "",
        "created_at": first_created_at.isoformat(),
        "updated_at": last_created_at.isoformat(),
        "messages": [],
    }

    for query, response, created_at in rows:
        timestamp = created_at.isoformat()
        if query:
            session["messages"].append(
                {
                    "id": uuid.uuid4().hex,
                    "role": "user",
                    "content": query,
                    "created_at": timestamp,
                }
            )
            if not session["title"]:
                session["title"] = query
        if response:
            session["messages"].append(
                {
                    "id": uuid.uuid4().hex,
                    "role": "bot",
                    "content": response,
                    "created_at": timestamp,
                }
            )

    return session
