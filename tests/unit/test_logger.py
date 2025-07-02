"""
Unit tests for logging system.

Tests the logging utilities including setup, formatters, and specialized loggers.
"""

import pytest
import logging
import json
from pathlib import Path
from unittest.mock import patch, mock_open
import tempfile
import shutil

from src.utils.logger import (
    JSONFormatter, 
    setup_logger, 
    get_logger,
    OCRLoggerAdapter,
    get_gui_logger,
    get_ocr_logger,
    get_core_logger,
    get_utils_logger
)


class TestJSONFormatter:
    """Test the JSON log formatter."""
    
    def test_basic_formatting(self):
        """Test basic JSON formatting of log records."""
        formatter = JSONFormatter()
        
        # Create a log record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        formatted = formatter.format(record)
        data = json.loads(formatted)
        
        assert data['level'] == 'INFO'
        assert data['logger'] == 'test_logger'
        assert data['message'] == 'Test message'
        assert data['module'] == 'test_module'
        assert data['function'] == 'test_function'
        assert data['line'] == 42
        assert 'timestamp' in data
    
    def test_formatting_with_extra_fields(self):
        """Test JSON formatting with OCR-specific extra fields."""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name="ocr_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=10,
            msg="Processing file",
            args=(),
            exc_info=None
        )
        record.module = "ocr_module"
        record.funcName = "process_file"
        
        # Add OCR-specific fields
        record.ocr_file = "document.pdf"
        record.processing_time = 1.23
        record.confidence = 0.85
        
        formatted = formatter.format(record)
        data = json.loads(formatted)
        
        assert data['ocr_file'] == "document.pdf"
        assert data['processing_time'] == 1.23
        assert data['confidence'] == 0.85
    
    def test_formatting_with_exception(self):
        """Test JSON formatting with exception information."""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="error_logger",
            level=logging.ERROR,
            pathname="/test/path.py",
            lineno=20,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )
        record.module = "error_module"
        record.funcName = "error_function"
        
        formatted = formatter.format(record)
        data = json.loads(formatted)
        
        assert 'exception' in data
        assert 'ValueError' in data['exception']
        assert 'Test exception' in data['exception']


class TestSetupLogger:
    """Test the setup_logger function."""
    
    def test_basic_logger_setup(self):
        """Test basic logger setup with defaults."""
        logger = setup_logger("test_basic", log_to_file=False)
        
        assert logger.name == "test_basic"
        assert logger.level == logging.INFO
        assert len(logger.handlers) >= 1  # At least console handler
    
    def test_logger_with_different_level(self):
        """Test logger setup with different log levels."""
        logger = setup_logger("test_debug", level="DEBUG", log_to_file=False)
        assert logger.level == logging.DEBUG
        
        logger = setup_logger("test_error", level="ERROR", log_to_file=False)
        assert logger.level == logging.ERROR
    
    def test_logger_with_file_output(self, temp_dir):
        """Test logger setup with file output."""
        log_dir = temp_dir / "logs"
        
        logger = setup_logger(
            "test_file", 
            log_to_file=True, 
            log_dir=str(log_dir)
        )
        
        # Should have both console and file handlers
        assert len(logger.handlers) >= 2
        
        # Check that log directory was created
        assert log_dir.exists()
        
        # Test logging to file
        logger.info("Test message")
        
        # Find the log file
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 1
        
        log_content = log_files[0].read_text(encoding='utf-8')
        assert "Test message" in log_content
    
    def test_logger_with_json_format(self, temp_dir):
        """Test logger setup with JSON formatting."""
        log_dir = temp_dir / "json_logs"
        
        logger = setup_logger(
            "test_json",
            log_to_file=True,
            log_dir=str(log_dir),
            json_format=True
        )
        
        logger.info("JSON test message")
        
        # Find and read log file
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 1
        
        log_content = log_files[0].read_text(encoding='utf-8')
        
        # Should be valid JSON
        log_data = json.loads(log_content.strip())
        assert log_data['message'] == "JSON test message"
        assert log_data['level'] == "INFO"
    
    @patch('src.utils.logger.HAS_COLOREDLOGS', False)
    def test_logger_without_coloredlogs(self):
        """Test logger setup when coloredlogs is not available."""
        logger = setup_logger("test_no_color", log_to_file=False)
        
        # Should still work without coloredlogs
        assert logger.name == "test_no_color"
        assert len(logger.handlers) >= 1
    
    def test_logger_propagate_disabled(self):
        """Test that logger propagate is disabled to prevent duplicates."""
        logger = setup_logger("test_propagate", log_to_file=False)
        assert logger.propagate is False


class TestGetLogger:
    """Test the get_logger function."""
    
    def test_get_logger_with_prefix(self):
        """Test that get_logger adds the correct prefix."""
        logger = get_logger("test_component")
        assert logger.name == "ocr_enhanced.test_component"
    
    def test_specialized_loggers(self):
        """Test the specialized logger getter functions."""
        gui_logger = get_gui_logger()
        assert gui_logger.name == "ocr_enhanced.gui"
        
        ocr_logger = get_ocr_logger()
        assert ocr_logger.name == "ocr_enhanced.ocr"
        
        core_logger = get_core_logger()
        assert core_logger.name == "ocr_enhanced.core"
        
        utils_logger = get_utils_logger()
        assert utils_logger.name == "ocr_enhanced.utils"


class TestOCRLoggerAdapter:
    """Test the OCR logger adapter."""
    
    def test_adapter_adds_context(self):
        """Test that adapter adds context to log records."""
        base_logger = logging.getLogger("test_adapter")
        adapter = OCRLoggerAdapter(base_logger, {'ocr_file': 'test.pdf'})
        
        # Mock the base logger to capture what gets passed
        with patch.object(base_logger, 'info') as mock_info:
            adapter.info("Test message", extra={'processing_time': 1.5})
            
            # Verify the call
            mock_info.assert_called_once()
            args, kwargs = mock_info.call_args
            
            assert args[0] == "Test message"
            assert 'extra' in kwargs
            assert kwargs['extra']['ocr_file'] == 'test.pdf'
            assert kwargs['extra']['processing_time'] == 1.5
    
    def test_adapter_overwrites_extra(self):
        """Test that adapter context overwrites conflicting extra fields."""
        base_logger = logging.getLogger("test_overwrite")
        adapter = OCRLoggerAdapter(base_logger, {'confidence': 0.9})
        
        with patch.object(base_logger, 'error') as mock_error:
            # Try to override confidence in extra
            adapter.error("Error message", extra={'confidence': 0.5})
            
            args, kwargs = mock_error.call_args
            # Adapter context should take precedence
            assert kwargs['extra']['confidence'] == 0.9


@pytest.mark.integration
class TestLoggingIntegration:
    """Integration tests for the logging system."""
    
    def test_end_to_end_logging(self, temp_dir):
        """Test complete logging workflow."""
        log_dir = temp_dir / "integration_logs"
        
        # Setup logger with file output
        logger = setup_logger(
            "integration_test",
            level="DEBUG",
            log_to_file=True,
            log_dir=str(log_dir),
            json_format=True
        )
        
        # Create adapter with OCR context
        adapter = OCRLoggerAdapter(logger, {
            'ocr_file': 'integration_test.pdf',
            'engine': 'test_engine'
        })
        
        # Log messages at different levels
        adapter.debug("Starting processing")
        adapter.info("Processing page 1", extra={'page_number': 1})
        adapter.warning("Low confidence detected", extra={'confidence': 0.3})
        
        try:
            raise RuntimeError("Test error")
        except RuntimeError:
            adapter.error("Processing failed", exc_info=True)
        
        # Verify log file was created and contains expected content
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 1
        
        log_content = log_files[0].read_text(encoding='utf-8')
        log_lines = [line for line in log_content.strip().split('\n') if line]
        
        # Should have 4 log entries
        assert len(log_lines) == 4
        
        # Parse and verify each log entry
        for line in log_lines:
            entry = json.loads(line)
            assert entry['logger'] == 'integration_test'
            assert entry['ocr_file'] == 'integration_test.pdf'
            assert entry['engine'] == 'test_engine'
        
        # Check specific entries
        debug_entry = json.loads(log_lines[0])
        assert debug_entry['level'] == 'DEBUG'
        assert debug_entry['message'] == 'Starting processing'
        
        info_entry = json.loads(log_lines[1])
        assert info_entry['level'] == 'INFO'
        assert info_entry['page_number'] == 1
        
        warning_entry = json.loads(log_lines[2])
        assert warning_entry['level'] == 'WARNING'
        assert warning_entry['confidence'] == 0.3
        
        error_entry = json.loads(log_lines[3])
        assert error_entry['level'] == 'ERROR'
        assert 'exception' in error_entry
        assert 'RuntimeError' in error_entry['exception']
    
    def test_multiple_loggers_isolation(self, temp_dir):
        """Test that multiple loggers are properly isolated."""
        log_dir = temp_dir / "multi_logs"
        
        # Create multiple loggers
        logger1 = setup_logger("multi_test_1", log_to_file=True, log_dir=str(log_dir))
        logger2 = setup_logger("multi_test_2", log_to_file=True, log_dir=str(log_dir))
        
        # Log to each
        logger1.info("Message from logger 1")
        logger2.info("Message from logger 2")
        
        # Should create separate log files
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 2
        
        # Verify content isolation
        all_content = ""
        for log_file in log_files:
            content = log_file.read_text(encoding='utf-8')
            all_content += content
        
        assert "Message from logger 1" in all_content
        assert "Message from logger 2" in all_content