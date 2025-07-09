"""
Visual workflow editor for OCR Enhanced automation.

This module provides a drag-and-drop workflow editor allowing users
to create, modify, and manage automation workflows visually.
"""

import sys
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import asdict

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QPushButton, QLabel, QLineEdit, QTextEdit, QComboBox,
        QListWidget, QListWidgetItem, QScrollArea, QFrame,
        QGroupBox, QSplitter, QTabWidget, QDialog,
        QDialogButtonBox, QFormLayout, QSpinBox,
        QCheckBox, QMessageBox, QFileDialog, QGraphicsView,
        QGraphicsScene, QGraphicsItem, QGraphicsRectItem,
        QGraphicsTextItem, QGraphicsLineItem, QApplication
    )
    from PyQt6.QtCore import (
        Qt, QRectF, QPointF, pyqtSignal, QMimeData,
        QTimer, QPropertyAnimation, QEasingCurve
    )
    from PyQt6.QtGui import (
        QFont, QPainter, QPen, QBrush, QColor, QPixmap,
        QDrag, QDragEnterEvent, QDragMoveEvent, QDropEvent
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    QWidget = object
    QDialog = object
    pyqtSignal = lambda: None

from ..automation.workflows import (
    Workflow, WorkflowTrigger, WorkflowAction, WorkflowManager,
    TriggerType, ActionType, WorkflowStatus
)
from ..utils.logger import get_logger
from .themes import get_current_colors


class WorkflowNode(QGraphicsRectItem):
    """Visual representation of a workflow node."""
    
    def __init__(self, node_type: str, title: str, x: float = 0, y: float = 0):
        super().__init__(0, 0, 200, 80)
        self.node_type = node_type
        self.title = title
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        
        # Node properties
        self.properties = {}
        self.connections = []
        
        # Visual styling
        self.setup_appearance()
        
        # Text item for title
        self.text_item = QGraphicsTextItem(title, self)
        self.text_item.setPos(10, 25)
        self.text_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        
    def setup_appearance(self):
        """Setup node appearance based on type."""
        colors = get_current_colors()
        
        # Color mapping for different node types
        type_colors = {
            "trigger": colors["success"],
            "action": colors["primary"],
            "condition": colors["warning"],
            "output": colors["info"]
        }
        
        base_color = type_colors.get(self.node_type, colors["surface"])
        
        self.setBrush(QBrush(QColor(base_color)))
        self.setPen(QPen(QColor(colors["border"]), 2))
        
    def mousePressEvent(self, event):
        """Handle mouse press for node selection."""
        super().mousePressEvent(event)
        
    def paint(self, painter, option, widget):
        """Custom paint method for rounded corners."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw rounded rectangle
        rect = self.boundingRect()
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRoundedRect(rect, 10, 10)
        
        # Draw connection points
        point_size = 6
        colors = get_current_colors()
        
        # Input point (left side)
        if self.node_type != "trigger":
            painter.setBrush(QBrush(QColor(colors["surface"])))
            painter.setPen(QPen(QColor(colors["border"]), 1))
            painter.drawEllipse(int(-point_size/2), int(rect.height()/2 - point_size/2), 
                              point_size, point_size)
        
        # Output point (right side)
        if self.node_type != "output":
            painter.setBrush(QBrush(QColor(colors["surface"])))
            painter.setPen(QPen(QColor(colors["border"]), 1))
            painter.drawEllipse(int(rect.width() - point_size/2), int(rect.height()/2 - point_size/2),
                              point_size, point_size)
    
    def get_input_point(self) -> QPointF:
        """Get input connection point in scene coordinates."""
        return self.mapToScene(0, self.boundingRect().height() / 2)
    
    def get_output_point(self) -> QPointF:
        """Get output connection point in scene coordinates."""
        return self.mapToScene(self.boundingRect().width(), self.boundingRect().height() / 2)


class WorkflowConnection(QGraphicsLineItem):
    """Visual connection between workflow nodes."""
    
    def __init__(self, start_node: WorkflowNode, end_node: WorkflowNode):
        super().__init__()
        self.start_node = start_node
        self.end_node = end_node
        self.update_line()
        
        # Visual styling
        colors = get_current_colors()
        self.setPen(QPen(QColor(colors["primary"]), 3))
        
    def update_line(self):
        """Update line position based on node positions."""
        start_point = self.start_node.get_output_point()
        end_point = self.end_node.get_input_point()
        self.setLine(start_point.x(), start_point.y(), end_point.x(), end_point.y())


class NodePropertyDialog(QDialog):
    """Dialog for editing node properties."""
    
    def __init__(self, node: WorkflowNode, parent=None):
        super().__init__(parent)
        self.node = node
        self.setup_ui()
        
    def setup_ui(self):
        """Setup property dialog UI."""
        self.setWindowTitle(f"Propriedades: {self.node.title}")
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # Form layout for properties
        form_layout = QFormLayout()
        
        # Title
        self.title_edit = QLineEdit(self.node.title)
        form_layout.addRow("Título:", self.title_edit)
        
        # Type-specific properties
        if self.node.node_type == "trigger":
            self.setup_trigger_properties(form_layout)
        elif self.node.node_type == "action":
            self.setup_action_properties(form_layout)
        elif self.node.node_type == "condition":
            self.setup_condition_properties(form_layout)
            
        layout.addLayout(form_layout)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def setup_trigger_properties(self, form_layout):
        """Setup trigger-specific properties."""
        # Trigger type
        self.trigger_type_combo = QComboBox()
        self.trigger_type_combo.addItems([
            "FILE_ADDED", "SCHEDULE", "EMAIL_RECEIVED", 
            "TEMPLATE_MATCHED", "WEBHOOK", "MANUAL"
        ])
        form_layout.addRow("Tipo de Trigger:", self.trigger_type_combo)
        
        # File patterns (for FILE_ADDED)
        self.file_patterns_edit = QLineEdit()
        self.file_patterns_edit.setPlaceholderText("*.pdf, *.png, *.jpg")
        form_layout.addRow("Padrões de Arquivo:", self.file_patterns_edit)
        
        # Schedule expression (for SCHEDULE)
        self.schedule_edit = QLineEdit()
        self.schedule_edit.setPlaceholderText("0 9 * * *")
        form_layout.addRow("Expressão CRON:", self.schedule_edit)
        
    def setup_action_properties(self, form_layout):
        """Setup action-specific properties."""
        # Action type
        self.action_type_combo = QComboBox()
        self.action_type_combo.addItems([
            "OCR_PROCESS", "EXTRACT_FIELDS", "MOVE_FILE",
            "COPY_FILE", "SEND_EMAIL", "WEBHOOK", "SCRIPT"
        ])
        form_layout.addRow("Tipo de Ação:", self.action_type_combo)
        
        # Parameters
        self.parameters_edit = QTextEdit()
        self.parameters_edit.setPlaceholderText("Parâmetros em formato JSON")
        form_layout.addRow("Parâmetros:", self.parameters_edit)
        
        # Timeout
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 3600)
        self.timeout_spin.setValue(300)
        self.timeout_spin.setSuffix(" segundos")
        form_layout.addRow("Timeout:", self.timeout_spin)
        
    def setup_condition_properties(self, form_layout):
        """Setup condition-specific properties."""
        # Condition expression
        self.condition_edit = QLineEdit()
        self.condition_edit.setPlaceholderText("field == 'value'")
        form_layout.addRow("Condição:", self.condition_edit)
        
        # True path
        self.true_path_edit = QLineEdit()
        self.true_path_edit.setPlaceholderText("Nome do próximo nó se verdadeiro")
        form_layout.addRow("Caminho Verdadeiro:", self.true_path_edit)
        
        # False path
        self.false_path_edit = QLineEdit()
        self.false_path_edit.setPlaceholderText("Nome do próximo nó se falso")
        form_layout.addRow("Caminho Falso:", self.false_path_edit)
        
    def get_properties(self) -> Dict[str, Any]:
        """Get properties from dialog."""
        properties = {"title": self.title_edit.text()}
        
        if self.node.node_type == "trigger":
            properties.update({
                "trigger_type": self.trigger_type_combo.currentText(),
                "file_patterns": [p.strip() for p in self.file_patterns_edit.text().split(",") if p.strip()],
                "schedule": self.schedule_edit.text()
            })
        elif self.node.node_type == "action":
            properties.update({
                "action_type": self.action_type_combo.currentText(),
                "parameters": self.parameters_edit.toPlainText(),
                "timeout": self.timeout_spin.value()
            })
        elif self.node.node_type == "condition":
            properties.update({
                "condition": self.condition_edit.text(),
                "true_path": self.true_path_edit.text(),
                "false_path": self.false_path_edit.text()
            })
            
        return properties


class WorkflowCanvas(QGraphicsView):
    """Canvas for visual workflow editing."""
    
    node_selected = pyqtSignal(WorkflowNode)
    workflow_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Canvas properties
        self.nodes: List[WorkflowNode] = []
        self.connections: List[WorkflowConnection] = []
        self.selected_node: Optional[WorkflowNode] = None
        self.connection_mode = False
        self.connection_start_node: Optional[WorkflowNode] = None
        
        self.setup_canvas()
        
    def setup_canvas(self):
        """Setup canvas properties."""
        # Set scene size
        self.scene.setSceneRect(0, 0, 2000, 1500)
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        # Visual properties
        colors = get_current_colors()
        self.setStyleSheet(f"background-color: {colors['background_alt']};")
        
        # Grid background
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        
    def add_node(self, node_type: str, title: str, x: float = 100, y: float = 100) -> WorkflowNode:
        """Add a new node to the canvas."""
        node = WorkflowNode(node_type, title, x, y)
        self.scene.addItem(node)
        self.nodes.append(node)
        
        # Connect selection signal
        self.scene.selectionChanged.connect(self.on_selection_changed)
        
        self.workflow_changed.emit()
        return node
        
    def remove_node(self, node: WorkflowNode):
        """Remove a node from the canvas."""
        # Remove connections involving this node
        connections_to_remove = [
            conn for conn in self.connections 
            if conn.start_node == node or conn.end_node == node
        ]
        
        for conn in connections_to_remove:
            self.remove_connection(conn)
            
        # Remove node
        self.scene.removeItem(node)
        if node in self.nodes:
            self.nodes.remove(node)
            
        self.workflow_changed.emit()
        
    def add_connection(self, start_node: WorkflowNode, end_node: WorkflowNode) -> WorkflowConnection:
        """Add a connection between two nodes."""
        # Check if connection already exists
        for conn in self.connections:
            if conn.start_node == start_node and conn.end_node == end_node:
                return conn
                
        connection = WorkflowConnection(start_node, end_node)
        self.scene.addItem(connection)
        self.connections.append(connection)
        
        # Update connection when nodes move
        start_node.connections.append(connection)
        end_node.connections.append(connection)
        
        self.workflow_changed.emit()
        return connection
        
    def remove_connection(self, connection: WorkflowConnection):
        """Remove a connection."""
        self.scene.removeItem(connection)
        if connection in self.connections:
            self.connections.remove(connection)
            
        # Remove from node connections
        if connection in connection.start_node.connections:
            connection.start_node.connections.remove(connection)
        if connection in connection.end_node.connections:
            connection.end_node.connections.remove(connection)
            
        self.workflow_changed.emit()
        
    def on_selection_changed(self):
        """Handle selection changes."""
        selected_items = self.scene.selectedItems()
        if selected_items and isinstance(selected_items[0], WorkflowNode):
            self.selected_node = selected_items[0]
            self.node_selected.emit(self.selected_node)
        else:
            self.selected_node = None
            
    def start_connection_mode(self):
        """Start connection mode for linking nodes."""
        self.connection_mode = True
        self.setCursor(Qt.CursorShape.CrossCursor)
        
    def end_connection_mode(self):
        """End connection mode."""
        self.connection_mode = False
        self.connection_start_node = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        super().mousePressEvent(event)
        
        if self.connection_mode:
            item = self.itemAt(event.pos())
            if isinstance(item, WorkflowNode):
                if self.connection_start_node is None:
                    self.connection_start_node = item
                else:
                    if item != self.connection_start_node:
                        self.add_connection(self.connection_start_node, item)
                    self.end_connection_mode()
                    
    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Delete and self.selected_node:
            self.remove_node(self.selected_node)
        elif event.key() == Qt.Key.Key_Escape:
            self.end_connection_mode()
        else:
            super().keyPressEvent(event)
            
    def clear_workflow(self):
        """Clear all nodes and connections."""
        self.scene.clear()
        self.nodes.clear()
        self.connections.clear()
        self.workflow_changed.emit()
        
    def get_workflow_data(self) -> Dict[str, Any]:
        """Get workflow data for saving."""
        workflow_data = {
            "nodes": [],
            "connections": []
        }
        
        # Export nodes
        for node in self.nodes:
            node_data = {
                "id": id(node),
                "type": node.node_type,
                "title": node.title,
                "x": node.pos().x(),
                "y": node.pos().y(),
                "properties": node.properties
            }
            workflow_data["nodes"].append(node_data)
            
        # Export connections
        for conn in self.connections:
            conn_data = {
                "start_node_id": id(conn.start_node),
                "end_node_id": id(conn.end_node)
            }
            workflow_data["connections"].append(conn_data)
            
        return workflow_data
        
    def load_workflow_data(self, workflow_data: Dict[str, Any]):
        """Load workflow from data."""
        self.clear_workflow()
        
        # Create nodes first
        node_id_map = {}
        for node_data in workflow_data.get("nodes", []):
            node = self.add_node(
                node_data["type"],
                node_data["title"],
                node_data["x"],
                node_data["y"]
            )
            node.properties = node_data.get("properties", {})
            node_id_map[node_data["id"]] = node
            
        # Create connections
        for conn_data in workflow_data.get("connections", []):
            start_node = node_id_map.get(conn_data["start_node_id"])
            end_node = node_id_map.get(conn_data["end_node_id"])
            if start_node and end_node:
                self.add_connection(start_node, end_node)


class NodePalette(QWidget):
    """Palette of available workflow nodes."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup palette UI."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Paleta de Nós")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Node categories
        categories = {
            "Triggers": [
                ("trigger", "Arquivo Adicionado", "FILE_ADDED"),
                ("trigger", "Agendamento", "SCHEDULE"),
                ("trigger", "Email Recebido", "EMAIL_RECEIVED"),
                ("trigger", "Template Identificado", "TEMPLATE_MATCHED")
            ],
            "Actions": [
                ("action", "Processar OCR", "OCR_PROCESS"),
                ("action", "Extrair Campos", "EXTRACT_FIELDS"),
                ("action", "Mover Arquivo", "MOVE_FILE"),
                ("action", "Enviar Email", "SEND_EMAIL"),
                ("action", "Webhook", "WEBHOOK")
            ],
            "Control": [
                ("condition", "Condição", "CONDITION"),
                ("output", "Saída", "OUTPUT")
            ]
        }
        
        for category_name, nodes in categories.items():
            # Category group
            group = QGroupBox(category_name)
            group_layout = QVBoxLayout(group)
            
            for node_type, title, node_id in nodes:
                btn = QPushButton(title)
                btn.setProperty("node_type", node_type)
                btn.setProperty("node_title", title)
                btn.setProperty("node_id", node_id)
                btn.clicked.connect(self.on_node_button_clicked)
                group_layout.addWidget(btn)
                
            layout.addWidget(group)
            
        layout.addStretch()
        
    def on_node_button_clicked(self):
        """Handle node button clicks."""
        sender = self.sender()
        node_type = sender.property("node_type")
        node_title = sender.property("node_title")
        
        # Emit signal to parent to add node
        parent = self.parent()
        if hasattr(parent, 'add_node_to_canvas'):
            parent.add_node_to_canvas(node_type, node_title)


class WorkflowEditor(QWidget):
    """Main workflow editor widget."""
    
    workflow_saved = pyqtSignal(dict)
    
    def __init__(self, workflow_manager: Optional[WorkflowManager] = None, parent=None):
        super().__init__(parent)
        self.workflow_manager = workflow_manager
        self.logger = get_logger("workflow_editor")
        self.current_workflow: Optional[Workflow] = None
        
        if not PYQT_AVAILABLE:
            self.logger.warning("PyQt6 not available, using fallback editor")
            return
            
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the workflow editor UI."""
        layout = QVBoxLayout(self)
        
        # Header with controls
        header_layout = QHBoxLayout()
        
        title = QLabel("Editor de Workflows")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Workflow controls
        new_btn = QPushButton("Novo")
        new_btn.clicked.connect(self.new_workflow)
        header_layout.addWidget(new_btn)
        
        load_btn = QPushButton("Carregar")
        load_btn.clicked.connect(self.load_workflow)
        header_layout.addWidget(load_btn)
        
        save_btn = QPushButton("Salvar")
        save_btn.clicked.connect(self.save_workflow)
        header_layout.addWidget(save_btn)
        
        # Canvas controls
        connect_btn = QPushButton("Conectar Nós")
        connect_btn.clicked.connect(self.start_connection_mode)
        header_layout.addWidget(connect_btn)
        
        validate_btn = QPushButton("Validar")
        validate_btn.clicked.connect(self.validate_workflow)
        header_layout.addWidget(validate_btn)
        
        layout.addLayout(header_layout)
        
        # Main editor area
        editor_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - node palette
        self.node_palette = NodePalette()
        self.node_palette.setMaximumWidth(250)
        editor_splitter.addWidget(self.node_palette)
        
        # Center - workflow canvas
        self.canvas = WorkflowCanvas()
        self.canvas.node_selected.connect(self.on_node_selected)
        self.canvas.workflow_changed.connect(self.on_workflow_changed)
        editor_splitter.addWidget(self.canvas)
        
        # Right panel - properties
        properties_widget = QWidget()
        properties_layout = QVBoxLayout(properties_widget)
        
        properties_title = QLabel("Propriedades")
        properties_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        properties_layout.addWidget(properties_title)
        
        self.properties_area = QScrollArea()
        properties_layout.addWidget(self.properties_area)
        
        properties_widget.setMaximumWidth(300)
        editor_splitter.addWidget(properties_widget)
        
        # Set splitter proportions
        editor_splitter.setSizes([250, 800, 300])
        
        layout.addWidget(editor_splitter)
        
    def add_node_to_canvas(self, node_type: str, title: str):
        """Add a node to the canvas."""
        # Add node at center of visible area
        center_point = self.canvas.mapToScene(
            self.canvas.viewport().rect().center()
        )
        self.canvas.add_node(node_type, title, center_point.x(), center_point.y())
        
    def start_connection_mode(self):
        """Start connection mode."""
        self.canvas.start_connection_mode()
        
    def on_node_selected(self, node: WorkflowNode):
        """Handle node selection."""
        # Show node properties
        self.show_node_properties(node)
        
    def show_node_properties(self, node: WorkflowNode):
        """Show properties for selected node."""
        properties_widget = QWidget()
        properties_layout = QFormLayout(properties_widget)
        
        # Basic properties
        properties_layout.addRow("Tipo:", QLabel(node.node_type))
        properties_layout.addRow("Título:", QLabel(node.title))
        
        # Edit button
        edit_btn = QPushButton("Editar Propriedades")
        edit_btn.clicked.connect(lambda: self.edit_node_properties(node))
        properties_layout.addWidget(edit_btn)
        
        # Delete button
        delete_btn = QPushButton("Excluir Nó")
        delete_btn.clicked.connect(lambda: self.canvas.remove_node(node))
        properties_layout.addWidget(delete_btn)
        
        self.properties_area.setWidget(properties_widget)
        
    def edit_node_properties(self, node: WorkflowNode):
        """Edit node properties."""
        dialog = NodePropertyDialog(node, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            properties = dialog.get_properties()
            node.properties.update(properties)
            if "title" in properties:
                node.title = properties["title"]
                node.text_item.setPlainText(properties["title"])
            self.on_workflow_changed()
            
    def on_workflow_changed(self):
        """Handle workflow changes."""
        # Mark workflow as modified
        pass
        
    def new_workflow(self):
        """Create a new workflow."""
        self.canvas.clear_workflow()
        self.current_workflow = None
        
    def load_workflow(self):
        """Load a workflow from file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Carregar Workflow", "", "JSON Files (*.json)"
        )
        if filename:
            try:
                import json
                with open(filename, 'r', encoding='utf-8') as f:
                    workflow_data = json.load(f)
                self.canvas.load_workflow_data(workflow_data)
                QMessageBox.information(self, "Sucesso", "Workflow carregado com sucesso!")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao carregar workflow: {e}")
                
    def save_workflow(self):
        """Save the current workflow."""
        if not self.canvas.nodes:
            QMessageBox.warning(self, "Aviso", "Não há nós para salvar")
            return
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar Workflow", "", "JSON Files (*.json)"
        )
        if filename:
            try:
                import json
                workflow_data = self.canvas.get_workflow_data()
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(workflow_data, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "Sucesso", "Workflow salvo com sucesso!")
                self.workflow_saved.emit(workflow_data)
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao salvar workflow: {e}")
                
    def validate_workflow(self):
        """Validate the current workflow."""
        issues = []
        
        # Check for nodes
        if not self.canvas.nodes:
            issues.append("Workflow está vazio")
            
        # Check for trigger nodes
        triggers = [n for n in self.canvas.nodes if n.node_type == "trigger"]
        if not triggers:
            issues.append("Workflow deve ter pelo menos um trigger")
            
        # Check for disconnected nodes
        for node in self.canvas.nodes:
            if node.node_type != "trigger" and not any(
                conn.end_node == node for conn in self.canvas.connections
            ):
                issues.append(f"Nó '{node.title}' não está conectado")
                
        # Show validation results
        if issues:
            QMessageBox.warning(self, "Validação", "Problemas encontrados:\n" + "\n".join(issues))
        else:
            QMessageBox.information(self, "Validação", "Workflow válido!")
            
    def set_workflow_manager(self, manager: WorkflowManager):
        """Set the workflow manager."""
        self.workflow_manager = manager


# Factory function
def create_workflow_editor(workflow_manager: Optional[WorkflowManager] = None) -> WorkflowEditor:
    """Factory function to create workflow editor."""
    return WorkflowEditor(workflow_manager)


# Fallback for when PyQt6 is not available
class WorkflowEditorFallback:
    """Fallback workflow editor for when PyQt6 is not available."""
    
    def __init__(self, workflow_manager=None):
        self.workflow_manager = workflow_manager
        print("WorkflowEditor: PyQt6 not available, using fallback")
        
    def show(self):
        print("Workflow editor would be shown here if PyQt6 was available")
        
    def set_workflow_manager(self, manager):
        self.workflow_manager = manager


# Use fallback if PyQt6 is not available
if not PYQT_AVAILABLE:
    WorkflowEditor = WorkflowEditorFallback