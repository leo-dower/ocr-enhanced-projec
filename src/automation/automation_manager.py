"""
Automation Manager - Central orchestrator for all automation features.

This module provides a unified interface for managing all automation
capabilities including folder watching, workflows, scheduling, and rules.
"""

import asyncio
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json

from ..utils.logger import get_logger
from ..core.config import OCRConfig
from .folder_watcher import FolderWatcher, WatcherConfig
from .templates import TemplateManager
from .workflows import WorkflowManager, TriggerType
from .scheduler import ProcessingScheduler
from .email_integration import EmailMonitor, EmailProcessor
from .rules import RuleEngine


@dataclass
class AutomationConfig:
    """Configuration for automation features."""
    
    # General settings
    enabled: bool = True
    auto_start: bool = True
    
    # Folder watching
    folder_watching_enabled: bool = True
    watch_folders: List[str] = field(default_factory=list)
    processing_delay: float = 2.0
    batch_size: int = 5
    
    # Email monitoring
    email_monitoring_enabled: bool = False
    email_check_interval: int = 300  # seconds
    
    # Scheduling
    scheduling_enabled: bool = True
    
    # Rule engine
    rules_enabled: bool = True
    
    # Templates
    templates_enabled: bool = True
    auto_template_detection: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "enabled": self.enabled,
            "auto_start": self.auto_start,
            "folder_watching_enabled": self.folder_watching_enabled,
            "watch_folders": self.watch_folders,
            "processing_delay": self.processing_delay,
            "batch_size": self.batch_size,
            "email_monitoring_enabled": self.email_monitoring_enabled,
            "email_check_interval": self.email_check_interval,
            "scheduling_enabled": self.scheduling_enabled,
            "rules_enabled": self.rules_enabled,
            "templates_enabled": self.templates_enabled,
            "auto_template_detection": self.auto_template_detection
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AutomationConfig':
        """Create from dictionary."""
        return cls(**data)


class AutomationManager:
    """Central manager for all automation features."""
    
    def __init__(self, ocr_config: OCRConfig, ocr_processor: Optional[Callable] = None):
        self.ocr_config = ocr_config
        self.ocr_processor = ocr_processor
        self.logger = get_logger("automation_manager")
        
        # Configuration
        self.config_file = Path.home() / ".ocr_enhanced" / "automation_config.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.automation_config = self._load_automation_config()
        
        # Initialize components
        self.template_manager: Optional[TemplateManager] = None
        self.rule_engine: Optional[RuleEngine] = None
        self.workflow_manager: Optional[WorkflowManager] = None
        self.folder_watcher: Optional[FolderWatcher] = None
        self.scheduler: Optional[ProcessingScheduler] = None
        self.email_monitor: Optional[EmailMonitor] = None
        
        # State
        self.running = False
        self.components_initialized = False
        
        # Statistics
        self.stats = {
            "start_time": None,
            "total_files_processed": 0,
            "total_workflows_executed": 0,
            "total_rules_applied": 0,
            "errors": 0
        }
        
        # Initialize components if enabled
        if self.automation_config.enabled:
            self._initialize_components()
    
    def _load_automation_config(self) -> AutomationConfig:
        """Load automation configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                return AutomationConfig.from_dict(config_data)
            except Exception as e:
                self.logger.error(f"Error loading automation config: {e}")
        
        # Return default configuration
        return AutomationConfig(
            watch_folders=[self.ocr_config.input_folder] if self.ocr_config.input_folder else []
        )
    
    def _save_automation_config(self):
        """Save automation configuration to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.automation_config.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving automation config: {e}")
    
    def _initialize_components(self):
        """Initialize all automation components."""
        if self.components_initialized:
            return
        
        self.logger.info("Initializing automation components...")
        
        try:
            # Initialize template manager
            if self.automation_config.templates_enabled:
                self.template_manager = TemplateManager()
                self.logger.info("Template manager initialized")
            
            # Initialize rule engine
            if self.automation_config.rules_enabled:
                self.rule_engine = RuleEngine()
                self.logger.info("Rule engine initialized")
            
            # Initialize workflow manager
            self.workflow_manager = WorkflowManager(
                ocr_processor=self.ocr_processor,
                template_manager=self.template_manager
            )
            self.logger.info("Workflow manager initialized")
            
            # Initialize folder watcher
            if self.automation_config.folder_watching_enabled and self.automation_config.watch_folders:
                watcher_config = WatcherConfig(
                    watch_folders=self.automation_config.watch_folders,
                    output_folder=self.ocr_config.output_folder,
                    processing_delay=self.automation_config.processing_delay,
                    batch_size=self.automation_config.batch_size,
                    ocr_mode=self.ocr_config.mode,
                    ocr_language=self.ocr_config.language,
                    confidence_threshold=self.ocr_config.confidence_threshold
                )
                
                self.folder_watcher = FolderWatcher(
                    watcher_config,
                    self._process_file_with_automation
                )
                self.logger.info("Folder watcher initialized")
            
            # Initialize scheduler
            if self.automation_config.scheduling_enabled:
                self.scheduler = ProcessingScheduler(
                    workflow_manager=self.workflow_manager
                )
                self.logger.info("Scheduler initialized")
            
            # Initialize email monitor
            if self.automation_config.email_monitoring_enabled:
                email_processor = EmailProcessor(
                    workflow_manager=self.workflow_manager
                )
                self.email_monitor = EmailMonitor(email_processor)
                self.logger.info("Email monitor initialized")
            
            self.components_initialized = True
            self.logger.info("All automation components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing automation components: {e}")
            raise
    
    def _process_file_with_automation(self, file_path: Path, options: Dict[str, Any]) -> Dict[str, Any]:
        """Process file with full automation pipeline."""
        start_time = datetime.now()
        context = {
            "file_path": str(file_path),
            "file_name": file_path.name,
            "file_size": file_path.stat().st_size if file_path.exists() else 0,
            "processing_start": start_time.isoformat(),
            **options
        }
        
        try:
            self.logger.info(f"Processing file with automation: {file_path}")
            
            # Step 1: Apply pre-processing rules
            if self.rule_engine:
                pre_rules = self.rule_engine.apply_rules(context)
                context["pre_processing_rules"] = pre_rules
                
                if context.get("stop_processing", False):
                    return {"success": False, "reason": "Stopped by pre-processing rules"}
            
            # Step 2: Template detection if enabled
            if self.template_manager and self.automation_config.auto_template_detection:
                # We need text content for template detection
                # This would require a quick OCR pass first
                context["template_detection_enabled"] = True
            
            # Step 3: Process with OCR
            if self.ocr_processor:
                ocr_result = self.ocr_processor(file_path, options)
                context["ocr_result"] = ocr_result
                
                if ocr_result and ocr_result.get("success", False):
                    context["ocr_text"] = ocr_result.get("text", "")
                    context["ocr_confidence"] = ocr_result.get("confidence", 0.0)
            
            # Step 4: Template matching and field extraction
            if self.template_manager and context.get("ocr_text"):
                template = self.template_manager.identify_document_type(context["ocr_text"])
                if template:
                    context["template_name"] = template.name
                    context["template_confidence"] = template.matches_document(context["ocr_text"])
                    
                    # Extract fields using template
                    extracted_fields = template.extract_fields(context["ocr_text"])
                    context["extracted_fields"] = extracted_fields
                    
                    # Trigger template-matched workflows
                    if self.workflow_manager:
                        asyncio.create_task(
                            self.workflow_manager.process_trigger(
                                TriggerType.TEMPLATE_MATCHED,
                                context
                            )
                        )
            
            # Step 5: Apply post-processing rules
            if self.rule_engine:
                post_rules = self.rule_engine.apply_rules(context)
                context["post_processing_rules"] = post_rules
                
                # Validate results
                validation_result = self.rule_engine.validate_context(context)
                context["validation_result"] = validation_result
            
            # Step 6: Trigger file-based workflows
            if self.workflow_manager:
                asyncio.create_task(
                    self.workflow_manager.process_trigger(
                        TriggerType.FILE_ADDED,
                        context
                    )
                )
            
            # Update statistics
            self.stats["total_files_processed"] += 1
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": True,
                "processing_time": processing_time,
                "context": context,
                "automation_applied": True
            }
            
        except Exception as e:
            self.logger.error(f"Error in automation pipeline: {e}")
            self.stats["errors"] += 1
            
            return {
                "success": False,
                "error": str(e),
                "context": context
            }
    
    def start_automation(self):
        """Start all automation components."""
        if self.running:
            self.logger.warning("Automation is already running")
            return
        
        if not self.automation_config.enabled:
            self.logger.info("Automation is disabled in configuration")
            return
        
        self.logger.info("Starting automation...")
        
        try:
            # Ensure components are initialized
            if not self.components_initialized:
                self._initialize_components()
            
            # Start folder watcher
            if self.folder_watcher:
                self.folder_watcher.start_watching()
                self.logger.info("Folder watcher started")
            
            # Start scheduler
            if self.scheduler:
                self.scheduler.start_scheduler()
                self.logger.info("Scheduler started")
            
            # Start email monitor
            if self.email_monitor:
                self.email_monitor.start_monitoring(self.automation_config.email_check_interval)
                self.logger.info("Email monitor started")
            
            self.running = True
            self.stats["start_time"] = datetime.now()
            
            self.logger.info("Automation started successfully")
            
        except Exception as e:
            self.logger.error(f"Error starting automation: {e}")
            raise
    
    def stop_automation(self):
        """Stop all automation components."""
        if not self.running:
            return
        
        self.logger.info("Stopping automation...")
        
        try:
            # Stop folder watcher
            if self.folder_watcher:
                self.folder_watcher.stop_watching()
                self.logger.info("Folder watcher stopped")
            
            # Stop scheduler
            if self.scheduler:
                self.scheduler.stop_scheduler()
                self.logger.info("Scheduler stopped")
            
            # Stop email monitor
            if self.email_monitor:
                self.email_monitor.stop_monitoring()
                self.logger.info("Email monitor stopped")
            
            self.running = False
            self.logger.info("Automation stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping automation: {e}")
    
    def restart_automation(self):
        """Restart automation with current configuration."""
        self.logger.info("Restarting automation...")
        self.stop_automation()
        
        # Reload configuration
        self.automation_config = self._load_automation_config()
        
        # Reinitialize components
        self.components_initialized = False
        
        # Start again
        self.start_automation()
    
    def update_configuration(self, new_config: AutomationConfig):
        """Update automation configuration."""
        self.automation_config = new_config
        self._save_automation_config()
        
        # Restart if running to apply changes
        if self.running:
            self.restart_automation()
        
        self.logger.info("Automation configuration updated")
    
    def process_single_file(self, file_path: Path, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a single file through the automation pipeline."""
        if not self.components_initialized:
            self._initialize_components()
        
        processing_options = options or {
            "mode": self.ocr_config.mode,
            "language": self.ocr_config.language,
            "confidence_threshold": self.ocr_config.confidence_threshold,
            "output_folder": self.ocr_config.output_folder
        }
        
        return self._process_file_with_automation(file_path, processing_options)
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all automation components."""
        status = {
            "running": self.running,
            "configuration": self.automation_config.to_dict(),
            "components": {},
            "statistics": self.stats.copy()
        }
        
        # Add uptime if running
        if self.stats["start_time"]:
            uptime = (datetime.now() - self.stats["start_time"]).total_seconds()
            status["statistics"]["uptime_seconds"] = uptime
        
        # Component status
        if self.folder_watcher:
            status["components"]["folder_watcher"] = self.folder_watcher.get_statistics()
        
        if self.workflow_manager:
            status["components"]["workflows"] = self.workflow_manager.get_workflow_statistics()
        
        if self.scheduler:
            status["components"]["scheduler"] = self.scheduler.get_job_statistics()
        
        if self.email_monitor:
            status["components"]["email_monitor"] = self.email_monitor.get_statistics()
        
        if self.rule_engine:
            status["components"]["rule_engine"] = self.rule_engine.get_rule_statistics()
        
        if self.template_manager:
            status["components"]["templates"] = {
                "total_templates": len(self.template_manager.list_templates()),
                "template_names": self.template_manager.list_templates()
            }
        
        return status
    
    def get_logs(self, component: str = "all", limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent logs from automation components."""
        # This would integrate with the logging system to retrieve recent logs
        # For now, return placeholder
        return [{
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "level": "INFO",
            "message": f"Log retrieval for {component} - Feature coming soon"
        }]
    
    def create_automation_dashboard_data(self) -> Dict[str, Any]:
        """Create data for automation dashboard/monitoring."""
        status = self.get_status()
        
        dashboard_data = {
            "overview": {
                "automation_enabled": status["running"],
                "components_active": sum(1 for comp in status["components"].values() 
                                       if comp.get("running", False) or comp.get("is_running", False)),
                "total_files_processed": status["statistics"]["total_files_processed"],
                "success_rate": self._calculate_success_rate(),
                "uptime": status["statistics"].get("uptime_seconds", 0)
            },
            "components": status["components"],
            "recent_activity": self._get_recent_activity(),
            "performance_metrics": self._get_performance_metrics()
        }
        
        return dashboard_data
    
    def _calculate_success_rate(self) -> float:
        """Calculate overall success rate."""
        total = self.stats["total_files_processed"]
        errors = self.stats["errors"]
        
        if total == 0:
            return 1.0
        
        return (total - errors) / total
    
    def _get_recent_activity(self) -> List[Dict[str, Any]]:
        """Get recent activity across all components."""
        # This would aggregate recent activity from all components
        return [
            {
                "timestamp": datetime.now().isoformat(),
                "component": "automation_manager",
                "activity": "System status check",
                "status": "completed"
            }
        ]
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            "avg_processing_time": 0.0,  # Would calculate from actual data
            "peak_concurrent_files": 0,
            "memory_usage_mb": 0,
            "cpu_usage_percent": 0
        }


def create_automation_manager(ocr_config: OCRConfig, ocr_processor: Callable) -> AutomationManager:
    """Factory function to create automation manager."""
    return AutomationManager(ocr_config, ocr_processor)