from __future__ import annotations

import concurrent.futures
import functools
import logging
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

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
    QInputDialog,
    QProgressBar,
    QPushButton,
    QMenu,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...core.plugin_base import BasePlugin, PluginManifest
from datetime import datetime

from .core import LibraryIndex, MediaFile, scan_source
from .ui_helpers import BatchMetadataDialog, RatingStarBar, TagEditor
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

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        self._load_custom_presets()
        self._build_sources_tab()
        self._build_browse_tab()
        self._build_gallery_tab()
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
        self.gallery.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.gallery.itemActivated.connect(self._on_gallery_activated)
        self.gallery.itemDoubleClicked.connect(self._on_gallery_activated)
        self.gallery.currentItemChanged.connect(self._on_gallery_selection_changed)
        self.gallery.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.gallery.customContextMenuRequested.connect(self._on_gallery_context_menu)
        layout.addWidget(self.gallery, stretch=1)
        self.tabs.addTab(tab, "Galerie")

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
        layout.addWidget(self.external_player_button, alignment=Qt.AlignmentFlag.AlignHCenter)

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

        self._refresh_external_player_controls(abs_path)

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
