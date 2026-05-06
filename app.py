"""Streamlit interface for the local translation workflow app.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from active_project import load_active_project, save_active_project
from app_defaults import DEFAULT_SOURCE_LANGUAGE, DEFAULT_TARGET_LANGUAGE, DEFAULT_TEXT_TYPE
from analysis import analyse_source_text, format_analysis_report
from bilingual_review import build_review_rows, target_text_from_rows
from cost_estimator import new_cost_entry, total_cost
from deterministic_qa import run_rule_based_qa
from diff_view import (
    accept_proofreading_change,
    proofreading_changes,
    proofreading_diff_html,
    reject_proofreading_change,
)
from export_docx import create_bilingual_docx_from_rows, create_docx, create_formatted_docx_from_template
from export_bilingual_template import (
    BILINGUAL_EXTENSIONS,
    bilingual_source_segment_count,
    create_translated_bilingual_file,
    fit_target_segments_to_count,
    target_segments_from_rows,
    target_segments_from_text,
)
from export_pdf import create_pdf
from export_same_format import create_same_format_file
from export_xliff import create_xliff, create_xliff_from_aligned_rows, sentence_segments
from file_validation import export_preflight_warnings, validate_sdlxliff_template, validate_source_upload
from import_files import import_source_file, strip_protected_tokens
from error_utils import show_streamlit_error
from handout_translator_v1.app import render_handout_translator_section
from net_word_grid import analyse_net_words
from prompt_builder import build_translation_prompt, ensure_text_for_translation_section
from prompt_archive import (
    load_prompt_archive,
    save_prompt_to_archive,
    update_prompt_in_archive,
)
from project_repository import delete_project, list_projects, load_project, save_project, update_project
from pricing import pricing_rows
from progress_ui import StepProgress
from proofreader import proofread_translation
from qa import run_qa_check
from reference_files import analyse_reference_files, extract_reference_texts
from reflow import reflow_to_paragraph_count, source_docx_paragraph_count
from openai_client import DEFAULT_MODEL
from startup_checks import run_startup_checks
from state_manager import apply_project_snapshot, ensure_state_defaults, get_current_project_snapshot, reset_project_state
from sdlxliff_pipeline import validate_and_repair_sdlxliff_translations
from sdlxliff_translator import translate_sdlxliff_segments
from translator import translate_text
from translation_memory import create_tmx, find_tm_matches, format_tm_matches, import_tm, updated_tmx_from_aligned_rows
from text_stats import stats_label
from ui_qa_export import render_qa_export_tab
from xliff_aligner import align_fixed_source_segments, align_for_xliff, extract_text_from_xliff, quick_alignment_check
from xliff_to_docx import create_docx_from_xliff_and_template


LANGUAGES = [
    "English",
    "Slovenian",
    "German",
    "French",
    "Italian",
    "Spanish",
    "Croatian",
    "Serbian",
    "Bosnian",
    "Portuguese",
    "Dutch",
    "Polish",
]

DOMAINS = [
    "General",
    "Business",
    "Technical",
    "Legal",
    "Medical",
    "Financial",
    "Marketing",
    "Academic",
    "Website/UI",
    "Customer support",
]


def main() -> None:
    """Build the app screen and connect button clicks to the workflow."""
    st.set_page_config(page_title="TranslatAI", layout="wide")
    _init_session_state()
    _apply_visual_style()

    _app_header()
    _startup_warning_area()

    with st.sidebar:
        st.header("Settings")
        source_language = st.selectbox(
            "Source language",
            LANGUAGES,
            index=_option_index(LANGUAGES, st.session_state.source_language, DEFAULT_SOURCE_LANGUAGE),
        )
        st.session_state.source_language = source_language
        target_language = st.selectbox(
            "Target language",
            LANGUAGES,
            index=_option_index(LANGUAGES, st.session_state.target_language, DEFAULT_TARGET_LANGUAGE),
        )
        st.session_state.target_language = target_language
        domain = st.selectbox(
            "Text type/domain",
            DOMAINS,
            index=_option_index(DOMAINS, st.session_state.text_type, DEFAULT_TEXT_TYPE),
        )
        st.session_state.text_type = domain
        model = st.text_input("OpenAI model", value=DEFAULT_MODEL)
        include_report = st.checkbox("Export analysis report", value=True)
        if st.button("Show price list", use_container_width=True):
            st.session_state.show_price_list = not st.session_state.show_price_list
        st.divider()
        if st.button("Start new project", use_container_width=True):
            _start_new_project()
        st.divider()
        _project_repository_sidebar()

    if st.session_state.show_price_list:
        _price_list_area()
    _current_cost_area()
    _workflow_status()

    source_tab, context_tab, prompt_tab, translation_tab, handout_tab, qa_export_tab, xliff_docx_tab = st.tabs(
        ["1 Source", "2 Context", "3 Prompt", "4 Translation", "5 Handout Translator", "6 QA & Export", "7. XLIFF → DOCX"]
    )

    with source_tab:
        st.subheader("Source")
        if st.session_state.get("handout_handoff_message"):
            st.success(st.session_state.handout_handoff_message)
            st.session_state.handout_handoff_message = ""
        st.session_state.project_name = st.text_input(
            "Project name",
            value=st.session_state.project_name,
            placeholder="Client name or job number",
        )
        uploaded_file = st.file_uploader(
            "Upload source file",
            type=["txt", "csv", "docx", "pdf", "idml", "xlsx", "xls", "xlsm", "sdlxliff", "xliff", "xlf"],
            help="SDLXLIFF/XLIFF imports source segments for translation. DOCX and IDML keep the best chance of preserving design. PDF import extracts selectable text only; no OCR.",
        )
        if uploaded_file:
            _load_uploaded_file_once(uploaded_file)

        source_text = st.text_area(
            "Source text",
            value=st.session_state.source_text,
            height=320,
            placeholder="Paste plain text here, or upload a TXT, CSV, Excel, DOCX, IDML, selectable-text PDF, SDLXLIFF, XLIFF, or XLF above.",
        )
        st.session_state.source_text = source_text
        _show_text_stats("Source text", source_text)
        _net_word_grid_area(source_text)

    with context_tab:
        st.subheader("Context")
        tm_col, ref_col = st.columns(2)
        with tm_col:
            st.markdown("**Translation Memory**")
            tm_file = st.file_uploader(
                "Upload Translation Memory",
                type=["tmx", "csv", "sdltm"],
                help="TMX works best. SDLTM is imported read-only when the SQLite schema can be safely read. CSV must have source and target columns.",
            )
            if tm_file and st.button("Load Translation Memory", use_container_width=True):
                _load_translation_memory(tm_file)

            minimum_score = st.slider("Minimum fuzzy match", 50, 100, 70, 5)
            match_limit = st.number_input("Maximum matches", min_value=1, max_value=50, value=10)

            if st.button("Find TM matches", use_container_width=True):
                _find_translation_memory_matches(
                    st.session_state.source_text,
                    minimum_score,
                    int(match_limit),
                )

            st.session_state.tm_context = st.text_area(
                "Editable TM matches",
                value=st.session_state.tm_context,
                height=260,
                help="These matches are included in prompt generation and translation.",
            )
            _show_text_stats("Translation Memory matches", st.session_state.tm_context)

        with ref_col:
            st.markdown("**Client reference files**")
            reference_files = st.file_uploader(
                "Upload reference files",
                type=["txt", "csv", "docx", "pdf", "idml", "xlsx", "xls", "xlsm"],
                accept_multiple_files=True,
                help="Use this for client glossaries, past translations, style guides, or similar documents.",
            )
            if reference_files and st.button("Analyse reference files", use_container_width=True):
                _analyse_reference_files(reference_files, source_language, target_language, domain, model)

            st.session_state.reference_context = st.text_area(
                "Editable reference guidance",
                value=st.session_state.reference_context,
                height=340,
                help="This guidance is included in analysis, prompt generation, translation, proofreading, and QA.",
            )
            _show_text_stats("Reference guidance", st.session_state.reference_context)

    with prompt_tab:
        st.subheader("Analysis and Prompt")
        if st.button("Analyse source text", type="primary", use_container_width=True):
            _analyse(st.session_state.source_text, source_language, target_language, domain, model)

        st.session_state.analysis_report = st.text_area(
            "Editable analysis",
            value=st.session_state.analysis_report,
            height=260,
        )
        _show_text_stats("Analysis report", st.session_state.analysis_report)

        if st.button("Generate translation prompt", use_container_width=True):
            _build_prompt(st.session_state.source_text, source_language, target_language, domain, model)

        st.session_state.translation_prompt = st.text_area(
            "Editable translation prompt",
            value=st.session_state.translation_prompt,
            height=320,
        )
        _show_text_stats("Translation prompt", st.session_state.translation_prompt)
        _prompt_archive_area(source_language, target_language, domain)

    with translation_tab:
        st.subheader("Translation and Proofreading")
        col_translate, col_proofread = st.columns(2)
        with col_translate:
            if st.button("Translate text", type="primary", use_container_width=True):
                _translate(st.session_state.source_text, source_language, target_language, domain, model)
            st.session_state.translated_text = st.text_area(
                "Editable translation",
                value=st.session_state.translated_text,
                height=360,
            )
            _show_text_stats("Translated text", st.session_state.translated_text)

        with col_proofread:
            if st.button("Proofread translation", use_container_width=True):
                _proofread(target_language, domain, model)
            st.session_state.proofread_text = st.text_area(
                "Editable proofread translation",
                value=st.session_state.proofread_text,
                height=360,
            )
            _show_text_stats("Proofread translation", st.session_state.proofread_text)
            _proofreading_changes_view()

        st.divider()
        st.subheader("Manual bilingual review")
        col_build, col_apply = st.columns(2)
        with col_build:
            if st.button("Build bilingual review table", use_container_width=True):
                _build_bilingual_review_table(st.session_state.source_text)
        with col_apply:
            if st.button("Apply reviewed target text", use_container_width=True):
                _apply_bilingual_review_table()

        if st.session_state.bilingual_review_rows:
            _ensure_bilingual_review_open_flags()
            if st.session_state.bilingual_review_status:
                st.success(st.session_state.bilingual_review_status)
                st.session_state.bilingual_review_status = ""
            st.session_state.review_row_index = st.number_input(
                "Expanded row editor",
                min_value=1,
                max_value=len(st.session_state.bilingual_review_rows),
                value=min(st.session_state.review_row_index or 1, len(st.session_state.bilingual_review_rows)),
                help="Use this for long segments that are hard to edit in the table.",
            )
            _expanded_review_row_editor()
            edited_rows = st.data_editor(
                st.session_state.bilingual_review_rows,
                hide_index=True,
                use_container_width=True,
                height=520,
                num_rows="fixed",
                disabled=["Segment", "Source"],
                column_order=["Open", "Segment", "Source", "Target", "Review note"],
                column_config={
                    "Open": st.column_config.CheckboxColumn("Open", width="small"),
                    "Segment": st.column_config.NumberColumn("Segment", width="small"),
                    "Source": st.column_config.TextColumn("Source", width="large"),
                    "Target": st.column_config.TextColumn("Target", width="large"),
                    "Review note": st.column_config.TextColumn("Review note", width="medium"),
                },
                key=f"bilingual_review_editor_{st.session_state.bilingual_review_editor_version}",
            )
            st.session_state.bilingual_review_rows = edited_rows
            _open_selected_bilingual_review_row()
            if st.button("Re-align bilingual review table", use_container_width=True):
                _realign_bilingual_review_table(
                    st.session_state.source_text,
                    target_text_from_rows(st.session_state.bilingual_review_rows),
                    source_language,
                    target_language,
                    model,
                )

    with handout_tab:
        render_handout_translator_section()

    with qa_export_tab:
        render_qa_export_tab(
            include_report,
            source_language,
            target_language,
            domain,
            model,
            _qa,
            _export_area,
        )

    with xliff_docx_tab:
        st.subheader("XLIFF → DOCX")
        st.write("Upload an ordinary XLIFF/XLF file and the original DOCX file. The app will use the XLIFF target segments and try to place them into the original DOCX template.")
        
        xliff_file = st.file_uploader("Upload XLIFF/XLF", type=["xlf", "xliff"], key="xliff_uploader")
        docx_file = st.file_uploader("Upload original DOCX template", type=["docx"], key="docx_uploader")
        
        if st.button("Create translated DOCX", key="create_docx_button"):
            if not xliff_file:
                st.error("Please upload an XLIFF/XLF file.")
            elif not docx_file:
                st.error("Please upload the original DOCX template file.")
            else:
                try:
                    docx_bytes = create_docx_from_xliff_and_template(xliff_file.getvalue(), docx_file.getvalue())
                    st.session_state.translated_docx_bytes = docx_bytes
                    st.session_state.translated_docx_name = Path(docx_file.name).stem + "_target.docx"
                    st.success("Translated DOCX created successfully.")
                except Exception as e:
                    st.error(f"Failed to create translated DOCX: {str(e)}")
        
        if "translated_docx_bytes" in st.session_state:
            st.download_button(
                label="Download translated DOCX",
                data=st.session_state.translated_docx_bytes,
                file_name=st.session_state.translated_docx_name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="download_docx"
            )
        
        st.write("**Formatting preservation is best-effort.** This works best when the XLIFF segments correspond closely to the original DOCX text. Complex Word layouts, text boxes, floating shapes, comments, tracked changes, headers/footers, and unusual segmentation may require manual checking.")

    _autosave_active_project()


def _init_session_state() -> None:
    """Create the editable fields once so Streamlit keeps user changes."""
    ensure_state_defaults()
    if not st.session_state.get("active_project_restored"):
        try:
            snapshot = load_active_project()
            if snapshot:
                apply_project_snapshot(snapshot)
        except Exception:
            # A bad autosave should not prevent the app from opening.
            pass
        st.session_state.active_project_restored = True


def _option_index(options: list[str], current_value: str, fallback: str) -> int:
    """Return a safe selectbox index even when older projects saved unknown values."""
    value = current_value if current_value in options else fallback
    return options.index(value) if value in options else 0


def _apply_visual_style() -> None:
    """Apply light visual polish to Streamlit's default UI."""
    st.markdown(
        """
        <style>
        :root {
            --magic-bg: #eef1f0;
            --magic-panel: #ffffff;
            --magic-border: #d7dedb;
            --magic-border-strong: #bcc8c3;
            --magic-text: #252827;
            --magic-muted: #66706c;
            --magic-green: #1e6f64;
            --magic-green-dark: #184f48;
            --magic-green-soft: #edf7f3;
            --magic-gold: #d49a2f;
        }
        html,
        body,
        [data-testid="stAppViewContainer"] {
            background: var(--magic-bg);
            color: var(--magic-text);
        }
        .block-container {
            padding-top: 1.35rem;
            padding-bottom: 2rem;
            max-width: 1540px;
        }
        [data-testid="stSidebar"] {
            background: #f8faf9;
            border-right: 1px solid var(--magic-border);
        }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.7rem;
        }
        h1,
        h2,
        h3,
        p {
            letter-spacing: 0;
        }
        h1 {
            color: var(--magic-text);
        }
        h2,
        h3 {
            color: #343938;
        }
        p,
        .stCaptionContainer,
        [data-testid="stMarkdownContainer"] p {
            color: var(--magic-muted);
        }
        div[data-testid="stMetric"] {
            background: var(--magic-panel);
            border: 1px solid var(--magic-border);
            border-radius: 8px;
            padding: 0.7rem 0.85rem;
            box-shadow: 0 10px 24px rgba(48, 58, 55, 0.06);
        }
        [data-testid="stExpander"] {
            background: var(--magic-panel);
            border: 1px solid var(--magic-border);
            border-radius: 8px;
            box-shadow: 0 10px 24px rgba(48, 58, 55, 0.055);
            overflow: hidden;
        }
        .stButton > button,
        .stDownloadButton > button {
            min-height: 39px;
            border-radius: 6px;
            border: 1px solid #c6d2ce;
            background: #f7faf8;
            color: #1d574f;
            font-weight: 700;
            box-shadow: none;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: var(--magic-green);
            color: var(--magic-green-dark);
            background: var(--magic-green-soft);
        }
        .stButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"] {
            border: 0;
            background: var(--magic-green);
            color: #ffffff;
        }
        .stButton > button[kind="primary"]:hover,
        .stDownloadButton > button[kind="primary"]:hover {
            background: var(--magic-green-dark);
            color: #ffffff;
        }
        .magic-header {
            position: relative;
            min-height: 205px;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 1rem;
            border: 1px solid var(--magic-border);
            background: var(--magic-panel);
            box-shadow: 0 14px 30px rgba(48, 58, 55, 0.08);
        }
        .magic-header img {
            width: 100%;
            height: 205px;
            object-fit: cover;
            display: block;
            filter: saturate(0.85) contrast(1.02);
        }
        .magic-header::after {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(90deg, rgba(24, 79, 72, 0.88), rgba(30, 111, 100, 0.48), rgba(30, 111, 100, 0.12));
        }
        .magic-header-content {
            position: absolute;
            z-index: 1;
            left: 1.75rem;
            bottom: 1.35rem;
            max-width: 640px;
            color: white;
        }
        .magic-header-content h1 {
            margin: 0 0 0.35rem 0;
            font-size: 2rem;
            line-height: 1.15;
            letter-spacing: 0;
        }
        .magic-header-content p {
            margin: 0;
            color: rgba(255, 255, 255, 0.88);
            font-size: 1rem;
        }
        .workflow-strip {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 0.65rem;
            margin: 0.25rem 0 1.15rem 0;
        }
        .workflow-pill {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            border: 1px solid var(--magic-border);
            border-radius: 8px;
            padding: 0.75rem 0.8rem;
            background: var(--magic-panel);
            min-height: 62px;
            box-shadow: 0 10px 24px rgba(48, 58, 55, 0.055);
        }
        .workflow-pill.done {
            border-color: #9db2aa;
            background: var(--magic-green-soft);
        }
        .workflow-pill.pending {
            background: #fbfcfb;
        }
        .workflow-icon {
            display: inline-flex;
            width: 30px;
            height: 30px;
            align-items: center;
            justify-content: center;
            border-radius: 999px;
            font-weight: 700;
            color: #65706c;
            background: #eef1f0;
            flex: 0 0 auto;
        }
        .workflow-pill.done .workflow-icon {
            color: #ffffff;
            background: var(--magic-green);
        }
        .workflow-text {
            display: flex;
            flex-direction: column;
            line-height: 1.1;
        }
        .workflow-text strong {
            color: var(--magic-text);
            font-size: 0.9rem;
        }
        .workflow-text small {
            color: var(--magic-muted);
            font-size: 0.76rem;
            margin-top: 0.2rem;
        }
        .net-grid-summary {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 1rem 0 0.5rem 0;
        }
        .net-grid-summary div {
            border: 1px solid #dbe2df;
            background: #f9fbfa;
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 10px 24px rgba(48, 58, 55, 0.055);
        }
        .net-grid-summary span {
            display: block;
            color: var(--magic-muted);
            font-size: 0.88rem;
            margin-bottom: 0.35rem;
        }
        .net-grid-summary strong {
            display: block;
            color: var(--magic-green-dark);
            font-size: 1.75rem;
            line-height: 1.1;
        }
        .cost-summary-box {
            background: var(--magic-panel);
            border: 1px solid var(--magic-border);
            border-radius: 8px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 10px 24px rgba(48, 58, 55, 0.055);
        }
        .cost-summary-box span {
            display: block;
            color: var(--magic-muted);
            font-size: 0.88rem;
            margin-bottom: 0.25rem;
        }
        .cost-summary-box strong {
            display: block;
            color: var(--magic-green-dark);
            font-size: 1.9rem;
            line-height: 1.1;
        }
        .proof-diff {
            border: 1px solid var(--magic-border);
            border-radius: 8px;
            background: var(--magic-panel);
            padding: 1rem;
            max-height: 320px;
            overflow: auto;
            line-height: 1.65;
            font-size: 0.95rem;
        }
        .proof-diff .diff-context {
            color: var(--magic-text);
        }
        .proof-diff del {
            color: #991b1b;
            background: #fee2e2;
            text-decoration: line-through;
            padding: 0.08rem 0.18rem;
            border-radius: 4px;
        }
        .proof-diff ins {
            color: var(--magic-green-dark);
            background: #d1fae5;
            text-decoration: none;
            padding: 0.08rem 0.18rem;
            border-radius: 4px;
        }
        div[data-testid="stAlert"] {
            border-radius: 8px;
            border: 1px solid var(--magic-border);
        }
        @media (max-width: 900px) {
            .workflow-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .net-grid-summary {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _app_header() -> None:
    """Render the branded app header."""
    header_path = Path("assets") / "app_header.png"
    if not header_path.exists():
        st.title("TranslatAI")
        return

    st.markdown(
        f"""
        <div class="magic-header">
            <img src="data:image/png;base64,{_image_base64(header_path)}" alt="">
            <div class="magic-header-content">
                <h1>TranslatAI</h1>
                <p>AI-assisted translation, review, alignment, and delivery in one focused workspace.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _startup_warning_area() -> None:
    """Show startup warnings once without blocking local app use."""
    if "startup_warnings" not in st.session_state:
        st.session_state.startup_warnings = run_startup_checks()
    warnings = st.session_state.startup_warnings
    if not warnings:
        return
    with st.expander("Startup checks", expanded=False):
        for warning in warnings:
            st.warning(f"{warning['area']}: {warning['message']}")


def _image_base64(path: Path) -> str:
    """Read a local image as base64 for Streamlit HTML."""
    import base64

    return base64.b64encode(path.read_bytes()).decode("ascii")


def _load_uploaded_file_once(uploaded_file) -> None:
    """Import a selected source file once per file selection."""
    file_bytes = uploaded_file.getvalue()
    signature = f"{uploaded_file.name}:{len(file_bytes)}:{hash(file_bytes)}"
    if st.session_state.last_uploaded_source_signature == signature:
        existing_type = st.session_state.get("source_file_type", "")
        existing_text = st.session_state.get("source_text", "")
        if existing_type in {"sdlxliff", "xliff", "xlf"} and "[[SEG_" in existing_text:
            # The source text may have been imported by an older version of the app.
            # Re-import it so the new SDLXLIFF cleanup logic takes effect.
            _load_uploaded_file(uploaded_file, file_bytes)
        return
    if _load_uploaded_file(uploaded_file, file_bytes):
        st.session_state.last_uploaded_source_signature = signature


def _load_uploaded_file(uploaded_file, file_bytes: bytes | None = None) -> bool:
    """Extract text from an uploaded file and place it into the source box."""
    progress = StepProgress("File import")
    try:
        progress.update(15, "Reading uploaded file")
        if file_bytes is None:
            file_bytes = uploaded_file.getvalue()
        validation_warnings = validate_source_upload(uploaded_file.name, file_bytes)
        progress.update(45, "Extracting source text")
        st.session_state.source_text = import_source_file(uploaded_file.name, file_bytes)
        if uploaded_file.name.split(".")[-1].lower() in {"sdlxliff", "xliff", "xlf"}:
            st.session_state.source_text = strip_protected_tokens(st.session_state.source_text)
        progress.update(75, "Saving file metadata")
        st.session_state.source_file_name = uploaded_file.name
        st.session_state.source_file_type = uploaded_file.name.split(".")[-1].lower()
        st.session_state.source_file_bytes = file_bytes
        st.session_state.uploaded_file_metadata = {
            "name": uploaded_file.name,
            "extension": st.session_state.source_file_type,
            "size_bytes": len(file_bytes),
        }
        _clear_downstream_outputs()
        progress.done("Source file loaded")
        st.success(f"Loaded source text from {uploaded_file.name}.")
        for warning in validation_warnings:
            st.warning(warning)
        if st.session_state.source_file_type == "pdf":
            st.info("PDF import extracts selectable text only. Exact PDF design preservation is not included.")
        if st.session_state.source_file_type == "idml":
            st.info(
                "IDML import extracts editable story text from Stories/*.xml. "
                "Same-format export preserves the IDML package and replaces story text."
            )
        if st.session_state.source_file_type in {"sdlxliff", "xliff", "xlf"}:
            st.info(
                "Bilingual file import extracts editable source segments for this workflow. "
                "SDLXLIFF tags/placeholders are protected during translation and restored during export."
            )
        return True
    except Exception as exc:
        show_streamlit_error("file_import", exc)
        return False


def _price_list_area() -> None:
    """Show the estimated GPT-5.5 API cost table."""
    with st.expander("Estimated GPT-5.5 API price list", expanded=True):
        st.dataframe(pricing_rows(), hide_index=True, use_container_width=True)
        st.caption(
            "Estimates use roughly 1,000 words = 1,300 tokens. Actual cost depends on "
            "document structure, prompt length, QA detail, and XLIFF alignment size."
        )


def _net_word_grid_area(source_text: str) -> None:
    """Show weighted/net word count analysis based on the uploaded grid."""
    with st.expander("Net word count grid analysis", expanded=False):
        st.session_state.grid_base_rate = st.number_input(
            "Base rate per word",
            min_value=0.0,
            value=float(st.session_state.grid_base_rate),
            step=0.01,
            format="%.4f",
        )
        if st.button("Analyse with net word grid", use_container_width=True):
            try:
                result = analyse_net_words(
                    source_text,
                    st.session_state.tm_entries,
                    float(st.session_state.grid_base_rate),
                )
                st.session_state.net_word_grid_rows = result["rows"]
                st.session_state.net_word_grid_summary = {
                    "Total raw words": result["total_raw_words"],
                    "Total net words": result["total_net_words"],
                    "Total cost": result["total_cost"],
                }
                st.success("Net word grid analysis completed.")
            except Exception as exc:
                st.error(f"Net word grid analysis failed: {exc}")

        if st.session_state.net_word_grid_rows:
            st.dataframe(st.session_state.net_word_grid_rows, hide_index=True, use_container_width=True)
            _net_word_grid_summary_band()
            st.caption(
                "Category rate / word = base rate x payable weight. TM fuzzy ranges depend on loaded "
                "TM data; without a loaded TM, most non-repeated text is treated as New / No match."
            )


def _net_word_grid_summary_band() -> None:
    """Show prominent net word and cost results below the grid."""
    summary = st.session_state.net_word_grid_summary
    if not summary:
        return

    st.markdown(
        f"""
        <div class="net-grid-summary">
            <div>
                <span>Total raw words</span>
                <strong>{summary["Total raw words"]:,}</strong>
            </div>
            <div>
                <span>Total net words</span>
                <strong>{summary["Total net words"]:,.2f}</strong>
            </div>
            <div>
                <span>Final cost</span>
                <strong>&euro;{summary["Total cost"]:,.2f}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _current_cost_area() -> None:
    """Show estimated API cost for this current job."""
    with st.expander("Estimated current job cost", expanded=False):
        if not st.session_state.cost_entries:
            st.info("No GPT-5.5 steps have been run yet.")
            return
        estimated_total = total_cost(st.session_state.cost_entries)
        st.markdown(
            f"""
            <div class="cost-summary-box">
                <span>Estimated total</span>
                <strong>&euro;{estimated_total:.4f}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.dataframe(st.session_state.cost_entries, hide_index=True, use_container_width=True)
        st.caption("This is an estimate based on word counts, not exact API billing.")


def _workflow_status() -> None:
    """Show a compact completion overview for the workflow."""
    steps = [
        ("Source", bool(st.session_state.source_text.strip())),
        ("Context", bool(st.session_state.tm_context.strip() or st.session_state.reference_context.strip())),
        ("Prompt", bool(st.session_state.translation_prompt.strip())),
        ("Translation", bool(st.session_state.translated_text.strip())),
        ("Proofread", bool(st.session_state.proofread_text.strip())),
        ("QA", bool(st.session_state.qa_report.strip())),
    ]
    pills = []
    for label, done in steps:
        status_class = "done" if done else "pending"
        symbol = "&#10003;" if done else "&#9675;"
        status = "Done" if done else "Pending"
        pills.append(
            f'<div class="workflow-pill {status_class}">'
            f'<span class="workflow-icon">{symbol}</span>'
            f'<span class="workflow-text"><strong>{label}</strong><small>{status}</small></span>'
            "</div>"
        )
    st.markdown(f"<div class=\"workflow-strip\">{''.join(pills)}</div>", unsafe_allow_html=True)


def _project_repository_sidebar() -> None:
    """Sidebar controls for saving and loading projects."""
    st.subheader("Project repository")
    if st.button("Save current project", use_container_width=True):
        _save_current_project()

    projects = list_projects()
    if not projects:
        st.caption("No saved projects yet.")
        return

    labels = [project["label"] for project in projects]
    selected = st.selectbox("Load saved project", [""] + labels)
    if st.button("Load selected project", use_container_width=True) and selected:
        project = projects[labels.index(selected)]
        _load_saved_project(project["path"])
    if st.button("Update selected project", use_container_width=True) and selected:
        project = projects[labels.index(selected)]
        _update_saved_project(project["path"])
    if st.button("Delete selected project", use_container_width=True) and selected:
        project = projects[labels.index(selected)]
        _delete_saved_project(project["path"])


def _save_current_project() -> None:
    """Save current session fields to the local project repository."""
    try:
        path = save_project(st.session_state.project_name, _project_state())
        st.success(f"Saved project: {path.name}")
    except Exception as exc:
        show_streamlit_error("project_save", exc)


def _load_saved_project(path: str) -> None:
    """Load saved project fields into the current session."""
    try:
        state = load_project(path)
        apply_project_snapshot(state)
        _autosave_active_project()
        st.success("Project loaded.")
    except Exception as exc:
        show_streamlit_error("project_load", exc)


def _delete_saved_project(path: str) -> None:
    """Delete one saved project from the local repository."""
    try:
        deleted_path = delete_project(path)
        st.success(f"Deleted project: {deleted_path.name}")
        st.rerun()
    except Exception as exc:
        show_streamlit_error("project_delete", exc)


def _update_saved_project(path: str) -> None:
    """Overwrite the selected saved project with current session fields."""
    try:
        updated_path = update_project(path, st.session_state.project_name, _project_state())
        st.success(f"Updated project: {updated_path.name}")
    except Exception as exc:
        show_streamlit_error("project_update", exc)


def _project_state() -> dict:
    """Collect serializable session fields for project saving."""
    return get_current_project_snapshot()


def _autosave_active_project() -> None:
    """Quietly persist the current working state so browser refresh is safe."""
    try:
        save_active_project(_project_state())
    except Exception:
        # Autosave is a convenience; it should never interrupt translation work.
        pass


def _show_text_stats(label: str, text: str) -> None:
    """Show a compact word and character count below a text field."""
    st.caption(f"{label}: {stats_label(text)}")


def _add_cost_entry(step: str, input_text: str, output_text: str = "") -> None:
    """Add one estimated API cost row for the current job."""
    st.session_state.cost_entries.append(new_cost_entry(step, input_text, output_text))


def _clear_downstream_outputs() -> None:
    """Clear generated fields when the source file changes."""
    st.session_state.analysis_report = ""
    st.session_state.translation_prompt = ""
    st.session_state.translated_text = ""
    st.session_state.proofread_text = ""
    st.session_state.proofreading_baseline_text = ""
    st.session_state.qa_report = ""
    st.session_state.rule_based_qa_warnings = []
    st.session_state.aligned_xliff_bytes = b""
    st.session_state.aligned_xliff_summary = ""
    st.session_state.aligned_rows = []
    st.session_state.realigned_xliff_bytes = b""
    st.session_state.realigned_xliff_summary = ""
    st.session_state.realigned_rows = []
    st.session_state.realigned_template_name = ""
    st.session_state.realigned_template_type = ""
    st.session_state.realigned_template_bytes = b""
    st.session_state.bilingual_review_rows = []
    st.session_state.reflow_summary = ""
    st.session_state.net_word_grid_rows = []
    st.session_state.net_word_grid_summary = {}
    st.session_state.cost_entries = []


def _start_new_project() -> None:
    """Clear the workspace so the user can start a fresh project."""
    reset_project_state()
    _autosave_active_project()
    st.success("Started a new project.")
    st.rerun()


def _load_translation_memory(tm_file) -> None:
    """Load a TMX or CSV translation memory into session state."""
    progress = StepProgress("Translation Memory import")
    try:
        progress.update(20, "Reading memory file")
        st.session_state.tm_entries = import_tm(tm_file.name, tm_file.getvalue())
        progress.update(80, "Saving entries")
        st.session_state.tm_file_name = tm_file.name
        progress.done("Memory loaded")
        st.success(f"Loaded {len(st.session_state.tm_entries)} TM entries from {tm_file.name}.")
    except Exception as exc:
        st.error(f"Translation Memory import failed: {exc}")


def _find_translation_memory_matches(source_text: str, minimum_score: int, match_limit: int) -> None:
    """Find fuzzy TM matches for the current source text."""
    progress = StepProgress("Translation Memory matching")
    try:
        progress.update(15, "Checking source and memory")
        if not source_text.strip():
            raise ValueError("Paste or upload source text first.")
        if not st.session_state.tm_entries:
            raise ValueError("Load a TMX or CSV Translation Memory first.")
        progress.update(45, "Finding fuzzy matches")
        matches = find_tm_matches(
            source_text,
            st.session_state.tm_entries,
            minimum_score=minimum_score,
            limit=match_limit,
        )
        progress.update(80, "Preparing editable match context")
        st.session_state.tm_context = format_tm_matches(matches)
        progress.done("Matching complete")
        if matches:
            st.success(f"Found {len(matches)} Translation Memory matches.")
        else:
            st.info("No Translation Memory matches found at that threshold.")
    except Exception as exc:
        st.error(f"Translation Memory matching failed: {exc}")


def _analyse_reference_files(reference_files, source_language: str, target_language: str, domain: str, model: str) -> None:
    """Extract and analyse uploaded client reference materials."""
    progress = StepProgress("Reference file analysis")
    try:
        progress.update(20, "Extracting reference text")
        references = extract_reference_texts(reference_files)
        progress.update(50, "Analysing terminology and style")
        st.session_state.reference_context = analyse_reference_files(
            references,
            source_language,
            target_language,
            domain,
            model=model.strip() or DEFAULT_MODEL,
        )
        _add_cost_entry(
            "Reference analysis",
            "\n\n".join(reference["text"] for reference in references),
            st.session_state.reference_context,
        )
        st.session_state.reference_file_names = [reference["name"] for reference in references]
        progress.done("Reference guidance ready")
        st.success(f"Analysed {len(references)} reference file(s).")
    except Exception as exc:
        st.error(f"Reference analysis failed: {exc}")


def _analyse(
    source_text: str,
    source_language: str,
    target_language: str,
    domain: str,
    model: str,
) -> None:
    """Use GPT-5.5 to analyse source text and prepare a first prompt draft."""
    progress = StepProgress("Analysis and prompt draft")
    try:
        selected_model = model.strip() or DEFAULT_MODEL
        progress.update(10, "Sending source text to GPT-5.5")
        analysis = analyse_source_text(
            source_text,
            source_language,
            target_language,
            domain,
            st.session_state.reference_context,
            model=selected_model,
        )
        _add_cost_entry(
            "Source analysis",
            source_text + "\n\n" + st.session_state.reference_context,
            analysis,
        )
        progress.update(55, "Formatting analysis")
        st.session_state.analysis_report = format_analysis_report(analysis)
        progress.update(70, "Generating prompt draft")
        st.session_state.translation_prompt = build_translation_prompt(
            source_language,
            target_language,
            domain,
            st.session_state.analysis_report,
            source_text,
            st.session_state.tm_context,
            st.session_state.reference_context,
            model=selected_model,
        )
        _add_cost_entry(
            "Prompt draft",
            st.session_state.analysis_report + "\n\n" + st.session_state.tm_context + "\n\n" + st.session_state.reference_context,
            st.session_state.translation_prompt,
        )
        progress.done("Analysis and prompt ready")
        st.success("GPT-5.5 analysed the source text and generated a prompt draft.")
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")


def _build_prompt(
    source_text: str,
    source_language: str,
    target_language: str,
    domain: str,
    model: str,
) -> None:
    """Use GPT-5.5 to rebuild the prompt from the current editable analysis."""
    progress = StepProgress("Prompt generation")
    try:
        progress.update(20, "Sending analysis to GPT-5.5")
        st.session_state.translation_prompt = build_translation_prompt(
            source_language,
            target_language,
            domain,
            st.session_state.analysis_report,
            source_text,
            st.session_state.tm_context,
            st.session_state.reference_context,
            model=model.strip() or DEFAULT_MODEL,
        )
        _add_cost_entry(
            "Prompt generation",
            st.session_state.analysis_report + "\n\n" + st.session_state.tm_context + "\n\n" + st.session_state.reference_context,
            st.session_state.translation_prompt,
        )
        progress.done("Prompt generated")
        st.success("GPT-5.5 generated the translation prompt.")
    except Exception as exc:
        st.error(f"Prompt generation failed: {exc}")


def _prompt_archive_area(source_language: str, target_language: str, domain: str) -> None:
    """Show controls for saving and reusing prompt templates."""
    with st.expander("Prompt archive", expanded=False):
        st.session_state.prompt_archive_title = st.text_input(
            "Prompt template name",
            value=st.session_state.prompt_archive_title,
            placeholder="Example: Legal contract EN to SL",
        )

        archive_entries = load_prompt_archive()
        labels = [_prompt_label(entry) for entry in archive_entries]
        selected_label = st.selectbox(
            "Saved prompt template",
            [""] + labels,
            index=0,
        )
        selected_entry = archive_entries[labels.index(selected_label)] if selected_label else None

        col_save, col_update, col_load = st.columns(3)
        with col_save:
            if st.button("Save current prompt"):
                _save_current_prompt(source_language, target_language, domain)
        with col_update:
            if st.button("Update current prompt"):
                _update_current_prompt(source_language, target_language, domain, selected_entry)
        with col_load:
            if st.button("Load prompt template") and selected_entry:
                progress = StepProgress("Prompt template load")
                progress.update(50, "Loading selected template")
                st.session_state.translation_prompt = selected_entry["prompt"]
                st.session_state.prompt_archive_title = selected_entry.get("title", "")
                st.session_state.prompt_archive_selected_id = selected_entry.get("id", "")
                progress.done("Template loaded")
                st.success("Prompt template loaded into the editable prompt box.")

def _save_current_prompt(source_language: str, target_language: str, domain: str) -> None:
    """Save the current editable translation prompt."""
    progress = StepProgress("Prompt archive save")
    try:
        progress.update(50, "Saving prompt template")
        entry = save_prompt_to_archive(
            st.session_state.translation_prompt,
            source_language,
            target_language,
            domain,
            st.session_state.prompt_archive_title,
        )
        st.session_state.prompt_archive_selected_id = entry.get("id", "")
        progress.done("Prompt saved")
        st.success(f"Saved prompt template: {entry['title']}")
    except Exception as exc:
        st.error(f"Prompt archive save failed: {exc}")


def _update_current_prompt(
    source_language: str,
    target_language: str,
    domain: str,
    selected_entry: dict[str, str] | None = None,
) -> None:
    """Update the selected saved prompt with the current editable prompt."""
    progress = StepProgress("Prompt archive update")
    try:
        progress.update(50, "Updating prompt template")
        prompt_id = (selected_entry or {}).get("id") or st.session_state.prompt_archive_selected_id
        entry = update_prompt_in_archive(
            prompt_id,
            st.session_state.translation_prompt,
            source_language,
            target_language,
            domain,
            st.session_state.prompt_archive_title,
        )
        st.session_state.prompt_archive_selected_id = entry.get("id", "")
        progress.done("Prompt updated")
        st.success(f"Updated prompt template: {entry['title']}")
    except Exception as exc:
        st.error(f"Prompt archive update failed: {exc}")


def _prompt_label(entry: dict[str, str]) -> str:
    """Create a readable label for a saved prompt."""
    return (
        f"{entry.get('created_at', '')} | {entry.get('title', 'Untitled')} | "
        f"{entry.get('source_language', '')} to {entry.get('target_language', '')} | "
        f"{entry.get('domain', '')}"
    )


def _translate(source_text: str, source_language: str, target_language: str, domain: str, model: str) -> None:
    """Call the translator and save the editable result."""
    progress = StepProgress("Translation")
    try:
        progress.update(15, "Preparing translation request")
        if st.session_state.translation_prompt.strip():
            st.session_state.translation_prompt = ensure_text_for_translation_section(
                st.session_state.translation_prompt,
                source_text,
            )
        if st.session_state.source_file_type == "sdlxliff" and st.session_state.source_file_bytes:
            result = translate_sdlxliff_segments(
                st.session_state.source_file_bytes,
                st.session_state.translation_prompt,
                st.session_state.tm_context,
                st.session_state.reference_context,
                source_language,
                target_language,
                domain,
                model=model.strip() or DEFAULT_MODEL,
                progress_callback=lambda current, total: progress.update(
                    min(85, 20 + round((current / max(total, 1)) * 60)),
                    f"Translating SDLXLIFF segment {current}/{total}",
                ),
            )
            st.session_state.translated_text = result.target_text
            st.session_state.bilingual_review_rows = result.review_rows
            _ensure_bilingual_review_open_flags()
            st.session_state.bilingual_review_editor_version += 1
            st.session_state.bilingual_review_status = (
                f"Validated {len(result.review_rows)} SDLXLIFF segment(s) with protected tags."
            )
        else:
            st.session_state.translated_text = translate_text(
                source_text,
                st.session_state.translation_prompt,
                st.session_state.tm_context,
                st.session_state.reference_context,
                source_language,
                target_language,
                domain,
                model=model.strip() or DEFAULT_MODEL,
            )
            st.session_state.bilingual_review_rows = []
        _add_cost_entry(
            "Translation",
            st.session_state.translation_prompt + "\n\n" + st.session_state.tm_context + "\n\n" + st.session_state.reference_context,
            st.session_state.translated_text,
        )
        st.session_state.aligned_xliff_bytes = b""
        st.session_state.aligned_xliff_summary = ""
        st.session_state.aligned_rows = []
        st.session_state.realigned_xliff_bytes = b""
        st.session_state.realigned_xliff_summary = ""
        st.session_state.realigned_rows = []
        st.session_state.realigned_template_name = ""
        st.session_state.realigned_template_type = ""
        st.session_state.realigned_template_bytes = b""
        st.session_state.reflow_summary = ""
        progress.done("Translation completed")
        st.success("Translation completed.")
    except Exception as exc:
        st.error(str(exc))


def _proofread(target_language: str, domain: str, model: str) -> None:
    """Use GPT-5.5 to proofread the editable translation."""
    progress = StepProgress("Proofreading")
    try:
        progress.update(20, "Sending translation to GPT-5.5")
        st.session_state.proofread_text = proofread_translation(
            st.session_state.translated_text,
            target_language,
            domain,
            st.session_state.tm_context,
            st.session_state.reference_context,
            model=model.strip() or DEFAULT_MODEL,
        )
        st.session_state.proofreading_baseline_text = st.session_state.translated_text
        _add_cost_entry(
            "Proofreading",
            st.session_state.translated_text + "\n\n" + st.session_state.tm_context + "\n\n" + st.session_state.reference_context,
            st.session_state.proofread_text,
        )
        st.session_state.aligned_xliff_bytes = b""
        st.session_state.aligned_xliff_summary = ""
        st.session_state.aligned_rows = []
        st.session_state.realigned_xliff_bytes = b""
        st.session_state.realigned_xliff_summary = ""
        st.session_state.realigned_rows = []
        st.session_state.bilingual_review_rows = []
        st.session_state.reflow_summary = ""
        progress.done("Proofreading completed")
        st.success("Proofreading completed.")
    except Exception as exc:
        st.error(f"Proofreading failed: {exc}")


def _qa(
    source_text: str,
    source_language: str,
    target_language: str,
    domain: str,
    model: str,
) -> None:
    """Use GPT-5.5 to run source-target QA checks."""
    progress = StepProgress("QA check")
    try:
        progress.update(20, "Preparing source-target comparison")
        text_for_qa = _final_translation_text()
        st.session_state.rule_based_qa_warnings = run_rule_based_qa(
            source_text,
            text_for_qa,
            st.session_state.bilingual_review_rows,
        )
        progress.update(45, "Sending QA request to GPT-5.5")
        st.session_state.qa_report = run_qa_check(
            source_text,
            text_for_qa,
            source_language,
            target_language,
            domain,
            st.session_state.tm_context,
            st.session_state.reference_context,
            model=model.strip() or DEFAULT_MODEL,
        )
        _add_cost_entry(
            "QA check",
            source_text + "\n\n" + text_for_qa + "\n\n" + st.session_state.tm_context + "\n\n" + st.session_state.reference_context,
            st.session_state.qa_report,
        )
        progress.done("QA completed")
        st.success("QA check completed.")
    except Exception as exc:
        st.error(f"QA check failed: {exc}")


def _build_bilingual_review_table(source_text: str) -> None:
    """Create editable source/target rows for manual bilingual review."""
    try:
        target_text = _final_translation_text()
        fixed_segments = _fixed_bilingual_source_segments(source_text)
        if fixed_segments:
            target_segments = sentence_segments(target_text)
            max_rows = max(len(fixed_segments), len(target_segments))
            st.session_state.bilingual_review_rows = [
                {
                    "Segment": index + 1,
                    "Source": fixed_segments[index] if index < len(fixed_segments) else "",
                    "Target": target_segments[index] if index < len(target_segments) else "",
                    "Review note": "Original SDLXLIFF/XLIFF source segment." if index < len(fixed_segments) else "",
                }
                for index in range(max_rows)
            ]
        else:
            st.session_state.bilingual_review_rows = build_review_rows(source_text, target_text)
        _ensure_bilingual_review_open_flags()
        st.session_state.bilingual_review_editor_version += 1
        st.success(f"Built bilingual review table with {len(st.session_state.bilingual_review_rows)} rows.")
    except Exception as exc:
        st.error(f"Bilingual review table failed: {exc}")


def _apply_bilingual_review_table() -> None:
    """Use edited review rows as the final target text."""
    try:
        st.session_state.proofread_text = target_text_from_rows(st.session_state.bilingual_review_rows)
        st.session_state.aligned_xliff_bytes = b""
        st.session_state.aligned_xliff_summary = ""
        st.session_state.aligned_rows = []
        st.session_state.realigned_xliff_bytes = b""
        st.session_state.realigned_xliff_summary = ""
        st.session_state.realigned_rows = []
        st.session_state.realigned_template_name = ""
        st.session_state.realigned_template_type = ""
        st.session_state.realigned_template_bytes = b""
        st.session_state.reflow_summary = ""
        st.success("Reviewed target text applied as the final translation.")
    except Exception as exc:
        st.error(f"Could not apply bilingual review table: {exc}")


def _realign_bilingual_review_table(
    source_text: str,
    target_text: str,
    source_language: str,
    target_language: str,
    model: str,
) -> None:
    """Re-align the manual bilingual review table using GPT-5.5."""
    progress = StepProgress("Bilingual review re-alignment")
    try:
        progress.update(30, "Aligning reviewed target text")
        fixed_segments = _fixed_bilingual_source_segments(source_text)
        if fixed_segments:
            rows = align_fixed_source_segments(
                fixed_segments,
                target_text,
                source_language,
                target_language,
                model=model.strip() or DEFAULT_MODEL,
            )
        else:
            rows = align_for_xliff(
                source_text,
                target_text,
                source_language,
                target_language,
                model=model.strip() or DEFAULT_MODEL,
            )
        st.session_state.bilingual_review_rows = [
            {
                "Open": False,
                "Segment": index,
                "Source": row.get("source", ""),
                "Target": row.get("target", ""),
                "Review note": row.get("note", ""),
            }
            for index, row in enumerate(rows, start=1)
        ]
        st.session_state.aligned_rows = rows
        st.session_state.aligned_xliff_bytes = create_xliff_from_aligned_rows(
            rows,
            source_language,
            target_language,
            aligned_cleanly=True,
        )
        st.session_state.aligned_xliff_summary = _alignment_summary("Aligned bilingual review", rows)
        _add_cost_entry("Bilingual review re-alignment", source_text + "\n\n" + target_text, str(rows))
        progress.done("Review table re-aligned")
        st.session_state.bilingual_review_editor_version += 1
        st.session_state.bilingual_review_status = "Bilingual review table re-aligned and refreshed."
        st.rerun()
    except Exception as exc:
        st.error(f"Bilingual review re-alignment failed: {exc}")


def _ensure_bilingual_review_open_flags() -> None:
    """Ensure the review table has one clickable Open checkbox column."""
    if not st.session_state.bilingual_review_rows:
        return

    current_index = int(st.session_state.review_row_index or 1)
    for index, row in enumerate(st.session_state.bilingual_review_rows, start=1):
        row.setdefault("Open", index == current_index)
    if not any(bool(row.get("Open")) for row in st.session_state.bilingual_review_rows):
        safe_index = max(1, min(current_index, len(st.session_state.bilingual_review_rows)))
        st.session_state.bilingual_review_rows[safe_index - 1]["Open"] = True


def _open_selected_bilingual_review_row() -> None:
    """Use the clicked Open checkbox to switch the expanded editor above."""
    previous_index = int(st.session_state.review_row_index or 1)
    checked_indices = [
        index
        for index, row in enumerate(st.session_state.bilingual_review_rows, start=1)
        if bool(row.get("Open"))
    ]
    newly_checked = [index for index in checked_indices if index != previous_index]
    selected_index = newly_checked[0] if newly_checked else (checked_indices[0] if checked_indices else None)

    if selected_index is None:
        return

    for index, row in enumerate(st.session_state.bilingual_review_rows, start=1):
        row["Open"] = index == selected_index

    if selected_index != previous_index:
        st.session_state.review_row_index = selected_index
        st.session_state.bilingual_review_editor_version += 1
        st.rerun()


def _expanded_review_row_editor() -> None:
    """Show one bilingual review row in large text areas."""
    if not st.session_state.bilingual_review_rows:
        return

    index = int(st.session_state.review_row_index) - 1
    row = st.session_state.bilingual_review_rows[index]
    editor_version = st.session_state.bilingual_review_editor_version
    st.caption(f"Editing segment {row.get('Segment')}")
    source_col, target_col = st.columns(2)
    with source_col:
        st.text_area(
            "Full source segment",
            value=str(row.get("Source") or ""),
            height=180,
            disabled=True,
            key=f"review_source_{editor_version}_{index}",
        )
    with target_col:
        updated_target = st.text_area(
            "Full target segment",
            value=str(row.get("Target") or ""),
            height=180,
            key=f"review_target_{editor_version}_{index}",
        )
        updated_note = st.text_input(
            "Review note",
            value=str(row.get("Review note") or ""),
            key=f"review_note_{editor_version}_{index}",
        )

    st.session_state.bilingual_review_rows[index]["Target"] = updated_target
    st.session_state.bilingual_review_rows[index]["Review note"] = updated_note


def _proofreading_changes_view() -> None:
    """Show visible proofreading changes while keeping exported text clean."""
    if not st.session_state.translated_text.strip() or not st.session_state.proofread_text.strip():
        return

    if not st.session_state.proofreading_baseline_text.strip():
        st.session_state.proofreading_baseline_text = st.session_state.translated_text

    changes = proofreading_changes(
        st.session_state.proofreading_baseline_text,
        st.session_state.proofread_text,
    )
    with st.expander("Visible proofreading changes", expanded=False):
        st.markdown(
            f'<div class="proof-diff">{proofreading_diff_html(st.session_state.proofreading_baseline_text, st.session_state.proofread_text)}</div>',
            unsafe_allow_html=True,
        )
        if not changes:
            st.success("No unresolved proofreading changes.")
            return

        labels = [_proofreading_change_label(change) for change in changes]
        selected = st.selectbox("Select correction", labels)
        selected_change = changes[labels.index(selected)]

        col_accept, col_reject, col_accept_all, col_reject_all = st.columns(4)
        with col_accept:
            if st.button("Accept selected correction", use_container_width=True):
                st.session_state.proofreading_baseline_text = accept_proofreading_change(
                    st.session_state.proofreading_baseline_text,
                    st.session_state.proofread_text,
                    int(selected_change["id"]),
                )
                st.success("Correction accepted.")
        with col_reject:
            if st.button("Reject selected correction", use_container_width=True):
                st.session_state.proofread_text = reject_proofreading_change(
                    st.session_state.proofreading_baseline_text,
                    st.session_state.proofread_text,
                    int(selected_change["id"]),
                )
                st.success("Correction rejected and reverted.")
        with col_accept_all:
            if st.button("Accept all corrections", use_container_width=True):
                st.session_state.proofreading_baseline_text = st.session_state.proofread_text
                st.success("All corrections accepted.")
        with col_reject_all:
            if st.button("Reject all corrections", use_container_width=True):
                st.session_state.proofread_text = st.session_state.proofreading_baseline_text
                st.success("All corrections rejected and reverted.")
        st.caption("Red text was removed; green text was added. Exports and bilingual review use the clean proofread text.")


def _proofreading_change_label(change: dict[str, str | int]) -> str:
    """Readable label for one proofreading correction."""
    original = str(change.get("original") or "(empty)")
    proofread = str(change.get("proofread") or "(empty)")
    return f"{change['id']}. {change['type']}: {original[:60]} -> {proofread[:60]}"


def _project_readiness_check(source_text: str, final_translation: str) -> None:
    """Show non-blocking export readiness checks."""
    checks = _readiness_rows(source_text, final_translation)
    needs_attention = sum(1 for row in checks if row["Status"] == "Needs attention")
    optional = sum(1 for row in checks if row["Status"] == "Optional")

    with st.expander("Project readiness check", expanded=True):
        if needs_attention:
            st.warning(
                f"{needs_attention} item(s) need attention. Export is still available; decide based on the job."
            )
        elif optional:
            st.info(f"Ready to export. {optional} optional improvement(s) are available.")
        else:
            st.success("Ready to export.")
        st.dataframe(checks, hide_index=True, use_container_width=True)
        st.caption("This checklist is advisory only. It never blocks export buttons.")


def _readiness_rows(source_text: str, final_translation: str) -> list[dict[str, str]]:
    """Build export readiness rows for the current project."""
    rows = []
    rows.append(_readiness_row("Source text", bool(source_text.strip()), "Source text is present.", "Source text is missing."))
    rows.append(_readiness_row("Final translation", bool(final_translation.strip()), "Final translation is present.", "Translate or proofread before export."))
    rows.append(_proofreading_readiness_row())
    rows.append(_manual_review_readiness_row())
    rows.append(_qa_readiness_row())
    rows.append(_file_template_readiness_row(final_translation))
    rows.append(_alignment_readiness_row())
    rows.append(_context_readiness_row())
    rows.append(_export_path_readiness_row())
    return rows


def _readiness_row(item: str, ready: bool, ready_detail: str, attention_detail: str) -> dict[str, str]:
    """Create one readiness row."""
    return {
        "Check": item,
        "Status": "Ready" if ready else "Needs attention",
        "Details": ready_detail if ready else attention_detail,
    }


def _optional_row(item: str, ready: bool, ready_detail: str, optional_detail: str) -> dict[str, str]:
    """Create one optional readiness row."""
    return {
        "Check": item,
        "Status": "Ready" if ready else "Optional",
        "Details": ready_detail if ready else optional_detail,
    }


def _proofreading_readiness_row() -> dict[str, str]:
    if st.session_state.proofread_text.strip():
        changes = proofreading_changes(
            st.session_state.proofreading_baseline_text or st.session_state.translated_text,
            st.session_state.proofread_text,
        )
        if changes:
            return {
                "Check": "Proofreading",
                "Status": "Optional",
                "Details": f"{len(changes)} visible proofreading change(s) are still unresolved.",
            }
        return {"Check": "Proofreading", "Status": "Ready", "Details": "Proofread text is available."}
    return _optional_row("Proofreading", False, "", "Proofreading has not been run or saved.")


def _manual_review_readiness_row() -> dict[str, str]:
    rows = _review_table_aligned_rows()
    if rows:
        missing = sum(1 for row in rows if not row.get("source") or not row.get("target"))
        if missing:
            return {
                "Check": "Manual bilingual review",
                "Status": "Needs attention",
                "Details": f"{missing} review row(s) have missing source or target text.",
            }
        return {"Check": "Manual bilingual review", "Status": "Ready", "Details": f"{len(rows)} reviewed bilingual row(s) are available."}
    return _optional_row("Manual bilingual review", False, "", "No manual bilingual review rows yet.")


def _qa_readiness_row() -> dict[str, str]:
    return _optional_row(
        "QA check",
        bool(st.session_state.qa_report.strip()),
        "QA report is available.",
        "QA has not been run yet.",
    )


def _file_template_readiness_row(final_translation: str) -> dict[str, str]:
    file_type = st.session_state.source_file_type
    if file_type == "docx":
        if not st.session_state.source_file_bytes:
            return {"Check": "Formatted DOCX template", "Status": "Needs attention", "Details": "Original DOCX bytes are missing. Re-upload the source DOCX for formatted export."}
        try:
            paragraph_count = source_docx_paragraph_count(st.session_state.source_file_bytes)
            target_lines = len([line for line in final_translation.splitlines() if line.strip()])
            return {
                "Check": "Formatted DOCX template",
                "Status": "Ready",
                "Details": f"Original DOCX has {paragraph_count} paragraph(s). Export will fit {target_lines} target line(s) into that layout.",
            }
        except Exception as exc:
            return {"Check": "Formatted DOCX template", "Status": "Needs attention", "Details": str(exc)}
    if file_type in BILINGUAL_EXTENSIONS:
        if st.session_state.source_file_bytes:
            try:
                count = bilingual_source_segment_count(st.session_state.source_file_bytes)
                return {"Check": "Same-format bilingual template", "Status": "Ready", "Details": f"Original {file_type.upper()} has {count} source segment(s)."}
            except Exception as exc:
                return {"Check": "Same-format bilingual template", "Status": "Needs attention", "Details": str(exc)}
        return {"Check": "Same-format bilingual template", "Status": "Needs attention", "Details": f"Original {file_type.upper()} bytes are missing. Re-upload the source file for same-format export."}
    return {"Check": "Input file template", "Status": "Optional", "Details": "No same-format template export is available for this input type."}


def _alignment_readiness_row() -> dict[str, str]:
    if st.session_state.source_file_type in BILINGUAL_EXTENSIONS:
        rows = _bilingual_export_rows()
        if not rows:
            return {"Check": "Bilingual alignment", "Status": "Optional", "Details": "Same-format export can auto-fit target text, but reviewed alignment is better for TM quality."}
        low_confidence = sum(1 for row in rows if int(row.get("confidence", 0) or 0) < 90)
        if low_confidence:
            return {"Check": "Bilingual alignment", "Status": "Needs attention", "Details": f"{low_confidence} aligned row(s) are below 90% confidence."}
        return {"Check": "Bilingual alignment", "Status": "Ready", "Details": f"{len(rows)} high-confidence row(s) available."}
    if st.session_state.sdlxliff_template_bytes:
        return {"Check": "SDLXLIFF template", "Status": "Ready", "Details": f"Template loaded: {st.session_state.sdlxliff_template_name}"}
    return {"Check": "Bilingual alignment", "Status": "Optional", "Details": "Alignment is mainly needed for SDLXLIFF/XLIFF/TMX exports, not formatted DOCX/PDF."}


def _context_readiness_row() -> dict[str, str]:
    has_context = bool(st.session_state.tm_context.strip() or st.session_state.reference_context.strip())
    return _optional_row(
        "TM/reference context",
        has_context,
        "TM or reference context is available.",
        "No TM/reference context has been added.",
    )


def _export_path_readiness_row() -> dict[str, str]:
    rows = _review_table_aligned_rows()
    if rows:
        detail = "Bilingual exports will use manual bilingual review rows."
    elif st.session_state.aligned_rows:
        detail = "Bilingual exports will use prepared aligned rows."
    elif st.session_state.realigned_rows:
        detail = "Bilingual exports will use re-aligned uploaded XLIFF rows."
    elif st.session_state.source_file_type in BILINGUAL_EXTENSIONS:
        detail = "Same-format export will auto-fit final target text to source segments."
    elif st.session_state.source_file_type == "docx":
        detail = "Target DOCX will use the original DOCX layout template."
    else:
        detail = "Exports will use the final plain target text."
    return {"Check": "Export source", "Status": "Ready", "Details": detail}


def _export_area(
    include_report: bool,
    source_text: str,
    source_language: str,
    target_language: str,
    model: str,
) -> None:
    """Show a simple same-format export button."""
    st.subheader("Export")
    final_translation = _final_translation_text()
    export_base = _export_base_name()
    file_type = (st.session_state.source_file_type or "").lower()

    if not file_type:
        st.info("Upload a source file first. The export button will match that file type.")
        return
    if not final_translation.strip():
        st.info("Translate or proofread the text first. The export button will appear when final target text exists.")
        return

    _simple_same_format_export_button(export_base, file_type, final_translation)
    _simple_same_format_warning(file_type)


def _simple_same_format_export_button(export_base: str, file_type: str, final_translation: str) -> None:
    """Prepare the same-format file and show one clear download button."""
    file_name = f"{export_base}_target.{file_type}"
    label = f"Download {file_type.upper()}"
    try:
        data, mime_type, note = _same_format_export_payload(file_type, final_translation)
        st.download_button(
            label,
            data=data,
            file_name=file_name,
            mime=mime_type,
            use_container_width=True,
            type="primary",
            key="simple_same_format_export",
        )
        if note:
            st.caption(note)
    except Exception as exc:
        st.button(label, use_container_width=True, disabled=True)
        st.error(f"Export file could not be prepared yet. {exc}")


def _same_format_export_payload(file_type: str, target_text: str) -> tuple[bytes, str, str]:
    """Create the actual same-format export bytes for the simple export UI."""
    if file_type in BILINGUAL_EXTENSIONS:
        if not st.session_state.source_file_bytes:
            raise ValueError("Re-upload the original bilingual source file first.")
        if file_type == "sdlxliff":
            rows = _review_table_aligned_rows()
            if not rows:
                raise ValueError(
                    "Run Translate text first so the app can create validated SDLXLIFF target rows."
                )
            target_segments = validate_and_repair_sdlxliff_translations(
                st.session_state.source_file_bytes,
                target_segments_from_rows(rows),
            )
            data = create_translated_bilingual_file(st.session_state.source_file_bytes, target_segments)
            return data, "application/xliff+xml", "Exports only validated SDLXLIFF rows with approved protected tags."
        rows = _bilingual_export_rows()
        required_count = bilingual_source_segment_count(st.session_state.source_file_bytes)
        target_segments = target_segments_from_rows(rows) if rows else target_segments_from_text(target_text)
        if len(target_segments) != required_count:
            target_segments = fit_target_segments_to_count(target_text, required_count)
        data = create_translated_bilingual_file(st.session_state.source_file_bytes, target_segments)
        return data, "application/xliff+xml", "Uses the uploaded bilingual file as the template."

    if not st.session_state.source_file_bytes and file_type in {"docx", "xlsx", "xlsm", "idml"}:
        raise ValueError("Re-upload the original source file first.")
    return create_same_format_file(file_type, st.session_state.source_file_bytes, target_text)


def _simple_same_format_warning(file_type: str) -> None:
    """Explain the few formats where exact design preservation is limited."""
    if file_type in {"docx", "xlsx", "xlsm", "idml", "sdlxliff", "xliff", "xlf"}:
        st.success("The app will use the uploaded file as the template and preserve the structure as much as possible.")
    elif file_type == "pdf":
        st.warning("PDF export keeps the file type, but the original PDF design is regenerated rather than preserved.")
    elif file_type == "xls":
        st.warning("Legacy XLS export keeps an Excel-openable file, but the original XLS design is not fully preserved.")
    else:
        st.info("This format has little or no visual design to preserve.")


def _export_summary_strip(final_translation: str) -> None:
    """Show compact context so the user knows which export path applies."""
    file_type = (st.session_state.source_file_type or "plain text").upper()
    if st.session_state.proofread_text.strip():
        target_status = "Proofread"
    elif st.session_state.translated_text.strip():
        target_status = "Translated"
    else:
        target_status = "Missing"
    rows = _bilingual_export_rows()
    if _review_table_aligned_rows():
        bilingual_status = "Manual review rows"
    elif rows:
        bilingual_status = "Aligned rows"
    elif st.session_state.source_file_type in BILINGUAL_EXTENSIONS:
        bilingual_status = "Auto-fit available"
    else:
        bilingual_status = "Optional"

    col1, col2, col3 = st.columns(3)
    col1.metric("Source type", file_type)
    col2.metric("Final target", target_status)
    col3.metric("Bilingual export", bilingual_status)


def _recommended_export_panel(
    export_base: str,
    source_text: str,
    final_translation: str,
    source_language: str,
    target_language: str,
    model: str,
) -> None:
    """Show the one path that makes most sense for the current source file."""
    file_type = st.session_state.source_file_type
    if file_type in BILINGUAL_EXTENSIONS:
        st.markdown("**Recommended output: Trados bilingual file**")
        st.info(
            "Because the source is SDLXLIFF/XLIFF, export the same bilingual format for Trados. "
            "Alignment and manual review improve TM quality, but the file can still be downloaded without them."
        )
        _primary_bilingual_actions(
            export_base,
            source_text,
            final_translation,
            source_language,
            target_language,
            model,
            key_prefix="recommended",
        )
        return

    st.markdown("**Recommended output: client-ready target file**")
    if file_type == "docx":
        st.info("Because the source is DOCX, use the original DOCX as the formatting template for the target file.")
        _docx_client_actions(export_base, final_translation, target_language, model, key_prefix="recommended")
    elif file_type:
        st.info("Use same-format export when available. PDF is available as a simple fallback.")
        _non_docx_client_actions(export_base, final_translation, key_prefix="recommended")
    else:
        st.info("No uploaded source file is active. Export is limited to the final target text.")
        _download_pdf("PDF", f"{export_base}_target.pdf", "Translation", final_translation, key="recommended_pdf")


def _client_files_export_panel(
    export_base: str,
    final_translation: str,
    target_language: str,
    model: str,
) -> None:
    """Client-facing target files, separate from Trados/CAT files."""
    st.markdown("**Client deliverables**")
    if st.session_state.source_file_type in BILINGUAL_EXTENSIONS:
        st.info(
            "For SDLXLIFF/XLIFF projects, the clean final DOCX is normally exported from Trados after opening "
            "the translated bilingual file. Use these only as plain fallback deliverables."
        )
        _download_pdf("PDF", f"{export_base}_target.pdf", "Translation", final_translation, key="client_pdf_bilingual")
        return

    if st.session_state.source_file_type == "docx":
        _docx_client_actions(export_base, final_translation, target_language, model, key_prefix="client")
    else:
        _non_docx_client_actions(export_base, final_translation, key_prefix="client")


def _docx_client_actions(export_base: str, final_translation: str, target_language: str, model: str, key_prefix: str) -> None:
    """DOCX-specific export actions."""
    col1, col2, col3 = st.columns(3)
    with col1:
        _download_formatted_docx(
            "DOCX - preserve formatting",
            f"{export_base}_target.docx",
            final_translation,
            key=f"{key_prefix}_target_docx",
        )
        st.caption("Uses the uploaded DOCX as the formatting template.")
    with col2:
        if st.session_state.reflow_summary:
            st.success(st.session_state.reflow_summary)
        if st.button("Reflow DOCX text", use_container_width=True, key=f"{key_prefix}_reflow_docx"):
            _reflow_for_target_docx(final_translation, target_language, model)
        st.caption("Use if paragraph count prevents DOCX export.")
    with col3:
        _download_pdf(
            "PDF",
            f"{export_base}_target.pdf",
            "Translation",
            final_translation,
            key=f"{key_prefix}_target_pdf",
        )


def _non_docx_client_actions(export_base: str, final_translation: str, key_prefix: str) -> None:
    """Client file actions for TXT, CSV, Excel, PDF, IDML, and plain text."""
    col1, col2 = st.columns(2)
    with col1:
        extension = st.session_state.source_file_type or "txt"
        _download_same_format_final_file(
            f"{export_base}_target.{extension}",
            final_translation,
            label="Same format as input",
            key=f"{key_prefix}_same_format",
        )
    with col2:
        _download_pdf(
            "PDF",
            f"{export_base}_target.pdf",
            "Translation",
            final_translation,
            key=f"{key_prefix}_pdf",
        )


def _cat_files_export_panel(
    export_base: str,
    source_text: str,
    final_translation: str,
    source_language: str,
    target_language: str,
    model: str,
) -> None:
    """Trados/CAT exchange exports and repair tools."""
    st.markdown("**Trados and CAT files**")
    _bilingual_workflow_status()
    if st.session_state.source_file_type in BILINGUAL_EXTENSIONS:
        _primary_bilingual_actions(
            export_base,
            source_text,
            final_translation,
            source_language,
            target_language,
            model,
            key_prefix="cat",
        )
        _alignment_status_message()
    else:
        st.info(
            "For a real SDLXLIFF, upload a Trados-created SDLXLIFF template below. "
            "Generic XLIFF can be created without a template."
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            _download_xliff(
                "Generic XLIFF",
                f"{export_base}_bilingual.xliff",
                source_text,
                final_translation,
                source_language,
                target_language,
                key="cat_generic_xliff",
            )
        with col2:
            _download_sdlxliff(
                "SDLXLIFF from template",
                f"{export_base}_bilingual.sdlxliff",
                source_text,
                final_translation,
                source_language,
                target_language,
                key="cat_template_sdlxliff",
            )
        with col3:
            _download_bilingual_docx(
                "Bilingual review DOCX",
                f"{export_base}_bilingual.docx",
                key="cat_bilingual_docx",
            )
        if st.session_state.aligned_xliff_summary or st.session_state.realigned_xliff_summary:
            _alignment_status_message()

    with st.expander("Templates and repair tools", expanded=False):
        _sdlxliff_template_loader()
        st.divider()
        _realign_bilingual_file_panel(export_base, source_language, target_language, model)


def _primary_bilingual_actions(
    export_base: str,
    source_text: str,
    final_translation: str,
    source_language: str,
    target_language: str,
    model: str,
    key_prefix: str,
) -> None:
    """Primary alignment and same-format bilingual export actions."""
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Prepare alignment", type="primary", use_container_width=True, key=f"{key_prefix}_prepare_alignment"):
            _prepare_aligned_xliff(
                source_text,
                final_translation,
                source_language,
                target_language,
                model,
            )
        st.caption("Best before exporting to Trados/TM.")
    with col2:
        if st.button("Quick check", use_container_width=True, key=f"{key_prefix}_quick_alignment"):
            _quick_alignment_check(source_language, target_language, model)
        st.caption("Repairs only weak alignment rows.")
    with col3:
        _download_latest_aligned_bilingual_version(
            export_base,
            final_translation,
            source_text,
            source_language,
            target_language,
            key_prefix=key_prefix,
        )


def _alignment_status_message() -> None:
    """Show one current alignment status message."""
    if st.session_state.aligned_xliff_summary:
        st.success(st.session_state.aligned_xliff_summary)
    elif st.session_state.realigned_xliff_summary:
        st.success(st.session_state.realigned_xliff_summary)
    else:
        st.info("You can download now, or prepare alignment first for a better Trados-ready bilingual file.")


def _sdlxliff_template_loader() -> None:
    """Load an optional real SDLXLIFF template for non-SDLXLIFF sources."""
    sdlxliff_template = st.file_uploader(
        "Optional SDLXLIFF template",
        type=["sdlxliff"],
        help="Use a real Trados-created SDLXLIFF template when the original source was DOCX, Excel, PDF, TXT, CSV, or IDML.",
    )
    if sdlxliff_template and st.button("Use SDLXLIFF template", use_container_width=True, key="use_sdlxliff_template"):
        try:
            template_bytes = sdlxliff_template.getvalue()
            validate_sdlxliff_template(sdlxliff_template.name, template_bytes)
            st.session_state.sdlxliff_template_name = sdlxliff_template.name
            st.session_state.sdlxliff_template_bytes = template_bytes
            st.success(f"Loaded SDLXLIFF template: {sdlxliff_template.name}")
            st.rerun()
        except Exception as exc:
            st.error(f"SDLXLIFF template could not be loaded: {exc}")
    if st.session_state.sdlxliff_template_name:
        st.caption(f"Current SDLXLIFF template: {st.session_state.sdlxliff_template_name}")


def _realign_bilingual_file_panel(export_base: str, source_language: str, target_language: str, model: str) -> None:
    """Upload an existing bilingual file for re-alignment/repair."""
    reupload = st.file_uploader("Re-align existing XLIFF / SDLXLIFF", type=["xliff", "xlf", "sdlxliff"])
    if reupload and st.button("Re-align uploaded bilingual file", use_container_width=True, key="realign_uploaded_bilingual"):
        _realign_uploaded_xliff(reupload, source_language, target_language, model)
    if st.session_state.realigned_xliff_summary:
        st.success(st.session_state.realigned_xliff_summary)
    if st.session_state.realigned_xliff_bytes:
        st.download_button(
            _realigned_download_label(),
            data=st.session_state.realigned_xliff_bytes,
            file_name=f"{export_base}_realigned.{_realigned_download_extension()}",
            mime="application/xliff+xml",
            use_container_width=True,
            key="download_realigned_bilingual",
        )


def _memory_export_panel(
    export_base: str,
    source_text: str,
    final_translation: str,
    source_language: str,
    target_language: str,
) -> None:
    """Translation memory exports."""
    st.markdown("**Translation memory files**")
    st.caption("TMX is for reuse outside this project. Updating an uploaded TMX uses high-confidence aligned rows.")
    col1, col2 = st.columns(2)
    with col1:
        _download_tmx(
            "TMX memory",
            f"{export_base}_memory.tmx",
            source_text,
            final_translation,
            source_language,
            target_language,
            key="memory_tmx",
        )
    with col2:
        _download_updated_uploaded_tm(
            "Updated uploaded TMX",
            f"{export_base}_updated_memory.tmx",
            source_language,
            target_language,
            key="memory_updated_tmx",
        )


def _report_export_panel(include_report: bool, export_base: str) -> None:
    """Optional project report exports."""
    if not include_report:
        st.info("Enable Export analysis report in the sidebar to download reports.")
        return
    report_body = _combined_report()
    col1, col2 = st.columns(2)
    with col1:
        _download_docx(
            "Analysis report DOCX",
            f"{export_base}_analysis_report.docx",
            "Analysis Report",
            report_body,
            key="report_docx",
        )
    with col2:
        _download_pdf(
            "Analysis report PDF",
            f"{export_base}_analysis_report.pdf",
            "Analysis Report",
            report_body,
            key="report_pdf",
        )


def _export_preflight_area(source_text: str, final_translation: str) -> None:
    """Show simple export warnings before users click individual download buttons."""
    warnings = export_preflight_warnings(
        source_text,
        final_translation,
        st.session_state.source_file_type,
        st.session_state.source_file_bytes,
        st.session_state.sdlxliff_template_bytes,
    )
    if not warnings:
        return
    with st.expander("Export preflight notes", expanded=False):
        for warning in warnings:
            st.warning(warning)


def _combined_report() -> str:
    """Combine analysis, prompt, proofreading, and QA into one optional report."""
    return (
        f"Analysis\n\n{st.session_state.analysis_report}\n\n"
        f"Translation prompt\n\n{st.session_state.translation_prompt}\n\n"
        f"Translation Memory matches\n\n{st.session_state.tm_context}\n\n"
        f"Client reference guidance\n\n{st.session_state.reference_context}\n\n"
        f"Proofread translation\n\n{st.session_state.proofread_text}\n\n"
        f"QA report\n\n{st.session_state.qa_report}"
    ).strip()


def _export_base_name() -> str:
    """Use the uploaded source filename as the export base when available."""
    file_name = st.session_state.source_file_name.strip()
    if not file_name:
        return "translation"
    return Path(file_name).stem or "translation"


def _prepare_aligned_xliff(
    source_text: str,
    target_text: str,
    source_language: str,
    target_language: str,
    model: str,
) -> None:
    """Use GPT-5.5 to align source and target before XLIFF export."""
    progress = StepProgress("Aligned XLIFF preparation")
    try:
        progress.update(20, "Segmenting source and aligning target")
        fixed_segments = _fixed_bilingual_source_segments(source_text)
        if fixed_segments:
            rows = align_fixed_source_segments(
                fixed_segments,
                target_text,
                source_language,
                target_language,
                model=model.strip() or DEFAULT_MODEL,
            )
        else:
            rows = align_for_xliff(
                source_text,
                target_text,
                source_language,
                target_language,
                model=model.strip() or DEFAULT_MODEL,
            )
        _add_cost_entry(
            "Aligned XLIFF",
            source_text + "\n\n" + target_text,
            str(rows),
        )
        progress.update(75, "Building aligned XLIFF")
        st.session_state.aligned_xliff_bytes = create_xliff_from_aligned_rows(
            rows,
            source_language,
            target_language,
            aligned_cleanly=True,
        )
        st.session_state.aligned_rows = rows
        st.session_state.aligned_xliff_summary = _alignment_summary("Aligned XLIFF", rows)
        progress.done("Aligned XLIFF ready")
        st.success(st.session_state.aligned_xliff_summary)
    except Exception as exc:
        st.session_state.aligned_xliff_bytes = b""
        st.session_state.aligned_xliff_summary = ""
        st.error(f"Aligned XLIFF preparation failed: {exc}")


def _realign_uploaded_xliff(uploaded_xliff, source_language: str, target_language: str, model: str) -> None:
    """Re-align an uploaded bilingual XLIFF/SDLXLIFF and make it the active alignment."""
    progress = StepProgress("Bilingual file re-alignment")
    try:
        progress.update(20, "Reading uploaded bilingual file")
        uploaded_bytes = uploaded_xliff.getvalue()
        uploaded_type = uploaded_xliff.name.split(".")[-1].lower()
        source_text, target_text = extract_text_from_xliff(uploaded_bytes)
        progress.update(45, "Re-aligning source and target")
        rows = align_for_xliff(
            source_text,
            target_text,
            source_language,
            target_language,
            model=model.strip() or DEFAULT_MODEL,
        )
        progress.update(80, "Building re-aligned XLIFF")
        st.session_state.realigned_xliff_bytes = create_xliff_from_aligned_rows(
            rows,
            source_language,
            target_language,
            aligned_cleanly=True,
        )
        st.session_state.realigned_rows = rows
        st.session_state.realigned_template_name = uploaded_xliff.name
        st.session_state.realigned_template_type = uploaded_type
        st.session_state.realigned_template_bytes = uploaded_bytes
        st.session_state.aligned_rows = rows
        st.session_state.aligned_xliff_bytes = st.session_state.realigned_xliff_bytes
        st.session_state.realigned_xliff_summary = _alignment_summary("Re-aligned XLIFF", rows)
        st.session_state.aligned_xliff_summary = st.session_state.realigned_xliff_summary
        _sync_bilingual_review_rows_from_alignment(rows)
        _add_cost_entry("Bilingual file re-alignment", source_text + "\n\n" + target_text, str(rows))
        progress.done("Re-aligned bilingual file ready")
    except Exception as exc:
        st.session_state.realigned_xliff_bytes = b""
        st.session_state.realigned_xliff_summary = ""
        st.error(f"Bilingual file re-alignment failed: {exc}")


def _alignment_summary(label: str, rows: list[dict[str, str]]) -> str:
    """Summarize alignment confidence for the user."""
    total = len(rows)
    approved = sum(1 for row in rows if int(row.get("confidence", 0)) >= 90 and row.get("target"))
    review = total - approved
    return f"{label} ready: {approved}/{total} high-confidence segment(s), {review} need review."


def _bilingual_workflow_status() -> None:
    """Show a short SDLXLIFF/XLIFF-first status for the bilingual workflow."""
    file_type = (st.session_state.realigned_template_type or st.session_state.source_file_type or "").upper()
    if file_type in {"SDLXLIFF", "XLIFF", "XLF"}:
        tag_note = " Inline tags/placeholders are protected for SDLXLIFF exports." if file_type == "SDLXLIFF" else ""
        st.info(
            f"Current bilingual workflow: {file_type}. The latest export preserves the original bilingual package "
            f"and updates target segments for Trados.{tag_note}"
        )
    else:
        st.info(
            "For best Trados DOCX export, start from a real SDLXLIFF. Generic XLIFF remains available for exchange."
        )
    if _review_table_aligned_rows():
        st.success("Bilingual exports will use the current manual review table rows.")


def _fixed_bilingual_source_segments(source_text: str) -> list[str]:
    """Use original uploaded bilingual segments as fixed alignment source when possible."""
    if st.session_state.source_file_type not in BILINGUAL_EXTENSIONS:
        return []
    return [line.strip() for line in source_text.splitlines() if line.strip()]


def _quick_alignment_check(source_language: str, target_language: str, model: str) -> None:
    """Run a focused alignment check on low-confidence rows only."""
    rows = st.session_state.aligned_rows or st.session_state.realigned_rows
    if not rows:
        st.info("Prepare alignment or re-align the bilingual review table first.")
        return

    weak_count = sum(1 for row in rows if int(row.get("confidence", 0) or 0) < 90 or not row.get("target"))
    if weak_count == 0:
        st.success("No low-confidence alignment rows need quick checking.")
        return

    progress = StepProgress("Quick alignment check")
    try:
        progress.update(25, f"Reviewing {weak_count} low-confidence row(s)")
        improved_rows = quick_alignment_check(
            rows,
            source_language,
            target_language,
            model=model.strip() or DEFAULT_MODEL,
        )
        progress.update(70, "Refreshing aligned files and review table")
        st.session_state.aligned_rows = improved_rows
        st.session_state.realigned_rows = []
        st.session_state.aligned_xliff_bytes = create_xliff_from_aligned_rows(
            improved_rows,
            source_language,
            target_language,
            aligned_cleanly=True,
        )
        st.session_state.aligned_xliff_summary = _alignment_summary("Quick alignment check", improved_rows)
        _sync_bilingual_review_rows_from_alignment(improved_rows)
        _add_cost_entry("Quick alignment check", str(rows), str(improved_rows))
        progress.done("Quick alignment check complete")
        st.success(st.session_state.aligned_xliff_summary)
        st.rerun()
    except Exception as exc:
        st.error(f"Quick alignment check failed: {exc}")


def _sync_bilingual_review_rows_from_alignment(rows: list[dict[str, str]]) -> None:
    """Refresh the visible bilingual review table from aligned rows."""
    st.session_state.bilingual_review_rows = [
        {
            "Open": False,
            "Segment": index,
            "Source": row.get("source", ""),
            "Target": row.get("target", ""),
            "Review note": row.get("note", ""),
        }
        for index, row in enumerate(rows, start=1)
    ]
    _ensure_bilingual_review_open_flags()
    st.session_state.bilingual_review_editor_version += 1


def _reflow_for_target_docx(target_text: str, target_language: str, model: str) -> None:
    """Reflow final target text to the uploaded DOCX paragraph count."""
    progress = StepProgress("Target DOCX reflow")
    try:
        if st.session_state.source_file_type != "docx":
            raise ValueError("Upload a DOCX source file first.")
        progress.update(20, "Counting source paragraphs")
        paragraph_count = source_docx_paragraph_count(st.session_state.source_file_bytes)
        progress.update(45, "Reflowing target text")
        reflowed_text = reflow_to_paragraph_count(
            target_text,
            paragraph_count,
            target_language,
            model=model.strip() or DEFAULT_MODEL,
        )
        actual_count = len([line for line in reflowed_text.splitlines() if line.strip()])
        if actual_count != paragraph_count:
            raise ValueError(
                f"Reflow returned {actual_count} paragraphs, but source has {paragraph_count}. "
                "Try again or edit manually."
            )
        st.session_state.proofread_text = reflowed_text
        st.session_state.reflow_summary = f"Target text reflowed to {paragraph_count} DOCX paragraph(s)."
        _add_cost_entry("Target DOCX reflow", target_text, reflowed_text)
        progress.done("Reflow ready")
    except Exception as exc:
        st.error(f"Target DOCX reflow failed: {exc}")


def _final_translation_text() -> str:
    """Use the proofread translation as final output when it exists."""
    if st.session_state.proofread_text.strip():
        return st.session_state.proofread_text
    return st.session_state.translated_text


def _download_docx(label: str, file_name: str, title: str, body: str, key: str | None = None) -> None:
    """Create a DOCX download button, or show a helpful error."""
    try:
        data = create_docx(title, body)
        _download_bytes_button(
            label,
            data,
            file_name,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=key,
        )
    except Exception as exc:
        st.info(f"{label} will be available when text exists. {exc}")


def _download_bilingual_docx(label: str, file_name: str, key: str | None = None) -> None:
    """Create a bilingual DOCX from prepared aligned rows."""
    rows = _bilingual_export_rows()
    if not rows:
        st.info("Prepare alignment or build the manual bilingual review table first.")
        return

    try:
        data = create_bilingual_docx_from_rows(rows)
        st.download_button(
            label,
            data=data,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key=key,
        )
    except Exception as exc:
        st.info(f"{label} will be available when source and target text exist. {exc}")


def _download_formatted_docx(label: str, file_name: str, target_text: str, key: str | None = None) -> None:
    """Create a DOCX using the uploaded DOCX as a formatting template."""
    if st.session_state.source_file_type != "docx":
        st.info("Formatted DOCX export is available after uploading a DOCX source file.")
        return

    try:
        data = create_formatted_docx_from_template(
            st.session_state.source_file_bytes,
            target_text,
        )
        st.download_button(
            label,
            data=data,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key=key,
        )
        st.caption("DOCX export uses the original DOCX paragraph/layout structure, independent of XLIFF alignment.")
    except Exception as exc:
        st.info(f"{label} is not available yet. {exc}")


def _download_same_format_bilingual_file(
    file_name: str,
    target_text: str,
    label: str = "Same format as input",
    key: str | None = None,
) -> None:
    """Create a target SDLXLIFF/XLIFF/XLF from the uploaded bilingual file."""
    if st.session_state.source_file_type not in BILINGUAL_EXTENSIONS:
        st.info("Same-format export is available after uploading SDLXLIFF, XLIFF, or XLF.")
        return
    if not st.session_state.source_file_bytes:
        st.info(
            "Same-format export needs the original uploaded SDLXLIFF/XLIFF file. "
            "Please re-upload the source bilingual file, then click Use uploaded file again."
        )
        return

    try:
        rows = _bilingual_export_rows()
        required_count = bilingual_source_segment_count(st.session_state.source_file_bytes)
        target_segments = target_segments_from_rows(rows) if rows else target_segments_from_text(target_text)
        if len(target_segments) != required_count:
            target_segments = fit_target_segments_to_count(target_text, required_count)
        data = create_translated_bilingual_file(st.session_state.source_file_bytes, target_segments)
        st.download_button(
            label,
            data=data,
            file_name=file_name,
            mime="application/xliff+xml",
            use_container_width=True,
            key=key,
        )
        if rows and len(target_segments) == len(target_segments_from_rows(rows)):
            st.caption("Export uses the current bilingual rows and the original uploaded bilingual file as the template.")
        else:
            st.caption(
                "Export uses the original uploaded bilingual file as the template and fits the final target text into it."
            )
    except Exception as exc:
        st.info(f"Same-format bilingual export is not available yet. {exc}")


def _download_same_format_final_file(
    file_name: str,
    target_text: str,
    label: str = "Same format as input",
    key: str | None = None,
) -> None:
    """Create a final download with the same extension as the input file."""
    if not st.session_state.source_file_type:
        st.info("Upload a source file first to enable same-format export.")
        return
    if st.session_state.source_file_type in BILINGUAL_EXTENSIONS:
        _download_same_format_bilingual_file(file_name, target_text, label=label, key=key)
        return
    if not st.session_state.source_file_bytes and st.session_state.source_file_type in {"docx", "xlsx", "xlsm", "idml"}:
        st.info("Same-format export needs the original uploaded source file. Re-upload it and click Use uploaded file.")
        return

    try:
        data, mime_type, note = create_same_format_file(
            st.session_state.source_file_type,
            st.session_state.source_file_bytes,
            target_text,
        )
        st.download_button(
            label,
            data=data,
            file_name=file_name,
            mime=mime_type,
            use_container_width=True,
            key=key,
        )
        if note:
            st.caption(note)
    except Exception as exc:
        st.info(f"Same-format export is not available yet. {exc}")


def _download_pdf(label: str, file_name: str, title: str, body: str, key: str | None = None) -> None:
    """Create a PDF download button, or show a helpful error."""
    try:
        data = create_pdf(title, body)
        _download_bytes_button(label, data, file_name, "application/pdf", key=key)
    except Exception as exc:
        st.info(f"{label} will be available when text exists. {exc}")


def _download_bytes_button(label: str, data: bytes, file_name: str, mime: str, key: str | None = None) -> None:
    """Keep simple download buttons consistent across export helpers."""
    st.download_button(label, data=data, file_name=file_name, mime=mime, use_container_width=True, key=key)


def _download_xliff(
    label: str,
    file_name: str,
    source_text: str,
    target_text: str,
    source_language: str,
    target_language: str,
    key: str | None = None,
) -> None:
    """Create an XLIFF download button, or show a helpful error."""
    try:
        review_rows = _review_table_aligned_rows()
        if review_rows:
            data = create_xliff_from_aligned_rows(
                review_rows,
                source_language,
                target_language,
                aligned_cleanly=True,
            )
        elif st.session_state.aligned_xliff_bytes:
            data = st.session_state.aligned_xliff_bytes
        else:
            data = create_xliff(source_text, target_text, source_language, target_language)
            st.info("For best alignment, click Prepare aligned bilingual XLIFF before downloading.")
        st.download_button(label, data=data, file_name=file_name, mime="application/xliff+xml", use_container_width=True, key=key)
    except Exception as exc:
        st.info(f"{label} will be available when source and target text exist. {exc}")


def _download_latest_aligned_bilingual_version(
    export_base: str,
    target_text: str,
    source_text: str,
    source_language: str,
    target_language: str,
    key_prefix: str = "latest_bilingual",
) -> None:
    """Download the best available bilingual file, even before alignment."""
    rows = st.session_state.aligned_rows or st.session_state.realigned_rows

    try:
        template_bytes, extension, label = _latest_aligned_template()
        if template_bytes:
            required_count = bilingual_source_segment_count(template_bytes)
            target_segments = target_segments_from_rows(rows) if rows else []
            if len(target_segments) != required_count:
                target_segments = fit_target_segments_to_count(target_text, required_count)
            data = create_translated_bilingual_file(template_bytes, target_segments)
            st.download_button(
                label,
                data=data,
                file_name=f"{export_base}_latest.{extension}",
                mime="application/xliff+xml",
                use_container_width=True,
                key=f"{key_prefix}_latest_{extension}",
            )
            if rows:
                st.caption("Uses the latest prepared/re-aligned/quick-checked rows in the available bilingual template.")
            else:
                st.caption("No alignment has been prepared yet. This export fits the final translation into the template segment count.")
            return

        if rows:
            data = create_xliff_from_aligned_rows(
                rows,
                source_language,
                target_language,
                aligned_cleanly=True,
            )
        else:
            data = create_xliff(source_text, target_text, source_language, target_language)
        st.download_button(
            "Download latest XLIFF",
            data=data,
            file_name=f"{export_base}_latest.xliff",
            mime="application/xliff+xml",
            use_container_width=True,
            key=f"{key_prefix}_latest_xliff",
        )
    except Exception as exc:
        st.info(f"Latest bilingual export is not available yet. {exc}")


def _latest_aligned_template() -> tuple[bytes, str, str]:
    """Choose the best available bilingual template for latest aligned export."""
    realigned_type = st.session_state.realigned_template_type
    if realigned_type in BILINGUAL_EXTENSIONS and st.session_state.realigned_template_bytes:
        return (
            st.session_state.realigned_template_bytes,
            realigned_type,
            f"Download latest {realigned_type.upper()}",
        )
    file_type = st.session_state.source_file_type
    if file_type in BILINGUAL_EXTENSIONS and st.session_state.source_file_bytes:
        return (
            st.session_state.source_file_bytes,
            file_type,
            f"Download latest {file_type.upper()}",
        )
    if st.session_state.sdlxliff_template_bytes:
        return (
            st.session_state.sdlxliff_template_bytes,
            "sdlxliff",
            "Download latest SDLXLIFF",
        )
    return b"", "xliff", "Download latest XLIFF"


def _realigned_download_extension() -> str:
    """Use the extension from the uploaded repair/re-align file."""
    extension = st.session_state.realigned_template_type
    return extension if extension in BILINGUAL_EXTENSIONS else "xliff"


def _realigned_download_label() -> str:
    """Label the repair/re-align download according to the uploaded file type."""
    return f"Download re-aligned {_realigned_download_extension().upper()}"


def _download_sdlxliff(
    label: str,
    file_name: str,
    source_text: str,
    target_text: str,
    source_language: str,
    target_language: str,
    key: str | None = None,
) -> None:
    """Create an SDLXLIFF download button."""
    if st.session_state.source_file_type != "sdlxliff":
        template_bytes = st.session_state.sdlxliff_template_bytes
        if not template_bytes:
            st.info(
                "A real SDLXLIFF export for non-SDLXLIFF inputs needs a Trados-created SDLXLIFF template. "
                "Upload one below, or use Bilingual XLIFF."
            )
            return
    else:
        template_bytes = st.session_state.source_file_bytes

    if not template_bytes:
        st.info("SDLXLIFF export needs the original uploaded SDLXLIFF or an SDLXLIFF template.")
        return

    try:
        rows = _bilingual_export_rows()
        required_count = bilingual_source_segment_count(template_bytes)
        target_segments = target_segments_from_rows(rows) if rows else target_segments_from_text(target_text)
        if len(target_segments) != required_count:
            target_segments = fit_target_segments_to_count(target_text, required_count)
        data = create_translated_bilingual_file(template_bytes, target_segments)
        st.download_button(label, data=data, file_name=file_name, mime="application/xliff+xml", use_container_width=True, key=key)
        st.caption("Uses a real Trados-created SDLXLIFF as the template.")
    except Exception as exc:
        st.info(f"{label} will be available when source and target text exist. {exc}")


def _download_tmx(
    label: str,
    file_name: str,
    source_text: str,
    target_text: str,
    source_language: str,
    target_language: str,
    key: str | None = None,
) -> None:
    """Create a TMX download button for reusing this translation later."""
    try:
        data = create_tmx(source_text, target_text, source_language, target_language)
        st.download_button(label, data=data, file_name=file_name, mime="application/x-tmx+xml", use_container_width=True, key=key)
    except Exception as exc:
        st.info(f"{label} will be available when source and target text exist. {exc}")


def _download_updated_uploaded_tm(
    label: str,
    file_name: str,
    source_language: str,
    target_language: str,
    key: str | None = None,
) -> None:
    """Download uploaded TM plus high-confidence aligned translation rows."""
    rows = _bilingual_export_rows()
    if not st.session_state.tm_entries:
        st.info("Load a Translation Memory first to create an updated TMX.")
        return
    if not rows:
        st.info("Prepare alignment or build the manual bilingual review table first.")
        return

    try:
        data = updated_tmx_from_aligned_rows(
            st.session_state.tm_entries,
            rows,
            source_language,
            target_language,
            minimum_confidence=90,
        )
        st.download_button(label, data=data, file_name=file_name, mime="application/x-tmx+xml", use_container_width=True, key=key)
    except Exception as exc:
        st.info(f"{label} is not available yet. {exc}")


def _bilingual_export_rows() -> list[dict[str, str]]:
    """Prefer the current manual review table for bilingual exports."""
    review_rows = _review_table_aligned_rows()
    if review_rows:
        return review_rows
    return st.session_state.aligned_rows or st.session_state.realigned_rows


def _review_table_aligned_rows() -> list[dict[str, str]]:
    """Convert the current manual review table into aligned export rows."""
    export_rows = []
    for index, row in enumerate(st.session_state.bilingual_review_rows or [], start=1):
        source = str(row.get("Source") or "").strip()
        target = str(row.get("Target") or "").strip()
        if not source and not target:
            continue
        segment_id = str(row.get("Segment") or index)
        note = str(row.get("Review note") or "").strip()
        confidence = 100 if source and target else 0
        if not source:
            note = (note + " " if note else "") + "Missing source segment in manual review table."
        if not target:
            note = (note + " " if note else "") + "Missing target segment in manual review table."
        export_rows.append(
            {
                "id": segment_id,
                "source": source,
                "target": target,
                "confidence": confidence,
                "note": note or "Manual bilingual review row.",
            }
        )
    return export_rows


if __name__ == "__main__":
    main()
