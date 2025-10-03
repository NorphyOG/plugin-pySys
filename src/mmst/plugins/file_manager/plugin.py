from __future__ import annotations

import concurrent.futures
import os
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal, QUrl  # type: ignore[import-not-found]
from PySide6.QtGui import QDesktopServices  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.plugin_base import BasePlugin, PluginManifest
from .backup import BackupResult, perform_backup
from .scanner import DuplicateGroup, DuplicateScanner

try:
    from send2trash import send2trash  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency
    send2trash = None


class FileManagerWidget(QWidget):
    scan_completed = Signal(list)
    scan_failed = Signal(str)
    scan_progress = Signal(str, int, int)
    backup_log_message = Signal(str)
    backup_completed = Signal(bool, str)
    backup_progress_init = Signal(int)
    backup_progress = Signal(int, int, str)

    def __init__(self, plugin: "FileManagerPlugin") -> None:
        super().__init__()
        self._plugin = plugin
        self._current_directory: Optional[Path] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        self._build_duplicate_tab()
        self._build_backup_tab()

        self.scan_completed.connect(self._display_results)
        self.scan_failed.connect(self._handle_error)
        self.scan_progress.connect(self._update_progress)
        self.backup_log_message.connect(self._append_backup_log)
        self.backup_progress_init.connect(self._init_backup_progress)
        self.backup_progress.connect(self._update_backup_progress)
        self.backup_completed.connect(self._handle_backup_finished)

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------
    def _build_duplicate_tab(self) -> None:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(8)

        controls = QGroupBox("Duplikat-Scanner")
        controls_layout = QFormLayout(controls)

        self.directory_edit = QLineEdit()
        browse_button = QPushButton("Ordner auswählen")
        browse_button.clicked.connect(self._choose_directory)

        directory_row = QWidget()
        directory_row_layout = QHBoxLayout(directory_row)
        directory_row_layout.setContentsMargins(0, 0, 0, 0)
        directory_row_layout.addWidget(self.directory_edit)
        directory_row_layout.addWidget(browse_button)
        controls_layout.addRow("Ordner", directory_row)

        self.scan_button = QPushButton("Scannen")
        self.scan_button.clicked.connect(self._start_scan)
        controls_layout.addRow(self.scan_button)

        tab_layout.addWidget(controls)

        self.results = QTreeWidget()
        self.results.setHeaderLabels(["Dateiname", "Pfad", "Größe", "Hash"])
        self.results.setRootIsDecorated(True)
        self.results.itemChanged.connect(self._on_result_item_changed)
        self.results.itemSelectionChanged.connect(self._on_selection_changed)
        tab_layout.addWidget(self.results, stretch=1)

        button_row = QWidget()
        button_row_layout = QHBoxLayout(button_row)
        button_row_layout.setContentsMargins(0, 0, 0, 0)
        button_row_layout.addStretch(1)

        self.open_button = QPushButton("Im Ordner anzeigen")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_selected)
        button_row_layout.addWidget(self.open_button)

        self.delete_button = QPushButton("Ausgewählte löschen")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._delete_selected)
        button_row_layout.addWidget(self.delete_button)

        tab_layout.addWidget(button_row)

        self.status_label = QLabel("Keine Scans durchgeführt.")
        tab_layout.addWidget(self.status_label)

        self.tabs.addTab(tab, "Duplikate")

    def _build_backup_tab(self) -> None:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(8)

        controls = QGroupBox("Backup")
        controls_layout = QFormLayout(controls)

        self.backup_source_edit = QLineEdit()
        source_button = QPushButton("Quelle wählen")
        source_button.clicked.connect(lambda: self._choose_backup_path(self.backup_source_edit))

        source_row = QWidget()
        source_row_layout = QHBoxLayout(source_row)
        source_row_layout.setContentsMargins(0, 0, 0, 0)
        source_row_layout.addWidget(self.backup_source_edit)
        source_row_layout.addWidget(source_button)
        controls_layout.addRow("Quelle", source_row)

        self.backup_target_edit = QLineEdit()
        target_button = QPushButton("Ziel wählen")
        target_button.clicked.connect(lambda: self._choose_backup_path(self.backup_target_edit))

        target_row = QWidget()
        target_row_layout = QHBoxLayout(target_row)
        target_row_layout.setContentsMargins(0, 0, 0, 0)
        target_row_layout.addWidget(self.backup_target_edit)
        target_row_layout.addWidget(target_button)
        controls_layout.addRow("Ziel", target_row)

        self.mirror_checkbox = QCheckBox("Ziel spiegeln (entfernt Dateien, die nicht mehr existieren)")
        controls_layout.addRow(self.mirror_checkbox)

        self.backup_button = QPushButton("Backup starten")
        self.backup_button.clicked.connect(self._start_backup)
        controls_layout.addRow(self.backup_button)

        tab_layout.addWidget(controls)

        self.backup_log = QTextEdit()
        self.backup_log.setReadOnly(True)
        tab_layout.addWidget(self.backup_log, stretch=1)

        progress_row = QWidget()
        progress_layout = QHBoxLayout(progress_row)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.backup_progress_bar = QProgressBar()
        self.backup_progress_bar.setMinimum(0)
        self.backup_progress_bar.setMaximum(0)  # indeterminate until initialized
        self.backup_progress_bar.setVisible(False)
        progress_layout.addWidget(self.backup_progress_bar, stretch=1)
        self.backup_progress_label = QLabel("")
        self.backup_progress_label.setMinimumWidth(200)
        progress_layout.addWidget(self.backup_progress_label)
        tab_layout.addWidget(progress_row)

        self.tabs.addTab(tab, "Backup")

    def set_enabled(self, enabled: bool) -> None:
        self.setEnabled(enabled)

    def _choose_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Ordner auswählen")
        if directory:
            self.directory_edit.setText(directory)

    def _choose_backup_path(self, field: QLineEdit) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Ordner auswählen")
        if directory:
            field.setText(directory)

    def _start_backup(self) -> None:
        source_text = self.backup_source_edit.text().strip()
        target_text = self.backup_target_edit.text().strip()

        if not source_text or not target_text:
            QMessageBox.warning(self, "Pfad fehlt", "Bitte Quelle und Ziel auswählen.")
            return

        source = Path(source_text)
        target = Path(target_text)

        if not source.exists() or not source.is_dir():
            QMessageBox.warning(self, "Ungültige Quelle", "Das Quellverzeichnis existiert nicht oder ist kein Ordner.")
            return

        if source == target:
            QMessageBox.warning(self, "Ungültige Auswahl", "Quelle und Ziel dürfen nicht identisch sein.")
            return

        try:
            target.relative_to(source)
        except ValueError:
            pass
        else:
            QMessageBox.warning(
                self,
                "Ungültige Auswahl",
                "Das Ziel darf nicht innerhalb des Quellverzeichnisses liegen.",
            )
            return

        self.backup_log.clear()
        self.backup_log.append(f"Backup gestartet: {source} → {target}")
        self.backup_button.setEnabled(False)
        if hasattr(self, "backup_progress_bar"):
            self.backup_progress_bar.setVisible(True)
            self.backup_progress_bar.setRange(0, 0)  # indeterminate until total known
        self._plugin.run_backup(source, target, self.mirror_checkbox.isChecked())

    def _append_backup_log(self, message: str) -> None:
        self.backup_log.append(message)
        scrollbar = self.backup_log.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _handle_backup_finished(self, success: bool, summary: str) -> None:
        self.backup_button.setEnabled(True)
        if hasattr(self, "backup_progress_bar"):
            self.backup_progress_bar.setVisible(False)
        if success:
            self.backup_log.append(summary)
            QMessageBox.information(self, "Backup abgeschlossen", summary)
        else:
            self.backup_log.append(f"Fehler: {summary}")
            QMessageBox.critical(self, "Backup fehlgeschlagen", summary)

    def _init_backup_progress(self, total: int) -> None:
        if hasattr(self, "backup_progress_bar"):
            self.backup_progress_bar.setRange(0, max(0, total))
            self.backup_progress_bar.setValue(0)
            self.backup_progress_bar.setVisible(True)
        if hasattr(self, "backup_progress_label"):
            self.backup_progress_label.setText("")

    def _update_backup_progress(self, processed: int, total: int, message: str) -> None:
        if hasattr(self, "backup_progress_bar"):
            # Ensure range reflects latest total (defensive if totals are refined)
            if self.backup_progress_bar.maximum() != max(0, total):
                self.backup_progress_bar.setRange(0, max(0, total))
            self.backup_progress_bar.setValue(min(processed, max(0, total)))
        if hasattr(self, "backup_progress_label") and total > 0:
            percent = int((processed / total) * 100) if total else 0
            filename = ""
            if message:
                # extract trailing filename/path after colon if present
                parts = message.split(":", 1)
                filename = parts[1].strip() if len(parts) > 1 else message
            self.backup_progress_label.setText(f"{percent}% – {filename}")
        # Also mirror into log for transparency
        if message:
            self.backup_log.append(message)
            scrollbar = self.backup_log.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())

    def _start_scan(self) -> None:
        path_text = self.directory_edit.text().strip()
        if not path_text:
            QMessageBox.warning(self, "Ordner fehlt", "Bitte wählen Sie einen Ordner aus.")
            return
        root = Path(path_text)
        self.status_label.setText("Scan läuft...")
        self.scan_button.setEnabled(False)
        self.results.blockSignals(True)
        self.results.clear()
        self.results.blockSignals(False)
        self.delete_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self._plugin.run_duplicate_scan(root)

    def _display_results(self, groups: List[DuplicateGroup]) -> None:
        total_files = sum(len(g.entries) for g in groups)

        self.results.blockSignals(True)
        self.results.clear()
        if not groups:
            self.status_label.setText("Keine Duplikate gefunden.")
            self.scan_button.setEnabled(True)
            self.results.blockSignals(False)
            return

        for index, group in enumerate(groups, start=1):
            total_group_size = sum(entry.size for entry in group.entries)
            header = QTreeWidgetItem(
                [
                    f"Gruppe {index} ({len(group.entries)} Dateien)",
                    str(group.entries[0].path.parent),
                    self._format_size(total_group_size),
                    group.checksum,
                ]
            )
            header.setFlags(
                header.flags()
                & ~Qt.ItemFlag.ItemIsUserCheckable
                & ~Qt.ItemFlag.ItemIsSelectable
            )
            self.results.addTopLevelItem(header)
            header.setExpanded(True)

            for entry in group.entries:
                child = QTreeWidgetItem(
                    [
                        entry.path.name,
                        str(entry.path.parent),
                        self._format_size(entry.size),
                        group.checksum,
                    ]
                )
                child.setFlags(
                    child.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsSelectable
                )
                child.setCheckState(0, Qt.CheckState.Unchecked)
                child.setData(0, Qt.ItemDataRole.UserRole, str(entry.path))
                header.addChild(child)

        self.results.blockSignals(False)
        self.status_label.setText(
            f"{len(groups)} Duplikatgruppen mit insgesamt {total_files} Dateien gefunden."
        )
        self._on_selection_changed()
        self._update_delete_button()
        self.scan_button.setEnabled(True)

    def _handle_error(self, message: str) -> None:
        self.scan_button.setEnabled(True)
        self.status_label.setText("Fehler beim Scannen.")
        QMessageBox.critical(self, "Fehler", message)

    def _on_result_item_changed(self, item: QTreeWidgetItem, column: int) -> None:  # pragma: no cover - UI slot
        if item is None or item.parent() is None:
            return
        self._update_delete_button()

    def _update_delete_button(self) -> None:
        if not hasattr(self, "delete_button"):
            return
        has_checked = False
        for group_index in range(self.results.topLevelItemCount()):
            group_item = self.results.topLevelItem(group_index)
            if group_item is None:
                continue
            for child_index in range(group_item.childCount()):
                child = group_item.child(child_index)
                if child is None:
                    continue
                if child.checkState(0) == Qt.CheckState.Checked:
                    has_checked = True
                    break
            if has_checked:
                break
        self.delete_button.setEnabled(has_checked)

    def _delete_selected(self) -> None:
        items_to_delete: List[tuple[QTreeWidgetItem, QTreeWidgetItem]] = []
        for group_index in range(self.results.topLevelItemCount()):
            group_item = self.results.topLevelItem(group_index)
            if group_item is None:
                continue
            checked_children: List[QTreeWidgetItem] = []
            for child_index in range(group_item.childCount()):
                child = group_item.child(child_index)
                if child is None:
                    continue
                if child.checkState(0) == Qt.CheckState.Checked:
                    checked_children.append(child)
            if not checked_children:
                continue
            if len(checked_children) == group_item.childCount():
                QMessageBox.warning(
                    self,
                    "Löschen nicht möglich",
                    "Mindestens eine Datei je Gruppe muss erhalten bleiben.",
                )
                return
            for child in checked_children:
                items_to_delete.append((group_item, child))

        if not items_to_delete:
            return

        confirm = QMessageBox.question(
            self,
            "Dateien löschen",
            f"Sollen {len(items_to_delete)} ausgewählte Dateien in den Papierkorb verschoben werden?",
            QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        errors: List[str] = []
        for group_item, child in items_to_delete:
            path_value = child.data(0, Qt.ItemDataRole.UserRole)
            path = Path(path_value) if path_value else None
            if path is None:
                continue
            try:
                if send2trash:
                    send2trash(str(path))
                else:  # pragma: no cover - fallback
                    path.unlink()
            except Exception as exc:  # pragma: no cover - surface errors in UI
                errors.append(f"{path}: {exc}")
                continue
            group_item.removeChild(child)

        # Remove groups that have lost duplicate status (less than 2 files remaining)
        for index in reversed(range(self.results.topLevelItemCount())):
            group_item = self.results.topLevelItem(index)
            if group_item is None:
                continue
            if group_item.childCount() < 2:
                self.results.takeTopLevelItem(index)

        remaining_groups = self.results.topLevelItemCount()
        remaining_files = 0
        for i in range(remaining_groups):
            item = self.results.topLevelItem(i)
            if item is None:
                continue
            remaining_files += item.childCount()
        if remaining_groups:
            self.status_label.setText(
                f"{remaining_groups} Gruppen verbleiben ({remaining_files} Dateien)."
            )
        else:
            self.status_label.setText("Keine Duplikate mehr vorhanden.")

        self._update_delete_button()
        self._on_selection_changed()

        if errors:
            QMessageBox.warning(
                self,
                "Löschen teilweise fehlgeschlagen",
                "\n".join(errors),
            )

    def _on_selection_changed(self) -> None:
        if not hasattr(self, "open_button"):
            return
        for item in self.results.selectedItems():
            if item and item.parent() is not None:
                self.open_button.setEnabled(True)
                return
        self.open_button.setEnabled(False)

    def _open_selected(self) -> None:
        for item in self.results.selectedItems():
            if item is None or item.parent() is None:
                continue
            path_value = item.data(0, Qt.ItemDataRole.UserRole)
            if not path_value:
                continue
            target = Path(path_value)
            url = QUrl.fromLocalFile(str(target.parent))
            if not QDesktopServices.openUrl(url):  # pragma: no cover - depends on OS handlers
                QMessageBox.warning(
                    self,
                    "Öffnen fehlgeschlagen",
                    f"Der Ordner {target.parent} konnte nicht geöffnet werden.",
                )
            return

    def _update_progress(self, path_text: str, processed: int, total: int) -> None:
        if total <= 0:
            self.status_label.setText("Scan läuft...")
            return
        name = Path(path_text).name if path_text else ""
        display_name = f" – {name}" if name else ""
        self.status_label.setText(f"Scan läuft… ({processed}/{total}){display_name}")

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if value < 1024:
                return f"{value:.2f} {unit}"
            value /= 1024
        return f"{value:.2f} PB"


class FileManagerPlugin(BasePlugin):
    def __init__(self, services):
        super().__init__(services)
        self._manifest = PluginManifest(
            identifier="mmst.file_manager",
            name="Dateiverwaltung",
            description="Scanner für doppelte Dateien und einfache Sicherungen",
            version="0.1.0",
            author="MMST Team",
            tags=("files", "backup"),
        )
        self._widget: Optional[FileManagerWidget] = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._active = False
        self._scanner = DuplicateScanner()

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def create_view(self) -> QWidget:
        if not self._widget:
            self._widget = FileManagerWidget(self)
            self._widget.set_enabled(self._active)
        return self._widget

    def initialize(self) -> None:
        self.services.ensure_subdirectories("backups", "logs")

    def start(self) -> None:
        self._active = True
        if self._widget:
            self._widget.set_enabled(True)

    def stop(self) -> None:
        self._active = False
        if self._widget:
            self._widget.set_enabled(False)

    def configure(self, parent: Optional[QWidget] = None) -> None:
        raise NotImplementedError("Konfigurationsoberfläche folgt in einer späteren Version.")

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)

    # ------------------------------------------------------------------
    # Duplicate scan orchestration
    # ------------------------------------------------------------------
    def run_duplicate_scan(self, root: Path) -> None:
        if not self._active:
            if self._widget:
                self._widget.scan_failed.emit("Plugin ist nicht aktiv.")
            return

        logger = self.services.logger

        def progress(path: Path, processed: int, total: int) -> None:
            logger.debug("Duplicate scan progress %s (%s/%s)", path, processed, total)
            current_widget = self._widget
            if current_widget:
                current_widget.scan_progress.emit(str(path), processed, total)

        future = self._executor.submit(self._scanner.scan, root, progress)

        def _handle_future(completed: concurrent.futures.Future[List[DuplicateGroup]]) -> None:
            try:
                result = completed.result()
            except Exception as exc:  # pragma: no cover - passes error via UI
                if self._widget:
                    self._widget.scan_failed.emit(str(exc))
                self.services.logger.exception("Duplicate scan failed for %s", root)
                return
            if self._widget:
                self._widget.scan_completed.emit(result)

        future.add_done_callback(_handle_future)

    # ------------------------------------------------------------------
    # Backup orchestration
    # ------------------------------------------------------------------
    def run_backup(self, source: Path, target: Path, mirror: bool) -> None:
        if not self._active:
            if self._widget:
                self._widget.backup_completed.emit(False, "Plugin ist nicht aktiv.")
            return

        logger = self.services.logger

        # Pre-calc total files in source tree for progress bar
        try:
            total_files = sum(len(files) for _, _, files in os.walk(source))
        except Exception:
            total_files = 0

        widget = self._widget
        if widget and total_files > 0:
            widget.backup_progress_init.emit(total_files)

        # Track processed files (copies or skips count as processed)
        processed = 0

        def progress(message: str) -> None:
            nonlocal processed
            logger.info("Backup: %s", message)
            current_widget = self._widget
            if current_widget:
                current_widget.backup_log_message.emit(message)

                normalized = message.lower()
                if normalized.startswith("kopiert:") or normalized.startswith("übersprungen:"):
                    processed += 1
                    current_widget.backup_progress.emit(processed, max(0, total_files), message)

        future: concurrent.futures.Future[BackupResult] = self._executor.submit(
            self._execute_backup, source, target, mirror, progress
        )

        def _handle_future(completed: concurrent.futures.Future[BackupResult]) -> None:
            widget = self._widget
            try:
                result = completed.result()
            except Exception as exc:  # pragma: no cover - passes error via UI
                logger.exception("Backup fehlgeschlagen: %s -> %s", source, target)
                if widget:
                    widget.backup_completed.emit(False, str(exc))
                return

            summary = (
                f"Kopiert: {result.copied_files}, Übersprungen: {result.skipped_files}, "
                f"Entfernt: {result.removed_files}, Volumen: {FileManagerWidget._format_size(result.total_bytes_copied)}, "
                f"Dauer: {result.duration_seconds:.1f}s"
            )
            logger.info("Backup abgeschlossen: %s", summary)
            if widget:
                widget.backup_completed.emit(True, summary)

        future.add_done_callback(_handle_future)

    @staticmethod
    def _execute_backup(
        source: Path,
        target: Path,
        mirror: bool,
        progress: Callable[[str], None],
    ) -> BackupResult:
        return perform_backup(source, target, mirror, progress)


Plugin = FileManagerPlugin
