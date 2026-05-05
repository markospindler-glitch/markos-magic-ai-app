@echo off
cd /d "%~dp0"
"%LOCALAPPDATA%\Programs\Python\Python313\python.exe" -m streamlit run app.py
pause
