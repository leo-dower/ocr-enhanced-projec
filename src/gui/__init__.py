"""
Graphical User Interface components.

This module contains all GUI-related classes including the main window,
dialogs, widgets, and user interaction handlers.
"""

from .main_window import MainWindow
from .widgets import FileListWidget, ProgressWidget

__all__ = ["MainWindow", "FileListWidget", "ProgressWidget"]