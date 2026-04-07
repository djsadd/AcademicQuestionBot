"""HTTP client for Platonus microservice."""
from __future__ import annotations

import os
from typing import Any, Dict

import requests


def _get_platonus_api_url() -> str:
    return os.getenv("PLATONUS_API_URL", "").strip()


def authenticate_platonus_user(login: str, password: str) -> Dict[str, Any]:
    base_url = _get_platonus_api_url()
    if not base_url:
        raise RuntimeError("PLATONUS_API_URL is not configured.")

    url = f"{base_url.rstrip('/')}/auth"
    try:
        response = requests.post(
            url,
            json={"login": login, "password": password},
            timeout=60,
        )
        if response.status_code == 401:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = None
            raise RuntimeError(detail or "Platonus authorization failed.")
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Platonus API request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Platonus API returned invalid JSON.") from exc

    if payload.get("status") != "ok":
        detail = payload.get("detail") or "Platonus authorization failed."
        raise RuntimeError(str(detail))

    return payload


def verify_platonus_credentials(login: str, password: str) -> Dict[str, Any]:
    normalized_login = login.strip()
    normalized_password = password.strip()
    if not normalized_login or not normalized_password:
        raise RuntimeError("Login and password required.")

    try:
        response = requests.post(
            "https://platonus.tau-edu.kz/rest/api/login",
            json={
                "login": normalized_login,
                "password": normalized_password,
                "iin": None,
                "icNumber": None,
                "authForDeductedStudentsAndGraduates": "false",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Platonus login request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Platonus login returned invalid JSON.") from exc

    if response.status_code >= 400:
        detail = payload.get("message") or payload.get("detail") or "Platonus authorization failed."
        raise RuntimeError(str(detail))

    if str(payload.get("login_status") or "").strip().lower() != "success":
        detail = payload.get("message") or payload.get("detail") or "Platonus authorization failed."
        raise RuntimeError(str(detail))

    headers = {
        "token": str(payload.get("auth_token") or "").strip(),
        "sid": str(payload.get("sid") or "").strip(),
        "accept": "application/json",
        "accept-language": "kz",
    }

    person_id_response = requests.get(
        "https://platonus.tau-edu.kz/rest/api/person/personID",
        headers=headers,
        timeout=30,
    )
    try:
        person_data = person_id_response.json()
    except ValueError as exc:
        raise RuntimeError("personID response is not JSON") from exc

    person_id = person_data.get("personID")
    if not person_id:
        person_id_retry_response = requests.get(
            "https://platonus.tau-edu.kz/rest/api/person/personID",
            headers=headers,
            timeout=30,
        )
        try:
            person_data_retry = person_id_retry_response.json()
        except ValueError as exc:
            raise RuntimeError("personID retry response is not JSON") from exc
        person_id = person_data_retry.get("personID")

    payload["personID"] = person_id
    return payload


def fetch_student_academic_calendar(person_id: str, lang: str = "ru") -> Dict[str, Any]:
    base_url = _get_platonus_api_url()
    if not base_url:
        raise RuntimeError("PLATONUS_API_URL is not configured.")

    url = f"{base_url.rstrip('/')}/student-academic-calendar/{person_id}"
    try:
        response = requests.get(url, params={"lang": lang}, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Platonus API request failed: {exc}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("Platonus API returned invalid JSON.") from exc


def fetch_platonus_session_status() -> Dict[str, Any]:
    base_url = _get_platonus_api_url()
    if not base_url:
        raise RuntimeError("PLATONUS_API_URL is not configured.")

    url = f"{base_url.rstrip('/')}/session"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Platonus API request failed: {exc}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("Platonus API returned invalid JSON.") from exc
