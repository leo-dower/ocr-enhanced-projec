"""
Rule engine for conditional OCR processing.

This module provides a flexible rule system for defining conditional
logic, data validation, and automated decision-making in OCR workflows.
"""

import re
import json
import operator
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import ast
import logging

from ..utils.logger import get_logger


class RuleType(Enum):
    """Types of rules."""
    CONDITION = "condition"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    ROUTING = "routing"
    NOTIFICATION = "notification"


class OperatorType(Enum):
    """Supported operators for conditions."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX_MATCH = "regex_match"
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    BETWEEN = "between"


class ActionType(Enum):
    """Types of actions that can be triggered by rules."""
    SET_VALUE = "set_value"
    SET_CONFIDENCE = "set_confidence"
    SET_LANGUAGE = "set_language"
    SET_MODE = "set_mode"
    MOVE_FILE = "move_file"
    COPY_FILE = "copy_file"
    SEND_EMAIL = "send_email"
    WEBHOOK = "webhook"
    LOG_MESSAGE = "log_message"
    TRIGGER_WORKFLOW = "trigger_workflow"
    STOP_PROCESSING = "stop_processing"
    RETRY_PROCESSING = "retry_processing"


@dataclass
class Condition:
    """Represents a single condition."""
    
    field_path: str  # e.g., "extracted_fields.total_amount.value"
    operator: OperatorType
    value: Any
    case_sensitive: bool = False
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate condition against context."""
        try:
            # Get field value from context using dot notation
            field_value = self._get_nested_value(context, self.field_path)
            
            # Handle case sensitivity for string operations
            if isinstance(field_value, str) and isinstance(self.value, str) and not self.case_sensitive:
                field_value = field_value.lower()
                compare_value = self.value.lower()
            else:
                compare_value = self.value
            
            # Apply operator
            if self.operator == OperatorType.EQUALS:
                return field_value == compare_value
            
            elif self.operator == OperatorType.NOT_EQUALS:
                return field_value != compare_value
            
            elif self.operator == OperatorType.GREATER_THAN:
                return self._to_number(field_value) > self._to_number(compare_value)
            
            elif self.operator == OperatorType.LESS_THAN:
                return self._to_number(field_value) < self._to_number(compare_value)
            
            elif self.operator == OperatorType.GREATER_EQUAL:
                return self._to_number(field_value) >= self._to_number(compare_value)
            
            elif self.operator == OperatorType.LESS_EQUAL:
                return self._to_number(field_value) <= self._to_number(compare_value)
            
            elif self.operator == OperatorType.CONTAINS:
                return str(compare_value) in str(field_value)
            
            elif self.operator == OperatorType.NOT_CONTAINS:
                return str(compare_value) not in str(field_value)
            
            elif self.operator == OperatorType.STARTS_WITH:
                return str(field_value).startswith(str(compare_value))
            
            elif self.operator == OperatorType.ENDS_WITH:
                return str(field_value).endswith(str(compare_value))
            
            elif self.operator == OperatorType.REGEX_MATCH:
                return bool(re.search(str(compare_value), str(field_value), 
                                    re.IGNORECASE if not self.case_sensitive else 0))
            
            elif self.operator == OperatorType.IN_LIST:
                return field_value in self.value if isinstance(self.value, list) else False
            
            elif self.operator == OperatorType.NOT_IN_LIST:
                return field_value not in self.value if isinstance(self.value, list) else True
            
            elif self.operator == OperatorType.IS_EMPTY:
                return not field_value or (isinstance(field_value, str) and field_value.strip() == "")
            
            elif self.operator == OperatorType.IS_NOT_EMPTY:
                return bool(field_value) and not (isinstance(field_value, str) and field_value.strip() == "")
            
            elif self.operator == OperatorType.BETWEEN:
                if isinstance(self.value, list) and len(self.value) == 2:
                    num_value = self._to_number(field_value)
                    return self._to_number(self.value[0]) <= num_value <= self._to_number(self.value[1])
                return False
            
            return False
            
        except Exception as e:
            logging.warning(f"Error evaluating condition {self.field_path} {self.operator.value}: {e}")
            return False
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        
        return value
    
    def _to_number(self, value: Any) -> float:
        """Convert value to number for numeric comparisons."""
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Try to extract number from string
            numeric_str = re.sub(r'[^\d.,-]', '', value)
            numeric_str = numeric_str.replace(',', '.')
            
            try:
                return float(numeric_str)
            except ValueError:
                return 0.0
        
        return 0.0


@dataclass
class RuleAction:
    """Represents an action to be executed when rule conditions are met."""
    
    action_type: ActionType
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the action with given context."""
        result = {"action_type": self.action_type.value, "success": False}
        
        try:
            if self.action_type == ActionType.SET_VALUE:
                field_path = self.parameters.get("field_path")
                value = self.parameters.get("value")
                if field_path and value is not None:
                    self._set_nested_value(context, field_path, value)
                    result["success"] = True
            
            elif self.action_type == ActionType.SET_CONFIDENCE:
                confidence = self.parameters.get("confidence", 0.75)
                context["confidence_threshold"] = confidence
                result["success"] = True
            
            elif self.action_type == ActionType.SET_LANGUAGE:
                language = self.parameters.get("language", "eng")
                context["ocr_language"] = language
                result["success"] = True
            
            elif self.action_type == ActionType.SET_MODE:
                mode = self.parameters.get("mode", "hybrid")
                context["ocr_mode"] = mode
                result["success"] = True
            
            elif self.action_type == ActionType.LOG_MESSAGE:
                message = self.parameters.get("message", "Rule action executed")
                level = self.parameters.get("level", "INFO")
                logger = get_logger("rule_action")
                getattr(logger, level.lower())(message)
                result["success"] = True
            
            elif self.action_type == ActionType.STOP_PROCESSING:
                context["stop_processing"] = True
                result["success"] = True
            
            # Additional actions would be implemented here
            # (MOVE_FILE, SEND_EMAIL, WEBHOOK, etc.)
            
            result["executed_at"] = datetime.now().isoformat()
            
        except Exception as e:
            result["error"] = str(e)
            logging.error(f"Error executing rule action {self.action_type.value}: {e}")
        
        return result
    
    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any):
        """Set value in nested dictionary using dot notation."""
        keys = path.split('.')
        current = data
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value


@dataclass
class ProcessingRule:
    """Represents a complete processing rule with conditions and actions."""
    
    rule_id: str
    name: str
    description: str = ""
    rule_type: RuleType = RuleType.CONDITION
    enabled: bool = True
    priority: int = 0
    
    # Conditions (all must be true for rule to trigger)
    conditions: List[Condition] = field(default_factory=list)
    
    # Actions to execute when conditions are met
    actions: List[RuleAction] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"
    tags: List[str] = field(default_factory=list)
    
    # Execution statistics
    execution_count: int = 0
    last_executed: Optional[datetime] = None
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate all conditions against context."""
        if not self.enabled or not self.conditions:
            return False
        
        # All conditions must be true
        return all(condition.evaluate(context) for condition in self.conditions)
    
    def execute(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute all actions if conditions are met."""
        if not self.evaluate(context):
            return []
        
        logger = get_logger("processing_rule")
        logger.info(f"Executing rule: {self.name}")
        
        results = []
        
        for action in self.actions:
            result = action.execute(context)
            results.append(result)
        
        # Update execution statistics
        self.execution_count += 1
        self.last_executed = datetime.now()
        
        return results
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary for serialization."""
        data = asdict(self)
        
        # Convert enums to strings
        data["rule_type"] = self.rule_type.value
        
        for i, condition in enumerate(data["conditions"]):
            condition["operator"] = self.conditions[i].operator.value
        
        for i, action in enumerate(data["actions"]):
            action["action_type"] = self.actions[i].action_type.value
        
        # Convert datetime to string
        data["created_at"] = self.created_at.isoformat()
        if self.last_executed:
            data["last_executed"] = self.last_executed.isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessingRule':
        """Create rule from dictionary."""
        # Convert datetime strings
        if "created_at" in data:
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "last_executed" in data and data["last_executed"]:
            data["last_executed"] = datetime.fromisoformat(data["last_executed"])
        
        # Convert enums
        if "rule_type" in data and isinstance(data["rule_type"], str):
            data["rule_type"] = RuleType(data["rule_type"])
        
        # Convert conditions
        if "conditions" in data:
            conditions = []
            for condition_data in data["conditions"]:
                if "operator" in condition_data and isinstance(condition_data["operator"], str):
                    condition_data["operator"] = OperatorType(condition_data["operator"])
                conditions.append(Condition(**condition_data))
            data["conditions"] = conditions
        
        # Convert actions
        if "actions" in data:
            actions = []
            for action_data in data["actions"]:
                if "action_type" in action_data and isinstance(action_data["action_type"], str):
                    action_data["action_type"] = ActionType(action_data["action_type"])
                actions.append(RuleAction(**action_data))
            data["actions"] = actions
        
        return cls(**data)


class RuleEngine:
    """Engine for managing and executing processing rules."""
    
    def __init__(self, rules_file: Optional[Path] = None):
        self.rules_file = rules_file or Path.home() / ".ocr_enhanced" / "rules.json"
        self.rules_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.rules: Dict[str, ProcessingRule] = {}
        self.logger = get_logger("rule_engine")
        
        # Load existing rules
        self.load_rules()
        
        # Create built-in rules if none exist
        if not self.rules:
            self._create_builtin_rules()
    
    def _create_builtin_rules(self):
        """Create built-in processing rules."""
        
        # High confidence rule
        high_confidence_rule = ProcessingRule(
            rule_id="high_confidence_processing",
            name="High Confidence Processing",
            description="Use cloud OCR for high confidence requirements",
            rule_type=RuleType.CONDITION,
            priority=10,
            conditions=[
                Condition(
                    field_path="template_name",
                    operator=OperatorType.IN_LIST,
                    value=["Brazilian Invoice", "Legal Document"]
                )
            ],
            actions=[
                RuleAction(
                    action_type=ActionType.SET_MODE,
                    parameters={"mode": "cloud"}
                ),
                RuleAction(
                    action_type=ActionType.SET_CONFIDENCE,
                    parameters={"confidence": 0.9}
                )
            ],
            tags=["confidence", "quality"]
        )
        
        # Language detection rule
        language_rule = ProcessingRule(
            rule_id="portuguese_document_detection",
            name="Portuguese Document Detection",
            description="Detect Portuguese documents and adjust language",
            rule_type=RuleType.CONDITION,
            priority=5,
            conditions=[
                Condition(
                    field_path="file_path",
                    operator=OperatorType.REGEX_MATCH,
                    value=r"(?i)(nota|fatura|recibo|documento)"
                )
            ],
            actions=[
                RuleAction(
                    action_type=ActionType.SET_LANGUAGE,
                    parameters={"language": "por"}
                ),
                RuleAction(
                    action_type=ActionType.LOG_MESSAGE,
                    parameters={"message": "Portuguese document detected", "level": "INFO"}
                )
            ],
            tags=["language", "detection"]
        )
        
        # Invoice validation rule
        invoice_validation_rule = ProcessingRule(
            rule_id="invoice_validation",
            name="Invoice Validation",
            description="Validate invoice fields and stop processing if invalid",
            rule_type=RuleType.VALIDATION,
            priority=15,
            conditions=[
                Condition(
                    field_path="template_name",
                    operator=OperatorType.EQUALS,
                    value="Brazilian Invoice"
                ),
                Condition(
                    field_path="extracted_fields.total_amount.confidence",
                    operator=OperatorType.LESS_THAN,
                    value=0.7
                )
            ],
            actions=[
                RuleAction(
                    action_type=ActionType.LOG_MESSAGE,
                    parameters={
                        "message": "Invoice validation failed - low confidence on total amount",
                        "level": "WARNING"
                    }
                ),
                RuleAction(
                    action_type=ActionType.STOP_PROCESSING,
                    parameters={}
                )
            ],
            tags=["validation", "invoice", "quality"]
        )
        
        # Large file handling rule
        large_file_rule = ProcessingRule(
            rule_id="large_file_handling",
            name="Large File Handling",
            description="Special handling for large files",
            rule_type=RuleType.CONDITION,
            priority=20,
            conditions=[
                Condition(
                    field_path="file_size",
                    operator=OperatorType.GREATER_THAN,
                    value=10485760  # 10MB
                )
            ],
            actions=[
                RuleAction(
                    action_type=ActionType.SET_MODE,
                    parameters={"mode": "local"}
                ),
                RuleAction(
                    action_type=ActionType.LOG_MESSAGE,
                    parameters={
                        "message": "Large file detected, using local processing",
                        "level": "INFO"
                    }
                )
            ],
            tags=["performance", "file_size"]
        )
        
        # Add rules
        self.add_rule(high_confidence_rule)
        self.add_rule(language_rule)
        self.add_rule(invoice_validation_rule)
        self.add_rule(large_file_rule)
        
        self.logger.info("Created built-in processing rules")
        self.save_rules()
    
    def load_rules(self):
        """Load rules from file."""
        if not self.rules_file.exists():
            return
        
        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                rules_data = json.load(f)
            
            for rule_data in rules_data:
                rule = ProcessingRule.from_dict(rule_data)
                self.rules[rule.rule_id] = rule
            
            self.logger.info(f"Loaded {len(self.rules)} processing rules")
            
        except Exception as e:
            self.logger.error(f"Error loading rules: {e}")
    
    def save_rules(self):
        """Save rules to file."""
        try:
            rules_data = [rule.to_dict() for rule in self.rules.values()]
            
            with open(self.rules_file, 'w', encoding='utf-8') as f:
                json.dump(rules_data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug("Saved processing rules to file")
            
        except Exception as e:
            self.logger.error(f"Error saving rules: {e}")
    
    def add_rule(self, rule: ProcessingRule):
        """Add a processing rule."""
        self.rules[rule.rule_id] = rule
        self.logger.info(f"Added rule: {rule.name}")
    
    def remove_rule(self, rule_id: str):
        """Remove a processing rule."""
        if rule_id in self.rules:
            rule_name = self.rules[rule_id].name
            del self.rules[rule_id]
            self.save_rules()
            self.logger.info(f"Removed rule: {rule_name}")
    
    def enable_rule(self, rule_id: str):
        """Enable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            self.save_rules()
            self.logger.info(f"Enabled rule: {rule_id}")
    
    def disable_rule(self, rule_id: str):
        """Disable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            self.save_rules()
            self.logger.info(f"Disabled rule: {rule_id}")
    
    def get_rule(self, rule_id: str) -> Optional[ProcessingRule]:
        """Get rule by ID."""
        return self.rules.get(rule_id)
    
    def list_rules(self, enabled_only: bool = False, 
                  rule_type: Optional[RuleType] = None,
                  tags: Optional[List[str]] = None) -> List[ProcessingRule]:
        """List rules with optional filtering."""
        rules = list(self.rules.values())
        
        if enabled_only:
            rules = [rule for rule in rules if rule.enabled]
        
        if rule_type:
            rules = [rule for rule in rules if rule.rule_type == rule_type]
        
        if tags:
            rules = [rule for rule in rules if any(tag in rule.tags for tag in tags)]
        
        # Sort by priority (highest first)
        rules.sort(key=lambda r: r.priority, reverse=True)
        
        return rules
    
    def apply_rules(self, context: Dict[str, Any], 
                   rule_type: Optional[RuleType] = None) -> List[Dict[str, Any]]:
        """Apply all applicable rules to the given context."""
        applicable_rules = self.list_rules(enabled_only=True, rule_type=rule_type)
        
        all_results = []
        
        for rule in applicable_rules:
            try:
                results = rule.execute(context)
                if results:
                    all_results.extend(results)
                    
                    # Check if processing should stop
                    if context.get("stop_processing", False):
                        self.logger.info("Processing stopped by rule")
                        break
                        
            except Exception as e:
                self.logger.error(f"Error executing rule {rule.name}: {e}")
        
        # Save updated rule statistics
        if all_results:
            self.save_rules()
        
        return all_results
    
    def validate_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run validation rules against context."""
        validation_results = self.apply_rules(context, RuleType.VALIDATION)
        
        has_errors = any(not result.get("success", True) for result in validation_results)
        
        return {
            "is_valid": not has_errors,
            "validation_results": validation_results,
            "stop_processing": context.get("stop_processing", False)
        }
    
    def get_rule_statistics(self) -> Dict[str, Any]:
        """Get rule execution statistics."""
        total_rules = len(self.rules)
        enabled_rules = sum(1 for rule in self.rules.values() if rule.enabled)
        
        # Most executed rules
        most_executed = sorted(
            self.rules.values(),
            key=lambda r: r.execution_count,
            reverse=True
        )[:5]
        
        # Recently executed rules
        recently_executed = [
            rule for rule in self.rules.values() 
            if rule.last_executed and rule.last_executed > datetime.now() - timedelta(hours=24)
        ]
        
        return {
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
            "disabled_rules": total_rules - enabled_rules,
            "total_executions": sum(rule.execution_count for rule in self.rules.values()),
            "most_executed": [
                {
                    "rule_id": rule.rule_id,
                    "name": rule.name,
                    "execution_count": rule.execution_count,
                    "last_executed": rule.last_executed.isoformat() if rule.last_executed else None
                }
                for rule in most_executed
            ],
            "recently_executed_count": len(recently_executed),
            "rules_by_type": {
                rule_type.value: sum(1 for rule in self.rules.values() 
                                   if rule.rule_type == rule_type)
                for rule_type in RuleType
            }
        }


def create_confidence_rule(min_confidence: float, action_mode: str = "cloud") -> ProcessingRule:
    """Helper to create a confidence-based rule."""
    return ProcessingRule(
        rule_id=f"confidence_rule_{min_confidence}",
        name=f"Low Confidence Rule ({min_confidence})",
        description=f"Switch to {action_mode} mode for low confidence",
        conditions=[
            Condition(
                field_path="ocr_result.confidence",
                operator=OperatorType.LESS_THAN,
                value=min_confidence
            )
        ],
        actions=[
            RuleAction(
                action_type=ActionType.SET_MODE,
                parameters={"mode": action_mode}
            )
        ]
    )


def create_field_validation_rule(field_name: str, required: bool = True) -> ProcessingRule:
    """Helper to create a field validation rule."""
    return ProcessingRule(
        rule_id=f"validate_{field_name}",
        name=f"Validate {field_name.title()}",
        description=f"Validate that {field_name} field is present and valid",
        rule_type=RuleType.VALIDATION,
        conditions=[
            Condition(
                field_path=f"extracted_fields.{field_name}.value",
                operator=OperatorType.IS_EMPTY if required else OperatorType.IS_NOT_EMPTY,
                value=None
            )
        ],
        actions=[
            RuleAction(
                action_type=ActionType.LOG_MESSAGE,
                parameters={
                    "message": f"Required field {field_name} is missing",
                    "level": "WARNING"
                }
            ),
            RuleAction(
                action_type=ActionType.STOP_PROCESSING,
                parameters={}
            ) if required else RuleAction(
                action_type=ActionType.LOG_MESSAGE,
                parameters={"message": f"Optional field {field_name} validated", "level": "INFO"}
            )
        ]
    )