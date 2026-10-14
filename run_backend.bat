@echo off
setlocal
cd /d "%~dp0backend"
if not exist "venv\Scripts\python.exe" (
  py -3.12 -m venv venv
  if errorlevel 1 py -3 -m venv venv
  if errorlevel 1 goto :error
  "venv\Scripts\python.exe" -m pip install --upgrade pip
  "venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :error
  "venv\Scripts\python.exe" -m spacy download en_core_web_sm
)
"venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
goto :eof
:error
echo Backend setup failed. See the error above and check Python 3.12 and internet access.
pause
