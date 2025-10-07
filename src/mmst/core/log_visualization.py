from __future__ import annotations

import math
import re
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime, timedelta
from collections import Counter, defaultdict

from PySide6.QtCore import Qt, QPointF, QRectF, QSize  # type: ignore[import-not-found]
from PySide6.QtGui import (  # type: ignore[import-not-found]
    QPainter, QPen, QBrush, QColor, QPainterPath, QLinearGradient,
    QFont, QFontMetrics
)
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QLabel, QFrame, QSizePolicy
)

# Define colors for different log levels
LOG_LEVEL_COLORS = {
    "DEBUG": QColor(100, 100, 255),     # Blue
    "INFO": QColor(0, 180, 0),          # Green
    "WARNING": QColor(255, 180, 0),     # Orange
    "ERROR": QColor(255, 0, 0),         # Red
    "CRITICAL": QColor(180, 0, 180)     # Purple
}

# Time intervals for grouping log entries
TIME_INTERVALS = {
    "1 minute": 60,
    "5 minutes": 300,
    "15 minutes": 900,
    "30 minutes": 1800,
    "1 hour": 3600,
    "6 hours": 21600,
    "12 hours": 43200,
    "1 day": 86400
}


class LogTimelineChart(QWidget):
    """Widget that displays a timeline chart of log entries."""
    
    def __init__(
        self, 
        parent: Optional[QWidget] = None,
        minimum_height: int = 100
    ):
        """Initialize the log timeline chart.
        
        Args:
            parent: Parent widget
            minimum_height: Minimum height of the chart
        """
        super().__init__(parent)
        
        # Set minimum size
        self.setMinimumHeight(minimum_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Initialize data
        self._timestamps_by_level: Dict[str, List[datetime]] = {}
        self._time_range: Tuple[datetime, datetime] = (
            datetime.now() - timedelta(hours=1),
            datetime.now()
        )
        
        # Initialize UI
        self.setToolTip("Log entries over time")
        
    def set_data(
        self, 
        timestamps_by_level: Dict[str, List[datetime]],
        time_range: Optional[Tuple[datetime, datetime]] = None
    ) -> None:
        """Set the data to display.
        
        Args:
            timestamps_by_level: Dictionary mapping log levels to lists of timestamps
            time_range: Optional time range to display (start, end)
        """
        self._timestamps_by_level = timestamps_by_level
        
        if time_range:
            self._time_range = time_range
        elif timestamps_by_level:
            # Calculate time range from data
            all_timestamps = []
            for timestamps in timestamps_by_level.values():
                all_timestamps.extend(timestamps)
            
            if all_timestamps:
                start_time = min(all_timestamps)
                end_time = max(all_timestamps)
                # Add a small buffer
                buffer = (end_time - start_time) * 0.05
                start_time -= buffer
                end_time += buffer
                self._time_range = (start_time, end_time)
        
        self.update()
    
    def paintEvent(self, event):
        """Paint the timeline chart."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get widget dimensions
        width = self.width()
        height = self.height()
        
        # Draw background
        painter.fillRect(0, 0, width, height, QColor(245, 245, 245))
        
        # Draw border
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawRect(0, 0, width - 1, height - 1)
        
        if not self._timestamps_by_level:
            # Draw message if no data
            painter.setPen(QColor(150, 150, 150))
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(
                0, 0, width, height, 
                Qt.AlignCenter,  # type: ignore[attr-defined]
                "No log data available"
            )
            return
        
        # Calculate metrics
        margin = 40
        chart_width = width - 2 * margin
        chart_height = height - 2 * margin
        
        # Draw time axis
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        y_axis = height - margin
        painter.drawLine(margin, y_axis, width - margin, y_axis)
        
        # Draw time labels and tick marks
        start_time, end_time = self._time_range
        time_span = (end_time - start_time).total_seconds()
        
        # Determine appropriate tick interval based on time span
        if time_span <= 60:  # 1 minute
            tick_interval = 10  # seconds
            format_str = "%H:%M:%S"
        elif time_span <= 3600:  # 1 hour
            tick_interval = 60  # 1 minute
            format_str = "%H:%M"
        elif time_span <= 86400:  # 1 day
            tick_interval = 3600  # 1 hour
            format_str = "%H:%M"
        else:
            tick_interval = 86400  # 1 day
            format_str = "%m-%d"
        
        # Calculate number of ticks
        num_ticks = min(10, max(4, int(time_span / tick_interval)))
        tick_interval = time_span / num_ticks
        
        for i in range(num_ticks + 1):
            time_offset = i * tick_interval
            timestamp = start_time + timedelta(seconds=time_offset)
            
            # Calculate x position
            x = margin + (time_offset / time_span) * chart_width
            
            # Draw tick mark
            painter.drawLine(x, y_axis, x, y_axis + 5)
            
            # Draw time label
            label = timestamp.strftime(format_str)
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            
            # Calculate label width
            font_metrics = QFontMetrics(font)
            label_width = font_metrics.horizontalAdvance(label)
            
            painter.drawText(
                x - label_width / 2, 
                y_axis + 20, 
                label
            )
        
        # Draw level axis
        painter.drawLine(margin, margin, margin, height - margin)
        
        # Sort log levels in standard order
        log_levels = sorted(
            self._timestamps_by_level.keys(),
            key=lambda x: ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].index(x)
                if x in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] else 999
        )
        
        level_height = chart_height / len(log_levels)
        
        # Draw level labels
        for i, level in enumerate(log_levels):
            y = margin + i * level_height + level_height / 2
            
            # Draw level label
            painter.setPen(LOG_LEVEL_COLORS.get(level, QColor(0, 0, 0)))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(5, y + 4, level)
            
            # Draw line for this level
            painter.setPen(QPen(QColor(230, 230, 230), 1, Qt.DashLine))  # type: ignore[attr-defined]
            painter.drawLine(margin, y, width - margin, y)
        
        # Draw data points for each level
        for i, level in enumerate(log_levels):
            timestamps = self._timestamps_by_level[level]
            y_base = margin + i * level_height + level_height / 2
            
            if not timestamps:
                continue
                
            # Set pen color for this level
            color = LOG_LEVEL_COLORS.get(level, QColor(0, 0, 0))
            painter.setPen(QPen(color, 2))
            painter.setBrush(QBrush(color.lighter(150)))
            
            # Draw markers for each timestamp
            for timestamp in timestamps:
                # Convert timestamp to x position
                seconds_from_start = (timestamp - start_time).total_seconds()
                if seconds_from_start < 0 or seconds_from_start > time_span:
                    continue
                    
                x = margin + (seconds_from_start / time_span) * chart_width
                
                # Draw circle marker
                painter.drawEllipse(QPointF(x, y_base), 3, 3)
        
        # Draw title
        painter.setPen(QColor(60, 60, 60))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            margin, 
            10, 
            chart_width, 
            30, 
            Qt.AlignCenter,  # type: ignore[attr-defined]
            "Log Entries Timeline"
        )


class LogLevelDistributionChart(QWidget):
    """Widget that displays a distribution chart of log levels."""
    
    def __init__(
        self, 
        parent: Optional[QWidget] = None,
        minimum_height: int = 150
    ):
        """Initialize the log level distribution chart.
        
        Args:
            parent: Parent widget
            minimum_height: Minimum height of the chart
        """
        super().__init__(parent)
        
        # Set minimum size
        self.setMinimumHeight(minimum_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Initialize data
        self._level_counts: Dict[str, int] = {}
        
        # Initialize UI
        self.setToolTip("Distribution of log entries by level")
        
    def set_data(self, level_counts: Dict[str, int]) -> None:
        """Set the data to display.
        
        Args:
            level_counts: Dictionary mapping log levels to counts
        """
        self._level_counts = level_counts
        self.update()
    
    def paintEvent(self, event):
        """Paint the distribution chart."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get widget dimensions
        width = self.width()
        height = self.height()
        
        # Draw background
        painter.fillRect(0, 0, width, height, QColor(245, 245, 245))
        
        # Draw border
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawRect(0, 0, width - 1, height - 1)
        
        if not self._level_counts:
            # Draw message if no data
            painter.setPen(QColor(150, 150, 150))
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(
                0, 0, width, height, 
                Qt.AlignCenter,  # type: ignore[attr-defined]
                "No log data available"
            )
            return
        
        # Calculate metrics
        margin = 40
        chart_width = width - 2 * margin
        chart_height = height - 2 * margin
        
        # Sort log levels in standard order
        log_levels = sorted(
            self._level_counts.keys(),
            key=lambda x: ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].index(x)
                if x in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] else 999
        )
        
        # Calculate total count
        total_count = sum(self._level_counts.values())
        
        # Calculate bar metrics
        bar_width = chart_width / len(log_levels)
        bar_margin = bar_width * 0.2
        actual_bar_width = bar_width - 2 * bar_margin
        
        # Draw bars
        for i, level in enumerate(log_levels):
            count = self._level_counts[level]
            percentage = count / total_count if total_count > 0 else 0
            
            # Calculate bar height
            bar_height = percentage * chart_height
            
            # Calculate bar position
            x = margin + i * bar_width + bar_margin
            y = height - margin - bar_height
            
            # Get color for this level
            color = LOG_LEVEL_COLORS.get(level, QColor(0, 0, 0))
            
            # Create gradient for bar
            gradient = QLinearGradient(
                x, y,
                x, y + bar_height
            )
            gradient.setColorAt(0, color.lighter(130))
            gradient.setColorAt(1, color)
            
            # Draw bar
            painter.setPen(QPen(color.darker(110), 1))
            painter.setBrush(QBrush(gradient))
            painter.drawRect(x, y, actual_bar_width, bar_height)
            
            # Draw level label
            painter.setPen(QColor(60, 60, 60))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            
            # Calculate label width
            font_metrics = QFontMetrics(font)
            label_width = font_metrics.horizontalAdvance(level)
            
            painter.drawText(
                x + actual_bar_width / 2 - label_width / 2, 
                height - margin + 15, 
                level
            )
            
            # Draw count label
            count_label = f"{count} ({percentage:.1%})"
            label_width = font_metrics.horizontalAdvance(count_label)
            
            painter.drawText(
                x + actual_bar_width / 2 - label_width / 2, 
                y - 5, 
                count_label
            )
        
        # Draw title
        painter.setPen(QColor(60, 60, 60))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            margin, 
            10, 
            chart_width, 
            30, 
            Qt.AlignCenter,  # type: ignore[attr-defined]
            "Log Level Distribution"
        )


class LogComponentBarChart(QWidget):
    """Widget that displays a bar chart of log entries by component."""
    
    def __init__(
        self, 
        parent: Optional[QWidget] = None,
        minimum_height: int = 200
    ):
        """Initialize the log component bar chart.
        
        Args:
            parent: Parent widget
            minimum_height: Minimum height of the chart
        """
        super().__init__(parent)
        
        # Set minimum size
        self.setMinimumHeight(minimum_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Initialize data
        self._component_counts: Dict[str, int] = {}
        self._max_components = 10
        
        # Initialize UI
        self.setToolTip("Log entries by component")
        
    def set_data(
        self, 
        component_counts: Dict[str, int],
        max_components: int = 10
    ) -> None:
        """Set the data to display.
        
        Args:
            component_counts: Dictionary mapping components to counts
            max_components: Maximum number of components to display
        """
        self._component_counts = component_counts
        self._max_components = max_components
        self.update()
    
    def paintEvent(self, event):
        """Paint the bar chart."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get widget dimensions
        width = self.width()
        height = self.height()
        
        # Draw background
        painter.fillRect(0, 0, width, height, QColor(245, 245, 245))
        
        # Draw border
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawRect(0, 0, width - 1, height - 1)
        
        if not self._component_counts:
            # Draw message if no data
            painter.setPen(QColor(150, 150, 150))
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(
                0, 0, width, height, 
                Qt.AlignCenter,  # type: ignore[attr-defined]
                "No log data available"
            )
            return
        
        # Calculate metrics
        left_margin = 150
        right_margin = 60
        top_margin = 40
        bottom_margin = 40
        chart_width = width - left_margin - right_margin
        chart_height = height - top_margin - bottom_margin
        
        # Sort components by count (descending)
        components = sorted(
            self._component_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:self._max_components]
        
        # Calculate bar metrics
        bar_height = chart_height / len(components)
        bar_margin = bar_height * 0.2
        actual_bar_height = bar_height - 2 * bar_margin
        
        # Get maximum count for scaling
        max_count = max([count for _, count in components]) if components else 1
        
        # Draw axis
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawLine(
            left_margin, top_margin,
            left_margin, height - bottom_margin
        )
        painter.drawLine(
            left_margin, height - bottom_margin,
            width - right_margin, height - bottom_margin
        )
        
        # Draw count ticks
        num_ticks = 5
        for i in range(num_ticks + 1):
            count = i * max_count / num_ticks
            x = left_margin + (count / max_count) * chart_width
            
            # Draw tick mark
            painter.drawLine(x, height - bottom_margin, x, height - bottom_margin + 5)
            
            # Draw count label
            count_label = str(int(count))
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            
            # Calculate label width
            font_metrics = QFontMetrics(font)
            label_width = font_metrics.horizontalAdvance(count_label)
            
            painter.drawText(
                x - label_width / 2, 
                height - bottom_margin + 20, 
                count_label
            )
        
        # Draw bars
        for i, (component, count) in enumerate(components):
            # Calculate bar width
            bar_width = (count / max_count) * chart_width
            
            # Calculate bar position
            x = left_margin
            y = top_margin + i * bar_height + bar_margin
            
            # Create gradient for bar
            gradient = QLinearGradient(
                x, y,
                x + bar_width, y
            )
            gradient.setColorAt(0, QColor(70, 130, 180))
            gradient.setColorAt(1, QColor(30, 90, 150))
            
            # Draw bar
            painter.setPen(QPen(QColor(50, 100, 150), 1))
            painter.setBrush(QBrush(gradient))
            painter.drawRect(x, y, bar_width, actual_bar_height)
            
            # Draw component label
            painter.setPen(QColor(60, 60, 60))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            
            # Truncate component name if too long
            truncated = component
            font_metrics = QFontMetrics(font)
            max_width = left_margin - 10
            
            if font_metrics.horizontalAdvance(truncated) > max_width:
                truncated = font_metrics.elidedText(
                    truncated,
                    Qt.TextElideMode.ElideRight,  # type: ignore[attr-defined]
                    max_width
                )
            
            painter.drawText(
                5, 
                y + actual_bar_height / 2 + 4, 
                truncated
            )
            
            # Draw count label
            count_label = str(count)
            painter.setPen(QColor(255, 255, 255))
            font.setBold(True)
            painter.setFont(font)
            
            # Draw label inside bar if there's room
            label_width = font_metrics.horizontalAdvance(count_label)
            label_height = font_metrics.height()
            
            if bar_width > label_width + 10:
                painter.drawText(
                    x + 5,
                    y + actual_bar_height / 2 + label_height / 2 - 1,
                    count_label
                )
            else:
                # Draw outside bar if too small
                painter.setPen(QColor(60, 60, 60))
                painter.drawText(
                    x + bar_width + 5,
                    y + actual_bar_height / 2 + label_height / 2 - 1,
                    count_label
                )
        
        # Draw title
        painter.setPen(QColor(60, 60, 60))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            left_margin, 
            10, 
            chart_width, 
            30, 
            Qt.AlignCenter,  # type: ignore[attr-defined]
            "Top Components by Log Volume"
        )


class LogErrorRateChart(QWidget):
    """Widget that displays a line chart of error rates over time."""
    
    def __init__(
        self, 
        parent: Optional[QWidget] = None,
        minimum_height: int = 150
    ):
        """Initialize the error rate chart.
        
        Args:
            parent: Parent widget
            minimum_height: Minimum height of the chart
        """
        super().__init__(parent)
        
        # Set minimum size
        self.setMinimumHeight(minimum_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Initialize data
        self._error_rates: Dict[datetime, float] = {}
        
        # Initialize UI
        self.setToolTip("Error rate over time")
        
    def set_data(
        self, 
        error_rates: Dict[datetime, float]
    ) -> None:
        """Set the data to display.
        
        Args:
            error_rates: Dictionary mapping timestamps to error rates
        """
        self._error_rates = error_rates
        self.update()
    
    def paintEvent(self, event):
        """Paint the error rate chart."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get widget dimensions
        width = self.width()
        height = self.height()
        
        # Draw background
        painter.fillRect(0, 0, width, height, QColor(245, 245, 245))
        
        # Draw border
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawRect(0, 0, width - 1, height - 1)
        
        if not self._error_rates:
            # Draw message if no data
            painter.setPen(QColor(150, 150, 150))
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(
                0, 0, width, height, 
                Qt.AlignCenter,  # type: ignore[attr-defined]
                "No error rate data available"
            )
            return
        
        # Calculate metrics
        margin = 40
        chart_width = width - 2 * margin
        chart_height = height - 2 * margin
        
        # Sort timestamps
        data_points = sorted(self._error_rates.items())
        
        # Get time range
        start_time = data_points[0][0]
        end_time = data_points[-1][0]
        time_span = (end_time - start_time).total_seconds()
        
        if time_span == 0:
            # Avoid division by zero
            time_span = 1
        
        # Draw time axis
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        y_axis = height - margin
        painter.drawLine(margin, y_axis, width - margin, y_axis)
        
        # Draw time labels and tick marks
        # Determine appropriate tick interval based on time span
        if time_span <= 60:  # 1 minute
            tick_interval = 10  # seconds
            format_str = "%H:%M:%S"
        elif time_span <= 3600:  # 1 hour
            tick_interval = 60  # 1 minute
            format_str = "%H:%M"
        elif time_span <= 86400:  # 1 day
            tick_interval = 3600  # 1 hour
            format_str = "%H:%M"
        else:
            tick_interval = 86400  # 1 day
            format_str = "%m-%d"
        
        # Calculate number of ticks
        num_ticks = min(10, max(4, int(time_span / tick_interval)))
        tick_interval = time_span / num_ticks
        
        for i in range(num_ticks + 1):
            time_offset = i * tick_interval
            timestamp = start_time + timedelta(seconds=time_offset)
            
            # Calculate x position
            x = margin + (time_offset / time_span) * chart_width
            
            # Draw tick mark
            painter.drawLine(x, y_axis, x, y_axis + 5)
            
            # Draw time label
            label = timestamp.strftime(format_str)
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            
            # Calculate label width
            font_metrics = QFontMetrics(font)
            label_width = font_metrics.horizontalAdvance(label)
            
            painter.drawText(
                x - label_width / 2, 
                y_axis + 20, 
                label
            )
        
        # Draw rate axis
        painter.drawLine(margin, margin, margin, height - margin)
        
        # Draw rate labels and tick marks
        max_rate = max(self._error_rates.values())
        if max_rate == 0:
            max_rate = 0.01  # Avoid division by zero
        
        # Round up to nearest 0.1
        max_rate = math.ceil(max_rate * 10) / 10
        
        num_ticks = 5
        for i in range(num_ticks + 1):
            rate = i * max_rate / num_ticks
            
            # Calculate y position
            y = height - margin - (rate / max_rate) * chart_height
            
            # Draw tick mark
            painter.drawLine(margin - 5, y, margin, y)
            
            # Draw rate label
            label = f"{rate:.1%}"
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            
            # Calculate label width
            font_metrics = QFontMetrics(font)
            label_width = font_metrics.horizontalAdvance(label)
            
            painter.drawText(
                margin - 10 - label_width, 
                y + 4, 
                label
            )
        
        # Draw grid lines
        painter.setPen(QPen(QColor(220, 220, 220), 1, Qt.DashLine))  # type: ignore[attr-defined]
        for i in range(1, num_ticks + 1):
            rate = i * max_rate / num_ticks
            y = height - margin - (rate / max_rate) * chart_height
            painter.drawLine(margin, y, width - margin, y)
        
        # Draw data points and line
        if data_points:
            # Create path for line
            path = QPainterPath()
            
            # Create path for filled area
            fill_path = QPainterPath()
            
            # Start at the first point
            timestamp, rate = data_points[0]
            seconds_from_start = (timestamp - start_time).total_seconds()
            x = margin + (seconds_from_start / time_span) * chart_width
            y = height - margin - (rate / max_rate) * chart_height
            
            path.moveTo(x, y)
            fill_path.moveTo(x, height - margin)
            fill_path.lineTo(x, y)
            
            # Add remaining points
            for timestamp, rate in data_points[1:]:
                seconds_from_start = (timestamp - start_time).total_seconds()
                x = margin + (seconds_from_start / time_span) * chart_width
                y = height - margin - (rate / max_rate) * chart_height
                
                path.lineTo(x, y)
                fill_path.lineTo(x, y)
            
            # Close fill path
            timestamp, _ = data_points[-1]
            seconds_from_start = (timestamp - start_time).total_seconds()
            x = margin + (seconds_from_start / time_span) * chart_width
            fill_path.lineTo(x, height - margin)
            fill_path.closeSubpath()
            
            # Draw filled area
            gradient = QLinearGradient(
                0, margin,
                0, height - margin
            )
            gradient.setColorAt(0, QColor(255, 0, 0, 100))
            gradient.setColorAt(1, QColor(255, 0, 0, 10))
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)  # type: ignore[attr-defined]
            painter.drawPath(fill_path)
            
            # Draw line
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.setBrush(Qt.NoBrush)  # type: ignore[attr-defined]
            painter.drawPath(path)
            
            # Draw data points
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            
            for timestamp, rate in data_points:
                seconds_from_start = (timestamp - start_time).total_seconds()
                x = margin + (seconds_from_start / time_span) * chart_width
                y = height - margin - (rate / max_rate) * chart_height
                
                painter.drawEllipse(QPointF(x, y), 4, 4)
        
        # Draw title
        painter.setPen(QColor(60, 60, 60))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            margin, 
            10, 
            chart_width, 
            30, 
            Qt.AlignCenter,  # type: ignore[attr-defined]
            "Error Rate Over Time"
        )


class LogHeatmapChart(QWidget):
    """Widget that displays a heatmap of log activity."""
    
    def __init__(
        self, 
        parent: Optional[QWidget] = None,
        minimum_height: int = 200
    ):
        """Initialize the heatmap chart.
        
        Args:
            parent: Parent widget
            minimum_height: Minimum height of the chart
        """
        super().__init__(parent)
        
        # Set minimum size
        self.setMinimumHeight(minimum_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Initialize data
        self._hour_counts: Dict[Tuple[int, int], int] = {}  # (hour, day) -> count
        self._max_count = 0
        
        # Initialize UI
        self.setToolTip("Log activity heatmap")
        
    def set_data(
        self, 
        timestamps: List[datetime],
        days_to_show: int = 7
    ) -> None:
        """Set the data to display.
        
        Args:
            timestamps: List of log timestamps
            days_to_show: Number of days to show in the heatmap
        """
        # Group timestamps by hour and day
        hour_counts: Dict[Tuple[int, int], int] = {}
        
        # Get current date
        today = datetime.now().date()
        
        # Initialize all hours with zero
        for day in range(days_to_show):
            for hour in range(24):
                hour_counts[(hour, day)] = 0
        
        # Count logs by hour and day
        for timestamp in timestamps:
            days_ago = (today - timestamp.date()).days
            if 0 <= days_ago < days_to_show:
                hour = timestamp.hour
                hour_counts[(hour, days_ago)] = hour_counts.get((hour, days_ago), 0) + 1
        
        self._hour_counts = hour_counts
        self._max_count = max(hour_counts.values()) if hour_counts else 1
        
        self.update()
    
    def paintEvent(self, event):
        """Paint the heatmap chart."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get widget dimensions
        width = self.width()
        height = self.height()
        
        # Draw background
        painter.fillRect(0, 0, width, height, QColor(245, 245, 245))
        
        # Draw border
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawRect(0, 0, width - 1, height - 1)
        
        if not self._hour_counts:
            # Draw message if no data
            painter.setPen(QColor(150, 150, 150))
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(
                0, 0, width, height, 
                Qt.AlignCenter,  # type: ignore[attr-defined]
                "No log data available for heatmap"
            )
            return
        
        # Calculate metrics
        left_margin = 40
        right_margin = 20
        top_margin = 40
        bottom_margin = 40
        
        chart_width = width - left_margin - right_margin
        chart_height = height - top_margin - bottom_margin
        
        # Calculate cell dimensions
        days = len(set(day for _, day in self._hour_counts.keys()))
        hours = 24  # Always 24 hours
        
        cell_width = chart_width / days if days > 0 else chart_width
        cell_height = chart_height / hours if hours > 0 else chart_height
        
        # Draw day labels
        painter.setPen(QColor(100, 100, 100))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        
        today = datetime.now().date()
        for day in range(days):
            x = left_margin + day * cell_width + cell_width / 2
            y = height - bottom_margin + 15
            
            day_date = today - timedelta(days=day)
            day_label = day_date.strftime("%a %d")
            
            # Calculate label width
            font_metrics = QFontMetrics(font)
            label_width = font_metrics.horizontalAdvance(day_label)
            
            painter.drawText(
                x - label_width / 2, 
                y, 
                day_label
            )
        
        # Draw hour labels
        for hour in range(0, 24, 2):  # Show every other hour
            x = left_margin - 5
            y = top_margin + hour * cell_height + cell_height / 2
            
            hour_label = f"{hour:02d}:00"
            
            # Calculate label width
            font_metrics = QFontMetrics(font)
            label_width = font_metrics.horizontalAdvance(hour_label)
            
            painter.drawText(
                x - label_width, 
                y + 4, 
                hour_label
            )
        
        # Draw heatmap cells
        for (hour, day), count in self._hour_counts.items():
            # Calculate intensity (0-1)
            intensity = count / self._max_count if self._max_count > 0 else 0
            
            # Calculate color
            # Use a gradient from light blue (low) to dark blue (high)
            r = int(220 - 170 * intensity)
            g = int(240 - 140 * intensity)
            b = int(255 - 50 * intensity)
            color = QColor(r, g, b)
            
            # Calculate cell position
            x = left_margin + day * cell_width
            y = top_margin + hour * cell_height
            
            # Draw cell
            painter.setPen(QPen(QColor(200, 200, 200), 1))
            painter.setBrush(QBrush(color))
            painter.drawRect(x, y, cell_width, cell_height)
            
            # Draw count if significant
            if count > 0 and cell_width >= 30 and cell_height >= 15:
                painter.setPen(QColor(60, 60, 60))
                font = painter.font()
                font.setPointSize(7)
                painter.setFont(font)
                
                count_label = str(count)
                
                # Calculate label dimensions
                font_metrics = QFontMetrics(font)
                label_width = font_metrics.horizontalAdvance(count_label)
                
                painter.drawText(
                    x + cell_width / 2 - label_width / 2, 
                    y + cell_height / 2 + 3, 
                    count_label
                )
        
        # Draw title
        painter.setPen(QColor(60, 60, 60))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            left_margin, 
            10, 
            chart_width, 
            30, 
            Qt.AlignCenter,  # type: ignore[attr-defined]
            "Log Activity Heatmap (by Hour/Day)"
        )


class LogVisualizationPanel(QWidget):
    """Panel that displays multiple log visualization charts."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the log visualization panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Set up layout
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Add control bar
        control_layout = QHBoxLayout()
        
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
        control_layout.addWidget(self._time_range_combo)
        
        control_layout.addStretch()
        
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
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        self._timeline_chart = LogTimelineChart()
        timeline_layout.addWidget(self._timeline_chart)
        top_splitter.addWidget(timeline_frame)
        
        # Level distribution chart
        level_dist_frame = QFrame()
        level_dist_layout = QVBoxLayout(level_dist_frame)
        level_dist_layout.setContentsMargins(0, 0, 0, 0)
        self._level_dist_chart = LogLevelDistributionChart()
        level_dist_layout.addWidget(self._level_dist_chart)
        top_splitter.addWidget(level_dist_frame)
        
        # Set initial sizes for top section
        top_splitter.setSizes([int(self.width() * 0.6), int(self.width() * 0.4)])
        
        main_splitter.addWidget(top_splitter)
        
        # Middle section: Component Bar Chart
        component_frame = QFrame()
        component_layout = QVBoxLayout(component_frame)
        component_layout.setContentsMargins(0, 0, 0, 0)
        self._component_chart = LogComponentBarChart()
        component_layout.addWidget(self._component_chart)
        
        main_splitter.addWidget(component_frame)
        
        # Bottom section: Error Rate and Heatmap
        bottom_splitter = QSplitter(Qt.Horizontal)  # type: ignore[attr-defined]
        bottom_splitter.setChildrenCollapsible(False)
        
        # Error rate chart
        error_rate_frame = QFrame()
        error_rate_layout = QVBoxLayout(error_rate_frame)
        error_rate_layout.setContentsMargins(0, 0, 0, 0)
        self._error_rate_chart = LogErrorRateChart()
        error_rate_layout.addWidget(self._error_rate_chart)
        bottom_splitter.addWidget(error_rate_frame)
        
        # Heatmap chart
        heatmap_frame = QFrame()
        heatmap_layout = QVBoxLayout(heatmap_frame)
        heatmap_layout.setContentsMargins(0, 0, 0, 0)
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
    
    def set_data(
        self,
        level_timestamps: Dict[str, List[datetime]],
        level_counts: Dict[str, int],
        component_counts: Dict[str, int],
        error_rates: Dict[datetime, float],
        all_timestamps: List[datetime]
    ):
        """Set data for all charts.
        
        Args:
            level_timestamps: Dictionary mapping log levels to timestamp lists
            level_counts: Dictionary mapping log levels to counts
            component_counts: Dictionary mapping components to counts
            error_rates: Dictionary mapping timestamps to error rates
            all_timestamps: List of all timestamps for heatmap
        """
        self._timeline_chart.set_data(level_timestamps)
        self._level_dist_chart.set_data(level_counts)
        self._component_chart.set_data(component_counts)
        self._error_rate_chart.set_data(error_rates)
        self._heatmap_chart.set_data(all_timestamps)