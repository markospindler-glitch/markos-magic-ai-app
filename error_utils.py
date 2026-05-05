"""User-friendly error handling helpers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

import streamlit as st


LOGGER = logging.getLogger("markos_magic_ai_app")
T = TypeVar("T")


USER_ERROR_MESSAGES = {
    "file_import": "The file could not be imported. Please check the file format and try again.",
    "project_load": "The project could not be loaded. The saved project may be incomplete or corrupted.",
    "project_save": "The project could not be saved. Please check the project name and try again.",
    "project_update": "The saved project could not be updated. Please try saving it as a new project.",
    "project_delete": "The saved project could not be deleted. Please check that the file still exists.",
    "export": "The export failed. Please try a simpler export format or check the source file.",
    "openai": "The GPT request could not be completed. Please check the API key and try again.",
    "generic": "Something went wrong. Please try again.",
}


def user_friendly_message(operation: str) -> str:
    """Return a stable non-technical message for common app operations."""
    return USER_ERROR_MESSAGES.get(operation, USER_ERROR_MESSAGES["generic"])


def log_exception(operation: str, exc: Exception) -> None:
    """Log technical details without exposing them as the main UI message."""
    LOGGER.exception("%s failed: %s", operation, exc)


def show_streamlit_error(operation: str, exc: Exception) -> None:
    """Show a clear error in Streamlit and keep technical detail available."""
    log_exception(operation, exc)
    st.error(user_friendly_message(operation))
    with st.expander("Technical detail", expanded=False):
        st.caption(str(exc))


def safe_operation(operation: str, callback: Callable[[], T], fallback: T | None = None) -> T | None:
    """Run a risky Streamlit operation with consistent user-facing errors."""
    try:
        return callback()
    except Exception as exc:
        show_streamlit_error(operation, exc)
        return fallback
