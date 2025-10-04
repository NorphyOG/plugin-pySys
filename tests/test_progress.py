"""
Unit tests for global progress tracking system.
"""
import pytest
from unittest.mock import MagicMock, patch

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # type: ignore[import-not-found]

from mmst.core.progress import (
    ProgressTask,
    TaskProgressWidget,
    ProgressDialog,
    ProgressTracker,
)


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestProgressTask:
    """Test ProgressTask dataclass."""
    
    def test_initialization(self):
        """Test task creation with defaults."""
        task = ProgressTask(
            task_id="test_123",
            title="Test Task",
        )
        
        assert task.task_id == "test_123"
        assert task.title == "Test Task"
        assert task.current == 0
        assert task.total == 100
        assert task.status == ""
        assert task.completed is False
        assert task.failed is False
    
    def test_custom_values(self):
        """Test task with custom values."""
        task = ProgressTask(
            task_id="custom",
            title="Custom",
            current=50,
            total=200,
            status="Processing...",
            completed=True,
            failed=False,
        )
        
        assert task.current == 50
        assert task.total == 200
        assert task.status == "Processing..."
        assert task.completed is True


class TestTaskProgressWidget:
    """Test TaskProgressWidget."""
    
    def test_widget_creation(self, qapp):
        """Test widget initialization."""
        task = ProgressTask(task_id="test", title="Test Task", total=100)
        widget = TaskProgressWidget(task)
        
        assert widget.task == task
        assert widget.title_label.text() == "<b>Test Task</b>"
        assert widget.progress_bar.maximum() == 100
        assert widget.progress_bar.value() == 0
    
    def test_update_progress(self, qapp):
        """Test progress update."""
        task = ProgressTask(task_id="test", title="Test", total=100)
        widget = TaskProgressWidget(task)
        
        widget.update_progress(50, 100, "Processing files")
        
        assert widget.progress_bar.value() == 50
        assert "50%" in widget.status_label.text()
        assert "Processing files" in widget.status_label.text()
    
    def test_mark_completed_success(self, qapp):
        """Test marking as completed successfully."""
        task = ProgressTask(task_id="test", title="Test", total=100)
        widget = TaskProgressWidget(task)
        
        widget.mark_completed(success=True)
        
        assert widget.progress_bar.value() == widget.progress_bar.maximum()
        assert "Abgeschlossen" in widget.status_label.text()
    
    def test_mark_completed_failure(self, qapp):
        """Test marking as failed."""
        task = ProgressTask(task_id="test", title="Test", total=100)
        widget = TaskProgressWidget(task)
        
        widget.mark_completed(success=False)
        
        assert "Fehlgeschlagen" in widget.status_label.text()


class TestProgressDialog:
    """Test ProgressDialog."""
    
    def test_dialog_creation(self, qapp):
        """Test dialog initialization."""
        dialog = ProgressDialog()
        
        assert dialog.windowTitle() == "Fortschritt"
        assert len(dialog.task_widgets) == 0
        assert not dialog.isVisible()
    
    def test_add_task(self, qapp):
        """Test adding a task."""
        dialog = ProgressDialog()
        
        dialog.add_task("task1", "Test Task", total=100)
        
        assert "task1" in dialog.task_widgets
        assert dialog.isVisible()  # Should auto-show
    
    def test_update_task(self, qapp):
        """Test updating task progress."""
        dialog = ProgressDialog()
        dialog.add_task("task1", "Test", total=100)
        
        dialog.update_task("task1", 50, 100, "Halfway done")
        
        widget = dialog.task_widgets["task1"]
        assert widget.progress_bar.value() == 50
    
    def test_complete_task(self, qapp):
        """Test completing a task."""
        dialog = ProgressDialog()
        dialog.add_task("task1", "Test", total=100)
        
        dialog.complete_task("task1", success=True)
        
        widget = dialog.task_widgets["task1"]
        assert widget.task.completed is True
    
    def test_remove_task(self, qapp):
        """Test removing a task."""
        dialog = ProgressDialog()
        dialog.add_task("task1", "Test", total=100)
        
        assert "task1" in dialog.task_widgets
        
        dialog.remove_task("task1")
        
        assert "task1" not in dialog.task_widgets
    
    def test_clear_completed(self, qapp):
        """Test clearing completed tasks."""
        dialog = ProgressDialog()
        dialog.add_task("task1", "Test 1", total=100)
        dialog.add_task("task2", "Test 2", total=100)
        dialog.add_task("task3", "Test 3", total=100)
        
        dialog.complete_task("task1", success=True)
        dialog.complete_task("task2", success=False)
        # task3 remains active
        
        dialog._clear_completed()
        
        assert "task1" not in dialog.task_widgets
        assert "task2" not in dialog.task_widgets
        assert "task3" in dialog.task_widgets
    
    def test_has_active_tasks(self, qapp):
        """Test checking for active tasks."""
        dialog = ProgressDialog()
        
        assert not dialog.has_active_tasks()
        
        dialog.add_task("task1", "Test", total=100)
        assert dialog.has_active_tasks()
        
        dialog.complete_task("task1")
        assert not dialog.has_active_tasks()


class TestProgressTracker:
    """Test ProgressTracker service."""
    
    def test_start_task(self, qapp):
        """Test starting a new task."""
        tracker = ProgressTracker()
        dialog = ProgressDialog()
        tracker.set_dialog(dialog)
        
        task_id = tracker.start_task("Test Task", total=100)
        
        assert task_id is not None
        assert task_id in dialog.task_widgets
    
    def test_update_task(self, qapp):
        """Test updating task via tracker."""
        tracker = ProgressTracker()
        dialog = ProgressDialog()
        tracker.set_dialog(dialog)
        
        task_id = tracker.start_task("Test", total=100)
        tracker.update(task_id, 50, 100, "Halfway")
        
        widget = dialog.task_widgets[task_id]
        assert widget.progress_bar.value() == 50
    
    def test_complete_task(self, qapp):
        """Test completing task via tracker."""
        tracker = ProgressTracker()
        dialog = ProgressDialog()
        tracker.set_dialog(dialog)
        
        task_id = tracker.start_task("Test", total=100)
        tracker.complete(task_id, success=True)
        
        widget = dialog.task_widgets[task_id]
        assert widget.task.completed is True
    
    def test_show_hide_dialog(self, qapp):
        """Test showing/hiding dialog via tracker."""
        tracker = ProgressTracker()
        dialog = ProgressDialog()
        tracker.set_dialog(dialog)
        
        assert not dialog.isVisible()
        
        tracker.show_dialog()
        assert dialog.isVisible()
        
        tracker.hide_dialog()
        assert not dialog.isVisible()


class TestProgressIntegration:
    """Integration tests for progress tracking."""
    
    def test_multiple_concurrent_tasks(self, qapp):
        """Test tracking multiple tasks simultaneously."""
        tracker = ProgressTracker()
        dialog = ProgressDialog()
        tracker.set_dialog(dialog)
        
        task1 = tracker.start_task("Task 1", 100)
        task2 = tracker.start_task("Task 2", 200)
        task3 = tracker.start_task("Task 3", 50)
        
        assert len(dialog.task_widgets) == 3
        
        tracker.update(task1, 50, 100, "Task 1 progress")
        tracker.update(task2, 100, 200, "Task 2 progress")
        tracker.complete(task3, success=True)
        
        assert dialog.task_widgets[task1].progress_bar.value() == 50
        assert dialog.task_widgets[task2].progress_bar.value() == 100
        assert dialog.task_widgets[task3].task.completed is True
    
    def test_task_lifecycle(self, qapp):
        """Test complete task lifecycle."""
        tracker = ProgressTracker()
        dialog = ProgressDialog()
        tracker.set_dialog(dialog)
        
        # Start task
        task_id = tracker.start_task("Complete Lifecycle", total=5)
        assert dialog.isVisible()
        assert task_id in dialog.task_widgets
        
        # Progress through steps
        for i in range(1, 6):
            tracker.update(task_id, i, 5, f"Step {i}/5")
        
        widget = dialog.task_widgets[task_id]
        assert widget.progress_bar.value() == 5
        
        # Complete
        tracker.complete(task_id, success=True)
        assert widget.task.completed is True
        
        # Remove
        dialog.remove_task(task_id)
        assert task_id not in dialog.task_widgets
