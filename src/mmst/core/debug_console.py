"""
Debug console for viewing application logs in real-time.

Provides a log viewer widget that can be integrated into settings
or shown as a separate window for debugging purposes.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Signal, QObject  # type: ignore[import-not-found]
from PySide6.QtGui import QTextCursor, QColor  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QComboBox,
    QLineEdit,
    QLabel,
    QCheckBox,
)


class LogHandler(logging.Handler):
    """
    Custom logging handler that emits Qt signals for log records.
    
    Allows real-time log display in UI without blocking.
    """
    
    class Emitter(QObject):
        """Signal emitter for log records."""
        log_emitted = Signal(str, int, str)  # message, level, logger_name
    
    def __init__(self):
        super().__init__()
        self.emitter = self.Emitter()
        
        # Format: [TIME] [LEVEL] [LOGGER] Message
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        self.setFormatter(formatter)
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit log record as Qt signal."""
        try:
            msg = self.format(record)
            self.emitter.log_emitted.emit(msg, record.levelno, record.name)
        except Exception:  # pragma: no cover
            self.handleError(record)


class DebugConsole(QWidget):
    """
    Debug console widget for viewing application logs.
    
    Features:
    - Real-time log display with color coding
    - Level filtering (DEBUG/INFO/WARNING/ERROR/CRITICAL)
    - Text search
    - Auto-scroll option
    - Clear button
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<h2>🐛 Debug-Console</h2>")
        layout.addWidget(header)
        
        # Controls row
        controls = QHBoxLayout()
        
        # Level filter
        controls.addWidget(QLabel("Level:"))
        self.level_combo = QComboBox()
        self.level_combo.addItem("ALLE", logging.NOTSET)
        self.level_combo.addItem("DEBUG", logging.DEBUG)
        self.level_combo.addItem("INFO", logging.INFO)
        self.level_combo.addItem("WARNING", logging.WARNING)
        self.level_combo.addItem("ERROR", logging.ERROR)
        self.level_combo.addItem("CRITICAL", logging.CRITICAL)
        self.level_combo.setCurrentIndex(1)  # Default: DEBUG
        self.level_combo.currentIndexChanged.connect(self._apply_filter)
        controls.addWidget(self.level_combo)
        
        controls.addSpacing(10)
        
        # Search
        controls.addWidget(QLabel("Suche:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Text suchen...")
        self.search_input.textChanged.connect(self._apply_filter)
        controls.addWidget(self.search_input, stretch=1)
        
        # Auto-scroll checkbox
        self.autoscroll_check = QCheckBox("Auto-Scroll")
        self.autoscroll_check.setChecked(True)
        controls.addWidget(self.autoscroll_check)
        
        # Clear button
        clear_btn = QPushButton("Löschen")
        clear_btn.clicked.connect(self._clear_logs)
        controls.addWidget(clear_btn)
        
        layout.addLayout(controls)
        
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }
        """)
        layout.addWidget(self.log_display, stretch=1)
        
        # Stats label
        self.stats_label = QLabel("Bereit")
        layout.addWidget(self.stats_label)
        
        # Internal state
        self._all_logs: list[tuple[str, int, str]] = []  # (message, level, logger_name)
        self._log_handler: Optional[LogHandler] = None
    
    def attach_to_logger(self, logger: logging.Logger) -> None:
        """
        Attach console to a logger hierarchy.
        
        Args:
            logger: Root logger to monitor (typically logging.getLogger())
        """
        if self._log_handler:
            logger.removeHandler(self._log_handler)
        
        self._log_handler = LogHandler()
        self._log_handler.setLevel(logging.DEBUG)
        self._log_handler.emitter.log_emitted.connect(self._on_log_received)
        
        logger.addHandler(self._log_handler)
    
    def _on_log_received(self, message: str, level: int, logger_name: str) -> None:
        """Handle incoming log record."""
        self._all_logs.append((message, level, logger_name))
        
        # Apply filter and potentially add to display
        if self._should_show(message, level, logger_name):
            self._append_colored(message, level)
        
        self._update_stats()
    
    def _should_show(self, message: str, level: int, logger_name: str) -> bool:
        """Check if log should be displayed based on filters."""
        # Level filter
        min_level = self.level_combo.currentData()
        if level < min_level:
            return False
        
        # Search filter
        search_text = self.search_input.text().strip().lower()
        if search_text and search_text not in message.lower():
            return False
        
        return True
    
    def _append_colored(self, message: str, level: int) -> None:
        """Append log message with color coding."""
        # Determine color based on level
        if level >= logging.CRITICAL:
            color = "#ff0000"  # Red
        elif level >= logging.ERROR:
            color = "#ff4444"  # Light red
        elif level >= logging.WARNING:
            color = "#ffaa00"  # Orange
        elif level >= logging.INFO:
            color = "#44ff44"  # Light green
        else:  # DEBUG
            color = "#888888"  # Gray
        
        # Append with color
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        html = f'<span style="color: {color};">{message}</span>'
        cursor.insertHtml(html + '<br>')
        
        # Auto-scroll if enabled
        if self.autoscroll_check.isChecked():
            self.log_display.setTextCursor(cursor)
            self.log_display.ensureCursorVisible()
    
    def _apply_filter(self) -> None:
        """Reapply filters and rebuild display."""
        self.log_display.clear()
        
        for message, level, logger_name in self._all_logs:
            if self._should_show(message, level, logger_name):
                self._append_colored(message, level)
        
        self._update_stats()
    
    def _clear_logs(self) -> None:
        """Clear all logs."""
        self._all_logs.clear()
        self.log_display.clear()
        self._update_stats()
    
    def _update_stats(self) -> None:
        """Update statistics label."""
        total = len(self._all_logs)
        
        # Count by level
        debug = sum(1 for _, lvl, _ in self._all_logs if lvl == logging.DEBUG)
        info = sum(1 for _, lvl, _ in self._all_logs if lvl == logging.INFO)
        warning = sum(1 for _, lvl, _ in self._all_logs if lvl == logging.WARNING)
        error = sum(1 for _, lvl, _ in self._all_logs if lvl == logging.ERROR)
        critical = sum(1 for _, lvl, _ in self._all_logs if lvl == logging.CRITICAL)
        
        stats_text = (
            f"Gesamt: {total} | "
            f"DEBUG: {debug} | INFO: {info} | "
            f"WARNING: {warning} | ERROR: {error} | CRITICAL: {critical}"
        )
        
        self.stats_label.setText(stats_text)
    
    def detach_from_logger(self, logger: logging.Logger) -> None:
        """Remove log handler from logger."""
        if self._log_handler:
            logger.removeHandler(self._log_handler)
            self._log_handler = None
