# Handoff for ChatGPT Programmer

Last updated: 2026-05-04

## Copy-paste prompt

Act as a world-class senior software engineer with strong experience in Python, Streamlit, document processing, localization technology, Trados Studio, SDLXLIFF/XLIFF/TMX, DOCX formatting, Excel files, and safe file export workflows.

You are taking over a local Windows Streamlit app called **Marko's Magic AI App**. The owner is a translator/project manager, not a programmer. Your job is to fix practical problems without making the app more complicated.

Primary goal right now:

Make the export section simple, reliable, and user-friendly.

The desired export behavior is:

1. The user uploads a source file.
2. The app translates/proofreads the content.
3. In the Export section, the user sees functional download button(s).
4. The main export should be the same file format as the input.
5. Where technically supported, the original formatting/design/structure should be preserved by using the uploaded source file as a template.
6. Do not show alignment buttons, advanced export tools, CAT-tool options, or confusing readiness tables in the main export section.
7. If export cannot be prepared, show a disabled button plus a clear, plain-English reason.

Do not refactor the whole app first. Inspect the code, identify the narrow failure, fix it, add or update targeted tests, and keep the existing workflow recognizable.

## Project location

Windows workspace:

```text
C:\Users\marko\OneDrive\Dokumenti\New project 2
```

Main app:

```text
app.py
```

Start command:

```powershell
python -m streamlit run app.py
```

In this environment, Python has usually been:

```text
%LOCALAPPDATA%\Programs\Python\Python313\python.exe
```

## Current technology stack

- Python
- Streamlit
- OpenAI API, intended model: `gpt-5.5`
- `python-docx`
- `reportlab`
- `PyMuPDF`
- `openpyxl`
- `xlrd`
- `pypdf`
- `Pillow`
- Local JSON project/prompt storage

Dependencies are listed in:

```text
requirements.txt
```

## What the app does

Marko's Magic AI App is a local translation workflow app. It supports:

- source file upload and source text extraction
- source analysis
- prompt generation
- translation
- proofreading
- manual bilingual review table
- QA checks
- project saving/loading
- prompt archive
- pricing/cost estimates
- translation memory/reference file support
- same-format export attempts
- SDLXLIFF/XLIFF/TMX-related helpers
- integrated handout translator under `handout_translator_v1`

The app became too broad. The owner now wants export simplified back to basics.

## Immediate user pain

The owner is unhappy with the entire Export section.

Recent requested direction:

> I want the output file to be the same as the input file, whereby the same format and design is kept. Delete all of the export section. Just give me buttons for export, without any alignment buttons, advanced options, nothing like that. Let's go back to the basics and build from there.

Then:

> I need functional export buttons in the export section, not just this message: The app will use the uploaded file as the template and preserve the structure as much as possible.

So the Export section should be extremely simple and action-first.

## Current export implementation

Relevant functions in `app.py`:

```text
_export_area
_simple_same_format_export_button
_same_format_export_payload
_simple_same_format_warning
_download_same_format_final_file
_download_same_format_bilingual_file
```

The simplified export section currently tries to:

- get final target text via `_final_translation_text()`
- get the input file extension from `st.session_state.source_file_type`
- build export bytes in `_same_format_export_payload`
- show a primary `st.download_button`
- show a preservation/limitation note underneath

This needs to be reviewed in the live app. The owner reports that they need actual functional export buttons, not just status text.

## Same-format export helpers

Relevant file:

```text
export_same_format.py
```

Main function:

```text
create_same_format_file(source_file_type, source_file_bytes, target_text)
```

Currently supported:

- `txt`: exports UTF-8 text
- `csv`: creates a simple CSV from target lines
- `pdf`: regenerates PDF, does not preserve original PDF design
- `docx`: uses `create_formatted_docx_from_template`
- `idml`: uses `create_translated_idml`
- `xlsx`: preserves workbook structure and replaces text cells
- `xlsm`: preserves workbook structure and VBA where possible
- `xls`: creates Excel-openable HTML, does not preserve original XLS design

DOCX implementation:

```text
export_docx.py
create_formatted_docx_from_template(template_bytes, translated_text)
```

This tries to preserve DOCX structure by replacing paragraph text in the original DOCX template. It may not preserve complex layouts perfectly, especially text boxes, floating shapes, headers/footers, complex tables, or unusual Word XML structures.

## SDLXLIFF/XLIFF export

Relevant files:

```text
sdlxliff_pipeline.py
export_bilingual_template.py
```

Important current behavior:

- SDLXLIFF is parsed as XML, not plain text.
- Editable `trans-unit` source segments are extracted.
- Locked / `translate="no"` segments are skipped.
- Inline tags/placeholders are protected using tokens like `[[TAG_1]]`, `[[TAG_1_OPEN]]`, `[[TAG_1_CLOSE]]`.
- During export, original XML inline tags are restored.
- Missing protected tokens are now auto-repaired conservatively where possible.
- Unknown/wrong protected tokens still block export.
- Output XML is validated before export.

This SDLXLIFF safety work should not be removed, but the UI should not force the user through alignment controls in the simplified export section.

## Important product decision

For now, the main export section should not try to teach the user all export theory.

It should show:

- one clear same-format download button when possible
- perhaps one optional fallback button only if useful, such as PDF or TXT
- short limitation note only after the button

Avoid:

- tabs
- alignment buttons
- "Prepare alignment"
- "Quick alignment check"
- "Advanced bilingual tools"
- readiness tables
- project preflight grids
- multiple confusing export paths

Those advanced features can remain in code for later, but they should not dominate the basic export UI.

## Acceptance criteria for the export fix

For a DOCX input:

- Export section shows a working button named something like `Download DOCX`.
- The output filename uses the input base name, e.g. `client_file_target.docx`.
- The output uses the uploaded DOCX as the template.
- Formatting preservation is attempted.
- If export fails because paragraph counts or template bytes are missing, the reason is clear.

For an SDLXLIFF input:

- Export section shows a working button named `Download SDLXLIFF`.
- The output remains `.sdlxliff`.
- The app preserves SDLXLIFF XML structure and tags.
- No alignment button is required in the simplified export UI.

For XLSX/XLSM input:

- Export section shows `Download XLSX` or `Download XLSM`.
- Workbook structure and styles are preserved where possible.
- Text cells are replaced in reading order.

For PDF input:

- If same-format PDF is offered, clearly state that original PDF design is not preserved.
- Do not imply exact PDF design preservation.

For unsupported or fragile cases:

- Show a disabled button or no button with a clear reason.
- Do not show only a success/info message with no download action.

## Known risks

1. `app.py` is too large and contains too much UI and workflow logic.
2. Streamlit session state is scattered.
3. DOCX formatting preservation is partial, not true full Word layout preservation.
4. PDF same-format preservation is not real; current PDF is regenerated.
5. Legacy `.xls` design preservation is not real.
6. SDLXLIFF export is safer than before but should be validated with real Trados-created files.
7. Large files can stress GPT calls, alignment, and Streamlit state.
8. Some older advanced export functions remain in `app.py` even if hidden from the simplified UI.

## Suggested first task for the programmer

Start with only the export UI.

1. Run the app.
2. Upload a small DOCX.
3. Add or simulate final translation text.
4. Confirm the Export section displays a functional `Download DOCX` button.
5. Download and inspect the file in Word.
6. Repeat with a small SDLXLIFF and XLSX if test files are available.
7. If the button is not shown, debug `_export_area`, `_simple_same_format_export_button`, and `_same_format_export_payload`.
8. Add tests for any helper changes.

Do not start by redesigning the whole app.

## Useful test commands

Run all tests:

```powershell
python -m unittest discover tests
```

Syntax check key files:

```powershell
python -m py_compile app.py export_same_format.py export_docx.py sdlxliff_pipeline.py export_bilingual_template.py import_files.py
```

Recently, the full suite passed with 61 tests.

## Key files to inspect

Start here:

```text
app.py
export_same_format.py
export_docx.py
sdlxliff_pipeline.py
export_bilingual_template.py
import_files.py
file_validation.py
state_manager.py
app_defaults.py
tests/
```

Then inspect only as needed:

```text
export_xliff.py
xliff_aligner.py
translation_memory.py
project_repository.py
active_project.py
error_utils.py
startup_checks.py
```

## Instructions for changes

- Keep changes small and safe.
- Do not remove the SDLXLIFF protected-tag pipeline.
- Do not reintroduce alignment buttons into the basic export section.
- Do not claim exact formatting preservation for formats that cannot support it.
- Prefer clear button labels over explanatory text.
- Put limitations under buttons, not instead of buttons.
- Add tests when changing helper logic.
- Keep Streamlit UI simple enough for a non-programmer.

## Plain-English target UX

The user should reach Export and think:

> I uploaded DOCX, so I click Download DOCX.

or:

> I uploaded SDLXLIFF, so I click Download SDLXLIFF.

They should not have to understand alignment, TM quality, XLIFF theory, template repair, or internal app state just to download the basic output file.

