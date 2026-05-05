"""Small UI renderer for the QA & Export tab.

The heavy QA and export work remains in app.py. This module only owns the
Streamlit layout for the tab, which keeps app.py a bit easier to maintain.
"""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

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
