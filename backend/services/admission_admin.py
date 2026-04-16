"""Admin helpers for reading and updating admission JSON data."""
from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ..langchain.tools.admission_info import DEFAULT_DATA_PATH


class AdmissionInfoPayload(BaseModel):
    """Loose schema for admission data with key business checks."""

    model_config = ConfigDict(extra="allow")

    institution: str = Field(min_length=1)
    currency: str = Field(min_length=1)
    contacts: dict[str, Any]
    documents: dict[str, Any]
    programs: list[dict[str, Any]]
    duration_rules: dict[str, Any] = Field(default_factory=dict)
    last_updated: str | None = None

    @field_validator("programs")
    @classmethod
    def validate_programs(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not value:
            raise ValueError("At least one program is required.")

        required_program_keys = {"name", "level", "duration", "tuition", "passing_score"}
        for index, program in enumerate(value, start=1):
            missing_keys = required_program_keys - set(program.keys())
            if missing_keys:
                missing = ", ".join(sorted(missing_keys))
                raise ValueError(f"Program #{index} is missing keys: {missing}.")
            if not any(
                isinstance(program.get(key), str) and program.get(key, "").strip()
                for key in ("name", "name_ru", "name_kk", "name_en")
            ):
                raise ValueError(
                    f"Program #{index} must define at least one non-empty name field."
                )
            if not isinstance(program.get("tuition"), dict):
                raise ValueError(f"Program #{index} field 'tuition' must be an object.")
            if not isinstance(program.get("passing_score"), dict):
                raise ValueError(f"Program #{index} field 'passing_score' must be an object.")
            aliases = program.get("aliases")
            if aliases is not None and not isinstance(aliases, list):
                raise ValueError(f"Program #{index} field 'aliases' must be a list.")
        return value

    @model_validator(mode="after")
    def validate_sections(self) -> "AdmissionInfoPayload":
        if not isinstance(self.contacts, dict) or not self.contacts:
            raise ValueError("Section 'contacts' must be a non-empty object.")
        if not isinstance(self.documents, dict) or not self.documents:
            raise ValueError("Section 'documents' must be a non-empty object.")
        return self


def get_data_path() -> Path:
    configured_path = os.getenv("ADMISSION_DATA_PATH")
    return Path(configured_path) if configured_path else DEFAULT_DATA_PATH


def load_admission_info_for_admin() -> dict[str, Any]:
    data_path = get_data_path()
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    AdmissionInfoPayload.model_validate(payload)
    return payload


def save_admission_info_for_admin(payload: dict[str, Any]) -> dict[str, Any]:
    validated = AdmissionInfoPayload.model_validate(payload)
    normalized = _apply_update_timestamps(validated.model_dump(mode="python"))

    data_path = get_data_path()
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized


def list_admission_programs_for_admin(
    *,
    search: str = "",
    level: str = "all",
    page: int = 1,
    per_page: int = 10,
) -> dict[str, Any]:
    payload = load_admission_info_for_admin()
    programs = payload.get("programs") or []
    normalized_search = search.strip().lower()
    normalized_level = level.strip().lower() or "all"

    matched_indices: list[int] = []
    for index, program in enumerate(programs):
        if normalized_level != "all" and str(program.get("level") or "").lower() != normalized_level:
            continue
        if normalized_search:
            haystack = " ".join(
                str(value).strip()
                for value in [
                    program.get("id"),
                    program.get("name"),
                    program.get("name_ru"),
                    program.get("name_kk"),
                    program.get("name_en"),
                    program.get("source"),
                    (program.get("passing_score") or {}).get("gop_code"),
                    *((program.get("aliases") or []) if isinstance(program.get("aliases"), list) else []),
                ]
                if value
            ).lower()
            if normalized_search not in haystack:
                continue
        matched_indices.append(index)

    safe_per_page = max(1, min(per_page, 100))
    safe_page = max(1, page)
    total = len(matched_indices)
    pages = max(1, (total + safe_per_page - 1) // safe_per_page)
    safe_page = min(safe_page, pages)
    start = (safe_page - 1) * safe_per_page
    sliced_indices = matched_indices[start:start + safe_per_page]

    return {
        "items": [
            {
                "program_index": index,
                "program_id": programs[index].get("id"),
            }
            for index in sliced_indices
        ],
        "page": safe_page,
        "per_page": safe_per_page,
        "total": total,
        "pages": pages,
        "filters": {
            "search": search,
            "level": normalized_level,
        },
    }


def _apply_update_timestamps(payload: dict[str, Any]) -> dict[str, Any]:
    current_date = date.today().isoformat()
    normalized = deepcopy(payload)
    normalized["last_updated"] = current_date
    return _refresh_nested_updated_at(normalized, current_date)


def _refresh_nested_updated_at(value: Any, current_date: str) -> Any:
    if isinstance(value, dict):
        updated = {
            key: _refresh_nested_updated_at(item, current_date)
            for key, item in value.items()
        }
        if "updated_at" in updated:
            updated["updated_at"] = current_date
        return updated
    if isinstance(value, list):
        return [_refresh_nested_updated_at(item, current_date) for item in value]
    return value


def validate_admission_payload(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = AdmissionInfoPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(exc.errors(include_url=False)) from exc
    return validated.model_dump(mode="python")
