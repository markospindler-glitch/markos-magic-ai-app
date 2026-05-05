@echo off
set /p OPENAI_KEY=Paste your OpenAI API key here, then press Enter: 
setx OPENAI_API_KEY "%OPENAI_KEY%"
echo.
echo API key saved. Close this window before starting the app.
pause
