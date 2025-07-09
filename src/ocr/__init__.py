"""
OCR Engine implementations.

This module contains different OCR engine implementations including:
- Tesseract (local)
- Mistral AI (cloud)
- Azure Computer Vision (cloud)
- Google Cloud Vision (cloud)
- Multi-engine system with intelligent fallback
- Hybrid processing logic
"""

from .base import OCREngine, OCRResult, OCROptions, OCREngineManager

# Core engines
try:
    from .tesseract_engine import TesseractEngine
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from .mistral_engine import MistralEngine
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False

try:
    from .hybrid_engine import HybridEngine
    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False

# Cloud engines
try:
    from .azure_vision import AzureVisionEngine, create_azure_vision_engine
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

try:
    from .google_vision import GoogleVisionEngine, create_google_vision_engine
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

# Multi-engine system
from .multi_engine import (
    MultiEngineOCR, EnginePreferences, EngineQualityMetrics,
    create_multi_engine_ocr, setup_standard_engines
)

# Build __all__ dynamically based on available engines
__all__ = [
    "OCREngine", "OCRResult", "OCROptions", "OCREngineManager",
    "MultiEngineOCR", "EnginePreferences", "EngineQualityMetrics",
    "create_multi_engine_ocr", "setup_standard_engines"
]

if TESSERACT_AVAILABLE:
    __all__.append("TesseractEngine")

if MISTRAL_AVAILABLE:
    __all__.append("MistralEngine")

if HYBRID_AVAILABLE:
    __all__.append("HybridEngine")

if AZURE_AVAILABLE:
    __all__.extend(["AzureVisionEngine", "create_azure_vision_engine"])

if GOOGLE_AVAILABLE:
    __all__.extend(["GoogleVisionEngine", "create_google_vision_engine"])


def get_available_engines() -> dict:
    """Get information about available OCR engines."""
    return {
        "tesseract": TESSERACT_AVAILABLE,
        "mistral": MISTRAL_AVAILABLE,
        "hybrid": HYBRID_AVAILABLE,
        "azure_vision": AZURE_AVAILABLE,
        "google_vision": GOOGLE_AVAILABLE
    }


def create_engine_manager_with_all_engines(**configs) -> OCREngineManager:
    """
    Create an OCR engine manager with all available engines.
    
    Args:
        **configs: Configuration dictionaries for each engine
                  (tesseract_config, mistral_config, azure_config, google_config)
    
    Returns:
        Configured OCR engine manager
    """
    manager = OCREngineManager()
    
    # Add Tesseract if available
    if TESSERACT_AVAILABLE and 'tesseract_config' in configs:
        tesseract = TesseractEngine(**configs['tesseract_config'])
        manager.register_engine(tesseract, make_default=True)
    
    # Add Mistral if available
    if MISTRAL_AVAILABLE and 'mistral_config' in configs:
        mistral = MistralEngine(**configs['mistral_config'])
        manager.register_engine(mistral)
    
    # Add Azure if available
    if AZURE_AVAILABLE and 'azure_config' in configs:
        azure = create_azure_vision_engine(**configs['azure_config'])
        manager.register_engine(azure)
    
    # Add Google if available
    if GOOGLE_AVAILABLE and 'google_config' in configs:
        google = create_google_vision_engine(**configs['google_config'])
        manager.register_engine(google)
    
    return manager