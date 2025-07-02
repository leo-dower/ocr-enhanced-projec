#!/bin/bash
# Linux build script for OCR Enhanced
# This script builds Linux executables

set -e  # Exit on any error

echo "=========================================="
echo "OCR Enhanced - Linux Build Script"
echo "=========================================="

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is not installed"
    echo "Please install Python 3.8+ using your package manager"
    echo "Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "CentOS/RHEL: sudo dnf install python3 python3-pip"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "ERROR: pyproject.toml not found"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Check system dependencies
echo "Checking system dependencies..."
if ! command -v tesseract &> /dev/null; then
    echo "WARNING: Tesseract OCR not found"
    echo "Install it with: sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-por"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv_build" ]; then
    echo "Creating build virtual environment..."
    python3 -m venv venv_build
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv_build/bin/activate

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install build dependencies
echo "Installing build dependencies..."
python -m pip install pyinstaller build wheel

# Install project dependencies
echo "Installing project dependencies..."
if ! python -m pip install -e .; then
    echo "WARNING: Could not install project in development mode"
    echo "Installing dependencies manually..."
    if [ -f "requirements.txt" ]; then
        python -m pip install -r requirements.txt
    fi
fi

# Create build directories
mkdir -p dist_executable
mkdir -p build_executable

# Build executables
echo "Building Linux executables..."
python build_scripts/build_executable.py --config all

echo ""
echo "=========================================="
echo "Build completed successfully!"
echo "=========================================="
echo ""
echo "Executables are available in: dist_executable/"
echo ""
echo "Next steps:"
echo "1. Test the executables: ./dist_executable/OCR-Enhanced-CLI"
echo "2. Install system dependencies if needed:"
echo "   sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-por poppler-utils"
echo "3. Distribute the generated TAR.GZ package"
echo ""

# Deactivate virtual environment
deactivate