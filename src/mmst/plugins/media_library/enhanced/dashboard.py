from __future__ import annotations
from typing import Any, List, Tuple, Dict
from pathlib import Path

try:  # GUI
    from PySide6.QtWidgets import (
        QWidget as _QtQWidget, QVBoxLayout as _QtQVBoxLayout, QLabel as _QtQLabel,
        QHBoxLayout as _QtQHBoxLayout, QPushButton as _QtQPushButton,
        QScrollArea as _QtQScrollArea, QFrame as _QtQFrame,
        QListWidget as _QtQListWidget, QListWidgetItem as _QtQListWidgetItem
    )
    from PySide6.QtCore import Qt  # type: ignore
    # Create aliases for easier usage
    QWidget, QVBoxLayout, QHBoxLayout = _QtQWidget, _QtQVBoxLayout, _QtQHBoxLayout
    QLabel, QPushButton, QScrollArea = _QtQLabel, _QtQPushButton, _QtQScrollArea
    QFrame, QListWidget, QListWidgetItem = _QtQFrame, _QtQListWidget, _QtQListWidgetItem
except Exception:  # pragma: no cover
    _QtQWidget = object  # type: ignore
    _QtQVBoxLayout = _QtQHBoxLayout = _QtQLabel = _QtQPushButton = _QtQScrollArea = _QtQFrame = _QtQListWidget = _QtQListWidgetItem = object  # type: ignore
    Qt = object()  # type: ignore
    # Provide aliases for use in the class
    QWidget, QVBoxLayout, QHBoxLayout = _QtQWidget, _QtQVBoxLayout, _QtQHBoxLayout
    QLabel, QPushButton, QScrollArea = _QtQLabel, _QtQPushButton, _QtQScrollArea
    QFrame, QListWidget, QListWidgetItem = _QtQFrame, _QtQListWidget, _QtQListWidgetItem

# Provide lightweight adapter classes (avoid direct subclassing issues when stubs)
SECTION_STYLE = "font-weight:600;color:#cfd3d6;padding:2px 4px;"
ITEM_STYLE = "color:#a6aaad;font-size:11px;"

class DashboardPlaceholder(_QtQWidget):  # type: ignore
    """Basic shelves implementation (phase 1):
    - Recently Added (chronological)
    - Top Rated (rating desc)
    - Tags (top tag frequencies)
    """
    def __init__(self, plugin: Any):
        super().__init__()
        self._plugin = plugin
        root = _QtQVBoxLayout(self)  # type: ignore
        header = _QtQHBoxLayout()  # type: ignore
        self._title = _QtQLabel("Dashboard / Shelves")  # type: ignore
        try: self._title.setStyleSheet("font-weight:600;color:#ccc;")  # type: ignore
        except Exception: pass
        header.addWidget(self._title)  # type: ignore
        header.addStretch(1)  # type: ignore
        self.refresh_button = _QtQPushButton("⟳")  # type: ignore
        try: self.refresh_button.setToolTip("Shelves neu aufbauen")  # type: ignore
        except Exception: pass
        try: self.refresh_button.clicked.connect(self.refresh)  # type: ignore[attr-defined]
        except Exception: pass
        header.addWidget(self.refresh_button)  # type: ignore
        root.addLayout(header)  # type: ignore

        # Scrollable body (in case of many tags)
        try:
            scroll = _QtQScrollArea()  # type: ignore
            scroll.setWidgetResizable(True)  # type: ignore[attr-defined]
            container = _QtQFrame()  # type: ignore
            self._body_layout = _QtQVBoxLayout(container)  # type: ignore
            scroll.setWidget(container)  # type: ignore[attr-defined]
            root.addWidget(scroll)  # type: ignore
        except Exception:
            self._body_layout = _QtQVBoxLayout()  # type: ignore
            root.addLayout(self._body_layout)  # type: ignore

        self.refresh()

    # ---------------------------------------------------------------- public
    def update_counts(self, total: int) -> None:
        try:
            self._title.setText(f"Dashboard / Shelves – {total} Dateien")  # type: ignore
        except Exception:
            pass

    def refresh(self) -> None:
        # Clear previous shelves
        try:
            while getattr(self._body_layout, 'count', lambda:0)():  # type: ignore[attr-defined]
                item = self._body_layout.takeAt(0)  # type: ignore[attr-defined]
                if item:
                    w = getattr(item, 'widget', lambda: None)()
                    if w:
                        try: w.deleteLater()
                        except Exception: pass
        except Exception:
            pass
        # Build shelves
        recent = self._query_recent()
        top_rated = self._query_top_rated()
        tags = self._aggregate_tags()
        self._add_section("Zuletzt hinzugefügt", [p.name for p in recent[:15]])
        self._add_section("Top bewertet", [f"{p.name} (★{r})" for p, r in top_rated[:15]])
        self._add_section("Tags", [f"{t} ({c})" for t, c in tags[:25]])

    # ---------------------------------------------------------------- internals
    def _add_section(self, title: str, items: List[str]):
        try:
            lbl = _QtQLabel(title)  # type: ignore
            lbl.setStyleSheet(SECTION_STYLE)  # type: ignore
            self._body_layout.addWidget(lbl)  # type: ignore[attr-defined]
            if not items:
                empty = QLabel("(leer)")  # type: ignore
                empty.setStyleSheet(ITEM_STYLE)  # type: ignore
                self._body_layout.addWidget(empty)  # type: ignore[attr-defined]
                return
            lst = QListWidget()  # type: ignore
            for text in items:
                it = QListWidgetItem(text)  # type: ignore
                lst.addItem(it)  # type: ignore
            self._body_layout.addWidget(lst)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _query_recent(self) -> List[Path]:
        out: List[Path] = []
        try:
            entries = self._plugin.list_recent_detailed(limit=200)  # type: ignore[attr-defined]
            for mf, root in entries:
                out.append((root / mf.path).resolve(False))
        except Exception:
            return out
        return out

    def _query_top_rated(self) -> List[Tuple[Path, int]]:
        results: List[Tuple[Path, int]] = []
        try:
            idx = getattr(self._plugin, '_library_index', None)
            if idx is None:
                return results
            # Direct SQL (rating DESC) fallback
            if hasattr(idx, '_conn') and hasattr(idx, '_lock'):
                with idx._lock:  # type: ignore[attr-defined]
                    cur = idx._conn.cursor()  # type: ignore[attr-defined]
                    cur.execute("SELECT s.path, f.path, f.rating FROM files f JOIN sources s ON f.source_id=s.id WHERE f.rating IS NOT NULL ORDER BY f.rating DESC, f.mtime DESC LIMIT 200")
                    for row in cur.fetchall():
                        src_root = Path(row[0])
                        rel = row[1]
                        rating = int(row[2]) if row[2] is not None else 0
                        results.append(((src_root / rel).resolve(False), rating))
        except Exception:
            return results
        return results

    def _aggregate_tags(self) -> List[Tuple[str, int]]:
        counts: Dict[str, int] = {}
        try:
            idx = getattr(self._plugin, '_library_index', None)
            if idx is None:
                return []
            if hasattr(idx, '_conn') and hasattr(idx, '_lock'):
                with idx._lock:  # type: ignore[attr-defined]
                    cur = idx._conn.cursor()  # type: ignore[attr-defined]
                    cur.execute("SELECT tags FROM files WHERE tags IS NOT NULL")
                    for (payload,) in cur.fetchall():
                        if not payload:
                            continue
                        import json
                        try:
                            parsed = json.loads(payload)
                            if isinstance(parsed, list):
                                for t in parsed:
                                    if not t:
                                        continue
                                    counts[t] = counts.get(t,0)+1
                        except Exception:
                            continue
        except Exception:
            return []
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
