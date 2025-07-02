@echo off
REM Windows build script for OCR Enhanced
REM This script builds Windows executables (.exe files)

echo ==========================================
echo OCR Enhanced - Windows Build Script
echo ==========================================

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and add it to PATH
    pause
    exit /b 1
)

REM Check if we're in the right directory
if not exist "pyproject.toml" (
    echo ERROR: pyproject.toml not found
    echo Please run this script from the project root directory
    pause
    exit /b 1
)

REM Install build dependencies
echo Installing build dependencies...
python -m pip install --upgrade pip
python -m pip install pyinstaller build wheel

REM Install project dependencies
echo Installing project dependencies...
python -m pip install -e .
if errorlevel 1 (
    echo WARNING: Could not install project in development mode
    echo Installing dependencies manually...
    python -m pip install -r requirements.txt
)

REM Create build directory
if not exist "dist_executable" mkdir dist_executable
if not exist "build_executable" mkdir build_executable

REM Build executables
echo Building Windows executables...
python build_scripts/build_executable.py --config all

if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Build completed successfully!
echo ==========================================
echo.
echo Executables are available in: dist_executable/
echo.
echo Next steps:
echo 1. Test the executables
echo 2. Install Tesseract OCR if not already installed
echo 3. Distribute the generated ZIP package
echo.
pause