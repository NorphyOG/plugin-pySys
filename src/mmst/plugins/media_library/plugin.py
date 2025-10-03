from __future__ import annotations

import concurrent.futures
import functools
import logging
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, cast

from PySide6.QtCore import Qt, Signal, QSize, QUrl, QPoint, QEvent, QTimer, QObject, QRect  # type: ignore[import-not-found]
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap, QCloseEvent, QKeyEvent  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QDialog,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QComboBox,
    QInputDialog,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QMenu,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTabWidget,
    QTextEdit,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

try:  # pragma: no cover - optional dependency
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput  # type: ignore[import-not-found]
    from PySide6.QtMultimediaWidgets import QVideoWidget  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - multimedia optional
    QMediaPlayer = None  # type: ignore[assignment]
    QAudioOutput = None  # type: ignore[assignment]
    QVideoWidget = None  # type: ignore[assignment]

HAS_QT_MULTIMEDIA = bool(QMediaPlayer) and bool(QAudioOutput)
HAS_VIDEO_WIDGET = HAS_QT_MULTIMEDIA and bool(QVideoWidget)

MediaPlayerCls = cast(Any, QMediaPlayer)
AudioOutputCls = cast(Any, QAudioOutput)
VideoWidgetCls = cast(Any, QVideoWidget)


class MediaPreviewWidget(QWidget):
    status_message = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("mediaPreview")

        self._available = HAS_QT_MULTIMEDIA
        self._current_path: Optional[Path] = None
        self._current_kind: Optional[str] = None
        self._duration: int = 0
        self._slider_pressed = False

        self.player: Any = None
        self.audio_output: Any = None
        self.video_widget: Optional[QWidget] = None
        self.play_button: Optional[QToolButton] = None
        self.stop_button: Optional[QToolButton] = None
        self.position_slider: Optional[QSlider] = None
        self.time_label: Optional[QLabel] = None
        self.volume_slider: Optional[QSlider] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        if not self._available:
            notice = QLabel(
                "Integrierte Wiedergabe benötigt das QtMultimedia-Modul. Bitte PySide6-QtMultimedia installieren."
            )
            notice.setWordWrap(True)
            notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(notice)
            self._info_label = notice
            return

        self.player = MediaPlayerCls(self)
        self.audio_output = AudioOutputCls(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)

        if HAS_VIDEO_WIDGET and VideoWidgetCls is not None:
            video_widget = VideoWidgetCls(self)
            video_widget.setMinimumHeight(200)
            video_widget.hide()
            layout.addWidget(video_widget)
            self.player.setVideoOutput(video_widget)
            self.video_widget = video_widget

        self._info_label = QLabel("Keine Vorschau geladen")
        self._info_label.setWordWrap(True)
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._info_label)

        controls = QWidget(self)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)

        self.play_button = QToolButton(controls)
        self.play_button.setEnabled(False)
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.setToolTip("Abspielen")
        self.play_button.clicked.connect(self._toggle_playback)
        controls_layout.addWidget(self.play_button)

        self.stop_button = QToolButton(controls)
        self.stop_button.setEnabled(False)
        self.stop_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.setToolTip("Stopp")
        self.stop_button.clicked.connect(self.stop)
        controls_layout.addWidget(self.stop_button)

        self.position_slider = QSlider(Qt.Orientation.Horizontal, controls)
        self.position_slider.setRange(0, 0)
        self.position_slider.setSingleStep(1000)
        self.position_slider.sliderPressed.connect(self._on_slider_pressed)
        self.position_slider.sliderReleased.connect(self._on_slider_released)
        self.position_slider.sliderMoved.connect(self._on_slider_moved)
        controls_layout.addWidget(self.position_slider, stretch=1)

        self.time_label = QLabel("00:00 / 00:00", controls)
        self.time_label.setMinimumWidth(110)
        controls_layout.addWidget(self.time_label)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal, controls)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.setValue(80)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        controls_layout.addWidget(self.volume_slider)

        layout.addWidget(controls)

        self.player.playbackStateChanged.connect(self._on_playback_state_changed)  # type: ignore[attr-defined]
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        try:
            self.player.errorOccurred.connect(self._on_error)  # type: ignore[attr-defined]
        except AttributeError:  # pragma: no cover - older Qt bindings
            try:
                self.player.error.connect(self._on_error)  # type: ignore[attr-defined]
            except AttributeError:
                pass

    def clear(self, message: Optional[str] = None) -> None:
        if not self._available or self.player is None or self.play_button is None or self.stop_button is None:
            if message:
                self._info_label.setText(message)
            return

        slider = self.position_slider
        time_label = self.time_label

        self._current_path = None
        self._current_kind = None
        self._duration = 0
        self.player.stop()
        self._update_play_button()
        self.play_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        if slider is not None:
            slider.setRange(0, 0)
            slider.setValue(0)
            slider.setEnabled(False)
        if time_label is not None:
            time_label.setText("00:00 / 00:00")
        if self.video_widget is not None:
            self.video_widget.hide()
        self._info_label.setText(message or "Keine Vorschau geladen")

    def set_media(self, path: Path, kind: str) -> None:
        if not self._available or self.player is None or self.play_button is None or self.stop_button is None:
            self._info_label.setText("QtMultimedia nicht verfügbar – Externe Wiedergabe verwenden.")
            return

        slider = self.position_slider

        normalized = kind.lower().strip() if kind else ""
        if normalized not in {"audio", "video"}:
            self.clear("Keine Vorschau für diesen Dateityp verfügbar.")
            return

        self._current_path = path
        self._current_kind = normalized
        self._duration = 0
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.play_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        if slider is not None:
            slider.setEnabled(False)
            slider.setRange(0, 0)
            slider.setValue(0)

        display_name = path.name
        if normalized == "video":
            if self.video_widget is not None:
                self.video_widget.show()
                self._info_label.setText(f"Video: {display_name}")
            else:
                self._info_label.setText("Videoausgabe nicht verfügbar – Ton wird abgespielt.")
        else:
            if self.video_widget is not None:
                self.video_widget.hide()
            self._info_label.setText(f"Audio: {display_name}")
        self._update_play_button()

    def stop(self) -> None:
        if not self._available or self.player is None:
            return
        self.player.stop()
        self._update_play_button()

    def _toggle_playback(self) -> None:
        if (
            not self._available
            or self.player is None
            or self.play_button is None
            or not self.play_button.isEnabled()
        ):
            return
        state = self.player.playbackState()
        playing_value = self._playing_state_value()
        if state == playing_value:
            self.player.pause()
        else:
            self.player.play()

    def _on_volume_changed(self, value: int) -> None:
        if not self._available or self.audio_output is None:
            return
        self.audio_output.setVolume(max(0.0, min(1.0, value / 100.0)))

    def _on_playback_state_changed(self, _state: int) -> None:
        self._update_play_button()

    def _on_position_changed(self, position: int) -> None:
        if not self._available or self._slider_pressed or self.position_slider is None:
            return
        self.position_slider.setValue(position)
        self._update_time_label(position)

    def _on_duration_changed(self, duration: int) -> None:
        if not self._available:
            return
        self._duration = max(0, duration)
        if self.position_slider is not None:
            self.position_slider.setRange(0, self._duration if self._duration > 0 else 0)
            self.position_slider.setEnabled(self._duration > 0)
        self._update_time_label(self.position_slider.value() if self.position_slider is not None else 0)

    def _on_media_status_changed(self, status: int) -> None:
        if not self._available:
            return
        loading_status = self._media_status_value("LoadingMedia")
        loaded_status = self._media_status_value("LoadedMedia")
        buffered_status = self._media_status_value("BufferedMedia")
        invalid_status = self._media_status_value("InvalidMedia")

        if status == loading_status:
            self._info_label.setText("Lade Vorschau…")
        elif status in (loaded_status, buffered_status):
            if self._current_path:
                prefix = "Video" if self._current_kind == "video" else "Audio"
                self._info_label.setText(f"{prefix}: {self._current_path.name}")
        elif status == invalid_status:
            self.clear("Datei kann nicht wiedergegeben werden.")
            if self._current_path:
                self.status_message.emit(f"Wiedergabe fehlgeschlagen: {self._current_path.name}")

    def _on_error(self, *args: Any) -> None:  # pragma: no cover - Qt specific
        message = "Unbekannter Fehler"
        if len(args) >= 2 and isinstance(args[1], str) and args[1]:
            message = args[1]
        elif len(args) == 1 and isinstance(args[0], str) and args[0]:
            message = args[0]
        if self._current_path:
            self.status_message.emit(f"Fehler bei Wiedergabe von {self._current_path.name}: {message}")
        self.clear("Fehler bei der Wiedergabe.")

    def _on_slider_pressed(self) -> None:
        self._slider_pressed = True

    def _on_slider_released(self) -> None:
        if not self._available:
            self._slider_pressed = False
            return
        self._slider_pressed = False
        if self.player is not None and self.position_slider is not None:
            self.player.setPosition(self.position_slider.value())

    def _on_slider_moved(self, value: int) -> None:
        self._update_time_label(value)

    def _update_play_button(self) -> None:
        if not self._available or self.play_button is None or self.player is None:
            return
        state = self.player.playbackState()
        playing_value = self._playing_state_value()
        if state == playing_value:
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self.play_button.setToolTip("Pausieren")
        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.play_button.setToolTip("Abspielen")

    def _update_time_label(self, position: Optional[int] = None) -> None:
        if not self._available or self.time_label is None:
            return
        current_value = 0
        if position is not None:
            current_value = max(0, position)
        elif self.position_slider is not None:
            current_value = max(0, self.position_slider.value())
        total = max(0, self._duration)
        self.time_label.setText(f"{self._format_time(current_value)} / {self._format_time(total)}")

    @staticmethod
    def _format_time(ms: int) -> str:
        total_seconds = max(0, int(ms) // 1000)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _media_status_value(name: str) -> Any:
        status_enum = getattr(MediaPlayerCls, "MediaStatus", None)
        return getattr(status_enum, name, getattr(MediaPlayerCls, name, None))

    @staticmethod
    def _playing_state_value() -> Any:
        playback_enum = getattr(MediaPlayerCls, "PlaybackState", None)
        value = getattr(playback_enum, "PlayingState", None)
        if value is None:
            value = getattr(MediaPlayerCls, "PlayingState", 2)
        return value


class CinemaModeWindow(QWidget):
    closed = Signal()
    current_media_changed = Signal(str)
    status_message = Signal(str)

    def __init__(self, entries: List[Dict[str, Any]], start_index: int = 0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        if not HAS_VIDEO_WIDGET or VideoWidgetCls is None or not HAS_QT_MULTIMEDIA:
            raise RuntimeError("Cinema mode requires QtMultimedia with video support.")

        self.setWindowFlag(Qt.WindowType.Window)
        self.setWindowTitle("Kino-Modus")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setStyleSheet("background-color: black;")

        self._entries = entries
        self._current_index = -1
        self._autoplay = True
        self._slider_pressed = False

        self.player = MediaPlayerCls(self)
        self.audio_output = AudioOutputCls(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.85)

        self.video_widget = VideoWidgetCls(self)
        self.player.setVideoOutput(self.video_widget)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.video_widget, stretch=1)

        controls_container = QWidget(self)
        controls_container.setStyleSheet("background-color: rgba(0, 0, 0, 190); color: white;")
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(16, 12, 16, 12)
        controls_layout.setSpacing(8)

        self.title_label = QLabel("", controls_container)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        controls_layout.addWidget(self.title_label)

        timeline_row = QHBoxLayout()
        timeline_row.setContentsMargins(0, 0, 0, 0)
        timeline_row.setSpacing(12)

        self.position_slider = QSlider(Qt.Orientation.Horizontal, controls_container)
        self.position_slider.setRange(0, 0)
        self.position_slider.setSingleStep(1000)
        self.position_slider.sliderPressed.connect(self._on_slider_pressed)
        self.position_slider.sliderReleased.connect(self._on_slider_released)
        self.position_slider.sliderMoved.connect(self._on_slider_moved)
        timeline_row.addWidget(self.position_slider, stretch=1)

        self.time_label = QLabel("00:00 / 00:00", controls_container)
        self.time_label.setStyleSheet("font-size: 14px;")
        self.time_label.setMinimumWidth(140)
        timeline_row.addWidget(self.time_label)

        controls_layout.addLayout(timeline_row)

        buttons_row = QHBoxLayout()
        buttons_row.setContentsMargins(0, 0, 0, 0)
        buttons_row.setSpacing(12)

        self.prev_button = QToolButton(controls_container)
        self.prev_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward))
        self.prev_button.setToolTip("Vorheriges Video")
        self.prev_button.clicked.connect(self._play_previous)
        buttons_row.addWidget(self.prev_button)

        self.play_button = QToolButton(controls_container)
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.setToolTip("Abspielen/Pausieren")
        self.play_button.clicked.connect(self._toggle_playback)
        buttons_row.addWidget(self.play_button)

        self.next_button = QToolButton(controls_container)
        self.next_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward))
        self.next_button.setToolTip("Nächstes Video")
        self.next_button.clicked.connect(self._play_next)
        buttons_row.addWidget(self.next_button)

        buttons_row.addSpacing(16)

        self.autoplay_button = QToolButton(controls_container)
        self.autoplay_button.setText("Autoplay")
        self.autoplay_button.setCheckable(True)
        self.autoplay_button.setChecked(True)
        self.autoplay_button.toggled.connect(self._on_autoplay_toggled)
        buttons_row.addWidget(self.autoplay_button)

        buttons_row.addStretch(1)

        self.sequence_label = QLabel("", controls_container)
        self.sequence_label.setStyleSheet("font-size: 14px;")
        buttons_row.addWidget(self.sequence_label)

        buttons_row.addStretch(1)

        self.exit_button = QToolButton(controls_container)
        self.exit_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton))
        self.exit_button.setToolTip("Kino-Modus schließen")
        self.exit_button.clicked.connect(self.close)
        buttons_row.addWidget(self.exit_button)

        controls_layout.addLayout(buttons_row)

        layout.addWidget(controls_container, stretch=0)

        self.player.playbackStateChanged.connect(self._on_playback_state_changed)  # type: ignore[attr-defined]
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        try:
            self.player.errorOccurred.connect(self._on_error)  # type: ignore[attr-defined]
        except AttributeError:  # pragma: no cover - older Qt bindings
            try:
                self.player.error.connect(self._on_error)  # type: ignore[attr-defined]
            except AttributeError:
                pass

        if not self._entries:
            raise ValueError("No video entries available for cinema mode")
        start_index = max(0, min(int(start_index), len(self._entries) - 1))
        self._load_index(start_index, auto_play=True)

    def _load_index(self, index: int, auto_play: bool = True) -> bool:
        if index < 0 or index >= len(self._entries):
            return False
        entry = self._entries[index]
        path_value = entry.get("path")
        if not isinstance(path_value, Path):
            return False
        abs_path = path_value
        if not abs_path.exists():
            self.status_message.emit(f"Datei nicht gefunden: {abs_path}")
            return False

        self._slider_pressed = False
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(str(abs_path)))
        self.position_slider.setEnabled(False)
        self.position_slider.setRange(0, 0)
        self.position_slider.setValue(0)
        self.time_label.setText("00:00 / 00:00")

        title_text = entry.get("title") or abs_path.name
        self.title_label.setText(title_text)
        self.sequence_label.setText(f"{index + 1} / {len(self._entries)}")

        self._current_index = index
        self._update_navigation_buttons()
        self.current_media_changed.emit(str(abs_path))
        if auto_play:
            self.player.play()
        return True

    def _update_navigation_buttons(self) -> None:
        has_prev = self._current_index > 0
        has_next = self._current_index < len(self._entries) - 1
        self.prev_button.setEnabled(has_prev)
        self.next_button.setEnabled(has_next)

    def _toggle_playback(self) -> None:
        state = self.player.playbackState()
        playing_value = MediaPreviewWidget._playing_state_value()
        if state == playing_value:
            self.player.pause()
        else:
            self.player.play()

    def _play_next(self) -> None:
        if self._current_index < len(self._entries) - 1:
            self._load_index(self._current_index + 1, auto_play=True)

    def _play_previous(self) -> None:
        if self._current_index > 0:
            self._load_index(self._current_index - 1, auto_play=True)

    def _on_autoplay_toggled(self, checked: bool) -> None:
        self._autoplay = bool(checked)

    def _on_playback_state_changed(self, _state: int) -> None:
        playing_value = MediaPreviewWidget._playing_state_value()
        if self.player.playbackState() == playing_value:
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self.play_button.setToolTip("Pausieren")
        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.play_button.setToolTip("Abspielen")

    def _on_media_status_changed(self, status: int) -> None:
        end_status = MediaPreviewWidget._media_status_value("EndOfMedia")
        if status == end_status:
            if self._autoplay and self._current_index < len(self._entries) - 1:
                self._play_next()
            return

    def _on_position_changed(self, position: int) -> None:
        if self._slider_pressed:
            return
        self.position_slider.setValue(position)
        self._update_time_label(position)

    def _on_duration_changed(self, duration: int) -> None:
        duration = max(0, duration)
        self.position_slider.setRange(0, duration if duration > 0 else 0)
        self.position_slider.setEnabled(duration > 0)
        current_value = self.position_slider.value() if self.position_slider.isEnabled() else 0
        self._update_time_label(current_value)

    def _on_slider_pressed(self) -> None:
        self._slider_pressed = True

    def _on_slider_released(self) -> None:
        self._slider_pressed = False
        if self.position_slider.isEnabled():
            self.player.setPosition(self.position_slider.value())

    def _on_slider_moved(self, value: int) -> None:
        self._update_time_label(value)

    def _update_time_label(self, position: int) -> None:
        total = self.position_slider.maximum()
        self.time_label.setText(
            f"{MediaPreviewWidget._format_time(position)} / {MediaPreviewWidget._format_time(total)}"
        )

    def _on_error(self, *args: Any) -> None:  # pragma: no cover - Qt specific
        message = "Unbekannter Fehler"
        if len(args) >= 2 and isinstance(args[1], str) and args[1]:
            message = args[1]
        elif len(args) == 1 and isinstance(args[0], str) and args[0]:
            message = args[0]
        self.status_message.emit(message)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
            return
        if key == Qt.Key.Key_Space:
            self._toggle_playback()
            return
        if key in (Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            self._play_next()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            self._play_previous()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        try:
            self.player.stop()
        finally:
            self.closed.emit()
        super().closeEvent(event)


from ...core.plugin_base import BasePlugin, PluginManifest
from datetime import datetime

from .core import LibraryIndex, MediaFile, scan_source
from .ui_helpers import BatchMetadataDialog, RatingStarBar, TagEditor
from .covers import CoverCache, PLACEHOLDER_COLORS
from .metadata import MediaMetadata, MetadataReader
from .watcher import FileSystemWatcher


class MediaLibraryWidget(QWidget):
    PATH_ROLE = int(Qt.ItemDataRole.UserRole)
    KIND_ROLE = PATH_ROLE + 1
    ICON_READY_ROLE = KIND_ROLE + 1

    scan_progress = Signal(str, int, int)
    scan_finished = Signal(int)
    scan_failed = Signal(str)
    library_changed = Signal()
    status_message = Signal(str)

    def __init__(self, plugin: "MediaLibraryPlugin") -> None:
        super().__init__()
        self._plugin = plugin
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._metadata_reader = MetadataReader()
        self._entries: List[tuple[MediaFile, Path]] = []
        self._entry_lookup: dict[str, tuple[MediaFile, Path]] = {}
        self._selected_path: Optional[Path] = None
        self._syncing_selection = False
        self._row_by_path: dict[str, int] = {}
        self._gallery_index_by_path: dict[str, int] = {}
        self._detail_field_labels: dict[str, QLabel] = {}
        self._detail_comment: Optional[QTextEdit] = None
        self.media_preview: Optional[MediaPreviewWidget] = None
        self._playlists_cache: List[Dict[str, Any]] = []
        self.playlists_list: Optional[QListWidget] = None
        self.playlist_items_table: Optional[QTableWidget] = None
        self.playlist_title_label: Optional[QLabel] = None
        self._playlist_add_selection_button: Optional[QPushButton] = None
        self._playlist_remove_button: Optional[QPushButton] = None
        self._playlist_rename_button: Optional[QPushButton] = None
        self._playlist_delete_button: Optional[QPushButton] = None
        self._current_playlist_id: Optional[int] = None
        self.add_to_playlist_button: Optional[QToolButton] = None
        self._playlist_add_menu: Optional[QMenu] = None
        self._all_entries: List[tuple[MediaFile, Path]] = []
        self._filters = {
            "text": "",
            "kind": "all",
            "sort": "recent",
            "preset": "recent",
            "rating": None,
            "genre": None,
        }
        self._view_presets = {
            "recent": {"label": "Zuletzt hinzugefügt", "kind": "all", "sort": "recent"},
            "audio": {"label": "Nur Audio", "kind": "audio", "sort": "recent"},
            "video": {"label": "Nur Video", "kind": "video", "sort": "recent"},
            "image": {"label": "Nur Bilder", "kind": "image", "sort": "recent"},
            "favorites": {"label": "Favoriten (≥4 Sterne)", "kind": "all", "sort": "recent", "rating": 4},
            "latest_changes": {"label": "Zuletzt geändert", "kind": "all", "sort": "mtime_desc"},
        }
        self._custom_presets: Dict[str, Dict[str, Any]] = {}
        self._view_state: Dict[str, Any] = self._plugin.load_view_state()
        self._metadata_cache: dict[str, MediaMetadata] = {}
        self._updating_view_combo = False
        self._rating_bar: Optional[RatingStarBar] = None
        self._tag_editor_widget: Optional[TagEditor] = None
        self._suppress_rating_signal = False
        self._suppress_tag_signal = False
        self._external_player_button: Optional[QToolButton] = None
        self._external_player_menu: Optional[QMenu] = None
        self._current_metadata_path: Optional[Path] = None
        self._browse_splitter: Optional[QSplitter] = None
        self._gallery_update_timer = QTimer(self)
        self._gallery_update_timer.setSingleShot(True)
        self._gallery_update_timer.timeout.connect(self._update_visible_gallery_icons)
        self._gallery_placeholder_icons: Dict[str, QIcon] = {}
        self._gallery_pending_icons = 0

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        self._load_custom_presets()
        self._build_sources_tab()
        self._build_browse_tab()
        self._build_gallery_tab()
        self._build_playlists_tab()
        self._initialize_view_filters()
        self._restore_view_state()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.scan_progress.connect(self._on_progress)
        self.scan_finished.connect(self._on_finished)
        self.scan_failed.connect(self._on_failed)
        self.library_changed.connect(self._on_library_changed)
        self.status_message.connect(self._on_status_message)

    def _build_sources_tab(self) -> None:
        tab = QWidget()
        form = QFormLayout(tab)

        self.source_edit = QLineEdit()
        pick = QPushButton("Ordner wählen")
        pick.clicked.connect(self._pick_source)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.source_edit, stretch=1)
        row_layout.addWidget(pick)
        form.addRow("Quelle", row)

        actions_row = QWidget()
        actions_layout = QHBoxLayout(actions_row)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        self.add_button = QPushButton("Zur Liste hinzufügen")
        self.add_button.clicked.connect(self._add_source)
        self.remove_button = QPushButton("Aus Liste entfernen")
        self.remove_button.clicked.connect(self._remove_selected_source)
        self.scan_button = QPushButton("Scannen")
        self.scan_button.clicked.connect(self._start_scan)
        actions_layout.addWidget(self.add_button)
        actions_layout.addWidget(self.remove_button)
        actions_layout.addWidget(self.scan_button)
        form.addRow(actions_row)

        self.sources_list = QListWidget()
        form.addRow("Quellenliste", self.sources_list)

        self.status = QLabel("Bereit.")
        form.addRow("Status", self.status)

        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setVisible(False)
        self.scan_progress_bar.setRange(0, 0)  # indeterminate until first progress
        form.addRow("Fortschritt", self.scan_progress_bar)

        watchdog_group = QGroupBox("Echtzeit-Überwachung")
        watchdog_layout = QVBoxLayout(watchdog_group)

        self.watch_checkbox = QCheckBox("Automatische Aktualisierung bei Dateiänderungen")
        self.watch_checkbox.setEnabled(self._plugin.watch_available)
        self.watch_checkbox.setChecked(self._plugin.watch_enabled)
        self.watch_checkbox.stateChanged.connect(self._on_watch_toggled)
        watchdog_layout.addWidget(self.watch_checkbox)

        self.watch_status = QLabel()
        watchdog_layout.addWidget(self.watch_status)
        self._update_watch_status()

        form.addRow(watchdog_group)

        self.tabs.addTab(tab, "Quellen")

    def _build_browse_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        self.view_combo = QComboBox()
        self.view_combo.addItem("Benutzerdefiniert", None)
        for key, config in self._view_presets.items():
            self.view_combo.addItem(config["label"], key)
        self.view_combo.currentIndexChanged.connect(self._on_view_preset_changed)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Suchen (Titel, Dateiname, Pfad)")
        self.search_edit.textChanged.connect(self._on_search_text_changed)

        self.kind_combo = QComboBox()
        self.kind_combo.addItem("Alle Typen", "all")
        self.kind_combo.addItem("Audio", "audio")
        self.kind_combo.addItem("Video", "video")
        self.kind_combo.addItem("Bilder", "image")
        self.kind_combo.addItem("Dokumente", "doc")
        self.kind_combo.addItem("Andere", "other")
        self.kind_combo.currentIndexChanged.connect(self._on_kind_changed)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Zuletzt hinzugefügt", "recent")
        self.sort_combo.addItem("Zuletzt geändert", "mtime_desc")
        self.sort_combo.addItem("Älteste zuerst", "mtime_asc")
        self.sort_combo.addItem("Name (A-Z)", "name")
        self.sort_combo.addItem("Größe (▼)", "size_desc")
        self.sort_combo.addItem("Größe (▲)", "size_asc")
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)

        reset_button = QPushButton("Zurücksetzen")
        reset_button.clicked.connect(self._reset_filters)

        controls_layout.addWidget(self.view_combo)
        controls_layout.addWidget(self.search_edit, stretch=1)
        controls_layout.addWidget(self.kind_combo)
        controls_layout.addWidget(self.sort_combo)
        controls_layout.addWidget(reset_button)

        self.save_preset_button = QPushButton("Preset speichern")
        self.save_preset_button.clicked.connect(self._on_save_preset_clicked)
        controls_layout.addWidget(self.save_preset_button)

        self.delete_preset_button = QPushButton("Preset löschen")
        self.delete_preset_button.clicked.connect(self._on_delete_preset_clicked)
        self.delete_preset_button.setEnabled(False)
        controls_layout.addWidget(self.delete_preset_button)

        self.batch_button = QToolButton()
        self.batch_button.setText("Stapelaktionen")
        self.batch_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.batch_button.setEnabled(False)
        self._batch_menu = QMenu(self.batch_button)
        self.batch_button.setMenu(self._batch_menu)
        self._build_batch_menu()
        controls_layout.addWidget(self.batch_button)

        layout.addWidget(controls)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Pfad", "Größe", "MTime", "Typ"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.itemDoubleClicked.connect(self._on_table_double_click)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.table)
        self.detail_panel = self._build_detail_panel()
        splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self._browse_splitter = splitter
        splitter.splitterMoved.connect(self._on_splitter_moved)

        layout.addWidget(splitter, stretch=1)
        self.tabs.addTab(tab, "Bibliothek")

    def _build_gallery_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.gallery = QListWidget()
        self.gallery.setViewMode(QListWidget.ViewMode.IconMode)
        self.gallery.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.gallery.setIconSize(QSize(160, 160))
        self.gallery.setGridSize(QSize(192, 220))
        self.gallery.setSpacing(12)
        self.gallery.setUniformItemSizes(True)
        self.gallery.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.gallery.itemActivated.connect(self._on_gallery_activated)
        self.gallery.itemDoubleClicked.connect(self._on_gallery_activated)
        self.gallery.currentItemChanged.connect(self._on_gallery_selection_changed)
        self.gallery.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.gallery.customContextMenuRequested.connect(self._on_gallery_context_menu)
        self.gallery.viewport().installEventFilter(self)
        self.gallery.verticalScrollBar().valueChanged.connect(self._on_gallery_scrolled)
        self.gallery.horizontalScrollBar().valueChanged.connect(self._on_gallery_scrolled)
        layout.addWidget(self.gallery, stretch=1)
        self.tabs.addTab(tab, "Galerie")

    def _build_playlists_tab(self) -> None:
        tab = QWidget()
        outer_layout = QVBoxLayout(tab)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal, tab)

        left_panel = QWidget(splitter)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        header_label = QLabel("Playlisten")
        header_label.setStyleSheet("font-weight: 600;")
        left_layout.addWidget(header_label)

        self.playlists_list = QListWidget(left_panel)
        self.playlists_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.playlists_list.currentItemChanged.connect(self._on_playlist_selection_changed)
        left_layout.addWidget(self.playlists_list, stretch=1)

        playlist_buttons = QHBoxLayout()
        playlist_buttons.setContentsMargins(0, 0, 0, 0)
        playlist_buttons.setSpacing(6)

        create_button = QPushButton("Neu…", left_panel)
        create_button.clicked.connect(self._create_playlist_dialog)
        playlist_buttons.addWidget(create_button)

        self._playlist_rename_button = QPushButton("Umbenennen…", left_panel)
        self._playlist_rename_button.clicked.connect(self._rename_selected_playlist)
        playlist_buttons.addWidget(self._playlist_rename_button)

        self._playlist_delete_button = QPushButton("Löschen", left_panel)
        self._playlist_delete_button.clicked.connect(self._delete_selected_playlist)
        playlist_buttons.addWidget(self._playlist_delete_button)

        playlist_buttons.addStretch(1)
        left_layout.addLayout(playlist_buttons)

        splitter.addWidget(left_panel)

        right_panel = QWidget(splitter)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self.playlist_title_label = QLabel("Keine Playlist ausgewählt", right_panel)
        self.playlist_title_label.setStyleSheet("font-weight: 600;")
        right_layout.addWidget(self.playlist_title_label)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(6)

        self._playlist_add_selection_button = QPushButton("Aus Auswahl hinzufügen", right_panel)
        self._playlist_add_selection_button.clicked.connect(self._add_selected_media_to_playlist)
        action_row.addWidget(self._playlist_add_selection_button)

        self._playlist_remove_button = QPushButton("Entfernen", right_panel)
        self._playlist_remove_button.clicked.connect(self._remove_selected_playlist_items)
        action_row.addWidget(self._playlist_remove_button)

        action_row.addStretch(1)
        right_layout.addLayout(action_row)

        self.playlist_items_table = QTableWidget(0, 4, right_panel)
        self.playlist_items_table.setHorizontalHeaderLabels(["Titel", "Künstler", "Album", "Dauer"])
        self.playlist_items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.playlist_items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.playlist_items_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.playlist_items_table.verticalHeader().setVisible(False)
        header = self.playlist_items_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.playlist_items_table.itemSelectionChanged.connect(self._update_playlist_controls_state)
        self.playlist_items_table.itemDoubleClicked.connect(self._on_playlist_item_double_clicked)
        right_layout.addWidget(self.playlist_items_table, stretch=1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        outer_layout.addWidget(splitter, stretch=1)
        self.tabs.addTab(tab, "Playlisten")

        self._update_playlist_controls_state()
        self._refresh_playlists()

    def _update_view_state_value(self, key: str, value: Any) -> None:
        if self._view_state.get(key) == value:
            return
        self._view_state[key] = value
        self._plugin.save_view_state(self._view_state)

    def _persist_filters(self) -> None:
        self._update_view_state_value("filters", dict(self._filters))

    def _on_tab_changed(self, index: int) -> None:
        self._update_view_state_value("active_tab", int(index))

    def _on_splitter_moved(self, pos: int, index: int) -> None:  # pragma: no cover - UI callback
        if self._browse_splitter is None:
            return
        self._update_view_state_value("splitter_sizes", list(self._browse_splitter.sizes()))

    def _restore_view_state(self) -> None:
        stored_filters = self._view_state.get("filters")
        if isinstance(stored_filters, dict):
            for key in self._filters.keys():
                if key in stored_filters:
                    self._filters[key] = stored_filters[key]

        text_value = str(self._filters.get("text") or "")
        self.search_edit.blockSignals(True)
        self.search_edit.setText(text_value)
        self.search_edit.blockSignals(False)

        self._set_combo_value(self.kind_combo, str(self._filters.get("kind", "all")))
        self._set_combo_value(self.sort_combo, str(self._filters.get("sort", "recent")))

        preset_key = self._filters.get("preset")
        self._updating_view_combo = True
        try:
            if preset_key and preset_key in self._view_presets:
                index = self.view_combo.findData(preset_key)
                if index >= 0:
                    self.view_combo.setCurrentIndex(index)
                else:
                    self.view_combo.setCurrentIndex(0)
            else:
                self.view_combo.setCurrentIndex(0)
        finally:
            self._updating_view_combo = False

        self._apply_and_refresh_filters()
        if preset_key and preset_key in self._view_presets:
            self._update_preset_buttons(preset_key)
        else:
            self._update_preset_buttons(None)

        splitter_sizes = self._view_state.get("splitter_sizes")
        if self._browse_splitter and isinstance(splitter_sizes, list) and all(isinstance(v, int) for v in splitter_sizes):
            if any(v > 0 for v in splitter_sizes):
                self._browse_splitter.setSizes(splitter_sizes)

        stored_tab = self._view_state.get("active_tab")
        if isinstance(stored_tab, int) and 0 <= stored_tab < self.tabs.count():
            self.tabs.setCurrentIndex(stored_tab)

        stored_path = self._view_state.get("selected_path")
        if isinstance(stored_path, str) and stored_path in self._entry_lookup:
            self._set_current_path(stored_path)

    # --- preset helpers -------------------------------------------------

    def _load_custom_presets(self) -> None:
        stored = self._plugin.load_custom_presets()
        if not stored:
            return
        for slug, config in stored.items():
            if not isinstance(config, dict):
                continue
            normalized = dict(config)
            label = str(normalized.get("label") or slug.replace("_", " ").title())
            normalized["label"] = label
            key = self._custom_key(slug)
            self._custom_presets[slug] = normalized
            self._view_presets[key] = normalized

    def _custom_key(self, slug: str) -> str:
        return f"custom:{slug}"

    def _persist_custom_presets(self) -> None:
        payload = {slug: dict(data) for slug, data in self._custom_presets.items()}
        self._plugin.save_custom_presets(payload)

    def _slugify_preset(self, name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()) or "preset"
        base = base.strip("-") or "preset"
        candidate = base
        suffix = 1
        while self._custom_key(candidate) in self._view_presets:
            suffix += 1
            candidate = f"{base}-{suffix}"
        return candidate

    def _on_save_preset_clicked(self) -> None:
        name, ok = QInputDialog.getText(self, "Preset speichern", "Name der Ansicht:", text="Neue Ansicht")
        if not ok or not name.strip():
            return
        slug = self._slugify_preset(name)
        preset_key = self._custom_key(slug)
        preset = {
            "label": name.strip(),
            "text": self._filters.get("text", ""),
            "kind": self._filters.get("kind", "all"),
            "sort": self._filters.get("sort", "recent"),
        }
        if self._filters.get("rating") is not None:
            preset["rating"] = self._filters["rating"]
        if self._filters.get("genre"):
            preset["genre"] = self._filters["genre"]
        self._custom_presets[slug] = preset
        self._view_presets[preset_key] = preset
        self.view_combo.addItem(preset["label"], preset_key)
        self._persist_custom_presets()
        self._updating_view_combo = True
        try:
            index = self.view_combo.findData(preset_key)
            if index >= 0:
                self.view_combo.setCurrentIndex(index)
        finally:
            self._updating_view_combo = False
        self._apply_view_preset(preset_key)
        self._update_preset_buttons(preset_key)

    def _on_delete_preset_clicked(self) -> None:
        data = self.view_combo.currentData()
        if not data:
            return
        preset_key = str(data)
        if not preset_key.startswith("custom:"):
            return
        slug = preset_key.split(":", 1)[1]
        self._view_presets.pop(preset_key, None)
        self._custom_presets.pop(slug, None)
        index = self.view_combo.findData(preset_key)
        if index >= 0:
            self.view_combo.removeItem(index)
        self._persist_custom_presets()
        self._reset_filters()
        self._update_preset_buttons(None)

    def _update_preset_buttons(self, preset_key: Optional[str]) -> None:
        if hasattr(self, "delete_preset_button"):
            self.delete_preset_button.setEnabled(bool(preset_key and str(preset_key).startswith("custom:")))

    # --- batch actions ---------------------------------------------------

    def _build_batch_menu(self) -> None:
        if not hasattr(self, "_batch_menu") or self._batch_menu is None:
            return
        self._batch_menu.clear()
        metadata_action = self._batch_menu.addAction("Metadaten (Batch)…")
        metadata_action.triggered.connect(self._on_batch_metadata)
        cover_action = self._batch_menu.addAction("Cover neu laden")
        cover_action.triggered.connect(self._on_batch_cover_reload)
        refresh_action = self._batch_menu.addAction("Neu indizieren")
        refresh_action.triggered.connect(self._on_batch_refresh_metadata)

    def _selected_paths(self) -> List[Path]:
        paths: Set[str] = set()
        selected_rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        for model_index in selected_rows:
            item = self.table.item(model_index.row(), 0)
            if item is None:
                continue
            raw = item.data(self.PATH_ROLE)
            if raw:
                paths.add(str(raw))
        for item in self.gallery.selectedItems():
            raw = item.data(self.PATH_ROLE)
            if raw:
                paths.add(str(raw))
        return [Path(p) for p in paths]

    def _update_batch_button_state(self) -> None:
        if hasattr(self, "batch_button"):
            self.batch_button.setEnabled(bool(self._selected_paths()))

    def _on_batch_metadata(self) -> None:
        paths = self._selected_paths()
        if not paths:
            self.status_message.emit("Keine Auswahl für Stapelaktionen.")
            return
        dialog = BatchMetadataDialog(len(paths), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        rating = dialog.selected_rating()
        tags = dialog.selected_tags()
        if rating is None and tags is None:
            return
        for path in paths:
            if rating is not None:
                self._plugin.set_rating(path, rating if rating > 0 else None)
            if tags is not None:
                self._plugin.set_tags(path, tags)
        self.status_message.emit(f"{len(paths)} Dateien aktualisiert.")

    def _on_batch_cover_reload(self) -> None:
        paths = self._selected_paths()
        if not paths:
            self.status_message.emit("Keine Auswahl für Cover-Aktualisierung.")
            return
        for path in paths:
            self._plugin.invalidate_cover(path)
            self.evict_metadata_cache(path)
        self.status_message.emit(f"Cover neu geladen für {len(paths)} Dateien.")
        self.library_changed.emit()

    def _on_batch_refresh_metadata(self) -> None:
        paths = self._selected_paths()
        if not paths:
            self.status_message.emit("Keine Auswahl für Neuindizierung.")
            return
        updated = 0
        for path in paths:
            if self._plugin.refresh_metadata(path):
                updated += 1
        if updated:
            self.status_message.emit(f"{updated} Dateien neu indiziert.")
            self.library_changed.emit()
        else:
            self.status_message.emit("Keine Dateien aktualisiert.")

    # --- external player integration ------------------------------------

    def _trigger_external_player(self, path: Path) -> None:
        if not self._plugin.open_with_external_player(path):
            self.status_message.emit("Kein externer Player konfiguriert.")

    def _refresh_external_player_controls(self, path: Path) -> None:
        if self.external_player_button is None or self._external_player_menu is None:
            return
        self._external_player_menu.clear()
        config = self._plugin.resolve_external_player(path)
        if config and config.get("command"):
            label = config.get("label", "Extern")
            action = self._external_player_menu.addAction(f"Mit {label} öffnen")
            action.triggered.connect(functools.partial(self._trigger_external_player, path))
        else:
            placeholder = self._external_player_menu.addAction("Kein Player konfiguriert")
            placeholder.setEnabled(False)
        configure_action = self._external_player_menu.addAction("Konfigurieren…")
        configure_action.triggered.connect(functools.partial(self._configure_external_player, path))
        if config and config.get("command"):
            remove_action = self._external_player_menu.addAction("Konfiguration entfernen")
            remove_action.triggered.connect(functools.partial(self._remove_external_player, path))
        self.external_player_button.setEnabled(True)

    def _configure_external_player(self, path: Path) -> None:
        ext = path.suffix.lstrip(".")
        current = self._plugin.resolve_external_player(path) or {}
        ext_text, ok = QInputDialog.getText(self, "Externen Player", "Dateiendung:", text=ext or "")
        if not ok or not ext_text.strip():
            return
        extension = ext_text.strip().lstrip(".")
        label_text, ok = QInputDialog.getText(
            self,
            "Externen Player",
            "Anzeigename:",
            text=str(current.get("label", extension.upper())) if current else extension.upper(),
        )
        if not ok:
            return
        command_text, ok = QInputDialog.getText(
            self,
            "Externen Player",
            "Befehl (mit {path}):",
            text=str(current.get("command", "")),
        )
        if not ok:
            return
        if command_text.strip():
            self._plugin.set_external_player(extension, label_text.strip() or extension.upper(), command_text.strip())
        else:
            self._plugin.remove_external_player(extension)
        if self._current_metadata_path:
            self._refresh_external_player_controls(self._current_metadata_path)

    def _remove_external_player(self, path: Path) -> None:
        extension = path.suffix.lstrip(".")
        if not extension:
            return
        self._plugin.remove_external_player(extension)
        if self._current_metadata_path:
            self._refresh_external_player_controls(self._current_metadata_path)

    # --- detail interactions --------------------------------------------

    def _on_rating_changed(self, value: int) -> None:
        if self._suppress_rating_signal or self._current_metadata_path is None:
            return
        rating_value = value if value > 0 else None
        self._plugin.set_rating(self._current_metadata_path, rating_value)

    def _on_tags_changed(self, tags: List[str]) -> None:
        if self._suppress_tag_signal or self._current_metadata_path is None:
            return
        self._plugin.set_tags(self._current_metadata_path, tags)

    def _initialize_view_filters(self) -> None:
        self._updating_view_combo = True
        try:
            preset_index = self.view_combo.findData("recent")
            if preset_index >= 0:
                self.view_combo.setCurrentIndex(preset_index)
            else:
                self.view_combo.setCurrentIndex(0)
        finally:
            self._updating_view_combo = False
        self._apply_view_preset("recent")
        self._update_preset_buttons("recent")

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.detail_heading = QLabel("Keine Auswahl")
        self.detail_heading.setWordWrap(True)
        self.detail_heading.setStyleSheet("font-weight: 600; font-size: 16px;")
        self.detail_heading.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.detail_heading)

        self.detail_cover = QLabel()
        self.detail_cover.setFixedSize(240, 240)
        self.detail_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_cover.setStyleSheet(
            "border: 1px solid rgba(255, 255, 255, 0.1); background-color: rgba(255, 255, 255, 0.03);"
        )
        layout.addWidget(self.detail_cover, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.external_player_button = QToolButton()
        self.external_player_button.setText("Extern öffnen")
        self.external_player_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.external_player_button.setEnabled(False)
        self._external_player_menu = QMenu(self.external_player_button)
        self.external_player_button.setMenu(self._external_player_menu)
        self.add_to_playlist_button = QToolButton()
        self.add_to_playlist_button.setText("Zur Playlist hinzufügen")
        self.add_to_playlist_button.setToolTip("Medien zur Playlist hinzufügen oder neue Playlist erstellen")
        self.add_to_playlist_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.add_to_playlist_button.setEnabled(False)
        self._playlist_add_menu = QMenu(self.add_to_playlist_button)
        self.add_to_playlist_button.setMenu(self._playlist_add_menu)

        controls_row = QWidget(panel)
        controls_layout = QHBoxLayout(controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.external_player_button)
        controls_layout.addWidget(self.add_to_playlist_button)
        controls_layout.addStretch(1)
        layout.addWidget(controls_row)

        self.media_preview = MediaPreviewWidget(panel)
        self.media_preview.status_message.connect(self.status_message.emit)
        layout.addWidget(self.media_preview)

        def make_label() -> QLabel:
            label = QLabel("—")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            return label

        self.detail_tabs = QTabWidget()

        overview_tab = QWidget()
        overview_form = QFormLayout(overview_tab)
        overview_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        for key, title in (
            ("path", "Pfad:"),
            ("format", "Format:"),
            ("size", "Größe:"),
            ("modified", "Geändert:"),
            ("duration", "Dauer:"),
            ("kind", "Typ:"),
        ):
            label = make_label()
            self._detail_field_labels[key] = label
            overview_form.addRow(title, label)
        self.detail_tabs.addTab(overview_tab, "Überblick")

        metadata_tab = QWidget()
        metadata_form = QFormLayout(metadata_tab)
        metadata_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        for key, title in (
            ("title", "Titel:"),
            ("artist", "Künstler:"),
            ("album", "Album:"),
            ("album_artist", "Album-Künstler:"),
            ("year", "Jahr:"),
            ("genre", "Genre:"),
            ("composer", "Komponist:"),
            ("tags", "Tags:"),
            ("rating", "Bewertung:"),
        ):
            if key == "tags":
                self._tag_editor_widget = TagEditor(metadata_tab)
                self._tag_editor_widget.setEnabled(False)
                self._tag_editor_widget.tagsChanged.connect(self._on_tags_changed)
                metadata_form.addRow(title, self._tag_editor_widget)
                continue
            if key == "rating":
                self._rating_bar = RatingStarBar(metadata_tab)
                self._rating_bar.setEnabled(False)
                self._rating_bar.ratingChanged.connect(self._on_rating_changed)
                metadata_form.addRow(title, self._rating_bar)
                continue
            label = make_label()
            self._detail_field_labels[key] = label
            metadata_form.addRow(title, label)

        self._detail_comment = QTextEdit()
        self._detail_comment.setReadOnly(True)
        self._detail_comment.setMaximumHeight(120)
        self._detail_comment.setPlaceholderText("Kein Kommentar")
        metadata_form.addRow("Kommentar:", self._detail_comment)
        self.detail_tabs.addTab(metadata_tab, "Metadaten")

        technical_tab = QWidget()
        technical_form = QFormLayout(technical_tab)
        technical_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        for key, title in (
            ("bitrate", "Bitrate:"),
            ("sample_rate", "Sample-Rate:"),
            ("channels", "Kanäle:"),
            ("codec", "Codec:"),
            ("resolution", "Auflösung:"),
        ):
            label = make_label()
            self._detail_field_labels[key] = label
            technical_form.addRow(title, label)
        self.detail_tabs.addTab(technical_tab, "Technisch")

        layout.addWidget(self.detail_tabs, stretch=1)
        self._clear_detail_panel()
        return panel

    def _clear_detail_panel(self) -> None:
        self.detail_heading.setText("Keine Auswahl")
        self.detail_heading.setToolTip("")
        self.detail_cover.clear()
        for label in self._detail_field_labels.values():
            label.setText("—")
        if self._detail_comment is not None:
            self._detail_comment.clear()
        if self.media_preview is not None:
            self.media_preview.clear()
        if self.add_to_playlist_button is not None:
            self.add_to_playlist_button.setEnabled(False)
        self._selected_path = None
        self._current_metadata_path = None
        if self.external_player_button is not None:
            self.external_player_button.setEnabled(False)
            if self._external_player_menu is not None:
                self._external_player_menu.clear()
        if self._rating_bar is not None:
            self._suppress_rating_signal = True
            self._rating_bar.update_rating(0)
            self._rating_bar.setEnabled(False)
            self._suppress_rating_signal = False
        if self._tag_editor_widget is not None:
            self._suppress_tag_signal = True
            self._tag_editor_widget.set_tags([])
            self._tag_editor_widget.setEnabled(False)
            self._suppress_tag_signal = False
        self.detail_tabs.setCurrentIndex(0)
        self._update_view_state_value("selected_path", None)
        self._update_add_to_playlist_button_state()

    def _set_detail_field(self, key: str, value: Optional[str]) -> None:
        label = self._detail_field_labels.get(key)
        if not label:
            return
        label.setText(value if value else "—")

    def _restore_selection(self, previous: Optional[Path]) -> None:
        target_key: Optional[str] = None
        if previous and str(previous) in self._entry_lookup:
            target_key = str(previous)
        else:
            stored = self._view_state.get("selected_path")
            if isinstance(stored, str) and stored in self._entry_lookup:
                target_key = stored
            elif self._entries:
                media, source_path = self._entries[0]
                target_key = str((source_path / Path(media.path)).resolve(strict=False))

        if target_key:
            self._set_current_path(target_key)
        else:
            self._selected_path = None
            self._clear_detail_panel()

    def _set_current_path(self, path_str: str, source: Optional[str] = None) -> None:
        if not path_str or path_str not in self._entry_lookup:
            return

        path = Path(path_str)
        if self._syncing_selection:
            self._display_entry(path)
            return

        self._syncing_selection = True
        try:
            if source != "table":
                row = self._row_by_path.get(path_str)
                if row is not None:
                    self.table.selectRow(row)
                    item = self.table.item(row, 0)
                    if item is not None:
                        self.table.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
            if source != "gallery":
                index = self._gallery_index_by_path.get(path_str)
                if index is not None:
                    self.gallery.setCurrentRow(index)
        finally:
            self._syncing_selection = False

        self._display_entry(path)
        selected_value = str(self._current_metadata_path) if self._current_metadata_path else None
        self._update_view_state_value("selected_path", selected_value)

    def _display_entry(self, path: Path) -> None:
        entry = self._entry_lookup.get(str(path))
        if not entry:
            self._clear_detail_panel()
            return

        media, source_path = entry
        abs_path = (source_path / Path(media.path)).resolve(strict=False)
        self._selected_path = abs_path
        self._current_metadata_path = abs_path

        pixmap = self._plugin.cover_pixmap(abs_path, media.kind)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.detail_cover.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.detail_cover.setPixmap(scaled)
        else:
            self.detail_cover.clear()

        metadata = self._get_cached_metadata(abs_path)
        db_rating, db_tags = self._plugin.get_file_attributes(abs_path)
        if db_rating is not None:
            metadata.rating = db_rating
        if db_tags:
            metadata.tags = list(db_tags)
        display_title = metadata.title or Path(media.path).stem
        self.detail_heading.setText(display_title)
        self.detail_heading.setToolTip(display_title)

        self._set_detail_field("path", str(abs_path))
        self._set_detail_field("format", metadata.format or media.kind.capitalize())
        self._set_detail_field("size", self._format_size(media.size))
        self._set_detail_field("modified", self._format_datetime(media.mtime))
        duration_text = self._format_duration(metadata.duration) if metadata.duration else None
        self._set_detail_field("duration", duration_text)
        self._set_detail_field("kind", media.kind.capitalize())

        self._set_detail_field("title", metadata.title)
        self._set_detail_field("artist", metadata.artist)
        self._set_detail_field("album", metadata.album)
        self._set_detail_field("album_artist", metadata.album_artist)
        self._set_detail_field("year", str(metadata.year) if metadata.year else None)
        self._set_detail_field("genre", metadata.genre)
        self._set_detail_field("composer", metadata.composer)
        tags_text = ", ".join(metadata.tags) if metadata.tags else None
        self._set_detail_field("tags", tags_text)
        self._set_detail_field("rating", self._format_rating(metadata.rating))

        if self._rating_bar is not None:
            self._suppress_rating_signal = True
            self._rating_bar.update_rating(metadata.rating or 0)
            self._rating_bar.setEnabled(True)
            self._suppress_rating_signal = False
        if self._tag_editor_widget is not None:
            tags_list = list(metadata.tags) if metadata.tags else []
            self._suppress_tag_signal = True
            self._tag_editor_widget.set_tags(tags_list)
            self._tag_editor_widget.setEnabled(True)
            self._suppress_tag_signal = False

        if self._detail_comment is not None:
            if metadata.comment:
                self._detail_comment.setPlainText(metadata.comment)
            else:
                self._detail_comment.clear()

        self._set_detail_field("bitrate", self._format_optional_int(metadata.bitrate, "kbps"))
        self._set_detail_field("sample_rate", self._format_sample_rate(metadata.sample_rate))
        self._set_detail_field("channels", str(metadata.channels) if metadata.channels else None)
        self._set_detail_field("codec", metadata.codec)
        self._set_detail_field("resolution", metadata.resolution)

        if self.media_preview is not None:
            self.media_preview.set_media(abs_path, media.kind)

        self._refresh_external_player_controls(abs_path)
        self._update_add_to_playlist_button_state()

    # --- playlist helpers ---------------------------------------------

    def _refresh_playlists(self, select_id: Optional[int] = None) -> None:
        target_id = select_id if select_id is not None else self._current_playlist_id
        self._playlists_cache = self._plugin.list_playlists()

        if self.playlists_list is not None:
            self.playlists_list.blockSignals(True)
            self.playlists_list.clear()
            for entry in self._playlists_cache:
                item = QListWidgetItem(f"{entry['name']} ({entry['count']})")
                item.setData(Qt.ItemDataRole.UserRole, int(entry["id"]))
                item.setData(Qt.ItemDataRole.UserRole + 1, entry["name"])
                self.playlists_list.addItem(item)
            self.playlists_list.blockSignals(False)

            if target_id is not None:
                for row in range(self.playlists_list.count()):
                    item = self.playlists_list.item(row)
                    if item is not None and item.data(Qt.ItemDataRole.UserRole) == int(target_id):
                        self.playlists_list.setCurrentRow(row)
                        break
                else:
                    self._current_playlist_id = None
                    self.playlists_list.setCurrentRow(-1)
            elif self.playlists_list.count() > 0:
                self.playlists_list.setCurrentRow(0)

        if self._current_playlist_id is None and not self._playlists_cache:
            self._refresh_playlist_items(None)

        self._update_playlist_add_menu()
        self._update_add_to_playlist_button_state()
        self._update_playlist_controls_state()

    def _playlist_entry_by_id(self, playlist_id: Optional[int]) -> Optional[Dict[str, Any]]:
        if playlist_id is None:
            return None
        for entry in self._playlists_cache:
            if int(entry["id"]) == int(playlist_id):
                return entry
        return None

    def _update_playlist_add_menu(self) -> None:
        if self._playlist_add_menu is None:
            return
        self._playlist_add_menu.clear()
        if not self._playlists_cache:
            empty_action = self._playlist_add_menu.addAction("Keine Playlists verfügbar")
            empty_action.setEnabled(False)
            create_action = self._playlist_add_menu.addAction("Neue Playlist…")
            create_action.triggered.connect(self._create_playlist_dialog)
            return
        for entry in self._playlists_cache:
            action = self._playlist_add_menu.addAction(entry["name"])
            action.triggered.connect(functools.partial(self._add_current_to_playlist, int(entry["id"])))
        self._playlist_add_menu.addSeparator()
        create_action = self._playlist_add_menu.addAction("Neue Playlist…")
        create_action.triggered.connect(self._create_playlist_dialog)

    def _update_add_to_playlist_button_state(self) -> None:
        if self.add_to_playlist_button is None:
            return
        has_path = self._selected_path is not None
        self.add_to_playlist_button.setEnabled(has_path)
        self._update_playlist_controls_state()

    def _update_playlist_controls_state(self) -> None:
        has_playlists = bool(self._playlists_cache)
        has_selection = self._current_playlist_id is not None
        has_media_selection = self._selected_path is not None
        has_item_selection = False
        if self.playlist_items_table is not None and self.playlist_items_table.selectionModel() is not None:
            has_item_selection = self.playlist_items_table.selectionModel().hasSelection()

        if self._playlist_rename_button is not None:
            self._playlist_rename_button.setEnabled(has_selection)
        if self._playlist_delete_button is not None:
            self._playlist_delete_button.setEnabled(has_selection)
        if self._playlist_add_selection_button is not None:
            self._playlist_add_selection_button.setEnabled(has_selection and has_media_selection)
        if self._playlist_remove_button is not None:
            self._playlist_remove_button.setEnabled(has_selection and has_item_selection)
        if self.playlists_list is not None and not has_playlists:
            self.playlists_list.setCurrentRow(-1)

    def _on_playlist_selection_changed(
        self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]
    ) -> None:
        if current is None:
            self._current_playlist_id = None
            self._refresh_playlist_items(None)
            self._update_playlist_controls_state()
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        playlist_id = int(data) if isinstance(data, int) else None
        self._current_playlist_id = playlist_id
        self._refresh_playlist_items(playlist_id)
        self._update_playlist_controls_state()

    def _refresh_playlist_items(self, playlist_id: Optional[int]) -> None:
        if self.playlist_items_table is None:
            return
        self.playlist_items_table.setRowCount(0)
        entry = self._playlist_entry_by_id(playlist_id)
        if playlist_id is None or entry is None:
            if self.playlist_title_label is not None:
                self.playlist_title_label.setText("Keine Playlist ausgewählt")
            self._update_playlist_controls_state()
            return

        items = self._plugin.list_playlist_items(int(playlist_id))
        self.playlist_items_table.setRowCount(len(items))
        for row_index, (media, source_path) in enumerate(items):
            abs_path = (source_path / Path(media.path)).resolve(strict=False)
            metadata = self._get_cached_metadata(abs_path)
            title = metadata.title or Path(media.path).stem
            artist = metadata.artist or "—"
            album = metadata.album or "—"
            duration_text = self._format_duration(metadata.duration) if metadata.duration else "—"

            title_item = QTableWidgetItem(title)
            title_item.setData(self.PATH_ROLE, str(abs_path))
            self.playlist_items_table.setItem(row_index, 0, title_item)
            self.playlist_items_table.setItem(row_index, 1, QTableWidgetItem(artist))
            self.playlist_items_table.setItem(row_index, 2, QTableWidgetItem(album))
            self.playlist_items_table.setItem(row_index, 3, QTableWidgetItem(duration_text))

        if self.playlist_title_label is not None:
            count = len(items)
            self.playlist_title_label.setText(f"{entry['name']} • {count} Titel")

        self._update_playlist_controls_state()

    def _create_playlist_dialog(self) -> None:
        name, accepted = QInputDialog.getText(self, "Neue Playlist", "Name der Playlist:")
        if not accepted:
            return
        if not name.strip():
            self.status_message.emit("Playlist-Name darf nicht leer sein.")
            return
        playlist_id = self._plugin.create_playlist(name)
        if playlist_id is None:
            self.status_message.emit("Playlist konnte nicht erstellt werden (Name möglicherweise bereits vorhanden).")
            return
        self.status_message.emit(f"Playlist angelegt: {name.strip()}")
        self._refresh_playlists(select_id=playlist_id)

    def _rename_selected_playlist(self) -> None:
        if self._current_playlist_id is None or self.playlists_list is None:
            return
        current_item = self.playlists_list.currentItem()
        if current_item is None:
            return
        old_name = str(current_item.data(Qt.ItemDataRole.UserRole + 1) or current_item.text())
        new_name, accepted = QInputDialog.getText(self, "Playlist umbenennen", "Neuer Name:", text=old_name)
        if not accepted:
            return
        new_name = new_name.strip()
        if not new_name:
            self.status_message.emit("Playlist-Name darf nicht leer sein.")
            return
        if not self._plugin.rename_playlist(self._current_playlist_id, new_name):
            self.status_message.emit("Playlist konnte nicht umbenannt werden (Name möglicherweise bereits vorhanden).")
            return
        self.status_message.emit(f"Playlist umbenannt in: {new_name}")
        self._refresh_playlists(select_id=self._current_playlist_id)

    def _delete_selected_playlist(self) -> None:
        if self._current_playlist_id is None or self.playlists_list is None:
            return
        current_item = self.playlists_list.currentItem()
        if current_item is None:
            return
        name = str(current_item.data(Qt.ItemDataRole.UserRole + 1) or current_item.text())
        confirm = QMessageBox.question(
            self,
            "Playlist löschen",
            f"Soll die Playlist '{name}' wirklich gelöscht werden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if self._plugin.delete_playlist(self._current_playlist_id):
            self.status_message.emit(f"Playlist gelöscht: {name}")
            self._current_playlist_id = None
            self._refresh_playlists()
        else:
            self.status_message.emit("Playlist konnte nicht gelöscht werden.")

    def _add_selected_media_to_playlist(self) -> None:
        if self._current_playlist_id is None:
            self.status_message.emit("Bitte zuerst eine Playlist auswählen.")
            return
        if self._selected_path is None:
            self.status_message.emit("Keine Mediendatei ausgewählt.")
            return
        success = self._plugin.add_to_playlist(self._current_playlist_id, self._selected_path)
        if success:
            self.status_message.emit(f"Zur Playlist hinzugefügt: {self._selected_path.name}")
            self._refresh_playlists(select_id=self._current_playlist_id)
            self._refresh_playlist_items(self._current_playlist_id)
        else:
            self.status_message.emit("Datei bereits in der Playlist oder nicht verfügbar.")

    def _add_current_to_playlist(self, playlist_id: int) -> None:
        if self._selected_path is None:
            self.status_message.emit("Keine Mediendatei ausgewählt.")
            return
        success = self._plugin.add_to_playlist(playlist_id, self._selected_path)
        entry = self._playlist_entry_by_id(playlist_id)
        name = entry["name"] if entry else f"Playlist {playlist_id}"
        if success:
            self.status_message.emit(f"Zur Playlist '{name}' hinzugefügt: {self._selected_path.name}")
            self._refresh_playlists(select_id=self._current_playlist_id)
            if self._current_playlist_id == int(playlist_id):
                self._refresh_playlist_items(self._current_playlist_id)
        else:
            self.status_message.emit(f"Datei bereits in Playlist '{name}'.")

    def _remove_selected_playlist_items(self) -> None:
        if self._current_playlist_id is None or self.playlist_items_table is None:
            return
        selection_model = self.playlist_items_table.selectionModel()
        if selection_model is None or not selection_model.hasSelection():
            return
        rows = sorted({index.row() for index in selection_model.selectedRows()}, reverse=True)
        removed = False
        for row in rows:
            item = self.playlist_items_table.item(row, 0)
            if item is None:
                continue
            path_value = item.data(self.PATH_ROLE)
            if not path_value:
                continue
            if self._plugin.remove_from_playlist(self._current_playlist_id, Path(str(path_value))):
                removed = True
        if removed:
            self.status_message.emit("Titel aus Playlist entfernt.")
            self._refresh_playlists(select_id=self._current_playlist_id)
            self._refresh_playlist_items(self._current_playlist_id)
        else:
            self.status_message.emit("Keine Titel entfernt.")

    def _on_playlist_item_double_clicked(self, item: QTableWidgetItem) -> None:
        if item is None:
            return
        path_value = item.data(self.PATH_ROLE)
        if isinstance(path_value, str):
            if path_value in self._entry_lookup:
                self._set_current_path(path_value)
            else:
                self.status_message.emit("Titel ist aktuell nicht in der Liste sichtbar. Filter anpassen?")

    def _on_table_selection_changed(self) -> None:
        if self._syncing_selection:
            return

        selected_items = self.table.selectedItems()
        if not selected_items:
            self._update_batch_button_state()
            return

        row = selected_items[0].row()
        path_item = self.table.item(row, 0)
        if path_item is None:
            return

        raw_path = path_item.data(self.PATH_ROLE)
        if raw_path:
            self._set_current_path(str(raw_path), source="table")
        self._update_batch_button_state()

    def _on_gallery_selection_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        if self._syncing_selection:
            return

        if current is None:
            if not self._entries:
                self._clear_detail_panel()
            self._update_batch_button_state()
            return

        raw_path = current.data(self.PATH_ROLE)
        if raw_path:
            self._set_current_path(str(raw_path), source="gallery")
        self._update_batch_button_state()

    def _on_table_context_menu(self, pos: QPoint) -> None:
        viewport_pos = self.table.viewport().mapFrom(self.table, pos)
        item = self.table.itemAt(viewport_pos)
        if item is None:
            return
        raw_path = item.data(self.PATH_ROLE)
        if not raw_path:
            return
        path = Path(str(raw_path))
        self._set_current_path(str(raw_path), source="table")
        global_pos = self.table.viewport().mapToGlobal(viewport_pos)
        self._show_quick_actions_menu(path, global_pos)

    def _on_gallery_context_menu(self, pos: QPoint) -> None:
        viewport_pos = self.gallery.viewport().mapFrom(self.gallery, pos)
        item = self.gallery.itemAt(viewport_pos)
        if item is None:
            return
        raw_path = item.data(self.PATH_ROLE)
        if not raw_path:
            return
        path = Path(str(raw_path))
        self._set_current_path(str(raw_path), source="gallery")
        global_pos = self.gallery.viewport().mapToGlobal(viewport_pos)
        self._show_quick_actions_menu(path, global_pos)

    def _show_quick_actions_menu(self, path: Path, global_pos: QPoint) -> None:
        menu = QMenu(self)
        open_action = menu.addAction("Abspielen / Öffnen")
        external_action = None
        remove_external_action = None
        configure_external_action = None
        config = self._plugin.resolve_external_player(path)
        if config and config.get("command"):
            label = config.get("label", "Extern")
            external_action = menu.addAction(f"Mit {label} öffnen")
        reveal_action = menu.addAction("Im Ordner anzeigen")
        menu.addSeparator()
        configure_external_action = menu.addAction("Externen Player konfigurieren…")
        if config and config.get("command"):
            remove_external_action = menu.addAction("Externe Konfiguration entfernen")
        action = menu.exec(global_pos)
        if action == open_action:
            self._open_media_file(path)
        elif external_action is not None and action == external_action:
            self._trigger_external_player(path)
        elif action == reveal_action:
            self._reveal_in_file_manager(path)
        elif configure_external_action is not None and action == configure_external_action:
            self._configure_external_player(path)
        elif remove_external_action is not None and action == remove_external_action:
            self._remove_external_player(path)

    def _open_media_file(self, path: Path) -> None:
        if not path.exists():
            self.status_message.emit(f"Datei nicht gefunden: {path}")
            return
        url = QUrl.fromLocalFile(str(path))
        if not QDesktopServices.openUrl(url):  # pragma: no cover - OS dependent
            self.status_message.emit(f"Datei kann nicht geöffnet werden: {path.name}")

    def _reveal_in_file_manager(self, path: Path) -> None:
        target = path if path.is_dir() else path.parent
        if not target.exists():
            self.status_message.emit(f"Ordner nicht gefunden: {target}")
            return
        if sys.platform.startswith("win") and path.exists():
            try:  # pragma: no cover - OS dependent
                subprocess.run(["explorer", "/select,", str(path)], check=False)
                return
            except Exception:
                pass
        url = QUrl.fromLocalFile(str(target))
        if not QDesktopServices.openUrl(url):  # pragma: no cover - OS dependent
            self.status_message.emit(f"Ordner kann nicht geöffnet werden: {target}")

    def _on_view_preset_changed(self, index: int) -> None:
        if self._updating_view_combo:
            return

        preset_key = self.view_combo.itemData(index)
        if not preset_key:
            self._filters["preset"] = None
            self._filters["rating"] = None
            self._filters["genre"] = None
            self._apply_and_refresh_filters()
            self._update_preset_buttons(None)
            return

        key_str = str(preset_key)
        self._apply_view_preset(key_str)
        self._update_preset_buttons(key_str)

    def _apply_view_preset(self, preset_key: str) -> None:
        preset = self._view_presets.get(preset_key)
        if not preset:
            return

        self._filters["preset"] = preset_key
        self._filters["rating"] = preset.get("rating")
        self._filters["genre"] = preset.get("genre")
        text = preset.get("text", "")
        self._filters["text"] = text
        self._filters["kind"] = preset.get("kind", "all")
        self._filters["sort"] = preset.get("sort", "recent")

        self.search_edit.blockSignals(True)
        self.search_edit.setText(text)
        self.search_edit.blockSignals(False)

        self._set_combo_value(self.kind_combo, self._filters["kind"])
        self._set_combo_value(self.sort_combo, self._filters["sort"])
        self._apply_and_refresh_filters()

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        combo.blockSignals(True)
        try:
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)
        finally:
            combo.blockSignals(False)

    def _set_custom_view(self) -> None:
        if self._filters.get("preset") is None:
            return
        self._filters["preset"] = None
        self._filters["rating"] = None
        self._filters["genre"] = None
        self._updating_view_combo = True
        try:
            self.view_combo.setCurrentIndex(0)
        finally:
            self._updating_view_combo = False
        self._update_preset_buttons(None)

    def _on_search_text_changed(self, text: str) -> None:
        self._filters["text"] = text.strip()
        self._set_custom_view()
        self._apply_and_refresh_filters()

    def _on_kind_changed(self, index: int) -> None:
        value = self.kind_combo.itemData(index) or "all"
        self._filters["kind"] = str(value)
        self._set_custom_view()
        self._apply_and_refresh_filters()

    def _on_sort_changed(self, index: int) -> None:
        value = self.sort_combo.itemData(index) or "recent"
        self._filters["sort"] = str(value)
        self._set_custom_view()
        self._apply_and_refresh_filters()

    def _reset_filters(self) -> None:
        self._updating_view_combo = True
        try:
            preset_index = self.view_combo.findData("recent")
            if preset_index >= 0:
                self.view_combo.setCurrentIndex(preset_index)
            else:
                self.view_combo.setCurrentIndex(0)
        finally:
            self._updating_view_combo = False
        self._apply_view_preset("recent")

    def _apply_and_refresh_filters(self) -> None:
        if not self._all_entries:
            self._entries = []
            self._entry_lookup = {}
            self.table.setRowCount(0)
            self.gallery.clear()
            self._clear_detail_panel()
            self._persist_filters()
            return
        self._rebuild_filtered_entries()
        self._persist_filters()

    def _apply_filters(self, entries: List[tuple[MediaFile, Path]]) -> List[tuple[MediaFile, Path]]:
        if not entries:
            return []

        text = (self._filters.get("text") or "").lower()
        kind_filter = self._filters.get("kind", "all")
        rating_min = self._filters.get("rating")
        genre_filter = self._filters.get("genre")

        filtered: List[tuple[MediaFile, Path]] = []
        for media, source_path in entries:
            abs_path = (source_path / Path(media.path)).resolve(strict=False)
            key_str = str(abs_path)
            metadata: Optional[MediaMetadata] = None

            if text:
                base_name = Path(media.path).name.lower()
                if text not in base_name and text not in key_str.lower():
                    metadata = self._get_cached_metadata(abs_path)
                    candidates = [
                        metadata.title or "",
                        metadata.album or "",
                        metadata.artist or "",
                    ]
                    if not any(text in value.lower() for value in candidates):
                        continue

            if kind_filter != "all" and media.kind != kind_filter:
                continue

            if rating_min is not None or genre_filter:
                if metadata is None:
                    metadata = self._get_cached_metadata(abs_path)
                if rating_min is not None:
                    current_rating = metadata.rating or 0
                    if current_rating < rating_min:
                        continue
                if genre_filter:
                    genre_value = (metadata.genre or "").lower()
                    if genre_value != genre_filter.lower():
                        continue

            filtered.append((media, source_path))

        return self._sort_entries(filtered)

    def _sort_entries(self, entries: List[tuple[MediaFile, Path]]) -> List[tuple[MediaFile, Path]]:
        sort_key = self._filters.get("sort", "recent")
        if sort_key == "recent":
            return list(entries)
        if sort_key == "mtime_desc":
            return sorted(entries, key=lambda item: item[0].mtime, reverse=True)
        if sort_key == "mtime_asc":
            return sorted(entries, key=lambda item: item[0].mtime)
        if sort_key == "name":
            return sorted(entries, key=lambda item: Path(item[0].path).name.lower())
        if sort_key == "size_desc":
            return sorted(entries, key=lambda item: item[0].size, reverse=True)
        if sort_key == "size_asc":
            return sorted(entries, key=lambda item: item[0].size)
        return list(entries)

    def _get_cached_metadata(self, path: Path) -> MediaMetadata:
        key = str(path)
        metadata = self._metadata_cache.get(key)
        if metadata is None:
            metadata = self._metadata_reader.read(path)
            self._metadata_cache[key] = metadata
        db_rating, db_tags = self._plugin.get_file_attributes(path)
        if db_rating is not None:
            metadata.rating = db_rating
        if db_tags:
            metadata.tags = list(db_tags)
        return metadata

    def evict_metadata_cache(self, path: Path) -> None:
        candidates = {str(path)}
        try:
            candidates.add(str(path.resolve(strict=False)))
        except Exception:
            pass
        for key in candidates:
            self._metadata_cache.pop(key, None)

    def clear_metadata_cache(self) -> None:
        self._metadata_cache.clear()

    def _format_size(self, size: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        value = float(size)
        for unit in units:
            if value < 1024 or unit == "TB":
                if unit == "B":
                    return f"{int(value)} {unit}"
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} TB"

    def _format_datetime(self, timestamp: float) -> str:
        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            return "—"

    def _format_duration(self, seconds: float) -> str:
        total_seconds = int(round(seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def _format_optional_int(self, value: Optional[int], unit: str | None = None) -> Optional[str]:
        if value is None:
            return None
        if unit:
            return f"{value} {unit}"
        return str(value)

    def _format_sample_rate(self, value: Optional[int]) -> Optional[str]:
        if value is None:
            return None
        if value >= 1000 and value % 1000 == 0:
            return f"{value / 1000:.1f} kHz"
        return f"{value} Hz"

    def _format_rating(self, rating: Optional[int]) -> Optional[str]:
        if rating is None or rating <= 0:
            return None
        rating = max(0, min(rating, 5))
        return "★" * rating + "☆" * (5 - rating)

    def _refresh_library_views(self) -> None:
        entries = self._plugin.list_recent_detailed()
        self._all_entries = entries
        valid_keys = {
            str((source_path / Path(media.path)).resolve(strict=False))
            for media, source_path in entries
        }
        self._metadata_cache = {k: v for k, v in self._metadata_cache.items() if k in valid_keys}
        self._rebuild_filtered_entries()

    def _rebuild_filtered_entries(self) -> None:
        previous = self._selected_path
        filtered = self._apply_filters(self._all_entries)
        self._entries = filtered
        self._entry_lookup = {}
        for media, source_path in filtered:
            abs_path = (source_path / Path(media.path)).resolve(strict=False)
            self._entry_lookup[str(abs_path)] = (media, source_path)

        self._populate_table(filtered)
        self._populate_gallery(filtered)
        self._restore_selection(previous)
        self._update_batch_button_state()

    def _populate_table(self, entries: List[tuple[MediaFile, Path]]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(entries))
        self._row_by_path = {}
        for row, (media, source_path) in enumerate(entries):
            abs_path = (source_path / Path(media.path)).resolve(strict=False)

            path_item = QTableWidgetItem(media.path)
            path_item.setData(self.PATH_ROLE, str(abs_path))
            path_item.setData(self.KIND_ROLE, media.kind)
            self.table.setItem(row, 0, path_item)
            self.table.setItem(row, 1, QTableWidgetItem(str(media.size)))
            self.table.setItem(row, 2, QTableWidgetItem(str(media.mtime)))
            self.table.setItem(row, 3, QTableWidgetItem(media.kind))
            self._row_by_path[str(abs_path)] = row
        self.table.blockSignals(False)

    def _populate_gallery(self, entries: List[tuple[MediaFile, Path]]) -> None:
        self.gallery.setUpdatesEnabled(False)
        self.gallery.blockSignals(True)
        self._gallery_update_timer.stop()
        self.gallery.clear()
        self._gallery_index_by_path = {}
        self._gallery_pending_icons = len(entries)
        placeholder_cache: Dict[str, QIcon] = {}
        for index, (media, source_path) in enumerate(entries):
            abs_path = (source_path / Path(media.path)).resolve(strict=False)
            kind = media.kind or "other"
            icon = placeholder_cache.get(kind)
            if icon is None:
                icon = self._gallery_placeholder_icon(kind)
                placeholder_cache[kind] = icon
            item = QListWidgetItem(icon, Path(media.path).name)
            item.setToolTip(str(abs_path))
            item.setData(self.PATH_ROLE, str(abs_path))
            item.setData(self.KIND_ROLE, kind)
            item.setData(self.ICON_READY_ROLE, False)
            self.gallery.addItem(item)
            self._gallery_index_by_path[str(abs_path)] = index
        self.gallery.blockSignals(False)
        self.gallery.setUpdatesEnabled(True)
        self._schedule_gallery_icon_update()

    def _gallery_placeholder_icon(self, kind: str) -> QIcon:
        icon = self._gallery_placeholder_icons.get(kind)
        if icon is not None:
            return icon
        size = self.gallery.iconSize()
        if size.isEmpty():
            size = QSize(160, 160)
        color = PLACEHOLDER_COLORS.get(kind, PLACEHOLDER_COLORS["other"])
        pixmap = QPixmap(size)
        pixmap.fill(color)
        icon = QIcon(pixmap)
        self._gallery_placeholder_icons[kind] = icon
        return icon

    def _schedule_gallery_icon_update(self, delay: int = 0) -> None:
        if self._gallery_pending_icons <= 0:
            self._gallery_update_timer.stop()
            return
        self._gallery_update_timer.start(max(0, delay))

    def _on_gallery_scrolled(self, _value: int) -> None:
        self._schedule_gallery_icon_update(40)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if self.gallery and obj is self.gallery.viewport():
            etype = event.type()
            if etype in {QEvent.Type.Resize, QEvent.Type.Show}:
                self._schedule_gallery_icon_update(0)
            elif etype in {QEvent.Type.Wheel, QEvent.Type.MouseMove, QEvent.Type.LayoutRequest}:
                self._schedule_gallery_icon_update(60)
        return super().eventFilter(obj, event)

    def _update_visible_gallery_icons(self) -> None:
        if self._gallery_pending_icons <= 0 or not self.gallery:
            self._gallery_update_timer.stop()
            return
        viewport = self.gallery.viewport()
        if viewport is None:
            return
        visible_rect = QRect(QPoint(0, 0), viewport.size())
        visible_rect.adjust(0, -200, 0, 200)
        items_loaded = 0
        max_batch = 16
        for index in range(self.gallery.count()):
            item = self.gallery.item(index)
            if item is None:
                continue
            if bool(item.data(self.ICON_READY_ROLE)):
                continue
            rect = self.gallery.visualItemRect(item)
            if not rect.isValid():
                continue
            if rect.bottom() < visible_rect.top():
                continue
            if rect.top() > visible_rect.bottom():
                if items_loaded == 0:
                    continue
                break
            self._load_gallery_icon(item)
            items_loaded += 1
            if items_loaded >= max_batch:
                break
        if self._gallery_pending_icons > 0:
            if items_loaded > 0:
                self._schedule_gallery_icon_update(80)
            else:
                self._schedule_gallery_icon_update(120)

    def _load_gallery_icon(self, item: QListWidgetItem) -> None:
        path_value = item.data(self.PATH_ROLE)
        kind_value = item.data(self.KIND_ROLE) or "other"
        icon_set = False
        if isinstance(path_value, str):
            abs_path = Path(path_value)
            try:
                pixmap = self._plugin.cover_pixmap(abs_path, str(kind_value))
            except Exception:
                pixmap = None
            if isinstance(pixmap, QPixmap) and not pixmap.isNull():
                item.setIcon(QIcon(pixmap))
                icon_set = True
        if not icon_set:
            item.setIcon(self._gallery_placeholder_icon(str(kind_value)))
        item.setData(self.ICON_READY_ROLE, True)
        self._gallery_pending_icons = max(0, self._gallery_pending_icons - 1)

    def _on_library_changed(self) -> None:
        self._refresh_library_views()
        self._refresh_playlists(select_id=self._current_playlist_id)

    def _on_status_message(self, message: str) -> None:
        self.status.setText(message)

    def _update_watch_status(self) -> None:
        if not self._plugin.watch_available:
            self.watch_status.setText("Überwachung: Nicht verfügbar (watchdog fehlt)")
            return
        if self._plugin.is_watching:
            count = self._plugin.watched_sources_count()
            self.watch_status.setText(f"Überwachung: Aktiv ({count} Quellen)")
        else:
            self.watch_status.setText("Überwachung: Inaktiv")

    def refresh_watch_controls(self) -> None:
        self.watch_checkbox.blockSignals(True)
        self.watch_checkbox.setChecked(self._plugin.watch_enabled)
        self.watch_checkbox.blockSignals(False)
        self._update_watch_status()

    def _pick_source(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Quelle wählen")
        if directory:
            self.source_edit.setText(directory)

    def _start_scan(self) -> None:
        text = self._current_source_path()
        if not text:
            self.status.setText("Bitte Quelle wählen.")
            return
        root = Path(text)
        self.status.setText("Scanne…")
        self.scan_button.setEnabled(False)
        if hasattr(self, "scan_progress_bar"):
            self.scan_progress_bar.setVisible(True)
            self.scan_progress_bar.setRange(0, 0)  # until total known
        self._plugin.run_scan(root)

    def _on_progress(self, path: str, processed: int, total: int) -> None:
        name = Path(path).name
        if total > 0:
            self.status.setText(f"Scanne… ({processed}/{total}) – {name}")
            if hasattr(self, "scan_progress_bar"):
                if self.scan_progress_bar.maximum() != total:
                    self.scan_progress_bar.setRange(0, total)
                self.scan_progress_bar.setValue(min(processed, total))
        else:
            self.status.setText(f"Scanne… – {name}")

    def _on_finished(self, count: int) -> None:
        self.status.setText(f"Scan abgeschlossen: {count} Dateien.")
        self.scan_button.setEnabled(True)
        if hasattr(self, "scan_progress_bar"):
            self.scan_progress_bar.setVisible(False)
        self._refresh_library_views()

    def _on_failed(self, message: str) -> None:
        self.status.setText(f"Fehler: {message}")
        self.scan_button.setEnabled(True)
        if hasattr(self, "scan_progress_bar"):
            self.scan_progress_bar.setVisible(False)

    def set_enabled(self, enabled: bool) -> None:
        self.setEnabled(enabled)

    # sources helpers
    def refresh_sources(self) -> None:
        self.sources_list.clear()
        for _id, path in self._plugin.list_sources():
            item = QListWidgetItem(path)
            item.setData(Qt.ItemDataRole.UserRole, int(_id))
            self.sources_list.addItem(item)

    def _current_source_path(self) -> str:
        current = self.sources_list.currentItem()
        if current is not None:
            return current.text().strip()
        return self.source_edit.text().strip()

    def _add_source(self) -> None:
        text = self.source_edit.text().strip()
        if not text:
            self.status.setText("Bitte Ordner wählen oder eingeben.")
            return
        self._plugin.add_source(Path(text))
        self.refresh_sources()
        self.status.setText("Quelle hinzugefügt.")

    def _remove_selected_source(self) -> None:
        item = self.sources_list.currentItem()
        if not item:
            self.status.setText("Keine Quelle ausgewählt.")
            return
        path = item.text()
        self._plugin.remove_source(Path(path))
        self.refresh_sources()
        self.status.setText("Quelle entfernt.")
    
    def _on_table_double_click(self, item: QTableWidgetItem) -> None:
        path_item = self.table.item(item.row(), 0)
        if path_item is None:
            return
        raw_path = path_item.data(self.PATH_ROLE)
        if raw_path is None:
            raw_path = path_item.text()
        self._open_metadata(Path(str(raw_path)))

    def _on_gallery_activated(self, item: QListWidgetItem) -> None:
        raw_path = item.data(self.PATH_ROLE)
        if raw_path is None:
            raw_path = item.text()
        self._open_metadata(Path(str(raw_path)))

    def _open_metadata(self, file_path: Path) -> None:
        from .editor import MetadataEditorDialog

        if not file_path.exists():
            self.status_message.emit(f"Datei nicht gefunden: {file_path}")
            return

        dialog = MetadataEditorDialog(file_path, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.evict_metadata_cache(file_path)
            self.status_message.emit(f"Metadaten gespeichert: {file_path.name}")
            self.library_changed.emit()
    
    def _on_watch_toggled(self, state: int) -> None:
        """Handle watchdog checkbox toggle."""
        enabled = state == Qt.CheckState.Checked.value
        self._plugin.enable_watching(enabled)
        self._update_watch_status()


class MediaLibraryPlugin(BasePlugin):
    IDENTIFIER = "mmst.media_library"

    def __init__(self, services) -> None:
        super().__init__(services)
        self._manifest = PluginManifest(
            identifier=self.IDENTIFIER,
            name="Media Library",
            description="Indizierung und Ansicht lokaler Medien",
            version="0.1.0",
            author="MMST Team",
            tags=("media", "library"),
        )
        self._widget: Optional[MediaLibraryWidget] = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._active = False
        db_dir = next(iter(self.services.ensure_subdirectories("library")))
        self._index = LibraryIndex(db_dir / "media.db")
        self._watcher = FileSystemWatcher()
        stored_watch = self.config.get("watch_enabled", False)
        if isinstance(stored_watch, bool):
            self._watch_enabled = stored_watch
        elif isinstance(stored_watch, str):
            self._watch_enabled = stored_watch.strip().lower() in {"1", "true", "yes", "on"}
        else:
            self._watch_enabled = bool(stored_watch)
        self._cover_cache = CoverCache(size=QSize(192, 192))
        self._log = logging.getLogger(__name__)

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def create_view(self) -> QWidget:
        if not self._widget:
            self._widget = MediaLibraryWidget(self)
            self._widget.set_enabled(self._active)
            self._widget.refresh_sources()
            self._widget.refresh_watch_controls()
            self._widget.library_changed.emit()
        return self._widget

    def start(self) -> None:
        self._active = True
        if self._widget:
            self._widget.set_enabled(True)
        # Auto-start watcher if enabled
        if self._watch_enabled and self._watcher.is_available:
            self._start_watching()

    def stop(self) -> None:
        self._active = False
        if self._widget:
            self._widget.set_enabled(False)
        # Stop watcher
        self._stop_watching()

    def shutdown(self) -> None:
        self._stop_watching()
        self._index.close()
        self._executor.shutdown(wait=False)

    # orchestration
    def run_scan(self, root: Path) -> None:
        if not self._active:
            if self._widget:
                self._widget.scan_failed.emit("Plugin ist nicht aktiv.")
            return

        def progress(path: str, processed: int, total: int) -> None:
            widget = self._widget
            if widget:
                widget.scan_progress.emit(path, processed, total)

        future = self._executor.submit(scan_source, root, self._index, progress)

        def _done(f: concurrent.futures.Future[int]) -> None:
            try:
                count = f.result()
            except Exception as exc:
                if self._widget:
                    self._widget.scan_failed.emit(str(exc))
                return
            self._cover_cache.clear()
            if self._widget:
                self._widget.clear_metadata_cache()
                self._widget.scan_finished.emit(int(count))

        future.add_done_callback(_done)

    # query interface
    def list_recent(self) -> List[MediaFile]:
        return self._index.list_files()

    def list_recent_detailed(self) -> List[tuple[MediaFile, Path]]:
        return self._index.list_files_with_sources()

    def cover_pixmap(self, path: Path, kind: str) -> QPixmap:
        return self._cover_cache.get(path, kind)

    @property
    def watch_enabled(self) -> bool:
        return self._watch_enabled

    def watched_sources_count(self) -> int:
        return len(self._watcher.get_watched_paths())

    # sources interface
    def list_sources(self) -> List[tuple[int, str]]:
        return [(int(_id), str(path)) for _id, path in self._index.list_sources()]

    def add_source(self, path: Path) -> int:
        return int(self._index.add_source(path))

    def remove_source(self, path: Path) -> None:
        self._index.remove_source(path)
    
    # filesystem watching
    def _start_watching(self) -> None:
        """Start filesystem watcher for all sources."""
        if not self._watcher.is_available:
            self._log.warning("watchdog not available, filesystem monitoring disabled")
            return
        
        if self._watcher.is_watching:
            return  # Already watching
        
        # Start observer with callbacks
        success = self._watcher.start(
            on_created=self._on_file_created,
            on_modified=self._on_file_modified,
            on_deleted=self._on_file_deleted,
            on_moved=self._on_file_moved,
        )
        
        if not success:
            self._log.error("failed to start filesystem watcher")
            return
        
        # Add all sources to watch list
        for _id, source_path in self.list_sources():
            self._watcher.add_path(Path(source_path))

        self._log.info(
            "filesystem watching started for %d sources",
            len(self._watcher.get_watched_paths()),
        )
        if self._widget:
            self._widget.refresh_watch_controls()
    
    def _stop_watching(self) -> None:
        """Stop filesystem watcher."""
        if self._watcher.is_watching:
            self._watcher.stop()
            self._log.info("filesystem watching stopped")
        if self._widget:
            self._widget.refresh_watch_controls()
    
    def _on_file_created(self, path: Path) -> None:
        """Handle file creation event."""
        if self._index.add_file_by_path(path):
            self._cover_cache.invalidate(path)
            self._log.info("indexed new file: %s", path)
            if self._widget:
                self._widget.evict_metadata_cache(path)
                self._widget.status_message.emit(f"Neue Datei indiziert: {path.name}")
                self._widget.library_changed.emit()
    
    def _on_file_modified(self, path: Path) -> None:
        """Handle file modification event."""
        if self._index.update_file_by_path(path):
            self._cover_cache.invalidate(path)
            self._log.info("updated file metadata: %s", path)
            if self._widget:
                self._widget.evict_metadata_cache(path)
                self._widget.status_message.emit(f"Datei aktualisiert: {path.name}")
                self._widget.library_changed.emit()
    
    def _on_file_deleted(self, path: Path) -> None:
        """Handle file deletion event."""
        if self._index.remove_file_by_path(path):
            self._cover_cache.invalidate(path)
            self._log.info("removed file from index: %s", path)
            if self._widget:
                self._widget.evict_metadata_cache(path)
                self._widget.status_message.emit(f"Datei entfernt: {path.name}")
                self._widget.library_changed.emit()
    
    def _on_file_moved(self, old_path: Path, new_path: Path) -> None:
        """Handle file move/rename event."""
        self._index.move_file(old_path, new_path)
        self._cover_cache.invalidate(old_path)
        self._cover_cache.invalidate(new_path)
        self._log.info("file moved: %s -> %s", old_path, new_path)
        if self._widget:
            self._widget.evict_metadata_cache(old_path)
            self._widget.evict_metadata_cache(new_path)
            self._widget.status_message.emit(f"Datei verschoben: {old_path.name} → {new_path.name}")
            self._widget.library_changed.emit()
    
    def enable_watching(self, enabled: bool) -> None:
        """Enable or disable filesystem watching."""
        self._watch_enabled = enabled
        if enabled and self._active:
            self._start_watching()
        elif not enabled:
            self._stop_watching()
        self.config["watch_enabled"] = bool(enabled)
        if self._widget:
            self._widget.refresh_watch_controls()
    
    @property
    def is_watching(self) -> bool:
        """Check if filesystem watching is active."""
        return self._watcher.is_watching
    
    @property
    def watch_available(self) -> bool:
        """Check if filesystem watching is available."""
        return self._watcher.is_available

    # --- attribute & preset helpers ------------------------------------

    def set_rating(self, path: Path, rating: Optional[int]) -> None:
        if self._index.set_rating(path, rating):
            self._cover_cache.invalidate(path)
            if self._widget:
                self._widget.evict_metadata_cache(path)
                self._widget.status_message.emit(
                    f"Bewertung aktualisiert: {path.name} → {rating or 0} Sterne"
                )
                self._widget.library_changed.emit()

    def set_tags(self, path: Path, tags: Iterable[str]) -> None:
        if self._index.set_tags(path, tags):
            if self._widget:
                self._widget.evict_metadata_cache(path)
                self._widget.status_message.emit(
                    "Tags aktualisiert: {}".format(path.name)
                )
                self._widget.library_changed.emit()

    def get_file_attributes(self, path: Path) -> Tuple[Optional[int], Tuple[str, ...]]:
        return self._index.get_attributes(path)

    def invalidate_cover(self, path: Path) -> None:
        self._cover_cache.invalidate(path)

    def refresh_metadata(self, path: Path) -> bool:
        updated = self._index.update_file_by_path(path)
        if updated:
            self._cover_cache.invalidate(path)
            if self._widget:
                self._widget.evict_metadata_cache(path)
        return bool(updated)

    # --- playlist interface ------------------------------------------

    def list_playlists(self) -> List[Dict[str, Any]]:
        playlists: List[Dict[str, Any]] = []
        for playlist_id, name, count in self._index.list_playlists():
            playlists.append({"id": int(playlist_id), "name": str(name), "count": int(count)})
        return playlists

    def create_playlist(self, name: str) -> Optional[int]:
        return self._index.create_playlist(name)

    def rename_playlist(self, playlist_id: int, new_name: str) -> bool:
        return self._index.rename_playlist(int(playlist_id), new_name)

    def delete_playlist(self, playlist_id: int) -> bool:
        return self._index.delete_playlist(int(playlist_id))

    def list_playlist_items(self, playlist_id: int) -> List[Tuple[MediaFile, Path]]:
        return self._index.list_playlist_items(int(playlist_id))

    def add_to_playlist(self, playlist_id: int, file_path: Path) -> bool:
        return self._index.add_to_playlist(int(playlist_id), file_path)

    def remove_from_playlist(self, playlist_id: int, file_path: Path) -> bool:
        return self._index.remove_from_playlist(int(playlist_id), file_path)

    def load_custom_presets(self) -> Dict[str, Dict[str, Any]]:
        raw = self.config.get("custom_presets", {})
        if not isinstance(raw, dict):
            return {}
        presets: Dict[str, Dict[str, Any]] = {}
        for key, value in raw.items():
            if isinstance(value, dict):
                presets[str(key)] = dict(value)
        return presets

    def save_custom_presets(self, presets: Dict[str, Dict[str, Any]]) -> None:
        self.config["custom_presets"] = presets

    def load_view_state(self) -> Dict[str, Any]:
        raw = self.config.get("view_state", {})
        if isinstance(raw, dict):
            return dict(raw)
        return {}

    def save_view_state(self, state: Dict[str, Any]) -> None:
        self.config["view_state"] = dict(state)

    # --- external player integration -----------------------------------

    def external_player_config(self) -> Dict[str, Dict[str, str]]:
        raw = self.config.get("external_players", {})
        if isinstance(raw, dict):
            normalized: Dict[str, Dict[str, str]] = {}
            for ext, data in raw.items():
                if isinstance(data, dict):
                    normalized[str(ext).lower()] = {
                        "command": str(data.get("command", "")),
                        "label": str(data.get("label", "Extern")),
                    }
            return normalized
        return {}

    def set_external_player(self, extension: str, label: str, command: str) -> None:
        extension = extension.lower().lstrip(".")
        data = self.external_player_config()
        data[extension] = {"label": label.strip() or extension.upper(), "command": command.strip()}
        self.config["external_players"] = data

    def remove_external_player(self, extension: str) -> None:
        extension = extension.lower().lstrip(".")
        data = self.external_player_config()
        if extension in data:
            del data[extension]
            self.config["external_players"] = data

    def resolve_external_player(self, path: Path) -> Optional[Dict[str, str]]:
        data = self.external_player_config()
        ext = path.suffix.lower().lstrip(".")
        if not ext:
            return None
        return data.get(ext)

    def open_with_external_player(self, path: Path) -> bool:
        config = self.resolve_external_player(path)
        if not config:
            return False
        command = config.get("command")
        if not command:
            return False
        rendered = command.replace("{path}", str(path))
        try:
            args = shlex.split(rendered)
        except ValueError:
            args = [rendered]
        try:
            subprocess.Popen(args)  # pragma: no cover - external invocation
            return True
        except Exception as exc:  # pragma: no cover - logging side effect
            if self._widget:
                self._widget.status_message.emit(f"Externer Player fehlgeschlagen: {exc}")
            return False


Plugin = MediaLibraryPlugin
