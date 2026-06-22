"""Central default values for TranslatAI.

Keeping these values in one place reduces the chance that project loading,
resetting, and session startup drift apart over time.
"""

from __future__ import annotations


DEFAULT_SOURCE_LANGUAGE = "English"
DEFAULT_TARGET_LANGUAGE = "Slovenian"
DEFAULT_TEXT_TYPE = "General"
PROJECT_SCHEMA_VERSION = 1


APP_STATE_DEFAULTS = {
    "project_id": "",
    "project_name": "",
    "source_language": DEFAULT_SOURCE_LANGUAGE,
    "target_language": DEFAULT_TARGET_LANGUAGE,
    "text_type": DEFAULT_TEXT_TYPE,
    "source_text": "",
    "analysis_report": "",
    "generated_prompt": "",
    "translation_prompt": "",
    "translated_text": "",
    "proofread_text": "",
    "proofreading_baseline_text": "",
    "qa_report": "",
    "rule_based_qa_warnings": [],
    "uploaded_file_metadata": {},
    "last_uploaded_source_signature": "",
    "source_files": [],
    "source_file_name": "",
    "source_file_type": "",
    "source_file_bytes": b"",
    "sdlxliff_template_name": "",
    "sdlxliff_template_bytes": b"",
    "tm_entries": [],
    "tm_context": "",
    "tm_file_name": "",
    "prompt_archive_title": "",
    "prompt_archive_selected_id": "",
    "aligned_xliff_bytes": b"",
    "aligned_xliff_summary": "",
    "aligned_rows": [],
    "realigned_xliff_bytes": b"",
    "realigned_xliff_summary": "",
    "realigned_rows": [],
    "realigned_template_name": "",
    "realigned_template_type": "",
    "realigned_template_bytes": b"",
    "show_price_list": False,
    "show_project_repository": False,
    "reference_context": "",
    "reference_file_names": [],
    "cost_entries": [],
    "bilingual_review_rows": [],
    "bilingual_review_editor_version": 0,
    "bilingual_review_status": "",
    "review_row_index": 1,
    "reflow_summary": "",
    "grid_base_rate": 0.10,
    "net_word_grid_rows": [],
    "net_word_grid_summary": {},
}


PROJECT_STATE_KEYS = [
    "project_id",
    "project_name",
    "source_language",
    "target_language",
    "text_type",
    "source_text",
    "source_files",
    "source_file_name",
    "source_file_type",
    "uploaded_file_metadata",
    "sdlxliff_template_name",
    "analysis_report",
    "generated_prompt",
    "translation_prompt",
    "translated_text",
    "proofread_text",
    "proofreading_baseline_text",
    "qa_report",
    "rule_based_qa_warnings",
    "tm_context",
    "tm_file_name",
    "reference_context",
    "reference_file_names",
    "cost_entries",
    "bilingual_review_rows",
    "aligned_rows",
    "aligned_xliff_summary",
    "realigned_rows",
    "realigned_xliff_summary",
    "realigned_template_name",
    "realigned_template_type",
    "reflow_summary",
    "grid_base_rate",
    "net_word_grid_rows",
    "net_word_grid_summary",
]


PROJECT_STATE_DEFAULTS = {
    key: APP_STATE_DEFAULTS[key]
    for key in PROJECT_STATE_KEYS
    if key in APP_STATE_DEFAULTS
}
