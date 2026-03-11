@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo =========================================
echo 🎬 Podcast-to-Shorts (PodcastClipper Pro)
echo =========================================

rem Check if virtual environment exists
if not exist "venv\" (
    echo [INFO] Virtual environment not found. Initiating first-time setup...
    
    rem Check if python is available
    python --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] Python is not installed or not in your PATH.
        echo Please install Python 3.10+ from python.org
        pause
        exit /b
    )

    echo [1/3] Creating virtual environment...
    python -m venv venv
    
    echo [2/3] Upgrading pip...
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    
    echo [3/3] Installing dependencies - this may take a few minutes...
    pip install -r requirements.txt
    
    echo.
    echo [SUCCESS] Environment setup complete!
    echo =========================================
) else (
    call venv\Scripts\activate.bat
)

echo [INFO] Starting application...
echo (AI models may take a moment to initialize on first run)
echo.

python main.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The application exited with code %errorlevel%.
    pause
)

deactivate
pause

