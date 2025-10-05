from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Callable, Dict, List, Optional
import time
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.plugin_base import BasePlugin, PluginManifest
from .converter import ConversionJob, ConversionResult, FileConverter
from .image_compression import ImageCompressionWidget
from .disk_monitor import DiskMonitorWidget, DiskMonitor
from .temp_cleaner import TempCleaner, ScanResult
from .tools import CONVERSION_FORMATS, Tool, ToolDetector, get_supported_formats, infer_format


class ConverterWidget(QWidget):
    conversion_started = Signal()
    conversion_progress = Signal(str)
    conversion_finished = Signal(bool, str)

    def __init__(self, plugin: "SystemToolsPlugin") -> None:
        super().__init__()
        self._plugin = plugin
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Tool status
        status_group = QGroupBox("Verfügbare Tools")
        status_layout = QFormLayout(status_group)
        self.tool_labels: Dict[str, QLabel] = {}
        for tool_name in ["ffmpeg", "imagemagick"]:
            label = QLabel("Prüfe...")
            self.tool_labels[tool_name] = label
            status_layout.addRow(tool_name.capitalize(), label)
        layout.addWidget(status_group)

        # Conversion controls
        conv_group = QGroupBox("Dateikonverter")
        conv_layout = QFormLayout(conv_group)

        self.source_edit = QLineEdit()
        source_button = QPushButton("Datei wählen")
        source_button.clicked.connect(self._pick_source)
        source_row = QWidget()
        source_row_layout = QHBoxLayout(source_row)
        source_row_layout.setContentsMargins(0, 0, 0, 0)
        source_row_layout.addWidget(self.source_edit, stretch=1)
        source_row_layout.addWidget(source_button)
        conv_layout.addRow("Quelle", source_row)

        self.format_combo = QComboBox()
        conv_layout.addRow("Zielformat", self.format_combo)

        # Preset controls
        preset_row = QWidget()
        preset_layout = QHBoxLayout(preset_row)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("-- Preset wählen --")
        self.preset_combo.currentIndexChanged.connect(self._load_preset)
        preset_layout.addWidget(self.preset_combo, stretch=1)
        
        save_preset_button = QPushButton("💾")
        save_preset_button.setToolTip("Preset speichern")
        save_preset_button.setMaximumWidth(40)
        save_preset_button.clicked.connect(self._save_preset)
        preset_layout.addWidget(save_preset_button)
        
        delete_preset_button = QPushButton("🗑️")
        delete_preset_button.setToolTip("Preset löschen")
        delete_preset_button.setMaximumWidth(40)
        delete_preset_button.clicked.connect(self._delete_preset)
        preset_layout.addWidget(delete_preset_button)
        
        conv_layout.addRow("Preset", preset_row)

        self.target_edit = QLineEdit()
        target_button = QPushButton("Ziel wählen")
        target_button.clicked.connect(self._pick_target)
        target_row = QWidget()
        target_row_layout = QHBoxLayout(target_row)
        target_row_layout.setContentsMargins(0, 0, 0, 0)
        target_row_layout.addWidget(self.target_edit, stretch=1)
        target_row_layout.addWidget(target_button)
        conv_layout.addRow("Ziel", target_row)

        self.convert_button = QPushButton("Konvertieren")
        self.convert_button.clicked.connect(self._start_conversion)
        conv_layout.addRow(self.convert_button)

        layout.addWidget(conv_group)

        # Log
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(200)
        layout.addWidget(self.log)

        layout.addStretch(1)

        # Signals
        self.conversion_progress.connect(self._on_progress)
        self.conversion_finished.connect(self._on_finished)
        
        # Load presets
        self._load_presets_list()

    def _load_presets_list(self) -> None:
        """Load saved presets into the combo box."""
        presets_file = self._plugin.services.data_dir / "conversion_presets.json"
        self.preset_combo.clear()
        self.preset_combo.addItem("-- Preset wählen --")
        
        if not presets_file.exists():
            return
        
        try:
            import json
            with open(presets_file, "r", encoding="utf-8") as f:
                presets = json.load(f)
            
            for preset_name in sorted(presets.keys()):
                self.preset_combo.addItem(preset_name)
        except Exception as exc:
            QMessageBox.warning(self, "Fehler", f"Presets konnten nicht geladen werden: {exc}")
    
    def _save_preset(self) -> None:
        """Save current format selection as a named preset."""
        from PySide6.QtWidgets import QInputDialog
        
        # Get current format selection
        if self.format_combo.currentIndex() < 0:
            QMessageBox.warning(self, "Fehler", "Bitte wählen Sie zuerst ein Zielformat aus.")
            return
        
        format_ext = self.format_combo.currentData()
        format_name = self.format_combo.currentText()
        
        if not format_ext:
            QMessageBox.warning(self, "Fehler", "Ungültiges Format.")
            return
        
        # Prompt for preset name
        preset_name, ok = QInputDialog.getText(
            self, "Preset speichern", "Presetname:", text=format_name
        )
        
        if not ok or not preset_name.strip():
            return
        
        preset_name = preset_name.strip()
        presets_file = self._plugin.services.data_dir / "conversion_presets.json"
        
        # Load existing presets
        presets = {}
        if presets_file.exists():
            try:
                import json
                with open(presets_file, "r", encoding="utf-8") as f:
                    presets = json.load(f)
            except Exception:
                pass
        
        # Save preset
        presets[preset_name] = {
            "format": format_ext,
            "display_name": format_name
        }
        
        # Write back to disk
        try:
            import json
            presets_file.parent.mkdir(parents=True, exist_ok=True)
            with open(presets_file, "w", encoding="utf-8") as f:
                json.dump(presets, f, indent=2, ensure_ascii=False)
            
            self._load_presets_list()
            # Select the newly saved preset
            index = self.preset_combo.findText(preset_name)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
            
            QMessageBox.information(self, "Erfolg", f"Preset '{preset_name}' gespeichert.")
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", f"Preset konnte nicht gespeichert werden: {exc}")
    
    def _load_preset(self, index: int) -> None:
        """Load a preset and set the format combo."""
        if index <= 0:  # Skip placeholder
            return
        
        preset_name = self.preset_combo.itemText(index)
        presets_file = self._plugin.services.data_dir / "conversion_presets.json"
        
        if not presets_file.exists():
            return
        
        try:
            import json
            with open(presets_file, "r", encoding="utf-8") as f:
                presets = json.load(f)
            
            if preset_name in presets:
                preset = presets[preset_name]
                target_ext = preset.get("format", "")
                
                # Find and select the matching format in combo
                for i in range(self.format_combo.count()):
                    if self.format_combo.itemData(i) == target_ext:
                        self.format_combo.setCurrentIndex(i)
                        
                        # Auto-update target if source is set
                        source_text = self.source_edit.text().strip()
                        if source_text:
                            source = Path(source_text)
                            target = source.with_suffix(f".{target_ext}")
                            self.target_edit.setText(str(target))
                        break
        except Exception as exc:
            QMessageBox.warning(self, "Fehler", f"Preset konnte nicht geladen werden: {exc}")
    
    def _delete_preset(self) -> None:
        """Delete the currently selected preset."""
        index = self.preset_combo.currentIndex()
        if index <= 0:  # Skip placeholder
            QMessageBox.information(self, "Hinweis", "Bitte wählen Sie ein Preset zum Löschen aus.")
            return
        
        preset_name = self.preset_combo.itemText(index)
        reply = QMessageBox.question(
            self,
            "Preset löschen",
            f"Preset '{preset_name}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        presets_file = self._plugin.services.data_dir / "conversion_presets.json"
        
        try:
            import json
            with open(presets_file, "r", encoding="utf-8") as f:
                presets = json.load(f)
            
            if preset_name in presets:
                del presets[preset_name]
            
            with open(presets_file, "w", encoding="utf-8") as f:
                json.dump(presets, f, indent=2, ensure_ascii=False)
            
            self._load_presets_list()
            QMessageBox.information(self, "Erfolg", f"Preset '{preset_name}' gelöscht.")
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", f"Preset konnte nicht gelöscht werden: {exc}")

    def refresh_tools(self) -> None:
        tools = self._plugin.detect_tools()
        for name, tool in tools.items():
            label = self.tool_labels.get(name)
            if label:
                if tool.available:
                    version = tool.version if tool.version else "unbekannt"
                    label.setText(f"✓ Verfügbar ({version})")
                    label.setStyleSheet("color: green;")
                else:
                    label.setText("✗ Nicht gefunden")
                    label.setStyleSheet("color: red;")

    def _pick_source(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Quelldatei wählen")
        if filename:
            self.source_edit.setText(filename)
            self._update_formats(Path(filename))

    def _update_formats(self, source: Path) -> None:
        category = infer_format(source)
        self.format_combo.clear()
        
        if category == "audio" or category == "video":
            tool = "ffmpeg"
        elif category == "image":
            tool = "imagemagick"
        else:
            self.format_combo.addItem("Unbekanntes Format")
            return

        formats = get_supported_formats(tool)
        for fmt in formats:
            self.format_combo.addItem(f"{fmt.display_name} (.{fmt.extension})", fmt.extension)

        # Auto-suggest target
        if self.format_combo.count() > 0:
            first_ext = self.format_combo.itemData(0)
            target = source.with_suffix(f".{first_ext}")
            self.target_edit.setText(str(target))

    def _pick_target(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(self, "Zieldatei wählen")
        if filename:
            self.target_edit.setText(filename)

    def _start_conversion(self) -> None:
        source = self.source_edit.text().strip()
        target = self.target_edit.text().strip()
        
        if not source or not target:
            QMessageBox.warning(self, "Fehler", "Bitte Quelle und Ziel wählen.")
            return

        target_ext = self.format_combo.currentData()
        if not target_ext:
            QMessageBox.warning(self, "Fehler", "Bitte Zielformat wählen.")
            return

        self.log.clear()
        self.log.appendPlainText(f"Starte Konvertierung: {source} → {target}")
        self.convert_button.setEnabled(False)
        self._plugin.run_conversion(Path(source), Path(target), str(target_ext))

    def _on_progress(self, message: str) -> None:
        self.log.appendPlainText(message)

    def _on_finished(self, success: bool, message: str) -> None:
        self.log.appendPlainText(message)
        self.convert_button.setEnabled(True)
        if success:
            QMessageBox.information(self, "Erfolg", message)
        else:
            QMessageBox.critical(self, "Fehler", message)

    def set_enabled(self, enabled: bool) -> None:
        self.setEnabled(enabled)


class BatchQueueWidget(QWidget):
    """Widget for batch conversion queue management."""
    
    queue_started = Signal()
    queue_item_progress = Signal(int, str)  # index, message
    queue_finished = Signal(int, int)  # succeeded, failed
    
    def __init__(self, plugin: "SystemToolsPlugin") -> None:
        super().__init__()
        self._plugin = plugin
        self._queue_jobs: List[ConversionJob] = []
        self._processing = False
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Queue controls
        controls_group = QGroupBox("Warteschlange")
        controls_layout = QVBoxLayout(controls_group)
        
        buttons_layout = QHBoxLayout()
        self.add_files_button = QPushButton("📁 Dateien hinzufügen")
        self.add_files_button.clicked.connect(self._add_files)
        buttons_layout.addWidget(self.add_files_button)
        
        self.clear_button = QPushButton("🗑️ Leeren")
        self.clear_button.clicked.connect(self._clear_queue)
        buttons_layout.addWidget(self.clear_button)
        
        self.remove_button = QPushButton("❌ Auswahl entfernen")
        self.remove_button.clicked.connect(self._remove_selected)
        buttons_layout.addWidget(self.remove_button)
        buttons_layout.addStretch()
        controls_layout.addLayout(buttons_layout)
        
        # Queue list
        self.queue_list = QListWidget()
        self.queue_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        controls_layout.addWidget(self.queue_list)
        
        # Queue info
        info_layout = QHBoxLayout()
        self.queue_info_label = QLabel("0 Dateien in Warteschlange")
        info_layout.addWidget(self.queue_info_label)
        info_layout.addStretch()
        controls_layout.addLayout(info_layout)
        
        layout.addWidget(controls_group)
        
        # Processing controls
        process_group = QGroupBox("Verarbeitung")
        process_layout = QVBoxLayout(process_group)
        
        # Format selection
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Zielformat:"))
        self.batch_format_combo = QComboBox()
        format_layout.addWidget(self.batch_format_combo, stretch=1)
        process_layout.addLayout(format_layout)
        
        # Process button
        self.process_button = QPushButton("▶️ Verarbeitung starten")
        self.process_button.clicked.connect(self._start_processing)
        self.process_button.setEnabled(False)
        process_layout.addWidget(self.process_button)
        
        # Progress
        self.batch_progress = QProgressBar()
        self.batch_progress.setVisible(False)
        process_layout.addWidget(self.batch_progress)
        
        self.batch_status_label = QLabel("")
        process_layout.addWidget(self.batch_status_label)
        
        layout.addWidget(process_group)
        
        # Log
        self.batch_log = QPlainTextEdit()
        self.batch_log.setReadOnly(True)
        self.batch_log.setMaximumHeight(150)
        layout.addWidget(self.batch_log)
        
        layout.addStretch(1)
        
        # Signals
        self.queue_item_progress.connect(self._on_item_progress)
        self.queue_finished.connect(self._on_queue_finished)
        
        self._populate_formats()
    
    def _populate_formats(self) -> None:
        """Populate format combo with common formats."""
        # Add common formats for batch processing
        formats = [
            ("MP4 Video", "mp4", "video"),
            ("MP3 Audio", "mp3", "audio"),
            ("AAC Audio", "aac", "audio"),
            ("PNG Image", "png", "image"),
            ("JPEG Image", "jpg", "image"),
            ("WebP Image", "webp", "image"),
        ]
        for display, ext, category in formats:
            self.batch_format_combo.addItem(display, {"ext": ext, "category": category})
    
    def _add_files(self) -> None:
        """Add files to the conversion queue."""
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Dateien zur Warteschlange hinzufügen"
        )
        
        if not filenames:
            return
        
        for filename in filenames:
            source = Path(filename)
            # Create default target path (same folder, new extension)
            format_data = self.batch_format_combo.currentData()
            if format_data:
                target = source.with_suffix(f".{format_data['ext']}")
                
                # Create a conversion job
                category = infer_format(source)
                source_format = source.suffix.lstrip(".")
                
                # Determine tool
                if category in {"audio", "video"}:
                    tool = "ffmpeg"
                elif category == "image":
                    tool = "imagemagick"
                else:
                    self.batch_log.appendPlainText(f"⚠️ Überspringe unbekanntes Format: {source.name}")
                    continue
                
                job = ConversionJob(
                    source=source,
                    target=target,
                    source_format=source_format,
                    target_format=format_data["ext"],
                    tool=tool,
                    command_path=None,  # Will be resolved at runtime
                )
                self._queue_jobs.append(job)
                
                # Add to list widget
                item = QListWidgetItem(f"⏳ {source.name} → {target.name}")
                self.queue_list.addItem(item)
        
        self._update_queue_info()
    
    def _clear_queue(self) -> None:
        """Clear all items from the queue."""
        if self._processing:
            QMessageBox.warning(self, "Hinweis", "Verarbeitung läuft. Bitte warten.")
            return
        
        self._queue_jobs.clear()
        self.queue_list.clear()
        self._update_queue_info()
    
    def _remove_selected(self) -> None:
        """Remove selected items from the queue."""
        if self._processing:
            QMessageBox.warning(self, "Hinweis", "Verarbeitung läuft. Bitte warten.")
            return
        
        # Get selected indices in reverse order
        selected_items = self.queue_list.selectedItems()
        for item in selected_items:
            index = self.queue_list.row(item)
            self.queue_list.takeItem(index)
            if 0 <= index < len(self._queue_jobs):
                self._queue_jobs.pop(index)
        
        self._update_queue_info()
    
    def _update_queue_info(self) -> None:
        """Update queue information label."""
        count = len(self._queue_jobs)
        self.queue_info_label.setText(f"{count} Datei{'en' if count != 1 else ''} in Warteschlange")
        self.process_button.setEnabled(count > 0 and not self._processing)
    
    def _start_processing(self) -> None:
        """Start batch processing all items in the queue."""
        if not self._queue_jobs:
            return
        
        self._processing = True
        self.process_button.setEnabled(False)
        self.add_files_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        
        self.batch_progress.setVisible(True)
        self.batch_progress.setRange(0, len(self._queue_jobs))
        self.batch_progress.setValue(0)
        
        self.batch_log.clear()
        self.batch_log.appendPlainText(f"🚀 Starte Verarbeitung von {len(self._queue_jobs)} Datei(en)...\n")
        
        # Start processing in plugin
        self._plugin.run_batch_queue(self._queue_jobs.copy())
    
    def _on_item_progress(self, index: int, message: str) -> None:
        """Update progress for a specific queue item."""
        self.batch_log.appendPlainText(message)
        self.batch_progress.setValue(index + 1)
        self.batch_status_label.setText(f"Verarbeite {index + 1}/{len(self._queue_jobs)}...")
        
        # Update list item icon
        if index < self.queue_list.count():
            item = self.queue_list.item(index)
            if item:
                text = item.text()
                if "✅" in message or "Erfolg" in message:
                    item.setText(text.replace("⏳", "✅"))
                elif "❌" in message or "Fehler" in message:
                    item.setText(text.replace("⏳", "❌"))
    
    def _on_queue_finished(self, succeeded: int, failed: int) -> None:
        """Called when batch processing is complete."""
        self._processing = False
        self.process_button.setEnabled(True)
        self.add_files_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.remove_button.setEnabled(True)
        
        self.batch_progress.setVisible(False)
        self.batch_status_label.setText("")
        
        total = succeeded + failed
        self.batch_log.appendPlainText(
            f"\n✨ Verarbeitung abgeschlossen: {succeeded}/{total} erfolgreich, {failed} fehlgeschlagen."
        )
        
        QMessageBox.information(
            self,
            "Verarbeitung abgeschlossen",
            f"{succeeded}/{total} Dateien erfolgreich konvertiert.\n{failed} Fehler.",
        )
    
    def set_enabled(self, enabled: bool) -> None:
        self.setEnabled(enabled)


class SystemToolsPlugin(BasePlugin):
    IDENTIFIER = "mmst.system_tools"

    def __init__(self, services) -> None:
        super().__init__(services)
        self._manifest = PluginManifest(
            identifier=self.IDENTIFIER,
            name="System Tools",
            description="Dateikonverter und Systemdiagnose",
            version="0.1.0",
            author="MMST Team",
            tags=("system", "converter", "tools"),
        )
        self._widget: Optional[QTabWidget] = None
        self._converter_widget: Optional[ConverterWidget] = None
        self._batch_widget: Optional[BatchQueueWidget] = None
        self._compression_widget: Optional[ImageCompressionWidget] = None
        self._disk_monitor_widget: Optional[DiskMonitorWidget] = None
        # Temp cleaner components
        self._temp_cleaner_widget: Optional[QWidget] = None
        self._temp_cleaner_backend = TempCleaner()
        self._temp_cleaner_last_scan: Optional[ScanResult] = None

        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._active = False
        self._detector = ToolDetector()
        self._converter = FileConverter()
        self._disk_monitor_timer: Optional[QTimer] = None

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def create_view(self) -> QWidget:
        if not self._widget:
            # Create tab widget
            self._widget = QTabWidget()
            
            # Create converter tab
            self._converter_widget = ConverterWidget(self)
            self._converter_widget.set_enabled(self._active)
            self._converter_widget.refresh_tools()
            self._widget.addTab(self._converter_widget, "🔄 Einzelkonvertierung")
            
            # Create batch queue tab
            self._batch_widget = BatchQueueWidget(self)
            self._batch_widget.set_enabled(self._active)
            self._widget.addTab(self._batch_widget, "📋 Batch-Warteschlange")
            
            # Create image compression tab
            self._compression_widget = ImageCompressionWidget(self)
            self._compression_widget.set_enabled(self._active)
            self._widget.addTab(self._compression_widget, "🖼️ Bild-Komprimierung")
            
            # Create disk monitor tab
            self._disk_monitor_widget = DiskMonitorWidget()
            self._disk_monitor_widget.set_enabled(self._active)
            self._widget.addTab(self._disk_monitor_widget, "💾 Disk Monitor")

            # Create temp cleaner tab
            self._temp_cleaner_widget = self._create_temp_cleaner_tab()
            self._temp_cleaner_widget.setEnabled(self._active)
            self._widget.addTab(self._temp_cleaner_widget, "🧹 Temp Cleaner")
            # Restore persisted temp cleaner state
            self._restore_temp_cleaner_state()
        
        return self._widget

    def start(self) -> None:
        self._active = True
        if self._converter_widget:
            self._converter_widget.set_enabled(True)
        if self._batch_widget:
            self._batch_widget.set_enabled(True)
        if self._compression_widget:
            self._compression_widget.set_enabled(True)
        if self._disk_monitor_widget:
            self._disk_monitor_widget.set_enabled(True)
        if self._temp_cleaner_widget:
            self._temp_cleaner_widget.setEnabled(True)
        
        self._start_monitoring()

    def stop(self) -> None:
        self._active = False
        if self._converter_widget:
            self._converter_widget.set_enabled(False)
        if self._batch_widget:
            self._batch_widget.set_enabled(False)
        if self._compression_widget:
            self._compression_widget.set_enabled(False)
        if self._disk_monitor_widget:
            self._disk_monitor_widget.set_enabled(False)
        if self._temp_cleaner_widget:
            self._temp_cleaner_widget.setEnabled(False)
            
        self._stop_monitoring()
        # Persist temp cleaner state
        self._persist_temp_cleaner_state()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)
        self._stop_monitoring()

    def _start_monitoring(self):
        """Start the background disk monitoring timer."""
        if self._disk_monitor_timer is None:
            self._disk_monitor_timer = QTimer()
            self._disk_monitor_timer.timeout.connect(self._check_disk_health)
            # Check every 15 minutes
            self._disk_monitor_timer.start(15 * 60 * 1000) 
            # Also run once on startup
            self._check_disk_health()

    def _stop_monitoring(self):
        """Stop the background disk monitoring timer."""
        if self._disk_monitor_timer:
            self._disk_monitor_timer.stop()
            self._disk_monitor_timer = None

    def _check_disk_health(self):
        """Periodically check disk health and send notifications on issues."""
        monitor = DiskMonitor()
        if not monitor.is_available:
            return

        def check():
            disks = monitor.get_disks()
            for disk in disks:
                summary = monitor.get_health_summary(disk.index)
                status = summary.get("status")

                if status == "CRITICAL":
                    message = f"Kritisches Problem bei Festplatte {disk.model}: {', '.join(summary.get('critical', []))}"
                    self.services.send_notification(
                        message,
                        level="critical",
                        source=self.IDENTIFIER
                    )
                elif status == "WARNING":
                    message = f"Warnung bei Festplatte {disk.model}: {', '.join(summary.get('warnings', []))}"
                    self.services.send_notification(
                        message,
                        level="warning",
                        source=self.IDENTIFIER
                    )
        
        self._executor.submit(check)

    # Tool detection
    def detect_tools(self) -> Dict[str, Tool]:
        return self._detector.detect_all()

    # Conversion orchestration
    def run_conversion(self, source: Path, target: Path, target_format: str) -> None:
        if not self._active:
            if self._converter_widget:
                self._converter_widget.conversion_finished.emit(False, "Plugin ist nicht aktiv.")
            return

        source_format = source.suffix.lstrip(".")
        category = infer_format(source)
        
        if category in {"audio", "video"}:
            tool = "ffmpeg"
        elif category == "image":
            tool = "imagemagick"
        else:
            if self._converter_widget:
                self._converter_widget.conversion_finished.emit(False, "Unbekanntes Dateiformat.")
            return

        # Check tool availability
        tool_info = self._detector.detect(tool)
        if not tool_info.available:
            if self._converter_widget:
                msg = f"{tool.capitalize()} ist nicht installiert. Bitte installiere es zuerst."
                self._converter_widget.conversion_finished.emit(False, msg)
            return

        job = ConversionJob(
            source=source,
            target=target,
            source_format=source_format,
            target_format=target_format,
            tool=tool,
            command_path=Path(tool_info.path) if tool_info.path else None,
        )

        def progress(message: str) -> None:
            if self._converter_widget:
                self._converter_widget.conversion_progress.emit(message)

        future = self._executor.submit(self._converter.convert, job, progress)

        def _done(f: concurrent.futures.Future[ConversionResult]) -> None:
            try:
                result = f.result()
            except Exception as exc:
                if self._converter_widget:
                    self._converter_widget.conversion_finished.emit(False, f"Fehler: {exc}")
                return

            if self._converter_widget:
                self._converter_widget.conversion_finished.emit(result.success, result.message)

        future.add_done_callback(_done)

    # -------------------- Temp Cleaner --------------------
    def _create_temp_cleaner_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Category list
        category_group = QGroupBox("Kategorien")
        cat_layout = QVBoxLayout(category_group)
        from PySide6.QtWidgets import QCheckBox
        self._temp_cat_checkboxes: Dict[str, QCheckBox] = {}
        for key, display in self._temp_cleaner_backend.list_categories():
            cb = QCheckBox(display)
            cb.setChecked(True)
            self._temp_cat_checkboxes[key] = cb
            cat_layout.addWidget(cb)
        layout.addWidget(category_group)

        # Buttons
        button_row = QHBoxLayout()
        self._temp_scan_button = QPushButton("Scannen")
        self._temp_scan_button.clicked.connect(self._run_temp_scan)
        button_row.addWidget(self._temp_scan_button)
        self._temp_delete_button = QPushButton("Löschen (Dry Run)")
        self._temp_delete_button.clicked.connect(lambda: self._run_temp_delete(dry_run=True))
        self._temp_delete_button.setEnabled(False)
        button_row.addWidget(self._temp_delete_button)
        self._temp_delete_real_button = QPushButton("Löschen (Echt)")
        self._temp_delete_real_button.clicked.connect(lambda: self._run_temp_delete(dry_run=False))
        self._temp_delete_real_button.setEnabled(False)
        button_row.addWidget(self._temp_delete_real_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        # Summary + log
        self._temp_summary_label = QLabel("Noch kein Scan durchgeführt.")
        layout.addWidget(self._temp_summary_label)
        self._temp_log = QPlainTextEdit()
        self._temp_log.setReadOnly(True)
        self._temp_log.setMaximumBlockCount(1000)
        layout.addWidget(self._temp_log, stretch=1)

        return widget

    def _selected_temp_categories(self) -> List[str]:
        return [k for k, cb in self._temp_cat_checkboxes.items() if cb.isChecked()]

    def _run_temp_scan(self) -> None:
        if not self._active:
            return
        cats = self._selected_temp_categories()
        self._temp_log.appendPlainText(f"🔍 Starte Scan für {len(cats)} Kategorien...")
        self._temp_scan_button.setEnabled(False)

        def do_scan():
            result = self._temp_cleaner_backend.scan(selected_categories=cats)
            return result

        future = self._executor.submit(do_scan)

        def done(f: concurrent.futures.Future[ScanResult]):
            try:
                self._temp_cleaner_last_scan = f.result()
            except Exception as exc:
                self._temp_log.appendPlainText(f"❌ Scan fehlgeschlagen: {exc}")
            else:
                sr = self._temp_cleaner_last_scan
                if sr:
                    self._temp_summary_label.setText(
                        f"{sr.total_files} Dateien, Gesamtgröße: {self._format_size(sr.total_size)} in {len(sr.categories)} Kategorien (Dauer {sr.duration_seconds:.2f}s)"
                    )
                    for key, cat in sr.categories.items():
                        self._temp_log.appendPlainText(
                            f"[{cat.display}] {len(cat.files)} Dateien, {self._format_size(cat.total_size)}"
                        )
                    self._temp_delete_button.setEnabled(sr.total_files > 0)
                    self._temp_delete_real_button.setEnabled(sr.total_files > 0)
                    # Persist summary
                    self._persist_temp_cleaner_state(summary_only=True)
            finally:
                self._temp_scan_button.setEnabled(True)

        future.add_done_callback(lambda f: done(f))

    def _run_temp_delete(self, dry_run: bool) -> None:
        if not self._active or not self._temp_cleaner_last_scan:
            return
        scan = self._temp_cleaner_last_scan
        self._temp_log.appendPlainText("🧹 Lösche Dateien..." + (" (Dry Run)" if dry_run else ""))
        self._temp_delete_button.setEnabled(False)
        self._temp_delete_real_button.setEnabled(False)

        cats = self._selected_temp_categories()

        def do_delete():
            return self._temp_cleaner_backend.delete(scan, dry_run=dry_run, categories=cats)

        future = self._executor.submit(do_delete)

        def done(f: concurrent.futures.Future[dict]):
            try:
                report = f.result()
            except Exception as exc:
                self._temp_log.appendPlainText(f"❌ Löschen fehlgeschlagen: {exc}")
            else:
                total_removed = 0
                total_size = 0
                for key, stats in report.items():
                    cat = scan.categories.get(key)
                    if not cat:
                        continue
                    removed_files = stats['files']
                    removed_size = stats['size']
                    total_removed += removed_files
                    total_size += removed_size
                    self._temp_log.appendPlainText(
                        f"[{cat.display}] Entfernt: {removed_files} Dateien, {self._format_size(removed_size)} {'(Dry Run)' if dry_run else ''}"
                    )
                self._temp_log.appendPlainText(
                    f"Gesamt entfernt: {total_removed} Dateien, {self._format_size(total_size)} {'(Dry Run)' if dry_run else ''}"
                )
                if not dry_run:
                    # Re-run scan automatically to refresh view
                    self._run_temp_scan()
                else:
                    self._temp_delete_real_button.setEnabled(total_removed > 0)
                # Persist after delete
                self._persist_temp_cleaner_state(summary_only=True)
            finally:
                self._temp_delete_button.setEnabled(True)
                if dry_run:
                    self._temp_delete_real_button.setEnabled(True)

        future.add_done_callback(lambda f: done(f))

    def _format_size(self, size: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        value = float(size)
        for unit in units:
            if value < 1024.0:
                return f"{value:.2f} {unit}"
            value /= 1024.0
        return f"{value:.2f} PB"

    # -------------------- Persistence (Temp Cleaner) --------------------
    def _persist_temp_cleaner_state(self, summary_only: bool = False) -> None:
        try:
            cfg = self.services.get_plugin_config(self.IDENTIFIER) or {}
            if not summary_only:
                cfg['temp_cleaner.selected_categories'] = self._selected_temp_categories()
            if self._temp_cleaner_last_scan:
                cfg['temp_cleaner.last_summary'] = {
                    'total_files': self._temp_cleaner_last_scan.total_files,
                    'total_size': self._temp_cleaner_last_scan.total_size,
                    'timestamp': time.time(),
                }
            # Ensure we pass a plain dict (some services may return custom mapping)
            self.services.save_plugin_config(self.IDENTIFIER, dict(cfg))
        except Exception:
            pass

    def _restore_temp_cleaner_state(self) -> None:
        try:
            cfg = self.services.get_plugin_config(self.IDENTIFIER) or {}
            selected = set(cfg.get('temp_cleaner.selected_categories', []))
            if selected and hasattr(self, '_temp_cat_checkboxes'):
                for key, cb in self._temp_cat_checkboxes.items():
                    cb.setChecked(key in selected)
            last = cfg.get('temp_cleaner.last_summary')
            if last:
                self._temp_summary_label.setText(
                    f"Letzter Scan: {last.get('total_files', 0)} Dateien, {self._format_size(last.get('total_size', 0))}"
                )
        except Exception:
            pass
    
    def run_batch_queue(self, jobs: List[ConversionJob]) -> None:
        """Process a batch queue of conversion jobs sequentially."""
        if not self._active:
            if self._batch_widget:
                self._batch_widget.queue_finished.emit(0, len(jobs))
            return
        
        # Start global progress tracking
        task_id = self.services.progress.start_task(
            title=f"Batch-Konvertierung ({len(jobs)} Dateien)",
            total=len(jobs)
        )
        self.services.logger.info(f"🔄 Starting batch conversion: {len(jobs)} files")
        
        def process_queue() -> None:
            succeeded = 0
            failed = 0
            successful_conversions = []
            
            for index, job in enumerate(jobs):
                # Resolve command path
                tool_info = self._detector.detect(job.tool)
                if tool_info.available and tool_info.path:
                    job.command_path = Path(tool_info.path)
                else:
                    # Tool not available
                    if self._batch_widget:
                        self._batch_widget.queue_item_progress.emit(
                            index, f"❌ {job.source.name}: {job.tool} nicht gefunden"
                        )
                    failed += 1
                    continue
                
                # Progress callback
                def item_progress(message: str) -> None:
                    if self._batch_widget:
                        self._batch_widget.queue_item_progress.emit(index, f"  {message}")
                
                # Update global progress
                status = f"{job.source.name} → {job.target_format.upper()}"
                self.services.progress.update(task_id, index, len(jobs), status)
                
                try:
                    # Start conversion message
                    if self._batch_widget:
                        self._batch_widget.queue_item_progress.emit(
                            index, f"⏳ {job.source.name} → {job.target.name}"
                        )
                    
                    result = self._converter.convert(job, item_progress)
                    
                    if result.success:
                        succeeded += 1
                        successful_conversions.append({
                            'source': str(job.source),
                            'target': str(job.target),
                            'format': job.target_format
                        })
                        if self._batch_widget:
                            self._batch_widget.queue_item_progress.emit(
                                index, f"✅ {job.source.name}: Erfolg"
                            )
                    else:
                        failed += 1
                        if self._batch_widget:
                            self._batch_widget.queue_item_progress.emit(
                                index, f"❌ {job.source.name}: {result.message}"
                            )
                except Exception as exc:
                    failed += 1
                    if self._batch_widget:
                        self._batch_widget.queue_item_progress.emit(
                            index, f"❌ {job.source.name}: {exc}"
                        )
            
            # Emit event for successful conversions
            if successful_conversions:
                self.services.event_bus.emit('files.converted', {
                    'conversions': successful_conversions,
                    'source': 'system_tools.batch_converter'
                })
            
            # Complete global progress
            self.services.progress.complete(task_id, success=(failed == 0))
            self.services.logger.info(f"✅ Batch conversion finished: {succeeded} succeeded, {failed} failed")
            
            # Signal completion
            if self._batch_widget:
                self._batch_widget.queue_finished.emit(succeeded, failed)
        
        # Run in executor
        self._executor.submit(process_queue)
    
    def run_image_compression(
        self,
        source: Path,
        target: Path,
        target_format: str,
        quality: int,
        callback: Optional[Callable[[], None]] = None
    ) -> None:
        """Run image compression with quality setting.
        
        Args:
            source: Source image path
            target: Target image path
            target_format: Target format (jpg, png, webp)
            quality: Quality setting (1-100)
            callback: Optional callback to invoke on completion
        """
        if not self._active:
            if callback:
                callback()
            return
        
        def compress() -> None:
            try:
                # Detect ImageMagick
                tools = self.detect_tools()
                imagemagick_tool = tools.get("imagemagick")
                
                if not imagemagick_tool or not imagemagick_tool.available:
                    if callback:
                        callback()
                    return
                
                # Create conversion job
                job = ConversionJob(
                    source=source,
                    target=target,
                    source_format=source.suffix.lstrip("."),
                    target_format=target_format,
                    tool="imagemagick",
                    command_path=Path(imagemagick_tool.path) if imagemagick_tool.path else None
                )
                
                # Build ImageMagick command with quality setting
                import subprocess
                
                cmd = [
                    str(imagemagick_tool.path),
                    str(source),
                    "-quality", str(quality),
                ]
                
                # Format-specific options
                if target_format == "jpg":
                    cmd.extend(["-sampling-factor", "4:2:0"])
                elif target_format == "webp":
                    cmd.extend(["-define", f"webp:method=6"])
                
                cmd.append(str(target))
                
                # Run conversion
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0 and target.exists():
                    # Success
                    pass
                else:
                    # Failed - cleanup target if exists
                    if target.exists():
                        target.unlink()
                
            except Exception:
                # Cleanup on error
                if target.exists():
                    target.unlink()
            finally:
                if callback:
                    callback()
        
        # Run in executor
        self._executor.submit(compress)


Plugin = SystemToolsPlugin
