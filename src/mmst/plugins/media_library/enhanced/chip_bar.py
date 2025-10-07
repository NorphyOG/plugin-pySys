from __future__ import annotations
"""Lightweight filter chip bar for Ultra mode.

Shows active filters (search, rating min, tags) as dismissible chips.
Headless-safe: all Qt calls wrapped in try/except and attribute existence checks.
"""
from typing import List, Callable, Any

try:  # pragma: no cover - GUI imports
    from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
    from PySide6.QtCore import Signal
except Exception:  # pragma: no cover
    class _Stub:
        def __init__(self, *a, **k): pass
        def __getattr__(self, _): return lambda *a, **k: None
    QWidget = _Stub  # type: ignore
    QHBoxLayout = QPushButton = QLabel = _Stub  # type: ignore
    Signal = lambda *a, **k: None  # type: ignore


class ChipBarWidget(QWidget):  # type: ignore[misc]
    chip_removed = Signal(str)  # str key of removed chip  # type: ignore

    def __init__(self):
        super().__init__()
        self._chips: dict[str, Any] = {}
        try:
            self.setObjectName("chipBar")  # type: ignore
            self.setStyleSheet(
                """
                #chipBar { background:transparent; }
                #chipBar QPushButton { background:#262a2d; border:1px solid #353a3e; border-radius:12px; padding:2px 8px; font-size:11px; }
                #chipBar QPushButton:hover { border-color:#4a545a; }
                """
            )  # type: ignore
        except Exception:
            pass
        try:
            self._layout = QHBoxLayout(self)  # type: ignore
            self._layout.setContentsMargins(0,0,0,0)  # type: ignore
            self._layout.setSpacing(6)  # type: ignore
            self._layout.addStretch(1)  # right spacer so chips left-align
        except Exception:
            self._layout = None

    # -------------- public API -----------------
    def set_state(self, *, search: str|None, rating_min: int|None, tags: List[str]|None):
        """Update displayed chips to reflect current filter state."""
        wanted: dict[str, str] = {}
        if search:
            wanted['search'] = f"🔍 {search[:32]}" + ("…" if len(search) > 32 else "")
        if rating_min and rating_min > 0:
            wanted['rating'] = "⭐" * int(rating_min)
        if tags:
            # collapse if too many
            if len(tags) <= 4:
                for t in tags:
                    wanted[f"tag:{t}"] = f"🏷 {t}"
            else:
                wanted['tags'] = f"🏷 {len(tags)} Tags"
        # remove obsolete
        for key in list(self._chips.keys()):
            if key not in wanted:
                self._remove_chip_widget(key)
        # add/update needed
        for key, label in wanted.items():
            if key in self._chips:
                btn = self._chips[key]
                try: btn.setText(label + " ✕")  # type: ignore
                except Exception: pass
            else:
                self._add_chip(key, label)

    # -------------- internals ------------------
    def _add_chip(self, key: str, label: str):
        try:
            btn = QPushButton(label + " ✕")  # type: ignore
            btn.setObjectName("chip")  # type: ignore
            btn.clicked.connect(lambda _=False, k=key: self._on_chip_clicked(k))  # type: ignore[attr-defined]
            # insert before stretch (assumed last item)
            if self._layout is not None and hasattr(self._layout, 'insertWidget') and hasattr(self._layout, 'count'):
                try:
                    cnt = self._layout.count()  # type: ignore[attr-defined]
                    if not isinstance(cnt, int):
                        raise TypeError
                    stretch_index = max(0, cnt - 1)
                    self._layout.insertWidget(stretch_index, btn)  # type: ignore[attr-defined]
                except Exception:
                    try: self._layout.addWidget(btn)  # type: ignore[attr-defined]
                    except Exception: pass
            self._chips[key] = btn
        except Exception:
            self._chips[key] = object()

    def _remove_chip_widget(self, key: str):
        btn = self._chips.pop(key, None)
        try:
            if btn and hasattr(btn, 'setParent'):
                btn.setParent(None)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _on_chip_clicked(self, key: str):
        # emit removal and let controller clear underlying filter
        try:
            if hasattr(self, 'chip_removed'):
                self.chip_removed.emit(key)  # type: ignore[attr-defined]
        except Exception:
            pass
        self._remove_chip_widget(key)

__all__ = ["ChipBarWidget"]
