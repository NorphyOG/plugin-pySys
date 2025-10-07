"""Classic (vereinfachte) MediaLibrary Ansicht.

Diese Ansicht repräsentiert das frühere, einfache Verhalten:
 - Nur Tabelle (keine Galerie / Split / Playerkomplexität)
 - Filter: Typ, Suche, Sortierung (Subset)
 - Detailpanel mit dynamischen Feldern
 - Kompatibel mit bestehenden Tests über identische Feldnamen wo nötig

Sie dient als Fallback / Performance-orientierter Modus und wird per
Konfiguration (``media_library.view_mode = classic``) aktiviert.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, cast

try:  # pragma: no cover - falls PySide6 nicht vorhanden (Headless Tests nutzen Fallbacks)
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
        QComboBox, QLineEdit, QLabel, QPushButton, QTabWidget
    )
except Exception:  # pragma: no cover
    QWidget = object  # type: ignore
    QVBoxLayout = QHBoxLayout = QTableWidget = QTableWidgetItem = object  # type: ignore
    QComboBox = QLineEdit = QLabel = QPushButton = QTabWidget = object  # type: ignore
    class Signal:  # type: ignore
        def __init__(self,*_,**__):
            pass

from .core import MediaFile  # type: ignore
from .metadata import MediaMetadata  # type: ignore


class ClassicMediaLibraryWidget(QWidget):
    PATH_ROLE = 1000
    scan_progress = Signal(str, int, int)  # API Kompatibilität
    library_changed = Signal()

    def __init__(self, plugin: Any) -> None:
        super().__init__()
        self._plugin = plugin
        self._entries: List[Tuple[MediaFile, Path]] = []
        self._all_entries: List[Tuple[MediaFile, Path]] = []
        self._row_by_path: Dict[str, int] = {}
        self._kind_filter = "all"
        self._search_term = ""
        self._current_metadata_path: Optional[Path] = None
        self._metadata_reader = getattr(plugin, "_metadata_reader", None)
        self._metadata_cache: Dict[str, MediaMetadata] = {}

        root = QVBoxLayout(self)  # type: ignore

        control_row = QHBoxLayout()  # type: ignore
        self.kind_combo = QComboBox()  # type: ignore
        for label, key in [("Alle","all"),("Audio","audio"),("Video","video"),("Bilder","image"),("Andere","other")]:
            try:
                self.kind_combo.addItem(label, key)  # type: ignore[attr-defined]
            except Exception:
                pass
        try:
            self.kind_combo.currentIndexChanged.connect(self._on_kind_changed)  # type: ignore[attr-defined]
        except Exception:
            pass
        control_row.addWidget(self.kind_combo)  # type: ignore

        self.search_edit = QLineEdit()  # type: ignore
        try:
            self.search_edit.setPlaceholderText("Suche…")  # type: ignore[attr-defined]
            self.search_edit.textChanged.connect(self._on_search_text_changed)  # type: ignore[attr-defined]
        except Exception:
            pass
        control_row.addWidget(self.search_edit)  # type: ignore

        self.sort_combo = QComboBox()  # type: ignore
        for key,label in [
            ("recent","Zuletzt"),("title","Titel"),("rating_desc","Bewertung ↓"),("rating_asc","Bewertung ↑"),
            ("duration_desc","Dauer ↓"),("duration_asc","Dauer ↑"),("kind","Typ")
        ]:
            try:
                self.sort_combo.addItem(label,key)  # type: ignore[attr-defined]
            except Exception:
                pass
        try:
            self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)  # type: ignore[attr-defined]
        except Exception:
            pass
        control_row.addWidget(self.sort_combo)  # type: ignore

        self.reset_button = QPushButton("Reset")  # type: ignore
        try:
            self.reset_button.clicked.connect(self._reset_filters)  # type: ignore[attr-defined]
        except Exception:
            pass
        control_row.addWidget(self.reset_button)  # type: ignore
        root.addLayout(control_row)  # type: ignore

        # Tabelle (einfach)
        self.table = QTableWidget(0,4)  # type: ignore
        try:
            self.table.setHorizontalHeaderLabels(["Titel","Typ","Pfad","Dauer"])  # type: ignore[attr-defined]
            from PySide6.QtWidgets import QAbstractItemView  # type: ignore
            self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # type: ignore[attr-defined]
            self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)  # type: ignore[attr-defined]
            self.table.itemSelectionChanged.connect(self._on_table_selection_changed)  # type: ignore[attr-defined]
        except Exception:
            pass
        root.addWidget(self.table)  # type: ignore

        # Details
        self.detail_heading = QLabel("–")  # type: ignore
        root.addWidget(self.detail_heading)  # type: ignore
        detail_row = QHBoxLayout()  # type: ignore
        self._detail_field_labels: Dict[str, QLabel] = {}
        for f in ("artist","album","genre","comment","rating","bitrate","sample_rate","channels","codec","resolution","duration"):
            lbl = QLabel(f"{f}: –")  # type: ignore
            self._detail_field_labels[f] = lbl
            try:
                lbl.setVisible(False)  # type: ignore[attr-defined]
                detail_row.addWidget(lbl)  # type: ignore
            except Exception:
                pass
        root.addLayout(detail_row)  # type: ignore

        # Tabs Platzhalter (Tests erwarten .tabs Attribut mit mindestens 3 Indizes)
        try:
            self.tabs = QTabWidget()  # type: ignore
            for name in ("Bibliothek","Playlist","Tags"):
                self.tabs.addTab(QWidget(), name)  # type: ignore[attr-defined]
            root.addWidget(self.tabs)  # type: ignore
        except Exception:
            class _Tabs:  # Fallback minimal
                def setCurrentIndex(self,*_): return None
            self.tabs = _Tabs()  # type: ignore

        self._load_initial_entries()
        self._initial_select()

    # ---------------- Daten Laden -----------------
    def _load_initial_entries(self) -> None:
        try:
            entries = self._plugin.list_recent_detailed()
        except Exception:
            entries = []
        self._all_entries = [(mf, root) for (mf, root) in entries]
        self._entries = list(self._all_entries)
        self._apply_sort("recent")
        self._rebuild_table()

    def _initial_select(self) -> None:
        if not self._entries:
            return
        path = self._abs_path(self._entries[0])
        self._current_metadata_path = path
        self._update_detail_section(path)

    # ---------------- Hilfsfunktionen -----------------
    def _abs_path(self, entry: Tuple[MediaFile, Path]) -> Path:
        mf, root = entry
        return (root / Path(mf.path)).resolve(strict=False)

    def _read_metadata(self, path: Path) -> MediaMetadata:
        key = str(path)
        if key in self._metadata_cache:
            return self._metadata_cache[key]
        reader = self._metadata_reader
        meta: MediaMetadata
        if reader is None:
            meta = MediaMetadata(title=path.stem)
        else:
            try:
                meta = reader.read(path)  # type: ignore[attr-defined]
            except Exception:
                meta = MediaMetadata(title=path.stem)
        self._metadata_cache[key] = meta
        return meta

    # ---------------- Darstellung -----------------
    def _rebuild_table(self) -> None:
        try:
            self.table.setRowCount(len(self._entries))  # type: ignore[attr-defined]
        except Exception:
            return
        self._row_by_path.clear()
        for row, (mf, root) in enumerate(self._entries):
            abs_path = self._abs_path((mf, root))
            meta = self._read_metadata(abs_path)
            title = getattr(meta, "title", abs_path.stem)
            cells = [title, mf.kind, str(abs_path), self._format_duration(getattr(meta, "duration", None))]
            for col, text in enumerate(cells):
                try:
                    item = QTableWidgetItem(text)  # type: ignore
                    if col == 2:
                        item.setData(self.PATH_ROLE, str(abs_path))  # type: ignore[attr-defined]
                    self.table.setItem(row, col, item)  # type: ignore[attr-defined]
                except Exception:
                    pass
            self._row_by_path[str(abs_path)] = row

    @staticmethod
    def _format_duration(value: Optional[float]) -> str:
        if not value or value <= 0:
            return ""
        total = int(value)
        m, s = divmod(total, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h:d}:{m:02d}:{s:02d}"
        return f"{m:d}:{s:02d}"

    # ---------------- Filter / Suche / Sortierung -----------------
    def _apply_filters(self) -> None:
        result: List[Tuple[MediaFile, Path]] = []
        term = self._search_term
        kfilter = self._kind_filter
        for entry in self._all_entries:
            mf, root = entry
            if kfilter != "all" and mf.kind != kfilter:
                continue
            if term:
                meta = self._read_metadata(self._abs_path(entry))
                hay = " ".join(str(getattr(meta,a,"")) for a in ("title","artist","album","genre","comment")).lower()
                if term not in hay:
                    continue
            result.append(entry)
        self._entries = result

    def _apply_sort(self, key: str) -> None:
        if key == "recent":
            self._entries.sort(key=lambda t: t[0].mtime, reverse=True)
        elif key == "title":
            self._entries.sort(key=lambda t: self._read_metadata(self._abs_path(t)).title.lower())  # type: ignore
        elif key == "rating_desc":
            self._entries.sort(key=lambda t: getattr(self._read_metadata(self._abs_path(t)), "rating", 0), reverse=True)
        elif key == "rating_asc":
            self._entries.sort(key=lambda t: getattr(self._read_metadata(self._abs_path(t)), "rating", 0))
        elif key == "duration_desc":
            self._entries.sort(key=lambda t: getattr(self._read_metadata(self._abs_path(t)), "duration", 0.0), reverse=True)
        elif key == "duration_asc":
            self._entries.sort(key=lambda t: getattr(self._read_metadata(self._abs_path(t)), "duration", 0.0))
        elif key == "kind":
            self._entries.sort(key=lambda t: t[0].kind)

    # ---------------- Events -----------------
    def _on_kind_changed(self, index: int) -> None:
        try:
            self._kind_filter = str(self.kind_combo.itemData(index))  # type: ignore[attr-defined]
        except Exception:
            self._kind_filter = "all"
        self._refresh()

    def _on_search_text_changed(self, text: str) -> None:
        self._search_term = text.strip().lower()
        self._refresh()

    def _on_sort_changed(self, index: int) -> None:
        try:
            key = str(self.sort_combo.itemData(index))  # type: ignore[attr-defined]
        except Exception:
            key = "recent"
        self._apply_sort(key)
        self._rebuild_table()

    def _reset_filters(self) -> None:
        self._kind_filter = "all"
        self._search_term = ""
        self._entries = list(self._all_entries)
        self._apply_sort("recent")
        self._rebuild_table()
        if self._entries:
            self._update_detail_section(self._abs_path(self._entries[0]))

    def _refresh(self) -> None:
        self._apply_filters()
        # Re-apply current sort key
        try:
            key = str(self.sort_combo.itemData(self.sort_combo.currentIndex()))  # type: ignore[attr-defined]
        except Exception:
            key = "recent"
        self._apply_sort(key)
        self._rebuild_table()
        if self._entries:
            self._update_detail_section(self._abs_path(self._entries[0]))

    def _on_table_selection_changed(self) -> None:
        try:
            selection = self.table.selectionModel().selectedRows()  # type: ignore[attr-defined]
            if not selection:
                return
            row = selection[0].row()
            path_item = self.table.item(row, 2)  # type: ignore[attr-defined]
            if path_item:
                path = Path(path_item.text())
                self._current_metadata_path = path
                self._update_detail_section(path)
        except Exception:
            pass

    # ---------------- Details -----------------
    def _update_detail_section(self, path: Path) -> None:
        meta = self._read_metadata(path)
        title = getattr(meta, "title", path.stem)
        try:
            self.detail_heading.setText(title)  # type: ignore[attr-defined]
        except Exception:
            pass
        # Sichtbarkeit ähnlich dynamisch wie erweiterte Version
        kind = "other"
        entry = self._row_by_path.get(str(path))
        for f,lbl in self._detail_field_labels.items():
            try:
                lbl.setVisible(False)  # type: ignore[attr-defined]
            except Exception:
                pass
        # Allgemeine Felder
        for f in ("artist","album","genre","comment"):
            val = getattr(meta,f,None)
            if val:
                self._set_label(f,f"{f}: {val}")
        # Technische Felder je nach Medienart
        if getattr(meta,"bitrate",None):
            self._set_label("bitrate", f"bitrate: {getattr(meta,'bitrate')}")
        if getattr(meta,"sample_rate",None):
            self._set_label("sample_rate", f"sample_rate: {getattr(meta,'sample_rate')}")
        if getattr(meta,"channels",None):
            self._set_label("channels", f"channels: {getattr(meta,'channels')}")
        if getattr(meta,"codec",None):
            self._set_label("codec", f"codec: {getattr(meta,'codec')}")
        if getattr(meta,"resolution",None):
            self._set_label("resolution", f"resolution: {getattr(meta,'resolution')}")
        if getattr(meta,"duration",None):
            dur = self._format_duration(getattr(meta,"duration"))
            if dur:
                self._set_label("duration", f"duration: {dur}")

    def _set_label(self, key: str, text: str) -> None:
        lbl = self._detail_field_labels.get(key)
        if not lbl:
            return
        try:
            lbl.setText(text)  # type: ignore[attr-defined]
            lbl.setVisible(True)  # type: ignore[attr-defined]
        except Exception:
            pass

__all__ = ["ClassicMediaLibraryWidget"]
