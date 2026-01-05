"""User context helpers."""
from typing import Dict


def build_context(user_id: int) -> Dict[str, str]:
    return {"university": "Demo University", "language": "ru"}
