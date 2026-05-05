# Marko's Magic AI App

This is a simple Windows-friendly Streamlit app for a translation workflow.

Version 1 supports:

- Paste plain source text
- Upload TXT, CSV, Excel, DOCX, IDML, or selectable-text PDF source files
- Upload TMX, CSV, or read-only SDLTM Translation Memories
- Find fuzzy Translation Memory matches and edit them before translation
- Upload client reference files such as glossaries, past translations, style guides, or similar documents
- Analyse reference files and use their terminology/style guidance throughout the workflow
- Save generated prompts in a local prompt archive for later reuse
- Show progress bars with percentages for workflow steps and export generation
- Show an estimated GPT-5.5 API price list inside the app
- Show estimated cost for the current translation job after each GPT-5.5 step
- Show word and character counters for key text fields
- Analyse source text with the translation net word count grid and estimate raw words, net words, and cost
- Use a six-step tabbed interface: Source, Context, Prompt, Translation, Handout Translator, and QA & Export
- Translate scanned/image handouts into Slovenian and recreate them as HTML, PDF, or Word from the integrated Handout Translator
- Branded visual header image and polished Streamlit styling
- Save and load past projects from a local project repository
- Manually review source/target sentence pairs in an editable bilingual table before QA
- Show visible proofreading changes in the app while keeping exports clean
- Choose source language, target language, and text domain
- Analyse grammar, style, terminology, syntax, spelling, punctuation, topic, register, and translation risks using GPT-5.5
- Generate and edit a custom GPT-5.5 translation prompt
- Translate using GPT-5.5 through the OpenAI API
- Proofread the translation as a native speaker using GPT-5.5
- Run a GPT-5.5 source/target QA check
- Export translation as DOCX and PDF
- Export target SDLXLIFF/XLIFF/XLF in the same format when the source upload is a bilingual file
- Export the final translation in the same extension as the input file where supported
- Export bilingual SDLXLIFF from the Bilingual files section
- Export a target-language DOCX from the original uploaded DOCX while preserving the DOCX package, styles, fonts, tables, images, spacing, and layout as much as possible
- Reflow the final target text to match the source DOCX paragraph count before Target DOCX export
- Export a sentence-segmented bilingual DOCX review table
- Prepare an aligned bilingual XLIFF using GPT-5.5 before export
- Export bilingual source/target XLIFF for CAT tools such as Trados Studio
- Re-upload an existing XLIFF/XLF and re-align it with GPT-5.5
- Mark XLIFF segment alignment confidence so uncertain pairs can be reviewed before TM use
- Export the finished work as a TMX memory for reuse
- Download an updated uploaded TMX that merges the original TM with high-confidence aligned final segments
- Optionally export an analysis report as DOCX and PDF

DOCX formatting preservation depends on paragraph alignment: keep one target paragraph for each source paragraph. The app edits the original DOCX XML text nodes directly, which preserves formatting much better than rebuilding a new Word file. IDML import/export reads and replaces editable story text in `Stories/*.xml` while preserving the IDML package. Excel/CSV import extracts readable cell values as text. PDF import extracts selectable text only. It does not use OCR and does not rebuild the original PDF design.

## Setup on Windows

1. Install Python from <https://www.python.org/downloads/windows/>.
   During installation, tick **Add Python to PATH**.

2. Open PowerShell in this project folder.

3. Install the required packages:

```powershell
python -m pip install -r requirements.txt
```

4. Set your OpenAI API key:

```powershell
setx OPENAI_API_KEY "your_api_key_here"
```

Close and reopen PowerShell after running `setx`.

5. Start the app:

```powershell
streamlit run app.py
```

The app will open in your browser.

## Files

- `app.py` - Streamlit user interface
- `assets/app_header.png` - generated visual header asset
- `openai_client.py` - shared OpenAI API helper
- `import_files.py` - TXT, CSV, Excel, DOCX, IDML, and selectable-text PDF import
- `handout_translator_v1/` - integrated image/scan handout translator section
- `net_word_grid.py` - weighted/net word count analysis based on the pricing grid
- `analysis.py` - GPT-5.5 source-text analysis
- `bilingual_review.py` - editable bilingual review table helpers
- `prompt_builder.py` - GPT-5.5 custom translation prompt builder
- `prompt_archive.py` - reusable prompt template archive
- `project_repository.py` - local saved project repository
- `pricing.py` - in-app estimated API price table
- `cost_estimator.py` - current-job token and cost estimation
- `diff_view.py` - visible proofreading change view
- `text_stats.py` - word and character counters
- `progress_ui.py` - Streamlit progress bars for workflow steps
- `translator.py` - GPT-5.5 translation call
- `proofreader.py` - GPT-5.5 native-speaker proofreading
- `qa.py` - GPT-5.5 source/target QA checks
- `reference_files.py` - client reference file extraction and GPT-5.5 guidance analysis
- `reflow.py` - target text reflow for formatted DOCX export
- `translation_memory.py` - TMX/CSV import, fuzzy matching, and TMX export
- `export_docx.py` - DOCX export
- `export_bilingual_template.py` - same-format SDLXLIFF/XLIFF/XLF export from the uploaded bilingual template
- `export_pdf.py` - PDF export
- `export_same_format.py` - same-extension final export for TXT, CSV, PDF, DOCX, IDML, XLSX, XLSM, and legacy XLS fallback
- `export_xliff.py` - bilingual XLIFF export
- `xliff_aligner.py` - GPT-5.5 source/target segment alignment for XLIFF
- `requirements.txt` - Python packages to install

Saved projects keep editable text, context, reports, review rows, and alignment metadata. Re-upload the original DOCX if you need to regenerate a formatted Target DOCX from a loaded project.

SDLTM support is import-only. The app reads usable source/target pairs from SDL file-based Translation Memories when their SQLite structure can be safely inspected, but it does not modify `.sdltm` files. For maximum reliability, export SDLTM memories from Trados Studio as TMX and upload the TMX file.
