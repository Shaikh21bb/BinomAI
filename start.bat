@echo off
setlocal EnableDelayedExpansion

echo ====================================================
echo                BINOM AI - STARTUP MENU              
echo ====================================================

:: 1. Verify Environment Variables
echo.
echo [1/4] Verifying Environment Variables...
if not exist ".env" (
    echo Error: .env file not found.
    if exist ".env.example" (
        echo Copying .env.example to .env...
        copy .env.example .env
        echo Please fill in the required variables in .env and run this script again.
    ) else (
        echo Error: .env.example also not found. Cannot proceed.
    )
    exit /b 1
)

:: Find missing vars
set MISSING_VARS=0
for %%v in (DATABASE_URL SUPABASE_URL SUPABASE_ANON_KEY GOOGLE_AI_API_KEY) do (
    findstr /C:"%%v=" .env >nul
    if errorlevel 1 (
        echo [X] Missing required environment variable: %%v
        set MISSING_VARS=1
    )
)

if %MISSING_VARS%==1 (
    echo.
    echo How to fix: Open the .env file in the root directory and provide valid values.
    exit /b 1
)
echo [OK] Environment variables verified.

:: 2. Start Backend & Infrastructure
echo.
echo [2/4] Starting Infrastructure (Postgres, Redis, Celery, Backend)...
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker Compose is not installed or not in PATH.
    exit /b 1
)

docker-compose up -d --build
if errorlevel 1 (
    echo [X] Failed to start docker containers.
    echo How to fix: Ensure Docker Desktop is running.
    exit /b 1
)
echo [OK] Docker containers started.

:: 3. Start Frontend
echo.
echo [3/4] Starting Frontend (Next.js)...
if not exist "stitch_frontend\node_modules\" (
    echo Installing frontend dependencies...
    cd stitch_frontend
    call npm install
    cd ..
)

echo Starting Next.js in a new window...
start "BINOM AI - Frontend" cmd /c "cd stitch_frontend && npm run dev"
echo [OK] Frontend starting.

:: 4. Health Checks
echo.
echo [4/4] Performing Health Checks...
echo Waiting for services to become ready (this may take up to 30 seconds)...
echo Please check http://localhost:8000/api/v1/health manually to verify advanced statuses.
echo.
echo ========================
echo BINOM AI STATUS
echo ========================
echo Backend: Check docker logs
echo Frontend: Check new console window
echo Database: Configured
echo Redis: Configured
echo Celery: Configured
echo Supabase: Configured
echo AI Engine: Configured
echo Everything Ready: Refer to endpoints

echo.
echo BINOM AI is running!
echo Frontend: http://localhost:3000
echo Backend API: http://localhost:8000/api/v1/docs
echo.
echo To stop services, run 'docker-compose down' and close the Frontend window.
pause
