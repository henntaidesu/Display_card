@echo off
setlocal enabledelayedexpansion
echo ========================================
echo   Display Card Manager - one-click build
echo ========================================

rem ===== Version (edit on each release) =====
set "VERSION=v1.0.0"

set "ROOT=%~dp0"
set "RELEASE=%ROOT%Releases\%VERSION%"

rem ---------------------------------------------------------------------------
rem Locate the displayCard conda env Python directly (no "conda activate", which
rem needs "conda init" shell integration and fails in a plain terminal).
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
if not defined DCPY (
  for /f "delims=" %%i in ('conda info --base 2^>nul') do set "CONDA_BASE=%%i"
  if defined CONDA_BASE if exist "!CONDA_BASE!\envs\displayCard\python.exe" set "DCPY=!CONDA_BASE!\envs\displayCard\python.exe"
)
if not defined DCPY (
  echo [ERROR] Could not find the displayCard conda env.
  echo         Create it:  conda create -n displayCard python=3.12
  pause
  exit /b 1
)
echo Using Python: !DCPY!

rem ===== Ensure pyinstaller. NOTE: call it via "python -m PyInstaller" (NOT bare
rem "pyinstaller"): this script is named pyinstaller.bat, and cmd resolves the bare
rem command to THIS file (current dir before PATH), recursing into itself. =====
"!DCPY!" -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo pyinstaller not found, installing...
    "!DCPY!" -m pip install pyinstaller
)

echo.
echo [1/3] Cleaning release dir %RELEASE% ...
if exist "%RELEASE%" rmdir /s /q "%RELEASE%"
mkdir "%RELEASE%"
if exist "%ROOT%build" rmdir /s /q "%ROOT%build"

echo.
echo [2/3] Building frontend ...
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: npm not found, install Node.js
    pause
    exit /b 1
)
pushd "%ROOT%webside"
if not exist "node_modules" (
    call npm install
    if %errorlevel% neq 0 (
        echo ERROR: npm install failed
        popd
        pause
        exit /b 1
    )
)
call npm run build
if %errorlevel% neq 0 (
    echo ERROR: frontend build failed
    popd
    pause
    exit /b 1
)
popd
if not exist "%ROOT%webside\dist\index.html" (
    echo ERROR: webside\dist\index.html not found
    pause
    exit /b 1
)

echo.
echo [3/3] Building DisplayCardManager.exe (frontend bundled in) ...
"!DCPY!" -m PyInstaller --clean --noconfirm "%ROOT%displaycard.spec" --distpath "%RELEASE%" --workpath "%ROOT%build"
if %errorlevel% neq 0 (
    echo ERROR: exe build failed
    pause
    exit /b 1
)

rem ===== Ship conf.ini next to the exe (contains your MySQL settings) =====
if exist "%ROOT%conf.ini" (
    copy "%ROOT%conf.ini" "%RELEASE%\conf.ini" >nul
) else (
    echo [!] conf.ini not found; the release has no config file. Create one next to the exe.
)

if exist "%ROOT%build" rmdir /s /q "%ROOT%build"

echo.
echo ========================================
echo   Build complete! Output: %RELEASE%
echo ========================================
dir /b "%RELEASE%"
echo ----------------------------------------
echo   1) Edit conf.ini next to the exe: fill in MySQL host/user/password.
echo   2) Make sure MySQL is running and the database exists (auto-created if the
echo      account has CREATE privilege).
echo   3) Run DisplayCardManager.exe, then open http://localhost:9910
echo ========================================
pause
endlocal
