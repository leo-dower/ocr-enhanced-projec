"""
Azure Computer Vision OCR Engine.

This module provides OCR capabilities using Microsoft Azure Computer Vision API.
It supports both Read API for documents and OCR API for images.
"""

import io
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import base64

try:
    # Azure Cognitive Services
    from azure.cognitiveservices.vision.computervision import ComputerVisionClient
    from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
    from msrest.authentication import CognitiveServicesCredentials
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    ComputerVisionClient = None
    CognitiveServicesCredentials = None
    OperationStatusCodes = None

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

from .base import OCREngine, OCRResult, OCROptions
from ..utils.logger import get_logger


class AzureVisionEngine(OCREngine):
    """Azure Computer Vision OCR Engine."""
    
    def __init__(self, endpoint: str, subscription_key: str, **kwargs):
        """
        Initialize Azure Vision OCR engine.
        
        Args:
            endpoint: Azure Computer Vision endpoint URL
            subscription_key: Azure subscription key
            **kwargs: Additional configuration options
        """
        super().__init__("azure_vision", **kwargs)
        self.endpoint = endpoint
        self.subscription_key = subscription_key
        self.logger = get_logger("azure_vision_ocr")
        
        # Configuration options
        self.use_read_api = kwargs.get("use_read_api", True)  # Use Read API for documents
        self.timeout = kwargs.get("timeout", 120)  # Timeout in seconds
        self.max_retries = kwargs.get("max_retries", 3)
        
        # Initialize client
        self.client = None
        if AZURE_AVAILABLE and self.endpoint and self.subscription_key:
            try:
                credentials = CognitiveServicesCredentials(self.subscription_key)
                self.client = ComputerVisionClient(self.endpoint, credentials)
                self.logger.info("Azure Computer Vision client initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize Azure client: {e}")
                self.client = None
    
    def is_available(self) -> bool:
        """Check if Azure Computer Vision is available."""
        if not AZURE_AVAILABLE:
            self.logger.warning("Azure Computer Vision SDK not installed")
            return False
            
        if not self.client:
            self.logger.warning("Azure Computer Vision client not initialized")
            return False
            
        try:
            # Test the connection with a simple call
            self.client.list_models()
            return True
        except Exception as e:
            self.logger.error(f"Azure Computer Vision not available: {e}")
            return False
    
    def process_image(self, image_path: Union[str, Path], options: OCROptions) -> OCRResult:
        """Process a single image using Azure Computer Vision."""
        start_time = time.time()
        image_path = Path(image_path)
        
        if not self.is_available():
            return self._create_error_result(
                image_path, options, "Azure Computer Vision not available", start_time
            )
        
        try:
            # Read image file
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()
            
            if self.use_read_api:
                return self._process_with_read_api(image_data, image_path, options, start_time)
            else:
                return self._process_with_ocr_api(image_data, image_path, options, start_time)
                
        except Exception as e:
            self.logger.error(f"Error processing image {image_path}: {e}")
            return self._create_error_result(image_path, options, str(e), start_time)
    
    def process_pdf(self, pdf_path: Union[str, Path], options: OCROptions) -> OCRResult:
        """Process a PDF using Azure Computer Vision Read API."""
        start_time = time.time()
        pdf_path = Path(pdf_path)
        
        if not self.is_available():
            return self._create_error_result(
                pdf_path, options, "Azure Computer Vision not available", start_time
            )
        
        try:
            # For PDFs, we need to convert to images first or use Read API directly
            if self.use_read_api:
                # Read API can handle PDFs directly
                with open(pdf_path, 'rb') as pdf_file:
                    pdf_data = pdf_file.read()
                return self._process_with_read_api(pdf_data, pdf_path, options, start_time)
            else:
                # Convert PDF to images and process each page
                return self._process_pdf_as_images(pdf_path, options, start_time)
                
        except Exception as e:
            self.logger.error(f"Error processing PDF {pdf_path}: {e}")
            return self._create_error_result(pdf_path, options, str(e), start_time)
    
    def _process_with_read_api(self, file_data: bytes, file_path: Path, 
                              options: OCROptions, start_time: float) -> OCRResult:
        """Process file using Azure Read API (recommended for documents)."""
        try:
            # Submit file for processing
            stream = io.BytesIO(file_data)
            read_response = self.client.read_in_stream(
                image=stream,
                language=self._convert_language_code(options.language),
                raw=True
            )
            
            # Get operation ID from response headers
            operation_id = read_response.headers["Operation-Location"].split("/")[-1]
            
            # Wait for processing to complete
            result = self._wait_for_read_result(operation_id)
            
            if not result:
                return self._create_error_result(
                    file_path, options, "Read operation failed or timed out", start_time
                )
            
            # Parse results
            text_content = []
            pages_data = []
            total_confidence = 0.0
            word_count = 0
            
            for page in result.analyze_result.read_results:
                page_text = []
                page_words = []
                
                for line in page.lines:
                    page_text.append(line.text)
                    
                    # Extract word-level data if available
                    for word in getattr(line, 'words', []):
                        page_words.append({
                            'text': word.text,
                            'confidence': word.confidence,
                            'bounding_box': word.bounding_box
                        })
                        total_confidence += word.confidence
                        word_count += 1
                
                page_content = '\n'.join(page_text)
                text_content.append(page_content)
                
                pages_data.append({
                    'page_number': len(pages_data) + 1,
                    'text': page_content,
                    'words': page_words,
                    'lines': len(page.lines),
                    'language': getattr(page, 'language', options.language)
                })
            
            full_text = '\n\n'.join(text_content)
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
            self.logger.error(f"Read API processing failed: {e}")
            return self._create_error_result(file_path, options, str(e), start_time)
    
    def _process_with_ocr_api(self, image_data: bytes, image_path: Path,
                             options: OCROptions, start_time: float) -> OCRResult:
        """Process image using Azure OCR API (legacy, for simple images)."""
        try:
            stream = io.BytesIO(image_data)
            ocr_result = self.client.recognize_text_in_stream(
                image=stream,
                language=self._convert_language_code(options.language),
                detect_orientation=True,
                raw=True
            )
            
            # Get operation ID
            operation_id = ocr_result.headers["Operation-Location"].split("/")[-1]
            
            # Wait for result
            result = self._wait_for_ocr_result(operation_id)
            
            if not result:
                return self._create_error_result(
                    image_path, options, "OCR operation failed or timed out", start_time
                )
            
            # Parse results
            text_lines = []
            words_data = []
            
            for region in result.recognition_results[0].lines:
                text_lines.append(region.text)
                
                for word in region.words:
                    words_data.append({
                        'text': word.text,
                        'confidence': getattr(word, 'confidence', 0.9),
                        'bounding_box': word.bounding_box
                    })
            
            full_text = '\n'.join(text_lines)
            
            pages_data = [{
                'page_number': 1,
                'text': full_text,
                'words': words_data,
                'lines': len(text_lines),
                'language': options.language
            }]
            
            return OCRResult(
                text=full_text,
                confidence=0.9,  # OCR API doesn't provide detailed confidence
                pages=pages_data,
                processing_time=time.time() - start_time,
                engine=self.name,
                language=options.language,
                file_path=str(image_path),
                word_count=len(full_text.split()),
                character_count=len(full_text),
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"OCR API processing failed: {e}")
            return self._create_error_result(image_path, options, str(e), start_time)
    
    def _wait_for_read_result(self, operation_id: str):
        """Wait for Read API operation to complete."""
        max_wait_time = self.timeout
        poll_interval = 1.0
        elapsed_time = 0.0
        
        while elapsed_time < max_wait_time:
            try:
                result = self.client.get_read_result(operation_id)
                
                if result.status == OperationStatusCodes.succeeded:
                    return result
                elif result.status == OperationStatusCodes.failed:
                    self.logger.error("Read operation failed")
                    return None
                
                # Still running, wait and check again
                time.sleep(poll_interval)
                elapsed_time += poll_interval
                
                # Increase poll interval gradually
                poll_interval = min(poll_interval * 1.2, 5.0)
                
            except Exception as e:
                self.logger.error(f"Error checking read result: {e}")
                return None
        
        self.logger.error(f"Read operation timed out after {max_wait_time} seconds")
        return None
    
    def _wait_for_ocr_result(self, operation_id: str):
        """Wait for OCR API operation to complete."""
        max_wait_time = self.timeout
        poll_interval = 1.0
        elapsed_time = 0.0
        
        while elapsed_time < max_wait_time:
            try:
                result = self.client.get_text_operation_result(operation_id)
                
                if result.status == OperationStatusCodes.succeeded:
                    return result
                elif result.status == OperationStatusCodes.failed:
                    self.logger.error("OCR operation failed")
                    return None
                
                time.sleep(poll_interval)
                elapsed_time += poll_interval
                poll_interval = min(poll_interval * 1.2, 5.0)
                
            except Exception as e:
                self.logger.error(f"Error checking OCR result: {e}")
                return None
        
        self.logger.error(f"OCR operation timed out after {max_wait_time} seconds")
        return None
    
    def _process_pdf_as_images(self, pdf_path: Path, options: OCROptions, start_time: float) -> OCRResult:
        """Convert PDF to images and process each page (fallback method)."""
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
                img_buffer.seek(0)
                
                # Process page with OCR API
                page_result = self._process_with_ocr_api(
                    img_buffer.getvalue(), 
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
    
    def _convert_language_code(self, language: str) -> str:
        """Convert language code to Azure format."""
        # Map common language codes to Azure supported codes
        language_map = {
            'eng': 'en',
            'por': 'pt',
            'spa': 'es',
            'fra': 'fr',
            'deu': 'de',
            'ita': 'it',
            'rus': 'ru',
            'chi_sim': 'zh-Hans',
            'chi_tra': 'zh-Hant',
            'jpn': 'ja',
            'kor': 'ko'
        }
        
        # Handle compound language codes (e.g., "por+eng")
        if '+' in language:
            primary_lang = language.split('+')[0]
            return language_map.get(primary_lang, 'en')
        
        return language_map.get(language, 'en')
    
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
            'chi_sim', 'chi_tra', 'jpn', 'kor', 'ara', 'hin'
        ]
    
    def get_info(self) -> Dict[str, Any]:
        """Get engine information."""
        info = super().get_info()
        info.update({
            'endpoint': self.endpoint,
            'use_read_api': self.use_read_api,
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'azure_sdk_available': AZURE_AVAILABLE,
            'pillow_available': PILLOW_AVAILABLE
        })
        return info


def create_azure_vision_engine(endpoint: str, subscription_key: str, **kwargs) -> AzureVisionEngine:
    """
    Factory function to create Azure Computer Vision OCR engine.
    
    Args:
        endpoint: Azure Computer Vision endpoint URL
        subscription_key: Azure subscription key
        **kwargs: Additional configuration options
        
    Returns:
        Configured Azure Vision OCR engine
    """
    return AzureVisionEngine(endpoint, subscription_key, **kwargs)


# Configuration helper
def get_azure_config_template() -> Dict[str, Any]:
    """Get configuration template for Azure Computer Vision."""
    return {
        'endpoint': 'https://your-resource.cognitiveservices.azure.com/',
        'subscription_key': 'your-subscription-key-here',
        'use_read_api': True,
        'timeout': 120,
        'max_retries': 3
    }


# Example usage
if __name__ == "__main__":
    # Example configuration (replace with your actual credentials)
    config = get_azure_config_template()
    
    print("Azure Computer Vision OCR Engine")
    print("=" * 40)
    print(f"SDK Available: {AZURE_AVAILABLE}")
    print(f"Pillow Available: {PILLOW_AVAILABLE}")
    
    if AZURE_AVAILABLE:
        # Create engine (will fail without valid credentials)
        engine = create_azure_vision_engine(
            endpoint=config['endpoint'],
            subscription_key=config['subscription_key']
        )
        
        print(f"Engine Available: {engine.is_available()}")
        print(f"Supported Languages: {engine.get_supported_languages()}")
        print(f"Engine Info: {engine.get_info()}")
    else:
        print("Install Azure SDK with: pip install azure-cognitiveservices-vision-computervision")