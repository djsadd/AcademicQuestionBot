"""Validate the structured admission data file used by admission tools."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "backend" / "data" / "admission_info.json"
REQUIRED_TOP_LEVEL_KEYS = {"contacts", "documents", "programs"}
REQUIRED_PROGRAM_KEYS = {"name", "level", "duration", "tuition", "passing_score"}
LOCALIZED_NAME_KEYS = {"name_ru", "name_kk", "name_en"}


def _is_localized_mapping(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return any(key in {"ru", "kk", "en"} for key in value.keys())


def _is_text_or_localized(value: object) -> bool:
    return (
        (isinstance(value, str) and bool(value.strip()))
        or _is_localized_mapping(value)
    )


def main() -> int:
    configured_path = os.getenv("ADMISSION_DATA_PATH")
    data_path = Path(configured_path) if configured_path else DEFAULT_PATH

    if not data_path.exists():
        print(f"[ERROR] File not found: {data_path}")
        return 1

    try:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[ERROR] Invalid JSON in {data_path}: {exc}")
        return 1

    missing = REQUIRED_TOP_LEVEL_KEYS - set(payload.keys())
    if missing:
        print(f"[ERROR] Missing top-level keys: {', '.join(sorted(missing))}")
        return 1

    programs = payload.get("programs")
    if not isinstance(programs, list) or not programs:
        print("[ERROR] 'programs' must be a non-empty list.")
        return 1

    for index, program in enumerate(programs, 1):
        if not isinstance(program, dict):
            print(f"[ERROR] Program #{index} is not an object.")
            return 1
        missing_program_keys = REQUIRED_PROGRAM_KEYS - set(program.keys())
        if missing_program_keys:
            print(
                f"[ERROR] Program #{index} ({program.get('name', 'unknown')}) "
                f"is missing keys: {', '.join(sorted(missing_program_keys))}"
            )
            return 1
        localized_names = [program.get(key) for key in LOCALIZED_NAME_KEYS]
        if not any(isinstance(value, str) and value.strip() for value in localized_names):
            print(
                f"[ERROR] Program #{index} ({program.get('name', 'unknown')}) "
                "must define at least one localized name: name_ru, name_kk or name_en."
            )
            return 1
        aliases = program.get("aliases")
        if aliases is not None and not isinstance(aliases, list):
            print(
                f"[ERROR] Program #{index} ({program.get('name', 'unknown')}) "
                "'aliases' must be a list when provided."
            )
            return 1
        if not _is_text_or_localized(program.get("duration")):
            print(
                f"[ERROR] Program #{index} ({program.get('name', 'unknown')}) "
                "'duration' must be a non-empty string or a localized object."
            )
            return 1
        tuition = program.get("tuition")
        if not isinstance(tuition, dict):
            print(f"[ERROR] Program #{index} ({program.get('name', 'unknown')}) 'tuition' must be an object.")
            return 1
        if "period" in tuition and tuition.get("period") not in (None, "") and not _is_text_or_localized(tuition.get("period")):
            print(
                f"[ERROR] Program #{index} ({program.get('name', 'unknown')}) "
                "'tuition.period' must be a string or a localized object."
            )
            return 1
        passing_score = program.get("passing_score")
        if not isinstance(passing_score, dict):
            print(f"[ERROR] Program #{index} ({program.get('name', 'unknown')}) 'passing_score' must be an object.")
            return 1
        if "exam" in passing_score and passing_score.get("exam") not in (None, "") and not _is_text_or_localized(passing_score.get("exam")):
            print(
                f"[ERROR] Program #{index} ({program.get('name', 'unknown')}) "
                "'passing_score.exam' must be a string or a localized object."
            )
            return 1

    print(f"[OK] Admission data file is valid: {data_path}")
    print(f"[OK] Programs loaded: {len(programs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
