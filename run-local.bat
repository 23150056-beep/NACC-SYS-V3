@echo off
REM ---------------------------------------------------------------------------
REM  NACC SYS V3 - start the local copy.
REM
REM  Opens two windows: the Django API on :8000 and the Vite frontend on :5173.
REM  Close either window to stop that half. Run setup-local.bat first.
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
echo.
echo    Sign in   admin@racco1.gov.ph  /  admin1234
echo.
echo  Two windows will open. Close them to stop.
echo.

start "NACC API"      cmd /k "cd /d %~dp0backend && .venv\Scripts\python manage.py runserver 8000"
timeout /t 3 >nul
start "NACC Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 6 >nul
start http://localhost:5173
exit /b 0
