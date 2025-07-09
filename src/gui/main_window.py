"""
Modern main window for OCR Enhanced.

This module provides the main application window with modern UI,
integrating all automation controls, dashboard, and workflow editor.
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from PyQt6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTabWidget, QMenuBar, QStatusBar, QToolBar,
        QAction, QMessageBox, QFileDialog, QProgressBar,
        QLabel, QPushButton, QSplitter, QDockWidget,
        QApplication, QSystemTrayIcon, QMenu
    )
    from PyQt6.QtCore import (
        Qt, QTimer, pyqtSignal, QThread, pyqtSlot,
        QSettings, QSize
    )
    from PyQt6.QtGui import (
        QFont, QIcon, QPixmap, QAction as QGuiAction,
        QKeySequence, QPalette
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    QMainWindow = object
    pyqtSignal = lambda: None

from ..automation.automation_manager import AutomationManager
from ..core.config import OCRConfig
from ..utils.logger import get_logger
from .themes import ThemeManager, ThemeType, get_theme_manager, apply_theme
from .dashboard import AutomationDashboard
from .automation_controls import AutomationControls
from .workflow_editor import WorkflowEditor


class StatusBarWidget(QWidget):
    """Custom status bar widget with automation status."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup status bar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # Automation status
        self.automation_status = QLabel("Automação: Inativa")
        self.automation_status.setStyleSheet("color: #dc3545; font-weight: bold;")
        layout.addWidget(self.automation_status)
        
        layout.addStretch()
        
        # Processing indicator
        self.processing_indicator = QProgressBar()
        self.processing_indicator.setVisible(False)
        self.processing_indicator.setMaximumWidth(150)
        layout.addWidget(self.processing_indicator)
        
        # Files processed counter
        self.files_counter = QLabel("Arquivos: 0")
        layout.addWidget(self.files_counter)
        
        # Theme toggle
        self.theme_button = QPushButton("🌙")
        self.theme_button.setToolTip("Alternar tema")
        self.theme_button.setMaximumSize(30, 25)
        self.theme_button.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_button)
        
    def update_automation_status(self, is_running: bool):
        """Update automation status display."""
        if is_running:
            self.automation_status.setText("Automação: Ativa")
            self.automation_status.setStyleSheet("color: #28a745; font-weight: bold;")
        else:
            self.automation_status.setText("Automação: Inativa")
            self.automation_status.setStyleSheet("color: #dc3545; font-weight: bold;")
            
    def update_files_counter(self, count: int):
        """Update files processed counter."""
        self.files_counter.setText(f"Arquivos: {count}")
        
    def show_processing(self, show: bool):
        """Show/hide processing indicator."""
        self.processing_indicator.setVisible(show)
        
    def toggle_theme(self):
        """Toggle between light and dark themes."""
        theme_manager = get_theme_manager()
        
        if theme_manager.current_theme == ThemeType.LIGHT:
            apply_theme(ThemeType.DARK)
            self.theme_button.setText("☀️")
        else:
            apply_theme(ThemeType.LIGHT)
            self.theme_button.setText("🌙")


class MainWindow(QMainWindow):
    """Modern main window for OCR Enhanced."""
    
    def __init__(self, automation_manager: Optional[AutomationManager] = None):
        super().__init__()
        self.automation_manager = automation_manager
        self.logger = get_logger("main_window")
        self.settings = QSettings("OCREnhanced", "MainWindow")
        
        if not PYQT_AVAILABLE:
            self.logger.warning("PyQt6 not available, using fallback main window")
            return
            
        self.setup_ui()
        self.setup_theme()
        self.setup_automation()
        self.setup_system_tray()
        self.restore_geometry()
        
    def setup_ui(self):
        """Setup the main user interface."""
        self.setWindowTitle("OCR Enhanced - Automação Avançada")
        self.setMinimumSize(1200, 800)
        
        # Central widget with tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Main tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        
        # Dashboard tab
        self.dashboard = AutomationDashboard(self.automation_manager)
        self.tab_widget.addTab(self.dashboard, "📊 Dashboard")
        
        # Automation controls tab
        self.automation_controls = AutomationControls(self.automation_manager)
        self.tab_widget.addTab(self.automation_controls, "⚙️ Controles")
        
        # Workflow editor tab
        self.workflow_editor = WorkflowEditor()
        self.tab_widget.addTab(self.workflow_editor, "🔄 Workflows")
        
        # Processing tab (placeholder for now)
        processing_widget = QWidget()
        processing_layout = QVBoxLayout(processing_widget)
        processing_layout.addWidget(QLabel("Interface de processamento será implementada"))
        self.tab_widget.addTab(processing_widget, "📄 Processamento")
        
        layout.addWidget(self.tab_widget)
        
        # Setup menu bar
        self.setup_menu_bar()
        
        # Setup toolbar
        self.setup_toolbar()
        
        # Setup status bar
        self.setup_status_bar()
        
        # Setup dock widgets
        self.setup_dock_widgets()
        
    def setup_menu_bar(self):
        """Setup the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("Arquivo")
        
        new_workflow_action = QAction("Novo Workflow", self)
        new_workflow_action.setShortcut(QKeySequence.StandardKey.New)
        new_workflow_action.triggered.connect(self.new_workflow)
        file_menu.addAction(new_workflow_action)
        
        open_workflow_action = QAction("Abrir Workflow", self)
        open_workflow_action.setShortcut(QKeySequence.StandardKey.Open)
        open_workflow_action.triggered.connect(self.open_workflow)
        file_menu.addAction(open_workflow_action)
        
        save_workflow_action = QAction("Salvar Workflow", self)
        save_workflow_action.setShortcut(QKeySequence.StandardKey.Save)
        save_workflow_action.triggered.connect(self.save_workflow)
        file_menu.addAction(save_workflow_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Sair", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Automation menu
        automation_menu = menubar.addMenu("Automação")
        
        start_automation_action = QAction("Iniciar Automação", self)
        start_automation_action.triggered.connect(self.start_automation)
        automation_menu.addAction(start_automation_action)
        
        stop_automation_action = QAction("Parar Automação", self)
        stop_automation_action.triggered.connect(self.stop_automation)
        automation_menu.addAction(stop_automation_action)
        
        automation_menu.addSeparator()
        
        refresh_action = QAction("Atualizar Status", self)
        refresh_action.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh_action.triggered.connect(self.refresh_status)
        automation_menu.addAction(refresh_action)
        
        # View menu
        view_menu = menubar.addMenu("Visualizar")
        
        toggle_theme_action = QAction("Alternar Tema", self)
        toggle_theme_action.setShortcut(QKeySequence("Ctrl+T"))
        toggle_theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(toggle_theme_action)
        
        fullscreen_action = QAction("Tela Cheia", self)
        fullscreen_action.setShortcut(QKeySequence.StandardKey.FullScreen)
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        # Help menu
        help_menu = menubar.addMenu("Ajuda")
        
        about_action = QAction("Sobre", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        documentation_action = QAction("Documentação", self)
        documentation_action.triggered.connect(self.show_documentation)
        help_menu.addAction(documentation_action)
        
    def setup_toolbar(self):
        """Setup the toolbar."""
        toolbar = self.addToolBar("Principal")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        
        # Quick actions
        start_action = QAction("▶️", self)
        start_action.setToolTip("Iniciar Automação")
        start_action.triggered.connect(self.start_automation)
        toolbar.addAction(start_action)
        
        stop_action = QAction("⏹️", self)
        stop_action.setToolTip("Parar Automação")
        stop_action.triggered.connect(self.stop_automation)
        toolbar.addAction(stop_action)
        
        toolbar.addSeparator()
        
        refresh_action = QAction("🔄", self)
        refresh_action.setToolTip("Atualizar")
        refresh_action.triggered.connect(self.refresh_status)
        toolbar.addAction(refresh_action)
        
        settings_action = QAction("⚙️", self)
        settings_action.setToolTip("Configurações")
        settings_action.triggered.connect(self.show_settings)
        toolbar.addAction(settings_action)
        
    def setup_status_bar(self):
        """Setup the status bar."""
        self.status_widget = StatusBarWidget()
        self.statusBar().addPermanentWidget(self.status_widget)
        
        # Update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(2000)  # Update every 2 seconds
        
    def setup_dock_widgets(self):
        """Setup dock widgets for additional panels."""
        # Log dock
        log_dock = QDockWidget("Log de Atividades", self)
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        
        from PyQt6.QtWidgets import QTextEdit
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(150)
        log_layout.addWidget(self.log_display)
        
        log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
        
    def setup_theme(self):
        """Setup theme management."""
        self.theme_manager = get_theme_manager()
        
        # Apply default theme
        apply_theme(ThemeType.LIGHT)
        
        # Connect theme change signal
        self.theme_manager.theme_changed.connect(self.on_theme_changed)
        
    def setup_automation(self):
        """Setup automation connections."""
        if self.automation_manager:
            # Connect automation controls
            self.automation_controls.set_automation_manager(self.automation_manager)
            self.dashboard.set_automation_manager(self.automation_manager)
            
            # Connect signals
            self.automation_controls.automation_changed.connect(self.on_automation_changed)
            self.dashboard.refresh_requested.connect(self.update_status)
            
    def setup_system_tray(self):
        """Setup system tray icon."""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            
            # Create tray menu
            tray_menu = QMenu()
            
            show_action = tray_menu.addAction("Mostrar")
            show_action.triggered.connect(self.show)
            
            tray_menu.addSeparator()
            
            start_action = tray_menu.addAction("Iniciar Automação")
            start_action.triggered.connect(self.start_automation)
            
            stop_action = tray_menu.addAction("Parar Automação")
            stop_action.triggered.connect(self.stop_automation)
            
            tray_menu.addSeparator()
            
            quit_action = tray_menu.addAction("Sair")
            quit_action.triggered.connect(self.close)
            
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self.tray_icon_activated)
            
            # Set icon (placeholder)
            self.tray_icon.setToolTip("OCR Enhanced")
            self.tray_icon.show()
            
    def tray_icon_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()
            
    def restore_geometry(self):
        """Restore window geometry from settings."""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
            
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)
            
    def closeEvent(self, event):
        """Handle close event."""
        # Save geometry
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        
        # Check if automation is running
        if self.automation_manager and self.automation_manager.running:
            reply = QMessageBox.question(
                self, "Fechar Aplicação",
                "A automação está ativa. Deseja parar a automação e fechar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            elif reply == QMessageBox.StandardButton.Yes:
                self.automation_manager.stop_automation()
                
        # Hide to tray if available
        if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()
            
    # Menu actions
    def new_workflow(self):
        """Create new workflow."""
        self.tab_widget.setCurrentIndex(2)  # Switch to workflow editor
        self.workflow_editor.new_workflow()
        
    def open_workflow(self):
        """Open workflow."""
        self.tab_widget.setCurrentIndex(2)
        self.workflow_editor.load_workflow()
        
    def save_workflow(self):
        """Save workflow."""
        self.workflow_editor.save_workflow()
        
    def start_automation(self):
        """Start automation."""
        if self.automation_manager:
            try:
                self.automation_manager.start_automation()
                self.add_log_message("Automação iniciada", "success")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao iniciar automação: {e}")
                self.add_log_message(f"Erro ao iniciar automação: {e}", "error")
                
    def stop_automation(self):
        """Stop automation."""
        if self.automation_manager:
            try:
                self.automation_manager.stop_automation()
                self.add_log_message("Automação parada", "warning")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao parar automação: {e}")
                
    def refresh_status(self):
        """Refresh status displays."""
        self.dashboard.refresh_dashboard()
        self.update_status()
        
    def toggle_theme(self):
        """Toggle application theme."""
        self.status_widget.toggle_theme()
        
    def toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
            
    def show_settings(self):
        """Show settings dialog."""
        QMessageBox.information(self, "Configurações", "Dialog de configurações será implementado")
        
    def show_about(self):
        """Show about dialog."""
        about_text = """
        <h2>OCR Enhanced</h2>
        <p><b>Versão:</b> 3.0</p>
        <p><b>Descrição:</b> Sistema avançado de OCR com automação completa</p>
        <br>
        <p><b>Funcionalidades:</b></p>
        <ul>
        <li>OCR local e em nuvem</li>
        <li>Automação de workflows</li>
        <li>Monitoramento de pastas e email</li>
        <li>Sistema de regras e templates</li>
        <li>Interface moderna e responsiva</li>
        </ul>
        <br>
        <p><b>Desenvolvido com:</b> Python, PyQt6, Tesseract, Mistral AI</p>
        """
        QMessageBox.about(self, "Sobre OCR Enhanced", about_text)
        
    def show_documentation(self):
        """Show documentation."""
        QMessageBox.information(self, "Documentação", "Documentação será aberta no navegador")
        
    # Event handlers
    def on_theme_changed(self, theme_name: str):
        """Handle theme changes."""
        self.add_log_message(f"Tema alterado para: {theme_name}", "info")
        
    def on_automation_changed(self, changes: Dict[str, Any]):
        """Handle automation configuration changes."""
        for feature, enabled in changes.items():
            status = "habilitado" if enabled else "desabilitado"
            self.add_log_message(f"{feature} {status}", "info")
            
    def update_status(self):
        """Update status displays."""
        if not self.automation_manager:
            return
            
        try:
            status = self.automation_manager.get_status()
            
            # Update status bar
            self.status_widget.update_automation_status(status.get("running", False))
            
            files_count = status.get("statistics", {}).get("total_files_processed", 0)
            self.status_widget.update_files_counter(files_count)
            
        except Exception as e:
            self.logger.error(f"Error updating status: {e}")
            
    def add_log_message(self, message: str, level: str = "info"):
        """Add message to log display."""
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color based on level
        colors = {
            "info": "#007acc",
            "success": "#28a745",
            "warning": "#ffc107",
            "error": "#dc3545"
        }
        
        color = colors.get(level, colors["info"])
        formatted_message = f"<span style='color: {color}'>[{timestamp}] {message}</span>"
        
        self.log_display.append(formatted_message)
        
        # Keep only last 100 lines
        text = self.log_display.toHtml()
        lines = text.split('<br>')
        if len(lines) > 100:
            self.log_display.setHtml('<br>'.join(lines[-100:]))
            
    def set_automation_manager(self, manager: AutomationManager):
        """Set automation manager."""
        self.automation_manager = manager
        self.setup_automation()


# Factory function
def create_main_window(automation_manager: Optional[AutomationManager] = None) -> MainWindow:
    """Factory function to create main window."""
    return MainWindow(automation_manager)


def run_gui_application(automation_manager: Optional[AutomationManager] = None):
    """Run the GUI application."""
    if not PYQT_AVAILABLE:
        print("PyQt6 not available. Please install PyQt6 to use the GUI:")
        print("pip install PyQt6")
        return None
        
    app = QApplication(sys.argv)
    app.setApplicationName("OCR Enhanced")
    app.setApplicationVersion("3.0")
    app.setOrganizationName("OCR Enhanced")
    
    # Set application icon (placeholder)
    app.setQuitOnLastWindowClosed(False)
    
    # Create and show main window
    window = create_main_window(automation_manager)
    window.show()
    
    return app, window


# Fallback for when PyQt6 is not available
class MainWindowFallback:
    """Fallback main window for when PyQt6 is not available."""
    
    def __init__(self, automation_manager=None):
        self.automation_manager = automation_manager
        print("MainWindow: PyQt6 not available, using fallback")
        
    def show(self):
        print("Main window would be shown here if PyQt6 was available")
        print("Current automation status:", 
              "Running" if self.automation_manager and self.automation_manager.running else "Stopped")
        
    def set_automation_manager(self, manager):
        self.automation_manager = manager


# Use fallback if PyQt6 is not available
if not PYQT_AVAILABLE:
    MainWindow = MainWindowFallback