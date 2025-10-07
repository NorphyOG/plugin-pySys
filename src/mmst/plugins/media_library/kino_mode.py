"""Kino Mode (Cinema/Theater Mode) for Media Library.

Provides fullscreen viewing experience for videos and images:
- Fullscreen overlay widget
- Auto-hide controls (mouse movement detection)
- Keyboard shortcuts (ESC, Arrow keys, Space, F11)
- Slideshow mode for images (auto-advance)
- Playlist queue navigation
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Callable
from datetime import datetime

try:
    from PySide6.QtCore import Qt, QTimer, Signal, QEvent
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QSlider, QFrame
    )
    from PySide6.QtGui import QPixmap, QKeyEvent, QMouseEvent, QPainter, QColor
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtMultimediaWidgets import QVideoWidget
except ImportError:  # pragma: no cover - fallback for type hints
    QWidget = object  # type: ignore
    Signal = lambda: None  # type: ignore


class KinoModeWidget(QWidget):
    """Fullscreen cinema mode widget for immersive media viewing.
    
    Features:
    - Fullscreen video/image display
    - Auto-hide controls (fade out after 3s of no mouse movement)
    - Keyboard shortcuts:
      - ESC: Exit fullscreen
      - Space: Play/Pause
      - Left/Right: Previous/Next media
      - F11: Toggle fullscreen
      - S: Toggle slideshow (for images)
    - Slideshow mode for images (configurable interval, default 5s)
    - Playlist queue display (current position)
    """
    
    # Signals
    exit_requested = Signal()  # Emitted when user wants to exit Kino Mode
    next_requested = Signal()  # Emitted when user wants next media
    previous_requested = Signal()  # Emitted when user wants previous media
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
        # State
        self._current_path: Optional[Path] = None
        self._current_kind: str = "other"
        self._playlist: List[Path] = []
        self._playlist_index: int = 0
        self._slideshow_active: bool = False
        self._slideshow_interval: int = 5000  # milliseconds
        
        # Media player components
        try:
            self._media_player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._media_player.setAudioOutput(self._audio_output)
            self._video_widget = QVideoWidget(self)
            self._media_player.setVideoOutput(self._video_widget)
            self._player_available = True
        except Exception:
            self._media_player = None  # type: ignore
            self._audio_output = None  # type: ignore
            self._video_widget = None  # type: ignore
            self._player_available = False
        
        # Image display
        self._image_label: Optional[QLabel] = None
        
        # Timers
        self._controls_hide_timer = QTimer(self)
        self._controls_hide_timer.setSingleShot(True)
        self._controls_hide_timer.timeout.connect(self._hide_controls)
        
        self._slideshow_timer = QTimer(self)
        self._slideshow_timer.timeout.connect(self._advance_slideshow)
        
        # Setup UI
        self._setup_ui()
        
        # Enable mouse tracking for auto-hide
        self.setMouseTracking(True)
        
        # Window flags
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    
    def _setup_ui(self) -> None:
        """Setup UI layout with video/image layers and controls."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Content area (video or image)
        self._content_frame = QFrame(self)
        self._content_frame.setStyleSheet("background-color: #000000;")
        content_layout = QVBoxLayout(self._content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Video widget
        if self._player_available:
            self._video_widget.setVisible(False)
            content_layout.addWidget(self._video_widget)
        
        # Image label (for photos)
        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet("background-color: #000000; color: #ffffff;")
        self._image_label.setScaledContents(False)
        self._image_label.setVisible(False)
        content_layout.addWidget(self._image_label)
        
        layout.addWidget(self._content_frame, stretch=1)
        
        # Controls overlay (bottom)
        self._controls_frame = QFrame(self)
        self._controls_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 180);
                border-top: 1px solid #333333;
            }
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 30);
            }
            QLabel {
                color: #ffffff;
                font-size: 12px;
            }
        """)
        controls_layout = QVBoxLayout(self._controls_frame)
        controls_layout.setContentsMargins(20, 10, 20, 10)
        
        # Progress row (for videos)
        self._progress_row = QHBoxLayout()
        self._position_label = QLabel("0:00")
        self._progress_row.addWidget(self._position_label)
        
        self._progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setRange(0, 0)
        if self._player_available:
            self._progress_slider.sliderMoved.connect(self._seek_position)
        self._progress_row.addWidget(self._progress_slider, stretch=1)
        
        self._duration_label = QLabel("0:00")
        self._progress_row.addWidget(self._duration_label)
        controls_layout.addLayout(self._progress_row)
        
        # Buttons row
        buttons_row = QHBoxLayout()
        
        # Previous button
        self._prev_button = QPushButton("⏮ Previous")
        self._prev_button.clicked.connect(self._on_previous)
        buttons_row.addWidget(self._prev_button)
        
        # Play/Pause button
        self._play_pause_button = QPushButton("▶ Play")
        self._play_pause_button.clicked.connect(self._toggle_play_pause)
        buttons_row.addWidget(self._play_pause_button)
        
        # Next button
        self._next_button = QPushButton("Next ⏭")
        self._next_button.clicked.connect(self._on_next)
        buttons_row.addWidget(self._next_button)
        
        buttons_row.addStretch(1)
        
        # Slideshow toggle (for images)
        self._slideshow_button = QPushButton("🎞 Slideshow: OFF")
        self._slideshow_button.clicked.connect(self._toggle_slideshow)
        self._slideshow_button.setVisible(False)
        buttons_row.addWidget(self._slideshow_button)
        
        # Info label (playlist position)
        self._info_label = QLabel("")
        buttons_row.addWidget(self._info_label)
        
        # Exit button
        self._exit_button = QPushButton("✖ Exit (ESC)")
        self._exit_button.clicked.connect(self._on_exit)
        buttons_row.addWidget(self._exit_button)
        
        controls_layout.addLayout(buttons_row)
        
        layout.addWidget(self._controls_frame)
        
        # Connect media player signals
        if self._player_available:
            self._media_player.positionChanged.connect(self._update_position)
            self._media_player.durationChanged.connect(self._update_duration)
            self._media_player.playbackStateChanged.connect(self._update_play_button)
            self._media_player.mediaStatusChanged.connect(self._on_media_status_changed)
    
    def enter_fullscreen(self, path: Path, kind: str, playlist: Optional[List[Path]] = None, index: int = 0) -> None:
        """Enter fullscreen mode with the given media.
        
        Args:
            path: Path to media file
            kind: Media kind (audio/video/image)
            playlist: Optional playlist of paths for navigation
            index: Current position in playlist
        """
        self._current_path = path
        self._current_kind = kind
        self._playlist = playlist or [path]
        self._playlist_index = index
        
        # Load media
        self._load_media(path, kind)
        
        # Update info
        self._update_info_label()
        
        # Show fullscreen
        self.showFullScreen()
        
        # Reset controls timer
        self._reset_controls_timer()
    
    def _load_media(self, path: Path, kind: str) -> None:
        """Load media file based on kind."""
        if kind == "image":
            self._load_image(path)
        elif kind in ("video", "audio") and self._player_available:
            self._load_video(path)
        else:
            # Fallback: show filename
            if self._image_label:
                self._image_label.setText(f"📄 {path.name}\n\n(Kein Player verfügbar)")
                self._image_label.setVisible(True)
            if self._player_available:
                self._video_widget.setVisible(False)
    
    def _load_image(self, path: Path) -> None:
        """Load and display image file."""
        if not self._image_label:
            return
        
        try:
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                self._image_label.setText(f"❌ Fehler beim Laden:\n{path.name}")
            else:
                # Scale to fit window while preserving aspect ratio
                scaled = pixmap.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._image_label.setPixmap(scaled)
            
            self._image_label.setVisible(True)
            if self._player_available:
                self._video_widget.setVisible(False)
            
            # Hide progress bar for images
            self._progress_row.setEnabled(False)
            for i in range(self._progress_row.count()):
                widget = self._progress_row.itemAt(i).widget()
                if widget:
                    widget.setVisible(False)
            
            # Show slideshow button
            self._slideshow_button.setVisible(True)
            self._play_pause_button.setVisible(False)
            
        except Exception as e:
            if self._image_label:
                self._image_label.setText(f"❌ Fehler:\n{e}")
                self._image_label.setVisible(True)
    
    def _load_video(self, path: Path) -> None:
        """Load and play video/audio file."""
        if not self._player_available:
            return
        
        try:
            from PySide6.QtCore import QUrl
            
            self._media_player.setSource(QUrl.fromLocalFile(str(path)))
            self._video_widget.setVisible(True)
            if self._image_label:
                self._image_label.setVisible(False)
            
            # Show progress bar
            self._progress_row.setEnabled(True)
            for i in range(self._progress_row.count()):
                widget = self._progress_row.itemAt(i).widget()
                if widget:
                    widget.setVisible(True)
            
            # Hide slideshow button
            self._slideshow_button.setVisible(False)
            self._play_pause_button.setVisible(True)
            
            # Auto-play
            self._media_player.play()
            
        except Exception:
            pass
    
    def _toggle_play_pause(self) -> None:
        """Toggle play/pause for video."""
        if not self._player_available:
            return
        
        if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._media_player.pause()
        else:
            self._media_player.play()
    
    def _update_play_button(self, state) -> None:
        """Update play button text based on playback state."""
        try:
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self._play_pause_button.setText("⏸ Pause")
            else:
                self._play_pause_button.setText("▶ Play")
        except Exception:
            pass
    
    def _update_position(self, position: int) -> None:
        """Update progress slider and position label."""
        self._progress_slider.setValue(position)
        self._position_label.setText(self._format_time(position))
    
    def _update_duration(self, duration: int) -> None:
        """Update progress slider range and duration label."""
        self._progress_slider.setRange(0, duration)
        self._duration_label.setText(self._format_time(duration))
    
    def _seek_position(self, position: int) -> None:
        """Seek to position in video."""
        if self._player_available:
            self._media_player.setPosition(position)
    
    def _format_time(self, ms: int) -> str:
        """Format milliseconds to MM:SS."""
        seconds = ms // 1000
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}:{secs:02d}"
    
    def _on_media_status_changed(self, status) -> None:
        """Handle media status changes (e.g., end of media)."""
        try:
            if status == QMediaPlayer.MediaStatus.EndOfMedia:
                # Auto-advance to next media
                self._on_next()
        except Exception:
            pass
    
    def _on_previous(self) -> None:
        """Navigate to previous media in playlist."""
        if len(self._playlist) <= 1:
            return
        
        self._playlist_index = (self._playlist_index - 1) % len(self._playlist)
        path = self._playlist[self._playlist_index]
        
        # Infer kind from extension
        kind = self._infer_kind(path)
        
        self._load_media(path, kind)
        self._update_info_label()
        self._reset_controls_timer()
    
    def _on_next(self) -> None:
        """Navigate to next media in playlist."""
        if len(self._playlist) <= 1:
            return
        
        self._playlist_index = (self._playlist_index + 1) % len(self._playlist)
        path = self._playlist[self._playlist_index]
        
        # Infer kind from extension
        kind = self._infer_kind(path)
        
        self._load_media(path, kind)
        self._update_info_label()
        self._reset_controls_timer()
    
    def _infer_kind(self, path: Path) -> str:
        """Infer media kind from file extension."""
        ext = path.suffix.lower()
        if ext in (".mp4", ".avi", ".mkv", ".mov", ".webm"):
            return "video"
        elif ext in (".mp3", ".wav", ".flac", ".ogg", ".m4a"):
            return "audio"
        elif ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"):
            return "image"
        else:
            return "other"
    
    def _toggle_slideshow(self) -> None:
        """Toggle slideshow mode for images."""
        self._slideshow_active = not self._slideshow_active
        
        if self._slideshow_active:
            self._slideshow_button.setText("🎞 Slideshow: ON")
            self._slideshow_timer.start(self._slideshow_interval)
        else:
            self._slideshow_button.setText("🎞 Slideshow: OFF")
            self._slideshow_timer.stop()
    
    def _advance_slideshow(self) -> None:
        """Auto-advance to next image in slideshow."""
        if self._current_kind == "image":
            self._on_next()
    
    def _update_info_label(self) -> None:
        """Update playlist position info label."""
        if len(self._playlist) > 1:
            self._info_label.setText(f"{self._playlist_index + 1} / {len(self._playlist)}")
        else:
            self._info_label.setText("")
    
    def _on_exit(self) -> None:
        """Exit fullscreen mode."""
        self._cleanup()
        self.exit_requested.emit()
        self.close()
    
    def _cleanup(self) -> None:
        """Stop playback and timers."""
        if self._player_available:
            self._media_player.stop()
        self._slideshow_timer.stop()
        self._controls_hide_timer.stop()
    
    # Mouse and keyboard event handlers
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Show controls on mouse movement."""
        self._show_controls()
        self._reset_controls_timer()
        super().mouseMoveEvent(event)
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard shortcuts."""
        key = event.key()
        
        if key == Qt.Key.Key_Escape:
            self._on_exit()
        elif key == Qt.Key.Key_Space:
            self._toggle_play_pause()
        elif key == Qt.Key.Key_Left:
            self._on_previous()
        elif key == Qt.Key.Key_Right:
            self._on_next()
        elif key == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif key == Qt.Key.Key_S:
            if self._current_kind == "image":
                self._toggle_slideshow()
        else:
            super().keyPressEvent(event)
    
    def _show_controls(self) -> None:
        """Show controls overlay."""
        self._controls_frame.setVisible(True)
    
    def _hide_controls(self) -> None:
        """Hide controls overlay."""
        self._controls_frame.setVisible(False)
    
    def _reset_controls_timer(self) -> None:
        """Reset auto-hide timer (3 seconds)."""
        self._controls_hide_timer.stop()
        self._show_controls()
        self._controls_hide_timer.start(3000)
    
    def resizeEvent(self, event) -> None:
        """Re-scale image on window resize."""
        super().resizeEvent(event)
        
        if self._current_kind == "image" and self._image_label and self._current_path:
            try:
                pixmap = QPixmap(str(self._current_path))
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        self.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self._image_label.setPixmap(scaled)
            except Exception:
                pass
    
    def closeEvent(self, event) -> None:
        """Clean up on close."""
        self._cleanup()
        super().closeEvent(event)
