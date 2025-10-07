from __future__ import annotations

from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from enum import Enum
import time
import uuid
import threading
import queue

from PySide6.QtCore import Qt, QTimer, Signal, QObject  # type: ignore[import-not-found]
from PySide6.QtGui import QColor, QIcon  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QStyle
)


class NotificationLevel(Enum):
    """Notification importance levels."""
    INFO = "info"
    WARNING = "warning"  
    ERROR = "error"
    CRITICAL = "critical"
    SUCCESS = "success"


class Notification:
    """A notification object that holds information about a single notification."""
    
    def __init__(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        source: str = "system",
        details: Optional[str] = None,
        duration: int = 5000,
        action_text: Optional[str] = None,
        action_callback: Optional[Callable] = None,
        dismissible: bool = True
    ):
        """Initialize a notification.
        
        Args:
            message: The main notification message
            level: Notification importance level
            source: Source component/plugin that generated this notification
            details: Optional detailed message (shown in expanded view)
            duration: How long the notification should be shown (ms), 0 for persistent
            action_text: Text for the action button (if any)
            action_callback: Callback for the action button
            dismissible: Whether the notification can be manually dismissed
        """
        self.id = str(uuid.uuid4())
        self.message = message
        self.level = level
        self.source = source
        self.details = details
        self.duration = duration  # milliseconds, 0 = persistent
        self.timestamp = datetime.now()
        self.action_text = action_text
        self.action_callback = action_callback
        self.dismissible = dismissible
        self.dismissed = False
    
    def get_color(self) -> QColor:
        """Get the color associated with this notification level.
        
        Returns:
            QColor for the notification
        """
        if self.level == NotificationLevel.INFO:
            return QColor(70, 130, 180)  # Steel blue
        elif self.level == NotificationLevel.WARNING:
            return QColor(255, 165, 0)   # Orange
        elif self.level == NotificationLevel.ERROR:
            return QColor(220, 20, 60)   # Crimson
        elif self.level == NotificationLevel.CRITICAL:
            return QColor(139, 0, 0)     # Dark red
        elif self.level == NotificationLevel.SUCCESS:
            return QColor(46, 139, 87)   # Sea green
        else:
            return QColor(100, 100, 100) # Gray


class NotificationWidget(QFrame):
    """Widget to display a single notification."""
    
    dismissed = Signal(str)  # Signal emitted when notification is dismissed, passes notification ID
    action_triggered = Signal(str)  # Signal emitted when action is triggered, passes notification ID
    
    def __init__(
        self,
        notification: Notification,
        parent: Optional[QWidget] = None
    ):
        """Initialize notification widget.
        
        Args:
            notification: The notification to display
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.notification = notification
        
        # Set up appearance
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)
        
        # Set minimum size
        self.setMinimumHeight(60)
        self.setMinimumWidth(300)
        
        # Set up layout
        self._setup_ui()
        
        # Set up auto-dismiss timer if needed
        if notification.duration > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._auto_dismiss)
            self._timer.start(notification.duration)
    
    def _setup_ui(self):
        """Set up the UI components."""
        # Create main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        
        # Create header layout
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        
        # Add icon based on level
        icon = self._get_icon_for_level(self.notification.level)
        if icon:
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(24, 24))
            header_layout.addWidget(icon_label)
        
        # Add source label
        source_label = QLabel(self.notification.source)
        source_label.setStyleSheet(f"color: {self.notification.get_color().name()}; font-weight: bold;")
        header_layout.addWidget(source_label)
        
        # Add timestamp
        time_label = QLabel(self.notification.timestamp.strftime("%H:%M:%S"))
        time_label.setStyleSheet("color: #888;")
        header_layout.addWidget(time_label)
        
        # Add spacer
        header_layout.addStretch()
        
        # Add dismiss button if dismissible
        if self.notification.dismissible:
            dismiss_button = QPushButton()
            dismiss_button.setIcon(self.style().standardIcon(QStyle.SP_DialogCloseButton))
            dismiss_button.setFlat(True)
            dismiss_button.setMaximumSize(24, 24)
            dismiss_button.clicked.connect(self._on_dismiss)
            header_layout.addWidget(dismiss_button)
        
        # Add header to main layout
        layout.addLayout(header_layout)
        
        # Add message
        message_label = QLabel(self.notification.message)
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)  # type: ignore[attr-defined]
        layout.addWidget(message_label)
        
        # Add details if available
        if self.notification.details:
            details_label = QLabel(self.notification.details)
            details_label.setWordWrap(True)
            details_label.setTextInteractionFlags(Qt.TextSelectableByMouse)  # type: ignore[attr-defined]
            details_label.setStyleSheet("color: #555; font-size: 0.9em;")
            layout.addWidget(details_label)
        
        # Add action button if available
        if self.notification.action_text and self.notification.action_callback:
            action_button = QPushButton(self.notification.action_text)
            action_button.clicked.connect(self._on_action)
            action_layout = QHBoxLayout()
            action_layout.addStretch()
            action_layout.addWidget(action_button)
            layout.addLayout(action_layout)
    
    def _get_icon_for_level(self, level: NotificationLevel) -> Optional[QIcon]:
        """Get the appropriate icon for the notification level.
        
        Args:
            level: Notification level
            
        Returns:
            QIcon for the notification level
        """
        if level == NotificationLevel.INFO:
            return self.style().standardIcon(QStyle.SP_MessageBoxInformation)
        elif level == NotificationLevel.WARNING:
            return self.style().standardIcon(QStyle.SP_MessageBoxWarning)
        elif level == NotificationLevel.ERROR or level == NotificationLevel.CRITICAL:
            return self.style().standardIcon(QStyle.SP_MessageBoxCritical)
        elif level == NotificationLevel.SUCCESS:
            return self.style().standardIcon(QStyle.SP_DialogApplyButton)
        else:
            return None
    
    def _on_dismiss(self):
        """Handle dismiss button click."""
        self.notification.dismissed = True
        self.dismissed.emit(self.notification.id)
    
    def _on_action(self):
        """Handle action button click."""
        if self.notification.action_callback:
            self.notification.action_callback()
        self.action_triggered.emit(self.notification.id)
    
    def _auto_dismiss(self):
        """Handle auto-dismiss timeout."""
        self._on_dismiss()


class NotificationsAreaWidget(QWidget):
    """Widget for displaying a stack of notifications."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the notifications area widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._notifications: Dict[str, NotificationWidget] = {}
        
        # Set up UI
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Create scroll area
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Create container for notifications
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(5, 5, 5, 5)
        self._container_layout.setSpacing(10)
        self._container_layout.setAlignment(Qt.AlignTop)  # type: ignore[attr-defined]
        
        # Add stretch to push notifications to the top
        self._container_layout.addStretch()
        
        # Set container as scroll area widget
        self._scroll_area.setWidget(self._container)
        
        layout.addWidget(self._scroll_area)
    
    def add_notification(self, notification: Notification):
        """Add a notification to the area.
        
        Args:
            notification: The notification to add
        """
        # Create widget for the notification
        widget = NotificationWidget(notification)
        
        # Connect signals
        widget.dismissed.connect(self._on_notification_dismissed)
        
        # Store in dictionary
        self._notifications[notification.id] = widget
        
        # Add to layout (before the stretch)
        self._container_layout.insertWidget(0, widget)
        
        # Adjust minimum height based on number of notifications
        self._update_size_hint()
        
        # Ensure newest notification is visible
        self._scroll_area.ensureWidgetVisible(widget)
    
    def _on_notification_dismissed(self, notification_id: str):
        """Handle notification dismissal.
        
        Args:
            notification_id: ID of the dismissed notification
        """
        if notification_id in self._notifications:
            # Remove widget
            widget = self._notifications.pop(notification_id)
            self._container_layout.removeWidget(widget)
            widget.deleteLater()
            
            # Update size hint
            self._update_size_hint()
    
    def _update_size_hint(self):
        """Update the widget's size hint based on contents."""
        count = len(self._notifications)
        if count == 0:
            self.setMinimumHeight(50)
        else:
            # Set height to show at most 5 notifications
            visible_count = min(count, 5)
            self.setMinimumHeight(visible_count * 80 + 20)
    
    def clear(self):
        """Clear all notifications."""
        for notification_id in list(self._notifications.keys()):
            self._on_notification_dismissed(notification_id)


class NotificationSignals(QObject):
    """Signals for the notification manager."""
    
    new_notification = Signal(Notification)


class NotificationManager:
    """Manager for system-wide notifications."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> "NotificationManager":
        """Get the singleton instance of the notification manager.
        
        Returns:
            The notification manager instance
        """
        if cls._instance is None:
            cls._instance = NotificationManager()
        return cls._instance
    
    def __init__(self):
        """Initialize the notification manager."""
        if NotificationManager._instance is not None:
            raise RuntimeError("NotificationManager is a singleton, use get_instance()")
            
        # Initialize properties
        self._signals = NotificationSignals()
        self._notifications: List[Notification] = []
        self._history_limit = 100
        
        # Queue for notifications that need to be processed in the Qt thread
        self._queue = queue.Queue()
        
        # Timer to process queue in the Qt thread
        self._timer = QTimer()
        self._timer.timeout.connect(self._process_queue)
        self._timer.start(100)  # Process every 100 ms
    
    def notify(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        source: str = "system",
        details: Optional[str] = None,
        duration: int = 5000,
        action_text: Optional[str] = None,
        action_callback: Optional[Callable] = None,
        dismissible: bool = True
    ) -> Notification:
        """Send a notification.
        
        Args:
            message: The main notification message
            level: Notification importance level
            source: Source component/plugin that generated this notification
            details: Optional detailed message (shown in expanded view)
            duration: How long the notification should be shown (ms), 0 for persistent
            action_text: Text for the action button (if any)
            action_callback: Callback for the action button
            dismissible: Whether the notification can be manually dismissed
            
        Returns:
            The created notification object
        """
        # Create notification
        notification = Notification(
            message=message,
            level=level,
            source=source,
            details=details,
            duration=duration,
            action_text=action_text,
            action_callback=action_callback,
            dismissible=dismissible
        )
        
        # Add to queue for processing in Qt thread
        self._queue.put(notification)
        
        return notification
    
    def _process_queue(self):
        """Process the notification queue."""
        # Process all notifications in the queue
        while not self._queue.empty():
            try:
                notification = self._queue.get_nowait()
                
                # Add to history
                self._notifications.append(notification)
                
                # Limit history size
                if len(self._notifications) > self._history_limit:
                    self._notifications.pop(0)
                
                # Emit signal for UI components
                self._signals.new_notification.emit(notification)
                
                # Mark as done
                self._queue.task_done()
            except queue.Empty:
                break
    
    def get_history(self) -> List[Notification]:
        """Get notification history.
        
        Returns:
            List of notifications
        """
        return self._notifications.copy()
    
    def get_signals(self) -> NotificationSignals:
        """Get the notification signals object.
        
        Returns:
            The notification signals
        """
        return self._signals
    
    def clear_history(self):
        """Clear notification history."""
        self._notifications.clear()