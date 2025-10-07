#!/usr/bin/env python
# fix_media_library.py - Erstellt fehlende Dateien für die erweiterte Media Library

from __future__ import annotations

import os
import sys
from pathlib import Path

def ensure_directory(path):
    """Stellt sicher, dass ein Verzeichnis existiert."""
    path.mkdir(parents=True, exist_ok=True)


def create_table_view():
    """Erstellt die fehlende table_view.py Datei für die erweiterte Media Library."""
    file_path = Path("src/mmst/plugins/media_library/enhanced/table_view.py")
    
    if file_path.exists():
        print(f"Die Datei {file_path} existiert bereits.")
        return
        
    content = """from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from pathlib import Path

try:  # GUI imports
    from PySide6.QtCore import Qt, Signal, QSize, QPoint  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QTableWidget,
        QTableWidgetItem,
        QHeaderView,
        QAbstractItemView,
        QMenu,
    )
    from PySide6.QtGui import QAction  # type: ignore
except Exception:  # pragma: no cover
    class QTableWidget:  # type: ignore
        def __init__(self, *a, **k): pass
        def setRowCount(self, *a, **k): pass
        def setColumnCount(self, *a, **k): pass
        def setHorizontalHeaderLabels(self, *a, **k): pass
        def horizontalHeader(self): return type('obj', (object,), {'setSectionResizeMode': lambda *a, **k: None})
        def setItem(self, *a, **k): pass
        def setContextMenuPolicy(self, *a, **k): pass
        def customContextMenuRequested(self): return type('obj', (object,), {'connect': lambda *a, **k: None})
        def rowCount(self): return 0
    
    class QTableWidgetItem:  # type: ignore
        def __init__(self, *a, **k): pass
        def setData(self, *a, **k): pass
        
    class QHeaderView:  # type: ignore
        class ResizeMode:  # type: ignore
            Stretch = None
            ResizeToContents = None
    
    class QAbstractItemView:  # type: ignore
        class SelectionMode:  # type: ignore
            ExtendedSelection = None
    
    class QMenu:  # type: ignore
        def __init__(self, *a, **k): pass
        def addAction(self, *a, **k): return None
        def exec(self, *a, **k): return None
        
    class QAction:  # type: ignore
        def __init__(self, *a, **k): pass
        def triggered(self): return type('obj', (object,), {'connect': lambda *a, **k: None})
    
    Qt = type('Qt', (), {'AlignLeft': None})  # type: ignore
    Signal = lambda *a, **k: None  # type: ignore

from ..core import MediaFile  # type: ignore


class EnhancedTableWidget(QTableWidget):
    """Erweiterte Tabelle für die Media Library."""
    selection_changed = Signal(list) if Signal is not None else None  # type: ignore
    item_activated = Signal(Path) if Signal is not None else None  # type: ignore
    
    def __init__(self, plugin: Any):
        super().__init__()
        self._plugin = plugin
        self._entries: List[Tuple[MediaFile, Path]] = []
        self._setup_table()
        self._connect_signals()
    
    def _setup_table(self):
        """Konfiguriert das Tabellenaussehen."""
        try:
            self.setColumnCount(5)
            self.setHorizontalHeaderLabels(["Name", "Typ", "Größe", "Pfad", "Bewertung"])
            
            # Spaltenbreite anpassen
            header = self.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Typ
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Größe
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Pfad
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Bewertung
            
            # Mehrfachauswahl ermöglichen
            self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            
            # Kontextmenü einrichten
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._show_context_menu)  # type: ignore[attr-defined]
        except Exception:
            pass
    
    def _connect_signals(self):
        """Verbindet die Signale."""
        try:
            self.itemSelectionChanged.connect(self._on_selection_changed)  # type: ignore[attr-defined]
            self.itemDoubleClicked.connect(self._on_item_activated)  # type: ignore[attr-defined]
        except Exception:
            pass
    
    def _on_selection_changed(self):
        """Behandelt Änderungen der Auswahl."""
        try:
            selected_rows = set(item.row() for item in self.selectedItems())  # type: ignore[attr-defined]
            selected_paths = [self._get_path_for_row(row) for row in selected_rows]
            self.selection_changed.emit(selected_paths)  # type: ignore[attr-defined]
        except Exception:
            pass
    
    def _on_item_activated(self, item):
        """Behandelt Doppelklicks auf Elemente."""
        try:
            row = item.row()
            path = self._get_path_for_row(row)
            if path:
                self.item_activated.emit(path)  # type: ignore[attr-defined]
        except Exception:
            pass
    
    def _get_path_for_row(self, row: int) -> Optional[Path]:
        """Gibt den Pfad für die angegebene Zeile zurück."""
        try:
            if 0 <= row < len(self._entries):
                mf, root = self._entries[row]
                return (root / Path(mf.path)).resolve()
        except Exception:
            pass
        return None
    
    def _show_context_menu(self, pos: QPoint):
        """Zeigt das Kontextmenü an der angegebenen Position an."""
        try:
            menu = QMenu(self)
            
            # Aktionen hinzufügen
            play_action = QAction("Abspielen", self)
            play_action.triggered.connect(self._on_play_action)  # type: ignore[attr-defined]
            
            open_folder_action = QAction("In Explorer öffnen", self)
            open_folder_action.triggered.connect(self._on_open_folder_action)  # type: ignore[attr-defined]
            
            # Aktionen zum Menü hinzufügen
            menu.addAction(play_action)  # type: ignore[attr-defined]
            menu.addAction(open_folder_action)  # type: ignore[attr-defined]
            
            # Menü anzeigen
            menu.exec(self.mapToGlobal(pos))  # type: ignore[attr-defined]
        except Exception:
            pass
    
    def _on_play_action(self):
        """Behandelt die Abspielen-Aktion."""
        try:
            selected_rows = set(item.row() for item in self.selectedItems())  # type: ignore[attr-defined]
            if selected_rows:
                row = min(selected_rows)
                path = self._get_path_for_row(row)
                if path:
                    self.item_activated.emit(path)  # type: ignore[attr-defined]
        except Exception:
            pass
    
    def _on_open_folder_action(self):
        """Behandelt die In Explorer öffnen-Aktion."""
        try:
            selected_rows = set(item.row() for item in self.selectedItems())  # type: ignore[attr-defined]
            if selected_rows:
                row = min(selected_rows)
                path = self._get_path_for_row(row)
                if path and path.exists():
                    import subprocess
                    import os
                    if os.name == 'nt':
                        subprocess.run(['explorer', '/select,', str(path)])
                    elif os.name == 'posix':
                        subprocess.run(['xdg-open', str(path.parent)])
        except Exception:
            pass
    
    def load_entries(self, entries: List[Tuple[MediaFile, Path]]):
        """Lädt die Einträge in die Tabelle."""
        self._entries = entries
        self._populate_table()
    
    def _populate_table(self):
        """Füllt die Tabelle mit den Einträgen."""
        try:
            self.setRowCount(len(self._entries))
            
            for row, (mf, root) in enumerate(self._entries):
                # Name
                name_item = QTableWidgetItem(Path(mf.path).name)
                self.setItem(row, 0, name_item)
                
                # Typ
                type_item = QTableWidgetItem(mf.kind)
                self.setItem(row, 1, type_item)
                
                # Größe formatieren
                size = mf.size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                
                size_item = QTableWidgetItem(size_str)
                size_item.setData(Qt.ItemDataRole.UserRole, mf.size)  # type: ignore[attr-defined]
                self.setItem(row, 2, size_item)
                
                # Pfad
                path_item = QTableWidgetItem(str(root / mf.path))
                self.setItem(row, 3, path_item)
                
                # Bewertung
                rating = mf.rating or 0
                rating_item = QTableWidgetItem("★" * rating)
                self.setItem(row, 4, rating_item)
        except Exception as e:
            print(f"Fehler beim Füllen der Tabelle: {e}")
    
    def reload(self):
        """Lädt die Einträge neu und aktualisiert die Tabelle."""
        try:
            if hasattr(self._plugin, 'list_recent_detailed'):
                entries = self._plugin.list_recent_detailed()
                self.load_entries(entries)
        except Exception as e:
            print(f"Fehler beim Neuladen der Tabelle: {e}")
"""
    
    ensure_directory(file_path.parent)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Die Datei {file_path} wurde erstellt.")


def create_dashboard_placeholder():
    """Erstellt die fehlende dashboard.py Datei für die erweiterte Media Library."""
    file_path = Path("src/mmst/plugins/media_library/enhanced/dashboard.py")
    
    if file_path.exists():
        print(f"Die Datei {file_path} existiert bereits.")
        return
        
    content = """from __future__ import annotations
from typing import Any, Dict, List, Optional

try:  # GUI imports
    from PySide6.QtCore import Qt  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QWidget,
        QVBoxLayout,
        QLabel,
        QGridLayout,
    )
except Exception:  # pragma: no cover
    class QWidget:  # type: ignore
        def __init__(self, *a, **k): pass
    class QVBoxLayout:  # type: ignore
        def __init__(self, *a, **k): pass
        def addWidget(self, *a, **k): pass
    class QGridLayout:  # type: ignore
        def __init__(self, *a, **k): pass
        def addWidget(self, *a, **k): pass
    class QLabel:  # type: ignore
        def __init__(self, *a, **k): pass
    Qt = object()  # type: ignore


class DashboardPlaceholder(QWidget):
    """Platzhalter für das Dashboard der Media Library."""
    
    def __init__(self, plugin: Any = None):
        """Initialisiert den Dashboard-Platzhalter."""
        super().__init__()
        self._plugin = plugin
        self._setup_ui()
    
    def _setup_ui(self):
        """Richtet die Benutzeroberfläche ein."""
        layout = QVBoxLayout(self)
        
        # Titel
        title = QLabel("Media Library Dashboard")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Statistiken-Grid
        stats_layout = QGridLayout()
        
        # Zeilen für Statistiken
        stats = [
            ("Gesamt:", "0 Dateien"),
            ("Audio:", "0 Dateien"),
            ("Video:", "0 Dateien"),
            ("Bilder:", "0 Dateien"),
            ("Dokumente:", "0 Dateien"),
            ("Andere:", "0 Dateien")
        ]
        
        for row, (label_text, value_text) in enumerate(stats):
            label = QLabel(label_text)
            value = QLabel(value_text)
            stats_layout.addWidget(label, row, 0)
            stats_layout.addWidget(value, row, 1)
        
        layout.addLayout(stats_layout)
        
        # Info-Text
        info = QLabel(
            "Dies ist ein Platzhalter für das Dashboard. "
            "Die erweiterte Funktionalität wird geladen..."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
"""
    
    ensure_directory(file_path.parent)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Die Datei {file_path} wurde erstellt.")


def create_mini_player():
    """Erstellt die fehlende mini_player.py Datei für die erweiterte Media Library."""
    file_path = Path("src/mmst/plugins/media_library/enhanced/mini_player.py")
    
    if file_path.exists():
        print(f"Die Datei {file_path} existiert bereits.")
        return
        
    content = """from __future__ import annotations
from typing import Any, Dict, Optional
from pathlib import Path

try:  # GUI imports
    from PySide6.QtCore import Qt, QUrl  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QWidget,
        QVBoxLayout,
        QLabel,
        QHBoxLayout,
        QPushButton,
        QSlider,
    )
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput  # type: ignore
    from PySide6.QtMultimediaWidgets import QVideoWidget  # type: ignore
except Exception:  # pragma: no cover
    class QWidget:  # type: ignore
        def __init__(self, *a, **k): pass
    class QVBoxLayout:  # type: ignore
        def __init__(self, *a, **k): pass
        def addWidget(self, *a, **k): pass
        def addLayout(self, *a, **k): pass
    class QHBoxLayout:  # type: ignore
        def __init__(self, *a, **k): pass
        def addWidget(self, *a, **k): pass
        def addStretch(self, *a, **k): pass
    class QPushButton:  # type: ignore
        def __init__(self, *a, **k): pass
    class QLabel:  # type: ignore
        def __init__(self, *a, **k): pass
    class QSlider:  # type: ignore
        def __init__(self, *a, **k): pass
    class QMediaPlayer:  # type: ignore
        def __init__(self, *a, **k): pass
        class PlaybackState:  # type: ignore
            PlayingState = 1
            PausedState = 2
            StoppedState = 0
    class QAudioOutput:  # type: ignore
        def __init__(self, *a, **k): pass
    class QVideoWidget:  # type: ignore
        def __init__(self, *a, **k): pass
    class QUrl:  # type: ignore
        def fromLocalFile(file): return None
    Qt = type('Qt', (), {'Horizontal': None, 'Vertical': None})  # type: ignore


class MiniPlayerWidget(QWidget):
    """Einfacher Media Player für Audio- und Videodateien."""
    
    def __init__(self, plugin: Any = None):
        """Initialisiert den Mini-Player."""
        super().__init__()
        self._plugin = plugin
        self._current_file: Optional[Path] = None
        self._setup_ui()
        self._setup_player()
    
    def _setup_ui(self):
        """Richtet die Benutzeroberfläche ein."""
        try:
            layout = QVBoxLayout(self)
            
            # Titel-Label
            self._title_label = QLabel("Kein Medium ausgewählt")
            layout.addWidget(self._title_label)
            
            # Video-Widget (nur für Videos sichtbar)
            self._video_widget = QVideoWidget()
            layout.addWidget(self._video_widget)
            self._video_widget.setVisible(False)
            
            # Fortschrittsleiste
            self._progress_slider = QSlider(Qt.Horizontal)
            layout.addWidget(self._progress_slider)
            
            # Steuerungselemente
            controls_layout = QHBoxLayout()
            
            self._play_button = QPushButton("▶")
            self._stop_button = QPushButton("■")
            self._mute_button = QPushButton("🔊")
            
            controls_layout.addWidget(self._play_button)
            controls_layout.addWidget(self._stop_button)
            controls_layout.addWidget(self._mute_button)
            controls_layout.addStretch(1)
            
            layout.addLayout(controls_layout)
            
            # Signale verbinden
            self._play_button.clicked.connect(self._toggle_playback)  # type: ignore[attr-defined]
            self._stop_button.clicked.connect(self._stop_playback)  # type: ignore[attr-defined]
            self._mute_button.clicked.connect(self._toggle_mute)  # type: ignore[attr-defined]
        except Exception as e:
            print(f"Fehler beim Einrichten der UI: {e}")
    
    def _setup_player(self):
        """Initialisiert den Media Player."""
        try:
            self._player = QMediaPlayer()
            self._audio_output = QAudioOutput()
            self._player.setAudioOutput(self._audio_output)
            self._player.setVideoOutput(self._video_widget)
            
            # Signale verbinden
            self._player.playbackStateChanged.connect(self._update_play_button)  # type: ignore[attr-defined]
            self._player.positionChanged.connect(self._update_position)  # type: ignore[attr-defined]
            self._player.durationChanged.connect(self._update_duration)  # type: ignore[attr-defined]
            self._progress_slider.sliderMoved.connect(self._seek)  # type: ignore[attr-defined]
        except Exception as e:
            print(f"Fehler beim Einrichten des Players: {e}")
    
    def _toggle_playback(self):
        """Wechselt zwischen Abspielen und Pause."""
        try:
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._player.pause()
            else:
                self._player.play()
        except Exception:
            pass
    
    def _stop_playback(self):
        """Stoppt die Wiedergabe."""
        try:
            self._player.stop()
        except Exception:
            pass
    
    def _toggle_mute(self):
        """Schaltet den Ton ein oder aus."""
        try:
            self._audio_output.setMuted(not self._audio_output.isMuted())
            self._mute_button.setText("🔇" if self._audio_output.isMuted() else "🔊")
        except Exception:
            pass
    
    def _update_play_button(self, state):
        """Aktualisiert den Play-Button basierend auf dem Wiedergabestatus."""
        try:
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self._play_button.setText("⏸")
            else:
                self._play_button.setText("▶")
        except Exception:
            pass
    
    def _update_position(self, position):
        """Aktualisiert die Position des Fortschrittsbalkens."""
        try:
            self._progress_slider.setValue(position)
        except Exception:
            pass
    
    def _update_duration(self, duration):
        """Aktualisiert die Gesamtdauer des Fortschrittsbalkens."""
        try:
            self._progress_slider.setRange(0, duration)
        except Exception:
            pass
    
    def _seek(self, position):
        """Setzt die Wiedergabeposition."""
        try:
            self._player.setPosition(position)
        except Exception:
            pass
    
    def play_file(self, file_path: Path):
        """Spielt die angegebene Datei ab."""
        try:
            if not file_path.exists():
                print(f"Datei nicht gefunden: {file_path}")
                return
            
            # Dateityp prüfen
            suffix = file_path.suffix.lower()
            is_video = suffix in {'.mp4', '.mkv', '.avi', '.mov', '.webm'}
            
            # Video-Widget anzeigen/verstecken je nach Dateityp
            self._video_widget.setVisible(is_video)
            
            # Datei laden und abspielen
            self._player.setSource(QUrl.fromLocalFile(str(file_path)))
            self._player.play()
            
            # Titel aktualisieren
            self._title_label.setText(file_path.name)
            self._current_file = file_path
        except Exception as e:
            print(f"Fehler beim Abspielen der Datei: {e}")
"""
    
    ensure_directory(file_path.parent)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Die Datei {file_path} wurde erstellt.")


def create_neo_root():
    """Erstellt die fehlende neo_root.py Datei für die Ultra-Version der Media Library."""
    file_path = Path("src/mmst/plugins/media_library/enhanced/neo_root.py")
    
    if file_path.exists():
        print(f"Die Datei {file_path} existiert bereits.")
        return
        
    content = """from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

try:  # GUI imports
    from PySide6.QtCore import Qt, Signal  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QPushButton,
        QLabel,
        QSplitter,
        QStackedWidget,
    )
except Exception:  # pragma: no cover
    class QWidget:  # type: ignore
        def __init__(self, *a, **k): pass
    class QVBoxLayout:  # type: ignore
        def __init__(self, *a, **k): pass
        def addWidget(self, *a, **k): pass
        def addLayout(self, *a, **k): pass
    class QHBoxLayout:  # type: ignore
        def __init__(self, *a, **k): pass
        def addWidget(self, *a, **k): pass
        def addStretch(self, *a, **k): pass
    class QPushButton:  # type: ignore
        def __init__(self, *a, **k): pass
    class QLabel:  # type: ignore
        def __init__(self, *a, **k): pass
    class QSplitter:  # type: ignore
        def __init__(self, *a, **k): pass
    class QStackedWidget:  # type: ignore
        def __init__(self, *a, **k): pass
        def addWidget(self, *a, **k): pass
        def setCurrentIndex(self, *a, **k): pass
    Qt = object()  # type: ignore
    Signal = lambda *a, **k: None  # type: ignore

from ..core import MediaFile  # type: ignore
from .base import EnhancedRootWidget  # type: ignore


def create_ultra_widget(plugin: Any) -> QWidget:
    """Erstellt die Ultra-Version der Media Library."""
    return NeoRootWidget(plugin)


class NeoRootWidget(EnhancedRootWidget):
    """Ultra-Version der Media Library mit erweitertem Layout und Funktionen."""
    
    def __init__(self, plugin: Any):
        """Initialisiert die Ultra-Version der Media Library."""
        super().__init__(plugin)
        self._entries = []
        self._all_entries = []
        
        # Ultra-spezifische UI-Elemente
        self._setup_ultra_ui()
        
        # Initialdaten laden
        self._load_initial_entries()
    
    def _setup_ultra_ui(self):
        """Richtet die Ultra-spezifische Benutzeroberfläche ein."""
        try:
            # Info-Label hinzufügen
            info_label = QLabel("Ultra-Version der Media Library aktiviert")
            info_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            layout = self.layout()
            if layout:
                layout.addWidget(info_label)
        except Exception as e:
            print(f"Fehler beim Einrichten der Ultra-UI: {e}")
"""
    
    ensure_directory(file_path.parent)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Die Datei {file_path} wurde erstellt.")


def main():
    """Erstellt alle fehlenden Dateien für die Media Library."""
    print("Erstelle fehlende Dateien für die erweiterte Media Library...")
    
    create_table_view()
    create_dashboard_placeholder()
    create_mini_player()
    create_neo_root()
    
    print("\nAlle fehlenden Dateien wurden erstellt!")
    print("Bitte starten Sie die Anwendung neu mit 'python -m mmst.core.app'")


if __name__ == "__main__":
    main()