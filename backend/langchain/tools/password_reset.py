"""Password reset tool for the dean workflow.

There is no write-access integration with Platonus yet, so the tool must not
pretend to reset anything (the previous stub showed users a fake temporary
password). It returns verified self-service instructions instead and keeps a
request id for analytics.
"""
from __future__ import annotations

import os
from typing import Dict
from uuid import uuid4

SUPPORT_CONTACT = os.getenv("IT_SUPPORT_CONTACT", "IT-отдел университета или деканат")
RESET_URL = os.getenv("PLATONUS_RESET_URL", "")


def reset_password(login: str) -> Dict[str, str]:
    link = f'<a href="{RESET_URL}">{RESET_URL}</a>' if RESET_URL else "страницу входа Platonus"
    message = (
        "<p>Автоматический сброс пароля пока недоступен через бота.</p>"
        "<ol>"
        f"<li>Откройте {link} и воспользуйтесь функцией восстановления пароля, если она доступна.</li>"
        f"<li>Если восстановить доступ не получилось, обратитесь в {SUPPORT_CONTACT} с удостоверением личности.</li>"
        "<li>Никому не сообщайте свой пароль — сотрудники университета никогда его не спрашивают.</li>"
        "</ol>"
    )
    return {
        "status": "manual_required",
        "login": login or "unknown",
        "request_id": uuid4().hex,
        "message": message,
    }
