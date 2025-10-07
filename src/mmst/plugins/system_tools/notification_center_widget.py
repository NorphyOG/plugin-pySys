from __future__ import annotations

from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import time

from PySide6.QtCore import Qt, QTimer, Signal, Slot  # type: ignore[import-not-found]
from PySide6.QtGui import QColor, QIcon, QAction  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QToolButton, QMenu,
    QTabWidget, QCheckBox, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox
)

from mmst.core.notification_manager import (
    Notification, NotificationLevel, NotificationsAreaWidget,
    NotificationManager
)
from mmst.core.console_logger import ConsoleLogger


class NotificationCenterWidget(QWidget):
    """Widget for displaying and managing notifications."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the notification center.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Get logger
        self._logger = ConsoleLogger.get_instance().get_logger("MMST.NotificationCenter")
        
        # Get notification manager
        self._notification_mgr = NotificationManager.get_instance()
        
        # Store notification widgets
        self._notification_widgets: Dict[str, QWidget] = {}
        
        # Setup UI
        self._setup_ui()
        
        # Connect signals
        self._connect_signals()
        
        # Load initial history
        self._load_history()
    
    def _setup_ui(self):
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        
        # Create header with controls
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Notification Center")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        self._filter_combo = QComboBox()
        self._filter_combo.addItem("All Notifications", None)
        self._filter_combo.addItem("Info", NotificationLevel.INFO.value)
        self._filter_combo.addItem("Warning", NotificationLevel.WARNING.value)
        self._filter_combo.addItem("Error", NotificationLevel.ERROR.value)
        self._filter_combo.addItem("Critical", NotificationLevel.CRITICAL.value)
        self._filter_combo.addItem("Success", NotificationLevel.SUCCESS.value)
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        header_layout.addWidget(self._filter_combo)
        
        clear_button = QPushButton("Clear All")
        clear_button.clicked.connect(self._clear_all)
        header_layout.addWidget(clear_button)
        
        main_layout.addLayout(header_layout)
        
        # Create tabs
        self._tab_widget = QTabWidget()
        
        # Create active notifications tab
        active_tab = QWidget()
        active_layout = QVBoxLayout(active_tab)
        active_layout.setContentsMargins(0, 0, 0, 0)
        
        self._active_area = NotificationsAreaWidget()
        active_layout.addWidget(self._active_area)
        
        self._tab_widget.addTab(active_tab, "Active")
        
        # Create history tab
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.setContentsMargins(0, 0, 0, 0)
        
        self._history_table = QTableWidget(0, 4)
        self._history_table.setHorizontalHeaderLabels(["Time", "Source", "Level", "Message"])
        self._history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        history_layout.addWidget(self._history_table)
        
        self._tab_widget.addTab(history_tab, "History")
        
        main_layout.addWidget(self._tab_widget)
        
        # Set minimum size
        self.setMinimumSize(500, 400)
    
    def _connect_signals(self):
        """Connect notification signals."""
        # Connect to notification manager signals
        self._notification_mgr.get_signals().new_notification.connect(self._on_new_notification)
    
    def _load_history(self):
        """Load initial notification history."""
        history = self._notification_mgr.get_history()
        for notification in history:
            self._add_to_history_table(notification)
    
    def _on_new_notification(self, notification: Notification):
        """Handle new notification signal.
        
        Args:
            notification: The new notification
        """
        # Add to active notifications area
        self._active_area.add_notification(notification)
        
        # Add to history table
        self._add_to_history_table(notification)
        
        # Log the notification
        self._log_notification(notification)
    
    def _add_to_history_table(self, notification: Notification):
        """Add a notification to the history table.
        
        Args:
            notification: The notification to add
        """
        # Check filter
        filter_value = self._filter_combo.currentData()
        if filter_value is not None and notification.level.value != filter_value:
            return
        
        # Add to table
        row = self._history_table.rowCount()
        self._history_table.insertRow(row)
        
        # Time
        time_item = QTableWidgetItem(notification.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        self._history_table.setItem(row, 0, time_item)
        
        # Source
        source_item = QTableWidgetItem(notification.source)
        self._history_table.setItem(row, 1, source_item)
        
        # Level
        level_item = QTableWidgetItem(notification.level.value)
        level_item.setForeground(notification.get_color())
        self._history_table.setItem(row, 2, level_item)
        
        # Message
        message_item = QTableWidgetItem(notification.message)
        self._history_table.setItem(row, 3, message_item)
        
        # Scroll to new row
        self._history_table.scrollToItem(time_item)
    
    def _log_notification(self, notification: Notification):
        """Log a notification to the application log.
        
        Args:
            notification: The notification to log
        """
        # Map notification level to log level
        if notification.level == NotificationLevel.INFO:
            log_method = self._logger.info
        elif notification.level == NotificationLevel.WARNING:
            log_method = self._logger.warning
        elif notification.level == NotificationLevel.ERROR:
            log_method = self._logger.error
        elif notification.level == NotificationLevel.CRITICAL:
            log_method = self._logger.critical
        elif notification.level == NotificationLevel.SUCCESS:
            log_method = self._logger.info
        else:
            log_method = self._logger.info
        
        # Log the message
        log_method(f"NOTIFICATION [{notification.source}]: {notification.message}")
        if notification.details:
            log_method(f"  Details: {notification.details}")
    
    def _on_filter_changed(self):
        """Handle filter combo box change."""
        # Clear table
        self._history_table.setRowCount(0)
        
        # Reload history with filter
        self._load_history()
    
    def _clear_all(self):
        """Clear all notifications."""
        # Clear active notifications
        self._active_area.clear()
        
        # Clear history table
        self._history_table.setRowCount(0)
        
        # Note: This doesn't clear the notification manager history
        # as that would affect other notification center instances
    
    def add_test_notification(self, level: NotificationLevel):
        """Add a test notification.
        
        Args:
            level: Level for the test notification
        """
        self._notification_mgr.notify(
            message=f"This is a test {level.value} notification",
            level=level,
            source="NotificationTest",
            details=f"This is additional details for the {level.value} notification.\n"
                   f"It can contain multiple lines of text.",
            duration=level == NotificationLevel.INFO and 5000 or 0  # Only auto-dismiss INFO
        )
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the widget.
        
        Args:
            enabled: Whether to enable the widget
        """
        self.setEnabled(enabled)