"""Test isolation: never touch real infrastructure or paid APIs.

Environment variables are set before any backend module is imported, so the
values in a developer's ``.env`` (which ``load_dotenv`` would otherwise load)
cannot leak into tests.
"""
from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="aqb-tests-")

os.environ.update(
    {
        "APP_ENV": "test",
        "OPENAI_API_KEY": "",
        "POSTGRES_DSN": "",
        "RAG_STORAGE_PATH": os.path.join(_TMP, "documents"),
        "QDRANT_URL": "http://127.0.0.1:1",
        "QDRANT_STRICT": "false",
        "QDRANT_FALLBACK_ENABLED": "true",
        "QDRANT_RETRY_ATTEMPTS": "1",
        "QDRANT_RETRY_DELAY": "0",
    }
)
