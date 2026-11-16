"""Centralised, typed application settings read from the environment.

Every module should read configuration through ``get_settings()`` instead of
calling ``os.getenv`` directly, so defaults live in one place and are easy to
audit. Settings are cached; call ``get_settings.cache_clear()`` in tests after
changing environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

try:  # Load .env early so every entrypoint (API, worker, bot) sees the same config.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - optional dependency
    pass


def _str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = os.getenv(name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    return value


def _float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _list(name: str, default: str = "") -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: _str("APP_ENV", "local"))
    log_level: str = field(default_factory=lambda: _str("LOG_LEVEL", "INFO").upper())
    log_json: bool = field(default_factory=lambda: _bool("LOG_JSON", False))

    # HTTP
    cors_origins: tuple[str, ...] = field(default_factory=lambda: _list("CORS_ORIGINS", "*"))
    public_rate_limit_per_minute: int = field(
        default_factory=lambda: _int("PUBLIC_RATE_LIMIT_PER_MINUTE", 20, minimum=0)
    )
    chat_rate_limit_per_minute: int = field(
        default_factory=lambda: _int("CHAT_RATE_LIMIT_PER_MINUTE", 60, minimum=0)
    )
    max_message_chars: int = field(default_factory=lambda: _int("CHAT_MAX_MESSAGE_CHARS", 4000, minimum=100))

    # Database
    postgres_dsn: str = field(default_factory=lambda: _str("POSTGRES_DSN"))
    db_pool_min: int = field(default_factory=lambda: _int("DB_POOL_MIN", 1, minimum=1))
    db_pool_max: int = field(default_factory=lambda: _int("DB_POOL_MAX", 10, minimum=1))

    # LLM
    openai_api_key: str = field(default_factory=lambda: _str("OPENAI_API_KEY"))
    openai_base_url: str = field(
        default_factory=lambda: _str("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    )
    openai_model: str = field(default_factory=lambda: _str("OPENAI_MODEL", "gpt-4o-mini"))
    openai_fast_model: str = field(default_factory=lambda: _str("OPENAI_FAST_MODEL"))
    openai_team: str = field(default_factory=lambda: _str("OPENAI_TEAM"))
    openai_max_tokens: int = field(default_factory=lambda: _int("OPENAI_MAX_TOKENS", 1600, minimum=1))
    openai_timeout: float = field(default_factory=lambda: _float("OPENAI_TIMEOUT", 45.0))
    openai_max_retries: int = field(default_factory=lambda: _int("OPENAI_MAX_RETRIES", 2, minimum=0))

    # Agent pipeline
    agent_timeout_seconds: float = field(default_factory=lambda: _float("AGENT_TIMEOUT_SECONDS", 40.0))
    rag_top_k: int = field(default_factory=lambda: _int("RAG_TOP_K", 5, minimum=1))
    rag_min_score: float = field(default_factory=lambda: _float("RAG_MIN_SCORE", 0.2))
    rag_compression_enabled: bool = field(default_factory=lambda: _bool("RAG_COMPRESSION_ENABLED", True))
    rag_compression_workers: int = field(default_factory=lambda: _int("RAG_COMPRESSION_WORKERS", 4, minimum=1))

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}

    @property
    def fast_model(self) -> str:
        """Model used for cheap routing / compression calls."""
        return self.openai_fast_model or self.openai_model


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
