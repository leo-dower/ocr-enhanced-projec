"""
Workflow management system for automated OCR processing.

This module provides workflow orchestration, allowing users to define
complex processing pipelines with conditions, actions, and integrations.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, Future

from ..utils.logger import get_logger
from .templates import DocumentTemplate, TemplateManager


class WorkflowStatus(Enum):
    """Workflow execution status."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionType(Enum):
    """Types of workflow actions."""
    OCR_PROCESS = "ocr_process"
    MOVE_FILE = "move_file"
    COPY_FILE = "copy_file"
    DELETE_FILE = "delete_file"
    SEND_EMAIL = "send_email"
    WEBHOOK = "webhook"
    EXTRACT_FIELDS = "extract_fields"
    VALIDATE_DATA = "validate_data"
    CONDITIONAL = "conditional"
    DELAY = "delay"
    CUSTOM_SCRIPT = "custom_script"


class TriggerType(Enum):
    """Types of workflow triggers."""
    FILE_ADDED = "file_added"
    FILE_MODIFIED = "file_modified"
    SCHEDULE = "schedule"
    MANUAL = "manual"
    WEBHOOK = "webhook"
    EMAIL_RECEIVED = "email_received"
    TEMPLATE_MATCHED = "template_matched"


@dataclass
class WorkflowTrigger:
    """Defines when a workflow should be executed."""
    
    trigger_type: TriggerType
    name: str
    enabled: bool = True
    
    # File-based triggers
    watch_paths: List[str] = field(default_factory=list)
    file_patterns: List[str] = field(default_factory=list)
    
    # Schedule-based triggers
    schedule_cron: Optional[str] = None
    schedule_interval: Optional[int] = None  # seconds
    
    # Template-based triggers
    template_names: List[str] = field(default_factory=list)
    confidence_threshold: float = 0.8
    
    # Webhook triggers
    webhook_path: Optional[str] = None
    webhook_secret: Optional[str] = None
    
    # Email triggers
    email_filters: Dict[str, Any] = field(default_factory=dict)
    
    # Condition for trigger activation
    condition: Optional[str] = None  # Python expression
    
    def matches(self, context: Dict[str, Any]) -> bool:
        """Check if trigger conditions are met."""
        if not self.enabled:
            return False
        
        try:
            # Check basic trigger type match
            if self.trigger_type == TriggerType.FILE_ADDED:
                file_path = context.get("file_path", "")
                return any(pattern in file_path for pattern in self.file_patterns)
            
            elif self.trigger_type == TriggerType.TEMPLATE_MATCHED:
                template_confidence = context.get("template_confidence", 0.0)
                template_name = context.get("template_name", "")
                return (template_confidence >= self.confidence_threshold and 
                       template_name in self.template_names)
            
            # Evaluate custom condition if provided
            if self.condition:
                return eval(self.condition, {"__builtins__": {}}, context)
            
            return True
            
        except Exception as e:
            logging.warning(f"Error evaluating trigger condition: {e}")
            return False


@dataclass
class WorkflowAction:
    """Defines an action to be executed in a workflow."""
    
    action_type: ActionType
    name: str
    enabled: bool = True
    
    # Action parameters
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Conditional execution
    condition: Optional[str] = None
    
    # Error handling
    retry_count: int = 0
    retry_delay: float = 1.0
    continue_on_error: bool = False
    
    # Output handling
    output_variable: Optional[str] = None
    
    async def execute(self, context: Dict[str, Any], workflow_manager: 'WorkflowManager') -> Dict[str, Any]:
        """Execute the action with given context."""
        if not self.enabled:
            return {"status": "skipped", "reason": "action disabled"}
        
        # Check condition
        if self.condition and not eval(self.condition, {"__builtins__": {}}, context):
            return {"status": "skipped", "reason": "condition not met"}
        
        logger = get_logger(f"workflow.action.{self.name}")
        logger.info(f"Executing action: {self.name} ({self.action_type.value})")
        
        attempt = 0
        while attempt <= self.retry_count:
            try:
                result = await self._execute_action(context, workflow_manager)
                
                # Store output in context if variable name provided
                if self.output_variable and "output" in result:
                    context[self.output_variable] = result["output"]
                
                return result
                
            except Exception as e:
                attempt += 1
                logger.error(f"Action failed (attempt {attempt}): {e}")
                
                if attempt <= self.retry_count:
                    await asyncio.sleep(self.retry_delay)
                else:
                    if self.continue_on_error:
                        return {"status": "failed", "error": str(e), "continued": True}
                    else:
                        raise
        
        return {"status": "failed", "error": "Max retries exceeded"}
    
    async def _execute_action(self, context: Dict[str, Any], workflow_manager: 'WorkflowManager') -> Dict[str, Any]:
        """Execute specific action type."""
        if self.action_type == ActionType.OCR_PROCESS:
            return await self._execute_ocr_process(context, workflow_manager)
        
        elif self.action_type == ActionType.MOVE_FILE:
            return await self._execute_move_file(context)
        
        elif self.action_type == ActionType.COPY_FILE:
            return await self._execute_copy_file(context)
        
        elif self.action_type == ActionType.DELETE_FILE:
            return await self._execute_delete_file(context)
        
        elif self.action_type == ActionType.SEND_EMAIL:
            return await self._execute_send_email(context)
        
        elif self.action_type == ActionType.WEBHOOK:
            return await self._execute_webhook(context)
        
        elif self.action_type == ActionType.EXTRACT_FIELDS:
            return await self._execute_extract_fields(context, workflow_manager)
        
        elif self.action_type == ActionType.VALIDATE_DATA:
            return await self._execute_validate_data(context)
        
        elif self.action_type == ActionType.CONDITIONAL:
            return await self._execute_conditional(context, workflow_manager)
        
        elif self.action_type == ActionType.DELAY:
            return await self._execute_delay(context)
        
        elif self.action_type == ActionType.CUSTOM_SCRIPT:
            return await self._execute_custom_script(context)
        
        else:
            raise ValueError(f"Unknown action type: {self.action_type}")
    
    async def _execute_ocr_process(self, context: Dict[str, Any], workflow_manager: 'WorkflowManager') -> Dict[str, Any]:
        """Execute OCR processing action."""
        file_path = context.get("file_path") or self.parameters.get("file_path")
        if not file_path:
            raise ValueError("No file path provided for OCR processing")
        
        # Get OCR processor from workflow manager
        ocr_processor = workflow_manager.ocr_processor
        if not ocr_processor:
            raise ValueError("No OCR processor available")
        
        # Prepare OCR options
        ocr_options = {
            "mode": self.parameters.get("mode", "hybrid"),
            "language": self.parameters.get("language", "por+eng"),
            "confidence_threshold": self.parameters.get("confidence_threshold", 0.75),
            "output_folder": self.parameters.get("output_folder", context.get("output_folder"))
        }
        
        # Execute OCR processing
        result = await asyncio.get_event_loop().run_in_executor(
            None, ocr_processor, file_path, ocr_options
        )
        
        return {
            "status": "completed",
            "output": result,
            "ocr_result": result
        }
    
    async def _execute_move_file(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file move action."""
        source = context.get("file_path") or self.parameters.get("source")
        destination = self.parameters.get("destination")
        
        if not source or not destination:
            raise ValueError("Source and destination paths required for move operation")
        
        source_path = Path(source)
        dest_path = Path(destination)
        
        # Create destination directory if needed
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Handle name conflicts
        if dest_path.exists():
            counter = 1
            stem = dest_path.stem
            suffix = dest_path.suffix
            while dest_path.exists():
                dest_path = dest_path.parent / f"{stem}_{counter}{suffix}"
                counter += 1
        
        source_path.rename(dest_path)
        
        return {
            "status": "completed",
            "output": {"moved_to": str(dest_path)},
            "moved_path": str(dest_path)
        }
    
    async def _execute_copy_file(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file copy action."""
        import shutil
        
        source = context.get("file_path") or self.parameters.get("source")
        destination = self.parameters.get("destination")
        
        if not source or not destination:
            raise ValueError("Source and destination paths required for copy operation")
        
        source_path = Path(source)
        dest_path = Path(destination)
        
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        
        return {
            "status": "completed", 
            "output": {"copied_to": str(dest_path)},
            "copied_path": str(dest_path)
        }
    
    async def _execute_delete_file(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file deletion action."""
        file_path = context.get("file_path") or self.parameters.get("file_path")
        if not file_path:
            raise ValueError("No file path provided for deletion")
        
        path = Path(file_path)
        if path.exists():
            path.unlink()
        
        return {"status": "completed", "output": {"deleted": str(path)}}
    
    async def _execute_send_email(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute email sending action."""
        # Email sending implementation would go here
        # For now, just log the action
        logger = get_logger("workflow.email")
        logger.info(f"Would send email with parameters: {self.parameters}")
        
        return {"status": "completed", "output": {"email_sent": True}}
    
    async def _execute_webhook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute webhook call action."""
        import aiohttp
        
        url = self.parameters.get("url")
        method = self.parameters.get("method", "POST")
        headers = self.parameters.get("headers", {})
        data = self.parameters.get("data", {})
        
        # Include context data in webhook payload
        payload = {**data, "context": context}
        
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, json=payload) as response:
                response_text = await response.text()
                
                return {
                    "status": "completed",
                    "output": {
                        "status_code": response.status,
                        "response": response_text
                    }
                }
    
    async def _execute_extract_fields(self, context: Dict[str, Any], workflow_manager: 'WorkflowManager') -> Dict[str, Any]:
        """Execute field extraction action."""
        text = context.get("ocr_text") or context.get("text")
        template_name = self.parameters.get("template_name")
        
        if not text:
            raise ValueError("No text available for field extraction")
        
        if template_name and workflow_manager.template_manager:
            template = workflow_manager.template_manager.get_template(template_name)
            if template:
                extracted_fields = template.extract_fields(text)
                return {
                    "status": "completed",
                    "output": extracted_fields,
                    "extracted_fields": extracted_fields
                }
        
        return {"status": "failed", "error": "Template not found or no template manager"}
    
    async def _execute_validate_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute data validation action."""
        validation_rules = self.parameters.get("rules", [])
        data_to_validate = context.get("extracted_fields", {})
        
        validation_errors = []
        
        for rule in validation_rules:
            field_name = rule.get("field")
            rule_type = rule.get("type")
            value = data_to_validate.get(field_name, {}).get("value")
            
            if rule_type == "required" and not value:
                validation_errors.append(f"Required field '{field_name}' is missing")
            
            elif rule_type == "min_confidence":
                confidence = data_to_validate.get(field_name, {}).get("confidence", 0)
                min_confidence = rule.get("threshold", 0.8)
                if confidence < min_confidence:
                    validation_errors.append(f"Field '{field_name}' confidence {confidence} below threshold {min_confidence}")
        
        is_valid = len(validation_errors) == 0
        
        return {
            "status": "completed",
            "output": {
                "is_valid": is_valid,
                "errors": validation_errors
            },
            "validation_result": {
                "is_valid": is_valid,
                "errors": validation_errors
            }
        }
    
    async def _execute_conditional(self, context: Dict[str, Any], workflow_manager: 'WorkflowManager') -> Dict[str, Any]:
        """Execute conditional branching action."""
        condition = self.parameters.get("condition")
        true_actions = self.parameters.get("true_actions", [])
        false_actions = self.parameters.get("false_actions", [])
        
        if not condition:
            raise ValueError("No condition specified for conditional action")
        
        # Evaluate condition
        condition_result = eval(condition, {"__builtins__": {}}, context)
        
        # Execute appropriate actions
        actions_to_execute = true_actions if condition_result else false_actions
        results = []
        
        for action_config in actions_to_execute:
            action = WorkflowAction(**action_config)
            result = await action.execute(context, workflow_manager)
            results.append(result)
        
        return {
            "status": "completed",
            "output": {
                "condition_result": condition_result,
                "executed_actions": len(actions_to_execute),
                "results": results
            }
        }
    
    async def _execute_delay(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute delay action."""
        delay_seconds = self.parameters.get("seconds", 1.0)
        await asyncio.sleep(delay_seconds)
        
        return {
            "status": "completed",
            "output": {"delayed_seconds": delay_seconds}
        }
    
    async def _execute_custom_script(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute custom Python script action."""
        script_code = self.parameters.get("script")
        if not script_code:
            raise ValueError("No script code provided")
        
        # Create safe execution environment
        safe_globals = {
            "__builtins__": {
                "print": print,
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "Path": Path,
            },
            "context": context,
            "parameters": self.parameters
        }
        
        # Execute script
        exec(script_code, safe_globals)
        
        # Get result from context if modified
        result = safe_globals.get("result", {})
        
        return {
            "status": "completed",
            "output": result
        }


@dataclass
class WorkflowExecution:
    """Represents a single workflow execution instance."""
    
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str = ""
    status: WorkflowStatus = WorkflowStatus.CREATED
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Context and results
    initial_context: Dict[str, Any] = field(default_factory=dict)
    final_context: Dict[str, Any] = field(default_factory=dict)
    action_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Error information
    error_message: Optional[str] = None
    failed_action: Optional[str] = None
    
    def duration(self) -> Optional[timedelta]:
        """Get execution duration."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


@dataclass
class Workflow:
    """Defines a complete workflow with triggers and actions."""
    
    name: str
    description: str = ""
    enabled: bool = True
    
    # Workflow components
    triggers: List[WorkflowTrigger] = field(default_factory=list)
    actions: List[WorkflowAction] = field(default_factory=list)
    
    # Configuration
    max_concurrent_executions: int = 1
    timeout_seconds: int = 3600  # 1 hour
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.0"
    author: str = "OCR Enhanced"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert workflow to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Workflow':
        """Create workflow from dictionary."""
        # Convert triggers
        if 'triggers' in data:
            triggers = []
            for trigger_data in data['triggers']:
                if isinstance(trigger_data, dict):
                    if 'trigger_type' in trigger_data and isinstance(trigger_data['trigger_type'], str):
                        trigger_data['trigger_type'] = TriggerType(trigger_data['trigger_type'])
                    triggers.append(WorkflowTrigger(**trigger_data))
                else:
                    triggers.append(trigger_data)
            data['triggers'] = triggers
        
        # Convert actions
        if 'actions' in data:
            actions = []
            for action_data in data['actions']:
                if isinstance(action_data, dict):
                    if 'action_type' in action_data and isinstance(action_data['action_type'], str):
                        action_data['action_type'] = ActionType(action_data['action_type'])
                    actions.append(WorkflowAction(**action_data))
                else:
                    actions.append(action_data)
            data['actions'] = actions
        
        return cls(**data)


class WorkflowManager:
    """Manages workflow definitions and executions."""
    
    def __init__(self, workflows_dir: Optional[Path] = None, 
                 ocr_processor: Optional[Callable] = None,
                 template_manager: Optional[TemplateManager] = None):
        self.workflows_dir = workflows_dir or Path.home() / ".ocr_enhanced" / "workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        
        self.ocr_processor = ocr_processor
        self.template_manager = template_manager
        
        self.workflows: Dict[str, Workflow] = {}
        self.active_executions: Dict[str, WorkflowExecution] = {}
        self.execution_history: List[WorkflowExecution] = []
        
        self.logger = get_logger("workflow_manager")
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # Load workflows
        self.load_workflows()
        
        # Create built-in workflows
        self._create_builtin_workflows()
    
    def _create_builtin_workflows(self):
        """Create built-in workflow examples."""
        
        # Auto-process workflow
        auto_process_workflow = Workflow(
            name="Auto Process Documents",
            description="Automatically process new documents with OCR and template matching",
            triggers=[
                WorkflowTrigger(
                    trigger_type=TriggerType.FILE_ADDED,
                    name="New file trigger",
                    file_patterns=[".pdf", ".png", ".jpg", ".jpeg"]
                )
            ],
            actions=[
                WorkflowAction(
                    action_type=ActionType.OCR_PROCESS,
                    name="OCR Processing",
                    parameters={
                        "mode": "hybrid",
                        "language": "por+eng"
                    },
                    output_variable="ocr_result"
                ),
                WorkflowAction(
                    action_type=ActionType.EXTRACT_FIELDS,
                    name="Extract Fields",
                    condition="ocr_result.get('success', False)",
                    output_variable="extracted_fields"
                ),
                WorkflowAction(
                    action_type=ActionType.VALIDATE_DATA,
                    name="Validate Data",
                    parameters={
                        "rules": [
                            {"field": "total_amount", "type": "required"},
                            {"field": "invoice_number", "type": "required"}
                        ]
                    },
                    output_variable="validation_result"
                ),
                WorkflowAction(
                    action_type=ActionType.CONDITIONAL,
                    name="Process based on validation",
                    parameters={
                        "condition": "validation_result.get('is_valid', False)",
                        "true_actions": [
                            {
                                "action_type": "move_file",
                                "name": "Move to processed",
                                "parameters": {
                                    "destination": "processed/"
                                }
                            }
                        ],
                        "false_actions": [
                            {
                                "action_type": "move_file", 
                                "name": "Move to review",
                                "parameters": {
                                    "destination": "review/"
                                }
                            }
                        ]
                    }
                )
            ]
        )
        
        # Invoice processing workflow
        invoice_workflow = Workflow(
            name="Invoice Processing",
            description="Specialized workflow for invoice processing",
            triggers=[
                WorkflowTrigger(
                    trigger_type=TriggerType.TEMPLATE_MATCHED,
                    name="Invoice template matched",
                    template_names=["Brazilian Invoice"],
                    confidence_threshold=0.8
                )
            ],
            actions=[
                WorkflowAction(
                    action_type=ActionType.EXTRACT_FIELDS,
                    name="Extract invoice fields",
                    parameters={
                        "template_name": "Brazilian Invoice"
                    },
                    output_variable="invoice_data"
                ),
                WorkflowAction(
                    action_type=ActionType.VALIDATE_DATA,
                    name="Validate invoice data",
                    parameters={
                        "rules": [
                            {"field": "invoice_number", "type": "required"},
                            {"field": "total_amount", "type": "required"},
                            {"field": "cnpj", "type": "min_confidence", "threshold": 0.9}
                        ]
                    },
                    output_variable="validation"
                ),
                WorkflowAction(
                    action_type=ActionType.WEBHOOK,
                    name="Send to ERP system",
                    condition="validation.get('is_valid', False)",
                    parameters={
                        "url": "https://api.example.com/invoices",
                        "method": "POST",
                        "headers": {"Content-Type": "application/json"},
                        "data": {"invoice_data": "{{ invoice_data }}"}
                    }
                )
            ]
        )
        
        # Store built-in workflows
        self.workflows[auto_process_workflow.name] = auto_process_workflow
        self.workflows[invoice_workflow.name] = invoice_workflow
        
        self.logger.info(f"Created {len(self.workflows)} built-in workflows")
    
    def load_workflows(self):
        """Load workflows from files."""
        workflow_files = self.workflows_dir.glob("*.json")
        loaded_count = 0
        
        for workflow_file in workflow_files:
            try:
                with open(workflow_file, 'r', encoding='utf-8') as f:
                    workflow_data = json.load(f)
                
                workflow = Workflow.from_dict(workflow_data)
                self.workflows[workflow.name] = workflow
                loaded_count += 1
                
            except Exception as e:
                self.logger.error(f"Error loading workflow {workflow_file}: {e}")
        
        self.logger.info(f"Loaded {loaded_count} workflows from {self.workflows_dir}")
    
    def save_workflow(self, workflow: Workflow):
        """Save workflow to file."""
        try:
            workflow_file = self.workflows_dir / f"{workflow.name}.json"
            with open(workflow_file, 'w', encoding='utf-8') as f:
                json.dump(workflow.to_dict(), f, indent=2, ensure_ascii=False)
            
            self.workflows[workflow.name] = workflow
            self.logger.info(f"Saved workflow: {workflow.name}")
            
        except Exception as e:
            self.logger.error(f"Error saving workflow {workflow.name}: {e}")
    
    def delete_workflow(self, workflow_name: str):
        """Delete workflow."""
        if workflow_name in self.workflows:
            workflow_file = self.workflows_dir / f"{workflow_name}.json"
            if workflow_file.exists():
                workflow_file.unlink()
            
            del self.workflows[workflow_name]
            self.logger.info(f"Deleted workflow: {workflow_name}")
    
    def get_workflow(self, workflow_name: str) -> Optional[Workflow]:
        """Get workflow by name."""
        return self.workflows.get(workflow_name)
    
    def list_workflows(self) -> List[str]:
        """List all workflow names."""
        return list(self.workflows.keys())
    
    async def trigger_workflow(self, workflow_name: str, context: Dict[str, Any]) -> Optional[WorkflowExecution]:
        """Manually trigger a workflow."""
        workflow = self.workflows.get(workflow_name)
        if not workflow or not workflow.enabled:
            return None
        
        return await self._execute_workflow(workflow, context)
    
    async def process_trigger(self, trigger_type: TriggerType, context: Dict[str, Any]) -> List[WorkflowExecution]:
        """Process a trigger and execute matching workflows."""
        executions = []
        
        for workflow in self.workflows.values():
            if not workflow.enabled:
                continue
            
            # Check if any trigger matches
            for trigger in workflow.triggers:
                if trigger.trigger_type == trigger_type and trigger.matches(context):
                    self.logger.info(f"Trigger '{trigger.name}' matched for workflow '{workflow.name}'")
                    
                    execution = await self._execute_workflow(workflow, context)
                    if execution:
                        executions.append(execution)
                    break
        
        return executions
    
    async def _execute_workflow(self, workflow: Workflow, context: Dict[str, Any]) -> Optional[WorkflowExecution]:
        """Execute a workflow."""
        # Check concurrent execution limit
        active_count = sum(1 for exec in self.active_executions.values() 
                          if exec.workflow_name == workflow.name)
        
        if active_count >= workflow.max_concurrent_executions:
            self.logger.warning(f"Workflow '{workflow.name}' has reached max concurrent executions")
            return None
        
        # Create execution instance
        execution = WorkflowExecution(
            workflow_name=workflow.name,
            initial_context=context.copy(),
            started_at=datetime.now(),
            status=WorkflowStatus.RUNNING
        )
        
        self.active_executions[execution.execution_id] = execution
        
        try:
            self.logger.info(f"Starting workflow execution: {workflow.name} ({execution.execution_id})")
            
            # Execute actions sequentially
            for action in workflow.actions:
                action_start = datetime.now()
                
                try:
                    result = await asyncio.wait_for(
                        action.execute(context, self),
                        timeout=workflow.timeout_seconds
                    )
                    
                    result["action_name"] = action.name
                    result["execution_time"] = (datetime.now() - action_start).total_seconds()
                    execution.action_results.append(result)
                    
                    if result["status"] == "failed" and not action.continue_on_error:
                        execution.status = WorkflowStatus.FAILED
                        execution.error_message = result.get("error", "Action failed")
                        execution.failed_action = action.name
                        break
                        
                except asyncio.TimeoutError:
                    execution.status = WorkflowStatus.FAILED
                    execution.error_message = f"Action '{action.name}' timed out"
                    execution.failed_action = action.name
                    break
                    
                except Exception as e:
                    execution.status = WorkflowStatus.FAILED
                    execution.error_message = str(e)
                    execution.failed_action = action.name
                    self.logger.error(f"Action '{action.name}' failed: {e}")
                    break
            
            # Complete execution
            if execution.status == WorkflowStatus.RUNNING:
                execution.status = WorkflowStatus.COMPLETED
            
            execution.completed_at = datetime.now()
            execution.final_context = context.copy()
            
            self.logger.info(
                f"Workflow execution completed: {workflow.name} ({execution.execution_id}) "
                f"- Status: {execution.status.value}"
            )
            
        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.now()
            self.logger.error(f"Workflow execution failed: {e}")
        
        finally:
            # Move to history
            del self.active_executions[execution.execution_id]
            self.execution_history.append(execution)
            
            # Keep only last 1000 executions in memory
            if len(self.execution_history) > 1000:
                self.execution_history = self.execution_history[-1000:]
        
        return execution
    
    def get_execution_status(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get execution status by ID."""
        # Check active executions
        if execution_id in self.active_executions:
            return self.active_executions[execution_id]
        
        # Check history
        for execution in self.execution_history:
            if execution.execution_id == execution_id:
                return execution
        
        return None
    
    def get_workflow_statistics(self) -> Dict[str, Any]:
        """Get workflow execution statistics."""
        stats = {
            "total_workflows": len(self.workflows),
            "active_executions": len(self.active_executions),
            "total_executions": len(self.execution_history),
            "success_rate": 0.0,
            "workflows": {}
        }
        
        # Calculate success rate
        if self.execution_history:
            successful = sum(1 for ex in self.execution_history 
                           if ex.status == WorkflowStatus.COMPLETED)
            stats["success_rate"] = successful / len(self.execution_history)
        
        # Per-workflow statistics
        for workflow_name in self.workflows:
            workflow_executions = [ex for ex in self.execution_history 
                                 if ex.workflow_name == workflow_name]
            
            if workflow_executions:
                successful = sum(1 for ex in workflow_executions 
                               if ex.status == WorkflowStatus.COMPLETED)
                avg_duration = sum(ex.duration().total_seconds() for ex in workflow_executions 
                                 if ex.duration()) / len(workflow_executions)
                
                stats["workflows"][workflow_name] = {
                    "total_executions": len(workflow_executions),
                    "successful_executions": successful,
                    "success_rate": successful / len(workflow_executions),
                    "average_duration_seconds": avg_duration
                }
        
        return stats