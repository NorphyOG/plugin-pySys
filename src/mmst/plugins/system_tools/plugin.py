from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.plugin_base import BasePlugin, PluginManifest
from .converter import ConversionJob, ConversionResult, FileConverter
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
        self._widget: Optional[ConverterWidget] = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._active = False
        self._detector = ToolDetector()
        self._converter = FileConverter()

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def create_view(self) -> QWidget:
        if not self._widget:
            self._widget = ConverterWidget(self)
            self._widget.set_enabled(self._active)
            self._widget.refresh_tools()
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
        self._executor.shutdown(wait=False)

    # Tool detection
    def detect_tools(self) -> Dict[str, Tool]:
        return self._detector.detect_all()

    # Conversion orchestration
    def run_conversion(self, source: Path, target: Path, target_format: str) -> None:
        if not self._active:
            if self._widget:
                self._widget.conversion_finished.emit(False, "Plugin ist nicht aktiv.")
            return

        source_format = source.suffix.lstrip(".")
        category = infer_format(source)
        
        if category in {"audio", "video"}:
            tool = "ffmpeg"
        elif category == "image":
            tool = "imagemagick"
        else:
            if self._widget:
                self._widget.conversion_finished.emit(False, "Unbekanntes Dateiformat.")
            return

        # Check tool availability
        tool_info = self._detector.detect(tool)
        if not tool_info.available:
            if self._widget:
                msg = f"{tool.capitalize()} ist nicht installiert. Bitte installiere es zuerst."
                self._widget.conversion_finished.emit(False, msg)
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
            if self._widget:
                self._widget.conversion_progress.emit(message)

        future = self._executor.submit(self._converter.convert, job, progress)

        def _done(f: concurrent.futures.Future[ConversionResult]) -> None:
            try:
                result = f.result()
            except Exception as exc:
                if self._widget:
                    self._widget.conversion_finished.emit(False, f"Fehler: {exc}")
                return

            if self._widget:
                self._widget.conversion_finished.emit(result.success, result.message)

        future.add_done_callback(_done)


Plugin = SystemToolsPlugin
