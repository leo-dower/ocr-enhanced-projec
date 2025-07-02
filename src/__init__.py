"""
OCR Enhanced - Enhanced OCR application with local and cloud processing capabilities.

This package provides a comprehensive OCR solution supporting both local processing
with Tesseract and cloud processing with Mistral AI, including hybrid workflows
and multiple output formats.
"""

__version__ = "2.0.0"
__author__ = "OCR Enhanced Team"
__email__ = "contact@example.com"
__license__ = "MIT"

# Version information for programmatic access
VERSION_INFO = {
    "major": 2,
    "minor": 0,
    "patch": 0,
    "pre_release": None,  # alpha, beta, rc
    "build": None
}

def get_version() -> str:
    """Get the current version string."""
    version = f"{VERSION_INFO['major']}.{VERSION_INFO['minor']}.{VERSION_INFO['patch']}"
    
    if VERSION_INFO['pre_release']:
        version += f"-{VERSION_INFO['pre_release']}"
    
    if VERSION_INFO['build']:
        version += f"+{VERSION_INFO['build']}"
    
    return version

# Verify version consistency
assert __version__ == get_version(), "Version mismatch between __version__ and VERSION_INFO"

# Package metadata
PACKAGE_INFO = {
    "name": "ocr-enhanced",
    "version": __version__,
    "description": "Enhanced OCR application with local and cloud processing capabilities",
    "author": __author__,
    "author_email": __email__,
    "license": __license__,
    "url": "https://github.com/leo-dower/ocr-enhanced-projec",
    "keywords": ["ocr", "tesseract", "mistral", "pdf", "document-processing"],
    "python_requires": ">=3.8"
}

# Import main components for easy access
try:
    from .core.main import OCRApplication
    __all__ = ["OCRApplication", "__version__", "VERSION_INFO", "PACKAGE_INFO", "get_version"]
except ImportError:
    # Handle case where core components are not yet available
    __all__ = ["__version__", "VERSION_INFO", "PACKAGE_INFO", "get_version"]