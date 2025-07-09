"""
Modern GUI module for OCR Enhanced.

This module provides a modern PyQt6-based interface with:
- Real-time automation dashboard
- Visual workflow editor
- Automation controls
- Dark/light themes
- Live metrics and monitoring
"""

from .main_window import MainWindow
from .dashboard import AutomationDashboard
from .workflow_editor import WorkflowEditor
from .automation_controls import AutomationControls
from .themes import ThemeManager

# Legacy widgets for backward compatibility
try:
    from .widgets import FileListWidget, ProgressWidget
    legacy_widgets = ["FileListWidget", "ProgressWidget"]
except ImportError:
    legacy_widgets = []

__all__ = [
    'MainWindow',
    'AutomationDashboard', 
    'WorkflowEditor',
    'AutomationControls',
    'ThemeManager'
] + legacy_widgets