"""
Core OCR processing components.

This module contains the main application logic, configuration management,
and core processing orchestration.
"""

from .config import Config
from .processor import OCRProcessor

__all__ = ["Config", "OCRProcessor"]