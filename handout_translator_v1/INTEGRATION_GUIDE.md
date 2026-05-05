# Integration Guide: Use The Handout Translator Inside Another App

This guide explains how to use this translator as one section inside a larger app.

The translator is still usable as a standalone app with `run_app.bat`, but it now also exposes a reusable Streamlit function:

```python
render_handout_translator_section()
```

That function lives in:

```text
handout_translator_v1/app.py
```

## Best Option If Your Other App Uses Streamlit

Use this option if your other app is also a Python Streamlit app.

### 1. Put The Folder Next To Your Other App

Place the whole folder:

```text
handout_translator_v1
```

next to your other app's main file.

Example:

```text
my_other_app/
  main_app.py
  handout_translator_v1/
    app.py
    requirements.txt
    __init__.py
```

### 2. Install The Required Packages

Add these packages to your other app's requirements file:

```text
streamlit>=1.40.0
openai>=2.0.0
reportlab>=4.0.0
pypdf>=5.0.0
python-docx>=1.1.0
Pillow>=10.0.0
```

If your other app already has some of them, keep one copy only.

### 3. Add The Translator As A Tab Or Section

In your other app, import the translator section:

```python
from handout_translator_v1.app import render_handout_translator_section
```

Then place it wherever you want it to appear.

Example with tabs:

```python
import streamlit as st
from handout_translator_v1.app import render_handout_translator_section

st.set_page_config(page_title="My App", layout="wide")

tab_home, tab_translator = st.tabs(["Home", "Handout Translator"])

with tab_home:
    st.title("Home")
    st.write("Your other app content goes here.")

with tab_translator:
    render_handout_translator_section()
```

Example with a sidebar menu:

```python
import streamlit as st
from handout_translator_v1.app import render_handout_translator_section

st.set_page_config(page_title="My App", layout="wide")

section = st.sidebar.radio(
    "Choose section",
    ["Home", "Handout Translator"],
)

if section == "Home":
    st.title("Home")
    st.write("Your other app content goes here.")

if section == "Handout Translator":
    render_handout_translator_section()
```

### 4. Add The OpenAI API Key

The translator looks for the API key in either:

```text
.streamlit/secrets.toml
```

or in the Windows environment variable:

```text
OPENAI_API_KEY
```

For Streamlit, the simplest setup is:

```toml
OPENAI_API_KEY = "sk-proj-your-real-key-here"
```

Put that in your other app's `.streamlit/secrets.toml`.

Do not put the API key directly inside Python code.

## If Your Other App Is Not Streamlit

There are two realistic choices.

### Simple Choice: Run Translator Beside The Other App

Run the translator as its own local Streamlit page:

```powershell
streamlit run handout_translator_v1/app.py --server.port 8501
```

Then link to it from your other app:

```text
http://localhost:8501
```

Some web apps can also show it inside an iframe:

```html
<iframe src="http://localhost:8501" width="100%" height="900"></iframe>
```

This is the easiest integration, but it runs as a separate local page.

### Cleaner Choice: Extract The Core Functions

Ask a developer to move the non-Streamlit logic into a separate file such as:

```text
handout_translator_v1/translator_core.py
```

The reusable functions are currently:

```python
uploaded_image_to_data_url()
call_openai_vision()
parse_model_json()
build_handout_html()
build_pdf_bytes()
build_docx_bytes()
```

Then the other app can call those functions from its own interface.

## Files To Keep Together

Keep these files together:

```text
handout_translator_v1/
  app.py
  __init__.py
  requirements.txt
  README_WINDOWS.md
```

For standalone use, also keep:

```text
run_app.bat
.streamlit/secrets.toml
```

## Quick Checklist

1. Copy `handout_translator_v1` into your other app project.
2. Add the packages from `requirements.txt`.
3. Add your OpenAI API key to the other app's Streamlit secrets.
4. Import `render_handout_translator_section`.
5. Put it inside a tab, page, or sidebar section.
6. Run your other app.

