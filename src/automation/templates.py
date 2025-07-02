"""
Document template system for automated OCR processing.

This module provides templates for different document types, enabling
specialized processing rules, field extraction, and output formatting.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Pattern
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import logging

from ..utils.logger import get_logger


class DocumentType(Enum):
    """Supported document types."""
    INVOICE = "invoice"
    RECEIPT = "receipt"
    BUSINESS_CARD = "business_card"
    LEGAL_DOCUMENT = "legal_document"
    FORM = "form"
    TABLE = "table"
    LETTER = "letter"
    CONTRACT = "contract"
    ID_DOCUMENT = "id_document"
    GENERAL = "general"


class FieldType(Enum):
    """Types of fields that can be extracted."""
    TEXT = "text"
    NUMBER = "number"
    CURRENCY = "currency"
    DATE = "date"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    TABLE = "table"
    PERCENTAGE = "percentage"


@dataclass
class FieldExtractor:
    """Configuration for extracting a specific field from document."""
    
    name: str
    field_type: FieldType
    patterns: List[str] = field(default_factory=list)
    required: bool = False
    validation_regex: Optional[str] = None
    default_value: Optional[str] = None
    post_processing: List[str] = field(default_factory=list)
    confidence_threshold: float = 0.7
    
    def __post_init__(self):
        """Compile regex patterns for efficiency."""
        self.compiled_patterns = []
        for pattern in self.patterns:
            try:
                self.compiled_patterns.append(re.compile(pattern, re.IGNORECASE | re.MULTILINE))
            except re.error as e:
                logging.warning(f"Invalid regex pattern '{pattern}': {e}")
    
    def extract(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract field value from text."""
        try:
            for pattern in self.compiled_patterns:
                matches = pattern.finditer(text)
                for match in matches:
                    value = self._process_match(match)
                    if value and self._validate_value(value):
                        return {
                            "value": value,
                            "confidence": self._calculate_confidence(match, text),
                            "position": match.span(),
                            "raw_match": match.group()
                        }
            
            # Return default value if no match found
            if self.default_value:
                return {
                    "value": self.default_value,
                    "confidence": 0.5,
                    "position": None,
                    "raw_match": None
                }
            
            return None
            
        except Exception as e:
            logging.error(f"Error extracting field '{self.name}': {e}")
            return None
    
    def _process_match(self, match: re.Match) -> Optional[str]:
        """Process regex match based on field type."""
        try:
            # Get the captured group or full match
            value = match.group(1) if match.groups() else match.group()
            value = value.strip()
            
            # Apply field type specific processing
            if self.field_type == FieldType.NUMBER:
                # Extract numeric value
                numeric = re.sub(r'[^\d.,]', '', value)
                numeric = numeric.replace(',', '.')
                return numeric if numeric else None
                
            elif self.field_type == FieldType.CURRENCY:
                # Extract currency amount
                amount_match = re.search(r'[\d.,]+', value)
                if amount_match:
                    amount = amount_match.group().replace(',', '.')
                    # Try to identify currency symbol
                    currency_match = re.search(r'[R$€£¥₹]+|USD|EUR|BRL|GBP', value)
                    currency = currency_match.group() if currency_match else ""
                    return f"{amount} {currency}".strip()
                return None
                
            elif self.field_type == FieldType.DATE:
                # Normalize date format
                date_patterns = [
                    r'(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})',
                    r'(\d{2,4})[\/\-.](\d{1,2})[\/\-.](\d{1,2})',
                ]
                for pattern in date_patterns:
                    date_match = re.search(pattern, value)
                    if date_match:
                        return date_match.group()
                return value
                
            elif self.field_type == FieldType.EMAIL:
                # Validate email format
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                email_match = re.search(email_pattern, value)
                return email_match.group() if email_match else None
                
            elif self.field_type == FieldType.PHONE:
                # Normalize phone number
                phone = re.sub(r'[^\d+\-\(\)\s]', '', value)
                return phone.strip() if phone else None
                
            else:
                return value
                
        except Exception as e:
            logging.error(f"Error processing match for field '{self.name}': {e}")
            return None
    
    def _validate_value(self, value: str) -> bool:
        """Validate extracted value."""
        if not value:
            return False
        
        if self.validation_regex:
            try:
                return bool(re.match(self.validation_regex, value))
            except re.error:
                return True
        
        return True
    
    def _calculate_confidence(self, match: re.Match, full_text: str) -> float:
        """Calculate confidence score for the extracted value."""
        base_confidence = 0.8
        
        # Adjust based on match quality
        match_length = len(match.group())
        if match_length > 50:
            base_confidence += 0.1
        elif match_length < 5:
            base_confidence -= 0.1
        
        # Adjust based on context
        context_start = max(0, match.start() - 50)
        context_end = min(len(full_text), match.end() + 50)
        context = full_text[context_start:context_end].lower()
        
        # Look for relevant keywords in context
        relevant_keywords = {
            FieldType.CURRENCY: ['total', 'amount', 'price', 'valor', 'preço'],
            FieldType.DATE: ['date', 'data', 'vencimento', 'due'],
            FieldType.EMAIL: ['email', 'e-mail', 'contact', 'contato'],
            FieldType.PHONE: ['phone', 'telefone', 'tel', 'celular'],
        }
        
        keywords = relevant_keywords.get(self.field_type, [])
        for keyword in keywords:
            if keyword in context:
                base_confidence += 0.05
                break
        
        return min(1.0, max(0.0, base_confidence))


@dataclass
class ProcessingRule:
    """Rule for conditional processing based on document content."""
    
    name: str
    condition: str  # Text pattern to match
    action: str  # Action to take (e.g., "set_confidence", "set_language", "add_field")
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    
    def __post_init__(self):
        """Compile condition pattern."""
        try:
            self.condition_pattern = re.compile(self.condition, re.IGNORECASE)
        except re.error as e:
            logging.warning(f"Invalid condition pattern '{self.condition}': {e}")
            self.condition_pattern = None
    
    def matches(self, text: str) -> bool:
        """Check if rule condition matches the text."""
        if not self.condition_pattern:
            return False
        return bool(self.condition_pattern.search(text))


@dataclass
class DocumentTemplate:
    """Template for processing specific document types."""
    
    name: str
    document_type: DocumentType
    description: str = ""
    
    # Identification patterns
    identification_patterns: List[str] = field(default_factory=list)
    confidence_threshold: float = 0.8
    
    # Field extraction
    fields: List[FieldExtractor] = field(default_factory=list)
    
    # Processing settings
    ocr_language: str = "por+eng"
    ocr_mode: str = "hybrid"
    preprocessing_steps: List[str] = field(default_factory=list)
    
    # Output settings
    output_formats: List[str] = field(default_factory=lambda: ["json", "markdown"])
    output_template: Optional[str] = None
    
    # Processing rules
    rules: List[ProcessingRule] = field(default_factory=list)
    
    # Metadata
    created_date: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.0"
    author: str = "OCR Enhanced"
    
    def __post_init__(self):
        """Compile identification patterns."""
        self.compiled_patterns = []
        for pattern in self.identification_patterns:
            try:
                self.compiled_patterns.append(re.compile(pattern, re.IGNORECASE | re.MULTILINE))
            except re.error as e:
                logging.warning(f"Invalid identification pattern '{pattern}': {e}")
    
    def matches_document(self, text: str) -> float:
        """Check if template matches the document and return confidence score."""
        if not self.compiled_patterns:
            return 0.0
        
        matches = 0
        total_patterns = len(self.compiled_patterns)
        
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                matches += 1
        
        confidence = matches / total_patterns if total_patterns > 0 else 0.0
        return confidence
    
    def extract_fields(self, text: str) -> Dict[str, Any]:
        """Extract all configured fields from document text."""
        extracted_fields = {}
        
        for field_extractor in self.fields:
            result = field_extractor.extract(text)
            if result:
                extracted_fields[field_extractor.name] = result
            elif field_extractor.required:
                # Mark required field as missing
                extracted_fields[field_extractor.name] = {
                    "value": None,
                    "confidence": 0.0,
                    "position": None,
                    "error": "Required field not found"
                }
        
        return extracted_fields
    
    def apply_rules(self, text: str, processing_config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply processing rules to modify configuration."""
        config = processing_config.copy()
        
        # Sort rules by priority
        sorted_rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)
        
        for rule in sorted_rules:
            if rule.matches(text):
                logging.info(f"Applying rule: {rule.name}")
                
                if rule.action == "set_confidence":
                    config["confidence_threshold"] = rule.parameters.get("threshold", 0.75)
                elif rule.action == "set_language":
                    config["language"] = rule.parameters.get("language", "eng")
                elif rule.action == "set_mode":
                    config["mode"] = rule.parameters.get("mode", "hybrid")
                elif rule.action == "add_preprocessing":
                    steps = config.get("preprocessing_steps", [])
                    steps.extend(rule.parameters.get("steps", []))
                    config["preprocessing_steps"] = steps
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentTemplate':
        """Create template from dictionary."""
        # Convert enums
        if 'document_type' in data and isinstance(data['document_type'], str):
            data['document_type'] = DocumentType(data['document_type'])
        
        # Convert field extractors
        if 'fields' in data:
            fields = []
            for field_data in data['fields']:
                if isinstance(field_data, dict):
                    if 'field_type' in field_data and isinstance(field_data['field_type'], str):
                        field_data['field_type'] = FieldType(field_data['field_type'])
                    fields.append(FieldExtractor(**field_data))
                else:
                    fields.append(field_data)
            data['fields'] = fields
        
        # Convert rules
        if 'rules' in data:
            rules = []
            for rule_data in data['rules']:
                if isinstance(rule_data, dict):
                    rules.append(ProcessingRule(**rule_data))
                else:
                    rules.append(rule_data)
            data['rules'] = rules
        
        return cls(**data)


class TemplateManager:
    """Manages document templates for automatic OCR processing."""
    
    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates_dir = templates_dir or Path.home() / ".ocr_enhanced" / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        self.templates: Dict[str, DocumentTemplate] = {}
        self.logger = get_logger("template_manager")
        
        # Load built-in templates
        self._load_builtin_templates()
        
        # Load user templates
        self.load_templates()
    
    def _load_builtin_templates(self):
        """Load built-in document templates."""
        
        # Invoice template
        invoice_template = DocumentTemplate(
            name="Brazilian Invoice",
            document_type=DocumentType.INVOICE,
            description="Template for Brazilian invoices and NFe",
            identification_patterns=[
                r"nota\s+fiscal",
                r"nfe",
                r"cnpj",
                r"valor\s+total",
                r"fatura"
            ],
            fields=[
                FieldExtractor(
                    name="invoice_number",
                    field_type=FieldType.TEXT,
                    patterns=[
                        r"n[úu]mero\s*:?\s*(\d+)",
                        r"nf\s*:?\s*(\d+)",
                        r"nota\s+fiscal\s*:?\s*(\d+)"
                    ],
                    required=True
                ),
                FieldExtractor(
                    name="total_amount",
                    field_type=FieldType.CURRENCY,
                    patterns=[
                        r"total\s*:?\s*(r?\$?\s*[\d.,]+)",
                        r"valor\s+total\s*:?\s*(r?\$?\s*[\d.,]+)"
                    ],
                    required=True
                ),
                FieldExtractor(
                    name="issue_date",
                    field_type=FieldType.DATE,
                    patterns=[
                        r"data\s+de\s+emiss[ãa]o\s*:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
                        r"emitida\s+em\s*:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})"
                    ]
                ),
                FieldExtractor(
                    name="cnpj",
                    field_type=FieldType.TEXT,
                    patterns=[
                        r"cnpj\s*:?\s*(\d{2}\.?\d{3}\.?\d{3}\/?\d{4}\-?\d{2})"
                    ],
                    validation_regex=r"\d{2}\.?\d{3}\.?\d{3}\/?\d{4}\-?\d{2}"
                )
            ],
            rules=[
                ProcessingRule(
                    name="High confidence for invoices",
                    condition=r"nota\s+fiscal",
                    action="set_confidence",
                    parameters={"threshold": 0.9}
                )
            ]
        )
        
        # Business card template
        business_card_template = DocumentTemplate(
            name="Business Card",
            document_type=DocumentType.BUSINESS_CARD,
            description="Template for business cards",
            identification_patterns=[
                r"@\w+\.\w+",  # Email
                r"\(\d{2}\)\s*\d{4,5}\-?\d{4}",  # Phone
                r"cel\.|celular",
                r"fone|telefone"
            ],
            fields=[
                FieldExtractor(
                    name="name",
                    field_type=FieldType.TEXT,
                    patterns=[
                        r"^([A-Z][a-z]+\s+[A-Z][a-z]+.*?)$"
                    ],
                    required=True
                ),
                FieldExtractor(
                    name="email",
                    field_type=FieldType.EMAIL,
                    patterns=[
                        r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
                    ]
                ),
                FieldExtractor(
                    name="phone",
                    field_type=FieldType.PHONE,
                    patterns=[
                        r"(\(\d{2}\)\s*\d{4,5}\-?\d{4})",
                        r"(\d{2}\s*\d{4,5}\-?\d{4})"
                    ]
                ),
                FieldExtractor(
                    name="company",
                    field_type=FieldType.TEXT,
                    patterns=[
                        r"([A-Z][a-zA-Z\s&]+(?:Ltda|S\.A\.|Inc|Corp)\.?)"
                    ]
                )
            ]
        )
        
        # Receipt template
        receipt_template = DocumentTemplate(
            name="Receipt",
            document_type=DocumentType.RECEIPT,
            description="Template for receipts and cupom fiscal",
            identification_patterns=[
                r"cupom\s+fiscal",
                r"recibo",
                r"comprovante",
                r"total\s+pago"
            ],
            fields=[
                FieldExtractor(
                    name="total_paid",
                    field_type=FieldType.CURRENCY,
                    patterns=[
                        r"total\s*:?\s*(r?\$?\s*[\d.,]+)",
                        r"pago\s*:?\s*(r?\$?\s*[\d.,]+)"
                    ],
                    required=True
                ),
                FieldExtractor(
                    name="establishment",
                    field_type=FieldType.TEXT,
                    patterns=[
                        r"^([A-Z\s&]+)$"
                    ]
                ),
                FieldExtractor(
                    name="date_time",
                    field_type=FieldType.DATE,
                    patterns=[
                        r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\s+\d{1,2}:\d{2})"
                    ]
                )
            ]
        )
        
        # Register built-in templates
        self.templates[invoice_template.name] = invoice_template
        self.templates[business_card_template.name] = business_card_template
        self.templates[receipt_template.name] = receipt_template
        
        self.logger.info(f"Loaded {len(self.templates)} built-in templates")
    
    def load_templates(self):
        """Load templates from files."""
        template_files = self.templates_dir.glob("*.json")
        loaded_count = 0
        
        for template_file in template_files:
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
                
                template = DocumentTemplate.from_dict(template_data)
                self.templates[template.name] = template
                loaded_count += 1
                
            except Exception as e:
                self.logger.error(f"Error loading template {template_file}: {e}")
        
        self.logger.info(f"Loaded {loaded_count} user templates from {self.templates_dir}")
    
    def save_template(self, template: DocumentTemplate):
        """Save template to file."""
        try:
            template_file = self.templates_dir / f"{template.name}.json"
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(template.to_dict(), f, indent=2, ensure_ascii=False)
            
            self.templates[template.name] = template
            self.logger.info(f"Saved template: {template.name}")
            
        except Exception as e:
            self.logger.error(f"Error saving template {template.name}: {e}")
    
    def delete_template(self, template_name: str):
        """Delete template."""
        if template_name in self.templates:
            template_file = self.templates_dir / f"{template_name}.json"
            if template_file.exists():
                template_file.unlink()
            
            del self.templates[template_name]
            self.logger.info(f"Deleted template: {template_name}")
    
    def get_template(self, template_name: str) -> Optional[DocumentTemplate]:
        """Get template by name."""
        return self.templates.get(template_name)
    
    def list_templates(self) -> List[str]:
        """List all available template names."""
        return list(self.templates.keys())
    
    def identify_document_type(self, text: str) -> Optional[DocumentTemplate]:
        """Identify the best matching template for the document."""
        best_template = None
        best_confidence = 0.0
        
        for template in self.templates.values():
            confidence = template.matches_document(text)
            if confidence > best_confidence and confidence >= template.confidence_threshold:
                best_confidence = confidence
                best_template = template
        
        if best_template:
            self.logger.info(
                f"Identified document as '{best_template.name}' "
                f"with confidence {best_confidence:.2f}"
            )
        
        return best_template
    
    def process_document_with_template(self, text: str, template: DocumentTemplate) -> Dict[str, Any]:
        """Process document using specific template."""
        result = {
            "template_name": template.name,
            "document_type": template.document_type.value,
            "extracted_fields": template.extract_fields(text),
            "processing_config": template.apply_rules(text, {
                "language": template.ocr_language,
                "mode": template.ocr_mode,
                "confidence_threshold": template.confidence_threshold,
                "output_formats": template.output_formats
            }),
            "template_version": template.version,
            "processed_at": datetime.now().isoformat()
        }
        
        return result
    
    def auto_process_document(self, text: str) -> Dict[str, Any]:
        """Automatically identify and process document with best matching template."""
        template = self.identify_document_type(text)
        
        if template:
            return self.process_document_with_template(text, template)
        else:
            # Return basic processing for unidentified documents
            return {
                "template_name": "General",
                "document_type": DocumentType.GENERAL.value,
                "extracted_fields": {},
                "processing_config": {
                    "language": "por+eng",
                    "mode": "hybrid",
                    "confidence_threshold": 0.75,
                    "output_formats": ["json", "markdown"]
                },
                "template_version": "1.0",
                "processed_at": datetime.now().isoformat()
            }