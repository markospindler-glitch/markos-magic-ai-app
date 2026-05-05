# Deploying Marko's Magic AI App to Streamlit Community Cloud

## What Streamlit Cloud needs

Streamlit Community Cloud deploys from GitHub. The app folder must be published in a GitHub repository, and the main file must be:

```text
app.py
```

## Do not publish private local data

The repository should not include:

- OpenAI API keys
- `.streamlit/secrets.toml`
- local saved projects in `projects/`
- autosaved project data in `data/`
- local installers such as `python-3.13.13-amd64.exe`
- client documents, exports, TM files, SDLXLIFF files, or PDFs

These are excluded in `.gitignore`.

## Streamlit settings

When creating the app on Streamlit Community Cloud, use:

```text
Repository: markospindler-glitch/<your-repo-name>
Branch: main
Main file path: app.py
```

## OpenAI API key

In Streamlit Community Cloud, add this as an app secret:

```toml
OPENAI_API_KEY = "your_api_key_here"
```

Do not paste the API key into the code.

## Notes

- The app stores project data locally. On Streamlit Community Cloud, storage is temporary and not a reliable shared team database.
- For team use, the next major improvement should be shared persistent storage for projects and prompt templates.
- Heavy or private client files should be handled carefully because Streamlit Community Cloud is not the same as a controlled local Windows workstation.
