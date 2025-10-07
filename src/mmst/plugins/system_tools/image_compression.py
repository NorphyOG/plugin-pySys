"""
Image compression widget with visual before/after comparison.

Provides a dedicated UI for compressing images with quality control,
format selection, and batch processing capabilities.
"""
from __future__ import annotations

from pathlib import Path
import os
import shutil
import webbrowser
import tempfile
import concurrent.futures
from typing import List, Optional, TYPE_CHECKING, Dict, Any, Callable

from PySide6.QtCore import Qt, Signal, QSize  # type: ignore[import-not-found]
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QApplication,
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


class DataCompressionWidget(QWidget):
    """Widget for compressing images and other file types with visual comparison and compression tools."""
    
    compression_started = Signal()
    compression_progress = Signal(str)  # message
    compression_finished = Signal(bool, str)  # success, message
    
    def _detect_available_compression_tools(self) -> Dict[str, bool]:
        """Detect available compression tools and return a dictionary of tool names and availability."""
        result = {
            "imagemagick": False,
            "zip": False
        }
        
        # Check for ImageMagick
        imagemagick = self.tools.get("imagemagick")
        if imagemagick and imagemagick.available:
            result["imagemagick"] = True
            
        # Check for ZIP tools (7-Zip or built-in)
        if shutil.which("7z") or shutil.which("zip"):
            result["zip"] = True
            
        return result

    def __init__(self, plugin: SystemToolsPlugin) -> None:
        super().__init__()
        self._plugin = plugin
        self._source_path: Optional[Path] = None
        self._compressed_path: Optional[Path] = None
        self._file_type: str = "image"  # Default file type: "image", "archive", "other"
        
        self.setAcceptDrops(True)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Tool status bar
        status_bar = QHBoxLayout()
        
        # Check available tools
        self.tools = self._plugin.detect_tools()
        self.available_tools = self._detect_available_compression_tools()
        
        # Show warnings for missing tools
        if not self.available_tools.get("imagemagick"):
            warning = QLabel("⚠️ ImageMagick ist nicht installiert. Bild-Komprimierung eingeschränkt.")
            warning.setStyleSheet("color: orange; font-weight: bold;")
            status_bar.addWidget(warning)
            
        if not self.available_tools.get("zip"):
            warning = QLabel("⚠️ 7-Zip ist nicht installiert. Archiv-Komprimierung eingeschränkt.")
            warning.setStyleSheet("color: orange; font-weight: bold;")
            status_bar.addWidget(warning)
            
            install_btn = QPushButton("🔧 ImageMagick installieren")
            install_btn.clicked.connect(self._install_imagemagick)
            status_bar.addWidget(install_btn)
        else:
            imagemagick = self.tools.get("imagemagick")
            version = imagemagick.version if imagemagick else 'unbekannte Version'
            status = QLabel(f"✅ ImageMagick verfügbar ({version})")
            status.setStyleSheet("color: green;")
            status_bar.addWidget(status)
        
        status_bar.addStretch(1)
        layout.addLayout(status_bar)
        
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
        
        # File type selector
        self.file_type_combo = QComboBox()
        self.file_type_combo.addItems(["Bild", "Archiv", "Andere"])
        self.file_type_combo.currentTextChanged.connect(self._on_file_type_changed)
        controls_layout.addRow("Dateityp:", self.file_type_combo)
        
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
        
        # Statistics area
        stats_group = QGroupBox("Statistik")
        stats_layout = QFormLayout(stats_group)
        
        # Add statistics labels
        self.original_size_label = QLabel("0 KB")
        self.compressed_size_label = QLabel("0 KB")
        self.savings_label = QLabel("0 KB (0%)")
        
        stats_layout.addRow("Original:", self.original_size_label)
        stats_layout.addRow("Komprimiert:", self.compressed_size_label)
        stats_layout.addRow("Ersparnis:", self.savings_label)
        
        layout.addWidget(stats_group)
        
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
        """Open file dialog to select source file based on the current file type."""
        file_type = self._file_type
        
        if file_type == "image":
            title = "Bilddatei wählen"
            filter_str = "Bilder (*.jpg *.jpeg *.png *.bmp *.gif *.webp);;Alle Dateien (*.*)"
        elif file_type == "archive":
            title = "Datei oder Ordner für Archivierung wählen"
            filter_str = "Alle Dateien (*.*)"
            
            # For archives, offer to select directories too
            dir_path = QFileDialog.getExistingDirectory(
                self,
                "Ordner für Archivierung wählen"
            )
            
            if dir_path:
                self._set_source(Path(dir_path))
                return
        else:
            title = "Datei zur Komprimierung wählen"
            filter_str = "Alle Dateien (*.*)"
            
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            title,
            "",
            filter_str
        )
        
        if file_path:
            self._set_source(Path(file_path))
    
    def _set_source(self, path: Path) -> None:
        """Set the source file path and update UI accordingly."""
        self._source_path = path
        self._compressed_path = None
        self.source_edit.setText(path.name)
        
        # Automatically detect file type and update UI
        if path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']:
            self.file_type_combo.setCurrentText("Bild")
        elif path.is_dir() or path.suffix.lower() in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            self.file_type_combo.setCurrentText("Archiv")
        else:
            self.file_type_combo.setCurrentText("Andere")
            
        # Load preview if it's an image
        if path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']:
            self.original_preview.set_image(path)
        
        # Enable preview button
        self.preview_button.setEnabled(True)
        
        # Reset any existing preview
        self.compressed_preview.clear()
        self.save_button.setEnabled(False)
        self.replace_button.setEnabled(False)
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
            
    def _install_imagemagick(self) -> None:
        """Help the user install ImageMagick."""
        from .tools import ToolDetector
        tool_detector = ToolDetector()
        installation_info = tool_detector.get_installation_info("imagemagick")
        
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Information)
        message_box.setWindowTitle(installation_info["title"])
        message_box.setText(installation_info["description"])
        message_box.setInformativeText(installation_info["install_instructions"])
        
        # Add buttons
        message_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        # Add button to open download page
        if "download_url" in installation_info and installation_info["download_url"]:
            open_browser_btn = message_box.addButton("Download öffnen", QMessageBox.ButtonRole.ActionRole)
        else:
            open_browser_btn = None
            
        result = message_box.exec()
        
        # Open browser if the button was clicked
        if open_browser_btn and message_box.clickedButton() == open_browser_btn:
            import webbrowser
            webbrowser.open(installation_info["download_url"])
    
    def _on_file_type_changed(self, file_type: str) -> None:
        """Handle file type selection change."""
        if file_type == "Bild":
            self._file_type = "image"
            self.format_combo.clear()
            self.format_combo.addItems(["jpg", "png", "webp"])
            self.quality_slider.setEnabled(True)
            self.original_preview.setVisible(True)
            self.compressed_preview.setVisible(True)
            self.format_combo.setEnabled(True)
        elif file_type == "Archiv":
            self._file_type = "archive"
            self.format_combo.clear()
            self.format_combo.addItems(["zip", "7z"])
            self.quality_slider.setEnabled(True)
            self.original_preview.setVisible(False)
            self.compressed_preview.setVisible(False)
            self.format_combo.setEnabled(True)
        else:  # Other
            self._file_type = "other"
            self.format_combo.clear()
            self.format_combo.addItems(["compressed"])
            self.quality_slider.setEnabled(True)
            self.original_preview.setVisible(False)
            self.compressed_preview.setVisible(False)
            self.format_combo.setEnabled(False)
        
        self._update_preview_button()
        
    def _generate_preview(self) -> None:
        """Generate compressed preview."""
        if not self._source_path or not self._source_path.exists():
            QMessageBox.warning(self, "Fehler", "Keine gültige Quelldatei ausgewählt.")
            return
        
        # Generate preview based on file type
        if self._file_type == "image":
            self._generate_image_preview()
        elif self._file_type == "archive":
            self._generate_archive_preview()
        else:
            self._generate_generic_compression_preview()
            
    def _update_stats(self) -> None:
        """Update size statistics for the files."""
        if not self._source_path or not self._compressed_path:
            return
            
        if not self._source_path.exists() or not self._compressed_path.exists():
            return
            
        original_size = self._source_path.stat().st_size
        compressed_size = self._compressed_path.stat().st_size
        savings = original_size - compressed_size
        savings_percent = (savings / original_size) * 100 if original_size > 0 else 0
        
        self.original_size_label.setText(f"{original_size / 1024:.1f} KB")
        self.compressed_size_label.setText(f"{compressed_size / 1024:.1f} KB")
        self.savings_label.setText(f"{savings / 1024:.1f} KB ({savings_percent:.1f}%)")
    
    def _generate_archive_preview(self) -> None:
        """Generate archive compression preview."""
        if not self._source_path:
            return
            
        target_format = self.format_combo.currentText()
        compression_level = self.quality_slider.value()
        
        temp_dir = Path.home() / ".mmst" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self._compressed_path = temp_dir / f"{self._source_path.stem}_compressed.{target_format}"
        
        self.compression_started.emit()
        self.preview_button.setEnabled(False)
        self.compression_progress.emit(f"Erstelle {target_format}-Archiv...")
        
        # Run compression in thread
        def run_archive_compression():
            try:
                import subprocess
                import shutil
                import zipfile
                import os
                from tempfile import TemporaryDirectory
                
                source_path = self._source_path
                compressed_path = self._compressed_path
                
                if not source_path or not compressed_path:
                    return False
                    
                if target_format == "zip":
                    with zipfile.ZipFile(str(compressed_path), 'w', 
                                         compression=zipfile.ZIP_DEFLATED, 
                                         compresslevel=max(1, min(9, compression_level // 10))) as zipf:
                        if source_path.is_dir():
                            for root, _, files in os.walk(source_path):
                                for file in files:
                                    file_path = Path(root) / file
                                    zipf.write(str(file_path), str(file_path.relative_to(source_path)))
                        else:
                            zipf.write(str(source_path), source_path.name)
                else:  # 7z
                    if shutil.which("7z"):
                        subprocess.run([
                            "7z", "a", "-t7z", 
                            f"-mx={max(1, min(9, compression_level // 10))}", 
                            str(compressed_path), 
                            str(source_path)
                        ])
                    else:
                        raise Exception("7-Zip ist nicht installiert")
                return True
            except Exception as e:
                print(f"Fehler beim Komprimieren: {e}")
                return False
        
        # Run in thread
        def on_thread_complete(future):
            success = future.result()
            if success and self._compressed_path and self._compressed_path.exists():
                self.save_button.setEnabled(True)
                self.replace_button.setEnabled(False)  # Don't allow replacing originals with archives
                
                # Show compression stats instead of preview
                self._update_stats()
                self.compression_finished.emit(True, "Archiv erfolgreich erstellt!")
            else:
                self.compression_finished.emit(False, "Archiv-Erstellung fehlgeschlagen.")
            self.preview_button.setEnabled(True)
        
        # Run the compression in a background thread
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(run_archive_compression)
        
        # Use Qt timer to check result
        from PySide6.QtCore import QTimer
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(100)  # 100 ms
        
        def check_future():
            if future.done():
                on_thread_complete(future)
                timer.stop()
            else:
                timer.start()
                
        timer.timeout.connect(check_future)
        timer.start()

    def _generate_generic_compression_preview(self) -> None:
        """Generate generic compression preview."""
        if not self._source_path:
            return
            
        compression_level = self.quality_slider.value()
        
        temp_dir = Path.home() / ".mmst" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self._compressed_path = temp_dir / f"{self._source_path.stem}_compressed"
        
        self.compression_started.emit()
        self.preview_button.setEnabled(False)
        self.compression_progress.emit("Komprimiere Datei...")
        
        # Run compression in thread
        def run_generic_compression():
            try:
                import gzip
                import shutil
                
                source_path = self._source_path
                compressed_path = self._compressed_path
                
                if not source_path or not compressed_path:
                    return False
                
                # Use gzip for generic compression
                with open(str(source_path), 'rb') as f_in:
                    gz_path = str(compressed_path) + '.gz'
                    with gzip.open(gz_path, 'wb', 
                                 compresslevel=max(1, min(9, compression_level // 10))) as f_out:
                        shutil.copyfileobj(f_in, f_out)
                        
                self._compressed_path = Path(str(compressed_path) + '.gz')
                return True
            except Exception as e:
                print(f"Fehler beim Komprimieren: {e}")
                return False
        
        # Run in thread
        def on_thread_complete(future):
            success = future.result()
            if success and self._compressed_path and self._compressed_path.exists():
                self.save_button.setEnabled(True)
                self.replace_button.setEnabled(False)  # Don't allow replacing with compressed file
                
                # Show compression stats instead of preview
                self._update_stats()
                self.compression_finished.emit(True, "Datei erfolgreich komprimiert!")
            else:
                self.compression_finished.emit(False, "Komprimierung fehlgeschlagen.")
            self.preview_button.setEnabled(True)
        
        # Run the compression in a background thread
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(run_generic_compression)
        
        # Use Qt timer to check result
        from PySide6.QtCore import QTimer
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(100)  # 100 ms
        
        def check_future():
            if future.done():
                on_thread_complete(future)
                timer.stop()
            else:
                timer.start()
                
        timer.timeout.connect(check_future)
        timer.start()

    def _generate_image_preview(self) -> None:
        """Generate image compression preview."""
        if not self._source_path:
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
        
        if not self._source_path:
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
            
            if not self._source_path or not self._compressed_path:
                QMessageBox.critical(self, "Fehler", "Quell- oder Zieldatei nicht gefunden.")
                return
                
            try:
                backup_path = self._source_path.with_suffix(self._source_path.suffix + ".backup")
                shutil.move(str(self._source_path), str(backup_path))
                shutil.copy2(str(self._compressed_path), str(self._source_path))
                
                QMessageBox.information(
                    self,
                    "Ersetzt",
                    f"Original wurde ersetzt.\nBackup: {backup_path.name}"
                )
                
                # Reload original preview
                self.original_preview.set_image(self._source_path)
                self.compressed_preview.clear()
                self.save_button.setEnabled(False)
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Fehler beim Ersetzen der Originaldatei: {e}")
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
