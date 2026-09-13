@echo off
REM ---------------------------------------------------------------------------
REM  NACC SYS V3 - start the local model server.
REM
REM  The assistant, the chatbot, pre-session briefs and self-report detection
REM  all talk to Ollama on 11434. run-local.bat used to start the API and the
REM  frontend and leave this to whoever remembered, so on a fresh machine every
REM  one of those features failed one request at a time from inside a screen -
REM  which reads like a broken feature rather than a service nobody started.
REM
REM  Optional by design: the case-management system runs perfectly well with no
REM  model at all. This warns and reports success, so a machine without Ollama
REM  still starts everything else.
REM
REM  Safe to run on its own, and safe to run twice.
REM ---------------------------------------------------------------------------
setlocal

REM  The model everything here was built and measured against. qwen3.5:2b does
REM  not load on this machine - it fails allocating a ~2 GB buffer.
set "NACC_MODEL=qwen2.5:3b-instruct"

REM  Loopback only. Ollama listens on every network interface unless told
REM  otherwise, which puts an unauthenticated model server on whatever network
REM  this machine has joined - a campus, an office, a cafe.
set "OLLAMA_HOST=127.0.0.1"
REM  Keep the model resident between calls. A cold load measured 12-16s here,
REM  and eviction makes every request pay it. Costs about 1.9 GB of RAM.
set "OLLAMA_KEEP_ALIVE=-1"
REM  One generation at a time: concurrent runs on four cores measured slower
REM  rather than parallel.
set "OLLAMA_NUM_PARALLEL=1"
REM  One model resident, not several. Two 2 GB models on this machine is where
REM  it starts swapping.
set "OLLAMA_MAX_LOADED_MODELS=1"

REM --- Already serving? The Ollama tray app starts one of its own. -----------
netstat -an | findstr /c:":11434" | findstr /c:"LISTENING" >nul 2>nul
if errorlevel 1 goto :find_ollama

echo  [OK] Ollama is already listening on 11434.
netstat -an | findstr /c:"0.0.0.0:11434" >nul 2>nul
if errorlevel 1 goto :check_model
echo  [!!] ...on every network interface, not just this machine. Something
echo       else started that server - most likely the Ollama tray app - so
echo       the loopback setting in this script does not apply to it. Quit it
echo       from the notification area and run this again to bind it safely.
goto :check_model

REM --- Find it --------------------------------------------------------------
:find_ollama
set "OLLAMA_EXE="
where ollama >nul 2>nul
if not errorlevel 1 set "OLLAMA_EXE=ollama"
if defined OLLAMA_EXE goto :serve
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if defined OLLAMA_EXE goto :serve

echo  [--] Ollama was not found, so the assistant, the chatbot and
echo       self-report detection will be unavailable. Everything else runs.
echo       Install it from https://ollama.com/download then run:
echo           ollama pull %NACC_MODEL%
goto :done

:serve
start "NACC Ollama" /min "%OLLAMA_EXE%" serve
echo  [OK] Ollama starting on 127.0.0.1:11434

REM --- Installed is not the same as pulled ----------------------------------
:check_model
if exist "%USERPROFILE%\.ollama\models\manifests\registry.ollama.ai\library\qwen2.5\3b-instruct" goto :done
echo  [--] The model %NACC_MODEL% has not been pulled on this machine, so
echo       assistant features will fail at the first question rather than
echo       here. Run:
echo           ollama pull %NACC_MODEL%

:done
exit /b 0
