from __future__ import annotations

from typing import List, Optional
import re
import logging
import sys
from datetime import datetime

from PySide6.QtCore import Qt, Signal, Slot, QTimer  # type: ignore[import-not-found]
from PySide6.QtGui import QTextCursor, QColor, QFont, QAction  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QPlainTextEdit, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QFileDialog,
    QMenu, QToolBar, QLineEdit
)

from mmst.core.console_logger import ConsoleLogger


class ConsoleWidget(QWidget):
    """Enhanced widget for displaying logs from the ConsoleLogger."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the console widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Get the ConsoleLogger instance
        self._logger = ConsoleLogger.get_instance()
        self._app_logger = self._logger.get_logger("MMST.Console")
        
        # Initialize search variables
        self._search_results = []
        self._current_result = -1
        
        # Set up UI
        self._setup_ui()
        
        # Start periodic log refresh
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_logs)
        self._timer.start(1000)  # Refresh every second
        
        # Initialize component tracking
        self._components_seen = set()
        
        # Initialize with existing logs
        self._refresh_logs()
        
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Create toolbar
        toolbar = QToolBar()
        
        # Add level filter
        level_label = QLabel("Log Level:")
        toolbar.addWidget(level_label)
        
        self._level_combo = QComboBox()
        self._level_combo.addItems(["All", "Debug", "Info", "Warning", "Error", "Critical"])
        self._level_combo.setCurrentText("Info")
        self._level_combo.currentTextChanged.connect(self._filter_logs)
        toolbar.addWidget(self._level_combo)
        
        # Add component filter
        component_label = QLabel("Component:")
        toolbar.addWidget(component_label)
        
        self._component_combo = QComboBox()
        self._component_combo.addItem("All")
        self._component_combo.setMinimumWidth(120)
        self._component_combo.currentTextChanged.connect(self._filter_logs)
        toolbar.addWidget(self._component_combo)
        
        # Add search functionality
        toolbar.addSeparator()
        search_label = QLabel("Search:")
        toolbar.addWidget(search_label)
        
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Enter search text...")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.setMinimumWidth(200)
        self._search_box.returnPressed.connect(self._search_logs)
        toolbar.addWidget(self._search_box)
        
        search_button = QPushButton("Search")
        search_button.clicked.connect(self._search_logs)
        toolbar.addWidget(search_button)
        
        # Add next/previous buttons for search results
        self._next_button = QPushButton("▼ Next")
        self._next_button.clicked.connect(self._search_next)
        self._next_button.setEnabled(False)
        toolbar.addWidget(self._next_button)
        
        self._prev_button = QPushButton("▲ Previous")
        self._prev_button.clicked.connect(self._search_previous)
        self._prev_button.setEnabled(False)
        toolbar.addWidget(self._prev_button)
        
        # Add results count label
        self._results_label = QLabel("")
        toolbar.addWidget(self._results_label)
        
        # Add clear button
        toolbar.addSeparator()
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._clear)
        toolbar.addWidget(clear_button)
        
        # Add open log folder button
        toolbar.addSeparator()
        open_log_folder_button = QPushButton("Open Log Folder")
        open_log_folder_button.clicked.connect(self._open_log_folder)
        toolbar.addWidget(open_log_folder_button)
        
        layout.addWidget(toolbar)
        
        # Add the console text widget
        self._console = QPlainTextEdit()
        self._console.setReadOnly(True)
        self._console.setMaximumBlockCount(5000)  # limit scrollback
        self._console.setContextMenuPolicy(Qt.CustomContextMenu)  # type: ignore[attr-defined]
        self._console.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._console)
        
        # Set monospace font for better log readability
        font = QFont("Courier New", 9)  # or "Monospace" or "Consolas" etc.
        self._console.setFont(font)
        
        # Set tab width to avoid unwieldy indentation
        metrics = self._console.fontMetrics()
        self._console.setTabStopDistance(4 * metrics.horizontalAdvance(' '))
        
    def _show_context_menu(self, pos):
        """Show context menu for the console text widget."""
        menu = self._console.createStandardContextMenu()
        
        # Add custom actions
        menu.addSeparator()
        
        copy_all_action = QAction("Copy All", self)
        copy_all_action.triggered.connect(self._copy_all)
        menu.addAction(copy_all_action)
        
        save_action = QAction("Save Logs...", self)
        save_action.triggered.connect(self._save_logs)
        menu.addAction(save_action)
        
        # Show the menu
        menu.exec(self._console.mapToGlobal(pos))
    
    def _copy_all(self):
        """Copy all text to clipboard."""
        self._console.selectAll()
        self._console.copy()
        # Deselect
        cursor = self._console.textCursor()
        cursor.clearSelection()
        self._console.setTextCursor(cursor)
    
    def _save_logs(self):
        """Save logs to a file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Logs", "", "Log Files (*.log);;Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self._console.toPlainText())
                self._app_logger.info(f"Logs saved to: {file_path}")
            except Exception as e:
                self._app_logger.error(f"Failed to save logs: {e}")
    
    def _open_log_folder(self):
        """Open the log folder in file explorer."""
        try:
            from pathlib import Path
            import os
            log_dir = Path.home() / ".mmst" / "logs"
            if log_dir.exists():
                if os.name == 'nt':  # Windows
                    import subprocess
                    subprocess.run(['explorer', str(log_dir)])
                elif os.name == 'posix':  # macOS or Linux
                    if sys.platform == 'darwin':  # macOS
                        subprocess.run(['open', str(log_dir)])
                    else:  # Linux
                        subprocess.run(['xdg-open', str(log_dir)])
                self._app_logger.info(f"Opened log folder: {log_dir}")
            else:
                self._app_logger.warning(f"Log directory does not exist: {log_dir}")
        except Exception as e:
            self._app_logger.error(f"Failed to open log folder: {e}")
    
    def _clear(self):
        """Clear the console."""
        self._console.clear()
        
    def _refresh_logs(self):
        """Refresh logs from the logger buffer."""
        buffer = self._logger.get_buffer()
        
        # Store current cursor position
        scroll_bar = self._console.verticalScrollBar()
        was_at_bottom = scroll_bar.value() == scroll_bar.maximum()
        
        # Store current content
        current_text = self._console.toPlainText()
        
        # Check if we have active search
        had_search = len(self._search_results) > 0
        current_search_text = self._search_box.text().strip() if had_search else ""
        
        # Only update if content changed
        new_text = "\n".join(buffer)
        if new_text != current_text:
            # Remember cursor position
            old_cursor = self._console.textCursor()
            old_position = old_cursor.position()
            
            # Set new text - we'll do this when filtering
            # self._console.setPlainText(new_text)
            
            # Apply filtering - this will also update the text and component dropdown
            self._filter_logs()
            
            # If previously at bottom, scroll to bottom
            if was_at_bottom:
                scroll_bar.setValue(scroll_bar.maximum())
            else:
                # Try to restore cursor position
                new_cursor = self._console.textCursor()
                new_cursor.setPosition(min(old_position, len(new_text)))
                self._console.setTextCursor(new_cursor)
            
            # Re-run search if there was one active
            if had_search and current_search_text:
                self._search_logs()
    
    def _filter_logs(self):
        """Filter logs based on selected level and component."""
        level_text = self._level_combo.currentText().lower()
        component_text = self._component_combo.currentText()
        
        # Map level names to their numeric values
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL
        }
        
        apply_level_filter = level_text != "all"
        apply_component_filter = component_text != "All"
        
        # If no filters active, show all logs
        if not apply_level_filter and not apply_component_filter:
            # Show all logs
            buffer = self._logger.get_buffer()
            self._console.setPlainText("\n".join(buffer))
            scroll_bar = self._console.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.maximum())
            return
            
        if apply_level_filter:
            selected_level = level_map.get(level_text, logging.INFO)
        
        # Get the current logs and filter
        buffer = self._logger.get_buffer()
        filtered_logs = []
        components_seen = set()
        
        for line in buffer:
            include_line = True
            
            # Extract component from the line - format is typically "[LEVEL] COMPONENT: Message"
            component_match = re.search(r'\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]\s+([^:]+):', line, re.IGNORECASE)
            
            # Filter by level
            if apply_level_filter and include_line:
                level_match = re.search(r'\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]', line, re.IGNORECASE)
                if level_match:
                    line_level_text = level_match.group(1).lower()
                    line_level = level_map.get(line_level_text, 0)
                    include_line = line_level >= selected_level
                # If we can't determine level, include by default for level filter
            
            # Filter by component
            if apply_component_filter and include_line:
                if component_match:
                    line_component = component_match.group(2).strip()
                    components_seen.add(line_component)
                    include_line = line_component == component_text
                else:
                    # If we can't determine component, exclude for component filter
                    include_line = False
            
            # Add components to dropdown if not already there
            if component_match and not apply_component_filter:
                line_component = component_match.group(2).strip()
                components_seen.add(line_component)
            
            if include_line:
                filtered_logs.append(line)
        
        # Update console with filtered logs
        self._console.setPlainText("\n".join(filtered_logs))
        
        # Update component dropdown with discovered components
        self._update_component_dropdown(components_seen)
        
        # Scroll to bottom
        scroll_bar = self._console.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())
        
    def _update_component_dropdown(self, components_seen):
        """Update the component dropdown with discovered components.
        
        Args:
            components_seen: Set of component names found in logs
        """
        # Remember current selection
        current_component = self._component_combo.currentText()
        
        # Block signals during update
        self._component_combo.blockSignals(True)
        
        # Remember components we've already added
        existing_components = [self._component_combo.itemText(i) 
                              for i in range(1, self._component_combo.count())]
        
        # Add new components
        for component in sorted(components_seen):
            if component not in existing_components and component != "All":
                self._component_combo.addItem(component)
                
        # Restore selection or default to "All"
        if current_component in [self._component_combo.itemText(i) 
                                for i in range(self._component_combo.count())]:
            self._component_combo.setCurrentText(current_component)
        else:
            self._component_combo.setCurrentText("All")
            
        # Unblock signals
        self._component_combo.blockSignals(False)
    
    def append_text(self, text: str):
        """Append plain text to the console.
        
        Args:
            text: Text to append
        """
        self._console.appendPlainText(text)
        self._scroll_to_bottom()
    
    def append_html(self, html: str):
        """Append HTML text to the console.
        
        Args:
            html: HTML text to append
        """
        cursor = self._console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)  # type: ignore[attr-defined]
        cursor.insertHtml(html)  # type: ignore[attr-defined]
        cursor.insertText("\n")  # type: ignore[attr-defined]
        self._console.setTextCursor(cursor)
        self._scroll_to_bottom()
    
    def append_log(self, text: str, level: str = "info"):
        """Append a log message with appropriate formatting.
        
        Args:
            text: Log message
            level: Log level ("debug", "info", "warning", "error", or "critical")
        """
        # Map level to color
        colors = {
            "debug": "#607D8B",    # Blue Gray
            "info": "#2E7D32",     # Green
            "warning": "#FF8F00",  # Amber
            "error": "#C62828",    # Red
            "critical": "#6A1B9A"  # Purple
        }
        
        color = colors.get(level.lower(), colors["info"])
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        html = f'<span style="color: #555;">[{timestamp}]</span> <span style="color: {color};">[{level.upper()}]</span> {text}'
        self.append_html(html)
    
    def _scroll_to_bottom(self):
        """Scroll the console to the bottom."""
        self._console.verticalScrollBar().setValue(
            self._console.verticalScrollBar().maximum()
        )
    
    # Search functionality methods
    def _search_logs(self):
        """Search logs for the given text."""
        search_text = self._search_box.text().strip()
        if not search_text:
            self._results_label.setText("")
            self._next_button.setEnabled(False)
            self._prev_button.setEnabled(False)
            return
            
        # Create a list of matching positions
        self._search_results = []
        self._current_result = -1
        
        cursor = self._console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)  # type: ignore[attr-defined]
        self._console.setTextCursor(cursor)
        
        # Find all occurrences
        cursor = self._console.document().find(search_text)
        while not cursor.isNull():
            self._search_results.append(cursor.position())
            cursor = self._console.document().find(search_text, cursor)
        
        # Update UI based on results
        result_count = len(self._search_results)
        if result_count > 0:
            self._results_label.setText(f"Found {result_count} matches")
            self._next_button.setEnabled(True)
            self._prev_button.setEnabled(True)
            self._search_next()  # Go to first result
        else:
            self._results_label.setText("No matches found")
            self._next_button.setEnabled(False)
            self._prev_button.setEnabled(False)
    
    def _search_next(self):
        """Navigate to the next search result."""
        if not self._search_results:
            return
            
        self._current_result = (self._current_result + 1) % len(self._search_results)
        self._goto_current_result()
    
    def _search_previous(self):
        """Navigate to the previous search result."""
        if not self._search_results:
            return
            
        self._current_result = (self._current_result - 1) % len(self._search_results)
        self._goto_current_result()
    
    def _goto_current_result(self):
        """Go to the current search result position."""
        if 0 <= self._current_result < len(self._search_results):
            position = self._search_results[self._current_result]
            cursor = self._console.textCursor()
            cursor.setPosition(position)
            
            # Select the matched text (assuming the search text length)
            search_text = self._search_box.text()
            cursor.movePosition(
                QTextCursor.MoveOperation.Right,  # type: ignore[attr-defined]
                QTextCursor.MoveMode.KeepAnchor,  # type: ignore[attr-defined]
                len(search_text)
            )
            
            self._console.setTextCursor(cursor)
            self._console.ensureCursorVisible()
            self._results_label.setText(f"Match {self._current_result + 1} of {len(self._search_results)}")