"""
Pytest configuration and shared fixtures.

This module contains pytest configuration and fixtures that are available
to all test modules.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import json
import os
from typing import Dict, Any

# Import project modules for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import OCRConfig, ConfigManager
from src.utils.logger import setup_logger
from src.ocr.base import OCREngine, OCRResult, OCROptions


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_config_dir(temp_dir):
    """Create a temporary config directory."""
    config_dir = temp_dir / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def sample_config():
    """Create a sample OCR configuration."""
    return OCRConfig(
        input_folder="/tmp/test_input",
        output_folder="/tmp/test_output",
        mode="hybrid",
        language="eng+por",
        max_pages_per_batch=100,
        confidence_threshold=0.8,
        mistral_api_key="test_key_123"
    )


@pytest.fixture
def config_file(temp_config_dir, sample_config):
    """Create a temporary config file."""
    config_file = temp_config_dir / "test_config.json"
    config_data = {
        "mode": "hybrid",
        "language": "eng+por",
        "max_pages_per_batch": 100,
        "confidence_threshold": 0.8,
        "mistral_api_key": "test_key_123"
    }
    
    with open(config_file, 'w') as f:
        json.dump(config_data, f)
    
    return config_file


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        'OCR_INPUT_PATH': '/test/input',
        'OCR_OUTPUT_PATH': '/test/output',
        'OCR_MODE': 'local',
        'OCR_LANGUAGE': 'eng',
        'MISTRAL_API_KEY': 'mock_api_key',
        'OCR_LOG_LEVEL': 'DEBUG'
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def sample_ocr_result():
    """Create a sample OCR result for testing."""
    return OCRResult(
        text="This is a test document with some text.",
        confidence=0.85,
        pages=[
            {
                "page_number": 1,
                "text": "This is a test document",
                "confidence": 0.9,
                "word_count": 5
            },
            {
                "page_number": 2, 
                "text": "with some text.",
                "confidence": 0.8,
                "word_count": 3
            }
        ],
        processing_time=1.23,
        engine="test_engine",
        language="eng",
        word_count=8,
        character_count=39
    )


@pytest.fixture
def sample_ocr_options():
    """Create sample OCR options."""
    return OCROptions(
        language="eng+por",
        confidence_threshold=0.7,
        preprocessing=True,
        dpi=300,
        output_formats=["text", "json"]
    )


@pytest.fixture
def mock_ocr_engine():
    """Create a mock OCR engine for testing."""
    engine = Mock(spec=OCREngine)
    engine.name = "mock_engine"
    engine.is_available.return_value = True
    engine.get_supported_languages.return_value = ["eng", "por", "spa"]
    
    # Mock process methods to return sample results
    def mock_process_file(file_path, options=None):
        return OCRResult(
            text="Mock OCR result",
            confidence=0.9,
            pages=[{"page_number": 1, "text": "Mock OCR result", "confidence": 0.9}],
            processing_time=0.5,
            engine="mock_engine",
            language="eng",
            file_path=str(file_path)
        )
    
    engine.process_file.side_effect = mock_process_file
    engine.process_image.side_effect = mock_process_file
    engine.process_pdf.side_effect = mock_process_file
    
    return engine


@pytest.fixture
def sample_pdf_file(temp_dir):
    """Create a sample PDF file for testing."""
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n174\n%%EOF"
    
    pdf_file = temp_dir / "test_document.pdf"
    with open(pdf_file, 'wb') as f:
        f.write(pdf_content)
    
    return pdf_file


@pytest.fixture
def sample_image_file(temp_dir):
    """Create a sample image file for testing."""
    try:
        from PIL import Image, ImageDraw
        
        # Create a simple test image
        img = Image.new('RGB', (300, 100), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 30), 'Test OCR Text', fill='black')
        
        image_file = temp_dir / "test_image.png"
        img.save(image_file)
        
        return image_file
    except ImportError:
        # If PIL is not available, create a dummy file
        image_file = temp_dir / "test_image.png"
        image_file.write_bytes(b"fake_image_data")
        return image_file


@pytest.fixture
def caplog_debug(caplog):
    """Set logging level to DEBUG for tests."""
    import logging
    caplog.set_level(logging.DEBUG)
    return caplog


# Pytest configuration
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", 
        "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", 
        "unit: marks tests as unit tests"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on location."""
    for item in items:
        # Mark tests in integration folder as integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        # Mark tests in unit folder as unit tests  
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)


# Test utilities
class TestHelper:
    """Helper class with utility methods for tests."""
    
    @staticmethod
    def create_test_file(path: Path, content: str = "test content"):
        """Create a test file with given content."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path
    
    @staticmethod
    def assert_file_exists(path: Path):
        """Assert that a file exists."""
        assert path.exists(), f"File does not exist: {path}"
    
    @staticmethod
    def assert_file_contains(path: Path, text: str):
        """Assert that a file contains specific text."""
        content = path.read_text(encoding='utf-8')
        assert text in content, f"File {path} does not contain '{text}'"


@pytest.fixture
def test_helper():
    """Provide test helper utilities."""
    return TestHelper()