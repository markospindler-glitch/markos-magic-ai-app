# Handout Translator

This is your personal handout translation app.

Current version does this:

1. Upload one image of an English handout.
2. Send the image to the OpenAI API with vision.
3. Extract all visible English text.
4. Extract the handout structure as richer JSON with layout details.
5. Translate each element into Slovenian.
6. Let you review and edit each extracted element.
7. Recreate a cleaner A4 handout layout in HTML/CSS.
8. Recreate the DBT chain-analysis diagram when the original handout contains it.
9. Export the edited Slovenian handout as HTML, A4 PDF, or Word `.docx`.
10. Show the structured JSON and the section-by-section translation.

It does not yet include Canva-style visual polish. That comes next.

## Where To Put Your OpenAI API Key

Open this file:

`.streamlit\secrets.toml`

Find this line:

```toml
OPENAI_API_KEY = "PASTE_YOUR_OPENAI_API_KEY_HERE"
```

Replace `PASTE_YOUR_OPENAI_API_KEY_HERE` with your real OpenAI API key.

It should look like this:

```toml
OPENAI_API_KEY = "sk-proj-your-real-key-here"
```

Keep the quotation marks.

## How To Run On Windows

1. Open this folder:

   `C:\Users\marko\Documents\Codex\2026-05-01\i-am-not-a-programmer-help\handout_translator_v1`

2. Double-click:

   `run_app.bat`

3. The first run may take a few minutes because it checks that Streamlit and OpenAI are installed.

4. A browser window should open automatically.

5. Upload a JPG or PNG scan of one English handout page.

6. Click:

   `Extract, translate, and recreate layout`

## Development Order

We are building gradually:

1. OCR + translation - current version
2. Structured extraction with layout metadata - current version
3. Cleaner A4 layout recreation - current version
4. PDF export - current version
5. Word `.docx` export - current version
6. Editable review - current version
7. Canva-style design polish - next version

Do not try to build all steps at once.
