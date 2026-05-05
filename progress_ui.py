"""Small Streamlit progress helpers."""

from __future__ import annotations

import time

import streamlit as st


class StepProgress:
    """Show a colored percentage progress bar for one workflow step."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.status = st.empty()
        self.bar = st.progress(0, text=f"{label}: 0%")

    def update(self, percent: int, message: str = "") -> None:
        """Update the bar and status text."""
        percent = max(0, min(100, percent))
        text = f"{self.label}: {percent}%"
        if message:
            text = f"{text} - {message}"
        self.bar.progress(percent, text=text)
        self.status.caption(text)
        time.sleep(0.05)

    def done(self, message: str = "Done") -> None:
        """Mark the step as complete."""
        self.update(100, message)
