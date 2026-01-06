"""Password reset tool for dean workflow (temporary fake data)."""
from __future__ import annotations

from typing import Dict
from uuid import uuid4


def reset_password(login: str) -> Dict[str, str]:
    """Return a fake password reset payload for now."""
    request_id = str(uuid4())
    return {
        "status": "queued",
        "login": login or "unknown",
        "request_id": request_id,
        "temporary_password": "Temp-1234",
        "expires_in_minutes": "30",
        "note": "fake response; real reset integration pending",
    }
