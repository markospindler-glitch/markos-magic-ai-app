"""PDF export helpers."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.platypus.doctemplate import LayoutError


def create_pdf(title: str, body: str) -> bytes:
    """Create a simple PDF file in memory and return it as bytes."""
    if not body.strip():
        raise ValueError("There is no text to export.")

    file_buffer = BytesIO()
    document = SimpleDocTemplate(file_buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(_escape(title), styles["Title"]), Spacer(1, 12)]

    for line in body.split("\n"):
        story.append(Paragraph(_escape(line) or "&nbsp;", styles["BodyText"]))
        story.append(Spacer(1, 6))

    try:
        document.build(story)
    except LayoutError as exc:
        raise RuntimeError(f"PDF export failed because the text layout is too large: {exc}") from exc

    file_buffer.seek(0)
    return file_buffer.getvalue()


def _escape(text: str) -> str:
    """Escape characters that have special meaning in PDF paragraph markup."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
