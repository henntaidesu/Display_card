@echo off
chcp 65001 >nul
echo ========================================
echo   Display Card Manager - dev startup
echo ========================================
echo.

set ROOT=%~dp0
set BACKEND=%ROOT%backend
set WEBSIDE=%ROOT%webside

rem ===== conf.ini 检查：没有就从示例复制一份，并提醒填 MySQL 密码 =====
if not exist "%ROOT%conf.ini" (
    echo [!] conf.ini not found. Copying from conf.example.ini ...
    copy "%ROOT%conf.example.ini" "%ROOT%conf.ini" >nul
    echo [!] Please edit conf.ini and fill in your MySQL password, then re-run.
    echo.
)

echo [1/2] Activating conda env displayCard and starting backend ...
call conda activate displayCard
if errorlevel 1 (
    echo [ERROR] Failed to activate conda env displayCard.
    echo         Create it first:  conda create -n displayCard python=3.12
    pause
    exit /b 1
)

pushd "%BACKEND%"
rem 后台起后端；日志同时打印在本窗口
start "DisplayCard-Backend" /b python main.py
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
    if errorlevel 1 ( echo [ERROR] npm install failed & popd & pause & exit /b 1 )
)

echo.
echo ========================================
echo   Frontend:  http://localhost:9700
echo   Backend :  http://localhost:9701
echo   Press Ctrl+C to stop the frontend (backend keeps running in background)
echo ========================================
echo.

call npm run dev
popd
