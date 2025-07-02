# 🔍 OCR Enhanced - Advanced Document Processing

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A comprehensive OCR solution that combines local (Tesseract) and cloud (Mistral AI) processing with dynamic folder selection, searchable PDF generation, and hybrid processing modes.

## ✨ Features

### 🎯 **Core Functionality**
- **Hybrid OCR Processing**: Try local first, fallback to cloud if needed
- **Multiple Engines**: Tesseract (local) + Mistral AI (cloud)
- **Searchable PDFs**: Generate PDFs with invisible text layer
- **Batch Processing**: Handle multiple files efficiently
- **Dynamic Folders**: Choose input/output directories via GUI

### 🔧 **Processing Modes**
- **🔄 Hybrid**: Local first, cloud fallback (recommended)
- **☁️ Cloud Only**: Mistral AI processing only
- **💻 Local Only**: Tesseract processing only  
- **🔒 Privacy**: Force local processing (no data sent to cloud)

### 🎨 **User Experience**
- **Modern GUI**: Intuitive Tkinter interface with drag & drop
- **Real-time Progress**: Detailed progress tracking and logging
- **Folder Selection**: Choose custom input/output directories
- **Multi-format Output**: JSON, Markdown, and searchable PDF

## 🚀 Quick Start

### Installation

```bash
# Install from PyPI (recommended)
pip install ocr-enhanced

# Or install from source
git clone https://github.com/leo-dower/ocr-enhanced-projec.git
cd ocr-enhanced-projec
pip install -e .
```

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt install tesseract-ocr tesseract-ocr-por tesseract-ocr-eng poppler-utils
```

**Windows:**
- Download Tesseract from [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
- Install Poppler from [conda-forge](https://anaconda.org/conda-forge/poppler)

**macOS:**
```bash
brew install tesseract poppler
```

### Usage

**GUI Application:**
```bash
ocr-enhanced-gui
```

**Command Line:**
```bash
ocr-cli --input /path/to/pdfs --output /path/to/results
```

**Python API:**
```python
from src.core import OCRProcessor

processor = OCRProcessor(mode='hybrid')
result = processor.process_file('document.pdf')
```

## 📁 Project Structure

```
ocr-enhanced/
├── src/                    # Source code
│   ├── core/              # Core processing logic
│   ├── gui/               # User interface
│   ├── ocr/               # OCR engines
│   └── utils/             # Utilities
├── tests/                 # Test suite
├── docs/                  # Documentation
├── examples/              # Usage examples
└── requirements/          # Dependencies
```

## 🔧 Configuration

### Environment Variables
```bash
# API Configuration
MISTRAL_API_KEY=your_api_key_here

# Default Folders
OCR_INPUT_PATH=/path/to/input
OCR_OUTPUT_PATH=/path/to/output

# Processing Settings
OCR_MODE=hybrid
OCR_LANGUAGE=por+eng
```

### Configuration File
Create `~/.ocr-enhanced.json`:
```json
{
  "default_mode": "hybrid",
  "tesseract_path": "/usr/bin/tesseract",
  "default_language": "por+eng",
  "max_pages_per_batch": 200,
  "confidence_threshold": 0.75
}
```

## 🧪 Development

### Setup Development Environment
```bash
# Clone repository
git clone https://github.com/leo-dower/ocr-enhanced-projec.git
cd ocr-enhanced-projec

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Run Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test types
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m "not slow"    # Skip slow tests
```

### Code Quality
```bash
# Format code
black src tests

# Sort imports
isort src tests

# Lint code
flake8 src tests

# Type checking
mypy src

# Security check
bandit -r src
```

## 📊 Performance

| Mode | Speed | Accuracy | Privacy | Cost |
|------|-------|----------|---------|------|
| Local | Fast | Good | 100% | Free |
| Cloud | Medium | Excellent | Depends | Paid |
| Hybrid | Optimal | Best | Balanced | Mixed |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for your changes
5. Ensure all tests pass (`pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for local processing
- [Mistral AI](https://mistral.ai/) for cloud OCR capabilities
- [PyMuPDF](https://pymupdf.readthedocs.io/) for PDF manipulation

## 📞 Support

- 📖 [Documentation](https://github.com/leo-dower/ocr-enhanced-projec#readme)
- 🐛 [Issue Tracker](https://github.com/leo-dower/ocr-enhanced-projec/issues)
- 💬 [Discussions](https://github.com/leo-dower/ocr-enhanced-projec/discussions)

---

Made with ❤️ by the OCR Enhanced Team - Leo-dower and claudecode =)      
