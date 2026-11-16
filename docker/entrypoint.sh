#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${QDRANT_URL:-}" ]]; then
python - <<'PY'
import os
import sys
import time
import urllib.error
import urllib.request

url = os.environ.get("QDRANT_URL", "").rstrip("/")
if not url:
    raise SystemExit(0)

timeout = float(os.environ.get("QDRANT_STARTUP_TIMEOUT", "60"))
deadline = time.time() + timeout
health_url = f"{url}/healthz"

while time.time() < deadline:
    try:
        with urllib.request.urlopen(health_url, timeout=2) as resp:
            if resp.status == 200:
                raise SystemExit(0)
    except Exception:
        time.sleep(1)

print(f"Qdrant not ready after {timeout:.0f}s: {health_url}", file=sys.stderr)
PY
fi

exec "$@"
