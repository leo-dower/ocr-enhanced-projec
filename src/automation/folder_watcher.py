"""
Folder watching system for automatic OCR processing.

This module provides real-time monitoring of directories for new files,
automatically triggering OCR processing when documents are added.
"""

import os
import time
import threading
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent

from ..utils.logger import get_logger
from ..core.config import OCRConfig


@dataclass
class WatcherConfig:
    """Configuration for folder watching."""
    
    # Paths
    watch_folders: List[str] = field(default_factory=list)
    output_folder: str = ""
    
    # File filtering
    file_extensions: Set[str] = field(default_factory=lambda: {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp'})
    exclude_patterns: List[str] = field(default_factory=list)
    min_file_size: int = 1024  # Minimum file size in bytes
    max_file_size: int = 100 * 1024 * 1024  # Maximum file size in bytes (100MB)
    
    # Processing behavior
    processing_delay: float = 2.0  # Seconds to wait after file creation before processing
    recursive_watching: bool = True
    move_processed_files: bool = False
    processed_folder: str = ""
    
    # Batch processing
    batch_size: int = 5
    batch_timeout: float = 30.0  # Seconds to wait for batch to fill
    
    # Error handling
    max_retries: int = 3
    retry_delay: float = 5.0
    error_folder: str = ""
    
    # OCR settings
    ocr_mode: str = "hybrid"
    ocr_language: str = "por+eng"
    confidence_threshold: float = 0.75


class OCRFileHandler(FileSystemEventHandler):
    """File system event handler for OCR processing."""
    
    def __init__(self, watcher: 'FolderWatcher'):
        self.watcher = watcher
        self.logger = get_logger("folder_watcher.handler")
        self.pending_files: Dict[str, datetime] = {}
        self.processing_lock = threading.Lock()
    
    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
        
        self._queue_file_for_processing(event.src_path, "created")
    
    def on_moved(self, event):
        """Handle file move events."""
        if event.is_directory:
            return
        
        # File was moved into watched directory
        self._queue_file_for_processing(event.dest_path, "moved")
    
    def _queue_file_for_processing(self, file_path: str, event_type: str):
        """Queue a file for OCR processing after validation."""
        try:
            file_path = Path(file_path)
            
            # Validate file
            if not self._is_valid_file(file_path):
                return
            
            self.logger.info(f"File {event_type}: {file_path}")
            
            # Add to pending files with timestamp
            with self.processing_lock:
                self.pending_files[str(file_path)] = datetime.now()
            
            # Schedule processing after delay
            threading.Timer(
                self.watcher.config.processing_delay,
                self._process_pending_file,
                args=[str(file_path)]
            ).start()
            
        except Exception as e:
            self.logger.error(f"Error queuing file {file_path}: {e}")
    
    def _is_valid_file(self, file_path: Path) -> bool:
        """Check if file should be processed."""
        try:
            # Check if file exists
            if not file_path.exists():
                return False
            
            # Check file extension
            if file_path.suffix.lower() not in self.watcher.config.file_extensions:
                self.logger.debug(f"Skipping file with unsupported extension: {file_path}")
                return False
            
            # Check exclude patterns
            for pattern in self.watcher.config.exclude_patterns:
                if pattern in str(file_path):
                    self.logger.debug(f"File matches exclude pattern '{pattern}': {file_path}")
                    return False
            
            # Check file size
            file_size = file_path.stat().st_size
            if file_size < self.watcher.config.min_file_size:
                self.logger.debug(f"File too small ({file_size} bytes): {file_path}")
                return False
            
            if file_size > self.watcher.config.max_file_size:
                self.logger.warning(f"File too large ({file_size} bytes): {file_path}")
                return False
            
            # Check if file is still being written to
            if self._is_file_being_written(file_path):
                self.logger.debug(f"File still being written: {file_path}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating file {file_path}: {e}")
            return False
    
    def _is_file_being_written(self, file_path: Path) -> bool:
        """Check if file is still being written to."""
        try:
            # Try to open file in exclusive mode
            with open(file_path, 'rb') as f:
                # Try to get file size twice with small delay
                size1 = f.seek(0, 2)  # Seek to end
                time.sleep(0.1)
                f.seek(0, 2)
                size2 = f.tell()
                
                return size1 != size2
        except (PermissionError, OSError):
            # File is locked, likely still being written
            return True
    
    def _process_pending_file(self, file_path: str):
        """Process a file that was queued for processing."""
        try:
            file_path = Path(file_path)
            
            # Check if file is still pending
            with self.processing_lock:
                if file_path_str := str(file_path) not in self.pending_files:
                    return
                
                # Remove from pending
                del self.pending_files[file_path_str]
            
            # Final validation
            if not file_path.exists() or not self._is_valid_file(file_path):
                self.logger.warning(f"File no longer valid for processing: {file_path}")
                return
            
            # Queue for batch processing
            self.watcher._add_to_processing_queue(file_path)
            
        except Exception as e:
            self.logger.error(f"Error processing pending file {file_path}: {e}")


class FolderWatcher:
    """Main folder watching system for automatic OCR processing."""
    
    def __init__(self, config: WatcherConfig, ocr_processor: Optional[Callable] = None):
        self.config = config
        self.ocr_processor = ocr_processor
        self.logger = get_logger("folder_watcher")
        
        # Threading and control
        self.observer = Observer()
        self.running = False
        self.processing_thread: Optional[threading.Thread] = None
        
        # Processing queue and batch management
        self.processing_queue: queue.Queue = queue.Queue()
        self.current_batch: List[Path] = []
        self.batch_timer: Optional[threading.Timer] = None
        
        # Statistics
        self.stats = {
            "files_detected": 0,
            "files_processed": 0,
            "files_failed": 0,
            "batches_processed": 0,
            "start_time": None
        }
        
        # Setup output directories
        self._setup_directories()
    
    def _setup_directories(self):
        """Create necessary output directories."""
        directories = [
            self.config.output_folder,
            self.config.processed_folder,
            self.config.error_folder
        ]
        
        for dir_path in directories:
            if dir_path and not Path(dir_path).exists():
                Path(dir_path).mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created directory: {dir_path}")
    
    def start_watching(self):
        """Start monitoring the configured folders."""
        if self.running:
            self.logger.warning("Folder watcher is already running")
            return
        
        self.logger.info("Starting folder watcher...")
        
        # Validate configuration
        if not self.config.watch_folders:
            raise ValueError("No watch folders configured")
        
        if not self.config.output_folder:
            raise ValueError("No output folder configured")
        
        # Setup file system monitoring
        event_handler = OCRFileHandler(self)
        
        for folder in self.config.watch_folders:
            folder_path = Path(folder)
            if not folder_path.exists():
                self.logger.warning(f"Watch folder does not exist: {folder}")
                continue
            
            self.observer.schedule(
                event_handler, 
                str(folder_path),
                recursive=self.config.recursive_watching
            )
            self.logger.info(f"Monitoring folder: {folder}")
        
        # Start observer
        self.observer.start()
        
        # Start processing thread
        self.running = True
        self.processing_thread = threading.Thread(target=self._processing_worker, daemon=True)
        self.processing_thread.start()
        
        # Update statistics
        self.stats["start_time"] = datetime.now()
        
        self.logger.info("Folder watcher started successfully")
    
    def stop_watching(self):
        """Stop monitoring folders."""
        if not self.running:
            return
        
        self.logger.info("Stopping folder watcher...")
        
        # Stop observer
        self.observer.stop()
        self.observer.join()
        
        # Stop processing
        self.running = False
        
        # Process any remaining files in current batch
        if self.current_batch:
            self._process_batch(self.current_batch)
        
        # Wait for processing thread to finish
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5.0)
        
        self.logger.info("Folder watcher stopped")
    
    def _add_to_processing_queue(self, file_path: Path):
        """Add file to processing queue."""
        try:
            self.processing_queue.put(file_path, timeout=1.0)
            self.stats["files_detected"] += 1
            self.logger.debug(f"Added to queue: {file_path}")
        except queue.Full:
            self.logger.error(f"Processing queue is full, dropping file: {file_path}")
    
    def _processing_worker(self):
        """Worker thread for processing files."""
        self.logger.info("Processing worker started")
        
        while self.running:
            try:
                # Get file from queue with timeout
                try:
                    file_path = self.processing_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Add to current batch
                self.current_batch.append(file_path)
                self.logger.debug(f"Added to batch: {file_path} (batch size: {len(self.current_batch)})")
                
                # Check if batch is full or if we should process now
                if len(self.current_batch) >= self.config.batch_size:
                    self._process_batch(self.current_batch)
                    self.current_batch = []
                    self._cancel_batch_timer()
                else:
                    # Start or restart batch timer
                    self._restart_batch_timer()
                
            except Exception as e:
                self.logger.error(f"Error in processing worker: {e}")
        
        self.logger.info("Processing worker stopped")
    
    def _restart_batch_timer(self):
        """Restart the batch timeout timer."""
        self._cancel_batch_timer()
        
        self.batch_timer = threading.Timer(
            self.config.batch_timeout,
            self._process_batch_timeout
        )
        self.batch_timer.start()
    
    def _cancel_batch_timer(self):
        """Cancel the batch timeout timer."""
        if self.batch_timer:
            self.batch_timer.cancel()
            self.batch_timer = None
    
    def _process_batch_timeout(self):
        """Process current batch when timeout is reached."""
        if self.current_batch:
            self.logger.info(f"Batch timeout reached, processing {len(self.current_batch)} files")
            self._process_batch(self.current_batch)
            self.current_batch = []
    
    def _process_batch(self, files: List[Path]):
        """Process a batch of files."""
        if not files:
            return
        
        self.logger.info(f"Processing batch of {len(files)} files")
        batch_start_time = datetime.now()
        
        processed_count = 0
        failed_count = 0
        
        for file_path in files:
            try:
                success = self._process_single_file(file_path)
                if success:
                    processed_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing file {file_path}: {e}")
                failed_count += 1
        
        # Update statistics
        self.stats["files_processed"] += processed_count
        self.stats["files_failed"] += failed_count
        self.stats["batches_processed"] += 1
        
        batch_duration = datetime.now() - batch_start_time
        self.logger.info(
            f"Batch completed: {processed_count} processed, {failed_count} failed "
            f"in {batch_duration.total_seconds():.2f}s"
        )
    
    def _process_single_file(self, file_path: Path, retry_count: int = 0) -> bool:
        """Process a single file with OCR."""
        try:
            self.logger.info(f"Processing file: {file_path}")
            
            if not self.ocr_processor:
                self.logger.warning("No OCR processor configured, skipping file")
                return False
            
            # Call OCR processor
            result = self.ocr_processor(file_path, {
                "mode": self.config.ocr_mode,
                "language": self.config.ocr_language,
                "confidence_threshold": self.config.confidence_threshold,
                "output_folder": self.config.output_folder
            })
            
            if result and result.get("success", False):
                self.logger.info(f"Successfully processed: {file_path}")
                
                # Move file if configured
                if self.config.move_processed_files and self.config.processed_folder:
                    self._move_processed_file(file_path, self.config.processed_folder)
                
                return True
            else:
                self.logger.warning(f"OCR processing failed for: {file_path}")
                return self._handle_processing_failure(file_path, retry_count)
                
        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}")
            return self._handle_processing_failure(file_path, retry_count)
    
    def _handle_processing_failure(self, file_path: Path, retry_count: int) -> bool:
        """Handle processing failure with retry logic."""
        if retry_count < self.config.max_retries:
            self.logger.info(f"Retrying {file_path} (attempt {retry_count + 1}/{self.config.max_retries})")
            
            # Wait before retry
            time.sleep(self.config.retry_delay)
            
            return self._process_single_file(file_path, retry_count + 1)
        else:
            self.logger.error(f"Max retries exceeded for: {file_path}")
            
            # Move to error folder if configured
            if self.config.error_folder:
                self._move_processed_file(file_path, self.config.error_folder)
            
            return False
    
    def _move_processed_file(self, file_path: Path, destination_folder: str):
        """Move processed file to destination folder."""
        try:
            dest_folder = Path(destination_folder)
            dest_folder.mkdir(parents=True, exist_ok=True)
            
            dest_path = dest_folder / file_path.name
            
            # Handle name conflicts
            counter = 1
            while dest_path.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                dest_path = dest_folder / f"{stem}_{counter}{suffix}"
                counter += 1
            
            file_path.rename(dest_path)
            self.logger.info(f"Moved file: {file_path} -> {dest_path}")
            
        except Exception as e:
            self.logger.error(f"Error moving file {file_path} to {destination_folder}: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        stats = self.stats.copy()
        
        if stats["start_time"]:
            stats["uptime"] = datetime.now() - stats["start_time"]
            stats["uptime_seconds"] = stats["uptime"].total_seconds()
        
        stats["queue_size"] = self.processing_queue.qsize()
        stats["current_batch_size"] = len(self.current_batch)
        stats["is_running"] = self.running
        
        return stats
    
    def process_existing_files(self):
        """Process existing files in watch folders (one-time scan)."""
        self.logger.info("Scanning existing files in watch folders...")
        
        total_files = 0
        for folder in self.config.watch_folders:
            folder_path = Path(folder)
            if not folder_path.exists():
                continue
            
            # Scan for files
            pattern = "**/*" if self.config.recursive_watching else "*"
            for file_path in folder_path.glob(pattern):
                if file_path.is_file() and self._is_valid_existing_file(file_path):
                    self._add_to_processing_queue(file_path)
                    total_files += 1
        
        self.logger.info(f"Found {total_files} existing files to process")
    
    def _is_valid_existing_file(self, file_path: Path) -> bool:
        """Check if existing file should be processed."""
        try:
            # Use same validation as real-time files
            handler = OCRFileHandler(self)
            return handler._is_valid_file(file_path)
        except Exception:
            return False


def create_watcher_from_config(ocr_config: OCRConfig, ocr_processor: Callable) -> FolderWatcher:
    """Create folder watcher from OCR configuration."""
    watcher_config = WatcherConfig(
        watch_folders=[ocr_config.input_folder],
        output_folder=ocr_config.output_folder,
        ocr_mode=ocr_config.mode,
        ocr_language=ocr_config.language,
        confidence_threshold=ocr_config.confidence_threshold
    )
    
    return FolderWatcher(watcher_config, ocr_processor)