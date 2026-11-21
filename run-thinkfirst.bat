@echo off
setlocal EnableDelayedExpansion
title ThinkFirst Launcher

cd /d "%~dp0"

echo ============================================================================
echo   ThinkFirst - "Mind print" Learning Environment ^& Adaptive Diagnostic
echo   AI that makes you think, not AI that thinks for you.
echo ============================================================================
echo.

REM Optional Docker mode: run-thinkfirst.bat --docker
if /I "%~1"=="--docker" (
    echo [Docker Mode] Starting full Docker stack ^(Postgres + pgvector, Redis, Qdrant, SeaweedFS, API, Worker, Web^)...
    docker compose up --build
    exit /b !ERRORLEVEL!
)

REM 1. Locate Python for the FastAPI backend
set "PY_CMD="
if exist "%~dp0api\.venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0api\.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        set "PY_CMD=python"
    )
)

if "!PY_CMD!"=="" (
    echo [ERROR] Python 3.12+ was not found on PATH or in api\.venv.
    echo Install Python 3.12 or uv, then run this script again.
    pause
    exit /b 1
)

echo [1/4] Preparing FastAPI backend environment...
if not exist "%~dp0api\.env" (
    if exist "%~dp0.env.example" (
        copy /Y "%~dp0.env.example" "%~dp0api\.env" >nul
        echo       Created api\.env from .env.example
    )
)

REM Check if required Python packages are installed; install via uv or pip if missing
pushd "%~dp0api"
set "PYTHONPATH=%~dp0api"
"!PY_CMD!" -c "import fastapi, sqlalchemy, sympy, uvicorn" >nul 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo       Installing backend Python dependencies...
    where uv >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        if not exist ".venv\Scripts\python.exe" (
            uv venv --python 3.12 .venv
        )
        uv pip install --python .venv -e ".[dev]"
        set "PY_CMD=%~dp0api\.venv\Scripts\python.exe"
    ) else (
        "!PY_CMD!" -m pip install -e ".[dev]"
    )
)

echo [2/4] Seeding database, demo account ^& calibrated diagnostic knowledge space...
"!PY_CMD!" -m thinkfirst.seed --with-subject
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Database seeding failed.
    popd
    pause
    exit /b 1
)
popd

REM 2. Sync branding assets into web\ and thinkfirst-web\
if exist "%~dp0branding\*.svg" (
    if not exist "%~dp0web\public\brand" mkdir "%~dp0web\public\brand"
    copy /Y "%~dp0branding\*.svg" "%~dp0web\public\brand\" >nul
    copy /Y "%~dp0branding\favicon.svg" "%~dp0web\src\app\icon.svg" >nul
    if exist "%~dp0thinkfirst-web" (
        if not exist "%~dp0thinkfirst-web\public\brand" mkdir "%~dp0thinkfirst-web\public\brand"
        copy /Y "%~dp0branding\*.svg" "%~dp0thinkfirst-web\public\brand\" >nul
        copy /Y "%~dp0branding\favicon.svg" "%~dp0thinkfirst-web\src\app\icon.svg" >nul
    )
)

REM 3. Prepare Next.js frontend (uses web\ which is synced with thinkfirst-web\)
set "WEB_DIR=%~dp0web"
if /I "%~1"=="--thinkfirst-web" (
    set "WEB_DIR=%~dp0thinkfirst-web"
)

echo [3/4] Checking Next.js frontend dependencies in !WEB_DIR!...
pushd "!WEB_DIR!"
if not exist "node_modules" (
    echo       Installing frontend packages ^(npm install^)...
    call npm install
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] npm install failed in !WEB_DIR!.
        popd
        pause
        exit /b 1
    )
)
popd

echo [4/4] Launching ThinkFirst Backend API ^(port 8000^) and Frontend Web ^(port 3000^)...
start "ThinkFirst API (http://127.0.0.1:8000)" cmd /k "cd /d "%~dp0api" && set PYTHONPATH=%~dp0api&& "!PY_CMD!" -m uvicorn thinkfirst.main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 2 /nobreak >nul
start "ThinkFirst Web (http://localhost:3000)" cmd /k "cd /d "!WEB_DIR!" && set API_URL=http://127.0.0.1:8000&& npm run dev"

echo.
echo ============================================================================
echo   ThinkFirst is starting up!
echo   - Web App:      http://localhost:3000
echo   - API ^& Docs:   http://127.0.0.1:8000/api/docs
echo   - Demo Account: demo@thinkfirst.local  /  demo-password
echo ============================================================================
echo.
timeout /t 4 /nobreak >nul
start "" "http://localhost:3000"
exit /b 0
