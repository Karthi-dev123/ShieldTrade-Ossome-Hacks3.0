@echo off
echo Starting ShieldTrade E2E Evaluation...

if not exist ".env" (
    echo Error: .env file missing! Please put the .env file provided personally in this root folder.
    pause
    exit /b 1
)

findstr "USE_OLLAMA=true" .env >nul
if %errorlevel%==0 (
    where ollama >nul 2>nul
    if %errorlevel% neq 0 (
        echo Ollama is not installed. Please download and install from https://ollama.com/download to use the local fallback!
    ) else (
        echo Ollama is verified to be installed.
    )
)

bash scripts/demo_e2e_lifecycle.sh
pause
