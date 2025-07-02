"""
Integration tests for system-level functionality.

Tests that verify the complete system behavior including file I/O,
configuration loading, logging, and cross-component interactions.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock
import os

from src.core.config import OCRConfig, ConfigManager
from src.utils.logger import setup_logger, get_logger
from src.ocr.base import OCREngineManager, OCREngine, OCRResult, OCROptions


@pytest.mark.integration
class TestSystemConfiguration:
    """Test system-wide configuration behavior."""
    
    def test_config_persistence_across_components(self, temp_dir):
        """Test that configuration persists correctly across system components."""
        config_file = temp_dir / "system_config.json"
        
        # Create initial configuration
        initial_config = OCRConfig(
            mode="system_test",
            language="eng+por",
            max_pages_per_batch=150,
            confidence_threshold=0.85,
            input_folder=str(temp_dir / "sys_input"),
            output_folder=str(temp_dir / "sys_output")
        )
        
        # Save configuration
        with patch.object(ConfigManager, 'CONFIG_FILE', str(config_file)):
            saved = ConfigManager.save_config(initial_config)
            assert saved is True
            
            # Load in different context
            loaded_config = ConfigManager.load_config()
            
            # Verify all settings preserved
            assert loaded_config.mode == "system_test"
            assert loaded_config.language == "eng+por"
            assert loaded_config.max_pages_per_batch == 150
            assert loaded_config.confidence_threshold == 0.85
            assert loaded_config.input_folder == str(temp_dir / "sys_input")
            assert loaded_config.output_folder == str(temp_dir / "sys_output")
    
    def test_environment_override_system(self, temp_dir):
        """Test that environment variables properly override system config."""
        config_file = temp_dir / "env_test_config.json"
        
        # Create base configuration file
        file_config = {
            "mode": "file_mode",
            "language": "file_lang", 
            "max_pages_per_batch": 100
        }
        
        with open(config_file, 'w') as f:
            json.dump(file_config, f)
        
        # Set environment overrides
        env_vars = {
            'OCR_MODE': 'env_mode',
            'OCR_LANGUAGE': 'env_lang',
            'OCR_MAX_PAGES': '200'
        }
        
        with patch.object(ConfigManager, 'CONFIG_FILE', str(config_file)), \
             patch.dict(os.environ, env_vars):
            
            config = ConfigManager.load_config()
            
            # Environment should override file
            assert config.mode == "env_mode"
            assert config.language == "env_lang"
            assert config.max_pages_per_batch == 200


@pytest.mark.integration
class TestSystemLogging:
    """Test system-wide logging integration."""
    
    def test_multi_component_logging(self, temp_dir):
        """Test logging across multiple system components."""
        log_dir = temp_dir / "system_logs"
        
        # Setup loggers for different components
        gui_logger = setup_logger("system.gui", log_to_file=True, log_dir=str(log_dir))
        ocr_logger = setup_logger("system.ocr", log_to_file=True, log_dir=str(log_dir))
        core_logger = setup_logger("system.core", log_to_file=True, log_dir=str(log_dir))
        
        # Simulate multi-component activity
        gui_logger.info("GUI initialized")
        core_logger.info("Configuration loaded")
        ocr_logger.info("OCR engine started")
        
        gui_logger.debug("User selected file", extra={'file_count': 3})
        ocr_logger.info("Processing file", extra={'file_name': 'test.pdf'})
        core_logger.warning("Low memory warning", extra={'memory_usage': '85%'})
        
        # Verify log files created
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 3
        
        # Verify content in each log file
        for log_file in log_files:
            content = log_file.read_text(encoding='utf-8')
            assert len(content.strip()) > 0
            
            if "gui" in log_file.name:
                assert "GUI initialized" in content
                assert "User selected file" in content
            elif "ocr" in log_file.name:
                assert "OCR engine started" in content
                assert "Processing file" in content
            elif "core" in log_file.name:
                assert "Configuration loaded" in content
                assert "Low memory warning" in content
    
    def test_structured_logging_system_wide(self, temp_dir):
        """Test structured JSON logging across the system."""
        log_dir = temp_dir / "structured_logs"
        
        # Setup JSON logger
        logger = setup_logger(
            "structured_system",
            log_to_file=True,
            log_dir=str(log_dir),
            json_format=True
        )
        
        # Log structured events
        logger.info("System startup", extra={
            'component': 'main',
            'version': '2.0.0',
            'config_loaded': True
        })
        
        logger.error("Processing error", extra={
            'component': 'ocr',
            'file_path': '/test/file.pdf',
            'error_code': 'OCR_001',
            'retry_count': 2
        })
        
        # Read and parse log
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 1
        
        log_content = log_files[0].read_text(encoding='utf-8')
        log_lines = [json.loads(line) for line in log_content.strip().split('\n') if line]
        
        assert len(log_lines) == 2
        
        startup_log = log_lines[0]
        assert startup_log['message'] == "System startup"
        assert startup_log['component'] == 'main'
        assert startup_log['version'] == '2.0.0'
        assert startup_log['config_loaded'] is True
        
        error_log = log_lines[1]
        assert error_log['level'] == "ERROR"
        assert error_log['component'] == 'ocr'
        assert error_log['error_code'] == 'OCR_001'
        assert error_log['retry_count'] == 2


@pytest.mark.integration
class TestSystemFileOperations:
    """Test system-level file operations and I/O."""
    
    def test_input_output_directory_workflow(self, temp_dir):
        """Test complete input/output directory workflow."""
        input_dir = temp_dir / "system_input"
        output_dir = temp_dir / "system_output"
        input_dir.mkdir()
        output_dir.mkdir()
        
        # Create test input files
        test_files = []
        for i in range(3):
            file_path = input_dir / f"input_doc_{i}.pdf"
            file_path.write_bytes(f"Mock content {i}".encode())
            test_files.append(file_path)
        
        # Create configuration for directories
        config = OCRConfig(
            input_folder=str(input_dir),
            output_folder=str(output_dir),
            mode="system_test"
        )
        
        # Simulate processing all files
        class MockResultProcessor:
            def __init__(self, output_dir):
                self.output_dir = Path(output_dir)
            
            def save_result(self, file_path, result):
                output_file = self.output_dir / f"{file_path.stem}_result.json"
                result_data = {
                    'original_file': str(file_path),
                    'text': result.text,
                    'confidence': result.confidence,
                    'engine': result.engine,
                    'processing_time': result.processing_time
                }
                
                with open(output_file, 'w') as f:
                    json.dump(result_data, f, indent=2)
                
                return output_file
        
        processor = MockResultProcessor(output_dir)
        
        # Process each file
        from src.ocr.base import OCRResult
        for i, file_path in enumerate(test_files):
            mock_result = OCRResult(
                text=f"Processed content from {file_path.name}",
                confidence=0.85 + (i * 0.05),
                pages=[{"page": 1, "text": f"Content {i}"}],
                processing_time=1.0 + i,
                engine="system_test_engine",
                language="eng",
                file_path=str(file_path)
            )
            
            output_file = processor.save_result(file_path, mock_result)
            assert output_file.exists()
        
        # Verify all output files created
        output_files = list(output_dir.glob("*_result.json"))
        assert len(output_files) == 3
        
        # Verify content of output files
        for output_file in output_files:
            with open(output_file, 'r') as f:
                result_data = json.load(f)
            
            assert 'original_file' in result_data
            assert 'text' in result_data
            assert 'confidence' in result_data
            assert result_data['engine'] == "system_test_engine"
            assert result_data['confidence'] >= 0.85
    
    def test_file_permission_handling(self, temp_dir):
        """Test system behavior with file permission issues."""
        restricted_dir = temp_dir / "restricted"
        restricted_dir.mkdir()
        
        # Create a file and make it read-only
        test_file = restricted_dir / "readonly.pdf"
        test_file.write_bytes(b"Test content")
        
        # On Unix systems, make directory read-only
        if os.name != 'nt':  # Not Windows
            os.chmod(restricted_dir, 0o444)  # Read-only
        
        try:
            # Attempt to create output file in read-only directory
            output_file = restricted_dir / "output.json"
            
            if os.name != 'nt':
                # Should fail on Unix systems
                with pytest.raises((PermissionError, OSError)):
                    output_file.write_text("test output")
            else:
                # Windows might handle this differently
                try:
                    output_file.write_text("test output")
                except (PermissionError, OSError):
                    pass  # Expected behavior
        
        finally:
            # Restore permissions for cleanup
            if os.name != 'nt':
                os.chmod(restricted_dir, 0o755)


@pytest.mark.integration
class TestSystemErrorRecovery:
    """Test system-wide error recovery and resilience."""
    
    def test_partial_system_failure_recovery(self, temp_dir):
        """Test system recovery from partial component failures."""
        log_dir = temp_dir / "recovery_logs"
        
        # Setup system components
        logger = setup_logger("recovery_test", log_to_file=True, log_dir=str(log_dir))
        
        class SimulatedSystem:
            def __init__(self, logger):
                self.logger = logger
                self.processed_files = []
                self.failed_files = []
            
            def process_file_batch(self, files, fail_probability=0.3):
                """Simulate batch processing with some failures."""
                import random
                
                for i, file_path in enumerate(files):
                    self.logger.info(f"Processing file {file_path}", extra={'file_index': i})
                    
                    # Simulate random failures
                    if random.random() < fail_probability:
                        self.logger.error(f"Failed to process {file_path}", extra={
                            'file_index': i,
                            'error_type': 'processing_error'
                        })
                        self.failed_files.append(file_path)
                    else:
                        self.logger.info(f"Successfully processed {file_path}", extra={
                            'file_index': i,
                            'processing_time': random.uniform(0.5, 2.0)
                        })
                        self.processed_files.append(file_path)
                
                return len(self.processed_files), len(self.failed_files)
            
            def retry_failed_files(self):
                """Retry processing failed files."""
                retry_success = []
                retry_failed = []
                
                for file_path in self.failed_files:
                    self.logger.info(f"Retrying file {file_path}")
                    
                    # Simulate higher success rate on retry
                    if random.random() < 0.7:  # 70% success on retry
                        self.logger.info(f"Retry successful for {file_path}")
                        retry_success.append(file_path)
                        self.processed_files.append(file_path)
                    else:
                        self.logger.error(f"Retry failed for {file_path}")
                        retry_failed.append(file_path)
                
                self.failed_files = retry_failed
                return len(retry_success), len(retry_failed)
        
        # Create test files
        test_files = [f"test_file_{i}.pdf" for i in range(10)]
        
        # Simulate system with failures and recovery
        system = SimulatedSystem(logger)
        
        # Initial processing
        processed, failed = system.process_file_batch(test_files, fail_probability=0.3)
        
        # Retry failed files
        if failed > 0:
            retry_success, retry_failed = system.retry_failed_files()
            final_processed = processed + retry_success
            final_failed = retry_failed
        else:
            final_processed = processed
            final_failed = 0
        
        # System should process most files successfully
        assert final_processed >= 7  # At least 70% success rate
        assert final_processed + final_failed == len(test_files)
        
        # Verify logging captured the recovery process
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 1
        
        log_content = log_files[0].read_text(encoding='utf-8')
        assert "Processing file" in log_content
        assert "Successfully processed" in log_content
        
        if final_failed > 0:
            assert "Failed to process" in log_content
            assert "Retrying file" in log_content
    
    def test_configuration_corruption_recovery(self, temp_dir):
        """Test recovery from corrupted configuration."""
        config_file = temp_dir / "corrupt_config.json"
        backup_file = temp_dir / "config_backup.json"
        
        # Create valid backup configuration
        backup_config = {
            "mode": "backup_mode",
            "language": "backup_lang",
            "max_pages_per_batch": 250
        }
        
        with open(backup_file, 'w') as f:
            json.dump(backup_config, f)
        
        # Create corrupted main configuration
        config_file.write_text("{ corrupted json content }", encoding='utf-8')
        
        # Simulate recovery system
        class ConfigRecoverySystem:
            def __init__(self, main_file, backup_file):
                self.main_file = Path(main_file)
                self.backup_file = Path(backup_file)
            
            def load_config_with_recovery(self):
                """Load config with automatic recovery from backup."""
                try:
                    # Try to load main config
                    with open(self.main_file, 'r') as f:
                        config_data = json.load(f)
                    return config_data, "main"
                
                except (json.JSONDecodeError, FileNotFoundError):
                    # Fallback to backup
                    try:
                        with open(self.backup_file, 'r') as f:
                            config_data = json.load(f)
                        
                        # Restore main config from backup
                        with open(self.main_file, 'w') as f:
                            json.dump(config_data, f, indent=2)
                        
                        return config_data, "backup_restored"
                    
                    except (json.JSONDecodeError, FileNotFoundError):
                        # Use defaults if all else fails
                        default_config = {
                            "mode": "hybrid",
                            "language": "eng",
                            "max_pages_per_batch": 200
                        }
                        return default_config, "default"
        
        recovery_system = ConfigRecoverySystem(config_file, backup_file)
        config_data, source = recovery_system.load_config_with_recovery()
        
        # Should have recovered from backup
        assert source == "backup_restored"
        assert config_data["mode"] == "backup_mode"
        assert config_data["language"] == "backup_lang"
        assert config_data["max_pages_per_batch"] == 250
        
        # Main config should now be restored
        assert config_file.exists()
        with open(config_file, 'r') as f:
            restored_data = json.load(f)
        assert restored_data == backup_config


@pytest.mark.integration
class TestSystemPerformance:
    """Test system performance characteristics."""
    
    def test_memory_usage_during_batch_processing(self, temp_dir):
        """Test memory behavior during large batch processing."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create large batch of mock files
        input_dir = temp_dir / "memory_test_input"
        input_dir.mkdir()
        
        large_batch = []
        for i in range(50):  # Large batch
            file_path = input_dir / f"memory_test_{i}.pdf"
            file_path.write_bytes(b"Mock content" * 100)  # Small files
            large_batch.append(file_path)
        
        # Process batch while monitoring memory
        memory_readings = []
        
        class MemoryMonitoringEngine(OCREngine):
            def __init__(self):
                super().__init__("memory_monitor")
            
            def is_available(self):
                return True
            
            def process_file(self, file_path, options=None):
                # Monitor memory during processing
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_readings.append(current_memory)
                
                # Simulate processing
                return OCRResult(
                    text=f"Processed {file_path.name}",
                    confidence=0.85,
                    pages=[{"page": 1, "text": "content"}],
                    processing_time=0.1,
                    engine=self.name,
                    language="eng",
                    file_path=str(file_path)
                )
        
        engine = MemoryMonitoringEngine()
        manager = OCREngineManager()
        manager.register_engine(engine)
        
        # Process all files
        for file_path in large_batch:
            result = manager.process_with_fallback(file_path)
            assert result.success is True
        
        final_memory = process.memory_info().rss / 1024 / 1024
        
        # Memory growth should be reasonable (less than 100MB for this test)
        memory_growth = final_memory - initial_memory
        assert memory_growth < 100, f"Memory grew by {memory_growth:.2f}MB, which seems excessive"
        
        # Memory usage should be relatively stable during processing
        if len(memory_readings) > 10:
            max_memory = max(memory_readings)
            min_memory = min(memory_readings)
            memory_variance = max_memory - min_memory
            assert memory_variance < 50, f"Memory variance of {memory_variance:.2f}MB is too high"