"""
Backup scheduling engine using QTimer for automated backups.

Provides BackupScheduler class that manages periodic backups with
configurable intervals (hourly, daily, weekly, monthly) and persistence.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING

from PySide6.QtCore import QTimer, QObject, Signal  # type: ignore[import-not-found]

if TYPE_CHECKING:
    from ...core.services import CoreServices


logger = logging.getLogger(__name__)


class ScheduleInterval(Enum):
    """Backup schedule interval options."""
    
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    
    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        return {
            ScheduleInterval.HOURLY: "Stündlich",
            ScheduleInterval.DAILY: "Täglich",
            ScheduleInterval.WEEKLY: "Wöchentlich",
            ScheduleInterval.MONTHLY: "Monatlich",
        }[self]
    
    @property
    def milliseconds(self) -> int:
        """
        Get interval in milliseconds for QTimer.
        
        Note: QTimer has a maximum interval of ~24.8 days (2^31-1 ms).
        For WEEKLY and MONTHLY intervals, we use a daily check timer
        and verify if the actual interval has elapsed in the timeout handler.
        """
        return {
            ScheduleInterval.HOURLY: 60 * 60 * 1000,      # 1 hour
            ScheduleInterval.DAILY: 24 * 60 * 60 * 1000,  # 24 hours
            ScheduleInterval.WEEKLY: 24 * 60 * 60 * 1000,  # Check daily for weekly
            ScheduleInterval.MONTHLY: 24 * 60 * 60 * 1000,  # Check daily for monthly
        }[self]
    
    @classmethod
    def from_string(cls, value: str) -> Optional["ScheduleInterval"]:
        """Convert string to enum."""
        try:
            return cls(value)
        except ValueError:
            return None


class BackupSchedule:
    """Configuration for a scheduled backup."""
    
    def __init__(
        self,
        profile_name: str,
        interval: ScheduleInterval,
        enabled: bool = True,
        last_run: Optional[datetime] = None,
    ) -> None:
        self.profile_name = profile_name
        self.interval = interval
        self.enabled = enabled
        self.last_run = last_run
    
    @property
    def next_run(self) -> Optional[datetime]:
        """Calculate next scheduled run time."""
        if not self.last_run:
            return datetime.now()  # Run immediately if never run
        
        if self.interval == ScheduleInterval.HOURLY:
            delta = timedelta(hours=1)
        elif self.interval == ScheduleInterval.DAILY:
            delta = timedelta(days=1)
        elif self.interval == ScheduleInterval.WEEKLY:
            delta = timedelta(weeks=1)
        elif self.interval == ScheduleInterval.MONTHLY:
            delta = timedelta(days=30)
        else:
            return None
        
        return self.last_run + delta
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON persistence."""
        return {
            "profile_name": self.profile_name,
            "interval": self.interval.value,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Optional["BackupSchedule"]:
        """Deserialize from dictionary."""
        try:
            interval = ScheduleInterval.from_string(data["interval"])
            if not interval:
                return None
            
            last_run = None
            if data.get("last_run"):
                last_run = datetime.fromisoformat(data["last_run"])
            
            return cls(
                profile_name=data["profile_name"],
                interval=interval,
                enabled=data.get("enabled", True),
                last_run=last_run,
            )
        except (KeyError, ValueError) as exc:
            logger.warning(f"Failed to deserialize schedule: {exc}")
            return None


class BackupScheduler(QObject):
    """
    Manages automated backup scheduling using QTimer.
    
    Signals:
        schedule_triggered: Emitted when a scheduled backup should execute.
                           Args: (profile_name: str, schedule_id: str)
    """
    
    schedule_triggered = Signal(str, str)  # profile_name, schedule_id
    
    def __init__(self, services: CoreServices, storage_file: Path) -> None:
        super().__init__()
        self.services = services
        self.storage_file = storage_file
        self.schedules: dict[str, BackupSchedule] = {}
        self._timers: dict[str, QTimer] = {}
        self._load_schedules()
    
    def _load_schedules(self) -> None:
        """Load schedules from persistent storage."""
        if not self.storage_file.exists():
            return
        
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for schedule_id, schedule_data in data.items():
                schedule = BackupSchedule.from_dict(schedule_data)
                if schedule:
                    self.schedules[schedule_id] = schedule
                    if schedule.enabled:
                        self._start_timer(schedule_id)
            
            logger.info(f"Loaded {len(self.schedules)} backup schedules")
        except Exception as exc:
            logger.error(f"Failed to load schedules: {exc}")
    
    def _save_schedules(self) -> None:
        """Persist schedules to storage."""
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                schedule_id: schedule.to_dict()
                for schedule_id, schedule in self.schedules.items()
            }
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug("Schedules saved")
        except Exception as exc:
            logger.error(f"Failed to save schedules: {exc}")
    
    def add_schedule(
        self,
        schedule_id: str,
        profile_name: str,
        interval: ScheduleInterval,
        enabled: bool = True,
    ) -> None:
        """
        Add or update a backup schedule.
        
        Args:
            schedule_id: Unique identifier for this schedule
            profile_name: Name of backup profile to execute
            interval: Backup frequency
            enabled: Whether schedule is active
        """
        schedule = BackupSchedule(
            profile_name=profile_name,
            interval=interval,
            enabled=enabled,
        )
        self.schedules[schedule_id] = schedule
        self._save_schedules()
        
        if enabled:
            self._start_timer(schedule_id)
        
        logger.info(f"Schedule '{schedule_id}' added: {profile_name} {interval.display_name}")
    
    def remove_schedule(self, schedule_id: str) -> None:
        """Remove a scheduled backup."""
        if schedule_id in self.schedules:
            self._stop_timer(schedule_id)
            del self.schedules[schedule_id]
            self._save_schedules()
            logger.info(f"Schedule '{schedule_id}' removed")
    
    def enable_schedule(self, schedule_id: str, enabled: bool) -> None:
        """Enable or disable a schedule."""
        if schedule_id not in self.schedules:
            return
        
        self.schedules[schedule_id].enabled = enabled
        self._save_schedules()
        
        if enabled:
            self._start_timer(schedule_id)
        else:
            self._stop_timer(schedule_id)
        
        state = "enabled" if enabled else "disabled"
        logger.info(f"Schedule '{schedule_id}' {state}")
    
    def get_schedule(self, schedule_id: str) -> Optional[BackupSchedule]:
        """Retrieve a schedule by ID."""
        return self.schedules.get(schedule_id)
    
    def list_schedules(self) -> dict[str, BackupSchedule]:
        """Get all schedules."""
        return self.schedules.copy()
    
    def _start_timer(self, schedule_id: str) -> None:
        """Start QTimer for a schedule."""
        if schedule_id in self._timers:
            self._stop_timer(schedule_id)
        
        schedule = self.schedules[schedule_id]
        timer = QTimer(self)
        timer.timeout.connect(lambda: self._on_timer_fired(schedule_id))
        timer.start(schedule.interval.milliseconds)
        self._timers[schedule_id] = timer
        
        logger.debug(f"Timer started for schedule '{schedule_id}' (interval: {schedule.interval.display_name})")
    
    def _stop_timer(self, schedule_id: str) -> None:
        """Stop QTimer for a schedule."""
        if schedule_id in self._timers:
            self._timers[schedule_id].stop()
            self._timers[schedule_id].deleteLater()
            del self._timers[schedule_id]
            logger.debug(f"Timer stopped for schedule '{schedule_id}'")
    
    def _on_timer_fired(self, schedule_id: str) -> None:
        """
        Handle timer timeout - check if backup should execute.
        
        For WEEKLY and MONTHLY schedules, the timer fires daily but we only
        execute if the full interval has elapsed since last_run.
        """
        if schedule_id not in self.schedules:
            return
        
        schedule = self.schedules[schedule_id]
        if not schedule.enabled:
            return
        
        # Check if we should actually run (for longer intervals with daily timer)
        if schedule.last_run is not None:
            now = datetime.now()
            elapsed = now - schedule.last_run
            
            # Determine required elapsed time based on interval
            if schedule.interval == ScheduleInterval.WEEKLY:
                required_delta = timedelta(days=7)
            elif schedule.interval == ScheduleInterval.MONTHLY:
                required_delta = timedelta(days=30)
            else:
                required_delta = timedelta(seconds=0)  # Hourly/Daily always run
            
            # If not enough time has passed, skip this check
            if elapsed < required_delta:
                logger.debug(
                    f"Schedule '{schedule_id}' timer fired but interval not elapsed "
                    f"({elapsed.days} days < {required_delta.days} days required)"
                )
                return
        
        # Update last run timestamp
        schedule.last_run = datetime.now()
        self._save_schedules()
        
        # Emit signal for plugin to handle actual backup
        self.schedule_triggered.emit(schedule.profile_name, schedule_id)
        
        logger.info(f"Scheduled backup triggered: {schedule.profile_name} (ID: {schedule_id})")
    
    def stop_all(self) -> None:
        """Stop all active timers (cleanup on plugin stop)."""
        for schedule_id in list(self._timers.keys()):
            self._stop_timer(schedule_id)
        logger.info("All backup schedules stopped")
