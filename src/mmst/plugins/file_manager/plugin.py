from __future__ import annotations

import concurrent.futures
import logging
import os
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal, QUrl  # type: ignore[import-not-found]
from PySide6.QtGui import QDesktopServices  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QCheckBox,
    QComboBox,
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

logger = logging.getLogger(__name__)

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

        # Smart selection buttons
        smart_selection_group = QGroupBox("Intelligente Auswahl")
        smart_selection_layout = QHBoxLayout(smart_selection_group)
        smart_selection_layout.setContentsMargins(8, 8, 8, 8)
        
        btn_select_oldest = QPushButton("📅 Älteste wählen")
        btn_select_oldest.setToolTip("In jeder Gruppe alle außer der neuesten Datei auswählen")
        btn_select_oldest.clicked.connect(lambda: self._smart_select("oldest"))
        smart_selection_layout.addWidget(btn_select_oldest)
        
        btn_select_smallest = QPushButton("📏 Kleinste wählen")
        btn_select_smallest.setToolTip("In jeder Gruppe alle außer der größten Datei auswählen")
        btn_select_smallest.clicked.connect(lambda: self._smart_select("smallest"))
        smart_selection_layout.addWidget(btn_select_smallest)
        
        btn_select_by_folder = QPushButton("📁 Nach Ordner...")
        btn_select_by_folder.setToolTip("Alle Dateien in einem bestimmten Ordner auswählen")
        btn_select_by_folder.clicked.connect(lambda: self._smart_select("by_folder"))
        smart_selection_layout.addWidget(btn_select_by_folder)
        
        btn_deselect_all = QPushButton("❌ Alle abwählen")
        btn_deselect_all.clicked.connect(lambda: self._smart_select("deselect_all"))
        smart_selection_layout.addWidget(btn_deselect_all)
        
        tab_layout.addWidget(smart_selection_group)

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
        
        self.dry_run_checkbox = QCheckBox("Dry Run (nur Simulation, keine echten Änderungen)")
        controls_layout.addRow(self.dry_run_checkbox)

        # Profile management
        profile_row = QWidget()
        profile_layout = QHBoxLayout(profile_row)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("(Kein Profil)")
        self.profile_combo.currentTextChanged.connect(self._load_backup_profile)
        profile_layout.addWidget(self.profile_combo, stretch=1)
        
        save_profile_btn = QPushButton("💾 Speichern")
        save_profile_btn.setToolTip("Aktuelles Backup als Profil speichern")
        save_profile_btn.clicked.connect(self._save_backup_profile)
        profile_layout.addWidget(save_profile_btn)
        
        delete_profile_btn = QPushButton("🗑️ Löschen")
        delete_profile_btn.setToolTip("Ausgewähltes Profil löschen")
        delete_profile_btn.clicked.connect(self._delete_backup_profile)
        profile_layout.addWidget(delete_profile_btn)
        
        controls_layout.addRow("Profil", profile_row)

        self.backup_button = QPushButton("Backup starten")
        self.backup_button.clicked.connect(self._start_backup)
        controls_layout.addRow(self.backup_button)

        tab_layout.addWidget(controls)
        
        # Load saved profiles
        self._load_backup_profiles_list()

        # Schedule configuration section
        schedule_box = QGroupBox("⏰ Automatisches Backup (Zeitplan)")
        schedule_layout = QFormLayout(schedule_box)
        
        schedule_profile_row = QWidget()
        schedule_profile_layout = QHBoxLayout(schedule_profile_row)
        schedule_profile_layout.setContentsMargins(0, 0, 0, 0)
        
        self.schedule_profile_combo = QComboBox()
        self.schedule_profile_combo.addItem("-- Profil auswählen --")
        self.schedule_profile_combo.currentIndexChanged.connect(lambda: self._update_schedule_status())
        schedule_profile_layout.addWidget(self.schedule_profile_combo, stretch=1)
        schedule_layout.addRow("Profil", schedule_profile_row)
        
        self.schedule_interval_combo = QComboBox()
        self.schedule_interval_combo.addItem("Stündlich", "hourly")
        self.schedule_interval_combo.addItem("Täglich", "daily")
        self.schedule_interval_combo.addItem("Wöchentlich", "weekly")
        self.schedule_interval_combo.addItem("Monatlich", "monthly")
        schedule_layout.addRow("Intervall", self.schedule_interval_combo)
        
        self.schedule_enabled_checkbox = QCheckBox("Zeitplan aktiviert")
        schedule_layout.addRow(self.schedule_enabled_checkbox)
        
        self.schedule_next_run_label = QLabel("Nächster Lauf: --")
        schedule_layout.addRow("Status", self.schedule_next_run_label)
        
        schedule_button_row = QWidget()
        schedule_button_layout = QHBoxLayout(schedule_button_row)
        schedule_button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.schedule_save_button = QPushButton("✓ Zeitplan speichern")
        self.schedule_save_button.clicked.connect(self._save_schedule)
        schedule_button_layout.addWidget(self.schedule_save_button)
        
        self.schedule_delete_button = QPushButton("🗑️ Zeitplan löschen")
        self.schedule_delete_button.clicked.connect(self._delete_schedule)
        schedule_button_layout.addWidget(self.schedule_delete_button)
        
        schedule_layout.addRow(schedule_button_row)
        
        tab_layout.addWidget(schedule_box)

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

        is_dry_run = self.dry_run_checkbox.isChecked()
        
        self.backup_log.clear()
        if is_dry_run:
            self.backup_log.append(f"🔍 DRY RUN (Simulation): {source} → {target}")
            self.backup_log.append("HINWEIS: Keine tatsächlichen Änderungen werden durchgeführt.\n")
        else:
            self.backup_log.append(f"Backup gestartet: {source} → {target}")
        
        self.backup_button.setEnabled(False)
        if hasattr(self, "backup_progress_bar"):
            self.backup_progress_bar.setVisible(True)
            self.backup_progress_bar.setRange(0, 0)  # indeterminate until total known
        self._plugin.run_backup(source, target, self.mirror_checkbox.isChecked(), dry_run=is_dry_run)

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

    def _load_backup_profiles_list(self) -> None:
        """Load saved backup profiles into the combo box."""
        profiles_file = self._plugin.services.data_dir / "backup_profiles.json"
        self.profile_combo.clear()
        self.profile_combo.addItem("-- Profil wählen --")
        
        if not profiles_file.exists():
            return
        
        try:
            import json
            with open(profiles_file, "r", encoding="utf-8") as f:
                profiles = json.load(f)
            
            for profile_name in sorted(profiles.keys()):
                self.profile_combo.addItem(profile_name)
        except Exception as exc:
            QMessageBox.warning(self, "Fehler", f"Profile konnten nicht geladen werden: {exc}")
    
    def _save_backup_profile(self) -> None:
        """Save current backup settings as a named profile."""
        from PySide6.QtWidgets import QInputDialog
        
        profile_name, ok = QInputDialog.getText(
            self, "Profil speichern", "Profilname:"
        )
        
        if not ok or not profile_name.strip():
            return
        
        profile_name = profile_name.strip()
        profiles_file = self._plugin.services.data_dir / "backup_profiles.json"
        
        # Load existing profiles
        profiles = {}
        if profiles_file.exists():
            try:
                import json
                with open(profiles_file, "r", encoding="utf-8") as f:
                    profiles = json.load(f)
            except Exception:
                pass
        
        # Save current settings
        profiles[profile_name] = {
            "source": self.backup_source_edit.text().strip(),
            "target": self.backup_target_edit.text().strip(),
            "mirror": self.mirror_checkbox.isChecked()
        }
        
        # Write back to disk
        try:
            import json
            profiles_file.parent.mkdir(parents=True, exist_ok=True)
            with open(profiles_file, "w", encoding="utf-8") as f:
                json.dump(profiles, f, indent=2, ensure_ascii=False)
            
            self._load_backup_profiles_list()
            # Select the newly saved profile
            index = self.profile_combo.findText(profile_name)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
            
            QMessageBox.information(self, "Erfolg", f"Profil '{profile_name}' gespeichert.")
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", f"Profil konnte nicht gespeichert werden: {exc}")
    
    def _load_backup_profile(self, index: int) -> None:
        """Load a backup profile and populate the UI fields."""
        if index <= 0:  # Skip the placeholder item
            return
        
        profile_name = self.profile_combo.itemText(index)
        profiles_file = self._plugin.services.data_dir / "backup_profiles.json"
        
        if not profiles_file.exists():
            return
        
        try:
            import json
            with open(profiles_file, "r", encoding="utf-8") as f:
                profiles = json.load(f)
            
            if profile_name in profiles:
                settings = profiles[profile_name]
                self.backup_source_edit.setText(settings.get("source", ""))
                self.backup_target_edit.setText(settings.get("target", ""))
                self.mirror_checkbox.setChecked(settings.get("mirror", False))
        except Exception as exc:
            QMessageBox.warning(self, "Fehler", f"Profil konnte nicht geladen werden: {exc}")
    
    def _save_schedule(self) -> None:
        """Save or update the backup schedule configuration."""
        profile_index = self.schedule_profile_combo.currentIndex()
        if profile_index <= 0:
            QMessageBox.warning(self, "Profil fehlt", "Bitte wählen Sie ein Backup-Profil für den Zeitplan aus.")
            return
        
        profile_name = self.schedule_profile_combo.currentText()
        interval_value = self.schedule_interval_combo.currentData()
        enabled = self.schedule_enabled_checkbox.isChecked()
        
        # Use profile name as schedule ID
        schedule_id = f"profile_{profile_name}"
        
        try:
            from .scheduler import ScheduleInterval
            interval = ScheduleInterval.from_string(interval_value)
            if not interval:
                raise ValueError(f"Invalid interval: {interval_value}")
            
            self._plugin.scheduler.add_schedule(
                schedule_id=schedule_id,
                profile_name=profile_name,
                interval=interval,
                enabled=enabled,
            )
            
            self._update_schedule_status()
            
            status = "aktiviert" if enabled else "gespeichert (inaktiv)"
            QMessageBox.information(
                self,
                "Zeitplan gespeichert",
                f"Zeitplan für Profil '{profile_name}' wurde {status}."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", f"Zeitplan konnte nicht gespeichert werden: {exc}")
    
    def _delete_schedule(self) -> None:
        """Delete the active schedule for the selected profile."""
        profile_index = self.schedule_profile_combo.currentIndex()
        if profile_index <= 0:
            QMessageBox.information(self, "Hinweis", "Bitte wählen Sie ein Profil aus.")
            return
        
        profile_name = self.schedule_profile_combo.currentText()
        schedule_id = f"profile_{profile_name}"
        
        if not self._plugin.scheduler.get_schedule(schedule_id):
            QMessageBox.information(self, "Hinweis", f"Kein Zeitplan für Profil '{profile_name}' vorhanden.")
            return
        
        reply = QMessageBox.question(
            self,
            "Zeitplan löschen",
            f"Zeitplan für Profil '{profile_name}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            self._plugin.scheduler.remove_schedule(schedule_id)
            self._update_schedule_status()
            QMessageBox.information(self, "Erfolg", f"Zeitplan für '{profile_name}' gelöscht.")
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", f"Zeitplan konnte nicht gelöscht werden: {exc}")
    
    def _update_schedule_status(self) -> None:
        """Update the schedule status label with next run time."""
        profile_index = self.schedule_profile_combo.currentIndex()
        if profile_index <= 0:
            self.schedule_next_run_label.setText("Nächster Lauf: --")
            return
        
        profile_name = self.schedule_profile_combo.currentText()
        schedule_id = f"profile_{profile_name}"
        schedule = self._plugin.scheduler.get_schedule(schedule_id)
        
        if not schedule:
            self.schedule_next_run_label.setText("Nächster Lauf: Kein Zeitplan")
            self.schedule_enabled_checkbox.setChecked(False)
            return
        
        # Populate fields from existing schedule
        self.schedule_enabled_checkbox.setChecked(schedule.enabled)
        
        # Set interval combo
        from .scheduler import ScheduleInterval
        for i in range(self.schedule_interval_combo.count()):
            if self.schedule_interval_combo.itemData(i) == schedule.interval.value:
                self.schedule_interval_combo.setCurrentIndex(i)
                break
        
        if schedule.enabled and schedule.next_run:
            next_run_str = schedule.next_run.strftime("%d.%m.%Y %H:%M")
            self.schedule_next_run_label.setText(f"Nächster Lauf: {next_run_str}")
        else:
            self.schedule_next_run_label.setText("Nächster Lauf: Deaktiviert")
    
    def refresh_schedule_profile_list(self) -> None:
        """Refresh the schedule profile combo box from saved profiles."""
        current_text = self.schedule_profile_combo.currentText()
        self.schedule_profile_combo.clear()
        self.schedule_profile_combo.addItem("-- Profil auswählen --")
        
        profiles_file = self._plugin.services.data_dir / "backup_profiles.json"
        if not profiles_file.exists():
            return
        
        try:
            import json
            with open(profiles_file, "r", encoding="utf-8") as f:
                profiles = json.load(f)
            
            for profile_name in sorted(profiles.keys()):
                self.schedule_profile_combo.addItem(profile_name)
            
            # Restore previous selection if it still exists
            index = self.schedule_profile_combo.findText(current_text)
            if index >= 0:
                self.schedule_profile_combo.setCurrentIndex(index)
        except Exception:
            pass
    
    def _delete_backup_profile(self) -> None:
        """Delete the currently selected backup profile."""
        index = self.profile_combo.currentIndex()
        if index <= 0:  # Skip placeholder
            QMessageBox.information(self, "Hinweis", "Bitte wählen Sie ein Profil zum Löschen aus.")
            return
        
        profile_name = self.profile_combo.itemText(index)
        reply = QMessageBox.question(
            self,
            "Profil löschen",
            f"Profil '{profile_name}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        profiles_file = self._plugin.services.data_dir / "backup_profiles.json"
        
        try:
            import json
            with open(profiles_file, "r", encoding="utf-8") as f:
                profiles = json.load(f)
            
            if profile_name in profiles:
                del profiles[profile_name]
            
            with open(profiles_file, "w", encoding="utf-8") as f:
                json.dump(profiles, f, indent=2, ensure_ascii=False)
            
            self._load_backup_profiles_list()
            QMessageBox.information(self, "Erfolg", f"Profil '{profile_name}' gelöscht.")
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", f"Profil konnte nicht gelöscht werden: {exc}")

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
        deleted_paths: List[str] = []
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
                deleted_paths.append(str(path))
            except Exception as exc:  # pragma: no cover - surface errors in UI
                errors.append(f"{path}: {exc}")
                continue
            group_item.removeChild(child)
        
        # Emit event for deleted files
        if deleted_paths:
            self._plugin.services.event_bus.emit('files.deleted', {
                'paths': deleted_paths,
                'source': 'file_manager.duplicate_scanner'
            })

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

    def _smart_select(self, mode: str) -> None:
        """Intelligently select/deselect duplicate items based on criteria."""
        if mode == "deselect_all":
            # Deselect all items
            root = self.results.invisibleRootItem()
            for i in range(root.childCount()):
                group = root.child(i)
                for j in range(group.childCount()):
                    child = group.child(j)
                    child.setCheckState(0, Qt.CheckState.Unchecked)
            self.status_label.setText("Alle Auswahlen entfernt.")
            return
        
        folder_filter = ""
        if mode == "by_folder":
            # Ask user for folder path
            from PySide6.QtWidgets import QInputDialog
            folder, ok = QInputDialog.getText(
                self,
                "Ordner auswählen",
                "Geben Sie den Ordnerpfad ein (Dateien in diesem Ordner werden ausgewählt):"
            )
            if not ok or not folder:
                return
            folder_filter = folder.strip()
        
        selected_count = 0
        root = self.results.invisibleRootItem()
        
        for i in range(root.childCount()):
            group = root.child(i)
            if group.childCount() < 2:
                continue  # Skip if not a real duplicate group
            
            # Collect all files in this group with metadata
            files = []
            for j in range(group.childCount()):
                child = group.child(j)
                path_value = child.data(0, Qt.ItemDataRole.UserRole)
                if not path_value:
                    continue
                
                path = Path(str(path_value))
                if not path.exists():
                    continue
                
                stat = path.stat()
                files.append({
                    'item': child,
                    'path': path,
                    'size': stat.st_size,
                    'mtime': stat.st_mtime,
                })
            
            if not files:
                continue
            
            # Determine which files to select based on mode
            if mode == "oldest":
                # Keep newest, select all others
                newest = max(files, key=lambda f: f['mtime'])
                for file_info in files:
                    if file_info != newest:
                        file_info['item'].setCheckState(0, Qt.CheckState.Checked)
                        selected_count += 1
            
            elif mode == "smallest":
                # Keep largest, select all others
                largest = max(files, key=lambda f: f['size'])
                for file_info in files:
                    if file_info != largest:
                        file_info['item'].setCheckState(0, Qt.CheckState.Checked)
                        selected_count += 1
            
            elif mode == "by_folder":
                # Select all files in the specified folder
                for file_info in files:
                    if folder_filter in str(file_info['path'].parent):
                        file_info['item'].setCheckState(0, Qt.CheckState.Checked)
                        selected_count += 1
        
        if mode == "oldest":
            self.status_label.setText(f"{selected_count} älteste Dateien ausgewählt (neueste behalten).")
        elif mode == "smallest":
            self.status_label.setText(f"{selected_count} kleinste Dateien ausgewählt (größte behalten).")
        elif mode == "by_folder":
            self.status_label.setText(f"{selected_count} Dateien in '{folder_filter}' ausgewählt.")

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
        
        # Initialize backup scheduler
        from .scheduler import BackupScheduler
        schedules_file = self.services.data_dir / "backup_schedules.json"
        self.scheduler = BackupScheduler(self.services, schedules_file)
        self.scheduler.schedule_triggered.connect(self._on_scheduled_backup)

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def create_view(self) -> QWidget:
        if not self._widget:
            self._widget = FileManagerWidget(self)
            self._widget.set_enabled(self._active)
            self._widget.refresh_schedule_profile_list()
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
        # Stop all scheduled backups
        self.scheduler.stop_all()

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

        # Start global progress tracking
        task_id = self.services.progress.start_task(
            title=f"Duplikat-Scan: {root.name}",
            total=1  # Will be updated once we know total files
        )
        logger.info(f"🔍 Starting duplicate scan: {root}")

        def progress(path: Path, processed: int, total: int) -> None:
            logger.debug("Duplicate scan progress %s (%s/%s)", path, processed, total)
            current_widget = self._widget
            if current_widget:
                current_widget.scan_progress.emit(str(path), processed, total)
            
            # Update global progress
            status = f"Scanne: {path.name} ({processed}/{total})"
            self.services.progress.update(task_id, processed, max(1, total), status)

        future = self._executor.submit(self._scanner.scan, root, progress)

        def _handle_future(completed: concurrent.futures.Future[List[DuplicateGroup]]) -> None:
            try:
                result = completed.result()
                self.services.progress.complete(task_id, success=True)
                total_duplicates = sum(len(group.entries) for group in result)
                logger.info(f"✅ Duplicate scan completed: {len(result)} groups, {total_duplicates} total files")
            except Exception as exc:  # pragma: no cover - passes error via UI
                self.services.progress.complete(task_id, success=False)
                if self._widget:
                    self._widget.scan_failed.emit(str(exc))
                self.services.logger.exception("❌ Duplicate scan failed for %s", root)
                return
            if self._widget:
                self._widget.scan_completed.emit(result)

        future.add_done_callback(_handle_future)

    # ------------------------------------------------------------------
    # Backup orchestration
    # ------------------------------------------------------------------
    def run_backup(self, source: Path, target: Path, mirror: bool, dry_run: bool = False) -> None:
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

        # Start global progress tracking
        mode_str = "Dry-Run" if dry_run else "Backup"
        task_id = self.services.progress.start_task(
            title=f"{mode_str}: {source.name} → {target.name}",
            total=max(1, total_files)
        )
        logger.info(f"🔄 Starting backup: {source} → {target} ({total_files} files, mirror={mirror}, dry_run={dry_run})")

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
                    
                    # Update global progress
                    status = f"Verarbeitet: {processed}/{total_files}"
                    if ":" in message:
                        filename = message.split(":", 1)[1].strip()
                        status = f"{filename} ({processed}/{total_files})"
                    self.services.progress.update(task_id, processed, max(1, total_files), status)

        future: concurrent.futures.Future[BackupResult] = self._executor.submit(
            self._execute_backup, source, target, mirror, progress, dry_run
        )

        def _handle_future(completed: concurrent.futures.Future[BackupResult]) -> None:
            widget = self._widget
            try:
                result = completed.result()
                
                # Complete global progress successfully
                self.services.progress.complete(task_id, success=True)
                
            except Exception as exc:  # pragma: no cover - passes error via UI
                logger.exception("Backup fehlgeschlagen: %s -> %s", source, target)
                
                # Mark global progress as failed
                self.services.progress.complete(task_id, success=False)
                
                if widget:
                    widget.backup_completed.emit(False, str(exc))
                return

            summary = (
                f"Kopiert: {result.copied_files}, Übersprungen: {result.skipped_files}, "
                f"Entfernt: {result.removed_files}, Volumen: {FileManagerWidget._format_size(result.total_bytes_copied)}, "
                f"Dauer: {result.duration_seconds:.1f}s"
            )
            logger.info("✅ Backup abgeschlossen: %s", summary)
            if widget:
                widget.backup_completed.emit(True, summary)

        future.add_done_callback(_handle_future)
    
    def _on_scheduled_backup(self, profile_name: str, schedule_id: str) -> None:
        """
        Handle scheduled backup trigger.
        
        Args:
            profile_name: Name of backup profile to execute
            schedule_id: Identifier of the schedule that triggered
        """
        logger.info(f"Scheduled backup triggered: {profile_name} (schedule: {schedule_id})")
        
        # Notify user
        self.services.send_notification(
            f"Automatisches Backup gestartet: {profile_name}",
            level="info",
            source=self.manifest.identifier
        )
        
        # Load profile configuration
        profiles_file = self.services.data_dir / "backup_profiles.json"
        if not profiles_file.exists():
            logger.error(f"Profile file not found for scheduled backup: {profile_name}")
            self.services.send_notification(
                f"Backup-Profil '{profile_name}' nicht gefunden",
                level="error",
                source=self.manifest.identifier
            )
            return
        
        try:
            import json
            with open(profiles_file, "r", encoding="utf-8") as f:
                profiles = json.load(f)
            
            if profile_name not in profiles:
                logger.error(f"Profile '{profile_name}' not found in profiles file")
                self.services.send_notification(
                    f"Backup-Profil '{profile_name}' existiert nicht mehr",
                    level="error",
                    source=self.manifest.identifier
                )
                return
            
            settings = profiles[profile_name]
            source = Path(settings["source"])
            target = Path(settings["target"])
            mirror = settings.get("mirror", False)
            
            # Validate paths
            if not source.exists() or not source.is_dir():
                logger.error(f"Scheduled backup source invalid: {source}")
                self.services.send_notification(
                    f"Backup-Quelle nicht gefunden: {source}",
                    level="error",
                    source=self.manifest.identifier
                )
                return
            
            # Log to UI if widget is available
            if self._widget:
                self._widget.backup_log.append(f"\n⏰ Geplantes Backup: {profile_name}")
                self._widget.backup_log.append(f"Quelle: {source}")
                self._widget.backup_log.append(f"Ziel: {target}")
                self._widget.backup_log.append(f"Spiegel-Modus: {'Ja' if mirror else 'Nein'}\n")
            
            # Execute backup
            self.run_backup(source, target, mirror, dry_run=False)
            
        except Exception as exc:
            logger.exception(f"Failed to execute scheduled backup: {profile_name}")
            self.services.send_notification(
                f"Geplantes Backup fehlgeschlagen: {exc}",
                level="error",
                source=self.manifest.identifier
            )

    @staticmethod
    def _execute_backup(
        source: Path,
        target: Path,
        mirror: bool,
        progress: Callable[[str], None],
        dry_run: bool = False,
    ) -> BackupResult:
        return perform_backup(source, target, mirror, progress, dry_run)


Plugin = FileManagerPlugin
