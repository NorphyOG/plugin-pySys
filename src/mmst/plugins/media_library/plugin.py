from __future__ import annotations

import concurrent.futures
import logging
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal, QSize, QUrl, QPoint  # type: ignore[import-not-found]
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap  # type: ignore[import-not-found]
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
    QProgressBar,
    QPushButton,
    QMenu,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core.plugin_base import BasePlugin, PluginManifest
from datetime import datetime

from .core import LibraryIndex, MediaFile, scan_source
from .covers import CoverCache
from .metadata import MediaMetadata, MetadataReader
from .watcher import FileSystemWatcher


class MediaLibraryWidget(QWidget):
    PATH_ROLE = int(Qt.ItemDataRole.UserRole)
    KIND_ROLE = PATH_ROLE + 1

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
        self._metadata_cache: dict[str, MediaMetadata] = {}
        self._updating_view_combo = False

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        self._build_sources_tab()
        self._build_browse_tab()
        self._build_gallery_tab()
        self._initialize_view_filters()

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
        layout.addWidget(controls)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Pfad", "Größe", "MTime", "Typ"])
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
        self.gallery.itemActivated.connect(self._on_gallery_activated)
        self.gallery.itemDoubleClicked.connect(self._on_gallery_activated)
        self.gallery.currentItemChanged.connect(self._on_gallery_selection_changed)
        self.gallery.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.gallery.customContextMenuRequested.connect(self._on_gallery_context_menu)
        layout.addWidget(self.gallery, stretch=1)
        self.tabs.addTab(tab, "Galerie")

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
        self.detail_tabs.setCurrentIndex(0)

    def _set_detail_field(self, key: str, value: Optional[str]) -> None:
        label = self._detail_field_labels.get(key)
        if not label:
            return
        label.setText(value if value else "—")

    def _restore_selection(self, previous: Optional[Path]) -> None:
        target_key: Optional[str] = None
        if previous and str(previous) in self._entry_lookup:
            target_key = str(previous)
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

    def _display_entry(self, path: Path) -> None:
        entry = self._entry_lookup.get(str(path))
        if not entry:
            self._clear_detail_panel()
            return

        media, source_path = entry
        abs_path = (source_path / Path(media.path)).resolve(strict=False)
        self._selected_path = abs_path

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

    def _on_table_selection_changed(self) -> None:
        if self._syncing_selection:
            return

        selected_items = self.table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        path_item = self.table.item(row, 0)
        if path_item is None:
            return

        raw_path = path_item.data(self.PATH_ROLE)
        if raw_path:
            self._set_current_path(str(raw_path), source="table")

    def _on_gallery_selection_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        if self._syncing_selection:
            return

        if current is None:
            if not self._entries:
                self._clear_detail_panel()
            return

        raw_path = current.data(self.PATH_ROLE)
        if raw_path:
            self._set_current_path(str(raw_path), source="gallery")

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
        reveal_action = menu.addAction("Im Ordner anzeigen")
        action = menu.exec(global_pos)
        if action == open_action:
            self._open_media_file(path)
        elif action == reveal_action:
            self._reveal_in_file_manager(path)

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
            return

        self._apply_view_preset(str(preset_key))

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
            return
        self._rebuild_filtered_entries()

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
        self.gallery.clear()
        self._gallery_index_by_path = {}
        for index, (media, source_path) in enumerate(entries):
            abs_path = (source_path / Path(media.path)).resolve(strict=False)
            pixmap = self._plugin.cover_pixmap(abs_path, media.kind)
            icon = QIcon(pixmap)
            item = QListWidgetItem(icon, Path(media.path).name)
            item.setToolTip(str(abs_path))
            item.setData(self.PATH_ROLE, str(abs_path))
            item.setData(self.KIND_ROLE, media.kind)
            self.gallery.addItem(item)
            self._gallery_index_by_path[str(abs_path)] = index
        self.gallery.blockSignals(False)
        self.gallery.setUpdatesEnabled(True)

    def _on_library_changed(self) -> None:
        self._refresh_library_views()

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
        self._watch_enabled = False
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
        return self._index.list_files(limit=200)

    def list_recent_detailed(self) -> List[tuple[MediaFile, Path]]:
        return self._index.list_files_with_sources(limit=200)

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
        # Remove old path, add new path
        self._index.remove_file_by_path(old_path)
        self._index.add_file_by_path(new_path)
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


Plugin = MediaLibraryPlugin
