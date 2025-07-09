"""
Real-time automation dashboard for OCR Enhanced.

This module provides a comprehensive dashboard with live metrics,
status monitoring, charts, and visual feedback for the automation system.
"""

import sys
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QFrame, QScrollArea,
        QProgressBar, QGroupBox, QSplitter,
        QTableWidget, QTableWidgetItem, QHeaderView,
        QTextEdit, QListWidget, QListWidgetItem
    )
    from PyQt6.QtCore import (
        Qt, QTimer, pyqtSignal, QThread, pyqtSlot,
        QPropertyAnimation, QEasingCurve, QRect, QSize
    )
    from PyQt6.QtGui import (
        QFont, QPainter, QPen, QBrush, QColor, QPixmap, QIcon
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    QWidget = object
    pyqtSignal = lambda: None

from ..automation.automation_manager import AutomationManager
from ..utils.logger import get_logger
from .themes import get_current_colors, get_status_color


class MetricCard(QFrame):
    """Card widget for displaying key metrics."""
    
    def __init__(self, title: str, value: str = "0", unit: str = "", 
                 status: str = "inactive", parent=None):
        super().__init__(parent)
        self.title = title
        self.value = value
        self.unit = unit
        self.status = status
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the metric card UI."""
        self.setFrameStyle(QFrame.Shape.Box)
        self.setFixedSize(200, 120)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Title
        title_label = QLabel(self.title)
        title_label.setFont(QFont("Arial", 10))
        title_label.setStyleSheet("color: #666; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Value and unit
        value_layout = QHBoxLayout()
        
        self.value_label = QLabel(self.value)
        self.value_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: #333;")
        value_layout.addWidget(self.value_label)
        
        if self.unit:
            unit_label = QLabel(self.unit)
            unit_label.setFont(QFont("Arial", 12))
            unit_label.setStyleSheet("color: #666;")
            unit_label.setAlignment(Qt.AlignmentFlag.AlignBottom)
            value_layout.addWidget(unit_label)
            
        value_layout.addStretch()
        layout.addLayout(value_layout)
        
        # Status indicator
        self.status_label = QLabel("●")
        self.status_label.setFont(QFont("Arial", 16))
        self.update_status(self.status)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Apply card styling
        self.update_styling()
        
    def update_value(self, value: str, unit: str = None):
        """Update the metric value."""
        self.value = value
        self.value_label.setText(value)
        if unit is not None:
            self.unit = unit
            
    def update_status(self, status: str):
        """Update the status indicator."""
        self.status = status
        color = get_status_color(status)
        self.status_label.setStyleSheet(f"color: {color};")
        
    def update_styling(self):
        """Update card styling based on current theme."""
        colors = get_current_colors()
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {colors["card_background"]};
                border: 1px solid {colors["card_border"]};
                border-radius: 8px;
                padding: 12px;
                margin: 4px;
            }}
            QFrame:hover {{
                border-color: {colors["primary"]};
                background-color: {colors["surface_alt"]};
            }}
        """)


class StatusIndicatorWidget(QWidget):
    """Custom widget for drawing status indicators."""
    
    def __init__(self, size: int = 16, parent=None):
        super().__init__(parent)
        self.status = "inactive"
        self.size = size
        self.setFixedSize(size, size)
        
    def set_status(self, status: str):
        """Set status and update display."""
        self.status = status
        self.update()
        
    def paintEvent(self, event):
        """Paint the status indicator."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get status color
        color_str = get_status_color(self.status)
        color = QColor(color_str)
        
        # Draw circle
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(120), 1))
        painter.drawEllipse(2, 2, self.size - 4, self.size - 4)


class ComponentStatusWidget(QWidget):
    """Widget showing status of automation components."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup component status UI."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Status dos Componentes")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Component indicators
        self.components = {}
        components_layout = QGridLayout()
        
        # Define components
        component_list = [
            ("folder_watcher", "Monitoramento de Pastas"),
            ("scheduler", "Agendador"),
            ("email_monitor", "Email"),
            ("rule_engine", "Regras"),
            ("workflow_manager", "Workflows"),
            ("template_manager", "Templates")
        ]
        
        row = 0
        for component_id, component_name in component_list:
            indicator = StatusIndicatorWidget()
            label = QLabel(component_name)
            label.setFont(QFont("Arial", 9))
            
            components_layout.addWidget(indicator, row, 0)
            components_layout.addWidget(label, row, 1)
            
            self.components[component_id] = indicator
            row += 1
            
        layout.addLayout(components_layout)
        layout.addStretch()
        
    def update_component_status(self, component_id: str, status: str):
        """Update status of a specific component."""
        if component_id in self.components:
            self.components[component_id].set_status(status)


class RecentActivityWidget(QWidget):
    """Widget showing recent automation activity."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup recent activity UI."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Atividade Recente")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Activity list
        self.activity_list = QListWidget()
        self.activity_list.setMaximumHeight(200)
        layout.addWidget(self.activity_list)
        
    def add_activity(self, timestamp: datetime, activity: str, status: str = "info"):
        """Add activity to the list."""
        time_str = timestamp.strftime("%H:%M:%S")
        item_text = f"{time_str} - {activity}"
        
        item = QListWidgetItem(item_text)
        
        # Set color based on status
        if status == "success":
            item.setBackground(QColor("#d4edda"))
        elif status == "warning":
            item.setBackground(QColor("#fff3cd"))
        elif status == "error":
            item.setBackground(QColor("#f8d7da"))
            
        self.activity_list.insertItem(0, item)
        
        # Keep only last 50 items
        if self.activity_list.count() > 50:
            self.activity_list.takeItem(self.activity_list.count() - 1)


class PerformanceChartWidget(QWidget):
    """Simple performance chart widget."""
    
    def __init__(self, title: str = "Performance", parent=None):
        super().__init__(parent)
        self.title = title
        self.data_points = []
        self.max_points = 60  # Keep last 60 data points
        self.setMinimumHeight(150)
        
    def add_data_point(self, value: float):
        """Add a data point to the chart."""
        self.data_points.append(value)
        if len(self.data_points) > self.max_points:
            self.data_points.pop(0)
        self.update()
        
    def paintEvent(self, event):
        """Paint the performance chart."""
        if not self.data_points:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get dimensions
        width = self.width() - 40
        height = self.height() - 40
        
        # Draw background
        colors = get_current_colors()
        painter.fillRect(20, 20, width, height, QColor(colors["surface"]))
        
        # Draw border
        painter.setPen(QPen(QColor(colors["border"]), 1))
        painter.drawRect(20, 20, width, height)
        
        # Draw title
        painter.setPen(QPen(QColor(colors["text_primary"]), 1))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.drawText(25, 15, self.title)
        
        # Draw data
        if len(self.data_points) > 1:
            max_value = max(self.data_points) or 1
            min_value = min(self.data_points)
            value_range = max_value - min_value or 1
            
            painter.setPen(QPen(QColor(colors["primary"]), 2))
            
            for i in range(1, len(self.data_points)):
                x1 = 20 + (i - 1) * width / (self.max_points - 1)
                y1 = 20 + height - ((self.data_points[i - 1] - min_value) / value_range) * height
                
                x2 = 20 + i * width / (self.max_points - 1)
                y2 = 20 + height - ((self.data_points[i] - min_value) / value_range) * height
                
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))


class AutomationDashboard(QWidget):
    """Main automation dashboard widget."""
    
    refresh_requested = pyqtSignal()
    
    def __init__(self, automation_manager: Optional[AutomationManager] = None, parent=None):
        super().__init__(parent)
        self.automation_manager = automation_manager
        self.logger = get_logger("automation_dashboard")
        
        if not PYQT_AVAILABLE:
            self.logger.warning("PyQt6 not available, using fallback dashboard")
            return
            
        self.setup_ui()
        self.setup_timer()
        
    def setup_ui(self):
        """Setup the dashboard UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("Dashboard de Automação")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Refresh button
        refresh_btn = QPushButton("Atualizar")
        refresh_btn.clicked.connect(self.refresh_dashboard)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Main content in splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - metrics and status
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Metrics cards
        metrics_group = QGroupBox("Métricas Principais")
        metrics_layout = QGridLayout(metrics_group)
        
        self.files_processed_card = MetricCard("Arquivos Processados", "0")
        self.workflows_executed_card = MetricCard("Workflows Executados", "0")
        self.success_rate_card = MetricCard("Taxa de Sucesso", "0", "%")
        self.uptime_card = MetricCard("Tempo Ativo", "00:00:00")
        
        metrics_layout.addWidget(self.files_processed_card, 0, 0)
        metrics_layout.addWidget(self.workflows_executed_card, 0, 1)
        metrics_layout.addWidget(self.success_rate_card, 1, 0)
        metrics_layout.addWidget(self.uptime_card, 1, 1)
        
        left_layout.addWidget(metrics_group)
        
        # Component status
        status_group = QGroupBox("Status dos Componentes")
        status_layout = QVBoxLayout(status_group)
        
        self.component_status = ComponentStatusWidget()
        status_layout.addWidget(self.component_status)
        
        left_layout.addWidget(status_group)
        
        # Recent activity
        activity_group = QGroupBox("Atividade Recente")
        activity_layout = QVBoxLayout(activity_group)
        
        self.recent_activity = RecentActivityWidget()
        activity_layout.addWidget(self.recent_activity)
        
        left_layout.addWidget(activity_group)
        
        splitter.addWidget(left_panel)
        
        # Right panel - charts and details
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Performance chart
        chart_group = QGroupBox("Performance")
        chart_layout = QVBoxLayout(chart_group)
        
        self.performance_chart = PerformanceChartWidget("Arquivos por Minuto")
        chart_layout.addWidget(self.performance_chart)
        
        right_layout.addWidget(chart_group)
        
        # Error log
        log_group = QGroupBox("Log de Erros")
        log_layout = QVBoxLayout(log_group)
        
        self.error_log = QTextEdit()
        self.error_log.setReadOnly(True)
        self.error_log.setMaximumHeight(150)
        log_layout.addWidget(self.error_log)
        
        right_layout.addWidget(log_group)
        
        # Configuration summary
        config_group = QGroupBox("Configuração Atual")
        config_layout = QVBoxLayout(config_group)
        
        self.config_summary = QTextEdit()
        self.config_summary.setReadOnly(True)
        self.config_summary.setMaximumHeight(200)
        config_layout.addWidget(self.config_summary)
        
        right_layout.addWidget(config_group)
        
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([400, 600])
        
        layout.addWidget(splitter)
        
    def setup_timer(self):
        """Setup automatic refresh timer."""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_dashboard)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
        
        # Performance tracking
        self.last_files_count = 0
        self.last_update_time = datetime.now()
        
    def refresh_dashboard(self):
        """Refresh all dashboard data."""
        if not self.automation_manager:
            return
            
        try:
            # Get current status
            status = self.automation_manager.get_status()
            
            # Update metrics cards
            self.update_metrics(status)
            
            # Update component status
            self.update_component_status(status)
            
            # Update performance chart
            self.update_performance_chart(status)
            
            # Update configuration summary
            self.update_configuration_summary(status)
            
            # Emit refresh signal
            self.refresh_requested.emit()
            
        except Exception as e:
            self.logger.error(f"Error refreshing dashboard: {e}")
            self.add_error_to_log(f"Dashboard refresh error: {e}")
            
    def update_metrics(self, status: Dict[str, Any]):
        """Update metric cards with latest data."""
        stats = status.get("statistics", {})
        
        # Files processed
        files_count = stats.get("total_files_processed", 0)
        self.files_processed_card.update_value(str(files_count))
        
        # Workflows executed
        workflows_count = stats.get("total_workflows_executed", 0)
        self.workflows_executed_card.update_value(str(workflows_count))
        
        # Success rate
        errors = stats.get("errors", 0)
        if files_count > 0:
            success_rate = ((files_count - errors) / files_count) * 100
            self.success_rate_card.update_value(f"{success_rate:.1f}")
            
            # Update status based on success rate
            if success_rate >= 95:
                self.success_rate_card.update_status("success")
            elif success_rate >= 80:
                self.success_rate_card.update_status("warning")
            else:
                self.success_rate_card.update_status("error")
        else:
            self.success_rate_card.update_value("N/A")
            
        # Uptime
        uptime_seconds = stats.get("uptime_seconds", 0)
        if uptime_seconds > 0:
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
            self.uptime_card.update_value(uptime_str)
            self.uptime_card.update_status("active" if status.get("running") else "inactive")
            
    def update_component_status(self, status: Dict[str, Any]):
        """Update component status indicators."""
        components = status.get("components", {})
        
        # Map component status
        for component_id, component_data in components.items():
            if isinstance(component_data, dict):
                is_running = component_data.get("running", False) or component_data.get("is_running", False)
                component_status = "active" if is_running else "inactive"
            else:
                component_status = "active" if component_data else "inactive"
                
            self.component_status.update_component_status(component_id, component_status)
            
    def update_performance_chart(self, status: Dict[str, Any]):
        """Update performance chart with new data."""
        stats = status.get("statistics", {})
        current_files = stats.get("total_files_processed", 0)
        
        # Calculate files per minute
        now = datetime.now()
        time_diff = (now - self.last_update_time).total_seconds() / 60  # Convert to minutes
        
        if time_diff > 0:
            files_diff = current_files - self.last_files_count
            files_per_minute = files_diff / time_diff
            self.performance_chart.add_data_point(files_per_minute)
            
        self.last_files_count = current_files
        self.last_update_time = now
        
    def update_configuration_summary(self, status: Dict[str, Any]):
        """Update configuration summary."""
        config = status.get("configuration", {})
        
        summary_lines = [
            "=== CONFIGURAÇÃO DA AUTOMAÇÃO ===",
            f"Automação Ativa: {'Sim' if status.get('running') else 'Não'}",
            "",
            "=== COMPONENTES HABILITADOS ===",
            f"Monitoramento de Pastas: {'Sim' if config.get('folder_watching_enabled') else 'Não'}",
            f"Monitoramento de Email: {'Sim' if config.get('email_monitoring_enabled') else 'Não'}",
            f"Agendador: {'Sim' if config.get('scheduling_enabled') else 'Não'}",
            f"Motor de Regras: {'Sim' if config.get('rules_enabled') else 'Não'}",
            f"Templates: {'Sim' if config.get('templates_enabled') else 'Não'}",
            "",
            "=== CONFIGURAÇÕES ===",
            f"Delay de Processamento: {config.get('processing_delay', 'N/A')}s",
            f"Tamanho do Lote: {config.get('batch_size', 'N/A')}",
            f"Intervalo de Email: {config.get('email_check_interval', 'N/A')}s",
            f"Detecção Automática de Templates: {'Sim' if config.get('auto_template_detection') else 'Não'}",
        ]
        
        # Add watched folders
        watch_folders = config.get('watch_folders', [])
        if watch_folders:
            summary_lines.extend([
                "",
                "=== PASTAS MONITORADAS ==="
            ])
            for folder in watch_folders:
                summary_lines.append(f"• {folder}")
                
        self.config_summary.setPlainText("\n".join(summary_lines))
        
    def add_activity(self, activity: str, status: str = "info"):
        """Add activity to recent activity list."""
        self.recent_activity.add_activity(datetime.now(), activity, status)
        
    def add_error_to_log(self, error_message: str):
        """Add error to error log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {error_message}\n"
        self.error_log.append(log_entry)
        
        # Keep only last 1000 characters
        text = self.error_log.toPlainText()
        if len(text) > 1000:
            lines = text.split('\n')
            self.error_log.setPlainText('\n'.join(lines[-20:]))  # Keep last 20 lines
            
    def set_automation_manager(self, manager: AutomationManager):
        """Set the automation manager."""
        self.automation_manager = manager
        self.refresh_dashboard()


# Factory function
def create_automation_dashboard(automation_manager: Optional[AutomationManager] = None) -> AutomationDashboard:
    """Factory function to create automation dashboard."""
    return AutomationDashboard(automation_manager)


# Fallback for when PyQt6 is not available
class AutomationDashboardFallback:
    """Fallback dashboard for when PyQt6 is not available."""
    
    def __init__(self, automation_manager=None):
        self.automation_manager = automation_manager
        print("AutomationDashboard: PyQt6 not available, using fallback")
        
    def show(self):
        print("Dashboard would be shown here if PyQt6 was available")
        
    def refresh_dashboard(self):
        if self.automation_manager:
            status = self.automation_manager.get_status()
            print(f"Dashboard Status: {status}")
            
    def set_automation_manager(self, manager):
        self.automation_manager = manager


# Use fallback if PyQt6 is not available
if not PYQT_AVAILABLE:
    AutomationDashboard = AutomationDashboardFallback