@echo off
REM ---------------------------------------------------------------------------
REM  NACC SYS V3 - start the local copy.
REM
REM  Opens three windows: the Django API on :8000, the Vite frontend on :5173
REM  and the Ollama model server on :11434. Close a window to stop that half.
REM  Run setup-local.bat first. Ollama is optional - see start-ollama.bat.
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

if not exist backend\.venv\Scripts\python.exe (
    echo  The Python environment is missing. Run setup-local.bat first.
    pause
    exit /b 1
)
if not exist frontend\node_modules (
    echo  Frontend packages are missing. Run setup-local.bat first.
    pause
    exit /b 1
)

echo.
echo  Starting NACC SYS V3 locally...
echo.
echo    API       http://localhost:8000
echo    Frontend  http://localhost:5173
echo    Health    http://localhost:8000/healthz/
echo    Model     http://localhost:11434   qwen2.5:3b-instruct
echo.
echo    Sign in   admin@racco1.gov.ph  /  admin1234
echo.
echo  Three windows will open. Close them to stop.
echo.

REM  Before the API, so the assistant is reachable by the time a screen asks.
REM  Never fails the launch: a missing model server costs the assistant
REM  features and nothing else.
call "%~dp0start-ollama.bat"
echo.

start "NACC API"      cmd /k "cd /d %~dp0backend && .venv\Scripts\python manage.py runserver 8000"
timeout /t 3 >nul
start "NACC Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 6 >nul
start http://localhost:5173
exit /b 0
