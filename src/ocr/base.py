"""
Base classes and interfaces for OCR engines.

This module defines the common interface that all OCR engines must implement,
allowing for easy extensibility and consistent behavior across different providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import time


@dataclass
class OCRResult:
    """Standardized OCR result structure."""
    
    # Core content
    text: str                           # Extracted text
    confidence: float                   # Overall confidence (0.0 - 1.0)
    pages: List[Dict[str, Any]]        # Per-page results
    
    # Metadata
    processing_time: float             # Time taken in seconds
    engine: str                        # Engine used (tesseract, mistral, etc.)
    language: str                      # Language(s) detected/used
    file_path: Optional[str] = None    # Source file path
    
    # Quality metrics
    word_count: int = 0                # Number of words extracted
    character_count: int = 0           # Number of characters extracted
    
    # Error handling
    success: bool = True               # Whether processing succeeded
    error_message: Optional[str] = None # Error details if failed
    
    def __post_init__(self):
        """Calculate derived fields after initialization."""
        if not self.word_count and self.text:
            self.word_count = len(self.text.split())
        if not self.character_count and self.text:
            self.character_count = len(self.text)


@dataclass
class OCROptions:
    """Configuration options for OCR processing."""
    
    language: str = "eng"              # Language code(s)
    confidence_threshold: float = 0.0  # Minimum confidence to include text
    preprocessing: bool = True         # Apply image preprocessing
    dpi: int = 300                     # DPI for PDF to image conversion
    output_formats: List[str] = None   # Desired output formats
    
    def __post_init__(self):
        """Set default output formats if not specified."""
        if self.output_formats is None:
            self.output_formats = ["text", "json"]


class OCREngine(ABC):
    """
    Abstract base class for OCR engines.
    
    All OCR implementations (Tesseract, Mistral, etc.) must inherit from this class
    and implement the required methods.
    """
    
    def __init__(self, name: str, **kwargs):
        """
        Initialize OCR engine.
        
        Args:
            name: Engine identifier
            **kwargs: Engine-specific configuration
        """
        self.name = name
        self.config = kwargs
        self._is_available = None
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the OCR engine is available and properly configured.
        
        Returns:
            True if engine is ready to use, False otherwise
        """
        pass
    
    @abstractmethod
    def process_image(self, image_path: Union[str, Path], options: OCROptions) -> OCRResult:
        """
        Process a single image file.
        
        Args:
            image_path: Path to image file
            options: Processing options
            
        Returns:
            OCR result
        """
        pass
    
    @abstractmethod
    def process_pdf(self, pdf_path: Union[str, Path], options: OCROptions) -> OCRResult:
        """
        Process a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            options: Processing options
            
        Returns:
            OCR result
        """
        pass
    
    def process_file(self, file_path: Union[str, Path], options: OCROptions = None) -> OCRResult:
        """
        Process any supported file type.
        
        Args:
            file_path: Path to file
            options: Processing options (uses defaults if None)
            
        Returns:
            OCR result
        """
        if options is None:
            options = OCROptions()
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            return OCRResult(
                text="",
                confidence=0.0,
                pages=[],
                processing_time=0.0,
                engine=self.name,
                language=options.language,
                file_path=str(file_path),
                success=False,
                error_message=f"File not found: {file_path}"
            )
        
        start_time = time.time()
        
        try:
            # Determine file type and process accordingly
            suffix = file_path.suffix.lower()
            
            if suffix == '.pdf':
                result = self.process_pdf(file_path, options)
            elif suffix in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
                result = self.process_image(file_path, options)
            else:
                raise ValueError(f"Unsupported file type: {suffix}")
            
            # Ensure processing time is set
            if result.processing_time == 0.0:
                result.processing_time = time.time() - start_time
            
            # Set file path if not already set
            if result.file_path is None:
                result.file_path = str(file_path)
            
            return result
            
        except Exception as e:
            return OCRResult(
                text="",
                confidence=0.0,
                pages=[],
                processing_time=time.time() - start_time,
                engine=self.name,
                language=options.language,
                file_path=str(file_path),
                success=False,
                error_message=str(e)
            )
    
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes.
        
        Returns:
            List of language codes (e.g., ['eng', 'por', 'spa'])
        """
        return ['eng']  # Default implementation
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get engine information and status.
        
        Returns:
            Dictionary with engine details
        """
        return {
            'name': self.name,
            'available': self.is_available(),
            'supported_languages': self.get_supported_languages(),
            'config': self.config
        }
    
    def __str__(self) -> str:
        """String representation of the engine."""
        return f"{self.name} OCR Engine ({'available' if self.is_available() else 'unavailable'})"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"OCREngine(name='{self.name}', available={self.is_available()})"


class OCREngineManager:
    """
    Manages multiple OCR engines and provides unified access.
    
    This class handles engine selection, fallback logic, and result aggregation.
    """
    
    def __init__(self):
        """Initialize engine manager."""
        self.engines: Dict[str, OCREngine] = {}
        self.default_engine: Optional[str] = None
    
    def register_engine(self, engine: OCREngine, make_default: bool = False):
        """
        Register an OCR engine.
        
        Args:
            engine: OCR engine instance
            make_default: Whether to make this the default engine
        """
        self.engines[engine.name] = engine
        
        if make_default or self.default_engine is None:
            self.default_engine = engine.name
    
    def get_engine(self, name: str = None) -> Optional[OCREngine]:
        """
        Get an OCR engine by name.
        
        Args:
            name: Engine name (uses default if None)
            
        Returns:
            OCR engine instance or None if not found
        """
        if name is None:
            name = self.default_engine
        
        return self.engines.get(name)
    
    def get_available_engines(self) -> List[str]:
        """
        Get list of available engine names.
        
        Returns:
            List of engine names that are currently available
        """
        return [name for name, engine in self.engines.items() if engine.is_available()]
    
    def process_with_fallback(self, file_path: Union[str, Path], 
                            engine_order: List[str] = None,
                            options: OCROptions = None) -> OCRResult:
        """
        Process file with automatic fallback between engines.
        
        Args:
            file_path: Path to file to process
            engine_order: Order of engines to try (uses all available if None)
            options: Processing options
            
        Returns:
            OCR result from first successful engine
        """
        if engine_order is None:
            engine_order = self.get_available_engines()
        
        last_error = None
        
        for engine_name in engine_order:
            engine = self.get_engine(engine_name)
            if engine and engine.is_available():
                result = engine.process_file(file_path, options)
                
                if result.success:
                    return result
                else:
                    last_error = result.error_message
        
        # If all engines failed, return failure result
        return OCRResult(
            text="",
            confidence=0.0,
            pages=[],
            processing_time=0.0,
            engine="none",
            language=options.language if options else "unknown",
            file_path=str(file_path),
            success=False,
            error_message=f"All engines failed. Last error: {last_error}"
        )