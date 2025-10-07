from __future__ import annotations

from typing import Any, Dict, List, Tuple
from pathlib import Path

try:
    from PySide6.QtCore import Qt, Signal  # type: ignore
    from PySide6.QtWidgets import QWidget as QtWidget  # type: ignore
    from PySide6.QtWidgets import QVBoxLayout as QtVBoxLayout  # type: ignore
    from PySide6.QtWidgets import QTableWidget as QtTableWidget  # type: ignore
    from PySide6.QtWidgets import QTableWidgetItem as QtTableWidgetItem  # type: ignore
    from PySide6.QtWidgets import QHBoxLayout as QtHBoxLayout  # type: ignore
    from PySide6.QtWidgets import QLineEdit as QtLineEdit  # type: ignore
    from PySide6.QtWidgets import QComboBox as QtComboBox  # type: ignore
    from PySide6.QtWidgets import QPushButton as QtPushButton  # type: ignore
    from PySide6.QtWidgets import QLabel as QtLabel  # type: ignore
    WidgetBase = QtWidget  # type: ignore
except Exception:  # pragma: no cover
    class WidgetBase:  # type: ignore
        def __init__(self,*a,**k): pass
        def __getattr__(self, _): return lambda *a, **k: None
    class QVBoxLayout:  # type: ignore
        def __init__(self,*a,**k): pass
        def addWidget(self,*a,**k): pass
        def addLayout(self,*a,**k): pass
    class QHBoxLayout(QVBoxLayout):  # type: ignore
        def addStretch(self,*a,**k): pass
    class QLabel:  # type: ignore
        def __init__(self,*a,**k): pass
    QTableWidget = QTableWidgetItem = QLineEdit = QComboBox = QPushButton = object  # type: ignore
    Qt = object()  # type: ignore
    Signal = lambda *a, **k: None  # type: ignore

from ..core import MediaFile  # type: ignore
from ..metadata import MediaMetadata  # type: ignore
from ..smart_playlists import evaluate_smart_playlist  # type: ignore


class EnhancedTableWidget(WidgetBase):
    """Enhanced table (phase 1) – still lean but styled and extendable."""
    selection_changed = Signal()  # type: ignore

    def __init__(self, plugin: Any):
        super().__init__()
        self._plugin = plugin
        self._all_entries: List[Tuple[MediaFile, Path]] = []
        self._filtered: List[Tuple[MediaFile, Path]] = []
        self._row_by_path: Dict[str, int] = {}
        self._metadata_cache: Dict[str, MediaMetadata] = {}
        self._kind_filter = "all"
        self._search_term = ""
        self._sort_key = "recent"
        self._batch_bar = None  # type: ignore

        root = QtVBoxLayout(self)  # type: ignore
        self._controls = self._build_controls()
        root.addLayout(self._controls)  # type: ignore
        try:
            self._table = QtTableWidget(0, 5)  # type: ignore
            self._table.setHorizontalHeaderLabels(["Titel", "Typ", "Pfad", "Dauer", "Bewertung"])  # type: ignore
            from PySide6.QtWidgets import QAbstractItemView  # type: ignore
            self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # type: ignore
            self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)  # type: ignore
            self._table.itemSelectionChanged.connect(self._on_sel_changed)  # type: ignore
        except Exception:
            self._table = QtLabel("(Tabelle nicht verfügbar)")  # type: ignore
        root.addWidget(self._table)  # type: ignore
        self._status = QtLabel("0 Einträge")  # type: ignore
        self._status.setStyleSheet("color:#777;font-size:11px;padding:2px 4px;")  # type: ignore
        root.addWidget(self._status)  # type: ignore
        # Batch action bar (hidden initially)
        self._batch_bar = self._build_batch_bar()
        root.addWidget(self._batch_bar)  # type: ignore
        try:
            self._batch_bar.setVisible(False)  # type: ignore[attr-defined]
        except Exception: pass

        self.reload()

    # ------------------------------------------------------------------ public
    def reload(self) -> None:
        try:
            entries = self._plugin.list_recent_detailed()
        except Exception:
            entries = []
        # Apply smart playlist filter if active via enhanced root reference
        try:
            root = getattr(self._plugin, '_enhanced_root_ref', None)
            if root is not None:
                sp = root.get_active_playlist()  # type: ignore[attr-defined]
                if sp is not None:
                    def _meta_provider(p: Path):  # lightweight metadata provider
                        return self._read_metadata(p)
                    entries = evaluate_smart_playlist(sp, entries, _meta_provider)  # type: ignore[attr-defined]
        except Exception:
            pass
        self._all_entries = list(entries)
        self._apply_filters()
        self._apply_sort()
        self._rebuild()

    def selected_paths(self) -> List[Path]:  # for future batch actions
        out: List[Path] = []
        try:
            for idx in self._table.selectionModel().selectedRows():  # type: ignore[attr-defined]
                r = idx.row()
                if 0 <= r < len(self._filtered):
                    mf, root = self._filtered[r]
                    out.append((root / mf.path).resolve(False))
        except Exception:
            pass
        return out

    # ---------------------------------------------------------------- internals
    def _build_controls(self):
        try:
            bar = QtHBoxLayout()  # type: ignore
        except Exception:
            class _Dummy:
                def addWidget(self,*a,**k): pass
                def addStretch(self,*a,**k): pass
            bar = _Dummy()  # type: ignore
        self.kind_combo = QtComboBox()  # type: ignore
        for lab, key in [("Alle","all"),("Audio","audio"),("Video","video"),("Bilder","image"),("Andere","other")]:
            try: self.kind_combo.addItem(lab, key)  # type: ignore
            except Exception: pass
        try:
            self.kind_combo.currentIndexChanged.connect(self._on_kind_changed)  # type: ignore
        except Exception:
            pass
        try: bar.addWidget(self.kind_combo)  # type: ignore
        except Exception: pass
        self.search_edit = QtLineEdit()  # type: ignore
        try: self.search_edit.setPlaceholderText("Suche…")  # type: ignore
        except Exception: pass
        try: self.search_edit.textChanged.connect(self._on_search)  # type: ignore
        except Exception: pass
        try: bar.addWidget(self.search_edit)  # type: ignore
        except Exception: pass
        self.sort_combo = QtComboBox()  # type: ignore
        for key, label in [
            ("recent","Zuletzt"),
            ("rating_desc","Bewertung ↓"),("rating_asc","Bewertung ↑"),
            ("duration_desc","Dauer ↓"),("duration_asc","Dauer ↑"),
            ("kind","Typ"),("title","Titel")]:
            try: self.sort_combo.addItem(label, key)  # type: ignore
            except Exception: pass
        try: self.sort_combo.currentIndexChanged.connect(self._on_sort)  # type: ignore
        except Exception: pass
        try: bar.addWidget(self.sort_combo)  # type: ignore
        except Exception: pass
        self.reset_btn = QtPushButton("Reset")  # type: ignore
        try: self.reset_btn.clicked.connect(self._on_reset)  # type: ignore
        except Exception: pass
        try: bar.addWidget(self.reset_btn)  # type: ignore
        except Exception: pass
        try: bar.addStretch(1)  # type: ignore
        except Exception: pass
        return bar

    def _apply_filters(self):
        # Filtering logic applied to current full list -> _filtered
        # Kind filter
        data = []
        kfilter = self._kind_filter
        # obtain attribute filters (rating_min, tag_expr) from enhanced root if available
        rating_min = 0; tag_expr = ""
        try:
            root = getattr(self._plugin, '_enhanced_root_ref', None)
            if root is not None and hasattr(root, 'get_active_attribute_filters'):
                rating_min, tag_expr = root.get_active_attribute_filters()  # type: ignore[attr-defined]
        except Exception:
            pass
        tag_terms = [t.strip().lower() for t in tag_expr.split(',') if t.strip()] if tag_expr else []
        for mf, root in self._all_entries:
            if kfilter != 'all' and mf.kind != kfilter:
                # map common kinds (audio/video/image) fallback; keep simple
                if kfilter == 'audio' and mf.kind not in ('audio','music'): continue
                if kfilter == 'video' and mf.kind not in ('video',): continue
                if kfilter == 'image' and mf.kind not in ('image','photo','picture'): continue
                if kfilter == 'other' and mf.kind in ('audio','music','video','image','photo','picture'): continue
            # search term
            if self._search_term:
                if self._search_term not in mf.path.lower():
                    continue
            # rating filter (attribute may be None)
            if rating_min > 0:
                r_val = mf.rating if getattr(mf, 'rating', None) is not None else None
                if r_val is None or r_val < rating_min:
                    continue
            # tag filter (OR semantics among terms; all terms must appear? choose ANY for flexibility)
            if tag_terms:
                mf_tags = [t.lower() for t in getattr(mf, 'tags', [])]
                if not any(term in mf_tags for term in tag_terms):
                    continue
            data.append((mf, root))
        self._filtered = data
        
    def _apply_sort(self) -> None:
        try:
            if not self._filtered:
                return
                
            if self._sort_key == "recent":
                # Sort by modification time (newest first)
                self._filtered.sort(key=lambda x: getattr(x[0], 'mtime', 0) or 0, reverse=True)
            elif self._sort_key == "name":
                # Sort by filename
                self._filtered.sort(key=lambda x: Path(getattr(x[0], 'path', '')).name.lower())
            elif self._sort_key == "rating":
                # Sort by rating (highest first)
                self._filtered.sort(key=lambda x: getattr(x[0], 'rating', 0) or 0, reverse=True)
        except Exception:
            # Fallback - do nothing on sort error
            pass
    def _rebuild(self):
        if not hasattr(self._table, 'setRowCount'):
            return
        try:
            self._table.setRowCount(len(self._filtered))  # type: ignore
        except Exception:
            return
        self._row_by_path.clear()
        for row, (mf, root) in enumerate(self._filtered):
            abs_path = (root / mf.path).resolve(False)
            self._row_by_path[str(abs_path)] = row
            try:
                self._table.setItem(row,0,QtTableWidgetItem(mf.path))  # type: ignore[attr-defined]
                self._table.setItem(row,1,QtTableWidgetItem(mf.kind))  # type: ignore[attr-defined]
                self._table.setItem(row,2,QtTableWidgetItem(str(abs_path)))  # type: ignore[attr-defined]
                self._table.setItem(row,3,QtTableWidgetItem(""))  # type: ignore[attr-defined]
                self._table.setItem(row,4,QtTableWidgetItem(""))  # type: ignore[attr-defined]
            except Exception:
                continue
        try:
            self._status.setText(f"{len(self._filtered)} / {len(self._all_entries)} Einträge")  # type: ignore
        except Exception:
            pass

    def _read_metadata(self, path: Path) -> MediaMetadata:
        key = str(path)
        if key in self._metadata_cache:
            return self._metadata_cache[key]
        reader = getattr(self._plugin, '_metadata_reader', None)
        meta = reader.read(path) if reader else MediaMetadata(title=path.stem)
        self._metadata_cache[key] = meta
        return meta

    # ------------------------------ slots
    def _on_kind_changed(self, index: int) -> None:
        try: self._kind_filter = str(self.kind_combo.itemData(index))  # type: ignore
        except Exception: self._kind_filter = 'all'
        self._apply_filters(); self._apply_sort(); self._rebuild()

    def _on_search(self, text: str) -> None:
        self._search_term = text.lower().strip(); self._apply_filters(); self._apply_sort(); self._rebuild()

    def _on_sort(self, index: int) -> None:
        try: self._sort_key = str(self.sort_combo.itemData(index))  # type: ignore
        except Exception: self._sort_key = 'recent'
        self._apply_sort(); self._rebuild()

    def _on_reset(self) -> None:
        self._kind_filter = 'all'; self._search_term=''; self._sort_key='recent'
        try:
            self.search_edit.clear()  # type: ignore
            self.sort_combo.setCurrentIndex(0)  # type: ignore
            self.kind_combo.setCurrentIndex(0)  # type: ignore
        except Exception: pass
        self.reload()

    def _on_sel_changed(self) -> None:
        self.selection_changed.emit()  # type: ignore
        # toggle batch bar
        try:
            if not self._batch_bar:
                return
            selected = self._table.selectionModel().selectedRows()  # type: ignore[attr-defined]
            self._batch_bar.setVisible(len(selected) > 1)  # type: ignore[attr-defined]
        except Exception:
            pass

    # ------------------------------ batch actions ---------------------------
    def _build_batch_bar(self):  # pragma: no cover
        try:
            from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox  # type: ignore
        except Exception:
            return QtLabel("(Batch Aktionen nicht verfügbar)")  # type: ignore
        bar = QtWidget(self)  # type: ignore
        layout = QtHBoxLayout(bar)  # type: ignore
        layout.setContentsMargins(4,2,4,2)  # type: ignore
        layout.setSpacing(6)  # type: ignore
        lab = QtLabel("Batch:")  # type: ignore
        lab.setStyleSheet("color:#aaa;font-weight:600;")  # type: ignore
        layout.addWidget(lab)  # type: ignore
        # rating combo
        rating_combo = QtComboBox()  # type: ignore
        rating_combo.addItem("Bewertung setzen", None)  # type: ignore
        for i in range(1,6):
            rating_combo.addItem("★"*i, i)  # type: ignore
        def _apply_rating(idx):  # type: ignore
            try:
                val = rating_combo.itemData(idx)  # type: ignore[attr-defined]
                if val is None:
                    return
                for p in self.selected_paths():
                    try: self._plugin.set_rating(p, val)  # type: ignore[attr-defined]
                    except Exception: pass
            except Exception: pass
        try: rating_combo.currentIndexChanged.connect(_apply_rating)  # type: ignore[attr-defined]
        except Exception: pass
        layout.addWidget(rating_combo)  # type: ignore
        # tags edit
        tag_edit = QtLineEdit()  # type: ignore
        tag_edit.setPlaceholderText("Tags hinzufügen (Komma)")  # type: ignore
        def _apply_tags():  # type: ignore
            raw = tag_edit.text()  # type: ignore[attr-defined]
            if not raw.strip():
                return
            tags = [t.strip() for t in raw.split(',') if t.strip()]
            for p in self.selected_paths():
                try:
                    # merge existing tags if available
                    idx = getattr(self._plugin, '_library_index', None)
                    existing = []
                    if idx is not None:
                        try:
                            rating_existing, tags_existing = idx.get_attributes(p)  # type: ignore[attr-defined]
                            existing = list(tags_existing)
                        except Exception: pass
                    merged = sorted(set(existing + tags))
                    self._plugin.set_tags(p, merged)  # type: ignore[attr-defined]
                except Exception:
                    pass
        try: tag_edit.editingFinished.connect(_apply_tags)  # type: ignore[attr-defined]
        except Exception: pass
        layout.addWidget(tag_edit)  # type: ignore
        layout.addStretch(1)  # type: ignore
        return bar
