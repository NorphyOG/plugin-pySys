"""
Image compression widget with visual before/after comparison.

Provides a dedicated UI for compressing images with quality control,
format selection, and batch processing capabilities.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QSize  # type: ignore[import-not-found]
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from .plugin import SystemToolsPlugin


class ImagePreviewWidget(QWidget):
    """Widget to display image preview with label."""
    
    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Image label
        self.image_label = QLabel("Keine Vorschau verfügbar")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(300, 300)
        self.image_label.setStyleSheet("QLabel { background-color: #f0f0f0; border: 1px solid #ccc; }")
        layout.addWidget(self.image_label)
        
        # Info label
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.info_label)
    
    def set_image(self, path: Path) -> None:
        """Load and display an image."""
        if not path.exists():
            self.image_label.setText("Datei nicht gefunden")
            self.info_label.setText("")
            return
        
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.image_label.setText("Ungültiges Bildformat")
            self.info_label.setText("")
            return
        
        # Scale to fit while maintaining aspect ratio
        scaled = pixmap.scaled(
            400, 400,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
        
        # Show file info
        size_bytes = path.stat().st_size
        size_kb = size_bytes / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
        self.info_label.setText(f"{pixmap.width()} x {pixmap.height()} • {size_str}")
    
    def clear(self) -> None:
        """Clear the preview."""
        self.image_label.setText("Keine Vorschau verfügbar")
        self.info_label.setText("")


class CompressionPresetManager:
    """Manages compression presets."""
    
    PRESETS = {
        "Web Optimized": {"format": "jpg", "quality": 85},
        "High Quality": {"format": "jpg", "quality": 95},
        "Maximum Compression": {"format": "jpg", "quality": 60},
        "PNG Lossless": {"format": "png", "quality": 100},
        "WebP High": {"format": "webp", "quality": 90},
        "WebP Medium": {"format": "webp", "quality": 75},
    }
    
    @classmethod
    def get_preset_names(cls) -> List[str]:
        """Get list of available preset names."""
        return list(cls.PRESETS.keys())
    
    @classmethod
    def get_preset(cls, name: str) -> Optional[dict]:
        """Get preset configuration by name."""
        return cls.PRESETS.get(name)


class ImageCompressionWidget(QWidget):
    """Widget for compressing images with visual comparison."""
    
    compression_started = Signal()
    compression_progress = Signal(str)  # message
    compression_finished = Signal(bool, str)  # success, message
    
    def __init__(self, plugin: SystemToolsPlugin) -> None:
        super().__init__()
        self._plugin = plugin
        self._source_path: Optional[Path] = None
        self._compressed_path: Optional[Path] = None
        
        self.setAcceptDrops(True)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Top controls
        controls_group = QGroupBox("Komprimierungseinstellungen")
        controls_layout = QFormLayout(controls_group)
        
        # Source file selector
        source_row = QWidget()
        source_layout = QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        self.source_edit = QLabel("Keine Datei ausgewählt")
        self.source_edit.setStyleSheet("QLabel { background-color: white; padding: 4px; border: 1px solid #ccc; }")
        source_layout.addWidget(self.source_edit, stretch=1)
        source_button = QPushButton("📁 Datei wählen")
        source_button.clicked.connect(self._pick_source)
        source_layout.addWidget(source_button)
        controls_layout.addRow("Quelldatei:", source_row)
        
        # Preset selector
        preset_row = QWidget()
        preset_layout = QHBoxLayout(preset_row)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("-- Benutzerdefiniert --")
        for preset_name in CompressionPresetManager.get_preset_names():
            self.preset_combo.addItem(preset_name)
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self.preset_combo, stretch=1)
        controls_layout.addRow("Preset:", preset_row)
        
        # Format selector
        self.format_combo = QComboBox()
        self.format_combo.addItems(["jpg", "png", "webp"])
        self.format_combo.currentTextChanged.connect(self._update_preview_button)
        controls_layout.addRow("Zielformat:", self.format_combo)
        
        # Quality slider
        quality_row = QWidget()
        quality_layout = QHBoxLayout(quality_row)
        quality_layout.setContentsMargins(0, 0, 0, 0)
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setMinimum(1)
        self.quality_slider.setMaximum(100)
        self.quality_slider.setValue(85)
        self.quality_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.quality_slider.setTickInterval(10)
        self.quality_slider.valueChanged.connect(self._on_quality_changed)
        quality_layout.addWidget(self.quality_slider, stretch=1)
        self.quality_label = QLabel("85")
        self.quality_label.setMinimumWidth(30)
        quality_layout.addWidget(self.quality_label)
        controls_layout.addRow("Qualität:", quality_row)
        
        layout.addWidget(controls_group)
        
        # Preview button
        preview_button_row = QHBoxLayout()
        self.preview_button = QPushButton("🔍 Vorschau generieren")
        self.preview_button.clicked.connect(self._generate_preview)
        self.preview_button.setEnabled(False)
        preview_button_row.addStretch()
        preview_button_row.addWidget(self.preview_button)
        preview_button_row.addStretch()
        layout.addLayout(preview_button_row)
        
        # Preview area (side-by-side comparison)
        preview_group = QGroupBox("Vorschau")
        preview_layout = QVBoxLayout(preview_group)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.original_preview = ImagePreviewWidget("Original")
        self.compressed_preview = ImagePreviewWidget("Komprimiert")
        splitter.addWidget(self.original_preview)
        splitter.addWidget(self.compressed_preview)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        preview_layout.addWidget(splitter)
        layout.addWidget(preview_group, stretch=1)
        
        # Action buttons
        action_row = QHBoxLayout()
        action_row.addStretch()
        
        self.save_button = QPushButton("💾 Speichern unter...")
        self.save_button.clicked.connect(self._save_compressed)
        self.save_button.setEnabled(False)
        action_row.addWidget(self.save_button)
        
        self.replace_button = QPushButton("🔄 Original ersetzen")
        self.replace_button.clicked.connect(self._replace_original)
        self.replace_button.setEnabled(False)
        action_row.addWidget(self.replace_button)
        
        action_row.addStretch()
        layout.addLayout(action_row)
        
        # Hint label
        hint_label = QLabel("💡 Tipp: Sie können Bilder per Drag & Drop hinzufügen")
        hint_label.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint_label)
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the widget."""
        self.setEnabled(enabled)
    
    def _pick_source(self) -> None:
        """Open file dialog to select source image."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Bilddatei wählen",
            "",
            "Bilder (*.jpg *.jpeg *.png *.bmp *.gif *.webp);;Alle Dateien (*.*)"
        )
        
        if file_path:
            self._set_source(Path(file_path))
    
    def _set_source(self, path: Path) -> None:
        """Set the source image path."""
        self._source_path = path
        self._compressed_path = None
        self.source_edit.setText(path.name)
        self.original_preview.set_image(path)
        self.compressed_preview.clear()
        self.preview_button.setEnabled(True)
        self.save_button.setEnabled(False)
        self.replace_button.setEnabled(False)
    
    def _on_preset_changed(self, preset_name: str) -> None:
        """Handle preset selection."""
        if preset_name == "-- Benutzerdefiniert --":
            return
        
        preset = CompressionPresetManager.get_preset(preset_name)
        if preset:
            # Block signals to avoid triggering preview
            self.format_combo.blockSignals(True)
            self.quality_slider.blockSignals(True)
            
            # Update format
            format_index = self.format_combo.findText(preset["format"])
            if format_index >= 0:
                self.format_combo.setCurrentIndex(format_index)
            
            # Update quality
            self.quality_slider.setValue(preset["quality"])
            self.quality_label.setText(str(preset["quality"]))
            
            # Unblock signals
            self.format_combo.blockSignals(False)
            self.quality_slider.blockSignals(False)
    
    def _on_quality_changed(self, value: int) -> None:
        """Handle quality slider change."""
        self.quality_label.setText(str(value))
        # Reset preset to custom when user adjusts manually
        self.preset_combo.setCurrentIndex(0)
    
    def _update_preview_button(self) -> None:
        """Update preview button state."""
        # Reset preset to custom when format changes
        if self.preset_combo.currentIndex() != 0:
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(0)
            self.preset_combo.blockSignals(False)
    
    def _generate_preview(self) -> None:
        """Generate compressed preview."""
        if not self._source_path or not self._source_path.exists():
            QMessageBox.warning(self, "Fehler", "Keine gültige Quelldatei ausgewählt.")
            return
        
        # Create temporary compressed file
        target_format = self.format_combo.currentText()
        quality = self.quality_slider.value()
        
        temp_dir = Path.home() / ".mmst" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self._compressed_path = temp_dir / f"{self._source_path.stem}_compressed.{target_format}"
        
        self.compression_started.emit()
        self.preview_button.setEnabled(False)
        self.compression_progress.emit("Komprimiere Bild...")
        
        # Use plugin's converter
        def on_complete():
            if self._compressed_path and self._compressed_path.exists():
                self.compressed_preview.set_image(self._compressed_path)
                self.save_button.setEnabled(True)
                self.replace_button.setEnabled(True)
                self.compression_finished.emit(True, "Vorschau erfolgreich erstellt!")
            else:
                self.compression_finished.emit(False, "Komprimierung fehlgeschlagen.")
            
            self.preview_button.setEnabled(True)
        
        # Run compression in background
        self._plugin.run_image_compression(
            source=self._source_path,
            target=self._compressed_path,
            target_format=target_format,
            quality=quality,
            callback=on_complete
        )
    
    def _save_compressed(self) -> None:
        """Save compressed image to user-selected location."""
        if not self._compressed_path or not self._compressed_path.exists():
            return
        
        target_format = self.format_combo.currentText()
        default_name = f"{self._source_path.stem}_compressed.{target_format}"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Komprimiertes Bild speichern",
            str(Path.home() / default_name),
            f"Bilder (*.{target_format});;Alle Dateien (*.*)"
        )
        
        if file_path:
            import shutil
            shutil.copy2(self._compressed_path, file_path)
            QMessageBox.information(
                self,
                "Gespeichert",
                f"Komprimiertes Bild wurde gespeichert:\n{file_path}"
            )
    
    def _replace_original(self) -> None:
        """Replace original file with compressed version."""
        if not self._compressed_path or not self._compressed_path.exists():
            return
        
        reply = QMessageBox.question(
            self,
            "Original ersetzen",
            f"Möchten Sie die Originaldatei wirklich ersetzen?\n\n{self._source_path}\n\nDieser Vorgang kann nicht rückgängig gemacht werden!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            import shutil
            backup_path = self._source_path.with_suffix(self._source_path.suffix + ".backup")
            shutil.move(str(self._source_path), str(backup_path))
            shutil.copy2(self._compressed_path, self._source_path)
            
            QMessageBox.information(
                self,
                "Ersetzt",
                f"Original wurde ersetzt.\nBackup: {backup_path.name}"
            )
            
            # Reload original preview
            self.original_preview.set_image(self._source_path)
            self.compressed_preview.clear()
            self.save_button.setEnabled(False)
            self.replace_button.setEnabled(False)
    
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop event."""
        urls = event.mimeData().urls()
        if urls:
            path = Path(urls[0].toLocalFile())
            if path.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"]:
                self._set_source(path)
            else:
                QMessageBox.warning(self, "Ungültiges Format", "Bitte nur Bilddateien hinzufügen.")
