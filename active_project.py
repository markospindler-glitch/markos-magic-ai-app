"""Autosave for the currently open Streamlit project.

This is separate from the user's named project repository. Its only job is to
survive browser refreshes and Streamlit session resets.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app_defaults import PROJECT_SCHEMA_VERSION, PROJECT_STATE_DEFAULTS


ACTIVE_PROJECT_PATH = Path("data") / "current_project.json"


def save_active_project(state: dict[str, Any]) -> Path:
    """Save the currently open project snapshot."""
    ACTIVE_PROJECT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "state": state,
    }
    ACTIVE_PROJECT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ACTIVE_PROJECT_PATH


def load_active_project() -> dict[str, Any]:
    """Load the current autosaved project, filling defaults for older snapshots."""
    if not ACTIVE_PROJECT_PATH.exists():
        return {}
    try:
        payload = json.loads(ACTIVE_PROJECT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Current project autosave is corrupted.") from exc
    except OSError as exc:
        raise ValueError("Current project autosave could not be read.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Current project autosave has an invalid format.")
    state = payload.get("state")
    if not isinstance(state, dict):
        return {}
    normalized = copy.deepcopy(PROJECT_STATE_DEFAULTS)
    normalized.update(state)
    normalized.setdefault("source_file_bytes_b64", "")
    normalized.setdefault("sdlxliff_template_bytes_b64", "")
    normalized.setdefault("realigned_template_bytes_b64", "")
    return normalized
