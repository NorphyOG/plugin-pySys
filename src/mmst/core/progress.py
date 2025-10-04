"""
Global progress tracking system for long-running operations.

Provides a centralized progress dialog that can be shown/hidden,
tracking multiple concurrent tasks with progress bars and status messages.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional
from uuid import uuid4

from PySide6.QtCore import Qt, Signal, QObject  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QWidget,
    QGroupBox,
)


@dataclass
class ProgressTask:
    """Represents a single progress-tracked task."""
    
    task_id: str
    title: str
    current: int = 0
    total: int = 100
    status: str = ""
    completed: bool = False
    failed: bool = False


class TaskProgressWidget(QWidget):
    """Widget displaying a single task's progress."""
    
    def __init__(self, task: ProgressTask) -> None:
        super().__init__()
        self.task = task
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Title
        self.title_label = QLabel(f"<b>{task.title}</b>")
        layout.addWidget(self.title_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, max(1, task.total))
        self.progress_bar.setValue(task.current)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel(task.status or "Warte...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
    
    def update_progress(self, current: int, total: int, status: str) -> None:
        """Update progress display."""
        self.progress_bar.setRange(0, max(1, total))
        self.progress_bar.setValue(current)
        
        if total > 0:
            percentage = int((current / total) * 100)
            self.status_label.setText(f"{status} ({percentage}%)")
        else:
            self.status_label.setText(status)
    
    def mark_completed(self, success: bool = True) -> None:
        """Mark task as completed."""
        if success:
            self.progress_bar.setValue(self.progress_bar.maximum())
            self.status_label.setText("✓ Abgeschlossen")
            self.status_label.setStyleSheet("color: green;")
        else:
            self.status_label.setText("✗ Fehlgeschlagen")
            self.status_label.setStyleSheet("color: red;")


class ProgressDialog(QDialog):
    """
    Global progress dialog showing all active tasks.
    
    Can be shown/hidden without losing progress state.
    Supports multiple concurrent tasks from different plugins.
    """
    
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fortschritt")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        
        # Keep dialog open when clicking outside
        self.setModal(False)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<h2>⏳ Laufende Vorgänge</h2>")
        layout.addWidget(header)
        
        # Scroll area for tasks
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_layout.addStretch()
        
        scroll.setWidget(self.tasks_container)
        layout.addWidget(scroll, stretch=1)
        
        # Bottom buttons
        button_row = QHBoxLayout()
        button_row.addStretch()
        
        self.clear_button = QPushButton("Abgeschlossene entfernen")
        self.clear_button.clicked.connect(self._clear_completed)
        button_row.addWidget(self.clear_button)
        
        close_button = QPushButton("Schließen")
        close_button.clicked.connect(self.hide)
        button_row.addWidget(close_button)
        
        layout.addLayout(button_row)
        
        # Task tracking
        self.task_widgets: Dict[str, TaskProgressWidget] = {}
    
    def add_task(self, task_id: str, title: str, total: int = 100) -> None:
        """Add a new task to track."""
        if task_id in self.task_widgets:
            return  # Task already exists
        
        task = ProgressTask(
            task_id=task_id,
            title=title,
            total=total,
        )
        
        widget = TaskProgressWidget(task)
        
        # Insert before stretch
        self.tasks_layout.insertWidget(self.tasks_layout.count() - 1, widget)
        self.task_widgets[task_id] = widget
        
        # Show dialog if hidden
        if not self.isVisible():
            self.show()
    
    def update_task(self, task_id: str, current: int, total: int, status: str) -> None:
        """Update task progress."""
        if task_id not in self.task_widgets:
            return
        
        self.task_widgets[task_id].update_progress(current, total, status)
    
    def complete_task(self, task_id: str, success: bool = True) -> None:
        """Mark task as completed."""
        if task_id not in self.task_widgets:
            return
        
        self.task_widgets[task_id].mark_completed(success)
        self.task_widgets[task_id].task.completed = True
        self.task_widgets[task_id].task.failed = not success
    
    def remove_task(self, task_id: str) -> None:
        """Remove a task from display."""
        if task_id not in self.task_widgets:
            return
        
        widget = self.task_widgets[task_id]
        self.tasks_layout.removeWidget(widget)
        widget.deleteLater()
        del self.task_widgets[task_id]
        
        # Hide dialog if no tasks remain
        if not self.task_widgets:
            self.hide()
    
    def _clear_completed(self) -> None:
        """Remove all completed/failed tasks."""
        to_remove = [
            task_id
            for task_id, widget in self.task_widgets.items()
            if widget.task.completed or widget.task.failed
        ]
        
        for task_id in to_remove:
            self.remove_task(task_id)
    
    def has_active_tasks(self) -> bool:
        """Check if any tasks are still active."""
        return any(
            not (widget.task.completed or widget.task.failed)
            for widget in self.task_widgets.values()
        )


class ProgressTracker(QObject):
    """
    Service for tracking progress across the application.
    
    Plugins can register tasks and emit progress updates.
    """
    
    task_added = Signal(str, str, int)  # task_id, title, total
    task_updated = Signal(str, int, int, str)  # task_id, current, total, status
    task_completed = Signal(str, bool)  # task_id, success
    
    def __init__(self) -> None:
        super().__init__()
        self._dialog: Optional[ProgressDialog] = None
        self._log = logging.getLogger("MMST.Progress")
    
    def set_dialog(self, dialog: ProgressDialog) -> None:
        """Connect to progress dialog."""
        self._dialog = dialog
        self.task_added.connect(dialog.add_task)
        self.task_updated.connect(dialog.update_task)
        self.task_completed.connect(dialog.complete_task)
    
    def start_task(self, title: str, total: int = 100) -> str:
        """
        Start tracking a new task.
        
        Args:
            title: Display name for the task
            total: Total number of steps (default 100 for percentage)
        
        Returns:
            task_id: Unique identifier for updating progress
        """
        task_id = str(uuid4())
        self._log.info(f"Starting task: {title} (total={total})")
        self.task_added.emit(task_id, title, total)
        return task_id
    
    def update(self, task_id: str, current: int, total: int = -1, status: str = "") -> None:
        """
        Update task progress.
        
        Args:
            task_id: Task identifier from start_task()
            current: Current progress value
            total: New total (optional, keeps previous if -1)
            status: Status message to display
        """
        if total == -1:
            total = 100  # Default fallback
        self.task_updated.emit(task_id, current, total, status)
    
    def complete(self, task_id: str, success: bool = True) -> None:
        """
        Mark task as completed.
        
        Args:
            task_id: Task identifier
            success: Whether task completed successfully
        """
        status_text = "✅ erfolgreich" if success else "❌ fehlgeschlagen"
        self._log.info(f"Task completed: {task_id[:8]}... {status_text}")
        self.task_completed.emit(task_id, success)
    
    def show_dialog(self) -> None:
        """Show progress dialog."""
        if self._dialog:
            self._dialog.show()
            self._dialog.raise_()
            self._dialog.activateWindow()
    
    def hide_dialog(self) -> None:
        """Hide progress dialog."""
        if self._dialog:
            self._dialog.hide()
