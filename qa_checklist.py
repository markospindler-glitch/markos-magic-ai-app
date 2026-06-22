"""Editable QA checklist export/import and approved correction application."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

from openai_client import DEFAULT_MODEL, ask_openai


CHECKLIST_HEADERS = [
    "ID",
    "Approved",
    "Severity",
    "Category",
    "Issue",
    "Source excerpt",
    "Target excerpt",
    "PM correction / instruction",
]

APPROVED_VALUES = {"yes", "y", "true", "1", "approved", "approve", "x", "da"}
HEADER_ROW = 8


def build_qa_checklist_rows(rule_based_warnings: list[dict], qa_report: str) -> list[dict[str, str]]:
    """Convert rule-based and GPT QA output into editable checklist rows."""
    rows: list[dict[str, str]] = []
    for index, warning in enumerate(rule_based_warnings or [], start=1):
        rows.append(
            {
                "ID": f"R{index}",
                "Approved": "",
                "Severity": str(warning.get("severity") or ""),
                "Category": str(warning.get("category") or "Rule-based QA"),
                "Issue": str(warning.get("message") or ""),
                "Source excerpt": str(warning.get("source excerpt") or ""),
                "Target excerpt": str(warning.get("target excerpt") or ""),
                "PM correction / instruction": "",
            }
        )

    for index, line in enumerate(_qa_report_lines(qa_report), start=1):
        rows.append(
            {
                "ID": f"G{index}",
                "Approved": "",
                "Severity": "suggestion",
                "Category": "GPT QA note",
                "Issue": line,
                "Source excerpt": "",
                "Target excerpt": "",
                "PM correction / instruction": "",
            }
        )
    return rows


def create_qa_checklist_xlsx(rule_based_warnings: list[dict], qa_report: str) -> bytes:
    """Create an editable Excel checklist for PM approval/rejection."""
    rows = build_qa_checklist_rows(rule_based_warnings, qa_report)
    if not rows:
        raise ValueError("Run QA first before exporting a QA checklist.")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "QA checklist"
    header_fill = PatternFill("solid", fgColor="E91545")
    header_font = Font(color="FFFFFF", bold=True)
    title_fill = PatternFill("solid", fgColor="111827")
    instruction_fill = PatternFill("solid", fgColor="FFF1F4")
    approved_fill = PatternFill("solid", fgColor="FFF2CC")
    thin_border = Border(
        left=Side(style="thin", color="E5E7EB"),
        right=Side(style="thin", color="E5E7EB"),
        top=Side(style="thin", color="E5E7EB"),
        bottom=Side(style="thin", color="E5E7EB"),
    )

    sheet.merge_cells("A1:H1")
    sheet["A1"] = "TranslatAI QA Correction Checklist"
    sheet["A1"].fill = title_fill
    sheet["A1"].font = Font(color="FFFFFF", bold=True, size=16)
    sheet["A1"].alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 28

    instructions = [
        "How to use this checklist:",
        "1. Review each QA item below.",
        "2. In the yellow Approved column, choose Yes only for corrections that should be applied.",
        "3. Use No for rejected items, or leave blank when undecided.",
        "4. Add clear instructions in PM correction / instruction when the automatic issue text is not enough.",
        "5. Save the XLSX and reupload it in TranslatAI, then click Apply approved QA corrections.",
    ]
    for offset, text in enumerate(instructions, start=2):
        sheet.merge_cells(start_row=offset, start_column=1, end_row=offset, end_column=8)
        cell = sheet.cell(row=offset, column=1, value=text)
        cell.fill = instruction_fill
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        cell.font = Font(bold=offset == 2, color="111827")

    for column_index, header in enumerate(CHECKLIST_HEADERS, start=1):
        sheet.cell(row=HEADER_ROW, column=column_index, value=header)
    for cell in sheet[HEADER_ROW]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        cell.border = thin_border

    for row_index, row in enumerate(rows, start=HEADER_ROW + 1):
        for column_index, header in enumerate(CHECKLIST_HEADERS, start=1):
            cell = sheet.cell(row=row_index, column=column_index, value=row.get(header, ""))
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = thin_border
            if header == "Approved":
                cell.fill = approved_fill
            if header == "Severity":
                _style_severity_cell(cell)

    widths = [10, 14, 14, 24, 56, 42, 42, 56]
    for column_index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(column_index)].width = width
    for row_index in range(HEADER_ROW + 1, HEADER_ROW + len(rows) + 1):
        sheet.row_dimensions[row_index].height = 58

    validation = DataValidation(type="list", formula1='"Yes,No,Needs discussion"', allow_blank=True)
    validation.error = "Choose Yes, No, or Needs discussion."
    validation.errorTitle = "Invalid approval value"
    validation.prompt = "Choose Yes only when this correction should be applied by the app."
    validation.promptTitle = "Approval"
    sheet.add_data_validation(validation)
    validation.add(f"B{HEADER_ROW + 1}:B{HEADER_ROW + len(rows)}")

    sheet.freeze_panes = f"A{HEADER_ROW + 1}"
    sheet.auto_filter.ref = f"A{HEADER_ROW}:H{HEADER_ROW + len(rows)}"
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def read_qa_checklist_xlsx(file_bytes: bytes) -> list[dict[str, str]]:
    """Read an edited QA checklist from Excel."""
    if not file_bytes:
        raise ValueError("Upload a completed QA checklist first.")

    workbook = load_workbook(BytesIO(file_bytes), data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("The QA checklist is empty.")

    header_row_index = _find_header_row(rows)
    headers = [str(value or "").strip() for value in rows[header_row_index]]
    missing = [header for header in CHECKLIST_HEADERS if header not in headers]
    if missing:
        raise ValueError(
            "This does not look like a QA checklist exported by the app. "
            f"Missing column(s): {', '.join(missing)}."
        )

    header_index = {header: headers.index(header) for header in CHECKLIST_HEADERS}
    checklist_rows = []
    for raw_row in rows[header_row_index + 1:]:
        row = {
            header: _cell_value(raw_row[header_index[header]] if header_index[header] < len(raw_row) else "")
            for header in CHECKLIST_HEADERS
        }
        if any(value.strip() for value in row.values()):
            checklist_rows.append(row)
    return checklist_rows


def _find_header_row(rows: list[tuple]) -> int:
    """Find the checklist header row even when the sheet has instructions above it."""
    for index, row in enumerate(rows):
        headers = {str(value or "").strip() for value in row}
        if {"ID", "Approved", "Issue", "PM correction / instruction"}.issubset(headers):
            return index
    raise ValueError("This does not look like a QA checklist exported by the app.")


def approved_checklist_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return rows the PM approved for AI correction."""
    approved = []
    for row in rows or []:
        value = str(row.get("Approved") or "").strip().casefold()
        if value in APPROVED_VALUES:
            approved.append({key: str(row.get(key) or "") for key in CHECKLIST_HEADERS})
    return approved


def apply_approved_qa_corrections(
    source_text: str,
    target_text: str,
    approved_rows: list[dict[str, str]],
    target_language: str,
    domain: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """Ask AI to apply only approved QA checklist items to the final translation."""
    if not target_text.strip():
        raise ValueError("There is no final translation to correct.")
    if not approved_rows:
        raise ValueError("No approved QA checklist rows were found. Mark rows as Yes/X/Approved first.")

    checklist = _approved_rows_as_text(approved_rows)
    system_prompt = (
        f"You are a senior translation editor for {target_language}. "
        "Apply approved QA corrections precisely and conservatively."
    )
    user_prompt = f"""Apply the approved QA checklist items to the target translation.

Target language: {target_language}
Text type/domain: {domain}

Rules:
- Apply only approved checklist items.
- Use the PM correction / instruction when it is supplied.
- If that field is empty, use the Issue text as the correction instruction.
- Keep the source meaning unchanged.
- Do not introduce corrections from rejected or blank checklist rows.
- Do not rewrite good text unnecessarily.
- Preserve paragraph order, line breaks, numbers, names, dates, units, URLs, emails, placeholders, file markers, and tags.
- Return only the corrected full target translation.

Source text for reference:
{source_text}

Approved QA checklist:
{checklist}

Current target translation:
{target_text}
"""
    corrected = ask_openai(system_prompt, user_prompt, model=model)
    if not corrected.strip():
        raise RuntimeError("AI returned an empty corrected translation.")
    return corrected


def _qa_report_lines(qa_report: str) -> list[str]:
    """Use concise non-empty GPT QA report lines as checklist items."""
    lines = []
    for line in str(qa_report or "").splitlines():
        cleaned = line.strip().lstrip("-*0123456789. )\t").strip()
        if len(cleaned) >= 8:
            lines.append(cleaned)
    return lines[:80]


def _approved_rows_as_text(rows: list[dict[str, str]]) -> str:
    blocks = []
    for row in rows:
        instruction = row.get("PM correction / instruction") or row.get("Issue") or ""
        blocks.append(
            "\n".join(
                [
                    f"ID: {row.get('ID', '')}",
                    f"Severity: {row.get('Severity', '')}",
                    f"Category: {row.get('Category', '')}",
                    f"Issue: {row.get('Issue', '')}",
                    f"Source excerpt: {row.get('Source excerpt', '')}",
                    f"Target excerpt: {row.get('Target excerpt', '')}",
                    f"Approved instruction: {instruction}",
                ]
            )
        )
    return "\n\n".join(blocks)


def _cell_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _style_severity_cell(cell) -> None:
    """Make severity easy to scan for PMs."""
    severity = str(cell.value or "").casefold()
    if severity == "critical":
        cell.fill = PatternFill("solid", fgColor="FCA5A5")
        cell.font = Font(bold=True, color="7F1D1D")
    elif severity == "warning":
        cell.fill = PatternFill("solid", fgColor="FDE68A")
        cell.font = Font(bold=True, color="78350F")
    elif severity == "suggestion":
        cell.fill = PatternFill("solid", fgColor="DBEAFE")
        cell.font = Font(bold=True, color="1E3A8A")
