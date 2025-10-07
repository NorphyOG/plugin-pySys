from __future__ import annotations
"""Explorer-like sidebar navigation skeleton.
Provides sections: SOURCES, PLAYLISTS, SMART, TAGS.
Signals selection changes via a simple callback registration.
"""
from typing import Callable, List, Dict, Any, Optional, Tuple

try:  # pragma: no cover
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
        QMenu, QInputDialog
    )
    from PySide6.QtCore import Qt
    _HAS_QT = True
except Exception:  # pragma: no cover
    QWidget = object  # type: ignore
    QVBoxLayout = QLabel = QListWidget = QListWidgetItem = object  # type: ignore
    QMenu = QInputDialog = object  # type: ignore
    Qt = object  # type: ignore
    _HAS_QT = False

class Sidebar(QWidget):  # type: ignore[misc]
    """Sidebar mit Kontextmenüs (Playlists, Smart, Tags).

    data_provider(section)->List[objects]
    Optional CRUD callbacks set via setters (no hard dependency on backend specifics).
    """
    def __init__(self, data_provider: Callable[[str], List[Dict[str, Any]]] ):
        super().__init__()
        self._provider = data_provider
        self._on_select: List[Callable[[str, Dict[str, Any]], None]] = []
        # optional injected callbacks
        self._cb_new_playlist: Optional[Callable[[str], None]] = None
        self._cb_rename_playlist: Optional[Callable[[str, str], None]] = None
        self._cb_delete_playlist: Optional[Callable[[str], None]] = None
        self._cb_new_smart: Optional[Callable[[str], None]] = None
        self._cb_new_tag: Optional[Callable[[str], None]] = None
        self._cb_rename_tag: Optional[Callable[[str, str], None]] = None
        self._cb_delete_tag: Optional[Callable[[str], None]] = None
        try:
            layout = QVBoxLayout(self) if _HAS_QT else None  # type: ignore
            title = QLabel("Navigation") if _HAS_QT else None  # type: ignore
            if title and hasattr(title, 'setStyleSheet'):
                title.setStyleSheet("font-weight:600")  # type: ignore[attr-defined]
            if layout and title and hasattr(layout, 'addWidget'):
                layout.addWidget(title)  # type: ignore[attr-defined]
            self.list_widget = QListWidget() if _HAS_QT else None  # type: ignore
            if layout and self.list_widget and hasattr(layout, 'addWidget'):
                layout.addWidget(self.list_widget)  # type: ignore[attr-defined]
            if self.list_widget and hasattr(self.list_widget, 'itemSelectionChanged'):
                try: self.list_widget.itemSelectionChanged.connect(self._emit_selection)  # type: ignore[attr-defined]
                except Exception: pass
            if self.list_widget and _HAS_QT and hasattr(self.list_widget, 'setContextMenuPolicy'):
                try:
                    self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # type: ignore[attr-defined]
                    self.list_widget.customContextMenuRequested.connect(self._open_context_menu)  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception:
            self.list_widget = None  # type: ignore
        self.refresh()

    def on_select(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        self._on_select.append(callback)

    # ---- public setter for CRUD callbacks ----
    def set_playlist_callbacks(self, new_cb=None, rename_cb=None, delete_cb=None):
        self._cb_new_playlist = new_cb; self._cb_rename_playlist = rename_cb; self._cb_delete_playlist = delete_cb
    def set_smart_callbacks(self, new_cb=None):
        self._cb_new_smart = new_cb
    def set_tag_callbacks(self, new_cb=None, rename_cb=None, delete_cb=None):
        self._cb_new_tag = new_cb; self._cb_rename_tag = rename_cb; self._cb_delete_tag = delete_cb

    def refresh(self) -> None:
        if not self.list_widget or not _HAS_QT:
            return
        try:
            if hasattr(self.list_widget, 'clear'):
                self.list_widget.clear()  # type: ignore[attr-defined]
            for section in ("actions", "sources", "playlists", "smart", "tags"):
                items = self._provider(section)
                if not items:
                    continue
                try:
                    header = QListWidgetItem(f"[{section.upper()}]")  # type: ignore
                    # below: magic bit removal only if flags attr exists
                    if hasattr(header, 'flags'):
                        try: header.setFlags(header.flags() & ~0x1)  # type: ignore[attr-defined]
                        except Exception: pass
                    self.list_widget.addItem(header)  # type: ignore[attr-defined]
                except Exception:
                    continue
                for obj in items:
                    try:
                        name = obj.get("name") or obj.get("title") or obj.get("id") or "?"
                        it = QListWidgetItem(f"  {name}")  # type: ignore
                        if hasattr(it, 'setData'):
                            it.setData(32, (section, obj))  # type: ignore[attr-defined]
                        self.list_widget.addItem(it)  # type: ignore[attr-defined]
                    except Exception:
                        continue
        except Exception:
            return

    def _emit_selection(self) -> None:
        if not self.list_widget or not _HAS_QT:
            return
        try:
            selected = self.list_widget.selectedItems()  # type: ignore[attr-defined]
            if not selected:
                return
            item = selected[0]
            data = item.data(32) if hasattr(item, 'data') else None  # type: ignore[attr-defined]
            if not data or not isinstance(data, tuple):
                return
            section, payload = data
            for cb in list(self._on_select):
                try: cb(section, payload)
                except Exception: continue
        except Exception:
            return

    # ---------------- context menu -----------------
    def _open_context_menu(self, pos):  # type: ignore
        if not self.list_widget or not _HAS_QT:
            return
        try:
            item = self.list_widget.itemAt(pos)  # type: ignore[attr-defined]
            section = None; payload = {}
            if item and hasattr(item, 'data'):
                data = item.data(32)  # type: ignore[attr-defined]
                if isinstance(data, tuple): section, payload = data
            menu = QMenu(self)  # type: ignore
            def _add_action(text, handler):
                try:
                    if _HAS_QT:
                        from PySide6.QtGui import QAction  # type: ignore
                        act = QAction(text, menu)  # type: ignore
                        act.triggered.connect(handler)  # type: ignore[attr-defined]
                        menu.addAction(act)  # type: ignore[attr-defined]
                    else:
                        pass
                except Exception: pass
            pl_new = self._cb_new_playlist
            if pl_new: _add_action("Neue Playlist…", lambda cb=pl_new: self._prompt_and_call(cb, "Playlist-Namen eingeben:"))
            sp_new = self._cb_new_smart
            if sp_new: _add_action("Neue Smart Playlist…", lambda cb=sp_new: self._prompt_and_call(cb, "Smart Playlist-Namen eingeben:"))
            tag_new = self._cb_new_tag
            if tag_new: _add_action("Neuer Tag…", lambda cb=tag_new: self._prompt_and_call(cb, "Tag-Namen eingeben:"))
            if section == 'playlists' and payload:
                pl_ren = self._cb_rename_playlist
                if pl_ren: _add_action("Playlist umbenennen…", lambda cb=pl_ren: self._prompt_and_call(cb, "Neuer Name:", payload.get('name')))
                pl_del = self._cb_delete_playlist
                if pl_del: _add_action("Playlist löschen", lambda cb=pl_del: cb(payload.get('name') or ""))
            if section == 'tags' and payload:
                t_ren = self._cb_rename_tag
                if t_ren: _add_action("Tag umbenennen…", lambda cb=t_ren: self._prompt_and_call(cb, "Neuer Tag-Name:", payload.get('name')))
                t_del = self._cb_delete_tag
                if t_del: _add_action("Tag löschen", lambda cb=t_del: cb(payload.get('name') or ""))
            try: menu.exec(self.list_widget.mapToGlobal(pos))  # type: ignore[attr-defined]
            except Exception: pass
        except Exception:
            return

    def _prompt_and_call(self, fn: Callable, prompt: str, preset: str|None=None):  # type: ignore
        if not callable(fn):
            return
        try:
            if not _HAS_QT or QInputDialog is object:
                name = preset or "neu"
                if fn in (self._cb_rename_playlist, self._cb_rename_tag):
                    fn(name, name + "_renamed")  # type: ignore
                else:
                    fn(name)  # type: ignore
                return
            text, ok = QInputDialog.getText(self, "Eingabe", prompt, text=preset or "")  # type: ignore[attr-defined]
            if ok and text.strip():
                if fn in (self._cb_rename_playlist, self._cb_rename_tag):
                    fn(preset, text.strip())  # type: ignore
                else:
                    fn(text.strip())  # type: ignore
        except Exception:
            return

__all__ = ["Sidebar"]
