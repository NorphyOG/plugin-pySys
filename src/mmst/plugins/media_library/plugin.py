from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.plugin_base import BasePlugin, PluginManifest
from .core import LibraryIndex, MediaFile, scan_source


class MediaLibraryWidget(QWidget):
    scan_progress = Signal(str, int, int)
    scan_finished = Signal(int)
    scan_failed = Signal(str)

    def __init__(self, plugin: "MediaLibraryPlugin") -> None:
        super().__init__()
        self._plugin = plugin
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        self._build_sources_tab()
        self._build_browse_tab()

        self.scan_progress.connect(self._on_progress)
        self.scan_finished.connect(self._on_finished)
        self.scan_failed.connect(self._on_failed)

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

        self.tabs.addTab(tab, "Quellen")

    def _build_browse_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Pfad", "Größe", "MTime", "Typ"]) 
        layout.addWidget(self.table, stretch=1)
        self.tabs.addTab(tab, "Bibliothek")

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
        # refresh table
        items = self._plugin.list_recent()
        self.table.setRowCount(len(items))
        for row, mf in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(mf.path))
            self.table.setItem(row, 1, QTableWidgetItem(str(mf.size)))
            self.table.setItem(row, 2, QTableWidgetItem(str(mf.mtime)))
            self.table.setItem(row, 3, QTableWidgetItem(mf.kind))

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

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def create_view(self) -> QWidget:
        if not self._widget:
            self._widget = MediaLibraryWidget(self)
            self._widget.set_enabled(self._active)
            self._widget.refresh_sources()
        return self._widget

    def start(self) -> None:
        self._active = True
        if self._widget:
            self._widget.set_enabled(True)

    def stop(self) -> None:
        self._active = False
        if self._widget:
            self._widget.set_enabled(False)

    def shutdown(self) -> None:
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
            if self._widget:
                self._widget.scan_finished.emit(int(count))

        future.add_done_callback(_done)

    # query interface
    def list_recent(self) -> List[MediaFile]:
        return self._index.list_files(limit=200)

    # sources interface
    def list_sources(self) -> List[tuple[int, str]]:
        return [(int(_id), str(path)) for _id, path in self._index.list_sources()]

    def add_source(self, path: Path) -> int:
        return int(self._index.add_source(path))

    def remove_source(self, path: Path) -> None:
        self._index.remove_source(path)


Plugin = MediaLibraryPlugin
