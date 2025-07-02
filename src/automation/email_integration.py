"""
Email integration for automated OCR processing.

This module provides email monitoring and processing capabilities,
allowing automatic OCR processing of email attachments.
"""

import imaplib
import poplib
import smtplib
import email
import io
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from email.mime.base import MimeBase
from email import encoders
import ssl
import re
import tempfile
import mimetypes

from ..utils.logger import get_logger


@dataclass
class EmailAccount:
    """Email account configuration."""
    
    name: str
    email_address: str
    
    # IMAP settings
    imap_server: str = ""
    imap_port: int = 993
    imap_use_ssl: bool = True
    
    # POP3 settings (alternative to IMAP)
    pop_server: str = ""
    pop_port: int = 995
    pop_use_ssl: bool = True
    
    # SMTP settings (for sending)
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_use_tls: bool = True
    
    # Authentication
    username: str = ""
    password: str = ""
    
    # Processing settings
    enabled: bool = True
    folders_to_monitor: List[str] = field(default_factory=lambda: ["INBOX"])
    mark_as_read: bool = True
    delete_after_processing: bool = False
    
    # Filters
    sender_whitelist: List[str] = field(default_factory=list)
    sender_blacklist: List[str] = field(default_factory=list)
    subject_filters: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Set default values based on email provider."""
        if not self.username:
            self.username = self.email_address
        
        # Auto-configure common providers
        domain = self.email_address.split('@')[1].lower()
        
        if 'gmail' in domain:
            self.imap_server = self.imap_server or "imap.gmail.com"
            self.smtp_server = self.smtp_server or "smtp.gmail.com"
        elif 'outlook' in domain or 'hotmail' in domain:
            self.imap_server = self.imap_server or "outlook.office365.com"
            self.smtp_server = self.smtp_server or "smtp-mail.outlook.com"
        elif 'yahoo' in domain:
            self.imap_server = self.imap_server or "imap.mail.yahoo.com"
            self.smtp_server = self.smtp_server or "smtp.mail.yahoo.com"


@dataclass
class EmailFilter:
    """Email filtering configuration."""
    
    name: str
    enabled: bool = True
    
    # Sender filters
    from_addresses: List[str] = field(default_factory=list)
    from_domains: List[str] = field(default_factory=list)
    
    # Subject filters
    subject_contains: List[str] = field(default_factory=list)
    subject_regex: Optional[str] = None
    
    # Attachment filters
    attachment_extensions: List[str] = field(default_factory=lambda: ['.pdf', '.png', '.jpg', '.jpeg'])
    min_attachment_size: int = 1024  # bytes
    max_attachment_size: int = 50 * 1024 * 1024  # 50MB
    
    # Processing configuration
    workflow_name: Optional[str] = None
    template_name: Optional[str] = None
    output_folder: Optional[str] = None
    
    def matches_email(self, email_msg: email.message.EmailMessage) -> bool:
        """Check if email matches this filter."""
        if not self.enabled:
            return False
        
        # Check sender
        from_header = email_msg.get('From', '').lower()
        
        if self.from_addresses:
            if not any(addr.lower() in from_header for addr in self.from_addresses):
                return False
        
        if self.from_domains:
            if not any(domain.lower() in from_header for domain in self.from_domains):
                return False
        
        # Check subject
        subject = email_msg.get('Subject', '').lower()
        
        if self.subject_contains:
            if not any(keyword.lower() in subject for keyword in self.subject_contains):
                return False
        
        if self.subject_regex:
            try:
                if not re.search(self.subject_regex, subject, re.IGNORECASE):
                    return False
            except re.error:
                pass
        
        return True


@dataclass
class EmailAttachment:
    """Represents an email attachment."""
    
    filename: str
    content_type: str
    size: int
    content: bytes
    
    def save_to_file(self, file_path: Path) -> bool:
        """Save attachment to file."""
        try:
            with open(file_path, 'wb') as f:
                f.write(self.content)
            return True
        except Exception:
            return False
    
    def is_processable(self) -> bool:
        """Check if attachment can be processed by OCR."""
        processable_types = [
            'application/pdf',
            'image/png',
            'image/jpeg',
            'image/jpg',
            'image/tiff',
            'image/bmp'
        ]
        
        # Check by content type
        if self.content_type.lower() in processable_types:
            return True
        
        # Check by filename extension
        ext = Path(self.filename).suffix.lower()
        processable_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']
        
        return ext in processable_extensions


@dataclass
class ProcessedEmail:
    """Represents a processed email with results."""
    
    message_id: str
    from_address: str
    subject: str
    received_date: datetime
    
    attachments_processed: int = 0
    attachments_total: int = 0
    processing_results: List[Dict[str, Any]] = field(default_factory=list)
    
    success: bool = False
    error_message: Optional[str] = None
    processing_time: float = 0.0


class EmailProcessor:
    """Processes emails and their attachments for OCR."""
    
    def __init__(self, workflow_manager=None, temp_dir: Optional[Path] = None):
        self.workflow_manager = workflow_manager
        self.temp_dir = temp_dir or Path(tempfile.gettempdir()) / "ocr_email_attachments"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = get_logger("email_processor")
        
        # Statistics
        self.stats = {
            "emails_processed": 0,
            "attachments_processed": 0,
            "processing_errors": 0,
            "start_time": datetime.now()
        }
    
    def extract_attachments(self, email_msg: email.message.EmailMessage) -> List[EmailAttachment]:
        """Extract attachments from email message."""
        attachments = []
        
        try:
            for part in email_msg.walk():
                if part.get_content_disposition() == 'attachment':
                    filename = part.get_filename()
                    if not filename:
                        continue
                    
                    content_type = part.get_content_type()
                    content = part.get_payload(decode=True)
                    
                    if content:
                        attachment = EmailAttachment(
                            filename=filename,
                            content_type=content_type,
                            size=len(content),
                            content=content
                        )
                        attachments.append(attachment)
            
        except Exception as e:
            self.logger.error(f"Error extracting attachments: {e}")
        
        return attachments
    
    def process_email(self, email_msg: email.message.EmailMessage, 
                     email_filter: EmailFilter) -> ProcessedEmail:
        """Process an email message and its attachments."""
        start_time = time.time()
        
        # Create processed email record
        processed_email = ProcessedEmail(
            message_id=email_msg.get('Message-ID', ''),
            from_address=email_msg.get('From', ''),
            subject=email_msg.get('Subject', ''),
            received_date=datetime.now()
        )
        
        try:
            self.logger.info(f"Processing email: {processed_email.subject}")
            
            # Extract attachments
            attachments = self.extract_attachments(email_msg)
            processed_email.attachments_total = len(attachments)
            
            if not attachments:
                self.logger.info("No attachments found in email")
                processed_email.success = True
                return processed_email
            
            # Filter processable attachments
            processable_attachments = [att for att in attachments if att.is_processable()]
            
            if not processable_attachments:
                self.logger.info("No processable attachments found")
                processed_email.success = True
                return processed_email
            
            # Process each attachment
            for attachment in processable_attachments:
                try:
                    result = self._process_attachment(attachment, email_filter, processed_email)
                    processed_email.processing_results.append(result)
                    
                    if result.get('success', False):
                        processed_email.attachments_processed += 1
                        
                except Exception as e:
                    self.logger.error(f"Error processing attachment {attachment.filename}: {e}")
                    processed_email.processing_results.append({
                        'filename': attachment.filename,
                        'success': False,
                        'error': str(e)
                    })
            
            # Mark as successful if at least one attachment processed
            processed_email.success = processed_email.attachments_processed > 0
            
            # Update statistics
            self.stats["emails_processed"] += 1
            self.stats["attachments_processed"] += processed_email.attachments_processed
            
        except Exception as e:
            processed_email.error_message = str(e)
            processed_email.success = False
            self.stats["processing_errors"] += 1
            self.logger.error(f"Error processing email: {e}")
        
        finally:
            processed_email.processing_time = time.time() - start_time
        
        return processed_email
    
    def _process_attachment(self, attachment: EmailAttachment, 
                          email_filter: EmailFilter, 
                          processed_email: ProcessedEmail) -> Dict[str, Any]:
        """Process a single attachment."""
        result = {
            'filename': attachment.filename,
            'size': attachment.size,
            'content_type': attachment.content_type,
            'success': False
        }
        
        try:
            # Save attachment to temporary file
            temp_file = self.temp_dir / f"{int(time.time())}_{attachment.filename}"
            
            if not attachment.save_to_file(temp_file):
                raise Exception("Failed to save attachment to temporary file")
            
            # Prepare processing context
            context = {
                'file_path': str(temp_file),
                'email_from': processed_email.from_address,
                'email_subject': processed_email.subject,
                'attachment_filename': attachment.filename,
                'output_folder': email_filter.output_folder
            }
            
            # Process with workflow if configured
            if email_filter.workflow_name and self.workflow_manager:
                import asyncio
                
                # Create event loop for this thread if needed
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                workflow_execution = loop.run_until_complete(
                    self.workflow_manager.trigger_workflow(email_filter.workflow_name, context)
                )
                
                if workflow_execution and workflow_execution.status.value == "completed":
                    result['success'] = True
                    result['workflow_execution_id'] = workflow_execution.execution_id
                    result['ocr_result'] = workflow_execution.final_context.get('ocr_result')
                else:
                    result['error'] = 'Workflow execution failed'
            
            else:
                # Basic OCR processing without workflow
                result['success'] = True
                result['message'] = 'Attachment saved for manual processing'
                result['temp_file'] = str(temp_file)
            
            self.logger.info(f"Processed attachment: {attachment.filename}")
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"Error processing attachment {attachment.filename}: {e}")
        
        finally:
            # Clean up temporary file (optional, might want to keep for debugging)
            try:
                if temp_file.exists() and result.get('success', False):
                    temp_file.unlink()
            except Exception:
                pass
        
        return result


class EmailMonitor:
    """Monitors email accounts for new messages with attachments."""
    
    def __init__(self, email_processor: EmailProcessor):
        self.email_processor = email_processor
        self.accounts: Dict[str, EmailAccount] = {}
        self.filters: Dict[str, EmailFilter] = {}
        
        self.running = False
        self.monitor_threads: List[threading.Thread] = []
        
        self.logger = get_logger("email_monitor")
        self.processed_messages: set = set()  # Track processed message IDs
        
        # Statistics
        self.stats = {
            "emails_checked": 0,
            "emails_processed": 0,
            "last_check": None,
            "errors": 0
        }
    
    def add_account(self, account: EmailAccount):
        """Add email account to monitor."""
        self.accounts[account.name] = account
        self.logger.info(f"Added email account: {account.name} ({account.email_address})")
    
    def add_filter(self, email_filter: EmailFilter):
        """Add email filter."""
        self.filters[email_filter.name] = email_filter
        self.logger.info(f"Added email filter: {email_filter.name}")
    
    def start_monitoring(self, check_interval: int = 300):
        """Start monitoring email accounts."""
        if self.running:
            self.logger.warning("Email monitoring is already running")
            return
        
        if not self.accounts:
            self.logger.warning("No email accounts configured")
            return
        
        self.running = True
        self.logger.info(f"Starting email monitoring for {len(self.accounts)} accounts")
        
        # Start monitoring thread for each account
        for account in self.accounts.values():
            if account.enabled:
                thread = threading.Thread(
                    target=self._monitor_account,
                    args=(account, check_interval),
                    daemon=True
                )
                thread.start()
                self.monitor_threads.append(thread)
        
        self.logger.info("Email monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring email accounts."""
        if not self.running:
            return
        
        self.running = False
        self.logger.info("Stopping email monitoring...")
        
        # Wait for threads to finish
        for thread in self.monitor_threads:
            thread.join(timeout=5.0)
        
        self.monitor_threads.clear()
        self.logger.info("Email monitoring stopped")
    
    def _monitor_account(self, account: EmailAccount, check_interval: int):
        """Monitor a single email account."""
        self.logger.info(f"Starting monitoring for account: {account.name}")
        
        while self.running:
            try:
                self._check_account(account)
                self.stats["last_check"] = datetime.now()
                
            except Exception as e:
                self.logger.error(f"Error checking account {account.name}: {e}")
                self.stats["errors"] += 1
            
            # Wait before next check
            time.sleep(check_interval)
        
        self.logger.info(f"Stopped monitoring account: {account.name}")
    
    def _check_account(self, account: EmailAccount):
        """Check an email account for new messages."""
        if account.imap_server:
            self._check_imap_account(account)
        elif account.pop_server:
            self._check_pop_account(account)
        else:
            self.logger.warning(f"No server configured for account {account.name}")
    
    def _check_imap_account(self, account: EmailAccount):
        """Check IMAP account for new messages."""
        try:
            # Connect to IMAP server
            if account.imap_use_ssl:
                mail = imaplib.IMAP4_SSL(account.imap_server, account.imap_port)
            else:
                mail = imaplib.IMAP4(account.imap_server, account.imap_port)
            
            mail.login(account.username, account.password)
            
            # Check each folder
            for folder in account.folders_to_monitor:
                try:
                    mail.select(folder)
                    
                    # Search for unseen messages with attachments
                    typ, message_numbers = mail.search(None, 'UNSEEN')
                    
                    for num in message_numbers[0].split():
                        try:
                            # Fetch message
                            typ, msg_data = mail.fetch(num, '(RFC822)')
                            
                            email_body = msg_data[0][1]
                            email_msg = email.message_from_bytes(email_body)
                            
                            message_id = email_msg.get('Message-ID', '')
                            
                            # Skip if already processed
                            if message_id in self.processed_messages:
                                continue
                            
                            self.stats["emails_checked"] += 1
                            
                            # Check if email has attachments
                            if not self._has_attachments(email_msg):
                                continue
                            
                            # Apply filters
                            matching_filters = self._get_matching_filters(email_msg)
                            
                            if matching_filters:
                                for email_filter in matching_filters:
                                    processed_email = self.email_processor.process_email(
                                        email_msg, email_filter
                                    )
                                    
                                    if processed_email.success:
                                        self.stats["emails_processed"] += 1
                                        self.logger.info(
                                            f"Successfully processed email: {processed_email.subject}"
                                        )
                                    
                                    # Mark message as read if configured
                                    if account.mark_as_read:
                                        mail.store(num, '+FLAGS', '\\Seen')
                                    
                                    # Delete message if configured
                                    if account.delete_after_processing:
                                        mail.store(num, '+FLAGS', '\\Deleted')
                                
                                # Track processed message
                                self.processed_messages.add(message_id)
                        
                        except Exception as e:
                            self.logger.error(f"Error processing message {num}: {e}")
                
                except Exception as e:
                    self.logger.error(f"Error checking folder {folder}: {e}")
            
            # Expunge deleted messages
            mail.expunge()
            mail.close()
            mail.logout()
            
        except Exception as e:
            self.logger.error(f"Error connecting to IMAP server: {e}")
    
    def _check_pop_account(self, account: EmailAccount):
        """Check POP3 account for new messages."""
        try:
            # Connect to POP3 server
            if account.pop_use_ssl:
                mail = poplib.POP3_SSL(account.pop_server, account.pop_port)
            else:
                mail = poplib.POP3(account.pop_server, account.pop_port)
            
            mail.user(account.username)
            mail.pass_(account.password)
            
            # Get message count
            num_messages = len(mail.list()[1])
            
            # Process each message
            for i in range(1, num_messages + 1):
                try:
                    # Retrieve message
                    raw_email = b"\n".join(mail.retr(i)[1])
                    email_msg = email.message_from_bytes(raw_email)
                    
                    message_id = email_msg.get('Message-ID', '')
                    
                    # Skip if already processed
                    if message_id in self.processed_messages:
                        continue
                    
                    self.stats["emails_checked"] += 1
                    
                    # Check if email has attachments
                    if not self._has_attachments(email_msg):
                        continue
                    
                    # Apply filters
                    matching_filters = self._get_matching_filters(email_msg)
                    
                    if matching_filters:
                        for email_filter in matching_filters:
                            processed_email = self.email_processor.process_email(
                                email_msg, email_filter
                            )
                            
                            if processed_email.success:
                                self.stats["emails_processed"] += 1
                        
                        # Delete message if configured
                        if account.delete_after_processing:
                            mail.dele(i)
                        
                        # Track processed message
                        self.processed_messages.add(message_id)
                
                except Exception as e:
                    self.logger.error(f"Error processing POP3 message {i}: {e}")
            
            mail.quit()
            
        except Exception as e:
            self.logger.error(f"Error connecting to POP3 server: {e}")
    
    def _has_attachments(self, email_msg: email.message.EmailMessage) -> bool:
        """Check if email has attachments."""
        for part in email_msg.walk():
            if part.get_content_disposition() == 'attachment':
                return True
        return False
    
    def _get_matching_filters(self, email_msg: email.message.EmailMessage) -> List[EmailFilter]:
        """Get filters that match the email."""
        matching_filters = []
        
        for email_filter in self.filters.values():
            if email_filter.matches_email(email_msg):
                matching_filters.append(email_filter)
        
        return matching_filters
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        processor_stats = self.email_processor.stats.copy()
        
        return {
            "monitoring": {
                "running": self.running,
                "accounts_configured": len(self.accounts),
                "filters_configured": len(self.filters),
                "emails_checked": self.stats["emails_checked"],
                "emails_processed": self.stats["emails_processed"],
                "last_check": self.stats["last_check"].isoformat() if self.stats["last_check"] else None,
                "errors": self.stats["errors"]
            },
            "processing": {
                "emails_processed": processor_stats["emails_processed"],
                "attachments_processed": processor_stats["attachments_processed"],
                "processing_errors": processor_stats["processing_errors"],
                "uptime": (datetime.now() - processor_stats["start_time"]).total_seconds()
            }
        }


def create_gmail_account(email_address: str, app_password: str) -> EmailAccount:
    """Helper to create Gmail account configuration."""
    return EmailAccount(
        name=f"Gmail_{email_address.split('@')[0]}",
        email_address=email_address,
        username=email_address,
        password=app_password,
        imap_server="imap.gmail.com",
        imap_port=993,
        smtp_server="smtp.gmail.com",
        smtp_port=587
    )


def create_outlook_account(email_address: str, password: str) -> EmailAccount:
    """Helper to create Outlook account configuration."""
    return EmailAccount(
        name=f"Outlook_{email_address.split('@')[0]}",
        email_address=email_address,
        username=email_address,
        password=password,
        imap_server="outlook.office365.com",
        imap_port=993,
        smtp_server="smtp-mail.outlook.com",
        smtp_port=587
    )


def create_invoice_filter(workflow_name: str = "Invoice Processing", 
                         output_folder: str = "invoices/") -> EmailFilter:
    """Helper to create invoice processing filter."""
    return EmailFilter(
        name="Invoice Filter",
        subject_contains=["invoice", "fatura", "nota fiscal", "cobrança"],
        attachment_extensions=[".pdf"],
        workflow_name=workflow_name,
        output_folder=output_folder
    )