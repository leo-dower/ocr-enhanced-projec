"""
Logging utilities for OCR Enhanced application.

Provides structured logging with different output formats and levels.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
import json
from datetime import datetime

try:
    import coloredlogs
    HAS_COLOREDLOGS = True
except ImportError:
    HAS_COLOREDLOGS = False


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs JSON structured logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'ocr_file'):
            log_data['ocr_file'] = record.ocr_file
        if hasattr(record, 'processing_time'):
            log_data['processing_time'] = record.processing_time
        if hasattr(record, 'confidence'):
            log_data['confidence'] = record.confidence
            
        return json.dumps(log_data, ensure_ascii=False)


def setup_logger(
    name: str = "ocr_enhanced",
    level: str = "INFO", 
    log_to_file: bool = True,
    log_dir: Optional[str] = None,
    json_format: bool = False
) -> logging.Logger:
    """
    Set up a logger with console and optional file output.
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file
        log_dir: Directory for log files (default: ~/logs)
        json_format: Whether to use JSON formatting for file logs
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Set level
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if HAS_COLOREDLOGS:
        # Use coloredlogs for prettier console output
        coloredlogs.install(
            level=log_level,
            logger=logger,
            fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
    else:
        # Fallback to standard formatting
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_to_file:
        if log_dir is None:
            log_dir = Path.home() / "logs" / "ocr_enhanced"
        else:
            log_dir = Path(log_dir)
        
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"ocr_{timestamp}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        
        if json_format:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        logger.info(f"Logging to file: {log_file}")
    
    # Prevent duplicate logs in parent loggers
    logger.propagate = False
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(f"ocr_enhanced.{name}")


class OCRLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds OCR-specific context to log records.
    
    Usage:
        adapter = OCRLoggerAdapter(logger, {'ocr_file': 'document.pdf'})
        adapter.info("Processing started", extra={'processing_time': 1.23})
    """
    
    def process(self, msg, kwargs):
        """Add extra context to log record."""
        extra = kwargs.get('extra', {})
        extra.update(self.extra)
        kwargs['extra'] = extra
        return msg, kwargs


# Pre-configured loggers for different components
def get_gui_logger() -> logging.Logger:
    """Get logger for GUI components."""
    return get_logger("gui")


def get_ocr_logger() -> logging.Logger:
    """Get logger for OCR processing."""
    return get_logger("ocr")


def get_core_logger() -> logging.Logger:
    """Get logger for core functionality."""
    return get_logger("core")


def get_utils_logger() -> logging.Logger:
    """Get logger for utility functions."""
    return get_logger("utils")