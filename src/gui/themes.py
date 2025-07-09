"""
Theme management for modern OCR Enhanced GUI.

This module provides comprehensive theming capabilities including:
- Dark and light themes
- Custom color schemes
- Dynamic theme switching
- Professional styling
"""

from typing import Dict, Any, Optional
from enum import Enum

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtGui import QPalette, QColor, QFont
    from PyQt6.QtWidgets import QApplication
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    QObject = object
    pyqtSignal = lambda: None


class ThemeType(Enum):
    """Available theme types."""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"  # Follow system theme


class ThemeManager(QObject):
    """Manages application themes and styling."""
    
    theme_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.current_theme = ThemeType.LIGHT
        self._setup_themes()
        
    def _setup_themes(self):
        """Setup theme definitions."""
        
        # Light theme colors
        self.light_theme = {
            "primary": "#007acc",
            "primary_dark": "#005a9b",
            "primary_light": "#4da3d9",
            "secondary": "#28a745",
            "secondary_dark": "#218838",
            "warning": "#ffc107",
            "warning_dark": "#e0a800",
            "danger": "#dc3545",
            "danger_dark": "#c82333",
            "success": "#28a745",
            "info": "#17a2b8",
            
            # Background colors
            "background": "#ffffff",
            "background_alt": "#f8f9fa",
            "surface": "#ffffff",
            "surface_alt": "#f1f3f4",
            
            # Text colors
            "text_primary": "#212529",
            "text_secondary": "#6c757d",
            "text_muted": "#868e96",
            "text_disabled": "#adb5bd",
            
            # Border and divider colors
            "border": "#dee2e6",
            "border_light": "#e9ecef",
            "divider": "#e9ecef",
            
            # Card and panel colors
            "card_background": "#ffffff",
            "card_border": "#dee2e6",
            "panel_background": "#f8f9fa",
            
            # Input colors
            "input_background": "#ffffff",
            "input_border": "#ced4da",
            "input_focus": "#007acc",
            
            # Button colors
            "button_background": "#007acc",
            "button_hover": "#005a9b",
            "button_pressed": "#004578",
            
            # Status colors
            "status_active": "#28a745",
            "status_inactive": "#6c757d",
            "status_warning": "#ffc107",
            "status_error": "#dc3545"
        }
        
        # Dark theme colors
        self.dark_theme = {
            "primary": "#4da3d9",
            "primary_dark": "#007acc",
            "primary_light": "#7ec3e8",
            "secondary": "#4caf50",
            "secondary_dark": "#388e3c",
            "warning": "#ff9800",
            "warning_dark": "#f57c00",
            "danger": "#f44336",
            "danger_dark": "#d32f2f",
            "success": "#4caf50",
            "info": "#2196f3",
            
            # Background colors
            "background": "#1e1e1e",
            "background_alt": "#2d2d30",
            "surface": "#252526",
            "surface_alt": "#2d2d30",
            
            # Text colors
            "text_primary": "#ffffff",
            "text_secondary": "#cccccc",
            "text_muted": "#999999",
            "text_disabled": "#666666",
            
            # Border and divider colors
            "border": "#404040",
            "border_light": "#555555",
            "divider": "#404040",
            
            # Card and panel colors
            "card_background": "#252526",
            "card_border": "#404040",
            "panel_background": "#2d2d30",
            
            # Input colors
            "input_background": "#3c3c3c",
            "input_border": "#555555",
            "input_focus": "#4da3d9",
            
            # Button colors
            "button_background": "#4da3d9",
            "button_hover": "#007acc",
            "button_pressed": "#005a9b",
            
            # Status colors
            "status_active": "#4caf50",
            "status_inactive": "#999999",
            "status_warning": "#ff9800",
            "status_error": "#f44336"
        }
        
    def get_current_theme(self) -> Dict[str, str]:
        """Get current theme colors."""
        if self.current_theme == ThemeType.DARK:
            return self.dark_theme
        else:
            return self.light_theme
            
    def set_theme(self, theme_type: ThemeType):
        """Set application theme."""
        if not PYQT_AVAILABLE:
            return
            
        self.current_theme = theme_type
        
        app = QApplication.instance()
        if app:
            self._apply_theme_to_app(app)
            self.theme_changed.emit(theme_type.value)
            
    def _apply_theme_to_app(self, app: QApplication):
        """Apply theme to application."""
        theme_colors = self.get_current_theme()
        
        # Create custom palette
        palette = QPalette()
        
        # Set colors based on theme
        if self.current_theme == ThemeType.DARK:
            palette.setColor(QPalette.ColorRole.Window, QColor(theme_colors["background"]))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(theme_colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.Base, QColor(theme_colors["input_background"]))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme_colors["surface_alt"]))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme_colors["surface"]))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme_colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.Text, QColor(theme_colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.Button, QColor(theme_colors["surface"]))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme_colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.BrightText, QColor(theme_colors["danger"]))
            palette.setColor(QPalette.ColorRole.Link, QColor(theme_colors["primary"]))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(theme_colors["primary"]))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(theme_colors["text_primary"]))
        else:
            # Light theme
            palette.setColor(QPalette.ColorRole.Window, QColor(theme_colors["background"]))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(theme_colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.Base, QColor(theme_colors["input_background"]))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme_colors["background_alt"]))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme_colors["surface"]))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme_colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.Text, QColor(theme_colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.Button, QColor(theme_colors["surface"]))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme_colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.BrightText, QColor(theme_colors["danger"]))
            palette.setColor(QPalette.ColorRole.Link, QColor(theme_colors["primary"]))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(theme_colors["primary"]))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            
        app.setPalette(palette)
        
        # Set application stylesheet
        stylesheet = self.get_application_stylesheet()
        app.setStyleSheet(stylesheet)
        
    def get_application_stylesheet(self) -> str:
        """Get comprehensive application stylesheet."""
        theme_colors = self.get_current_theme()
        
        return f"""
        /* Main Application Styling */
        QMainWindow {{
            background-color: {theme_colors["background"]};
            color: {theme_colors["text_primary"]};
        }}
        
        /* Widgets */
        QWidget {{
            background-color: {theme_colors["background"]};
            color: {theme_colors["text_primary"]};
        }}
        
        /* Buttons */
        QPushButton {{
            background-color: {theme_colors["button_background"]};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            min-width: 80px;
        }}
        
        QPushButton:hover {{
            background-color: {theme_colors["button_hover"]};
        }}
        
        QPushButton:pressed {{
            background-color: {theme_colors["button_pressed"]};
        }}
        
        QPushButton:disabled {{
            background-color: {theme_colors["text_disabled"]};
            color: {theme_colors["text_muted"]};
        }}
        
        /* Secondary buttons */
        QPushButton[class="secondary"] {{
            background-color: {theme_colors["surface"]};
            color: {theme_colors["text_primary"]};
            border: 1px solid {theme_colors["border"]};
        }}
        
        QPushButton[class="secondary"]:hover {{
            background-color: {theme_colors["surface_alt"]};
        }}
        
        /* Danger buttons */
        QPushButton[class="danger"] {{
            background-color: {theme_colors["danger"]};
        }}
        
        QPushButton[class="danger"]:hover {{
            background-color: {theme_colors["danger_dark"]};
        }}
        
        /* Success buttons */
        QPushButton[class="success"] {{
            background-color: {theme_colors["success"]};
        }}
        
        QPushButton[class="success"]:hover {{
            background-color: {theme_colors["secondary_dark"]};
        }}
        
        /* Input fields */
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background-color: {theme_colors["input_background"]};
            border: 1px solid {theme_colors["input_border"]};
            border-radius: 4px;
            padding: 6px 10px;
            color: {theme_colors["text_primary"]};
            selection-background-color: {theme_colors["primary"]};
        }}
        
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border-color: {theme_colors["input_focus"]};
            outline: none;
        }}
        
        /* Tables */
        QTableWidget {{
            background-color: {theme_colors["surface"]};
            alternate-background-color: {theme_colors["surface_alt"]};
            border: 1px solid {theme_colors["border"]};
            gridline-color: {theme_colors["border_light"]};
        }}
        
        QTableWidget::item {{
            padding: 8px;
            border-bottom: 1px solid {theme_colors["border_light"]};
        }}
        
        QTableWidget::item:selected {{
            background-color: {theme_colors["primary"]};
            color: white;
        }}
        
        QHeaderView::section {{
            background-color: {theme_colors["panel_background"]};
            border: 1px solid {theme_colors["border"]};
            padding: 8px 10px;
            font-weight: bold;
        }}
        
        /* Lists */
        QListWidget {{
            background-color: {theme_colors["surface"]};
            border: 1px solid {theme_colors["border"]};
            border-radius: 4px;
        }}
        
        QListWidget::item {{
            padding: 8px 10px;
            border-bottom: 1px solid {theme_colors["border_light"]};
        }}
        
        QListWidget::item:selected {{
            background-color: {theme_colors["primary"]};
            color: white;
        }}
        
        QListWidget::item:hover {{
            background-color: {theme_colors["surface_alt"]};
        }}
        
        /* Group boxes */
        QGroupBox {{
            font-weight: bold;
            border: 1px solid {theme_colors["border"]};
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            background-color: {theme_colors["background"]};
        }}
        
        /* Tabs */
        QTabWidget::pane {{
            border: 1px solid {theme_colors["border"]};
            background-color: {theme_colors["surface"]};
        }}
        
        QTabBar::tab {{
            background-color: {theme_colors["panel_background"]};
            border: 1px solid {theme_colors["border"]};
            padding: 8px 16px;
            margin-right: 2px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {theme_colors["surface"]};
            border-bottom-color: {theme_colors["surface"]};
        }}
        
        QTabBar::tab:hover {{
            background-color: {theme_colors["surface_alt"]};
        }}
        
        /* Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background-color: {theme_colors["panel_background"]};
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {theme_colors["border"]};
            border-radius: 6px;
            min-height: 20px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {theme_colors["text_muted"]};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
        }}
        
        /* Checkboxes */
        QCheckBox {{
            spacing: 8px;
        }}
        
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {theme_colors["input_border"]};
            border-radius: 3px;
            background-color: {theme_colors["input_background"]};
        }}
        
        QCheckBox::indicator:checked {{
            background-color: {theme_colors["primary"]};
            border-color: {theme_colors["primary"]};
        }}
        
        /* Progress bars */
        QProgressBar {{
            border: 1px solid {theme_colors["border"]};
            border-radius: 4px;
            text-align: center;
            background-color: {theme_colors["surface"]};
        }}
        
        QProgressBar::chunk {{
            background-color: {theme_colors["primary"]};
            border-radius: 3px;
        }}
        
        /* Sliders */
        QSlider::groove:horizontal {{
            border: 1px solid {theme_colors["border"]};
            height: 6px;
            background-color: {theme_colors["surface"]};
            border-radius: 3px;
        }}
        
        QSlider::handle:horizontal {{
            background-color: {theme_colors["primary"]};
            border: 1px solid {theme_colors["primary_dark"]};
            width: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }}
        
        QSlider::handle:horizontal:hover {{
            background-color: {theme_colors["primary_light"]};
        }}
        
        /* Tooltips */
        QToolTip {{
            background-color: {theme_colors["surface"]};
            color: {theme_colors["text_primary"]};
            border: 1px solid {theme_colors["border"]};
            padding: 6px 8px;
            border-radius: 4px;
        }}
        
        /* Status bar */
        QStatusBar {{
            background-color: {theme_colors["panel_background"]};
            border-top: 1px solid {theme_colors["border"]};
        }}
        
        /* Menu bar */
        QMenuBar {{
            background-color: {theme_colors["panel_background"]};
            border-bottom: 1px solid {theme_colors["border"]};
        }}
        
        QMenuBar::item {{
            padding: 6px 12px;
        }}
        
        QMenuBar::item:selected {{
            background-color: {theme_colors["surface_alt"]};
        }}
        
        /* Menus */
        QMenu {{
            background-color: {theme_colors["surface"]};
            border: 1px solid {theme_colors["border"]};
        }}
        
        QMenu::item {{
            padding: 6px 20px;
        }}
        
        QMenu::item:selected {{
            background-color: {theme_colors["primary"]};
            color: white;
        }}
        
        /* Splitters */
        QSplitter::handle {{
            background-color: {theme_colors["border"]};
        }}
        
        QSplitter::handle:horizontal {{
            width: 2px;
        }}
        
        QSplitter::handle:vertical {{
            height: 2px;
        }}
        """
        
    def get_card_stylesheet(self) -> str:
        """Get stylesheet for card components."""
        theme_colors = self.get_current_theme()
        
        return f"""
        QFrame[class="card"] {{
            background-color: {theme_colors["card_background"]};
            border: 1px solid {theme_colors["card_border"]};
            border-radius: 8px;
            padding: 16px;
            margin: 8px;
        }}
        
        QFrame[class="card"]:hover {{
            border-color: {theme_colors["primary"]};
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        """
        
    def get_dashboard_stylesheet(self) -> str:
        """Get stylesheet for dashboard components."""
        theme_colors = self.get_current_theme()
        
        return f"""
        QWidget[class="dashboard"] {{
            background-color: {theme_colors["background"]};
        }}
        
        QLabel[class="metric-value"] {{
            font-size: 24px;
            font-weight: bold;
            color: {theme_colors["primary"]};
        }}
        
        QLabel[class="metric-label"] {{
            font-size: 12px;
            color: {theme_colors["text_secondary"]};
        }}
        
        QFrame[class="metric-card"] {{
            background-color: {theme_colors["card_background"]};
            border: 1px solid {theme_colors["card_border"]};
            border-radius: 8px;
            padding: 16px;
            margin: 4px;
        }}
        """


# Global theme manager instance
_theme_manager = None

def get_theme_manager() -> ThemeManager:
    """Get global theme manager instance."""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager


def apply_theme(theme_type: ThemeType):
    """Apply theme to application."""
    manager = get_theme_manager()
    manager.set_theme(theme_type)


def get_current_colors() -> Dict[str, str]:
    """Get current theme colors."""
    manager = get_theme_manager()
    return manager.get_current_theme()


# Convenience functions for specific stylesheets
def get_button_style(button_type: str = "primary") -> str:
    """Get button style for specific type."""
    colors = get_current_colors()
    
    styles = {
        "primary": f"""
            QPushButton {{
                background-color: {colors["primary"]};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {colors["primary_dark"]};
            }}
        """,
        "secondary": f"""
            QPushButton {{
                background-color: {colors["surface"]};
                color: {colors["text_primary"]};
                border: 1px solid {colors["border"]};
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {colors["surface_alt"]};
            }}
        """,
        "danger": f"""
            QPushButton {{
                background-color: {colors["danger"]};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {colors["danger_dark"]};
            }}
        """,
        "success": f"""
            QPushButton {{
                background-color: {colors["success"]};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {colors["secondary_dark"]};
            }}
        """
    }
    
    return styles.get(button_type, styles["primary"])


def get_status_color(status: str) -> str:
    """Get color for status indicator."""
    colors = get_current_colors()
    
    status_colors = {
        "active": colors["status_active"],
        "inactive": colors["status_inactive"],
        "warning": colors["status_warning"],
        "error": colors["status_error"],
        "success": colors["success"],
        "info": colors["info"]
    }
    
    return status_colors.get(status, colors["status_inactive"])