"""Metadata editor dialog for MediaLibrary plugin."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .metadata import MediaMetadata, MetadataReader, MetadataWriter


class MetadataEditorDialog(QDialog):
    """Calibre-like metadata editor for media files."""
    
    def __init__(self, file_path: Path, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.file_path = file_path
        self.reader = MetadataReader()
        self.writer = MetadataWriter()
        
        # Load current metadata
        self.metadata = self.reader.read(file_path)
        
        self.setWindowTitle(f"Metadaten bearbeiten - {file_path.name}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self._build_ui()
        self._load_metadata()
    
    def _build_ui(self) -> None:
        """Build the editor UI."""
        layout = QVBoxLayout(self)
        
        # File info (read-only)
        info_group = QGroupBox("Dateiinformationen")
        info_layout = QFormLayout(info_group)
        
        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        info_layout.addRow("Pfad:", self.path_label)
        
        self.format_label = QLabel()
        info_layout.addRow("Format:", self.format_label)
        
        self.size_label = QLabel()
        info_layout.addRow("Größe:", self.size_label)
        
        self.duration_label = QLabel()
        info_layout.addRow("Dauer:", self.duration_label)
        
        layout.addWidget(info_group)
        
        # Metadata tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)
        
        self._build_common_tab()
        self._build_audio_tab()
        self._build_video_tab()
        self._build_technical_tab()
        
        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._save_metadata)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
    
    def _build_common_tab(self) -> None:
        """Build common metadata fields tab."""
        tab = QWidget()
        form = QFormLayout(tab)
        
        self.title_edit = QLineEdit()
        form.addRow("Titel:", self.title_edit)
        
        self.artist_edit = QLineEdit()
        form.addRow("Künstler/Interpret:", self.artist_edit)
        
        self.album_edit = QLineEdit()
        form.addRow("Album:", self.album_edit)
        
        self.album_artist_edit = QLineEdit()
        form.addRow("Album-Künstler:", self.album_artist_edit)
        
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2100)
        self.year_spin.setSpecialValueText("Unbekannt")
        self.year_spin.setValue(0)
        form.addRow("Jahr:", self.year_spin)
        
        self.genre_edit = QLineEdit()
        form.addRow("Genre:", self.genre_edit)
        
        self.comment_text = QTextEdit()
        self.comment_text.setMaximumHeight(100)
        form.addRow("Kommentar:", self.comment_text)
        
        self.tabs.addTab(tab, "Allgemein")
    
    def _build_audio_tab(self) -> None:
        """Build audio-specific metadata fields tab."""
        tab = QWidget()
        form = QFormLayout(tab)
        
        self.track_number_spin = QSpinBox()
        self.track_number_spin.setRange(0, 999)
        self.track_number_spin.setSpecialValueText("Keine")
        form.addRow("Track-Nummer:", self.track_number_spin)
        
        self.track_total_spin = QSpinBox()
        self.track_total_spin.setRange(0, 999)
        self.track_total_spin.setSpecialValueText("Unbekannt")
        form.addRow("Gesamt-Tracks:", self.track_total_spin)
        
        self.disc_number_spin = QSpinBox()
        self.disc_number_spin.setRange(0, 99)
        self.disc_number_spin.setSpecialValueText("Keine")
        form.addRow("Disc-Nummer:", self.disc_number_spin)
        
        self.disc_total_spin = QSpinBox()
        self.disc_total_spin.setRange(0, 99)
        self.disc_total_spin.setSpecialValueText("Unbekannt")
        form.addRow("Gesamt-Discs:", self.disc_total_spin)
        
        self.composer_edit = QLineEdit()
        form.addRow("Komponist:", self.composer_edit)
        
        self.tabs.addTab(tab, "Audio")
    
    def _build_video_tab(self) -> None:
        """Build video-specific metadata fields tab."""
        tab = QWidget()
        form = QFormLayout(tab)
        
        self.director_edit = QLineEdit()
        form.addRow("Regisseur:", self.director_edit)
        
        self.description_text = QTextEdit()
        self.description_text.setMaximumHeight(150)
        form.addRow("Beschreibung:", self.description_text)
        
        info = QLabel("Hinweis: Video-Metadaten können derzeit nur gelesen, aber nicht geschrieben werden.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #888;")
        form.addRow(info)
        
        self.tabs.addTab(tab, "Video")
    
    def _build_technical_tab(self) -> None:
        """Build technical info tab (read-only)."""
        tab = QWidget()
        form = QFormLayout(tab)
        
        self.bitrate_label = QLabel()
        form.addRow("Bitrate:", self.bitrate_label)
        
        self.sample_rate_label = QLabel()
        form.addRow("Sample-Rate:", self.sample_rate_label)
        
        self.channels_label = QLabel()
        form.addRow("Kanäle:", self.channels_label)
        
        self.codec_label = QLabel()
        form.addRow("Codec:", self.codec_label)
        
        self.resolution_label = QLabel()
        form.addRow("Auflösung:", self.resolution_label)
        
        info = QLabel("Technische Informationen sind schreibgeschützt.")
        info.setStyleSheet("color: #888;")
        form.addRow(info)
        
        self.tabs.addTab(tab, "Technisch")
    
    def _load_metadata(self) -> None:
        """Load metadata into UI fields."""
        # File info
        self.path_label.setText(str(self.file_path))
        self.format_label.setText(self.metadata.format or "Unbekannt")
        
        if self.metadata.filesize:
            size_mb = self.metadata.filesize / (1024 * 1024)
            self.size_label.setText(f"{size_mb:.2f} MB")
        else:
            self.size_label.setText("Unbekannt")
        
        if self.metadata.duration:
            mins = int(self.metadata.duration // 60)
            secs = int(self.metadata.duration % 60)
            self.duration_label.setText(f"{mins}:{secs:02d}")
        else:
            self.duration_label.setText("Unbekannt")
        
        # Common fields
        self.title_edit.setText(self.metadata.title or "")
        self.artist_edit.setText(self.metadata.artist or "")
        self.album_edit.setText(self.metadata.album or "")
        self.album_artist_edit.setText(self.metadata.album_artist or "")
        self.year_spin.setValue(self.metadata.year or 0)
        self.genre_edit.setText(self.metadata.genre or "")
        self.comment_text.setPlainText(self.metadata.comment or "")
        
        # Audio fields
        self.track_number_spin.setValue(self.metadata.track_number or 0)
        self.track_total_spin.setValue(self.metadata.track_total or 0)
        self.disc_number_spin.setValue(self.metadata.disc_number or 0)
        self.disc_total_spin.setValue(self.metadata.disc_total or 0)
        self.composer_edit.setText(self.metadata.composer or "")
        
        # Video fields
        self.director_edit.setText(self.metadata.director or "")
        self.description_text.setPlainText(self.metadata.description or "")
        
        # Technical info
        if self.metadata.bitrate:
            self.bitrate_label.setText(f"{self.metadata.bitrate} kbps")
        else:
            self.bitrate_label.setText("Unbekannt")
        
        if self.metadata.sample_rate:
            self.sample_rate_label.setText(f"{self.metadata.sample_rate} Hz")
        else:
            self.sample_rate_label.setText("Unbekannt")
        
        if self.metadata.channels:
            self.channels_label.setText(str(self.metadata.channels))
        else:
            self.channels_label.setText("Unbekannt")
        
        self.codec_label.setText(self.metadata.codec or "Unbekannt")
        self.resolution_label.setText(self.metadata.resolution or "Unbekannt")
    
    def _save_metadata(self) -> None:
        """Save metadata back to file and database."""
        # Update metadata object from UI
        self.metadata.title = self.title_edit.text() or None
        self.metadata.artist = self.artist_edit.text() or None
        self.metadata.album = self.album_edit.text() or None
        self.metadata.album_artist = self.album_artist_edit.text() or None
        self.metadata.year = self.year_spin.value() if self.year_spin.value() > 0 else None
        self.metadata.genre = self.genre_edit.text() or None
        self.metadata.comment = self.comment_text.toPlainText() or None
        
        self.metadata.track_number = self.track_number_spin.value() if self.track_number_spin.value() > 0 else None
        self.metadata.track_total = self.track_total_spin.value() if self.track_total_spin.value() > 0 else None
        self.metadata.disc_number = self.disc_number_spin.value() if self.disc_number_spin.value() > 0 else None
        self.metadata.disc_total = self.disc_total_spin.value() if self.disc_total_spin.value() > 0 else None
        self.metadata.composer = self.composer_edit.text() or None
        
        self.metadata.director = self.director_edit.text() or None
        self.metadata.description = self.description_text.toPlainText() or None
        
        # Write to file
        if self.writer.write(self.file_path, self.metadata):
            self.accept()
        else:
            # Show error message
            from PySide6.QtWidgets import QMessageBox  # type: ignore[import-not-found]
            QMessageBox.warning(
                self,
                "Fehler beim Speichern",
                "Die Metadaten konnten nicht in die Datei geschrieben werden.\n"
                "Möglicherweise wird das Dateiformat nicht unterstützt."
            )
    
    def get_updated_metadata(self) -> MediaMetadata:
        """Get the updated metadata object."""
        return self.metadata
