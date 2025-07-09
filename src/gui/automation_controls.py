"""
Visual automation controls for OCR Enhanced.

This module provides comprehensive visual controls for managing
and configuring the automation system, including folder watching,
scheduling, email monitoring, and workflow management.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QPushButton, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
        QCheckBox, QComboBox, QListWidget, QListWidgetItem,
        QTabWidget, QGroupBox, QScrollArea, QTextEdit,
        QProgressBar, QSlider, QFrame, QSplitter,
        QFileDialog, QMessageBox, QInputDialog,
        QTableWidget, QTableWidgetItem, QHeaderView
    )
    from PyQt6.QtCore import (
        Qt, QTimer, pyqtSignal, QThread, pyqtSlot,
        QPropertyAnimation, QEasingCurve, QRect
    )
    from PyQt6.QtGui import (
        QFont, QPixmap, QIcon, QPalette, QColor,
        QPainter, QPen, QBrush
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    
    # Fallback classes for when PyQt6 is not available
    class QWidget: pass
    class pyqtSignal: 
        def __init__(self, *args): pass
        def emit(self, *args): pass
    class QTimer: pass

from ..automation.automation_manager import AutomationManager, AutomationConfig
from ..automation.folder_watcher import WatcherConfig
from ..automation.workflows import Workflow, WorkflowTrigger, WorkflowAction, TriggerType, ActionType
from ..automation.scheduler import ScheduledJob, ScheduleType
from ..automation.email_integration import EmailAccount, EmailFilter
from ..automation.rules import ProcessingRule, Condition, RuleAction, OperatorType, ActionType as RuleActionType
from ..utils.logger import get_logger


class StatusIndicator(QWidget):
    """Visual status indicator with colors and animations."""
    
    def __init__(self, label: str = "", parent=None):
        super().__init__(parent)
        self.status = "inactive"  # inactive, active, warning, error
        self.label_text = label
        self.setFixedSize(20, 20)
        
    def set_status(self, status: str):
        """Set status: inactive, active, warning, error."""
        self.status = status
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Color mapping
        colors = {
            "inactive": QColor(128, 128, 128),
            "active": QColor(46, 204, 113),
            "warning": QColor(241, 196, 15),
            "error": QColor(231, 76, 60)
        }
        
        color = colors.get(self.status, colors["inactive"])
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(120), 2))
        
        # Draw circle
        painter.drawEllipse(2, 2, 16, 16)


class AutomationToggleCard(QFrame):
    """Card widget for toggling automation features."""
    
    toggled = pyqtSignal(str, bool)
    
    def __init__(self, title: str, description: str, feature_key: str, parent=None):
        super().__init__(parent)
        self.feature_key = feature_key
        self.setup_ui(title, description)
        
    def setup_ui(self, title: str, description: str):
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: #f9f9f9;
                padding: 10px;
                margin: 5px;
            }
            QFrame:hover {
                background-color: #f0f0f0;
                border-color: #007acc;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Header with title and toggle
        header_layout = QHBoxLayout()
        
        self.status_indicator = StatusIndicator()
        header_layout.addWidget(self.status_indicator)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        self.toggle_switch = QCheckBox()
        self.toggle_switch.toggled.connect(self._on_toggle)
        header_layout.addWidget(self.toggle_switch)
        
        layout.addLayout(header_layout)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label)
        
    def _on_toggle(self, checked: bool):
        self.status_indicator.set_status("active" if checked else "inactive")
        self.toggled.emit(self.feature_key, checked)
        
    def set_enabled(self, enabled: bool):
        self.toggle_switch.setChecked(enabled)
        self.status_indicator.set_status("active" if enabled else "inactive")


class FolderWatcherControls(QWidget):
    """Controls for folder watching configuration."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger("folder_watcher_controls")
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Watched folders section
        folders_group = QGroupBox("Pastas Monitoradas")
        folders_layout = QVBoxLayout(folders_group)
        
        # Add folder controls
        add_folder_layout = QHBoxLayout()
        self.folder_path_edit = QLineEdit()
        self.folder_path_edit.setPlaceholderText("Caminho da pasta para monitorar...")
        
        browse_btn = QPushButton("Procurar")
        browse_btn.clicked.connect(self._browse_folder)
        
        add_btn = QPushButton("Adicionar")
        add_btn.clicked.connect(self._add_folder)
        
        add_folder_layout.addWidget(self.folder_path_edit)
        add_folder_layout.addWidget(browse_btn)
        add_folder_layout.addWidget(add_btn)
        
        folders_layout.addLayout(add_folder_layout)
        
        # Folders list
        self.folders_list = QListWidget()
        self.folders_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        folders_layout.addWidget(self.folders_list)
        
        # Remove folder button
        remove_btn = QPushButton("Remover Selecionada")
        remove_btn.clicked.connect(self._remove_folder)
        folders_layout.addWidget(remove_btn)
        
        layout.addWidget(folders_group)
        
        # Configuration section
        config_group = QGroupBox("Configurações")
        config_layout = QGridLayout(config_group)
        
        # Processing delay
        config_layout.addWidget(QLabel("Delay de Processamento (s):"), 0, 0)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.1, 60.0)
        self.delay_spin.setValue(2.0)
        self.delay_spin.setSingleStep(0.5)
        config_layout.addWidget(self.delay_spin, 0, 1)
        
        # Batch size
        config_layout.addWidget(QLabel("Tamanho do Lote:"), 1, 0)
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 100)
        self.batch_size_spin.setValue(5)
        config_layout.addWidget(self.batch_size_spin, 1, 1)
        
        # Max retries
        config_layout.addWidget(QLabel("Max Tentativas:"), 2, 0)
        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(1, 10)
        self.retries_spin.setValue(3)
        config_layout.addWidget(self.retries_spin, 2, 1)
        
        # Recursive watching
        self.recursive_check = QCheckBox("Monitoramento Recursivo")
        self.recursive_check.setChecked(True)
        config_layout.addWidget(self.recursive_check, 3, 0, 1, 2)
        
        layout.addWidget(config_group)
        
    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
        if folder:
            self.folder_path_edit.setText(folder)
            
    def _add_folder(self):
        folder_path = self.folder_path_edit.text().strip()
        if folder_path and Path(folder_path).exists():
            self.folders_list.addItem(folder_path)
            self.folder_path_edit.clear()
        else:
            QMessageBox.warning(self, "Erro", "Pasta inválida ou não existe")
            
    def _remove_folder(self):
        current_row = self.folders_list.currentRow()
        if current_row >= 0:
            self.folders_list.takeItem(current_row)
            
    def get_configuration(self) -> Dict[str, Any]:
        """Get current folder watcher configuration."""
        folders = []
        for i in range(self.folders_list.count()):
            folders.append(self.folders_list.item(i).text())
            
        return {
            "watch_folders": folders,
            "processing_delay": self.delay_spin.value(),
            "batch_size": self.batch_size_spin.value(),
            "max_retries": self.retries_spin.value(),
            "recursive_watching": self.recursive_check.isChecked()
        }
        
    def set_configuration(self, config: Dict[str, Any]):
        """Set folder watcher configuration."""
        self.folders_list.clear()
        for folder in config.get("watch_folders", []):
            self.folders_list.addItem(folder)
            
        self.delay_spin.setValue(config.get("processing_delay", 2.0))
        self.batch_size_spin.setValue(config.get("batch_size", 5))
        self.retries_spin.setValue(config.get("max_retries", 3))
        self.recursive_check.setChecked(config.get("recursive_watching", True))


class SchedulerControls(QWidget):
    """Controls for scheduling configuration."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Jobs list
        jobs_group = QGroupBox("Trabalhos Agendados")
        jobs_layout = QVBoxLayout(jobs_group)
        
        # Jobs table
        self.jobs_table = QTableWidget()
        self.jobs_table.setColumnCount(6)
        self.jobs_table.setHorizontalHeaderLabels([
            "Nome", "Tipo", "Agendamento", "Próxima Execução", "Status", "Ações"
        ])
        
        header = self.jobs_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        jobs_layout.addWidget(self.jobs_table)
        
        # Job controls
        job_controls_layout = QHBoxLayout()
        
        add_job_btn = QPushButton("Novo Trabalho")
        add_job_btn.clicked.connect(self._add_job)
        
        edit_job_btn = QPushButton("Editar")
        edit_job_btn.clicked.connect(self._edit_job)
        
        delete_job_btn = QPushButton("Excluir")
        delete_job_btn.clicked.connect(self._delete_job)
        
        run_now_btn = QPushButton("Executar Agora")
        run_now_btn.clicked.connect(self._run_job_now)
        
        job_controls_layout.addWidget(add_job_btn)
        job_controls_layout.addWidget(edit_job_btn)
        job_controls_layout.addWidget(delete_job_btn)
        job_controls_layout.addStretch()
        job_controls_layout.addWidget(run_now_btn)
        
        jobs_layout.addLayout(job_controls_layout)
        layout.addWidget(jobs_group)
        
        # Quick schedules
        quick_group = QGroupBox("Agendamentos Rápidos")
        quick_layout = QGridLayout(quick_group)
        
        # Daily processing
        daily_btn = QPushButton("Processamento Diário")
        daily_btn.clicked.connect(self._create_daily_job)
        quick_layout.addWidget(daily_btn, 0, 0)
        
        # Hourly during business hours
        business_btn = QPushButton("Horário Comercial")
        business_btn.clicked.connect(self._create_business_hours_job)
        quick_layout.addWidget(business_btn, 0, 1)
        
        # Weekly report
        weekly_btn = QPushButton("Relatório Semanal")
        weekly_btn.clicked.connect(self._create_weekly_report)
        quick_layout.addWidget(weekly_btn, 1, 0)
        
        # Monthly cleanup
        cleanup_btn = QPushButton("Limpeza Mensal")
        cleanup_btn.clicked.connect(self._create_monthly_cleanup)
        quick_layout.addWidget(cleanup_btn, 1, 1)
        
        layout.addWidget(quick_group)
        
    def _add_job(self):
        # TODO: Open job creation dialog
        QMessageBox.information(self, "Info", "Dialog de criação de trabalho será implementado")
        
    def _edit_job(self):
        current_row = self.jobs_table.currentRow()
        if current_row >= 0:
            QMessageBox.information(self, "Info", "Dialog de edição será implementado")
            
    def _delete_job(self):
        current_row = self.jobs_table.currentRow()
        if current_row >= 0:
            reply = QMessageBox.question(
                self, "Confirmar", "Excluir trabalho selecionado?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.jobs_table.removeRow(current_row)
                
    def _run_job_now(self):
        current_row = self.jobs_table.currentRow()
        if current_row >= 0:
            QMessageBox.information(self, "Info", "Executando trabalho...")
            
    def _create_daily_job(self):
        QMessageBox.information(self, "Info", "Criando trabalho diário...")
        
    def _create_business_hours_job(self):
        QMessageBox.information(self, "Info", "Criando trabalho horário comercial...")
        
    def _create_weekly_report(self):
        QMessageBox.information(self, "Info", "Criando relatório semanal...")
        
    def _create_monthly_cleanup(self):
        QMessageBox.information(self, "Info", "Criando limpeza mensal...")


class EmailControls(QWidget):
    """Controls for email integration."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Email accounts
        accounts_group = QGroupBox("Contas de Email")
        accounts_layout = QVBoxLayout(accounts_group)
        
        # Accounts list
        self.accounts_list = QListWidget()
        accounts_layout.addWidget(self.accounts_list)
        
        # Account controls
        account_controls = QHBoxLayout()
        
        add_account_btn = QPushButton("Adicionar Conta")
        add_account_btn.clicked.connect(self._add_account)
        
        edit_account_btn = QPushButton("Editar")
        edit_account_btn.clicked.connect(self._edit_account)
        
        remove_account_btn = QPushButton("Remover")
        remove_account_btn.clicked.connect(self._remove_account)
        
        test_account_btn = QPushButton("Testar Conexão")
        test_account_btn.clicked.connect(self._test_account)
        
        account_controls.addWidget(add_account_btn)
        account_controls.addWidget(edit_account_btn)
        account_controls.addWidget(remove_account_btn)
        account_controls.addStretch()
        account_controls.addWidget(test_account_btn)
        
        accounts_layout.addLayout(account_controls)
        layout.addWidget(accounts_group)
        
        # Email filters
        filters_group = QGroupBox("Filtros de Email")
        filters_layout = QVBoxLayout(filters_group)
        
        # Filters list
        self.filters_list = QListWidget()
        filters_layout.addWidget(self.filters_list)
        
        # Filter controls
        filter_controls = QHBoxLayout()
        
        add_filter_btn = QPushButton("Novo Filtro")
        add_filter_btn.clicked.connect(self._add_filter)
        
        edit_filter_btn = QPushButton("Editar")
        edit_filter_btn.clicked.connect(self._edit_filter)
        
        remove_filter_btn = QPushButton("Remover")
        remove_filter_btn.clicked.connect(self._remove_filter)
        
        filter_controls.addWidget(add_filter_btn)
        filter_controls.addWidget(edit_filter_btn)
        filter_controls.addWidget(remove_filter_btn)
        filter_controls.addStretch()
        
        filters_layout.addLayout(filter_controls)
        layout.addWidget(filters_group)
        
        # Quick filters
        quick_filters_group = QGroupBox("Filtros Rápidos")
        quick_filters_layout = QGridLayout(quick_filters_group)
        
        invoice_filter_btn = QPushButton("Filtro de Faturas")
        invoice_filter_btn.clicked.connect(self._create_invoice_filter)
        quick_filters_layout.addWidget(invoice_filter_btn, 0, 0)
        
        receipt_filter_btn = QPushButton("Filtro de Recibos")
        receipt_filter_btn.clicked.connect(self._create_receipt_filter)
        quick_filters_layout.addWidget(receipt_filter_btn, 0, 1)
        
        contract_filter_btn = QPushButton("Filtro de Contratos")
        contract_filter_btn.clicked.connect(self._create_contract_filter)
        quick_filters_layout.addWidget(contract_filter_btn, 1, 0)
        
        general_filter_btn = QPushButton("Filtro Geral")
        general_filter_btn.clicked.connect(self._create_general_filter)
        quick_filters_layout.addWidget(general_filter_btn, 1, 1)
        
        layout.addWidget(quick_filters_group)
        
    def _add_account(self):
        QMessageBox.information(self, "Info", "Dialog de nova conta será implementado")
        
    def _edit_account(self):
        QMessageBox.information(self, "Info", "Dialog de edição de conta será implementado")
        
    def _remove_account(self):
        current_row = self.accounts_list.currentRow()
        if current_row >= 0:
            reply = QMessageBox.question(
                self, "Confirmar", "Remover conta selecionada?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.accounts_list.takeItem(current_row)
                
    def _test_account(self):
        QMessageBox.information(self, "Info", "Testando conexão...")
        
    def _add_filter(self):
        QMessageBox.information(self, "Info", "Dialog de novo filtro será implementado")
        
    def _edit_filter(self):
        QMessageBox.information(self, "Info", "Dialog de edição de filtro será implementado")
        
    def _remove_filter(self):
        current_row = self.filters_list.currentRow()
        if current_row >= 0:
            self.filters_list.takeItem(current_row)
            
    def _create_invoice_filter(self):
        QMessageBox.information(self, "Info", "Criando filtro de faturas...")
        
    def _create_receipt_filter(self):
        QMessageBox.information(self, "Info", "Criando filtro de recibos...")
        
    def _create_contract_filter(self):
        QMessageBox.information(self, "Info", "Criando filtro de contratos...")
        
    def _create_general_filter(self):
        QMessageBox.information(self, "Info", "Criando filtro geral...")


class AutomationControls(QWidget):
    """Main automation controls widget with tabs for different features."""
    
    automation_changed = pyqtSignal(dict)
    
    def __init__(self, automation_manager: Optional[AutomationManager] = None, parent=None):
        super().__init__(parent)
        self.automation_manager = automation_manager
        self.logger = get_logger("automation_controls")
        
        if not PYQT_AVAILABLE:
            self.logger.warning("PyQt6 not available, using fallback implementation")
            return
            
        self.setup_ui()
        self.setup_timer()
        
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Header with main automation toggle
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Controles de Automação")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Master automation toggle
        self.master_toggle = QPushButton("Iniciar Automação")
        self.master_toggle.setCheckable(True)
        self.master_toggle.clicked.connect(self._toggle_automation)
        self.master_toggle.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: #dc3545;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:checked:hover {
                background-color: #c82333;
            }
        """)
        header_layout.addWidget(self.master_toggle)
        
        layout.addLayout(header_layout)
        
        # Status indicators row
        status_layout = QHBoxLayout()
        
        # Feature toggles
        self.folder_watcher_card = AutomationToggleCard(
            "Monitoramento de Pastas",
            "Monitora pastas em tempo real para novos documentos",
            "folder_watching_enabled"
        )
        self.folder_watcher_card.toggled.connect(self._on_feature_toggle)
        
        self.email_card = AutomationToggleCard(
            "Monitoramento de Email",
            "Processa automaticamente anexos de email",
            "email_monitoring_enabled"
        )
        self.email_card.toggled.connect(self._on_feature_toggle)
        
        self.scheduler_card = AutomationToggleCard(
            "Agendador",
            "Executa processamentos em horários específicos",
            "scheduling_enabled"
        )
        self.scheduler_card.toggled.connect(self._on_feature_toggle)
        
        self.rules_card = AutomationToggleCard(
            "Motor de Regras",
            "Aplica regras condicionais ao processamento",
            "rules_enabled"
        )
        self.rules_card.toggled.connect(self._on_feature_toggle)
        
        status_layout.addWidget(self.folder_watcher_card)
        status_layout.addWidget(self.email_card)
        status_layout.addWidget(self.scheduler_card)
        status_layout.addWidget(self.rules_card)
        
        layout.addLayout(status_layout)
        
        # Tabs for detailed controls
        self.tabs = QTabWidget()
        
        # Folder watcher tab
        self.folder_controls = FolderWatcherControls()
        self.tabs.addTab(self.folder_controls, "Pastas")
        
        # Scheduler tab
        self.scheduler_controls = SchedulerControls()
        self.tabs.addTab(self.scheduler_controls, "Agendamento")
        
        # Email tab
        self.email_controls = EmailControls()
        self.tabs.addTab(self.email_controls, "Email")
        
        # Rules tab (placeholder for now)
        rules_widget = QWidget()
        rules_layout = QVBoxLayout(rules_widget)
        rules_layout.addWidget(QLabel("Controles de regras serão implementados"))
        self.tabs.addTab(rules_widget, "Regras")
        
        # Statistics tab
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        stats_layout.addWidget(self.stats_text)
        self.tabs.addTab(stats_widget, "Estatísticas")
        
        layout.addWidget(self.tabs)
        
    def setup_timer(self):
        """Setup timer for updating status."""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_status)
        self.update_timer.start(5000)  # Update every 5 seconds
        
    def _toggle_automation(self, checked: bool):
        """Toggle main automation on/off."""
        if not self.automation_manager:
            QMessageBox.warning(self, "Erro", "Gerenciador de automação não configurado")
            return
            
        try:
            if checked:
                self.automation_manager.start_automation()
                self.master_toggle.setText("Parar Automação")
                self.logger.info("Automation started via GUI")
            else:
                self.automation_manager.stop_automation()
                self.master_toggle.setText("Iniciar Automação")
                self.logger.info("Automation stopped via GUI")
                
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao controlar automação: {e}")
            self.master_toggle.setChecked(not checked)
            
    def _on_feature_toggle(self, feature_key: str, enabled: bool):
        """Handle feature toggle."""
        if not self.automation_manager:
            return
            
        config = self.automation_manager.automation_config
        setattr(config, feature_key, enabled)
        
        # Update configuration
        self.automation_manager.update_configuration(config)
        
        # Emit signal for external handlers
        self.automation_changed.emit({feature_key: enabled})
        
        self.logger.info(f"Feature {feature_key} set to {enabled}")
        
    def _update_status(self):
        """Update status indicators and statistics."""
        if not self.automation_manager:
            return
            
        try:
            # Update master toggle
            is_running = self.automation_manager.running
            self.master_toggle.setChecked(is_running)
            self.master_toggle.setText("Parar Automação" if is_running else "Iniciar Automação")
            
            # Update feature cards
            config = self.automation_manager.automation_config
            self.folder_watcher_card.set_enabled(config.folder_watching_enabled)
            self.email_card.set_enabled(config.email_monitoring_enabled)
            self.scheduler_card.set_enabled(config.scheduling_enabled)
            self.rules_card.set_enabled(config.rules_enabled)
            
            # Update statistics
            status = self.automation_manager.get_status()
            stats_text = self._format_statistics(status)
            self.stats_text.setPlainText(stats_text)
            
        except Exception as e:
            self.logger.error(f"Error updating status: {e}")
            
    def _format_statistics(self, status: Dict[str, Any]) -> str:
        """Format statistics for display."""
        stats_lines = [
            "=== STATUS DA AUTOMAÇÃO ===",
            f"Executando: {'Sim' if status['running'] else 'Não'}",
            "",
            "=== ESTATÍSTICAS ===",
            f"Arquivos Processados: {status['statistics']['total_files_processed']}",
            f"Workflows Executados: {status['statistics']['total_workflows_executed']}",
            f"Regras Aplicadas: {status['statistics']['total_rules_applied']}",
            f"Erros: {status['statistics']['errors']}",
            ""
        ]
        
        if status['statistics']['start_time']:
            uptime = status['statistics'].get('uptime_seconds', 0)
            hours, remainder = divmod(uptime, 3600)
            minutes, seconds = divmod(remainder, 60)
            stats_lines.append(f"Tempo Ativo: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}")
            
        stats_lines.extend([
            "",
            "=== COMPONENTES ==="
        ])
        
        for component, data in status.get('components', {}).items():
            stats_lines.append(f"{component.replace('_', ' ').title()}:")
            if isinstance(data, dict):
                for key, value in data.items():
                    stats_lines.append(f"  {key}: {value}")
            else:
                stats_lines.append(f"  Status: {data}")
            stats_lines.append("")
            
        return "\n".join(stats_lines)
        
    def set_automation_manager(self, manager: AutomationManager):
        """Set the automation manager."""
        self.automation_manager = manager
        self._update_status()
        
    def get_current_config(self) -> Dict[str, Any]:
        """Get current configuration from UI."""
        return {
            "folder_watcher": self.folder_controls.get_configuration(),
            # Add other configurations as they're implemented
        }


# Factory function for easy creation
def create_automation_controls(automation_manager: Optional[AutomationManager] = None) -> AutomationControls:
    """Factory function to create automation controls."""
    return AutomationControls(automation_manager)


# Fallback for when PyQt6 is not available
class AutomationControlsFallback:
    """Fallback automation controls for when PyQt6 is not available."""
    
    def __init__(self, automation_manager=None):
        self.automation_manager = automation_manager
        print("AutomationControls: PyQt6 not available, using fallback")
        
    def show(self):
        print("GUI controls would be shown here if PyQt6 was available")
        
    def set_automation_manager(self, manager):
        self.automation_manager = manager


# Use fallback if PyQt6 is not available
if not PYQT_AVAILABLE:
    AutomationControls = AutomationControlsFallback