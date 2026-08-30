@echo off
setlocal enabledelayedexpansion
echo ========================================
echo   Display Card Manager - dev startup
echo ========================================
echo.

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "WEBSIDE=%ROOT%webside"

rem conf.ini is the single config file (MySQL connection + listen port). The backend
rem also auto-generates a comment-free one on first run; this is just an early notice.
if not exist "%ROOT%conf.ini" (
    echo [!] conf.ini not found. The backend will create a default one on start.
    echo [!] After it appears, fill in the [mysql] password and re-run.
    echo.
)

rem ---------------------------------------------------------------------------
rem Locate the displayCard conda env Python directly. We do NOT use
rem "conda activate": it only works after "conda init" has set up cmd shell
rem integration, which fails in a plain double-clicked terminal. Running the
rem env's python.exe by full path needs no activation at all.
rem ---------------------------------------------------------------------------
set "DCPY="
for %%P in (
  "%USERPROFILE%\miniconda3\envs\displayCard\python.exe"
  "%USERPROFILE%\anaconda3\envs\displayCard\python.exe"
  "%LOCALAPPDATA%\miniconda3\envs\displayCard\python.exe"
  "%LOCALAPPDATA%\anaconda3\envs\displayCard\python.exe"
  "C:\ProgramData\miniconda3\envs\displayCard\python.exe"
  "C:\ProgramData\Anaconda3\envs\displayCard\python.exe"
) do (
  if exist "%%~P" set "DCPY=%%~P"
)

rem Fallback: derive the env path from "conda info --base" (conda just needs to be on PATH).
if not defined DCPY (
  for /f "delims=" %%i in ('conda info --base 2^>nul') do set "CONDA_BASE=%%i"
  if defined CONDA_BASE if exist "!CONDA_BASE!\envs\displayCard\python.exe" set "DCPY=!CONDA_BASE!\envs\displayCard\python.exe"
)

if not defined DCPY (
  echo [ERROR] Could not find the displayCard conda env.
  echo         Create it:  conda create -n displayCard python=3.12
  echo         Install deps: conda run -n displayCard pip install -r backend\requirements.txt
  pause
  exit /b 1
)

echo [1/2] Starting backend with:
echo        !DCPY!
rem Enable backend hot reload (uvicorn watches backend\*.py). Dev only; the exe
rem build ignores this flag.
set "DISPLAYCARD_RELOAD=1"
rem /b keeps the backend in THIS same console (no second window). Its log and the
rem frontend's log interleave in one CLI. The backend keeps running in the
rem background; closing this window stops both.
pushd "%BACKEND%"
start "DisplayCard-Backend" /b "!DCPY!" main.py
popd

timeout /t 2 /nobreak >nul

echo [2/2] Preparing frontend dev server ...
where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm not found. Install Node.js: https://nodejs.org/
    pause
    exit /b 1
)

pushd "%WEBSIDE%"
if not exist "node_modules" (
    echo Installing frontend deps ...
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed
        popd
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo   Frontend:  http://localhost:9911
echo   Backend :  http://localhost:9910   (backend + frontend logs share this window)
echo   Close this window to stop both.
echo ========================================
echo.

call npm run dev
popd

rem If npm exited on its own (not via Ctrl+C), the backend may still be holding
rem port 9910. Best-effort: kill whatever is LISTENING on it. (On Ctrl+C the shared
rem console usually signals the backend too, so this often finds nothing -- fine.)
echo.
echo Stopping backend on port 9910 ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":9910" ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
endlocal


