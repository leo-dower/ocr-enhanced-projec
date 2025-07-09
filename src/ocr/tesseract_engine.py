"""
Tesseract OCR Engine.

This module provides OCR capabilities using Tesseract OCR for local processing.
It supports both image and PDF files with comprehensive language support.
"""

import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import tempfile
import shutil

try:
    import pytesseract
    from PIL import Image
    from pdf2image import convert_from_path
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    pytesseract = None
    Image = None
    convert_from_path = None

from .base import OCREngine, OCRResult, OCROptions
from ..utils.logger import get_logger


class TesseractEngine(OCREngine):
    """Tesseract OCR Engine for local processing."""
    
    def __init__(self, tesseract_cmd: Optional[str] = None, **kwargs):
        """
        Initialize Tesseract OCR engine.
        
        Args:
            tesseract_cmd: Path to tesseract executable (auto-detected if None)
            **kwargs: Additional configuration options
        """
        super().__init__("tesseract_local", **kwargs)
        self.tesseract_cmd = tesseract_cmd
        self.logger = get_logger("tesseract_ocr")
        
        # Configuration options
        self.confidence_threshold = kwargs.get("confidence_threshold", 0.0)
        self.dpi = kwargs.get("dpi", 300)
        self.preprocessing = kwargs.get("preprocessing", True)
        self.timeout = kwargs.get("timeout", 300)
        
        # Initialize Tesseract
        if TESSERACT_AVAILABLE:
            self._setup_tesseract()
    
    def _setup_tesseract(self):
        """Setup Tesseract executable path."""
        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        else:
            # Try to find Tesseract automatically
            self._find_tesseract_executable()
    
    def _find_tesseract_executable(self):
        """Find Tesseract executable automatically."""
        common_paths = [
            '/usr/bin/tesseract',
            '/usr/local/bin/tesseract',
            '/opt/homebrew/bin/tesseract',  # macOS Homebrew
            'C:\\Program Files\\Tesseract-OCR\\tesseract.exe',
            'C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe',
            'tesseract'  # Assume it's in PATH
        ]
        
        for path in common_paths:
            if os.path.exists(path) or shutil.which(path):
                pytesseract.pytesseract.tesseract_cmd = path
                self.tesseract_cmd = path
                self.logger.info(f"Found Tesseract at: {path}")
                return
        
        self.logger.warning("Tesseract executable not found in common locations")
    
    def is_available(self) -> bool:
        """Check if Tesseract is available."""
        if not TESSERACT_AVAILABLE:
            self.logger.warning("Tesseract libraries not installed")
            return False
        
        try:
            # Test Tesseract by getting version
            version = pytesseract.get_tesseract_version()
            self.logger.info(f"Tesseract version: {version}")
            return True
        except Exception as e:
            self.logger.error(f"Tesseract not available: {e}")
            return False
    
    def process_image(self, image_path: Union[str, Path], options: OCROptions) -> OCRResult:
        """Process a single image using Tesseract."""
        start_time = time.time()
        image_path = Path(image_path)
        
        if not self.is_available():
            return self._create_error_result(
                image_path, options, "Tesseract not available", start_time
            )
        
        try:
            # Load image
            if not Image:
                raise ImportError("PIL not available")
            image = Image.open(image_path)
            
            # Preprocess image if enabled
            if self.preprocessing:
                image = self._preprocess_image(image)
            
            # Extract text with confidence data
            text_data = pytesseract.image_to_data(
                image,
                lang=self._convert_language_code(options.language),
                config=self._get_tesseract_config(),
                output_type=pytesseract.Output.DICT
            )
            
            # Extract plain text
            text = pytesseract.image_to_string(
                image,
                lang=self._convert_language_code(options.language),
                config=self._get_tesseract_config()
            )
            
            # Process results
            confidence, words_data = self._process_text_data(text_data, options)
            
            pages_data = [{
                'page_number': 1,
                'text': text.strip(),
                'words': words_data,
                'confidence': confidence,
                'language': options.language
            }]
            
            return OCRResult(
                text=text.strip(),
                confidence=confidence,
                pages=pages_data,
                processing_time=time.time() - start_time,
                engine=self.name,
                language=options.language,
                file_path=str(image_path),
                word_count=len(text.split()),
                character_count=len(text),
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Error processing image {image_path}: {e}")
            return self._create_error_result(image_path, options, str(e), start_time)
    
    def process_pdf(self, pdf_path: Union[str, Path], options: OCROptions) -> OCRResult:
        """Process a PDF using Tesseract."""
        start_time = time.time()
        pdf_path = Path(pdf_path)
        
        if not self.is_available():
            return self._create_error_result(
                pdf_path, options, "Tesseract not available", start_time
            )
        
        try:
            # Convert PDF to images
            if not convert_from_path:
                raise ImportError("pdf2image not available")
            self.logger.info(f"Converting PDF to images: {pdf_path.name}")
            images = convert_from_path(
                str(pdf_path),
                dpi=options.dpi,
                first_page=None,
                last_page=None,
                fmt='PNG'
            )
            
            if not images:
                return self._create_error_result(
                    pdf_path, options, "Failed to convert PDF to images", start_time
                )
            
            # Process each page
            all_text = []
            all_pages = []
            total_confidence = 0.0
            total_words = 0
            
            for page_num, image in enumerate(images, 1):
                try:
                    # Preprocess image if enabled
                    if self.preprocessing:
                        image = self._preprocess_image(image)
                    
                    # Extract text with confidence data
                    text_data = pytesseract.image_to_data(
                        image,
                        lang=self._convert_language_code(options.language),
                        config=self._get_tesseract_config(),
                        output_type=pytesseract.Output.DICT
                    )
                    
                    # Extract plain text
                    page_text = pytesseract.image_to_string(
                        image,
                        lang=self._convert_language_code(options.language),
                        config=self._get_tesseract_config()
                    )
                    
                    # Process results
                    confidence, words_data = self._process_text_data(text_data, options)
                    
                    if page_text.strip():
                        all_text.append(page_text.strip())
                        
                        page_data = {
                            'page_number': page_num,
                            'text': page_text.strip(),
                            'words': words_data,
                            'confidence': confidence,
                            'language': options.language
                        }
                        all_pages.append(page_data)
                        
                        total_confidence += confidence
                        total_words += len(page_text.split())
                    
                    self.logger.info(f"Processed page {page_num}: {len(page_text.strip())} chars, confidence: {confidence:.2f}")
                    
                except Exception as e:
                    self.logger.warning(f"Error processing page {page_num}: {e}")
                    # Add empty page to maintain page numbering
                    all_pages.append({
                        'page_number': page_num,
                        'text': '',
                        'words': [],
                        'confidence': 0.0,
                        'language': options.language,
                        'error': str(e)
                    })
            
            if not all_text:
                return self._create_error_result(
                    pdf_path, options, "No text could be extracted from any page", start_time
                )
            
            full_text = '\n\n'.join(all_text)
            avg_confidence = total_confidence / len(all_pages) if all_pages else 0.0
            
            return OCRResult(
                text=full_text,
                confidence=avg_confidence,
                pages=all_pages,
                processing_time=time.time() - start_time,
                engine=self.name,
                language=options.language,
                file_path=str(pdf_path),
                word_count=total_words,
                character_count=len(full_text),
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Error processing PDF {pdf_path}: {e}")
            return self._create_error_result(pdf_path, options, str(e), start_time)
    
    def _preprocess_image(self, image):
        """Apply image preprocessing to improve OCR accuracy."""
        if not TESSERACT_AVAILABLE or not Image:
            return image
            
        try:
            # Convert to grayscale if not already
            if image.mode != 'L':
                image = image.convert('L')
            
            # Apply basic enhancements
            from PIL import ImageEnhance, ImageFilter
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)
            
            # Apply noise reduction
            image = image.filter(ImageFilter.MedianFilter())
            
            return image
        except Exception as e:
            self.logger.warning(f"Image preprocessing failed: {e}")
            return image
    
    def _process_text_data(self, text_data: Dict, options: OCROptions) -> tuple:
        """Process Tesseract text data to extract confidence and word information."""
        try:
            confidences = []
            words_data = []
            
            for i, word_text in enumerate(text_data['text']):
                if word_text.strip():
                    conf = int(text_data['conf'][i])
                    if conf > 0:  # Valid confidence
                        confidences.append(conf)
                        
                        # Only include words above threshold
                        if conf >= options.confidence_threshold * 100:
                            words_data.append({
                                'text': word_text,
                                'confidence': conf / 100.0,
                                'bounding_box': [
                                    text_data['left'][i],
                                    text_data['top'][i],
                                    text_data['left'][i] + text_data['width'][i],
                                    text_data['top'][i] + text_data['height'][i]
                                ]
                            })
            
            # Calculate average confidence
            avg_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
            
            return avg_confidence, words_data
            
        except Exception as e:
            self.logger.error(f"Error processing text data: {e}")
            return 0.0, []
    
    def _get_tesseract_config(self) -> str:
        """Get Tesseract configuration string."""
        config_parts = []
        
        # Page segmentation mode (6 = single uniform block)
        config_parts.append("--psm 6")
        
        # OCR engine mode (3 = default)
        config_parts.append("--oem 3")
        
        # Additional configurations
        config_parts.append("-c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ")
        
        return " ".join(config_parts)
    
    def _convert_language_code(self, language: str) -> str:
        """Convert language code to Tesseract format."""
        language_map = {
            'eng': 'eng',
            'por': 'por',
            'spa': 'spa',
            'fra': 'fra',
            'deu': 'deu',
            'ita': 'ita',
            'rus': 'rus',
            'chi_sim': 'chi_sim',
            'chi_tra': 'chi_tra',
            'jpn': 'jpn',
            'kor': 'kor',
            'ara': 'ara',
            'hin': 'hin'
        }
        
        # Handle compound language codes (e.g., "por+eng")
        if '+' in language:
            languages = language.split('+')
            mapped_langs = [language_map.get(lang, 'eng') for lang in languages]
            return '+'.join(mapped_langs)
        
        return language_map.get(language, 'eng')
    
    def _create_error_result(self, file_path: Path, options: OCROptions,
                           error_message: str, start_time: float) -> OCRResult:
        """Create an error result."""
        return OCRResult(
            text="",
            confidence=0.0,
            pages=[],
            processing_time=time.time() - start_time,
            engine=self.name,
            language=options.language,
            file_path=str(file_path),
            success=False,
            error_message=error_message
        )
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        if not self.is_available():
            return []
        
        try:
            # Get installed languages from Tesseract
            langs = pytesseract.get_languages()
            
            # Map Tesseract language codes to our standard codes
            language_map = {
                'eng': 'eng',
                'por': 'por',
                'spa': 'spa',
                'fra': 'fra',
                'deu': 'deu',
                'ita': 'ita',
                'rus': 'rus',
                'chi_sim': 'chi_sim',
                'chi_tra': 'chi_tra',
                'jpn': 'jpn',
                'kor': 'kor',
                'ara': 'ara',
                'hin': 'hin'
            }
            
            # Return intersection of available and mapped languages
            return [code for code, tesseract_code in language_map.items() if tesseract_code in langs]
            
        except Exception as e:
            self.logger.error(f"Error getting supported languages: {e}")
            return ['eng']  # Default fallback
    
    def get_info(self) -> Dict[str, Any]:
        """Get engine information."""
        info = super().get_info()
        info.update({
            'tesseract_cmd': self.tesseract_cmd,
            'confidence_threshold': self.confidence_threshold,
            'dpi': self.dpi,
            'preprocessing': self.preprocessing,
            'timeout': self.timeout,
            'tesseract_available': TESSERACT_AVAILABLE
        })
        
        if self.is_available():
            try:
                info['tesseract_version'] = str(pytesseract.get_tesseract_version())
                info['installed_languages'] = pytesseract.get_languages()
            except Exception as e:
                info['version_error'] = str(e)
        
        return info


def create_tesseract_engine(tesseract_cmd: Optional[str] = None, **kwargs) -> TesseractEngine:
    """
    Factory function to create Tesseract OCR engine.
    
    Args:
        tesseract_cmd: Path to tesseract executable
        **kwargs: Additional configuration options
        
    Returns:
        Configured Tesseract OCR engine
    """
    return TesseractEngine(tesseract_cmd, **kwargs)


# Configuration helper
def get_tesseract_config_template() -> Dict[str, Any]:
    """Get configuration template for Tesseract."""
    return {
        'tesseract_cmd': None,  # Auto-detect
        'confidence_threshold': 0.0,
        'dpi': 300,
        'preprocessing': True,
        'timeout': 300
    }


# Example usage
if __name__ == "__main__":
    # Example configuration
    config = get_tesseract_config_template()
    
    print("Tesseract OCR Engine")
    print("=" * 30)
    print(f"Libraries Available: {TESSERACT_AVAILABLE}")
    
    if TESSERACT_AVAILABLE:
        # Create engine
        engine = create_tesseract_engine(**config)
        
        print(f"Engine Available: {engine.is_available()}")
        print(f"Supported Languages: {engine.get_supported_languages()}")
        print(f"Engine Info: {engine.get_info()}")
    else:
        print("Install Tesseract with: pip install pytesseract pillow pdf2image")
        print("And install Tesseract OCR software from: https://github.com/tesseract-ocr/tesseract")