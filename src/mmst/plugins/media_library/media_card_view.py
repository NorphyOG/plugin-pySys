"""Modern card-based view for Media Library inspired by Spotify/Netflix/Photo Galleries.

This module provides:
- MediaCard: Individual card widget with cover art, title, metadata
- CardGridView: Scrollable grid layout for cards
- CardListView: List view with inline preview
- DualView: Combined view with toggle between grid/list/both modes
"""

from __future__ import annotations

from typing import Optional, List, Any, Callable
from pathlib import Path
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QGridLayout, QSizePolicy, QComboBox, QButtonGroup, QRadioButton,
    QStackedWidget, QSplitter
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont


@dataclass
class MediaCardData:
    """Data model for media card display."""
    path: Path
    title: str
    subtitle: str = ""  # Artist/Album for audio, Resolution for video
    kind: str = "unknown"  # audio, video, image
    rating: int = 0  # 0-5 stars
    duration: int = 0  # seconds
    cover_path: Optional[Path] = None
    metadata: Optional[Any] = None  # Full metadata object if needed


class MediaCard(QFrame):
    """Individual media card widget with cover art and metadata.
    
    Visual style inspired by Spotify (audio), Netflix (video), photo galleries (images).
    """
    
    clicked = Signal(object)  # Emits MediaCardData
    
    def __init__(self, data: MediaCardData, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.data = data
        
        # Card styling
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)
        self.setStyleSheet("""
            MediaCard {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
            MediaCard:hover {
                background-color: #2a2a2a;
                border: 1px solid #555555;
            }
        """)
        self.setMinimumSize(180, 240)
        self.setMaximumSize(250, 340)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Cover art section
        self.cover_label = QLabel()
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setMinimumSize(164, 164)
        self.cover_label.setMaximumSize(234, 234)
        self.cover_label.setStyleSheet("background-color: #2a2a2a; border-radius: 4px;")
        self.cover_label.setScaledContents(False)
        
        # Load cover or use placeholder
        self._load_cover()
        
        layout.addWidget(self.cover_label)
        
        # Title label
        self.title_label = QLabel(data.title)
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(40)
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.title_label)
        
        # Subtitle (artist, resolution, etc)
        if data.subtitle:
            self.subtitle_label = QLabel(data.subtitle)
            self.subtitle_label.setWordWrap(True)
            self.subtitle_label.setMaximumHeight(30)
            subtitle_font = QFont()
            subtitle_font.setPointSize(8)
            self.subtitle_label.setFont(subtitle_font)
            self.subtitle_label.setStyleSheet("color: #b3b3b3;")
            layout.addWidget(self.subtitle_label)
        
        # Metadata row (rating, duration, kind)
        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        
        # Rating stars
        if data.rating > 0:
            rating_label = QLabel("★" * data.rating)
            rating_label.setStyleSheet("color: #ffd700; font-size: 12px;")
            meta_row.addWidget(rating_label)
        
        # Duration
        if data.duration > 0 and data.kind in ["audio", "video"]:
            mins = int(data.duration // 60)
            secs = int(data.duration % 60)
            duration_label = QLabel(f"{mins}:{secs:02d}")
            duration_label.setStyleSheet("color: #b3b3b3; font-size: 9px;")
            meta_row.addWidget(duration_label)
        
        meta_row.addStretch(1)
        
        # Kind badge
        kind_badge = QLabel(data.kind.upper())
        kind_badge.setStyleSheet("""
            background-color: #404040;
            color: #ffffff;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 8px;
            font-weight: bold;
        """)
        meta_row.addWidget(kind_badge)
        
        layout.addLayout(meta_row)
        layout.addStretch(1)
    
    def _load_cover(self) -> None:
        """Load cover art or generate placeholder."""
        if self.data.cover_path and self.data.cover_path.exists():
            pixmap = QPixmap(str(self.data.cover_path))
            if not pixmap.isNull():
                # Scale maintaining aspect ratio
                scaled = pixmap.scaled(
                    164, 164,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.cover_label.setPixmap(scaled)
                return
        
        # Generate placeholder
        self._create_placeholder()
    
    def _create_placeholder(self) -> None:
        """Create styled placeholder based on media kind."""
        pixmap = QPixmap(164, 164)
        
        # Color scheme by kind
        colors = {
            "audio": QColor(30, 215, 96),  # Spotify green
            "video": QColor(229, 9, 20),   # Netflix red
            "image": QColor(0, 149, 246),  # Instagram blue
        }
        bg_color = colors.get(self.data.kind, QColor(60, 60, 60))
        
        pixmap.fill(bg_color)
        
        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255, 180))
        
        # Draw icon text
        font = QFont()
        font.setPointSize(48)
        font.setBold(True)
        painter.setFont(font)
        
        icons = {
            "audio": "♪",
            "video": "▶",
            "image": "⊡"
        }
        icon = icons.get(self.data.kind, "?")
        
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, icon)
        painter.end()
        
        self.cover_label.setPixmap(pixmap)
    
    def mousePressEvent(self, event) -> None:
        """Emit clicked signal on mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)


class CardGridView(QScrollArea):
    """Scrollable grid view of media cards (Netflix/Spotify style)."""
    
    card_clicked = Signal(object)  # Emits MediaCardData
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("background-color: #121212;")
        
        # Container widget
        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setContentsMargins(16, 16, 16, 16)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.setWidget(self.container)
        
        self.cards: List[MediaCard] = []
        self._columns = 4  # Responsive: adjust based on width
    
    def set_media_items(self, items: List[MediaCardData]) -> None:
        """Populate grid with media cards."""
        self.clear()
        
        for idx, item in enumerate(items):
            card = MediaCard(item)
            card.clicked.connect(self.card_clicked.emit)
            
            row = idx // self._columns
            col = idx % self._columns
            self.grid_layout.addWidget(card, row, col)
            self.cards.append(card)
    
    def clear(self) -> None:
        """Remove all cards from grid."""
        for card in self.cards:
            card.deleteLater()
        self.cards.clear()
    
    def resizeEvent(self, event) -> None:
        """Adjust columns based on width."""
        super().resizeEvent(event)
        width = self.viewport().width()
        
        # Responsive column calculation
        if width < 600:
            new_cols = 2
        elif width < 900:
            new_cols = 3
        elif width < 1200:
            new_cols = 4
        else:
            new_cols = 5
        
        if new_cols != self._columns:
            self._columns = new_cols
            # Trigger relayout if needed
            # For simplicity, we could rebuild on resize


class CardListView(QScrollArea):
    """List view with inline preview cards (compact mode)."""
    
    card_clicked = Signal(object)  # Emits MediaCardData
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background-color: #121212;")
        
        self.container = QWidget()
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setSpacing(8)
        self.list_layout.setContentsMargins(8, 8, 8, 8)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.setWidget(self.container)
        
        self.cards: List[QWidget] = []
    
    def set_media_items(self, items: List[MediaCardData]) -> None:
        """Populate list with compact cards."""
        self.clear()
        
        for item in items:
            row_widget = self._create_list_row(item)
            self.list_layout.addWidget(row_widget)
            self.cards.append(row_widget)
    
    def _create_list_row(self, data: MediaCardData) -> QWidget:
        """Create horizontal list row widget."""
        row = QFrame()
        row.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        row.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
            }
            QFrame:hover {
                background-color: #2a2a2a;
                border: 1px solid #404040;
            }
        """)
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setMaximumHeight(80)
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # Thumbnail
        thumb = QLabel()
        thumb.setFixedSize(64, 64)
        thumb.setStyleSheet("background-color: #2a2a2a; border-radius: 4px;")
        
        # Load mini cover
        if data.cover_path and data.cover_path.exists():
            pixmap = QPixmap(str(data.cover_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                thumb.setPixmap(scaled)
        
        layout.addWidget(thumb)
        
        # Text info
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        
        title = QLabel(data.title)
        title.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 11px;")
        text_col.addWidget(title)
        
        if data.subtitle:
            subtitle = QLabel(data.subtitle)
            subtitle.setStyleSheet("color: #b3b3b3; font-size: 9px;")
            text_col.addWidget(subtitle)
        
        layout.addLayout(text_col, stretch=1)
        
        # Rating
        if data.rating > 0:
            rating = QLabel("★" * data.rating)
            rating.setStyleSheet("color: #ffd700; font-size: 11px;")
            layout.addWidget(rating)
        
        # Duration
        if data.duration > 0:
            mins = int(data.duration // 60)
            secs = int(data.duration % 60)
            duration = QLabel(f"{mins}:{secs:02d}")
            duration.setStyleSheet("color: #b3b3b3; font-size: 10px;")
            layout.addWidget(duration)
        
        # Kind badge
        kind = QLabel(data.kind.upper())
        kind.setStyleSheet("""
            background-color: #404040;
            color: #ffffff;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 8px;
        """)
        layout.addWidget(kind)
        
        # Store data and connect click
        row.mousePressEvent = lambda event: self._on_row_clicked(data, event)
        
        return row
    
    def _on_row_clicked(self, data: MediaCardData, event) -> None:
        """Handle row click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.card_clicked.emit(data)
    
    def clear(self) -> None:
        """Remove all rows."""
        for card in self.cards:
            card.deleteLater()
        self.cards.clear()


class DualView(QWidget):
    """Combined view with toggle between Grid/List/Both modes."""
    
    card_clicked = Signal(object)  # Emits MediaCardData
    
    MODE_GRID = "grid"
    MODE_LIST = "list"
    MODE_BOTH = "both"
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
        self.current_mode = self.MODE_GRID
        self._media_items: List[MediaCardData] = []
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Control bar
        control_bar = QWidget()
        control_bar.setStyleSheet("background-color: #1e1e1e; padding: 8px;")
        control_layout = QHBoxLayout(control_bar)
        control_layout.setContentsMargins(8, 4, 8, 4)
        
        control_layout.addWidget(QLabel("Ansicht:"))
        
        # View mode buttons
        self.mode_group = QButtonGroup(self)
        
        self.grid_btn = QRadioButton("🔲 Karten")
        self.grid_btn.setChecked(True)
        self.grid_btn.toggled.connect(lambda checked: checked and self._set_mode(self.MODE_GRID))
        self.mode_group.addButton(self.grid_btn)
        control_layout.addWidget(self.grid_btn)
        
        self.list_btn = QRadioButton("📋 Liste")
        self.list_btn.toggled.connect(lambda checked: checked and self._set_mode(self.MODE_LIST))
        self.mode_group.addButton(self.list_btn)
        control_layout.addWidget(self.list_btn)
        
        self.both_btn = QRadioButton("⚌ Beide")
        self.both_btn.toggled.connect(lambda checked: checked and self._set_mode(self.MODE_BOTH))
        self.mode_group.addButton(self.both_btn)
        control_layout.addWidget(self.both_btn)
        
        control_layout.addStretch(1)
        
        # Sort/Filter controls could go here
        control_layout.addWidget(QLabel("Sortieren:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Titel", "Bewertung", "Datum", "Dauer"])
        control_layout.addWidget(self.sort_combo)
        
        layout.addWidget(control_bar)
        
        # View container (stacked or splitter)
        self.view_stack = QStackedWidget()
        
        # Create views
        self.grid_view = CardGridView()
        self.grid_view.card_clicked.connect(self.card_clicked.emit)
        
        self.list_view = CardListView()
        self.list_view.card_clicked.connect(self.card_clicked.emit)
        
        # Splitter for dual mode
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(self.grid_view)
        self.splitter.addWidget(self.list_view)
        self.splitter.setSizes([400, 200])
        
        # Add to stack
        self.view_stack.addWidget(self.grid_view)  # Index 0
        self.view_stack.addWidget(self.list_view)  # Index 1
        self.view_stack.addWidget(self.splitter)   # Index 2
        
        layout.addWidget(self.view_stack, stretch=1)
    
    def _set_mode(self, mode: str) -> None:
        """Switch view mode."""
        self.current_mode = mode
        
        if mode == self.MODE_GRID:
            self.view_stack.setCurrentIndex(0)
        elif mode == self.MODE_LIST:
            self.view_stack.setCurrentIndex(1)
        elif mode == self.MODE_BOTH:
            self.view_stack.setCurrentIndex(2)
    
    def set_media_items(self, items: List[MediaCardData]) -> None:
        """Update all views with media items."""
        self._media_items = items
        
        # Update both views
        self.grid_view.set_media_items(items)
        self.list_view.set_media_items(items)
    
    def clear(self) -> None:
        """Clear all views."""
        self._media_items.clear()
        self.grid_view.clear()
        self.list_view.clear()
