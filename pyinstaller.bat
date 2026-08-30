@echo off
chcp 65001 >nul
echo ========================================
echo   Display Card Manager - one-click build
echo ========================================

rem ===== Version (edit on each release) =====
set VERSION=v1.0.0

set ROOT=%~dp0
set RELEASE=%ROOT%Releases\%VERSION%

echo.
echo [0/3] Activating conda env displayCard ...
call conda activate displayCard
if %errorlevel% neq 0 (
    echo ERROR: failed to activate conda env displayCard
    pause
    exit /b 1
)

rem ===== Ensure pyinstaller. NOTE: call it via "python -m PyInstaller" (NOT bare
rem "pyinstaller"): this script is named pyinstaller.bat, and cmd resolves the bare
rem command to THIS file (current dir before PATH), recursing into itself. =====
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo pyinstaller not found, installing...
    python -m pip install pyinstaller
)

echo.
echo [1/3] Cleaning release dir %RELEASE% ...
if exist "%RELEASE%" rmdir /s /q "%RELEASE%"
mkdir "%RELEASE%"
if exist "%ROOT%build" rmdir /s /q "%ROOT%build"

echo.
echo [2/3] Building frontend ...
where npm >nul 2>&1
if %errorlevel% neq 0 ( echo ERROR: npm not found, install Node.js & pause & exit /b 1 )
pushd "%ROOT%webside"
if not exist "node_modules" (
    call npm install
    if %errorlevel% neq 0 ( echo ERROR: npm install failed & popd & pause & exit /b 1 )
)
call npm run build
if %errorlevel% neq 0 ( echo ERROR: frontend build failed & popd & pause & exit /b 1 )
popd
if not exist "%ROOT%webside\dist\index.html" (
    echo ERROR: webside\dist\index.html not found
    pause
    exit /b 1
)

echo.
echo [3/3] Building DisplayCardManager.exe (frontend bundled in) ...
python -m PyInstaller --clean --noconfirm "%ROOT%displaycard.spec" ^
    --distpath "%RELEASE%" --workpath "%ROOT%build"
if %errorlevel% neq 0 ( echo ERROR: exe build failed & pause & exit /b 1 )

rem ===== Ship a conf.ini template next to the exe =====
copy "%ROOT%conf.example.ini" "%RELEASE%\conf.ini" >nul

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
echo   3) Run DisplayCardManager.exe, then open http://localhost:9701
echo ========================================
pause
