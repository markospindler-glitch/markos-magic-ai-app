"""Startup checks that keep missing folders/packages from causing unclear errors."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

from prompt_archive import ARCHIVE_PATH
from project_repository import PROJECTS_DIR


REQUIRED_PACKAGES = [
    "streamlit",
    "openai",
    "docx",
    "reportlab",
    "fitz",
    "openpyxl",
    "pypdf",
    "PIL",
]


def run_startup_checks() -> list[dict[str, str]]:
    """Return startup warnings instead of crashing during app launch."""
    warnings: list[dict[str, str]] = []
    _ensure_folder(PROJECTS_DIR, "Project repository", warnings)
    _ensure_folder(ARCHIVE_PATH.parent, "Prompt archive folder", warnings)
    _ensure_prompt_archive(warnings)
    _check_api_key(warnings)
    _check_required_packages(warnings)
    return warnings


def _ensure_folder(path: Path, label: str, warnings: list[dict[str, str]]) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        warnings.append({"area": label, "message": f"{label} could not be created: {exc}"})


def _ensure_prompt_archive(warnings: list[dict[str, str]]) -> None:
    if ARCHIVE_PATH.exists():
        return
    try:
        ARCHIVE_PATH.write_text("[]", encoding="utf-8")
    except Exception as exc:
        warnings.append({"area": "Prompt archive", "message": f"Prompt archive could not be created: {exc}"})


def _check_api_key(warnings: list[dict[str, str]]) -> None:
    if not os.getenv("OPENAI_API_KEY"):
        warnings.append(
            {
                "area": "OpenAI API key",
                "message": "OPENAI_API_KEY is not set. GPT steps will ask you to set the key before they run.",
            }
        )


def _check_required_packages(warnings: list[dict[str, str]]) -> None:
    for package in REQUIRED_PACKAGES:
        try:
            importlib.import_module(package)
        except Exception as exc:
            warnings.append({"area": "Python package", "message": f"Required package '{package}' is missing: {exc}"})
