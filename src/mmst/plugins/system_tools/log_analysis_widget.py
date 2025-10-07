from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import sys
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, Signal, Slot, QTimer  # type: ignore[import-not-found]
from PySide6.QtGui import QTextCursor, QColor, QFont, QAction  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser,
    QGroupBox, QComboBox, QSplitter, QFrame
)

from mmst.core.console_logger import ConsoleLogger
from mmst.core.log_analyzer import LogAnalyzer, LogEntry
from .console_widget import ConsoleWidget

# Try to import visualization components
try:
    from mmst.core.log_visualization import (
        LogTimelineChart,
        LogLevelDistributionChart,
        LogComponentBarChart,
        LogErrorRateChart,
        LogHeatmapChart
    )
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False


class LogVisualizationTab(QWidget):
    """Tab for visualizing log data with charts."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the visualization tab."""
        super().__init__(parent)
        
        # Get the ConsoleLogger instance
        self._logger = ConsoleLogger.get_instance()
        self._app_logger = self._logger.get_logger("MMST.LogVisualization")
        
        # Initialize log analyzer
        self._analyzer = LogAnalyzer()
        
        # Initialize charts
        self._timeline_chart = None
        self._level_dist_chart = None
        self._component_chart = None
        self._error_rate_chart = None
        self._heatmap_chart = None
        
        # Initialize timer
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_visualizations)
        
        # Set up UI
        self._setup_ui()
        
        # Set up timer for auto-refresh
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_visualizations)
        
        # Initial refresh
        self._refresh_visualizations()
    
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        if not VISUALIZATION_AVAILABLE:
            # Show message if visualization is not available
            label = QLabel("Log visualization components are not available.")
            label.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
            layout.addWidget(label)
            return
        
        # Add control bar
        control_layout = QHBoxLayout()
        
        refresh_button = QPushButton("Refresh Now")
        refresh_button.clicked.connect(self._refresh_visualizations)
        control_layout.addWidget(refresh_button)
        
        refresh_label = QLabel("Auto-refresh:")
        control_layout.addWidget(refresh_label)
        
        self._refresh_combo = QComboBox()
        self._refresh_combo.addItems([
            "Off", 
            "5 seconds", 
            "10 seconds", 
            "30 seconds", 
            "1 minute",
            "5 minutes"
        ])
        self._refresh_combo.setCurrentText("10 seconds")
        self._refresh_combo.currentTextChanged.connect(self._update_refresh_timer)
        control_layout.addWidget(self._refresh_combo)
        
        time_range_label = QLabel("Time range:")
        control_layout.addWidget(time_range_label)
        
        self._time_range_combo = QComboBox()
        self._time_range_combo.addItems([
            "Last hour",
            "Last 6 hours",
            "Last 12 hours",
            "Last day",
            "Last 3 days",
            "Last week"
        ])
        self._time_range_combo.setCurrentText("Last hour")
        self._time_range_combo.currentTextChanged.connect(self._refresh_visualizations)
        control_layout.addWidget(self._time_range_combo)
        
        control_layout.addStretch()
        
        self._status_label = QLabel("Ready")
        control_layout.addWidget(self._status_label)
        
        layout.addLayout(control_layout)
        
        # Create charts
        # Use splitters for resizable sections
        main_splitter = QSplitter(Qt.Vertical)  # type: ignore[attr-defined]
        main_splitter.setChildrenCollapsible(False)
        
        # Top section: Timeline and Level Distribution
        top_splitter = QSplitter(Qt.Horizontal)  # type: ignore[attr-defined]
        top_splitter.setChildrenCollapsible(False)
        
        # Timeline chart
        timeline_frame = QFrame()
        timeline_layout = QVBoxLayout(timeline_frame)
        timeline_layout.setContentsMargins(5, 5, 5, 5)
        self._timeline_chart = LogTimelineChart()
        timeline_layout.addWidget(self._timeline_chart)
        top_splitter.addWidget(timeline_frame)
        
        # Level distribution chart
        level_dist_frame = QFrame()
        level_dist_layout = QVBoxLayout(level_dist_frame)
        level_dist_layout.setContentsMargins(5, 5, 5, 5)
        self._level_dist_chart = LogLevelDistributionChart()
        level_dist_layout.addWidget(self._level_dist_chart)
        top_splitter.addWidget(level_dist_frame)
        
        # Set initial sizes for top section
        top_splitter.setSizes([int(self.width() * 0.6), int(self.width() * 0.4)])
        
        main_splitter.addWidget(top_splitter)
        
        # Middle section: Component Bar Chart
        component_frame = QFrame()
        component_layout = QVBoxLayout(component_frame)
        component_layout.setContentsMargins(5, 5, 5, 5)
        self._component_chart = LogComponentBarChart()
        component_layout.addWidget(self._component_chart)
        
        main_splitter.addWidget(component_frame)
        
        # Bottom section: Error Rate and Heatmap
        bottom_splitter = QSplitter(Qt.Horizontal)  # type: ignore[attr-defined]
        bottom_splitter.setChildrenCollapsible(False)
        
        # Error rate chart
        error_rate_frame = QFrame()
        error_rate_layout = QVBoxLayout(error_rate_frame)
        error_rate_layout.setContentsMargins(5, 5, 5, 5)
        self._error_rate_chart = LogErrorRateChart()
        error_rate_layout.addWidget(self._error_rate_chart)
        bottom_splitter.addWidget(error_rate_frame)
        
        # Heatmap chart
        heatmap_frame = QFrame()
        heatmap_layout = QVBoxLayout(heatmap_frame)
        heatmap_layout.setContentsMargins(5, 5, 5, 5)
        self._heatmap_chart = LogHeatmapChart()
        heatmap_layout.addWidget(self._heatmap_chart)
        bottom_splitter.addWidget(heatmap_frame)
        
        # Set initial sizes for bottom section
        bottom_splitter.setSizes([int(self.width() * 0.5), int(self.width() * 0.5)])
        
        main_splitter.addWidget(bottom_splitter)
        
        # Set initial sizes for main splitter
        main_splitter.setSizes([
            int(self.height() * 0.35),
            int(self.height() * 0.30),
            int(self.height() * 0.35)
        ])
        
        layout.addWidget(main_splitter)
        
        # Start timer based on selection
        self._update_refresh_timer()
    
    def _update_refresh_timer(self):
        """Update the refresh timer based on the selected interval."""
        # Stop current timer
        self._timer.stop()
        
        # Get selected interval
        interval_text = self._refresh_combo.currentText()
        
        if interval_text == "Off":
            return
        
        # Parse interval
        if interval_text == "5 seconds":
            interval_ms = 5000
        elif interval_text == "10 seconds":
            interval_ms = 10000
        elif interval_text == "30 seconds":
            interval_ms = 30000
        elif interval_text == "1 minute":
            interval_ms = 60000
        elif interval_text == "5 minutes":
            interval_ms = 300000
        else:
            interval_ms = 10000  # Default
        
        # Start timer
        self._timer.start(interval_ms)
    
    def _get_time_range(self) -> Tuple[datetime, datetime]:
        """Get the selected time range.
        
        Returns:
            Tuple containing start and end datetime
        """
        now = datetime.now()
        range_text = self._time_range_combo.currentText()
        
        if range_text == "Last hour":
            return (now - timedelta(hours=1), now)
        elif range_text == "Last 6 hours":
            return (now - timedelta(hours=6), now)
        elif range_text == "Last 12 hours":
            return (now - timedelta(hours=12), now)
        elif range_text == "Last day":
            return (now - timedelta(days=1), now)
        elif range_text == "Last 3 days":
            return (now - timedelta(days=3), now)
        elif range_text == "Last week":
            return (now - timedelta(days=7), now)
        else:
            return (now - timedelta(hours=1), now)  # Default
    
    def _refresh_visualizations(self):
        """Refresh all visualizations with current log data."""
        if not VISUALIZATION_AVAILABLE:
            return
            
        self._status_label.setText("Analyzing logs...")
        
        # Get time range
        start_time, end_time = self._get_time_range()
        
        # Get logs and parse
        logs = self._logger.get_buffer()
        log_text = "\n".join(logs)
        entries = self._analyzer.parse_logs(log_text)
        
        # Filter entries by time range
        entries = [entry for entry in entries 
                  if start_time <= entry.timestamp <= end_time]
        
        if not entries:
            self._status_label.setText("No log entries in selected time range")
            
            # Update charts with empty data
            if self._timeline_chart:
                self._timeline_chart.set_data({})
            if self._level_dist_chart:
                self._level_dist_chart.set_data({})
            if self._component_chart:
                self._component_chart.set_data({})
            if self._error_rate_chart:
                self._error_rate_chart.set_data({})
            if self._heatmap_chart:
                self._heatmap_chart.set_data([])
            
            return
        
        # Prepare data for timeline chart
        level_timestamps: Dict[str, List[datetime]] = {}
        for entry in entries:
            if entry.level not in level_timestamps:
                level_timestamps[entry.level] = []
            level_timestamps[entry.level].append(entry.timestamp)
        
        # Prepare data for level distribution chart
        level_counts = self._analyzer.count_by_level()
        
        # Prepare data for component chart
        component_counts = self._analyzer.count_by_component()
        
        # Prepare data for error rate chart
        # Use the selected time range interval
        range_text = self._time_range_combo.currentText()
        if "hour" in range_text.lower():
            interval_minutes = 5
        elif "day" in range_text.lower():
            interval_minutes = 30
        else:
            interval_minutes = 60
            
        error_rates = self._analyzer.get_error_rate(interval_minutes)
        
        # Prepare data for heatmap
        all_timestamps = [entry.timestamp for entry in entries]
        
        # Update charts
        if self._timeline_chart:
            self._timeline_chart.set_data(level_timestamps, (start_time, end_time))
        if self._level_dist_chart:
            self._level_dist_chart.set_data(level_counts)
        if self._component_chart:
            self._component_chart.set_data(component_counts)
        if self._error_rate_chart:
            self._error_rate_chart.set_data(error_rates)
        if self._heatmap_chart:
            self._heatmap_chart.set_data(all_timestamps)
        
        # Update status
        self._status_label.setText(
            f"Showing {len(entries)} log entries from "
            f"{start_time.strftime('%Y-%m-%d %H:%M')} to "
            f"{end_time.strftime('%Y-%m-%d %H:%M')}"
        )
    
    def showEvent(self, event):
        """Handle show event to refresh visualizations."""
        super().showEvent(event)
        self._refresh_visualizations()
        
    def hideEvent(self, event):
        """Handle hide event to pause refresh timer."""
        super().hideEvent(event)
        self._timer.stop()


class LogAnalysisWidget(QWidget):
    """Widget for analyzing log entries."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the log analysis widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Get the ConsoleLogger instance
        self._logger = ConsoleLogger.get_instance()
        self._app_logger = self._logger.get_logger("MMST.LogAnalysis")
        
        # Initialize log analyzer
        self._analyzer = LogAnalyzer()
        
        # Set up UI
        self._setup_ui()
        
        # Start timer for auto-refresh
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_analysis)
        self._timer.start(5000)  # Refresh every 5 seconds
        
        # Initial analysis
        self._refresh_analysis()
    
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Create control bar
        control_layout = QHBoxLayout()
        
        refresh_button = QPushButton("Refresh Analysis")
        refresh_button.clicked.connect(self._refresh_analysis)
        control_layout.addWidget(refresh_button)
        
        interval_label = QLabel("Time Interval:")
        control_layout.addWidget(interval_label)
        
        self._interval_combo = QComboBox()
        self._interval_combo.addItems(["1 minute", "5 minutes", "15 minutes", "30 minutes", "60 minutes"])
        self._interval_combo.setCurrentText("5 minutes")
        self._interval_combo.currentTextChanged.connect(self._refresh_analysis)
        control_layout.addWidget(self._interval_combo)
        
        control_layout.addStretch()
        
        self._status_label = QLabel("Ready")
        control_layout.addWidget(self._status_label)
        
        layout.addLayout(control_layout)
        
        # Create main content area with tabs
        self._tab_widget = QTabWidget()
        
        # Summary tab
        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        
        # Log level statistics
        level_group = QGroupBox("Log Levels")
        level_layout = QVBoxLayout(level_group)
        self._level_table = QTableWidget(0, 2)
        self._level_table.setHorizontalHeaderLabels(["Level", "Count"])
        self._level_table.horizontalHeader().setStretchLastSection(True)
        level_layout.addWidget(self._level_table)
        summary_layout.addWidget(level_group)
        
        # Component statistics
        component_group = QGroupBox("Top Components")
        component_layout = QVBoxLayout(component_group)
        self._component_table = QTableWidget(0, 2)
        self._component_table.setHorizontalHeaderLabels(["Component", "Count"])
        self._component_table.horizontalHeader().setStretchLastSection(True)
        component_layout.addWidget(self._component_table)
        summary_layout.addWidget(component_group)
        
        # Error statistics
        error_group = QGroupBox("Top Error Sources")
        error_layout = QVBoxLayout(error_group)
        self._error_table = QTableWidget(0, 2)
        self._error_table.setHorizontalHeaderLabels(["Component", "Error Count"])
        self._error_table.horizontalHeader().setStretchLastSection(True)
        error_layout.addWidget(self._error_table)
        summary_layout.addWidget(error_group)
        
        self._tab_widget.addTab(summary_tab, "Summary")
        
        # Errors tab
        errors_tab = QWidget()
        errors_layout = QVBoxLayout(errors_tab)
        
        errors_label = QLabel("Recent Errors and Critical Messages:")
        errors_layout.addWidget(errors_label)
        
        self._errors_browser = QTextBrowser()
        self._errors_browser.setOpenLinks(False)
        errors_layout.addWidget(self._errors_browser)
        
        self._tab_widget.addTab(errors_tab, "Errors")
        
        # Patterns tab
        patterns_tab = QWidget()
        patterns_layout = QVBoxLayout(patterns_tab)
        
        patterns_label = QLabel("Common Message Patterns:")
        patterns_layout.addWidget(patterns_label)
        
        self._patterns_table = QTableWidget(0, 2)
        self._patterns_table.setHorizontalHeaderLabels(["Pattern", "Count"])
        self._patterns_table.horizontalHeader().setStretchLastSection(True)
        patterns_layout.addWidget(self._patterns_table)
        
        self._tab_widget.addTab(patterns_tab, "Patterns")
        
        # Add visualization tab if available
        if VISUALIZATION_AVAILABLE:
            visualization_tab = LogVisualizationTab()
            self._tab_widget.addTab(visualization_tab, "Visualization")
        else:
            self._app_logger.warning("Log visualization components not available. Visualization tab will not be shown.")
            
        # Console tab
        console_tab = ConsoleWidget()
        self._tab_widget.addTab(console_tab, "Console")
        
        # Add tabs to layout
        layout.addWidget(self._tab_widget)
    
    def _refresh_analysis(self):
        """Refresh the log analysis."""
        self._status_label.setText("Analyzing logs...")
        
        # Get all log entries
        logs = self._logger.get_buffer()
        log_text = "\n".join(logs)
        
        # Parse logs
        entries = self._analyzer.parse_logs(log_text)
        if not entries:
            self._status_label.setText("No log entries found")
            return
            
        # Update level statistics
        level_counts = self._analyzer.count_by_level()
        self._level_table.setRowCount(len(level_counts))
        for i, (level, count) in enumerate(sorted(level_counts.items())):
            self._level_table.setItem(i, 0, QTableWidgetItem(level))
            self._level_table.setItem(i, 1, QTableWidgetItem(str(count)))
        
        # Update component statistics
        component_counts = self._analyzer.count_by_component()
        top_components = sorted(component_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        self._component_table.setRowCount(len(top_components))
        for i, (component, count) in enumerate(top_components):
            self._component_table.setItem(i, 0, QTableWidgetItem(component))
            self._component_table.setItem(i, 1, QTableWidgetItem(str(count)))
        
        # Update error statistics
        error_components = self._analyzer.get_top_error_components()
        self._error_table.setRowCount(len(error_components))
        for i, (component, count) in enumerate(error_components):
            self._error_table.setItem(i, 0, QTableWidgetItem(component))
            self._error_table.setItem(i, 1, QTableWidgetItem(str(count)))
        
        # Update errors tab
        error_entries = self._analyzer.get_error_entries()
        error_text = "\n\n".join([
            f"<b>{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')} [{entry.level}] {entry.component}:</b><br>{entry.message}"
            for entry in error_entries[-20:]  # Show last 20 errors
        ])
        self._errors_browser.setHtml(error_text)
        
        # Update patterns tab
        patterns = self._analyzer.get_common_patterns()
        self._patterns_table.setRowCount(len(patterns))
        for i, (pattern, count) in enumerate(patterns):
            self._patterns_table.setItem(i, 0, QTableWidgetItem(pattern))
            self._patterns_table.setItem(i, 1, QTableWidgetItem(str(count)))
        
        # Update status
        entry_count = len(entries)
        error_count = len(error_entries)
        self._status_label.setText(f"Analyzed {entry_count} log entries, found {error_count} errors/critical issues")
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the widget.
        
        Args:
            enabled: Whether to enable the widget
        """
        self.setEnabled(enabled)