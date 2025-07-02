"""
Unit tests for configuration management.

Tests the OCRConfig class and ConfigManager functionality including
loading from files, environment variables, and saving configuration.
"""

import pytest
import os
import json
from pathlib import Path
from unittest.mock import patch, mock_open

from src.core.config import OCRConfig, ConfigManager, get_config, update_config


class TestOCRConfig:
    """Test the OCRConfig dataclass."""
    
    def test_default_config(self):
        """Test that default configuration values are correct."""
        config = OCRConfig()
        
        assert config.mode == "hybrid"
        assert config.language == "por+eng"
        assert config.max_pages_per_batch == 200
        assert config.max_retries == 3
        assert config.confidence_threshold == 0.75
        assert config.window_width == 1600
        assert config.window_height == 900
        assert config.theme == "light"
        assert config.log_level == "INFO"
        assert config.log_to_file is True
        assert config.mistral_api_key is None
    
    def test_custom_config(self):
        """Test creating config with custom values."""
        config = OCRConfig(
            mode="local",
            language="eng",
            max_pages_per_batch=100,
            confidence_threshold=0.9,
            mistral_api_key="test_key"
        )
        
        assert config.mode == "local"
        assert config.language == "eng"
        assert config.max_pages_per_batch == 100
        assert config.confidence_threshold == 0.9
        assert config.mistral_api_key == "test_key"
    
    def test_path_expansion(self):
        """Test that paths are properly expanded."""
        config = OCRConfig(
            input_folder="~/test_input",
            output_folder="~/test_output"
        )
        
        # Should expand ~ to user home directory
        assert not config.input_folder.startswith("~")
        assert not config.output_folder.startswith("~")
        assert "test_input" in config.input_folder
        assert "test_output" in config.output_folder


class TestConfigManager:
    """Test the ConfigManager class."""
    
    def test_load_config_default(self):
        """Test loading default config when no file exists."""
        with patch('pathlib.Path.exists', return_value=False):
            config = ConfigManager.load_config()
            
            assert isinstance(config, OCRConfig)
            assert config.mode == "hybrid"
    
    def test_load_config_from_file(self, temp_dir):
        """Test loading config from file."""
        config_file = temp_dir / "test_config.json"
        config_data = {
            "mode": "local",
            "language": "eng",
            "max_pages_per_batch": 150,
            "confidence_threshold": 0.85
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        with patch.object(ConfigManager, 'CONFIG_FILE', str(config_file)):
            config = ConfigManager.load_config()
            
            assert config.mode == "local"
            assert config.language == "eng"
            assert config.max_pages_per_batch == 150
            assert config.confidence_threshold == 0.85
    
    def test_load_config_invalid_json(self, temp_dir):
        """Test handling of invalid JSON in config file."""
        config_file = temp_dir / "invalid_config.json"
        config_file.write_text("{ invalid json }", encoding='utf-8')
        
        with patch.object(ConfigManager, 'CONFIG_FILE', str(config_file)):
            # Should not raise exception, should return default config
            config = ConfigManager.load_config()
            assert isinstance(config, OCRConfig)
            assert config.mode == "hybrid"  # Default value
    
    def test_load_config_from_env(self, mock_env_vars):
        """Test loading config from environment variables."""
        with patch('pathlib.Path.exists', return_value=False):
            config = ConfigManager.load_config()
            
            assert config.input_folder == '/test/input'
            assert config.output_folder == '/test/output'
            assert config.mode == 'local'
            assert config.language == 'eng'
            assert config.mistral_api_key == 'mock_api_key'
            assert config.log_level == 'DEBUG'
    
    def test_load_config_env_numeric_values(self):
        """Test loading numeric values from environment."""
        env_vars = {
            'OCR_MAX_PAGES': '500',
            'OCR_MAX_RETRIES': '5',
            'OCR_WINDOW_WIDTH': '1920',
            'OCR_WINDOW_HEIGHT': '1080',
            'OCR_CONFIDENCE_THRESHOLD': '0.95'
        }
        
        with patch.dict(os.environ, env_vars), \
             patch('pathlib.Path.exists', return_value=False):
            
            config = ConfigManager.load_config()
            
            assert config.max_pages_per_batch == 500
            assert config.max_retries == 5
            assert config.window_width == 1920
            assert config.window_height == 1080
            assert config.confidence_threshold == 0.95
    
    def test_load_config_env_boolean_values(self):
        """Test loading boolean values from environment."""
        test_cases = [
            ('true', True),
            ('True', True),
            ('1', True),
            ('yes', True),
            ('on', True),
            ('false', False),
            ('False', False),
            ('0', False),
            ('no', False),
            ('off', False),
        ]
        
        for env_value, expected in test_cases:
            with patch.dict(os.environ, {'OCR_LOG_TO_FILE': env_value}), \
                 patch('pathlib.Path.exists', return_value=False):
                
                config = ConfigManager.load_config()
                assert config.log_to_file == expected, f"Failed for {env_value}"
    
    def test_save_config(self, temp_dir):
        """Test saving config to file."""
        config_file = temp_dir / "save_test.json"
        config = OCRConfig(
            mode="cloud",
            language="spa",
            max_pages_per_batch=300
        )
        
        with patch.object(ConfigManager, 'CONFIG_FILE', str(config_file)):
            result = ConfigManager.save_config(config)
            
            assert result is True
            assert config_file.exists()
            
            # Verify saved content
            with open(config_file, 'r') as f:
                saved_data = json.load(f)
            
            assert saved_data['mode'] == "cloud"
            assert saved_data['language'] == "spa"
            assert saved_data['max_pages_per_batch'] == 300
    
    def test_save_config_io_error(self, temp_dir):
        """Test handling IO errors when saving config."""
        config = OCRConfig()
        
        # Try to save to a read-only location
        with patch.object(ConfigManager, 'CONFIG_FILE', '/root/readonly.json'):
            result = ConfigManager.save_config(config)
            assert result is False
    
    def test_update_config_from_dict(self):
        """Test updating config from dictionary."""
        config = OCRConfig()
        data = {
            "mode": "privacy",
            "language": "por",
            "invalid_field": "should_be_ignored"
        }
        
        ConfigManager._update_config_from_dict(config, data)
        
        assert config.mode == "privacy"
        assert config.language == "por"
        # Invalid field should be ignored
        assert not hasattr(config, "invalid_field")


class TestConfigGlobalFunctions:
    """Test global configuration functions."""
    
    def test_get_config_singleton(self):
        """Test that get_config returns singleton instance."""
        with patch.object(ConfigManager, 'load_config') as mock_load:
            mock_config = OCRConfig(mode="test")
            mock_load.return_value = mock_config
            
            # Clear global config
            import src.core.config
            src.core.config._config = None
            
            # First call should load config
            config1 = get_config()
            assert mock_load.call_count == 1
            assert config1.mode == "test"
            
            # Second call should return same instance
            config2 = get_config()
            assert mock_load.call_count == 1  # Should not call load again
            assert config2 is config1
    
    def test_update_config_global(self):
        """Test updating global config."""
        new_config = OCRConfig(mode="updated")
        
        with patch.object(ConfigManager, 'save_config', return_value=True) as mock_save:
            result = update_config(new_config)
            
            assert result is True
            mock_save.assert_called_once_with(new_config)
            
            # Verify global config was updated
            current_config = get_config()
            assert current_config is new_config
    
    def test_update_config_save_failure(self):
        """Test handling save failure in update_config."""
        new_config = OCRConfig(mode="failed")
        
        with patch.object(ConfigManager, 'save_config', return_value=False):
            result = update_config(new_config)
            
            assert result is False


@pytest.mark.integration
class TestConfigIntegration:
    """Integration tests for configuration system."""
    
    def test_full_config_workflow(self, temp_dir):
        """Test complete config workflow: load, modify, save, reload."""
        config_file = temp_dir / "workflow_test.json"
        
        with patch.object(ConfigManager, 'CONFIG_FILE', str(config_file)):
            # 1. Load default config (file doesn't exist)
            config1 = ConfigManager.load_config()
            assert config1.mode == "hybrid"
            
            # 2. Modify and save
            config1.mode = "local"
            config1.language = "eng"
            saved = ConfigManager.save_config(config1)
            assert saved is True
            
            # 3. Load again - should get modified values
            config2 = ConfigManager.load_config()
            assert config2.mode == "local"
            assert config2.language == "eng"
    
    def test_config_precedence(self, temp_dir):
        """Test that environment variables override file config."""
        config_file = temp_dir / "precedence_test.json"
        file_config = {
            "mode": "cloud",
            "language": "spa"
        }
        
        with open(config_file, 'w') as f:
            json.dump(file_config, f)
        
        env_vars = {
            'OCR_MODE': 'local',  # Should override file value
            'OCR_LANGUAGE': 'eng'  # Should override file value
        }
        
        with patch.object(ConfigManager, 'CONFIG_FILE', str(config_file)), \
             patch.dict(os.environ, env_vars):
            
            config = ConfigManager.load_config()
            
            # Environment should take precedence
            assert config.mode == "local"
            assert config.language == "eng"