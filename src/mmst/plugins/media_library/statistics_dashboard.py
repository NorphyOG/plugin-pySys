"""Statistics Dashboard for Media Library.

Provides visual overview of library metrics:
- File counts by type (Audio, Video, Image)
- Total storage size
- Rating distribution
- Genre/Artist statistics
- Temporal distribution (added/modified dates)
"""

from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QGridLayout, QGroupBox, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPen


class StatCard(QFrame):
    """Individual statistic card widget."""
    
    def __init__(self, title: str, value: str, subtitle: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            StatCard {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        self.setMinimumSize(180, 100)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        
        # Title
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(9)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #b3b3b3;")
        layout.addWidget(title_label)
        
        # Main value
        value_label = QLabel(value)
        value_font = QFont()
        value_font.setPointSize(24)
        value_font.setBold(True)
        value_label.setFont(value_font)
        value_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(value_label)
        
        # Subtitle (optional)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_font = QFont()
            subtitle_font.setPointSize(8)
            subtitle_label.setFont(subtitle_font)
            subtitle_label.setStyleSheet("color: #808080;")
            layout.addWidget(subtitle_label)
        
        layout.addStretch(1)


class SimpleBarChart(QWidget):
    """Simple horizontal bar chart widget."""
    
    def __init__(self, data: List[Tuple[str, int]], max_bars: int = 10, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.data = data[:max_bars]  # Limit to top N
        self.setMinimumHeight(max(150, len(self.data) * 25))
        self.setStyleSheet("background-color: #2a2a2a; border-radius: 8px;")
    
    def paintEvent(self, event) -> None:
        """Draw horizontal bars."""
        super().paintEvent(event)
        
        if not self.data:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width() - 20
        height = self.height() - 20
        bar_height = min(20, height // len(self.data) - 5)
        
        max_value = max(count for _, count in self.data) if self.data else 1
        
        colors = [
            QColor(30, 215, 96),   # Green
            QColor(229, 9, 20),    # Red
            QColor(0, 149, 246),   # Blue
            QColor(255, 215, 0),   # Gold
            QColor(147, 51, 234),  # Purple
        ]
        
        for i, (label, count) in enumerate(self.data):
            y = 10 + i * (bar_height + 5)
            bar_width = int((count / max_value) * (width - 150)) if max_value > 0 else 0
            
            # Draw label
            painter.setPen(QColor(179, 179, 179))
            font = QFont()
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(10, y + bar_height - 5, label[:20])
            
            # Draw bar
            color = colors[i % len(colors)]
            painter.fillRect(150, y, bar_width, bar_height, color)
            
            # Draw count
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(155 + bar_width, y + bar_height - 5, str(count))
        
        painter.end()


class StatisticsDashboard(QWidget):
    """Main statistics dashboard widget."""
    
    refresh_requested = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
        self._stats: Dict[str, Any] = {}
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("📊 Bibliotheks-Statistik")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        
        refresh_btn = QPushButton("🔄 Aktualisieren")
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background-color: #1e1e1e; border: none;")
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(16)
        
        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)
        
        # Placeholder widgets (will be populated on update)
        self.overview_grid = QGridLayout()
        self.content_layout.addLayout(self.overview_grid)
        
        self.charts_layout = QVBoxLayout()
        self.content_layout.addLayout(self.charts_layout)
        
        self.content_layout.addStretch(1)
    
    def update_statistics(self, stats: Dict[str, Any]) -> None:
        """Update dashboard with new statistics."""
        self._stats = stats
        
        # Clear existing widgets
        self._clear_layout(self.overview_grid)
        self._clear_layout(self.charts_layout)
        
        # Overview cards
        row, col = 0, 0
        max_cols = 4
        
        # Total files
        total_files = stats.get('total_files', 0)
        card = StatCard("Gesamt Dateien", f"{total_files:,}")
        self.overview_grid.addWidget(card, row, col)
        col += 1
        
        # Total size
        total_size = stats.get('total_size', 0)
        size_str = self._format_size(total_size)
        card = StatCard("Gesamtgröße", size_str)
        self.overview_grid.addWidget(card, row, col)
        col += 1
        
        # Audio files
        audio_count = stats.get('audio_count', 0)
        card = StatCard("Audio", f"{audio_count:,}", f"{self._percentage(audio_count, total_files)}%")
        self.overview_grid.addWidget(card, row, col)
        col += 1
        
        # Video files
        video_count = stats.get('video_count', 0)
        card = StatCard("Video", f"{video_count:,}", f"{self._percentage(video_count, total_files)}%")
        self.overview_grid.addWidget(card, row, col)
        
        # Second row
        row, col = 1, 0
        
        # Image files
        image_count = stats.get('image_count', 0)
        card = StatCard("Bilder", f"{image_count:,}", f"{self._percentage(image_count, total_files)}%")
        self.overview_grid.addWidget(card, row, col)
        col += 1
        
        # Average rating
        avg_rating = stats.get('avg_rating', 0.0)
        card = StatCard("Ø Bewertung", f"{'★' * int(avg_rating)}", f"{avg_rating:.1f}/5")
        self.overview_grid.addWidget(card, row, col)
        col += 1
        
        # Files added last 7 days
        recent_count = stats.get('added_last_7_days', 0)
        card = StatCard("Letzte 7 Tage", f"{recent_count:,}", "hinzugefügt")
        self.overview_grid.addWidget(card, row, col)
        col += 1
        
        # Files modified last 7 days
        modified_count = stats.get('modified_last_7_days', 0)
        card = StatCard("Letzte 7 Tage", f"{modified_count:,}", "geändert")
        self.overview_grid.addWidget(card, row, col)
        
        # Charts section
        
        # Rating distribution
        if 'rating_distribution' in stats and stats['rating_distribution']:
            group = QGroupBox("Bewertungsverteilung")
            group.setStyleSheet("QGroupBox { color: #ffffff; font-weight: bold; }")
            group_layout = QVBoxLayout(group)
            
            rating_data = [(f"{r} ★" if r > 0 else "Unbewertet", count) 
                          for r, count in sorted(stats['rating_distribution'].items())]
            chart = SimpleBarChart(rating_data, max_bars=6)
            group_layout.addWidget(chart)
            
            self.charts_layout.addWidget(group)
        
        # Top genres
        if 'top_genres' in stats and stats['top_genres']:
            group = QGroupBox("Top Genres")
            group.setStyleSheet("QGroupBox { color: #ffffff; font-weight: bold; }")
            group_layout = QVBoxLayout(group)
            
            chart = SimpleBarChart(stats['top_genres'], max_bars=10)
            group_layout.addWidget(chart)
            
            self.charts_layout.addWidget(group)
        
        # Top artists
        if 'top_artists' in stats and stats['top_artists']:
            group = QGroupBox("Top Artists")
            group.setStyleSheet("QGroupBox { color: #ffffff; font-weight: bold; }")
            group_layout = QVBoxLayout(group)
            
            chart = SimpleBarChart(stats['top_artists'], max_bars=10)
            group_layout.addWidget(chart)
            
            self.charts_layout.addWidget(group)
    
    def _clear_layout(self, layout) -> None:
        """Clear all widgets from layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
    
    def _format_size(self, size_bytes: int) -> str:
        """Format byte size to human-readable string."""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    def _percentage(self, part: int, total: int) -> str:
        """Calculate percentage."""
        if total == 0:
            return "0.0"
        return f"{(part / total * 100):.1f}"
