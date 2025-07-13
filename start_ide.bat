@echo off
REM MeistroCraft IDE Startup Script for Windows
REM Automatically sets up virtual environment and starts the web interface

setlocal enabledelayedexpansion

REM Configuration
set VENV_DIR=venv
set PYTHON_MIN_VERSION=3.8

echo.
echo 🚀 MeistroCraft IDE Startup Script
echo ==================================

REM Function to check if Python is available and get version
set PYTHON_CMD=
for %%i in (python3.11 python3.10 python3.9 python3.8 python3 python) do (
    %%i --version >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=2" %%v in ('%%i --version 2^>^&1') do (
            set version=%%v
            for /f "tokens=1,2 delims=." %%a in ("!version!") do (
                if %%a geq 3 (
                    if %%b geq 8 (
                        set PYTHON_CMD=%%i
                        goto :found_python
                    )
                )
            )
        )
    )
)

:found_python
if "%PYTHON_CMD%"=="" (
    echo ❌ Error: Python 3.8 or higher is required
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

echo ✅ Found Python: %PYTHON_CMD%

REM Check if we're in the right directory
if not exist "web_server.py" (
    echo ❌ Error: Please run this script from the MeistroCraft directory
    echo    ^(The directory containing web_server.py^)
    pause
    exit /b 1
)

REM Check if config exists
if not exist "config\config.json" (
    echo ⚠️  Configuration file not found
    echo    Copying template to config\config.json...
    if exist "config\config.template.json" (
        copy "config\config.template.json" "config\config.json" >nul
        echo ✅ Configuration template copied
        echo 📝 Please edit config\config.json and add your API keys
    ) else (
        echo ❌ Error: config.template.json not found
        pause
        exit /b 1
    )
)

REM Create virtual environment if it doesn't exist
if not exist "%VENV_DIR%" (
    echo 📦 Creating virtual environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if !errorlevel! neq 0 (
        echo ❌ Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

REM Upgrade pip
echo 📦 Upgrading pip...
python -m pip install --upgrade pip

REM Install/upgrade requirements
echo 📦 Installing/updating dependencies...
pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo ❌ Error: Failed to install dependencies
    pause
    exit /b 1
)

echo ✅ Dependencies installed successfully

REM Check if all required modules can be imported
echo 🧪 Testing imports...
python -c "import fastapi; import uvicorn; import openai; import websockets; print('✅ All imports successful')"
if !errorlevel! neq 0 (
    echo ❌ Error: Some dependencies failed to import
    pause
    exit /b 1
)

REM Start the web server
echo.
echo 🌐 Starting MeistroCraft IDE Web Server...
echo 📖 Open your browser to: http://localhost:8000
echo 🔧 API docs available at: http://localhost:8000/docs
echo ⏹️  Press Ctrl+C to stop
echo.

REM Start the server
python web_server.py