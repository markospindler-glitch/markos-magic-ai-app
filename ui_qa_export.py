"""Small UI renderer for the QA & Export tab.

The heavy QA and export work remains in app.py. This module only owns the
Streamlit layout for the tab, which keeps app.py a bit easier to maintain.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import re

import streamlit as st

from export_docx import create_docx
from export_pdf import create_pdf
from text_stats import stats_label


def render_qa_export_tab(
    include_report: bool,
    source_language: str,
    target_language: str,
    domain: str,
    model: str,
    run_qa_callback: Callable[[str, str, str, str, str], None],
    export_area_callback: Callable[[bool, str, str, str, str], None],
) -> None:
    """Render the QA and export tab without changing the existing workflow."""
    st.subheader("QA and Export")
    if st.button("Run QA check", type="primary", use_container_width=True):
        run_qa_callback(st.session_state.source_text, source_language, target_language, domain, model)

    _rule_based_qa_area()

    st.session_state.qa_report = st.text_area(
        "Editable QA report",
        value=st.session_state.qa_report,
        height=220,
    )
    st.caption(f"QA report: {stats_label(st.session_state.qa_report)}")
    _qa_download_area(source_language, target_language, domain)

    export_area_callback(include_report, st.session_state.source_text, source_language, target_language, model)


def _rule_based_qa_area() -> None:
    """Show deterministic QA warnings before the editable GPT QA report."""
    st.markdown("**Rule-based QA warnings**")
    warnings = st.session_state.rule_based_qa_warnings
    if warnings:
        st.warning(f"{len(warnings)} rule-based warning(s) found. Exports are not blocked.")
        st.dataframe(warnings, use_container_width=True, hide_index=True)
    elif st.session_state.qa_report.strip():
        st.success("No rule-based QA warnings found.")
    else:
        st.caption("Run QA check to see rule-based warnings before the GPT QA report.")


def _qa_download_area(source_language: str, target_language: str, domain: str) -> None:
    """Show simple QA report export buttons inside step 6."""
    body = build_qa_export_body(
        st.session_state.rule_based_qa_warnings,
        st.session_state.qa_report,
        source_language,
        target_language,
        domain,
    )
    if not body.strip():
        st.caption("Run QA check before exporting the QA report.")
        return

    st.markdown("**Export QA report**")
    base_name = _qa_export_base_name()
    col_docx, col_pdf, col_txt = st.columns(3)
    with col_docx:
        try:
            st.download_button(
                "Download QA DOCX",
                data=create_docx("QA Report", body),
                file_name=f"{base_name}_qa_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="qa_report_docx_download",
            )
        except Exception as exc:
            st.info(f"QA DOCX will be available when QA text exists. {exc}")
    with col_pdf:
        try:
            st.download_button(
                "Download QA PDF",
                data=create_pdf("QA Report", body),
                file_name=f"{base_name}_qa_report.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="qa_report_pdf_download",
            )
        except Exception as exc:
            st.info(f"QA PDF will be available when QA text exists. {exc}")
    with col_txt:
        st.download_button(
            "Download QA TXT",
            data=body.encode("utf-8-sig"),
            file_name=f"{base_name}_qa_report.txt",
            mime="text/plain",
            use_container_width=True,
            key="qa_report_txt_download",
        )


def build_qa_export_body(
    rule_based_warnings: list[dict],
    qa_report: str,
    source_language: str,
    target_language: str,
    domain: str,
) -> str:
    """Build one readable QA export body from rule-based and GPT QA outputs."""
    has_warnings = bool(rule_based_warnings)
    has_report = bool(str(qa_report or "").strip())
    if not has_warnings and not has_report:
        return ""

    parts = [
        "QA Report",
        "",
        f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Language pair: {source_language} -> {target_language}",
        f"Domain: {domain}",
        "",
        "Rule-based QA warnings",
        "",
    ]
    if has_warnings:
        for index, warning in enumerate(rule_based_warnings, start=1):
            parts.extend(
                [
                    f"{index}. {warning.get('severity', '').upper()} | {warning.get('category', '')}",
                    f"Message: {warning.get('message', '')}",
                    f"Segment: {warning.get('segment index', '')}",
                    f"Source: {warning.get('source excerpt', '')}",
                    f"Target: {warning.get('target excerpt', '')}",
                    "",
                ]
            )
    else:
        parts.extend(["No rule-based QA warnings found.", ""])

    parts.extend(["GPT QA report", "", str(qa_report or "").strip()])
    return "\n".join(parts).strip()


def _qa_export_base_name() -> str:
    """Return a readable file base name for QA report downloads."""
    project_name = str(st.session_state.get("project_name") or "").strip()
    source_file = str(st.session_state.get("source_file_name") or "").strip()
    raw_name = project_name or source_file.rsplit(".", 1)[0] or "translatai"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("_")
    return safe_name or "translatai"
