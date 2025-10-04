"""
Unit tests for backup scheduler functionality.

Tests cover BackupSchedule, ScheduleInterval, and BackupScheduler
classes including persistence, QTimer integration, and signal emission.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Skip if PySide6 not available
pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer  # type: ignore[import-not-found]

from mmst.plugins.file_manager.scheduler import (
    BackupSchedule,
    BackupScheduler,
    ScheduleInterval,
)


class TestScheduleInterval:
    """Test ScheduleInterval enum."""
    
    def test_display_names(self):
        """Test human-readable display names."""
        assert ScheduleInterval.HOURLY.display_name == "Stündlich"
        assert ScheduleInterval.DAILY.display_name == "Täglich"
        assert ScheduleInterval.WEEKLY.display_name == "Wöchentlich"
        assert ScheduleInterval.MONTHLY.display_name == "Monatlich"
    
    def test_milliseconds(self):
        """
        Test timer interval milliseconds.
        
        Note: WEEKLY and MONTHLY use daily check timers (QTimer max ~24.8 days),
        with actual interval verification in _on_timer_fired().
        """
        assert ScheduleInterval.HOURLY.milliseconds == 60 * 60 * 1000  # 1 hour
        assert ScheduleInterval.DAILY.milliseconds == 24 * 60 * 60 * 1000  # 24 hours
        assert ScheduleInterval.WEEKLY.milliseconds == 24 * 60 * 60 * 1000  # Daily check
        assert ScheduleInterval.MONTHLY.milliseconds == 24 * 60 * 60 * 1000  # Daily check
    
    def test_from_string_valid(self):
        """Test conversion from string to enum."""
        assert ScheduleInterval.from_string("hourly") == ScheduleInterval.HOURLY
        assert ScheduleInterval.from_string("daily") == ScheduleInterval.DAILY
        assert ScheduleInterval.from_string("weekly") == ScheduleInterval.WEEKLY
        assert ScheduleInterval.from_string("monthly") == ScheduleInterval.MONTHLY
    
    def test_from_string_invalid(self):
        """Test conversion with invalid string."""
        assert ScheduleInterval.from_string("invalid") is None
        assert ScheduleInterval.from_string("") is None


class TestBackupSchedule:
    """Test BackupSchedule class."""
    
    def test_initialization(self):
        """Test schedule creation."""
        schedule = BackupSchedule(
            profile_name="test_profile",
            interval=ScheduleInterval.DAILY,
            enabled=True,
        )
        
        assert schedule.profile_name == "test_profile"
        assert schedule.interval == ScheduleInterval.DAILY
        assert schedule.enabled is True
        assert schedule.last_run is None
    
    def test_next_run_never_executed(self):
        """Test next_run when schedule has never run."""
        schedule = BackupSchedule(
            profile_name="test",
            interval=ScheduleInterval.HOURLY,
        )
        
        next_run = schedule.next_run
        assert next_run is not None
        # Should be approximately now (within 1 second)
        now = datetime.now()
        assert abs((next_run - now).total_seconds()) < 1
    
    def test_next_run_after_execution(self):
        """Test next_run calculation after previous execution."""
        last_run = datetime(2024, 1, 1, 12, 0, 0)
        
        # Hourly schedule
        schedule = BackupSchedule(
            profile_name="test",
            interval=ScheduleInterval.HOURLY,
            last_run=last_run,
        )
        expected = last_run + timedelta(hours=1)
        assert schedule.next_run == expected
        
        # Daily schedule
        schedule.interval = ScheduleInterval.DAILY
        expected = last_run + timedelta(days=1)
        assert schedule.next_run == expected
        
        # Weekly schedule
        schedule.interval = ScheduleInterval.WEEKLY
        expected = last_run + timedelta(weeks=1)
        assert schedule.next_run == expected
        
        # Monthly schedule (approximation)
        schedule.interval = ScheduleInterval.MONTHLY
        expected = last_run + timedelta(days=30)
        assert schedule.next_run == expected
    
    def test_serialization(self):
        """Test to_dict serialization."""
        last_run = datetime(2024, 1, 15, 10, 30, 0)
        schedule = BackupSchedule(
            profile_name="important_backup",
            interval=ScheduleInterval.WEEKLY,
            enabled=False,
            last_run=last_run,
        )
        
        data = schedule.to_dict()
        
        assert data["profile_name"] == "important_backup"
        assert data["interval"] == "weekly"
        assert data["enabled"] is False
        assert data["last_run"] == "2024-01-15T10:30:00"
    
    def test_deserialization(self):
        """Test from_dict deserialization."""
        data = {
            "profile_name": "backup_profile",
            "interval": "daily",
            "enabled": True,
            "last_run": "2024-02-20T14:00:00",
        }
        
        schedule = BackupSchedule.from_dict(data)
        
        assert schedule is not None
        assert schedule.profile_name == "backup_profile"
        assert schedule.interval == ScheduleInterval.DAILY
        assert schedule.enabled is True
        assert schedule.last_run == datetime(2024, 2, 20, 14, 0, 0)
    
    def test_deserialization_no_last_run(self):
        """Test deserialization without last_run."""
        data = {
            "profile_name": "new_backup",
            "interval": "hourly",
            "enabled": True,
        }
        
        schedule = BackupSchedule.from_dict(data)
        
        assert schedule is not None
        assert schedule.last_run is None
    
    def test_deserialization_invalid_interval(self):
        """Test deserialization with invalid interval."""
        data = {
            "profile_name": "test",
            "interval": "invalid_interval",
            "enabled": True,
        }
        
        schedule = BackupSchedule.from_dict(data)
        assert schedule is None
    
    def test_deserialization_missing_fields(self):
        """Test deserialization with missing required fields."""
        data = {"profile_name": "test"}  # Missing interval
        
        schedule = BackupSchedule.from_dict(data)
        assert schedule is None


class TestBackupScheduler:
    """Test BackupScheduler class."""
    
    @pytest.fixture
    def mock_services(self):
        """Create mock CoreServices."""
        services = MagicMock()
        services.data_dir = Path("/mock/data")
        return services
    
    @pytest.fixture
    def storage_file(self, tmp_path):
        """Create temporary storage file."""
        return tmp_path / "schedules.json"
    
    @pytest.fixture
    def scheduler(self, mock_services, storage_file):
        """Create BackupScheduler instance."""
        return BackupScheduler(mock_services, storage_file)
    
    def test_initialization(self, scheduler, storage_file):
        """Test scheduler initialization."""
        assert scheduler.storage_file == storage_file
        assert len(scheduler.schedules) == 0
        assert len(scheduler._timers) == 0
    
    def test_add_schedule(self, scheduler):
        """Test adding a new schedule."""
        scheduler.add_schedule(
            schedule_id="test_schedule",
            profile_name="daily_backup",
            interval=ScheduleInterval.DAILY,
            enabled=True,
        )
        
        assert "test_schedule" in scheduler.schedules
        schedule = scheduler.schedules["test_schedule"]
        assert schedule.profile_name == "daily_backup"
        assert schedule.interval == ScheduleInterval.DAILY
        assert schedule.enabled is True
        
        # Check timer was started
        assert "test_schedule" in scheduler._timers
    
    def test_add_schedule_disabled(self, scheduler):
        """Test adding disabled schedule (no timer)."""
        scheduler.add_schedule(
            schedule_id="disabled_schedule",
            profile_name="backup",
            interval=ScheduleInterval.HOURLY,
            enabled=False,
        )
        
        assert "disabled_schedule" in scheduler.schedules
        # Timer should not be started for disabled schedules
        assert "disabled_schedule" not in scheduler._timers
    
    def test_remove_schedule(self, scheduler):
        """Test removing a schedule."""
        scheduler.add_schedule(
            schedule_id="temp_schedule",
            profile_name="backup",
            interval=ScheduleInterval.WEEKLY,
        )
        
        assert "temp_schedule" in scheduler.schedules
        
        scheduler.remove_schedule("temp_schedule")
        
        assert "temp_schedule" not in scheduler.schedules
        assert "temp_schedule" not in scheduler._timers
    
    def test_enable_schedule(self, scheduler):
        """Test enabling a schedule."""
        scheduler.add_schedule(
            schedule_id="test",
            profile_name="backup",
            interval=ScheduleInterval.DAILY,
            enabled=False,
        )
        
        assert "test" not in scheduler._timers
        
        scheduler.enable_schedule("test", True)
        
        assert scheduler.schedules["test"].enabled is True
        assert "test" in scheduler._timers
    
    def test_disable_schedule(self, scheduler):
        """Test disabling a schedule."""
        scheduler.add_schedule(
            schedule_id="test",
            profile_name="backup",
            interval=ScheduleInterval.DAILY,
            enabled=True,
        )
        
        assert "test" in scheduler._timers
        
        scheduler.enable_schedule("test", False)
        
        assert scheduler.schedules["test"].enabled is False
        assert "test" not in scheduler._timers
    
    def test_get_schedule(self, scheduler):
        """Test retrieving a schedule."""
        scheduler.add_schedule(
            schedule_id="retrieve_test",
            profile_name="backup",
            interval=ScheduleInterval.MONTHLY,
        )
        
        schedule = scheduler.get_schedule("retrieve_test")
        
        assert schedule is not None
        assert schedule.profile_name == "backup"
        assert schedule.interval == ScheduleInterval.MONTHLY
    
    def test_get_schedule_nonexistent(self, scheduler):
        """Test retrieving nonexistent schedule."""
        schedule = scheduler.get_schedule("does_not_exist")
        assert schedule is None
    
    def test_list_schedules(self, scheduler):
        """Test listing all schedules."""
        scheduler.add_schedule("s1", "backup1", ScheduleInterval.HOURLY)
        scheduler.add_schedule("s2", "backup2", ScheduleInterval.DAILY)
        
        schedules = scheduler.list_schedules()
        
        assert len(schedules) == 2
        assert "s1" in schedules
        assert "s2" in schedules
    
    def test_persistence_save(self, scheduler, storage_file):
        """Test saving schedules to file."""
        scheduler.add_schedule(
            schedule_id="persist_test",
            profile_name="important",
            interval=ScheduleInterval.WEEKLY,
        )
        
        # Check file was created
        assert storage_file.exists()
        
        # Verify content
        with open(storage_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert "persist_test" in data
        assert data["persist_test"]["profile_name"] == "important"
        assert data["persist_test"]["interval"] == "weekly"
    
    def test_persistence_load(self, mock_services, storage_file):
        """Test loading schedules from file."""
        # Prepare storage file
        data = {
            "loaded_schedule": {
                "profile_name": "loaded_backup",
                "interval": "daily",
                "enabled": True,
                "last_run": None,
            }
        }
        storage_file.parent.mkdir(parents=True, exist_ok=True)
        with open(storage_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        # Create scheduler - should load automatically
        scheduler = BackupScheduler(mock_services, storage_file)
        
        assert "loaded_schedule" in scheduler.schedules
        schedule = scheduler.schedules["loaded_schedule"]
        assert schedule.profile_name == "loaded_backup"
        assert schedule.interval == ScheduleInterval.DAILY
        assert schedule.enabled is True
        
        # Timer should have been started for enabled schedule
        assert "loaded_schedule" in scheduler._timers
    
    def test_timer_signal_emission(self, scheduler):
        """Test that timer fires schedule_triggered signal."""
        # Connect mock slot
        mock_slot = Mock()
        scheduler.schedule_triggered.connect(mock_slot)
        
        scheduler.add_schedule(
            schedule_id="signal_test",
            profile_name="test_profile",
            interval=ScheduleInterval.HOURLY,
        )
        
        # Manually trigger timer callback
        scheduler._on_timer_fired("signal_test")
        
        # Verify signal was emitted
        mock_slot.assert_called_once_with("test_profile", "signal_test")
    
    def test_timer_updates_last_run(self, scheduler):
        """Test that timer updates last_run timestamp."""
        scheduler.add_schedule(
            schedule_id="timestamp_test",
            profile_name="backup",
            interval=ScheduleInterval.DAILY,
        )
        
        schedule = scheduler.schedules["timestamp_test"]
        assert schedule.last_run is None
        
        # Trigger timer
        scheduler._on_timer_fired("timestamp_test")
        
        # Check last_run was updated
        assert schedule.last_run is not None
        now = datetime.now()
        assert abs((schedule.last_run - now).total_seconds()) < 1
    
    def test_stop_all(self, scheduler):
        """Test stopping all timers."""
        scheduler.add_schedule("s1", "backup1", ScheduleInterval.HOURLY)
        scheduler.add_schedule("s2", "backup2", ScheduleInterval.DAILY)
        
        assert len(scheduler._timers) == 2
        
        scheduler.stop_all()
        
        assert len(scheduler._timers) == 0
    
    def test_timer_ignores_disabled_schedules(self, scheduler):
        """Test that timer doesn't trigger disabled schedules."""
        mock_slot = Mock()
        scheduler.schedule_triggered.connect(mock_slot)
        
        scheduler.add_schedule(
            schedule_id="disabled_test",
            profile_name="backup",
            interval=ScheduleInterval.DAILY,
            enabled=True,
        )
        
        # Disable it
        scheduler.schedules["disabled_test"].enabled = False
        
        # Try to trigger
        scheduler._on_timer_fired("disabled_test")
        
        # Signal should not have been emitted
        mock_slot.assert_not_called()


class TestSchedulerIntegration:
    """Integration tests for scheduler with plugin."""
    
    @pytest.fixture
    def mock_plugin(self, tmp_path):
        """Create mock FileManagerPlugin."""
        from mmst.core.services import CoreServices
        from unittest.mock import MagicMock
        
        services = MagicMock(spec=CoreServices)
        services.data_dir = tmp_path
        services.send_notification = MagicMock()
        
        # Mock plugin
        plugin = MagicMock()
        plugin.services = services
        plugin.manifest.identifier = "mmst.file_manager"
        
        return plugin
    
    def test_scheduled_backup_trigger(self, mock_plugin, tmp_path):
        """Test full scheduled backup flow."""
        # Create test profile
        profiles_file = tmp_path / "backup_profiles.json"
        profiles_file.parent.mkdir(parents=True, exist_ok=True)
        
        profiles = {
            "test_profile": {
                "source": str(tmp_path / "source"),
                "target": str(tmp_path / "target"),
                "mirror": False,
            }
        }
        with open(profiles_file, "w", encoding="utf-8") as f:
            json.dump(profiles, f)
        
        # Create source directory
        (tmp_path / "source").mkdir()
        
        # Initialize scheduler
        scheduler = BackupScheduler(mock_plugin.services, tmp_path / "schedules.json")
        
        # Connect signal
        triggered = []
        scheduler.schedule_triggered.connect(
            lambda name, id: triggered.append((name, id))
        )
        
        # Add schedule
        scheduler.add_schedule(
            schedule_id="test_schedule",
            profile_name="test_profile",
            interval=ScheduleInterval.DAILY,
        )
        
        # Trigger manually
        scheduler._on_timer_fired("test_schedule")
        
        # Verify signal was emitted
        assert len(triggered) == 1
        assert triggered[0] == ("test_profile", "test_schedule")
