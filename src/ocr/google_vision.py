"""
Google Cloud Vision OCR Engine.

This module provides OCR capabilities using Google Cloud Vision API.
It supports both text detection and document text detection.
"""

import io
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import base64

try:
    # Google Cloud Vision
    from google.cloud import vision
    from google.oauth2 import service_account
    GOOGLE_VISION_AVAILABLE = True
except ImportError:
    GOOGLE_VISION_AVAILABLE = False
    vision = None
    service_account = None

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

from .base import OCREngine, OCRResult, OCROptions
from ..utils.logger import get_logger


class GoogleVisionEngine(OCREngine):
    """Google Cloud Vision OCR Engine."""
    
    def __init__(self, credentials_path: Optional[str] = None, 
                 credentials_dict: Optional[Dict] = None, **kwargs):
        """
        Initialize Google Vision OCR engine.
        
        Args:
            credentials_path: Path to Google Cloud service account JSON file
            credentials_dict: Service account credentials as dictionary
            **kwargs: Additional configuration options
        """
        super().__init__("google_vision", **kwargs)
        self.credentials_path = credentials_path
        self.credentials_dict = credentials_dict
        self.logger = get_logger("google_vision_ocr")
        
        # Configuration options
        self.use_document_text = kwargs.get("use_document_text", True)  # Use document text detection
        self.language_hints = kwargs.get("language_hints", [])
        self.timeout = kwargs.get("timeout", 60)
        
        # Initialize client
        self.client = None
        if GOOGLE_VISION_AVAILABLE:
            try:
                if credentials_dict:
                    # Use credentials dictionary
                    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
                    self.client = vision.ImageAnnotatorClient(credentials=credentials)
                elif credentials_path and Path(credentials_path).exists():
                    # Use credentials file
                    credentials = service_account.Credentials.from_service_account_file(credentials_path)
                    self.client = vision.ImageAnnotatorClient(credentials=credentials)
                else:
                    # Use default credentials (from environment)
                    self.client = vision.ImageAnnotatorClient()
                
                self.logger.info("Google Cloud Vision client initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize Google Vision client: {e}")
                self.client = None
    
    def is_available(self) -> bool:
        """Check if Google Cloud Vision is available."""
        if not GOOGLE_VISION_AVAILABLE:
            self.logger.warning("Google Cloud Vision library not installed")
            return False
            
        if not self.client:
            self.logger.warning("Google Cloud Vision client not initialized")
            return False
            
        try:
            # Test the connection with a simple call
            # Create a tiny test image
            test_image = vision.Image(content=self._create_test_image())
            self.client.text_detection(image=test_image)
            return True
        except Exception as e:
            self.logger.error(f"Google Cloud Vision not available: {e}")
            return False
    
    def process_image(self, image_path: Union[str, Path], options: OCROptions) -> OCRResult:
        """Process a single image using Google Cloud Vision."""
        start_time = time.time()
        image_path = Path(image_path)
        
        if not self.is_available():
            return self._create_error_result(
                image_path, options, "Google Cloud Vision not available", start_time
            )
        
        try:
            # Read image file
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            return self._process_image_content(content, image_path, options, start_time)
                
        except Exception as e:
            self.logger.error(f"Error processing image {image_path}: {e}")
            return self._create_error_result(image_path, options, str(e), start_time)
    
    def process_pdf(self, pdf_path: Union[str, Path], options: OCROptions) -> OCRResult:
        """Process a PDF using Google Cloud Vision."""
        start_time = time.time()
        pdf_path = Path(pdf_path)
        
        if not self.is_available():
            return self._create_error_result(
                pdf_path, options, "Google Cloud Vision not available", start_time
            )
        
        try:
            # For PDFs, we need to convert to images and process each page
            return self._process_pdf_as_images(pdf_path, options, start_time)
                
        except Exception as e:
            self.logger.error(f"Error processing PDF {pdf_path}: {e}")
            return self._create_error_result(pdf_path, options, str(e), start_time)
    
    def _process_image_content(self, content: bytes, file_path: Path,
                              options: OCROptions, start_time: float) -> OCRResult:
        """Process image content using Google Cloud Vision."""
        try:
            # Create Vision API image object
            image = vision.Image(content=content)
            
            # Configure image context
            image_context = vision.ImageContext()
            if self.language_hints or options.language:
                # Convert language codes to Google format
                languages = self._convert_language_codes(options.language)
                image_context.language_hints = languages
            
            if self.use_document_text:
                # Use document text detection (better for documents)
                response = self.client.document_text_detection(
                    image=image,
                    image_context=image_context,
                    timeout=self.timeout
                )
                return self._parse_document_text_response(response, file_path, options, start_time)
            else:
                # Use regular text detection (better for natural images)
                response = self.client.text_detection(
                    image=image,
                    image_context=image_context,
                    timeout=self.timeout
                )
                return self._parse_text_response(response, file_path, options, start_time)
                
        except Exception as e:
            self.logger.error(f"Google Vision processing failed: {e}")
            return self._create_error_result(file_path, options, str(e), start_time)
    
    def _parse_document_text_response(self, response, file_path: Path,
                                    options: OCROptions, start_time: float) -> OCRResult:
        """Parse document text detection response."""
        try:
            # Check for errors
            if response.error.message:
                return self._create_error_result(
                    file_path, options, response.error.message, start_time
                )
            
            document = response.full_text_annotation
            if not document:
                return self._create_error_result(
                    file_path, options, "No text detected", start_time
                )
            
            # Extract full text
            full_text = document.text
            
            # Parse pages
            pages_data = []
            total_confidence = 0.0
            word_count = 0
            
            for page in document.pages:
                page_words = []
                page_text_blocks = []
                
                for block in page.blocks:
                    block_text = []
                    
                    for paragraph in block.paragraphs:
                        paragraph_text = []
                        
                        for word in paragraph.words:
                            # Extract word text
                            word_text = ''.join([symbol.text for symbol in word.symbols])
                            
                            # Calculate word confidence
                            word_confidence = word.confidence if hasattr(word, 'confidence') else 0.9
                            
                            page_words.append({
                                'text': word_text,
                                'confidence': word_confidence,
                                'bounding_box': self._extract_bounding_box(word.bounding_box)
                            })
                            
                            paragraph_text.append(word_text)
                            total_confidence += word_confidence
                            word_count += 1
                        
                        block_text.append(' '.join(paragraph_text))
                    
                    page_text_blocks.append('\n'.join(block_text))
                
                page_text = '\n\n'.join(page_text_blocks)
                
                pages_data.append({
                    'page_number': len(pages_data) + 1,
                    'text': page_text,
                    'words': page_words,
                    'blocks': len(page.blocks),
                    'language': self._detect_language(page)
                })
            
            avg_confidence = total_confidence / word_count if word_count > 0 else 0.0
            
            return OCRResult(
                text=full_text,
                confidence=avg_confidence,
                pages=pages_data,
                processing_time=time.time() - start_time,
                engine=self.name,
                language=options.language,
                file_path=str(file_path),
                word_count=word_count,
                character_count=len(full_text),
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing document text response: {e}")
            return self._create_error_result(file_path, options, str(e), start_time)
    
    def _parse_text_response(self, response, file_path: Path,
                           options: OCROptions, start_time: float) -> OCRResult:
        """Parse regular text detection response."""
        try:
            # Check for errors
            if response.error.message:
                return self._create_error_result(
                    file_path, options, response.error.message, start_time
                )
            
            annotations = response.text_annotations
            if not annotations:
                return self._create_error_result(
                    file_path, options, "No text detected", start_time
                )
            
            # First annotation contains full text
            full_text = annotations[0].description
            
            # Extract individual word data from remaining annotations
            words_data = []
            for annotation in annotations[1:]:  # Skip first (full text)
                words_data.append({
                    'text': annotation.description,
                    'confidence': 0.9,  # Google doesn't provide confidence for basic text detection
                    'bounding_box': self._extract_bounding_box(annotation.bounding_poly)
                })
            
            pages_data = [{
                'page_number': 1,
                'text': full_text,
                'words': words_data,
                'blocks': 1,
                'language': options.language
            }]
            
            return OCRResult(
                text=full_text,
                confidence=0.9,  # Default confidence for text detection
                pages=pages_data,
                processing_time=time.time() - start_time,
                engine=self.name,
                language=options.language,
                file_path=str(file_path),
                word_count=len(full_text.split()),
                character_count=len(full_text),
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing text response: {e}")
            return self._create_error_result(file_path, options, str(e), start_time)
    
    def _process_pdf_as_images(self, pdf_path: Path, options: OCROptions, start_time: float) -> OCRResult:
        """Convert PDF to images and process each page."""
        if not PILLOW_AVAILABLE:
            return self._create_error_result(
                pdf_path, options, "Pillow not available for PDF processing", start_time
            )
        
        try:
            from pdf2image import convert_from_path
            
            # Convert PDF to images
            images = convert_from_path(str(pdf_path), dpi=options.dpi)
            
            all_text = []
            all_pages = []
            total_confidence = 0.0
            total_words = 0
            
            for page_num, image in enumerate(images, 1):
                # Convert PIL image to bytes
                img_buffer = io.BytesIO()
                image.save(img_buffer, format='PNG')
                img_content = img_buffer.getvalue()
                
                # Process page
                page_result = self._process_image_content(
                    img_content, 
                    pdf_path, 
                    options, 
                    start_time
                )
                
                if page_result.success:
                    all_text.append(page_result.text)
                    
                    # Update page number in page data
                    page_data = page_result.pages[0].copy()
                    page_data['page_number'] = page_num
                    all_pages.append(page_data)
                    
                    total_confidence += page_result.confidence
                    total_words += page_result.word_count
                else:
                    self.logger.warning(f"Failed to process page {page_num}: {page_result.error_message}")
            
            if not all_text:
                return self._create_error_result(
                    pdf_path, options, "No pages could be processed", start_time
                )
            
            full_text = '\n\n'.join(all_text)
            avg_confidence = total_confidence / len(all_text) if all_text else 0.0
            
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
            self.logger.error(f"PDF to images processing failed: {e}")
            return self._create_error_result(pdf_path, options, str(e), start_time)
    
    def _extract_bounding_box(self, bounding_poly):
        """Extract bounding box coordinates."""
        vertices = bounding_poly.vertices
        return [
            [vertex.x, vertex.y] for vertex in vertices
        ]
    
    def _detect_language(self, page):
        """Detect language from page data."""
        # Google Vision doesn't always provide language detection
        # You could implement language detection based on text content
        return "unknown"
    
    def _convert_language_codes(self, language: str) -> List[str]:
        """Convert language codes to Google format."""
        language_map = {
            'eng': 'en',
            'por': 'pt',
            'spa': 'es',
            'fra': 'fr',
            'deu': 'de',
            'ita': 'it',
            'rus': 'ru',
            'chi_sim': 'zh-CN',
            'chi_tra': 'zh-TW',
            'jpn': 'ja',
            'kor': 'ko',
            'ara': 'ar',
            'hin': 'hi'
        }
        
        # Handle compound language codes
        if '+' in language:
            languages = language.split('+')
            return [language_map.get(lang, 'en') for lang in languages]
        
        return [language_map.get(language, 'en')]
    
    def _create_test_image(self) -> bytes:
        """Create a minimal test image for connection testing."""
        # Create a 1x1 pixel white PNG image
        return base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jX2j3wAAAABJRU5ErkJggg=='
        )
    
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
        return [
            'eng', 'por', 'spa', 'fra', 'deu', 'ita', 'rus',
            'chi_sim', 'chi_tra', 'jpn', 'kor', 'ara', 'hin',
            'tha', 'vie', 'nld', 'swe', 'nor', 'dan', 'fin'
        ]
    
    def get_info(self) -> Dict[str, Any]:
        """Get engine information."""
        info = super().get_info()
        info.update({
            'credentials_configured': bool(self.credentials_path or self.credentials_dict),
            'use_document_text': self.use_document_text,
            'language_hints': self.language_hints,
            'timeout': self.timeout,
            'google_vision_available': GOOGLE_VISION_AVAILABLE,
            'pillow_available': PILLOW_AVAILABLE
        })
        return info


def create_google_vision_engine(credentials_path: Optional[str] = None,
                               credentials_dict: Optional[Dict] = None,
                               **kwargs) -> GoogleVisionEngine:
    """
    Factory function to create Google Cloud Vision OCR engine.
    
    Args:
        credentials_path: Path to service account JSON file
        credentials_dict: Service account credentials as dictionary
        **kwargs: Additional configuration options
        
    Returns:
        Configured Google Vision OCR engine
    """
    return GoogleVisionEngine(credentials_path, credentials_dict, **kwargs)


# Configuration helper
def get_google_config_template() -> Dict[str, Any]:
    """Get configuration template for Google Cloud Vision."""
    return {
        'credentials_path': '/path/to/service-account-key.json',
        'credentials_dict': None,  # Alternative to credentials_path
        'use_document_text': True,
        'language_hints': [],
        'timeout': 60
    }


# Example usage
if __name__ == "__main__":
    # Example configuration
    config = get_google_config_template()
    
    print("Google Cloud Vision OCR Engine")
    print("=" * 40)
    print(f"SDK Available: {GOOGLE_VISION_AVAILABLE}")
    print(f"Pillow Available: {PILLOW_AVAILABLE}")
    
    if GOOGLE_VISION_AVAILABLE:
        # Create engine (will use default credentials from environment)
        engine = create_google_vision_engine()
        
        print(f"Engine Available: {engine.is_available()}")
        print(f"Supported Languages: {engine.get_supported_languages()}")
        print(f"Engine Info: {engine.get_info()}")
    else:
        print("Install Google Cloud Vision with: pip install google-cloud-vision")