@echo off
REM ---------------------------------------------------------------------------
REM  NACC SYS V3 - one-time local setup for Windows.
REM
REM  Creates a self-contained development copy: SQLite instead of Neon, files on
REM  disk instead of Cloudflare R2, no Google sign-in, no email. Nothing here
REM  touches the live system, and nothing here needs an internet service to be
REM  up. Run it once; use run-local.bat afterwards.
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

echo.
echo  NACC SYS V3 - local setup
echo  =========================
echo.

REM --- Prerequisites, checked before anything is created ---------------------
where python >nul 2>nul
if errorlevel 1 (
    echo  [X] Python is not on PATH.
    echo      Install Python 3.11 or newer from https://www.python.org/downloads/
    echo      IMPORTANT: tick "Add python.exe to PATH" in the installer.
    goto :fail
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo  [OK] Python %%v

where node >nul 2>nul
if errorlevel 1 (
    echo  [X] Node.js is not on PATH.
    echo      Install the LTS version from https://nodejs.org/
    goto :fail
)
for /f %%v in ('node --version') do echo  [OK] Node %%v
echo.

REM --- Backend ---------------------------------------------------------------
echo  [1/6] Creating the Python environment...
cd backend
if not exist .venv (
    python -m venv .venv
    if errorlevel 1 goto :fail
) else (
    echo        (.venv already exists - reusing it)
)

echo  [2/6] Installing backend packages... this takes a few minutes.
.venv\Scripts\python -m pip install --quiet --upgrade pip
.venv\Scripts\pip install --quiet -r requirements.txt
if errorlevel 1 goto :fail

if not exist .env (
    copy /y .env.example .env >nul
    echo        Created backend\.env  ^(SQLite, local files, no cloud services^)
) else (
    echo        backend\.env already exists - left alone
)

echo  [3/6] Building the database...
.venv\Scripts\python manage.py migrate --noinput
if errorlevel 1 goto :fail

echo  [4/6] Seeding roles and the default administrator...
.venv\Scripts\python manage.py seed_initial_data
if errorlevel 1 goto :fail

echo  [5/6] Loading Region I addresses ^(3,265 barangays^)...
.venv\Scripts\python manage.py seed_psgc
if errorlevel 1 goto :fail

REM --- Frontend --------------------------------------------------------------
cd ..\frontend
echo  [6/6] Installing frontend packages... this takes a few minutes.
if not exist .env (
    copy /y .env.example .env >nul
    echo        Created frontend\.env  ^(points at http://localhost:8000/api^)
) else (
    echo        frontend\.env already exists - left alone
)
call npm install --silent
if errorlevel 1 goto :fail

cd ..
echo.
echo  =========================================================
echo   Setup complete.
echo.
echo   Start it with:   run-local.bat
echo.
echo   Then open        http://localhost:5173
echo   Sign in as       admin@racco1.gov.ph  /  admin1234
echo  =========================================================
echo.
pause
exit /b 0

:fail
echo.
echo  Setup stopped because a step failed. The message above says which.
echo  Nothing was left half-installed that re-running will not fix.
echo.
pause
exit /b 1
