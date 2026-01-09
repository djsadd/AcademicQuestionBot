"""Platonus authentication via Playwright."""
from __future__ import annotations

from typing import Any

from playwright.sync_api import Error, TimeoutError, sync_playwright


def _extract_iin(info: Any) -> str | None:
    if not isinstance(info, dict):
        return None
    for key in ("iin", "IIN", "iinNumber", "iin_number"):
        value = info.get(key)
        if isinstance(value, (str, int)):
            return str(value).strip()
    return None


def auth(username: str, password: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(60000)

        page.goto("https://platonus.tau-edu.kz/mail?type=1", wait_until="domcontentloaded")

        try:
            page.wait_for_selector("#login_input", state="visible")
            page.fill("#login_input", username)
            page.fill("#pass_input", password)
        except TimeoutError as exc:
            browser.close()
            raise RuntimeError("Login or password input not available.") from exc

        page.click("#Submit1")
        page.wait_for_load_state("networkidle")

        cookies = page.context.cookies("https://platonus.tau-edu.kz")
        cookie_map = {cookie["name"]: cookie["value"] for cookie in cookies}
        cookie_header = "; ".join(
            f"{cookie['name']}={cookie['value']}" for cookie in cookies
        )
        user_agent = page.evaluate("() => navigator.userAgent")
        sid_value = cookie_map.get("plt_sid") or cookie_map.get("sid") or ""
        try:
            token_value = page.evaluate(
                "() => localStorage.getItem('token') || localStorage.getItem('access_token') || ''"
            )
        except Error:
            page.wait_for_load_state("domcontentloaded")
            token_value = page.evaluate(
                "() => localStorage.getItem('token') || localStorage.getItem('access_token') || ''"
            )

        headers = {
            "cookie": cookie_header,
            "sid": sid_value,
            "token": token_value,
            "user-agent": user_agent,
            "accept": "application/json",
            "accept-language": "kz",
        }
        person_id_response = page.request.get(
            "https://platonus.tau-edu.kz/rest/api/person/personID",
            headers=headers,
        )
        try:
            person_data = person_id_response.json()
        except ValueError:
            browser.close()
            raise RuntimeError("personID response is not JSON")
        person_id = person_data.get("personID")
        if not person_id:
            person_id_retry = page.request.get(
                "https://platonus.tau-edu.kz/rest/api/person/personID",
                headers=headers,
            )
            try:
                person_data_retry = person_id_retry.json()
            except ValueError:
                browser.close()
                raise RuntimeError("personID retry response is not JSON")
            person_id = person_data_retry.get("personID")

        roles_response = page.request.get(
            "https://platonus.tau-edu.kz/rest/api/person/roles",
            headers=headers,
        )
        try:
            roles_data = roles_response.json()
        except ValueError:
            browser.close()
            raise RuntimeError("roles response is not JSON")
        role_names = [
            str(role.get("name", "")).strip().lower()
            for role in roles_data
            if isinstance(role, dict)
        ]
        if "студент" in role_names:
            student_info_response = page.request.get(
                f"https://platonus.tau-edu.kz/rest/student/studentInfo/{person_id}/ru",
                headers=headers,
            )
            try:
                student_info = student_info_response.json()
            except ValueError:
                browser.close()
                raise RuntimeError("studentInfo response is not JSON")
            browser.close()
            return {
                "role": "студент",
                "info": student_info,
                "person_id": str(person_id) if person_id is not None else None,
                "iin": _extract_iin(student_info),
            }
        if "преподаватель" in role_names:
            employee_info_response = page.request.get(
                f"https://platonus.tau-edu.kz/rest/employee/employeeInfo/{person_id}/3/ru?dn=1",
                headers=headers,
            )
            try:
                employee_info = employee_info_response.json()
            except ValueError:
                browser.close()
                raise RuntimeError("employeeInfo response is not JSON")
            browser.close()
            return {
                "role": "преподаватель",
                "info": employee_info,
                "person_id": str(person_id) if person_id is not None else None,
                "iin": _extract_iin(employee_info),
            }
        if "деканат" in role_names:
            browser.close()
            raise RuntimeError("Выбран деканатский аккаунт для неверной роли.")
        browser.close()
        raise RuntimeError("Роль не определилась для текущего аккаунта.")


def fetch_token(username: str, password: str) -> dict:
    browser = None
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(60000)
            page.goto(
                "https://platonus.tau-edu.kz/mail?type=1", wait_until="domcontentloaded"
            )

            try:
                page.wait_for_selector("#login_input", state="visible")
                page.fill("#login_input", username)
                page.fill("#pass_input", password)
            except TimeoutError as exc:
                raise RuntimeError("Login or password input not available.") from exc

            page.click("#Submit1")
            page.wait_for_load_state("networkidle")

            cookies = page.context.cookies("https://platonus.tau-edu.kz")
            cookie_map = {cookie["name"]: cookie["value"] for cookie in cookies}
            cookie_header = "; ".join(
                f"{cookie['name']}={cookie['value']}" for cookie in cookies
            )
            user_agent = page.evaluate("() => navigator.userAgent")
            sid_value = cookie_map.get("plt_sid") or cookie_map.get("sid") or ""
            try:
                token_value = page.evaluate(
                    "() => localStorage.getItem('token') || localStorage.getItem('access_token') || ''"
                )
            except Error:
                page.wait_for_load_state("domcontentloaded")
                token_value = page.evaluate(
                    "() => localStorage.getItem('token') || localStorage.getItem('access_token') || ''"
                )

            return {
                "token": token_value,
                "cookie": cookie_header,
                "sid": sid_value,
                "user_agent": user_agent,
            }
        finally:
            if browser is not None:
                browser.close()
