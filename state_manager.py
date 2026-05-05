"""Small helpers around Streamlit session state.

The app still uses Streamlit state directly in many UI places. These helpers
centralize the risky startup/reset/project-snapshot paths first.
"""

from __future__ import annotations

import base64
import copy
from typing import Any, MutableMapping

import streamlit as st

from app_defaults import APP_STATE_DEFAULTS, PROJECT_STATE_KEYS


def get_state_value(key: str, default: Any = None, state: MutableMapping[str, Any] | None = None) -> Any:
    """Safely read one value from Streamlit session state."""
    target = state if state is not None else st.session_state
    return target.get(key, default)


def set_state_value(key: str, value: Any, state: MutableMapping[str, Any] | None = None) -> None:
    """Safely write one value to Streamlit session state."""
    target = state if state is not None else st.session_state
    target[key] = value


def ensure_state_defaults(state: MutableMapping[str, Any] | None = None) -> None:
    """Ensure all known app state keys exist."""
    target = state if state is not None else st.session_state
    for key, value in APP_STATE_DEFAULTS.items():
        if key not in target:
            target[key] = copy.deepcopy(value)


def reset_project_state(state: MutableMapping[str, Any] | None = None) -> None:
    """Reset the current project while keeping the app itself open."""
    target = state if state is not None else st.session_state
    current_editor_version = int(target.get("bilingual_review_editor_version") or 0)
    for key, value in APP_STATE_DEFAULTS.items():
        if key == "show_price_list":
            continue
        target[key] = copy.deepcopy(value)
    target["bilingual_review_editor_version"] = current_editor_version + 1


def get_current_project_snapshot(state: MutableMapping[str, Any] | None = None) -> dict[str, Any]:
    """Collect a JSON-friendly snapshot for project saving."""
    target = state if state is not None else st.session_state
    snapshot = {key: copy.deepcopy(target.get(key, APP_STATE_DEFAULTS.get(key))) for key in PROJECT_STATE_KEYS}

    source_file_bytes = target.get("source_file_bytes") or b""
    snapshot["source_file_bytes_b64"] = (
        base64.b64encode(source_file_bytes).decode("ascii") if source_file_bytes else ""
    )
    template_bytes = target.get("sdlxliff_template_bytes") or b""
    snapshot["sdlxliff_template_bytes_b64"] = (
        base64.b64encode(template_bytes).decode("ascii") if template_bytes else ""
    )
    realigned_template_bytes = target.get("realigned_template_bytes") or b""
    snapshot["realigned_template_bytes_b64"] = (
        base64.b64encode(realigned_template_bytes).decode("ascii") if realigned_template_bytes else ""
    )
    return snapshot


def apply_project_snapshot(snapshot: dict[str, Any], state: MutableMapping[str, Any] | None = None) -> None:
    """Apply a saved project snapshot back into Streamlit session state."""
    target = state if state is not None else st.session_state
    for key, value in snapshot.items():
        if key == "source_file_bytes_b64":
            target["source_file_bytes"] = base64.b64decode(value) if value else b""
        elif key == "sdlxliff_template_bytes_b64":
            target["sdlxliff_template_bytes"] = base64.b64decode(value) if value else b""
        elif key == "realigned_template_bytes_b64":
            target["realigned_template_bytes"] = base64.b64decode(value) if value else b""
        else:
            target[key] = value
    ensure_state_defaults(target)
