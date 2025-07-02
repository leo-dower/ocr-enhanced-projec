"""
Unit tests for OCR base classes and interfaces.

Tests the abstract base classes, data structures, and engine management
that form the foundation of the OCR system.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import time

from src.ocr.base import (
    OCRResult, 
    OCROptions, 
    OCREngine, 
    OCREngineManager
)


class TestOCRResult:
    """Test the OCRResult dataclass."""
    
    def test_basic_result_creation(self):
        """Test creating a basic OCR result."""
        result = OCRResult(
            text="Hello World",
            confidence=0.85,
            pages=[{"page": 1, "text": "Hello World"}],
            processing_time=1.5,
            engine="test_engine",
            language="eng"
        )
        
        assert result.text == "Hello World"
        assert result.confidence == 0.85
        assert len(result.pages) == 1
        assert result.processing_time == 1.5
        assert result.engine == "test_engine"
        assert result.language == "eng"
        assert result.success is True
        assert result.error_message is None
    
    def test_result_auto_calculations(self):
        """Test that word and character counts are calculated automatically."""
        result = OCRResult(
            text="Hello world! This is a test.",
            confidence=0.9,
            pages=[],
            processing_time=1.0,
            engine="test",
            language="eng"
        )
        
        # Should auto-calculate counts in __post_init__
        assert result.word_count == 6  # "Hello", "world!", "This", "is", "a", "test."
        assert result.character_count == 29  # Length of the text
    
    def test_result_with_manual_counts(self):
        """Test that manual counts are preserved."""
        result = OCRResult(
            text="Some text",
            confidence=0.8,
            pages=[],
            processing_time=1.0,
            engine="test",
            language="eng",
            word_count=100,  # Manual override
            character_count=500  # Manual override
        )
        
        # Manual counts should be preserved
        assert result.word_count == 100
        assert result.character_count == 500
    
    def test_error_result(self):
        """Test creating an error result."""
        result = OCRResult(
            text="",
            confidence=0.0,
            pages=[],
            processing_time=0.5,
            engine="failed_engine",
            language="eng",
            success=False,
            error_message="Engine not available"
        )
        
        assert result.success is False
        assert result.error_message == "Engine not available"
        assert result.word_count == 0
        assert result.character_count == 0


class TestOCROptions:
    """Test the OCROptions dataclass."""
    
    def test_default_options(self):
        """Test default option values."""
        options = OCROptions()
        
        assert options.language == "eng"
        assert options.confidence_threshold == 0.0
        assert options.preprocessing is True
        assert options.dpi == 300
        assert options.output_formats == ["text", "json"]
    
    def test_custom_options(self):
        """Test creating options with custom values."""
        options = OCROptions(
            language="por+eng",
            confidence_threshold=0.8,
            preprocessing=False,
            dpi=600,
            output_formats=["text", "json", "pdf"]
        )
        
        assert options.language == "por+eng"
        assert options.confidence_threshold == 0.8
        assert options.preprocessing is False
        assert options.dpi == 600
        assert options.output_formats == ["text", "json", "pdf"]


class MockOCREngine(OCREngine):
    """Mock OCR engine for testing."""
    
    def __init__(self, name="mock", available=True):
        super().__init__(name)
        self._available = available
        self.process_calls = []
    
    def is_available(self):
        return self._available
    
    def process_image(self, image_path, options):
        self.process_calls.append(('image', image_path, options))
        return OCRResult(
            text=f"Mock result for {image_path}",
            confidence=0.9,
            pages=[{"page": 1, "text": f"Mock result for {image_path}"}],
            processing_time=0.5,
            engine=self.name,
            language=options.language,
            file_path=str(image_path)
        )
    
    def process_pdf(self, pdf_path, options):
        self.process_calls.append(('pdf', pdf_path, options))
        return OCRResult(
            text=f"Mock PDF result for {pdf_path}",
            confidence=0.8,
            pages=[
                {"page": 1, "text": f"Page 1 of {pdf_path}"},
                {"page": 2, "text": f"Page 2 of {pdf_path}"}
            ],
            processing_time=1.2,
            engine=self.name,
            language=options.language,
            file_path=str(pdf_path)
        )


class TestOCREngine:
    """Test the abstract OCR engine base class."""
    
    def test_engine_initialization(self):
        """Test basic engine initialization."""
        engine = MockOCREngine("test_engine")
        
        assert engine.name == "test_engine"
        assert engine.is_available() is True
        assert engine.config == {}
    
    def test_engine_with_config(self):
        """Test engine initialization with configuration."""
        config = {"api_key": "test_key", "timeout": 30}
        engine = MockOCREngine("configured_engine", **config)
        
        assert engine.config == config
    
    def test_process_file_pdf(self, sample_pdf_file):
        """Test processing a PDF file."""
        engine = MockOCREngine()
        options = OCROptions(language="eng")
        
        result = engine.process_file(sample_pdf_file, options)
        
        assert result.success is True
        assert "Mock PDF result" in result.text
        assert result.engine == "mock"
        assert result.file_path == str(sample_pdf_file)
        assert len(result.pages) == 2
        
        # Verify the correct method was called
        assert len(engine.process_calls) == 1
        assert engine.process_calls[0][0] == 'pdf'
    
    def test_process_file_image(self, sample_image_file):
        """Test processing an image file."""
        engine = MockOCREngine()
        options = OCROptions(language="por")
        
        result = engine.process_file(sample_image_file, options)
        
        assert result.success is True
        assert "Mock result" in result.text
        assert result.language == "por"
        
        # Verify the correct method was called
        assert len(engine.process_calls) == 1
        assert engine.process_calls[0][0] == 'image'
    
    def test_process_file_nonexistent(self, temp_dir):
        """Test processing a file that doesn't exist."""
        engine = MockOCREngine()
        nonexistent_file = temp_dir / "nonexistent.pdf"
        
        result = engine.process_file(nonexistent_file)
        
        assert result.success is False
        assert "File not found" in result.error_message
        assert result.text == ""
        assert result.confidence == 0.0
    
    def test_process_file_unsupported_format(self, temp_dir):
        """Test processing an unsupported file format."""
        engine = MockOCREngine()
        unsupported_file = temp_dir / "document.docx"
        unsupported_file.write_text("fake content")
        
        result = engine.process_file(unsupported_file)
        
        assert result.success is False
        assert "Unsupported file type" in result.error_message
    
    def test_process_file_with_default_options(self, sample_pdf_file):
        """Test processing with default options when none provided."""
        engine = MockOCREngine()
        
        result = engine.process_file(sample_pdf_file)  # No options provided
        
        assert result.success is True
        # Should use default options
        call_options = engine.process_calls[0][2]
        assert call_options.language == "eng"  # Default language
    
    def test_process_file_timing(self, sample_image_file):
        """Test that processing time is recorded correctly."""
        engine = MockOCREngine()
        
        with patch('time.time', side_effect=[0.0, 1.5]):  # Mock time progression
            result = engine.process_file(sample_image_file)
        
        # Should use the mocked time difference if not already set
        assert result.processing_time > 0
    
    def test_get_supported_languages_default(self):
        """Test default supported languages."""
        engine = MockOCREngine()
        languages = engine.get_supported_languages()
        
        assert languages == ['eng']  # Default implementation
    
    def test_get_info(self):
        """Test engine info retrieval."""
        engine = MockOCREngine("info_test")
        info = engine.get_info()
        
        assert info['name'] == "info_test"
        assert info['available'] is True
        assert 'supported_languages' in info
        assert 'config' in info
    
    def test_string_representation(self):
        """Test string representations of engine."""
        engine = MockOCREngine("string_test")
        
        str_repr = str(engine)
        assert "string_test" in str_repr
        assert "available" in str_repr
        
        repr_str = repr(engine)
        assert "OCREngine" in repr_str
        assert "string_test" in repr_str


class TestOCREngineManager:
    """Test the OCR engine manager."""
    
    def test_manager_initialization(self):
        """Test basic manager initialization."""
        manager = OCREngineManager()
        
        assert len(manager.engines) == 0
        assert manager.default_engine is None
    
    def test_register_engine(self):
        """Test registering engines."""
        manager = OCREngineManager()
        engine1 = MockOCREngine("engine1")
        engine2 = MockOCREngine("engine2")
        
        # Register first engine (should become default)
        manager.register_engine(engine1)
        assert len(manager.engines) == 1
        assert manager.default_engine == "engine1"
        
        # Register second engine
        manager.register_engine(engine2)
        assert len(manager.engines) == 2
        assert manager.default_engine == "engine1"  # Should remain first
        
        # Register third engine as default
        engine3 = MockOCREngine("engine3")
        manager.register_engine(engine3, make_default=True)
        assert manager.default_engine == "engine3"
    
    def test_get_engine(self):
        """Test retrieving engines."""
        manager = OCREngineManager()
        engine = MockOCREngine("test_get")
        manager.register_engine(engine)
        
        # Get by name
        retrieved = manager.get_engine("test_get")
        assert retrieved is engine
        
        # Get default (no name)
        default = manager.get_engine()
        assert default is engine
        
        # Get non-existent
        missing = manager.get_engine("nonexistent")
        assert missing is None
    
    def test_get_available_engines(self):
        """Test getting list of available engines."""
        manager = OCREngineManager()
        
        available_engine = MockOCREngine("available", available=True)
        unavailable_engine = MockOCREngine("unavailable", available=False)
        
        manager.register_engine(available_engine)
        manager.register_engine(unavailable_engine)
        
        available_list = manager.get_available_engines()
        assert available_list == ["available"]
    
    def test_process_with_fallback_success_first(self, sample_pdf_file):
        """Test fallback processing when first engine succeeds."""
        manager = OCREngineManager()
        
        engine1 = MockOCREngine("primary")
        engine2 = MockOCREngine("fallback")
        
        manager.register_engine(engine1)
        manager.register_engine(engine2)
        
        result = manager.process_with_fallback(
            sample_pdf_file,
            engine_order=["primary", "fallback"]
        )
        
        assert result.success is True
        assert result.engine == "primary"
        
        # Only first engine should have been called
        assert len(engine1.process_calls) == 1
        assert len(engine2.process_calls) == 0
    
    def test_process_with_fallback_failure_then_success(self, sample_pdf_file):
        """Test fallback processing when first engine fails."""
        manager = OCREngineManager()
        
        # Create a failing engine
        failing_engine = MockOCREngine("failing")
        def fail_process(*args):
            return OCRResult(
                text="", confidence=0.0, pages=[], processing_time=0.1,
                engine="failing", language="eng", success=False,
                error_message="Engine failed"
            )
        failing_engine.process_file = fail_process
        
        success_engine = MockOCREngine("success")
        
        manager.register_engine(failing_engine)
        manager.register_engine(success_engine)
        
        result = manager.process_with_fallback(
            sample_pdf_file,
            engine_order=["failing", "success"]
        )
        
        assert result.success is True
        assert result.engine == "success"
    
    def test_process_with_fallback_all_fail(self, sample_pdf_file):
        """Test fallback processing when all engines fail."""
        manager = OCREngineManager()
        
        def fail_process(*args):
            return OCRResult(
                text="", confidence=0.0, pages=[], processing_time=0.1,
                engine="fail", language="eng", success=False,
                error_message="Failed"
            )
        
        engine1 = MockOCREngine("fail1")
        engine1.process_file = fail_process
        
        engine2 = MockOCREngine("fail2") 
        engine2.process_file = fail_process
        
        manager.register_engine(engine1)
        manager.register_engine(engine2)
        
        result = manager.process_with_fallback(
            sample_pdf_file,
            engine_order=["fail1", "fail2"]
        )
        
        assert result.success is False
        assert "All engines failed" in result.error_message
        assert result.engine == "none"
    
    def test_process_with_fallback_unavailable_engines(self, sample_pdf_file):
        """Test fallback processing with unavailable engines."""
        manager = OCREngineManager()
        
        unavailable = MockOCREngine("unavailable", available=False)
        available = MockOCREngine("available", available=True)
        
        manager.register_engine(unavailable)
        manager.register_engine(available)
        
        result = manager.process_with_fallback(
            sample_pdf_file,
            engine_order=["unavailable", "available"]
        )
        
        assert result.success is True
        assert result.engine == "available"
        
        # Unavailable engine should not have been called
        assert len(unavailable.process_calls) == 0
        assert len(available.process_calls) == 1
    
    def test_process_with_fallback_default_order(self, sample_pdf_file):
        """Test fallback processing with default engine order."""
        manager = OCREngineManager()
        
        engine1 = MockOCREngine("auto1", available=True)
        engine2 = MockOCREngine("auto2", available=False)  # Unavailable
        engine3 = MockOCREngine("auto3", available=True)
        
        manager.register_engine(engine1)
        manager.register_engine(engine2) 
        manager.register_engine(engine3)
        
        # Don't specify engine_order - should use available engines
        result = manager.process_with_fallback(sample_pdf_file)
        
        assert result.success is True
        # Should use one of the available engines
        assert result.engine in ["auto1", "auto3"]


@pytest.mark.integration 
class TestOCRBaseIntegration:
    """Integration tests for OCR base components."""
    
    def test_complete_workflow(self, sample_pdf_file, sample_image_file):
        """Test a complete OCR workflow using the base components."""
        # Setup manager with multiple engines
        manager = OCREngineManager()
        
        primary_engine = MockOCREngine("primary")
        backup_engine = MockOCREngine("backup")
        
        manager.register_engine(primary_engine)
        manager.register_engine(backup_engine)
        
        # Process different file types
        pdf_result = manager.process_with_fallback(sample_pdf_file)
        image_result = manager.process_with_fallback(sample_image_file)
        
        # Verify results
        assert pdf_result.success is True
        assert image_result.success is True
        assert pdf_result.engine == "primary"
        assert image_result.engine == "primary"
        
        # Verify file paths are preserved
        assert pdf_result.file_path == str(sample_pdf_file)
        assert image_result.file_path == str(sample_image_file)
        
        # Verify processing times are recorded
        assert pdf_result.processing_time > 0
        assert image_result.processing_time > 0