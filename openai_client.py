"""Small OpenAI helper used by the workflow modules.

Keeping the API call in one place makes the rest of the app easier to read.
"""

from __future__ import annotations

import os

from openai import OpenAI, OpenAIError
try:
    import streamlit as st
except Exception:  # pragma: no cover - tests can import this module without Streamlit runtime.
    st = None


DEFAULT_MODEL = "gpt-5.5"


def require_api_key() -> None:
    """Show a clear error if the OpenAI API key is missing."""
    api_key = _api_key()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Run set_api_key.bat, paste your API key, "
            "then close and reopen the app. On Streamlit Cloud, add OPENAI_API_KEY "
            "to the app secrets."
        )
    os.environ["OPENAI_API_KEY"] = api_key


def _api_key() -> str:
    """Read the OpenAI key from Windows env vars or Streamlit Cloud secrets."""
    env_key = os.getenv("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key
    if st is None:
        return ""
    try:
        return str(st.secrets.get("OPENAI_API_KEY", "")).strip()
    except Exception:
        return ""


def ask_openai(system_prompt: str, user_prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Send a text task to OpenAI and return the model's answer."""
    require_api_key()

    client = OpenAI()
    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except OpenAIError as exc:
        raise RuntimeError(f"OpenAI request failed: {exc}") from exc

    answer = response.output_text.strip()
    if not answer:
        raise RuntimeError("OpenAI returned an empty response.")
    return answer
