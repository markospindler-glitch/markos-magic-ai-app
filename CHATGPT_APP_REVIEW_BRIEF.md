# Marko's Magic AI App - Technical and Product Review Brief for ChatGPT

Last updated: 2026-05-03

## Purpose of this document

This document summarizes the current state of **Marko's Magic AI App** so ChatGPT can act as a programmer, localization-technology consultant, and translation-industry software adviser.

Use this document as a briefing note. Paste it into ChatGPT and ask it to analyse the app, what has already been built, what is risky, and what the best next development steps should be.

The desired ChatGPT role is:

> Act as a senior software engineer who understands translation workflows, CAT tools, Trados Studio, SDLXLIFF/XLIFF/TMX/TM handling, localization project management, document formatting, and small-team deployment. Analyse what has been built, identify risks, and suggest practical next steps.

## Executive summary

Marko's Magic AI App is a local Windows-friendly Streamlit app for AI-assisted translation work. It combines document/text import, GPT-5.5 source analysis, prompt creation, translation, proofreading, bilingual review, QA, export, Translation Memory support, reference-file support, project saving, pricing estimates, and an integrated handout translator.

The app is already a broad working prototype. The main product question is no longer "Can this be built?" but "Which parts should be hardened, simplified, redesigned, or separated before it is used by a team?"

The most important technical areas for expert review are:

- reliable file-format preservation, especially DOCX, XLSX, XLIFF, SDLXLIFF, and TMX
- safe Trados interoperability
- large-document handling and segmentation
- cost control for GPT-5.5 workflows
- team deployment, shared storage, project repository design, and API-key handling
- whether Streamlit remains suitable or whether the app should move toward a desktop app or frontend/backend architecture

## Product goal

Marko's Magic AI App is a local Windows-friendly Streamlit app for AI-assisted translation workflows. It is intended to help a translation team:

- Import source text or documents.
- Use OpenAI GPT-5.5 for analysis, prompt creation, translation, proofreading, QA, and alignment assistance.
- Work with Translation Memories and reference files.
- Review translation in an editable bilingual table.
- Export final files and bilingual files.
- Preserve formatting where possible.
- Store past projects and prompt templates.
- Estimate cost and word counts.
- Translate/recreate scanned handouts using an integrated image-based handout translator.

The app is not intended to fully replace Trados Studio, but it aims to reduce dependence on direct Trados integration while still supporting TM and bilingual exchange formats.

## Target user

The intended user is a translator, reviewer, or small translation-team project manager who is comfortable with translation workflows but not necessarily a programmer.

The app should therefore:

- keep the workflow clear and guided
- avoid hidden technical assumptions
- provide understandable error messages
- avoid corrupting client files or CAT-tool files
- make costs, risks, and file limitations visible before export
- preserve formatting and translation assets wherever technically possible

## Current technology stack

- Python
- Streamlit
- OpenAI API, default model currently `gpt-5.5`
- `python-docx`
- `reportlab`
- `PyMuPDF`
- `openpyxl`
- `xlrd`
- `pypdf`
- `Pillow`
- Local JSON storage for projects and prompt archive

Main app file:

- `app.py`

Integrated handout app:

- `handout_translator_v1/app.py`

## Current app structure

The main app has six tabs:

1. **Source**
2. **Context**
3. **Prompt**
4. **Translation**
5. **Handout Translator**
6. **QA & Export**

The sidebar contains:

- Source language
- Target language
- Text type/domain
- OpenAI model field
- Export analysis report toggle
- Price list toggle
- Start new project
- Project repository controls

## Core design principle

The app should stay simple and reliable from the user's point of view, even if the internal workflow is complex. Editable text boxes are intentionally used for analysis, prompts, translation, proofreading, and QA so the translator remains in control.

GPT-5.5 is used for language-intelligence tasks, but final responsibility remains with the human reviewer.

## Core workflow

### 1. Source input

The user can:

- Paste source text.
- Upload source files.

Supported source upload types:

- TXT
- CSV
- Excel: XLSX, XLS, XLSM
- DOCX
- selectable-text PDF
- SDLXLIFF
- XLIFF/XLF

SDLXLIFF/XLIFF import currently extracts source segments as plain text for translation workflow use. It does not directly edit the uploaded file in place.

### 2. Context

The user can upload:

- Translation Memory:
  - TMX
  - CSV
  - SDLTM read-only import where SQLite schema can be safely inspected
- Reference files:
  - TXT
  - CSV
  - DOCX
  - PDF
  - XLS/XLSX/XLSM

The app can:

- Find fuzzy TM matches.
- Format those matches as editable prompt context.
- Analyse reference documents with GPT-5.5 and produce editable terminology/style guidance.

SDLTM is treated as read-only. The app does not write back to `.sdltm`.

### 3. Analysis and prompt generation

The app uses GPT-5.5 to analyse:

- grammar
- style
- terminology
- syntax
- spelling
- punctuation
- topic
- register
- translation risks

It then generates a custom translation prompt. The prompt is editable.

The prompt builder ensures the final prompt includes:

```text
The text for translation:
```

followed by the source text.

### 4. Translation

The app translates using GPT-5.5.

The user can edit the translation manually.

### 5. Proofreading

The app can proofread using GPT-5.5 as a native speaker proofreader for the selected target language.

Proofreading features:

- Shows visible changes like tracked changes.
- Shows surrounding text, not only changed tokens.
- User can accept/reject selected corrections.
- User can accept all corrections.
- User can reject all corrections.
- Exports and manual bilingual review use the clean proofread text.

### 6. Manual bilingual review

The app can build an editable bilingual review table with:

- Segment
- Source
- Target
- Review note
- Open checkbox

The user can:

- Open a selected row in an expanded editor above the table.
- Edit target text.
- Edit notes.
- Apply reviewed target text as final translation.
- Re-align the bilingual review table using GPT-5.5.

The manual bilingual review table is treated as the preferred source for bilingual exports when available.

### 7. QA

The app runs a GPT-5.5 QA check comparing source and target.

QA includes:

- accuracy
- omissions/additions
- terminology
- numbers/names
- style/register
- formatting risks
- target consistency
- cases where the same source text may have been translated differently

QA report is editable.

## Export features

### Final files

The app can export:

- Target DOCX
- PDF
- Same format as input

Same-format support:

- DOCX: uses original DOCX as formatting/layout template.
- XLSX/XLSM: preserves workbook sheets/styles where possible and replaces text cells in reading order.
- XLS: legacy fallback; creates Excel-openable `.xls` table but does not preserve old binary formatting.
- TXT: exports translated TXT.
- CSV: exports translated CSV.
- PDF: regenerated PDF, not original design-preserving.
- SDLXLIFF/XLIFF/XLF: uses uploaded bilingual file as template where possible.

DOCX formatting preservation:

- Uses original DOCX package.
- Replaces text nodes in `word/document.xml`.
- Preserves styles, fonts, images, tables, sections, margins, spacing, and layout as much as possible.
- Automatically fits/merges target text back into the original source paragraph count.
- DOCX export is intentionally independent of bilingual/XLIFF alignment.

### Bilingual files

The app can export:

- Bilingual DOCX
- Bilingual XLIFF
- Bilingual SDLXLIFF

Important SDLXLIFF limitation:

- The app cannot safely create a real SDLXLIFF from scratch for arbitrary input formats.
- A real SDLXLIFF needs Trados-specific file type metadata.
- For non-SDLXLIFF inputs, the app supports an optional SDLXLIFF template upload.
- The template must be a real Trados-created SDLXLIFF.
- The app injects translated target segments into that SDLXLIFF template.

### Memory

The app can export:

- TMX memory
- Updated uploaded TMX

Updated TMX merges original TM entries with high-confidence aligned rows.

### Reports

The app can export:

- Analysis report DOCX
- Analysis report PDF

## XLIFF and SDLXLIFF logic

The app has XLIFF helpers for:

- creating bilingual XLIFF 1.2
- creating XLIFF from aligned rows
- marking confidence
- segmenting by sentence
- extracting/re-aligning uploaded XLIFF

Same-format SDLXLIFF/XLIFF export:

- Uses uploaded bilingual XML as a template.
- Counts source segments.
- Fits target segments to the source segment count.
- Updates target text in place.
- Marks target state as translated.

Known risk:

- SDLXLIFF is difficult because Trados expects its own metadata and file type definitions.
- Fake SDLXLIFF files made by renaming XLIFF are not valid for Trados.
- The current safe approach requires a real Trados-created SDLXLIFF template.

## Project repository

The app can save/load/update/delete projects locally.

Saved project state includes:

- source text
- uploaded source file metadata
- uploaded source file bytes encoded as base64
- analysis
- prompt
- translation
- proofread text
- QA report
- TM context
- reference context
- bilingual review rows
- alignment rows
- cost entries
- net word grid data
- SDLXLIFF template bytes encoded as base64

There is a **Start new project** button that clears the workspace without refreshing the browser manually.

## Prompt archive

The app can save generated prompts into a local prompt archive.

The prompt archive was simplified so JSON segment details are not shown in the UI.

## Cost and pricing features

The app includes:

- Estimated GPT-5.5 API price list.
- Estimated current job cost after GPT steps.
- Translation net word count grid based on a user-provided Excel grid.

The net word grid:

- calculates raw words
- payable weight %
- base rate per word
- category/effective rate per word
- net words
- final cost

## Handout Translator integration

An older app named `handout_translator_v1` was integrated into the main app as a new tab.

Purpose:

- Upload image/photo/scan of an English handout page.
- Use GPT-5.5 vision to extract English text, translate into Slovenian, and recreate structure/layout.
- Preview recreated A4 handout.
- Export HTML, PDF, and DOCX.

Additional integration features:

- The handout app can create a source-language DOCX from extracted English text.
- A button sends that source DOCX into the main app under **1 Source**.
- The main app then treats it as a DOCX input for the translation workflow.

Handout re-editing:

- After output is generated, there is a **Re-edit output with GPT-5.5** option.
- User can instruct GPT-5.5 to make layout more compact, avoid cutoff, improve A4 fit, etc.
- GPT-5.5 revises the structured JSON, then preview/downloads refresh.

## Readiness check

The QA & Export tab includes a non-blocking **Project readiness check**.

It checks:

- source text
- final translation
- proofreading status
- manual bilingual review status
- QA status
- DOCX template readiness
- SDLXLIFF/XLIFF template readiness
- bilingual alignment confidence
- TM/reference context
- export source/path

Statuses:

- Ready
- Needs attention
- Optional

Important:

- The readiness check is advisory only.
- Export buttons remain available even if status is not Ready.

## Known limitations and concerns

### Streamlit limitations

- Streamlit is fast for local prototypes, but less ideal for polished multi-user production UI.
- Complex state can be fragile.
- Row-click behavior in editable tables is limited; the app uses an Open checkbox workaround.
- Direct same-path local overwrite is not generally available in browser-based Streamlit.
- Browser-style upload/download workflows are not ideal for local-first professional file management.

### File format limitations

- DOCX layout preservation is improved but still not perfect.
- PDF import extracts selectable text only; no OCR.
- PDF output is regenerated and does not preserve original PDF design.
- XLSX/XLSM export preserves workbook structure where possible but may not perfectly preserve formulas/merged cells/complex workbook semantics.
- XLS legacy binary formatting is not preserved.
- SDLXLIFF cannot be safely created from scratch without Trados-generated metadata.
- SDLTM is read-only import only, not update/write.

### AI limitations

- GPT alignment can make mistakes.
- GPT translation/proofreading/QA should be reviewed by a human.
- Large files may be expensive and may require chunking.
- Current workflow may struggle with very large documents unless split into segments/chunks.
- Cost estimates are approximate unless token accounting is connected directly to actual API usage.

### Deployment/team concerns

- The app is local-first and currently designed for Windows/local usage.
- For team use, likely next needs:
  - shared project storage
  - user accounts/roles
  - controlled API key handling
  - deployment strategy
  - logging
  - audit trail
  - better handling for concurrent users
  - central TM/reference repository

## Specific areas where expert advice is needed

### 1. CAT-tool interoperability

The app currently supports XLIFF/SDLXLIFF workflows, but true Trados compatibility is delicate. SDLXLIFF should not be faked by renaming a generic XLIFF file. A real SDLXLIFF normally includes Trados-specific metadata and file type definitions.

Expert review should answer:

- What is the safest practical SDLXLIFF workflow?
- Should the app generate only generic XLIFF unless a real SDLXLIFF template is supplied?
- How should segment IDs, inline tags, and locked/non-translatable content be preserved?
- What minimum tests are needed before trusting SDLXLIFF output for TM updates?

### 2. Translation Memory strategy

The app can import TMX/CSV memories and read some SDLTM memories. SDLTM remains read-only because it is proprietary and SQLite-based.

Expert review should answer:

- Should the app standardize on TMX as the internal exchange format?
- How should fuzzy matching, context matches, penalties, and term consistency be handled?
- Should a real local TM database be introduced?
- How should accepted bilingual review rows update the TM?

### 3. Document-format preservation

DOCX export currently edits the original DOCX XML text nodes where possible. This preserves formatting better than rebuilding a DOCX from scratch. PDF export is regenerated and does not preserve original PDF design.

Expert review should answer:

- Is the DOCX XML replacement approach safe enough?
- How should tables, text boxes, headers/footers, footnotes, tracked changes, comments, and embedded objects be handled?
- Should PDF be treated as text-only in version 1 unless a separate layout engine is built?
- How should Excel files be translated while preserving formulas, styles, merged cells, and hidden sheets?

### 4. Large-document processing

The app may need to handle files of 10,000 to 30,000 words or more.

Expert review should answer:

- What chunking architecture should be used?
- How should context be carried across chunks?
- How should terminology consistency be enforced?
- How should partial failures and resumable jobs be handled?
- How should cost be estimated before work begins?

### 5. Team deployment

The app started as a local Windows Streamlit tool, but the goal is team use.

Expert review should answer:

- Should the next version remain Streamlit?
- Should it become a desktop app using Tauri/Electron?
- Should it become a proper web app with a backend?
- How should users, projects, permissions, API keys, and shared TMs be managed?
- How should backups, audit logs, and version history work?

## Current files of interest

Main UI:

- `app.py`

OpenAI helper:

- `openai_client.py`

Analysis/prompt/translation/proofreading/QA:

- `analysis.py`
- `prompt_builder.py`
- `translator.py`
- `proofreader.py`
- `qa.py`

File import/export:

- `import_files.py`
- `export_docx.py`
- `export_pdf.py`
- `export_xliff.py`
- `export_bilingual_template.py`
- `export_same_format.py`

Alignment and bilingual review:

- `xliff_aligner.py`
- `bilingual_review.py`

TM/reference:

- `translation_memory.py`
- `reference_files.py`

Cost/pricing:

- `cost_estimator.py`
- `pricing.py`
- `net_word_grid.py`

Persistence:

- `project_repository.py`
- `prompt_archive.py`

Handout translator:

- `handout_translator_v1/app.py`

Tests:

- `tests/`

## Suggested expert review questions

Ask ChatGPT to analyse:

1. Is this architecture suitable for a small translation team?
2. Which features should be split into modules/services next?
3. What are the biggest risks around SDLXLIFF/XLIFF/TMX handling?
4. How should the app handle large documents, chunking, and cost control?
5. What is the best path toward safe team deployment?
6. Should this remain Streamlit, or move to a proper frontend/backend architecture?
7. How can DOCX/XLSX formatting preservation be made more reliable?
8. How should project repository and prompt archive be redesigned for team use?
9. What would a production roadmap look like?
10. What should be removed, simplified, or postponed?
11. What should be tested before the app is trusted for real client jobs?
12. What would be the best minimum viable team version?
13. Which current features are prototype-level and should be hardened first?
14. What risks could create bad translations, corrupted files, or unusable CAT-tool imports?
15. How should the app present technical limitations to non-programmer users?

## Suggested prompt to use with this document

```text
You are a senior software engineer and localization technology consultant. You understand translation industry software, Trados Studio, CAT tools, SDLXLIFF/XLIFF/TMX/SDLTM, document format preservation, AI translation workflows, and deployment for small translation teams.

Read the attached project brief and analyse the app.

Please provide:
1. A high-level assessment.
2. The top architectural risks.
3. The top translation-industry workflow risks.
4. Which features are strong and should be kept.
5. Which features should be redesigned.
6. A practical development roadmap for the next 1 month, 3 months, and 6 months.
7. Specific technical recommendations for SDLXLIFF/XLIFF/TMX/DOCX handling.
8. Recommendations for team deployment.
9. Questions you would ask before turning this into production software.
10. A prioritized list of concrete changes a programmer should implement next.

Be practical and specific. Assume the user is not a programmer but is familiar with translation workflows.
```
