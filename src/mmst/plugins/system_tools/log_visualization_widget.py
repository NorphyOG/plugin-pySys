from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import sys

from PySide6.QtCore import Qt, Signal, Slot, QTimer  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QComboBox, QPushButton, QFrame
)

# Import the ConsoleLogger and LogAnalyzer
from mmst.core.console_logger import ConsoleLogger
from mmst.core.log_analyzer import LogAnalyzer, LogEntry

# Try to import the visualization components
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


class LogVisualizationWidget(QWidget):
    """Widget for visualizing log data with charts."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the log visualization widget."""
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