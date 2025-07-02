"""
OCR Enhanced Automation Module

This module provides automation capabilities including:
- Folder watching for automatic file processing
- Template system for document types
- Workflow management and scheduling
- Rule-based processing and routing
"""

from .folder_watcher import FolderWatcher, WatcherConfig
from .templates import DocumentTemplate, TemplateManager
from .workflows import Workflow, WorkflowManager
from .scheduler import ProcessingScheduler
from .rules import RuleEngine, ProcessingRule

__all__ = [
    "FolderWatcher",
    "WatcherConfig", 
    "DocumentTemplate",
    "TemplateManager",
    "Workflow",
    "WorkflowManager",
    "ProcessingScheduler",
    "RuleEngine",
    "ProcessingRule"
]