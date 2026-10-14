@echo off
setlocal
cd /d "%~dp0frontend"
if not exist "node_modules" (
  call npm install
  if errorlevel 1 goto :error
)
call npm run dev -- --host 127.0.0.1
goto :eof
:error
echo Frontend setup failed. Install Node.js 18 or newer and retry.
pause
