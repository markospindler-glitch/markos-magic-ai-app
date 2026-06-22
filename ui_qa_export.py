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
from openai_client import DEFAULT_MODEL
from qa_checklist import (
    apply_approved_qa_corrections,
    approved_checklist_rows,
    create_qa_checklist_xlsx,
    read_qa_checklist_xlsx,
)
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
    _qa_checklist_area(source_language, target_language, domain, model)

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


def _qa_checklist_area(source_language: str, target_language: str, domain: str, model: str) -> None:
    """Let PMs approve/reject QA items in Excel and apply approved corrections."""
    has_qa = bool(st.session_state.rule_based_qa_warnings or st.session_state.qa_report.strip())
    if not has_qa:
        return

    st.markdown("**QA correction checklist**")
    st.caption(
        "Download the Excel checklist, mark approved corrections in the Approved column "
        "with Yes/X/Approved, optionally add PM instructions, then reupload it."
    )
    base_name = _qa_export_base_name()
    col_download, col_upload = st.columns(2)
    with col_download:
        try:
            st.download_button(
                "Download QA checklist XLSX",
                data=create_qa_checklist_xlsx(
                    st.session_state.rule_based_qa_warnings,
                    st.session_state.qa_report,
                ),
                file_name=f"{base_name}_qa_checklist.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="qa_checklist_xlsx_download",
            )
        except Exception as exc:
            st.info(f"QA checklist will be available after QA exists. {exc}")
    with col_upload:
        uploaded = st.file_uploader(
            "Reupload approved QA checklist",
            type=["xlsx"],
            key="qa_checklist_reupload",
            help="Use the checklist exported by this app. Only approved rows are applied.",
        )
        if uploaded and st.button(
            "Apply approved QA corrections",
            use_container_width=True,
            key="apply_qa_checklist_corrections",
        ):
            _apply_uploaded_qa_checklist(uploaded, source_language, target_language, domain, model)


def _apply_uploaded_qa_checklist(uploaded_file, source_language: str, target_language: str, domain: str, model: str) -> None:
    """Apply approved checklist items to the final translation."""
    try:
        rows = read_qa_checklist_xlsx(uploaded_file.getvalue())
        approved_rows = approved_checklist_rows(rows)
        if not approved_rows:
            raise ValueError("No approved checklist rows found. Mark Approved as Yes, X, or Approved.")
        current_target = st.session_state.proofread_text.strip() or st.session_state.translated_text.strip()
        corrected = apply_approved_qa_corrections(
            st.session_state.source_text,
            current_target,
            approved_rows,
            target_language,
            domain,
            model=model.strip() or DEFAULT_MODEL,
        )
        st.session_state.proofread_text = corrected
        st.session_state.qa_checklist_status = (
            f"Applied {len(approved_rows)} approved QA correction(s) to the final translation."
        )
        _clear_stale_bilingual_exports()
        st.success(st.session_state.qa_checklist_status)
    except Exception as exc:
        st.error(f"Approved QA corrections could not be applied: {exc}")


def _clear_stale_bilingual_exports() -> None:
    """Clear generated bilingual files that no longer match corrected text."""
    for key, value in {
        "aligned_xliff_bytes": b"",
        "aligned_xliff_summary": "",
        "aligned_rows": [],
        "realigned_xliff_bytes": b"",
        "realigned_xliff_summary": "",
        "realigned_rows": [],
        "realigned_template_name": "",
        "realigned_template_type": "",
        "realigned_template_bytes": b"",
        "bilingual_review_rows": [],
        "reflow_summary": "",
    }.items():
        st.session_state[key] = value


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
