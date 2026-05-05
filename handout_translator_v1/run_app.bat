@echo off
cd /d "%~dp0"

set PYTHON_EXE=C:\Users\marko\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe

echo Checking required packages...
"%PYTHON_EXE%" -m pip install -r requirements.txt

echo Starting the app...
"%PYTHON_EXE%" -m streamlit run app.py

pause
