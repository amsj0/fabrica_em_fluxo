@echo off
cd /d "%~dp0"
set "FLUXO_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%FLUXO_PYTHON%" set "FLUXO_PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%FLUXO_PYTHON%" (
  echo Instale o ambiente conforme README.md.
  pause
  exit /b 1
)
"%FLUXO_PYTHON%" -m streamlit run app/main.py --server.address=127.0.0.1 --server.port=8502 --server.headless=true --browser.gatherUsageStats=false
