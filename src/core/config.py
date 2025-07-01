"""
Configuration management for OCR Enhanced application.

This module handles loading and managing configuration from various sources
including environment variables, config files, and command line arguments.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import json
from dataclasses import dataclass, asdict


@dataclass
class OCRConfig:
    """Configuration settings for OCR processing."""
    
    # Folder settings
    input_folder: str = "~/Documents/OCR_Input"
    output_folder: str = "~/Documents/OCR_Output"
    
    # Processing settings  
    mode: str = "hybrid"  # hybrid, local, cloud, privacy
    language: str = "por+eng"
    max_pages_per_batch: int = 200
    max_retries: int = 3
    confidence_threshold: float = 0.75
    
    # API settings
    mistral_api_key: Optional[str] = None
    api_timeout: int = 120
    
    # GUI settings
    window_width: int = 1600
    window_height: int = 900
    theme: str = "light"  # light, dark
    
    # Logging settings
    log_level: str = "INFO"
    log_to_file: bool = True
    
    def __post_init__(self):
        """Expand user paths after initialization."""
        self.input_folder = os.path.expanduser(self.input_folder)
        self.output_folder = os.path.expanduser(self.output_folder)


class ConfigManager:
    """Manages configuration loading and saving."""
    
    CONFIG_FILE = "~/.ocr-enhanced.json"
    
    @classmethod
    def load_config(cls) -> OCRConfig:
        """Load configuration from file and environment variables."""
        config = OCRConfig()
        
        # Load from file if exists
        config_path = Path(cls.CONFIG_FILE).expanduser()
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    cls._update_config_from_dict(config, file_config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config file: {e}")
        
        # Override with environment variables
        cls._load_from_env(config)
        
        return config
    
    @classmethod
    def save_config(cls, config: OCRConfig) -> bool:
        """Save configuration to file."""
        try:
            config_path = Path(cls.CONFIG_FILE).expanduser()
            config_path.parent.mkdir(exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(config), f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Error saving config: {e}")
            return False
    
    @staticmethod
    def _update_config_from_dict(config: OCRConfig, data: Dict[str, Any]):
        """Update config object from dictionary."""
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    @staticmethod
    def _load_from_env(config: OCRConfig):
        """Load configuration from environment variables."""
        env_mappings = {
            'OCR_INPUT_PATH': 'input_folder',
            'OCR_OUTPUT_PATH': 'output_folder',
            'OCR_MODE': 'mode',
            'OCR_LANGUAGE': 'language',
            'MISTRAL_API_KEY': 'mistral_api_key',
            'OCR_LOG_LEVEL': 'log_level',
        }
        
        for env_var, config_attr in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                setattr(config, config_attr, value)
        
        # Handle numeric environment variables
        numeric_mappings = {
            'OCR_MAX_PAGES': 'max_pages_per_batch',
            'OCR_MAX_RETRIES': 'max_retries',
            'OCR_WINDOW_WIDTH': 'window_width',
            'OCR_WINDOW_HEIGHT': 'window_height',
        }
        
        for env_var, config_attr in numeric_mappings.items():
            value = os.getenv(env_var)
            if value and value.isdigit():
                setattr(config, config_attr, int(value))
        
        # Handle float environment variables
        threshold = os.getenv('OCR_CONFIDENCE_THRESHOLD')
        if threshold:
            try:
                config.confidence_threshold = float(threshold)
            except ValueError:
                pass
        
        # Handle boolean environment variables
        log_to_file = os.getenv('OCR_LOG_TO_FILE')
        if log_to_file:
            config.log_to_file = log_to_file.lower() in ('true', '1', 'yes', 'on')


# Global configuration instance
_config: Optional[OCRConfig] = None


def get_config() -> OCRConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = ConfigManager.load_config()
    return _config


def update_config(new_config: OCRConfig) -> bool:
    """Update the global configuration and save to file."""
    global _config
    _config = new_config
    return ConfigManager.save_config(new_config)