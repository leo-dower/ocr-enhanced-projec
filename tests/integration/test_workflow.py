"""
Integration tests for complete OCR workflows.

Tests end-to-end processing including file loading, OCR processing,
result generation, and output saving.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import shutil

from src.core.config import OCRConfig
from src.utils.logger import setup_logger
from src.ocr.base import OCREngine, OCRResult, OCROptions, OCREngineManager


class MockOCREngine(OCREngine):
    """Mock OCR engine for integration testing."""
    
    def __init__(self, name="mock", quality_level="high"):
        super().__init__(name)
        self.quality_level = quality_level
        self.process_count = 0
    
    def is_available(self):
        return True
    
    def process_image(self, image_path, options):
        self.process_count += 1
        confidence = 0.9 if self.quality_level == "high" else 0.6
        
        return OCRResult(
            text=f"Extracted text from {image_path.name} using {self.name}",
            confidence=confidence,
            pages=[{"page": 1, "text": f"Page content from {image_path.name}"}],
            processing_time=0.5,
            engine=self.name,
            language=options.language,
            file_path=str(image_path)
        )
    
    def process_pdf(self, pdf_path, options):
        self.process_count += 1
        confidence = 0.85 if self.quality_level == "high" else 0.55
        
        return OCRResult(
            text=f"PDF content from {pdf_path.name} processed by {self.name}",
            confidence=confidence,
            pages=[
                {"page": 1, "text": f"Page 1 content from {pdf_path.name}"},
                {"page": 2, "text": f"Page 2 content from {pdf_path.name}"}
            ],
            processing_time=1.2,
            engine=self.name,
            language=options.language,
            file_path=str(pdf_path)
        )


@pytest.mark.integration
class TestCompleteWorkflow:
    """Test complete OCR processing workflows."""
    
    def test_single_file_processing_workflow(self, temp_dir, sample_pdf_file):
        """Test processing a single file through complete workflow."""
        # Setup
        config = OCRConfig(
            input_folder=str(temp_dir / "input"),
            output_folder=str(temp_dir / "output"),
            mode="hybrid",
            language="eng"
        )
        
        logger = setup_logger("integration_test", log_to_file=False)
        
        # Create engine manager
        manager = OCREngineManager()
        primary_engine = MockOCREngine("tesseract", quality_level="high")
        fallback_engine = MockOCREngine("mistral", quality_level="high")
        
        manager.register_engine(primary_engine)
        manager.register_engine(fallback_engine)
        
        # Process file
        options = OCROptions(
            language=config.language,
            confidence_threshold=config.confidence_threshold
        )
        
        result = manager.process_with_fallback(
            sample_pdf_file,
            options=options,
            engine_order=["tesseract", "mistral"]
        )
        
        # Verify results
        assert result.success is True
        assert result.engine == "tesseract"
        assert result.confidence >= config.confidence_threshold
        assert "PDF content" in result.text
        assert len(result.pages) == 2
        
        # Verify only primary engine was used
        assert primary_engine.process_count == 1
        assert fallback_engine.process_count == 0
    
    def test_fallback_workflow(self, temp_dir, sample_pdf_file):
        """Test workflow with fallback when primary engine fails."""
        config = OCRConfig(mode="hybrid", language="por")
        
        # Create failing primary engine
        failing_engine = MockOCREngine("failing_engine", quality_level="low")
        def fail_process(*args):
            return OCRResult(
                text="", confidence=0.0, pages=[], processing_time=0.1,
                engine="failing_engine", language="por", success=False,
                error_message="Primary engine failed"
            )
        failing_engine.process_file = fail_process
        
        # Create working fallback engine
        fallback_engine = MockOCREngine("fallback_engine", quality_level="high")
        
        manager = OCREngineManager()
        manager.register_engine(failing_engine)
        manager.register_engine(fallback_engine)
        
        # Process with fallback
        result = manager.process_with_fallback(
            sample_pdf_file,
            engine_order=["failing_engine", "fallback_engine"]
        )
        
        # Verify fallback was used
        assert result.success is True
        assert result.engine == "fallback_engine"
        assert fallback_engine.process_count == 1
    
    def test_batch_processing_workflow(self, temp_dir):
        """Test processing multiple files in batch."""
        # Create multiple test files
        input_dir = temp_dir / "batch_input"
        output_dir = temp_dir / "batch_output"
        input_dir.mkdir()
        output_dir.mkdir()
        
        # Create test files
        test_files = []
        for i in range(3):
            test_file = input_dir / f"test_document_{i}.pdf"
            test_file.write_bytes(b"Mock PDF content")
            test_files.append(test_file)
        
        # Setup batch processing
        config = OCRConfig(
            input_folder=str(input_dir),
            output_folder=str(output_dir),
            max_pages_per_batch=100
        )
        
        engine = MockOCREngine("batch_engine")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        # Process all files
        results = []
        for file_path in test_files:
            result = manager.process_with_fallback(file_path)
            results.append(result)
        
        # Verify all files were processed
        assert len(results) == 3
        assert all(r.success for r in results)
        assert engine.process_count == 3
        
        # Verify unique results for each file
        texts = [r.text for r in results]
        assert len(set(texts)) == 3  # All different texts
    
    def test_quality_threshold_workflow(self, temp_dir, sample_image_file):
        """Test workflow with quality threshold enforcement."""
        config = OCRConfig(confidence_threshold=0.8)
        
        # Create low-quality engine
        low_quality_engine = MockOCREngine("low_quality", quality_level="low")
        high_quality_engine = MockOCREngine("high_quality", quality_level="high")
        
        manager = OCREngineManager()
        manager.register_engine(low_quality_engine)
        manager.register_engine(high_quality_engine)
        
        options = OCROptions(confidence_threshold=config.confidence_threshold)
        
        # Process with quality check
        result = manager.process_with_fallback(
            sample_image_file,
            options=options,
            engine_order=["low_quality", "high_quality"]
        )
        
        # Should use high-quality engine due to threshold
        assert result.success is True
        assert result.confidence >= config.confidence_threshold
        
        # Verify both engines were tried (low quality failed threshold)
        assert low_quality_engine.process_count == 1
        assert high_quality_engine.process_count == 1


@pytest.mark.integration
class TestConfigurationIntegration:
    """Test configuration integration with other components."""
    
    def test_config_driven_processing(self, temp_dir, sample_pdf_file):
        """Test that configuration properly drives processing behavior."""
        # Test different configurations
        configs = [
            OCRConfig(mode="local", language="eng"),
            OCRConfig(mode="cloud", language="por"),
            OCRConfig(mode="hybrid", language="eng+por")
        ]
        
        for config in configs:
            engine = MockOCREngine(f"engine_{config.mode}")
            manager = OCREngineManager()
            manager.register_engine(engine)
            
            options = OCROptions(
                language=config.language,
                confidence_threshold=config.confidence_threshold
            )
            
            result = manager.process_with_fallback(sample_pdf_file, options=options)
            
            assert result.success is True
            assert result.language == config.language
            assert result.confidence >= config.confidence_threshold
    
    def test_logging_integration(self, temp_dir, sample_image_file):
        """Test that logging works correctly during processing."""
        log_dir = temp_dir / "integration_logs"
        
        # Setup logger with file output
        logger = setup_logger(
            "integration_workflow",
            log_to_file=True,
            log_dir=str(log_dir),
            json_format=True
        )
        
        # Process file while logging
        engine = MockOCREngine("logging_test")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        logger.info("Starting integration test processing")
        result = manager.process_with_fallback(sample_image_file)
        logger.info("Processing completed", extra={
            'success': result.success,
            'engine': result.engine,
            'processing_time': result.processing_time
        })
        
        # Verify log file was created and contains expected content
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 1
        
        log_content = log_files[0].read_text(encoding='utf-8')
        log_lines = [line for line in log_content.strip().split('\n') if line]
        
        assert len(log_lines) >= 2
        
        # Parse log entries
        start_entry = json.loads(log_lines[0])
        completion_entry = json.loads(log_lines[-1])
        
        assert start_entry['message'] == "Starting integration test processing"
        assert completion_entry['success'] is True
        assert completion_entry['engine'] == "logging_test"


@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Test error handling across the complete system."""
    
    def test_file_not_found_workflow(self, temp_dir):
        """Test workflow when input file doesn't exist."""
        nonexistent_file = temp_dir / "nonexistent.pdf"
        
        engine = MockOCREngine("error_test")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        result = manager.process_with_fallback(nonexistent_file)
        
        assert result.success is False
        assert "File not found" in result.error_message
        assert engine.process_count == 0  # Should not have been called
    
    def test_all_engines_fail_workflow(self, temp_dir, sample_pdf_file):
        """Test workflow when all engines fail."""
        def create_failing_engine(name):
            engine = MockOCREngine(name)
            def fail_process(*args):
                return OCRResult(
                    text="", confidence=0.0, pages=[], processing_time=0.1,
                    engine=name, language="eng", success=False,
                    error_message=f"{name} failed"
                )
            engine.process_file = fail_process
            return engine
        
        engine1 = create_failing_engine("fail1")
        engine2 = create_failing_engine("fail2")
        
        manager = OCREngineManager()
        manager.register_engine(engine1)
        manager.register_engine(engine2)
        
        result = manager.process_with_fallback(
            sample_pdf_file,
            engine_order=["fail1", "fail2"]
        )
        
        assert result.success is False
        assert "All engines failed" in result.error_message
        assert result.engine == "none"
    
    def test_partial_processing_recovery(self, temp_dir):
        """Test recovery from partial processing failures."""
        # Create batch of files where some might fail
        input_dir = temp_dir / "partial_input"
        input_dir.mkdir()
        
        # Create mix of processable and problematic files
        good_file = input_dir / "good.pdf"
        good_file.write_bytes(b"Good PDF content")
        
        # Create engine that fails on specific files
        selective_engine = MockOCREngine("selective")
        original_process = selective_engine.process_file
        
        def selective_process(file_path, options=None):
            if "good" in str(file_path):
                return original_process(file_path, options or OCROptions())
            else:
                return OCRResult(
                    text="", confidence=0.0, pages=[], processing_time=0.1,
                    engine="selective", language="eng", success=False,
                    error_message="Selective failure"
                )
        
        selective_engine.process_file = selective_process
        
        manager = OCREngineManager()
        manager.register_engine(selective_engine)
        
        # Process good file - should succeed
        good_result = manager.process_with_fallback(good_file)
        assert good_result.success is True
        assert "Good PDF content" in good_result.text


@pytest.mark.integration
class TestPerformanceIntegration:
    """Test performance aspects of the integrated system."""
    
    def test_processing_time_tracking(self, temp_dir, sample_pdf_file):
        """Test that processing times are accurately tracked."""
        engine = MockOCREngine("timing_test")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        import time
        start_time = time.time()
        result = manager.process_with_fallback(sample_pdf_file)
        total_time = time.time() - start_time
        
        assert result.success is True
        assert result.processing_time > 0
        assert result.processing_time <= total_time  # Should be reasonable
    
    def test_concurrent_processing_safety(self, temp_dir):
        """Test that concurrent processing doesn't cause issues."""
        import threading
        import queue
        
        # Create multiple test files
        input_dir = temp_dir / "concurrent_input"
        input_dir.mkdir()
        
        test_files = []
        for i in range(5):
            test_file = input_dir / f"concurrent_{i}.pdf"
            test_file.write_bytes(f"Content {i}".encode())
            test_files.append(test_file)
        
        # Setup shared engine
        engine = MockOCREngine("concurrent")
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        results_queue = queue.Queue()
        
        def process_file(file_path):
            try:
                result = manager.process_with_fallback(file_path)
                results_queue.put(('success', result))
            except Exception as e:
                results_queue.put(('error', str(e)))
        
        # Start concurrent processing
        threads = []
        for file_path in test_files:
            thread = threading.Thread(target=process_file, args=(file_path,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=10)  # 10-second timeout
        
        # Collect results
        results = []
        while not results_queue.empty():
            status, result = results_queue.get()
            results.append((status, result))
        
        # Verify all succeeded
        assert len(results) == 5
        assert all(status == 'success' for status, _ in results)
        assert all(r.success for _, r in results)
        
        # Verify engine processed all files
        assert engine.process_count == 5