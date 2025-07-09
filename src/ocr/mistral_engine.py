"""
Mistral AI OCR Engine.

This module provides OCR capabilities using Mistral AI's OCR API.
It supports both image and PDF files with high accuracy cloud processing.
"""

import time
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import json
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import OCREngine, OCRResult, OCROptions
from ..utils.logger import get_logger


class MistralEngine(OCREngine):
    """Mistral AI OCR Engine for cloud processing."""
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Mistral OCR engine.
        
        Args:
            api_key: Mistral AI API key
            **kwargs: Additional configuration options
        """
        super().__init__("mistral_cloud", **kwargs)
        self.api_key = api_key
        self.logger = get_logger("mistral_ocr")
        
        # Configuration options
        self.base_url = kwargs.get("base_url", "https://api.mistral.ai/v1")
        self.timeout_upload = kwargs.get("timeout_upload", 120)
        self.timeout_ocr = kwargs.get("timeout_ocr", 300)
        self.max_retries = kwargs.get("max_retries", 3)
        self.model = kwargs.get("model", "pixtral-12b-2409")
        
        # Session for reuse
        self.session = None
        self._setup_session()
    
    def _setup_session(self):
        """Setup HTTP session with retry strategy."""
        self.session = requests.Session()
        
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
    
    def is_available(self) -> bool:
        """Check if Mistral AI API is available."""
        if not self.api_key:
            self.logger.warning("Mistral AI API key not provided")
            return False
        
        try:
            # Test API connection
            response = self.session.get(
                f"{self.base_url}/models",
                timeout=30
            )
            
            if response.status_code == 200:
                models = response.json()
                available_models = [m.get('id', '') for m in models.get('data', [])]
                return self.model in available_models
            else:
                self.logger.error(f"API test failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Mistral AI not available: {e}")
            return False
    
    def process_image(self, image_path: Union[str, Path], options: OCROptions) -> OCRResult:
        """Process a single image using Mistral AI."""
        return self.process_file(image_path, options)
    
    def process_pdf(self, pdf_path: Union[str, Path], options: OCROptions) -> OCRResult:
        """Process a PDF using Mistral AI."""
        return self.process_file(pdf_path, options)
    
    def process_file(self, file_path: Union[str, Path], options: OCROptions = None) -> OCRResult:
        """Process any supported file type using Mistral AI."""
        start_time = time.time()
        file_path = Path(file_path)
        
        if options is None:
            options = OCROptions()
        
        if not self.is_available():
            return self._create_error_result(
                file_path, options, "Mistral AI API not available", start_time
            )
        
        try:
            # Step 1: Upload file
            self.logger.info(f"Uploading file: {file_path.name}")
            file_id = self._upload_file(file_path)
            
            if not file_id:
                return self._create_error_result(
                    file_path, options, "Failed to upload file", start_time
                )
            
            # Step 2: Process with OCR
            self.logger.info(f"Processing OCR for file ID: {file_id}")
            result = self._process_ocr(file_id, options)
            
            if not result:
                return self._create_error_result(
                    file_path, options, "OCR processing failed", start_time
                )
            
            # Step 3: Parse results
            return self._parse_mistral_response(result, file_path, options, start_time)
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}")
            return self._create_error_result(file_path, options, str(e), start_time)
    
    def _upload_file(self, file_path: Path) -> Optional[str]:
        """Upload file to Mistral AI."""
        try:
            file_size = file_path.stat().st_size
            timeout = max(self.timeout_upload, int(file_size / (1024 * 1024) * 10))
            
            self.logger.info(f"Uploading {file_path.name} ({file_size / (1024*1024):.1f} MB)")
            
            # Prepare file upload
            files = {
                'file': (file_path.name, open(file_path, 'rb'), 'application/octet-stream')
            }
            
            # Remove Content-Type header for file upload
            headers = dict(self.session.headers)
            headers.pop('Content-Type', None)
            
            response = self.session.post(
                f"{self.base_url}/files",
                files=files,
                headers=headers,
                timeout=timeout
            )
            
            files['file'][1].close()  # Close file handle
            
            if response.status_code == 200:
                result = response.json()
                file_id = result.get('id')
                self.logger.info(f"File uploaded successfully: {file_id}")
                return file_id
            else:
                self.logger.error(f"Upload failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Upload error: {e}")
            return None
    
    def _process_ocr(self, file_id: str, options: OCROptions) -> Optional[Dict]:
        """Process OCR using Mistral AI."""
        try:
            # Prepare OCR request
            ocr_data = {
                "model": self.model,
                "file_id": file_id,
                "language": options.language,
                "output_format": "json"
            }
            
            timeout = self.timeout_ocr
            self.logger.info(f"Starting OCR processing (timeout: {timeout}s)")
            
            response = self.session.post(
                f"{self.base_url}/ocr",
                json=ocr_data,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                self.logger.info("OCR processing completed successfully")
                return result
            else:
                self.logger.error(f"OCR failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            self.logger.error(f"OCR processing timeout after {timeout} seconds")
            return None
        except Exception as e:
            self.logger.error(f"OCR processing error: {e}")
            return None
    
    def _parse_mistral_response(self, response: Dict, file_path: Path, 
                               options: OCROptions, start_time: float) -> OCRResult:
        """Parse Mistral AI response into OCRResult."""
        try:
            # Extract pages from response
            pages_data = response.get('pages', [])
            
            if not pages_data:
                return self._create_error_result(
                    file_path, options, "No pages found in response", start_time
                )
            
            # Process each page
            all_text = []
            processed_pages = []
            total_confidence = 0.0
            total_words = 0
            
            for page in pages_data:
                page_text = page.get('text', '').strip()
                page_number = page.get('page_number', len(processed_pages) + 1)
                
                if page_text:
                    all_text.append(page_text)
                
                # Extract word-level data if available
                words_data = []
                if 'words' in page:
                    for word in page['words']:
                        words_data.append({
                            'text': word.get('text', ''),
                            'confidence': word.get('confidence', 0.9),
                            'bounding_box': word.get('bounding_box', [])
                        })
                
                # Calculate page confidence
                page_confidence = page.get('confidence', 0.9)
                if 'words' in page:
                    word_confidences = [w.get('confidence', 0.0) for w in page['words']]
                    if word_confidences:
                        page_confidence = sum(word_confidences) / len(word_confidences)
                
                processed_page = {
                    'page_number': page_number,
                    'text': page_text,
                    'words': words_data,
                    'confidence': page_confidence,
                    'language': options.language
                }
                
                processed_pages.append(processed_page)
                total_confidence += page_confidence
                total_words += len(page_text.split())
            
            # Combine all text
            full_text = '\n\n'.join(all_text)
            avg_confidence = total_confidence / len(processed_pages) if processed_pages else 0.0
            
            # Extract metadata
            metadata = response.get('metadata', {})
            processing_time = time.time() - start_time
            
            return OCRResult(
                text=full_text,
                confidence=avg_confidence,
                pages=processed_pages,
                processing_time=processing_time,
                engine=self.name,
                language=options.language,
                file_path=str(file_path),
                word_count=total_words,
                character_count=len(full_text),
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing Mistral response: {e}")
            return self._create_error_result(file_path, options, str(e), start_time)
    
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
            'base_url': self.base_url,
            'model': self.model,
            'timeout_upload': self.timeout_upload,
            'timeout_ocr': self.timeout_ocr,
            'max_retries': self.max_retries,
            'api_key_configured': bool(self.api_key)
        })
        return info


def create_mistral_engine(api_key: str, **kwargs) -> MistralEngine:
    """
    Factory function to create Mistral AI OCR engine.
    
    Args:
        api_key: Mistral AI API key
        **kwargs: Additional configuration options
        
    Returns:
        Configured Mistral OCR engine
    """
    return MistralEngine(api_key, **kwargs)


# Configuration helper
def get_mistral_config_template() -> Dict[str, Any]:
    """Get configuration template for Mistral AI."""
    return {
        'api_key': 'your-mistral-api-key-here',
        'base_url': 'https://api.mistral.ai/v1',
        'model': 'pixtral-12b-2409',
        'timeout_upload': 120,
        'timeout_ocr': 300,
        'max_retries': 3
    }


# Example usage
if __name__ == "__main__":
    # Example configuration
    config = get_mistral_config_template()
    
    print("Mistral AI OCR Engine")
    print("=" * 30)
    
    # Create engine (will fail without valid API key)
    engine = create_mistral_engine(**config)
    
    print(f"Engine Available: {engine.is_available()}")
    print(f"Supported Languages: {engine.get_supported_languages()}")
    print(f"Engine Info: {engine.get_info()}")