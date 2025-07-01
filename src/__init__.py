"""
Enhanced OCR Application

A comprehensive OCR solution supporting both local (Tesseract) and cloud (Mistral AI) processing,
with dynamic folder selection, searchable PDF generation, and hybrid processing modes.
"""

__version__ = "2.0.0"
__author__ = "OCR Enhanced Team"
__email__ = "contact@example.com"

from .core.main import OCRApplication

__all__ = ["OCRApplication"]