#!/bin/bash
# macOS build script for OCR Enhanced
# This script builds macOS executables and app bundles

set -e  # Exit on any error

echo "=========================================="
echo "OCR Enhanced - macOS Build Script"
echo "=========================================="

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is not installed"
    echo "Please install Python 3.8+ using Homebrew:"
    echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo "  brew install python"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "ERROR: pyproject.toml not found"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Check Homebrew and system dependencies
echo "Checking system dependencies..."
if ! command -v brew &> /dev/null; then
    echo "WARNING: Homebrew not found"
    echo "Some dependencies may need to be installed manually"
else
    # Check for Tesseract
    if ! command -v tesseract &> /dev/null; then
        echo "WARNING: Tesseract OCR not found"
        echo "Install it with: brew install tesseract"
    fi
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

# Install macOS-specific dependencies
echo "Installing macOS-specific dependencies..."
python -m pip install pyobjc-framework-Cocoa

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
echo "Building macOS executables..."
python build_scripts/build_executable.py --config all

# Code signing (if developer certificate is available)
echo "Checking for code signing certificate..."
if security find-identity -v -p codesigning | grep -q "Developer ID Application"; then
    echo "Developer certificate found. Code signing executables..."
    for app in dist_executable/*.app; do
        if [ -d "$app" ]; then
            echo "Signing $app..."
            codesign --force --sign "Developer ID Application" --deep "$app"
        fi
    done
else
    echo "No Developer ID certificate found. Skipping code signing."
    echo "Users will need to allow unsigned applications in Security preferences."
fi

echo ""
echo "=========================================="
echo "Build completed successfully!"
echo "=========================================="
echo ""
echo "Executables are available in: dist_executable/"
echo ""
echo "Next steps:"
echo "1. Test the applications:"
echo "   - GUI: open dist_executable/OCR-Enhanced-GUI.app"
echo "   - CLI: ./dist_executable/OCR-Enhanced-CLI"
echo "2. Install system dependencies if needed:"
echo "   brew install tesseract poppler"
echo "3. For distribution, consider notarizing the apps with Apple"
echo "4. Distribute the generated TAR.GZ package"
echo ""

# Deactivate virtual environment
deactivate