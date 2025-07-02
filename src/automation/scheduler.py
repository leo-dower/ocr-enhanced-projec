"""
Scheduling system for automated OCR processing.

This module provides cron-like scheduling capabilities for running
OCR workflows at specific times, intervals, or based on conditions.
"""

import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import time
import logging
from croniter import croniter
import json
from pathlib import Path

from ..utils.logger import get_logger


class ScheduleType(Enum):
    """Types of schedules."""
    CRON = "cron"
    INTERVAL = "interval"
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ScheduleStatus(Enum):
    """Schedule execution status."""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class ScheduledJob:
    """Represents a scheduled job."""
    
    job_id: str
    name: str
    schedule_type: ScheduleType
    
    # Schedule configuration
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Job configuration
    workflow_name: Optional[str] = None
    action_callback: Optional[Callable] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Execution control
    enabled: bool = True
    max_runs: Optional[int] = None
    run_count: int = 0
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    
    # Error handling
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize schedule calculations."""
        self._calculate_next_run()
    
    def _calculate_next_run(self):
        """Calculate next run time based on schedule type."""
        if not self.enabled:
            self.next_run = None
            return
        
        now = datetime.now()
        
        if self.schedule_type == ScheduleType.CRON and self.cron_expression:
            try:
                cron = croniter(self.cron_expression, now)
                self.next_run = cron.get_next(datetime)
            except Exception as e:
                logging.error(f"Invalid cron expression '{self.cron_expression}': {e}")
                self.next_run = None
        
        elif self.schedule_type == ScheduleType.INTERVAL and self.interval_seconds:
            if self.last_run:
                self.next_run = self.last_run + timedelta(seconds=self.interval_seconds)
            else:
                self.next_run = now + timedelta(seconds=self.interval_seconds)
        
        elif self.schedule_type == ScheduleType.ONCE and self.start_time:
            if self.run_count == 0 and self.start_time > now:
                self.next_run = self.start_time
            else:
                self.next_run = None  # Already ran or past due
        
        elif self.schedule_type == ScheduleType.DAILY:
            if self.start_time:
                # Use start_time as daily time
                today = now.date()
                daily_time = datetime.combine(today, self.start_time.time())
                if daily_time <= now:
                    daily_time += timedelta(days=1)
                self.next_run = daily_time
            else:
                self.next_run = now + timedelta(days=1)
        
        elif self.schedule_type == ScheduleType.WEEKLY:
            if self.start_time:
                # Find next occurrence of the same weekday and time
                target_weekday = self.start_time.weekday()
                target_time = self.start_time.time()
                
                days_ahead = target_weekday - now.weekday()
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                
                next_date = now.date() + timedelta(days=days_ahead)
                self.next_run = datetime.combine(next_date, target_time)
            else:
                self.next_run = now + timedelta(weeks=1)
        
        elif self.schedule_type == ScheduleType.MONTHLY:
            if self.start_time:
                # Same day of month, next month
                try:
                    if now.month == 12:
                        next_month = datetime(now.year + 1, 1, self.start_time.day, 
                                            self.start_time.hour, self.start_time.minute)
                    else:
                        next_month = datetime(now.year, now.month + 1, self.start_time.day,
                                            self.start_time.hour, self.start_time.minute)
                    self.next_run = next_month
                except ValueError:
                    # Handle day not existing in next month (e.g., Feb 31)
                    self.next_run = now + timedelta(days=30)
            else:
                self.next_run = now + timedelta(days=30)
        
        # Check end time
        if self.end_time and self.next_run and self.next_run > self.end_time:
            self.next_run = None
        
        # Check max runs
        if self.max_runs and self.run_count >= self.max_runs:
            self.next_run = None
    
    def should_run(self) -> bool:
        """Check if job should run now."""
        if not self.enabled or not self.next_run:
            return False
        
        return datetime.now() >= self.next_run
    
    def mark_completed(self):
        """Mark job as completed and calculate next run."""
        self.last_run = datetime.now()
        self.run_count += 1
        self.retry_count = 0  # Reset retry count on success
        self._calculate_next_run()
    
    def mark_failed(self):
        """Mark job as failed and handle retries."""
        self.retry_count += 1
        
        if self.retry_count < self.max_retries:
            # Schedule retry
            self.next_run = datetime.now() + timedelta(seconds=self.retry_delay)
        else:
            # Max retries exceeded, calculate next regular run
            self.retry_count = 0
            self._calculate_next_run()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = {
            "job_id": self.job_id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "cron_expression": self.cron_expression,
            "interval_seconds": self.interval_seconds,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "workflow_name": self.workflow_name,
            "context": self.context,
            "enabled": self.enabled,
            "max_runs": self.max_runs,
            "run_count": self.run_count,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "tags": self.tags
        }
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduledJob':
        """Create job from dictionary."""
        # Convert datetime strings
        for field in ['start_time', 'end_time', 'last_run', 'next_run', 'created_at']:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])
        
        # Convert enum
        if 'schedule_type' in data and isinstance(data['schedule_type'], str):
            data['schedule_type'] = ScheduleType(data['schedule_type'])
        
        # Remove callback for serialization
        data.pop('action_callback', None)
        
        return cls(**data)


@dataclass
class JobExecution:
    """Represents a job execution result."""
    
    job_id: str
    execution_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    
    def duration(self) -> Optional[timedelta]:
        """Get execution duration."""
        if self.completed_at:
            return self.completed_at - self.started_at
        return None


class ProcessingScheduler:
    """Scheduler for automated OCR processing jobs."""
    
    def __init__(self, workflow_manager=None, jobs_file: Optional[Path] = None):
        self.workflow_manager = workflow_manager
        self.jobs_file = jobs_file or Path.home() / ".ocr_enhanced" / "scheduled_jobs.json"
        self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.jobs: Dict[str, ScheduledJob] = {}
        self.execution_history: List[JobExecution] = []
        self.running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        
        self.logger = get_logger("scheduler")
        
        # Load jobs from file
        self.load_jobs()
        
        # Create example jobs
        self._create_example_jobs()
    
    def _create_example_jobs(self):
        """Create example scheduled jobs."""
        if not self.jobs:  # Only create if no jobs exist
            
            # Daily morning processing
            daily_job = ScheduledJob(
                job_id="daily_morning_process",
                name="Daily Morning Processing",
                description="Process documents every morning at 8 AM",
                schedule_type=ScheduleType.DAILY,
                start_time=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0),
                workflow_name="Auto Process Documents",
                context={"source": "daily_batch"},
                tags=["daily", "batch", "morning"]
            )
            
            # Hourly processing during business hours
            business_hours_job = ScheduledJob(
                job_id="business_hours_process",
                name="Business Hours Processing",
                description="Process documents every hour during business hours",
                schedule_type=ScheduleType.CRON,
                cron_expression="0 9-17 * * 1-5",  # Every hour, 9 AM to 5 PM, Monday to Friday
                workflow_name="Auto Process Documents",
                context={"source": "business_hours"},
                tags=["hourly", "business_hours"]
            )
            
            # Weekly report
            weekly_job = ScheduledJob(
                job_id="weekly_report",
                name="Weekly Processing Report",
                description="Generate weekly processing report every Friday",
                schedule_type=ScheduleType.WEEKLY,
                start_time=datetime.now().replace(hour=17, minute=0, second=0, microsecond=0),
                workflow_name="Generate Report",
                context={"report_type": "weekly"},
                tags=["weekly", "report"]
            )
            
            # Cleanup old files monthly
            monthly_cleanup = ScheduledJob(
                job_id="monthly_cleanup",
                name="Monthly File Cleanup",
                description="Clean up processed files older than 6 months",
                schedule_type=ScheduleType.MONTHLY,
                start_time=datetime.now().replace(day=1, hour=2, minute=0, second=0, microsecond=0),
                workflow_name="Cleanup Old Files",
                context={"age_days": 180},
                tags=["monthly", "cleanup", "maintenance"]
            )
            
            # Add jobs
            self.jobs[daily_job.job_id] = daily_job
            self.jobs[business_hours_job.job_id] = business_hours_job
            self.jobs[weekly_job.job_id] = weekly_job
            self.jobs[monthly_cleanup.job_id] = monthly_cleanup
            
            self.logger.info("Created example scheduled jobs")
            self.save_jobs()
    
    def load_jobs(self):
        """Load jobs from file."""
        if not self.jobs_file.exists():
            return
        
        try:
            with open(self.jobs_file, 'r', encoding='utf-8') as f:
                jobs_data = json.load(f)
            
            for job_data in jobs_data:
                job = ScheduledJob.from_dict(job_data)
                self.jobs[job.job_id] = job
            
            self.logger.info(f"Loaded {len(self.jobs)} scheduled jobs")
            
        except Exception as e:
            self.logger.error(f"Error loading scheduled jobs: {e}")
    
    def save_jobs(self):
        """Save jobs to file."""
        try:
            jobs_data = [job.to_dict() for job in self.jobs.values()]
            
            with open(self.jobs_file, 'w', encoding='utf-8') as f:
                json.dump(jobs_data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug("Saved scheduled jobs to file")
            
        except Exception as e:
            self.logger.error(f"Error saving scheduled jobs: {e}")
    
    def add_job(self, job: ScheduledJob):
        """Add a new scheduled job."""
        self.jobs[job.job_id] = job
        self.save_jobs()
        self.logger.info(f"Added scheduled job: {job.name} ({job.job_id})")
    
    def remove_job(self, job_id: str):
        """Remove a scheduled job."""
        if job_id in self.jobs:
            job_name = self.jobs[job_id].name
            del self.jobs[job_id]
            self.save_jobs()
            self.logger.info(f"Removed scheduled job: {job_name} ({job_id})")
    
    def enable_job(self, job_id: str):
        """Enable a scheduled job."""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = True
            self.jobs[job_id]._calculate_next_run()
            self.save_jobs()
            self.logger.info(f"Enabled job: {job_id}")
    
    def disable_job(self, job_id: str):
        """Disable a scheduled job."""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = False
            self.jobs[job_id].next_run = None
            self.save_jobs()
            self.logger.info(f"Disabled job: {job_id}")
    
    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get job by ID."""
        return self.jobs.get(job_id)
    
    def list_jobs(self, enabled_only: bool = False, tags: Optional[List[str]] = None) -> List[ScheduledJob]:
        """List jobs with optional filtering."""
        jobs = list(self.jobs.values())
        
        if enabled_only:
            jobs = [job for job in jobs if job.enabled]
        
        if tags:
            jobs = [job for job in jobs if any(tag in job.tags for tag in tags)]
        
        return jobs
    
    def get_next_jobs(self, count: int = 10) -> List[ScheduledJob]:
        """Get next jobs to run."""
        enabled_jobs = [job for job in self.jobs.values() 
                       if job.enabled and job.next_run]
        
        # Sort by next run time
        enabled_jobs.sort(key=lambda j: j.next_run)
        
        return enabled_jobs[:count]
    
    def start_scheduler(self):
        """Start the scheduler thread."""
        if self.running:
            self.logger.warning("Scheduler is already running")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        self.logger.info("Scheduler started")
    
    def stop_scheduler(self):
        """Stop the scheduler thread."""
        if self.running:
            self.running = False
            if self.scheduler_thread:
                self.scheduler_thread.join(timeout=5.0)
            self.logger.info("Scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop."""
        self.logger.info("Scheduler loop started")
        
        while self.running:
            try:
                # Check for jobs that should run
                current_time = datetime.now()
                
                for job in list(self.jobs.values()):
                    if job.should_run():
                        self.logger.info(f"Executing scheduled job: {job.name}")
                        
                        # Execute job in background
                        threading.Thread(
                            target=self._execute_job,
                            args=(job,),
                            daemon=True
                        ).start()
                
                # Sleep for 30 seconds before next check
                time.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)  # Wait longer on error
        
        self.logger.info("Scheduler loop stopped")
    
    def _execute_job(self, job: ScheduledJob):
        """Execute a scheduled job."""
        execution = JobExecution(
            job_id=job.job_id,
            execution_id=f"{job.job_id}_{int(time.time())}",
            started_at=datetime.now()
        )
        
        try:
            self.logger.info(f"Starting job execution: {job.name}")
            
            if job.workflow_name and self.workflow_manager:
                # Execute workflow
                import asyncio
                
                # Create event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    workflow_execution = loop.run_until_complete(
                        self.workflow_manager.trigger_workflow(job.workflow_name, job.context)
                    )
                    
                    if workflow_execution and workflow_execution.status.value == "completed":
                        execution.success = True
                        execution.result = {
                            "workflow_execution_id": workflow_execution.execution_id,
                            "action_results": workflow_execution.action_results
                        }
                        job.mark_completed()
                        self.logger.info(f"Job completed successfully: {job.name}")
                    else:
                        execution.success = False
                        execution.error_message = "Workflow execution failed"
                        job.mark_failed()
                        self.logger.error(f"Job failed: {job.name}")
                        
                finally:
                    loop.close()
                    
            elif job.action_callback:
                # Execute callback function
                result = job.action_callback(job.context)
                execution.success = True
                execution.result = result
                job.mark_completed()
                self.logger.info(f"Job completed successfully: {job.name}")
                
            else:
                execution.success = False
                execution.error_message = "No workflow or callback configured"
                job.mark_failed()
                self.logger.error(f"Job has no execution method: {job.name}")
        
        except Exception as e:
            execution.success = False
            execution.error_message = str(e)
            job.mark_failed()
            self.logger.error(f"Job execution failed: {job.name} - {e}")
        
        finally:
            execution.completed_at = datetime.now()
            self.execution_history.append(execution)
            
            # Keep only last 1000 executions
            if len(self.execution_history) > 1000:
                self.execution_history = self.execution_history[-1000:]
            
            # Save updated job state
            self.save_jobs()
    
    def run_job_now(self, job_id: str) -> Optional[JobExecution]:
        """Manually execute a job immediately."""
        job = self.jobs.get(job_id)
        if not job:
            return None
        
        self.logger.info(f"Manually executing job: {job.name}")
        self._execute_job(job)
        
        # Return the latest execution
        job_executions = [ex for ex in self.execution_history if ex.job_id == job_id]
        return job_executions[-1] if job_executions else None
    
    def get_job_statistics(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        total_jobs = len(self.jobs)
        enabled_jobs = sum(1 for job in self.jobs.values() if job.enabled)
        total_executions = len(self.execution_history)
        
        # Calculate success rate
        if total_executions > 0:
            successful_executions = sum(1 for ex in self.execution_history if ex.success)
            success_rate = successful_executions / total_executions
        else:
            success_rate = 0.0
        
        # Next jobs
        next_jobs = self.get_next_jobs(5)
        
        # Recent executions
        recent_executions = sorted(self.execution_history, 
                                 key=lambda ex: ex.started_at, reverse=True)[:10]
        
        return {
            "total_jobs": total_jobs,
            "enabled_jobs": enabled_jobs,
            "disabled_jobs": total_jobs - enabled_jobs,
            "total_executions": total_executions,
            "success_rate": success_rate,
            "scheduler_running": self.running,
            "next_jobs": [
                {
                    "job_id": job.job_id,
                    "name": job.name,
                    "next_run": job.next_run.isoformat() if job.next_run else None
                }
                for job in next_jobs
            ],
            "recent_executions": [
                {
                    "job_id": ex.job_id,
                    "execution_id": ex.execution_id,
                    "started_at": ex.started_at.isoformat(),
                    "success": ex.success,
                    "duration_seconds": ex.duration().total_seconds() if ex.duration() else None
                }
                for ex in recent_executions
            ]
        }
    
    def create_cron_job(self, name: str, cron_expression: str, workflow_name: str, 
                       context: Optional[Dict[str, Any]] = None) -> ScheduledJob:
        """Helper to create a cron-based job."""
        job = ScheduledJob(
            job_id=f"cron_{name.lower().replace(' ', '_')}_{int(time.time())}",
            name=name,
            schedule_type=ScheduleType.CRON,
            cron_expression=cron_expression,
            workflow_name=workflow_name,
            context=context or {}
        )
        
        self.add_job(job)
        return job
    
    def create_interval_job(self, name: str, interval_seconds: int, workflow_name: str,
                           context: Optional[Dict[str, Any]] = None) -> ScheduledJob:
        """Helper to create an interval-based job."""
        job = ScheduledJob(
            job_id=f"interval_{name.lower().replace(' ', '_')}_{int(time.time())}",
            name=name,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=interval_seconds,
            workflow_name=workflow_name,
            context=context or {}
        )
        
        self.add_job(job)
        return job
    
    def create_daily_job(self, name: str, hour: int, minute: int, workflow_name: str,
                        context: Optional[Dict[str, Any]] = None) -> ScheduledJob:
        """Helper to create a daily job."""
        start_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        job = ScheduledJob(
            job_id=f"daily_{name.lower().replace(' ', '_')}_{int(time.time())}",
            name=name,
            schedule_type=ScheduleType.DAILY,
            start_time=start_time,
            workflow_name=workflow_name,
            context=context or {}
        )
        
        self.add_job(job)
        return job