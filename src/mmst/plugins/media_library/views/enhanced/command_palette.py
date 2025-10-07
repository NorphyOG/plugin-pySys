from __future__ import annotations
"""Simple command palette overlay for Media Library.
Provides fuzzy-ish prefix filtering over registered commands.
"""
from typing import Callable, List, Dict, Any

try:  # pragma: no cover
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QShortcut
    )
    from PySide6.QtGui import QKeySequence
    from PySide6.QtCore import Qt
except Exception:  # pragma: no cover
    QWidget = object  # type: ignore
    QVBoxLayout = QLineEdit = QListWidget = QListWidgetItem = QShortcut = object  # type: ignore
    QKeySequence = Qt = object  # type: ignore

class CommandPalette(QWidget):  # type: ignore[misc]
    def __init__(self, plugin: Any, commands: Dict[str, Callable[[], None]]):
        super().__init__()
        self._plugin = plugin
        self._commands = commands
        self._items: List[str] = sorted(commands.keys())
        try:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.Tool)  # type: ignore[attr-defined]
            layout = QVBoxLayout(self)
            self.filter_edit = QLineEdit()  # type: ignore
            self.filter_edit.setPlaceholderText("Befehl suchen…")  # type: ignore[attr-defined]
            self.filter_edit.textChanged.connect(self._refilter)  # type: ignore[attr-defined]
            layout.addWidget(self.filter_edit)  # type: ignore
            self.list_widget = QListWidget()  # type: ignore
            layout.addWidget(self.list_widget)  # type: ignore
            self.list_widget.itemActivated.connect(self._run_current)  # type: ignore[attr-defined]
            self._populate(self._items)
            # Esc schließt
            QShortcut(QKeySequence("Esc"), self, activated=self.close)  # type: ignore
        except Exception:
            pass

    def open(self):  # noqa: D401
        try:
            if hasattr(self, 'filter_edit'):
                self.filter_edit.clear()  # type: ignore[attr-defined]
                self._populate(self._items)
                self.show()  # type: ignore[attr-defined]
                self.raise_()  # type: ignore[attr-defined]
                self.activateWindow()  # type: ignore[attr-defined]
        except Exception:
            pass

    # --------------- internal -----------------
    def _populate(self, names: List[str]):
        try:
            self.list_widget.clear()  # type: ignore[attr-defined]
            for name in names:
                self.list_widget.addItem(QListWidgetItem(name))  # type: ignore[attr-defined]
            if self.list_widget.count():  # type: ignore[attr-defined]
                self.list_widget.setCurrentRow(0)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _refilter(self, text: str) -> None:
        if not text:
            self._populate(self._items)
            return
        lowered = text.lower()
        filtered = [n for n in self._items if lowered in n.lower()]
        self._populate(filtered)

    def _run_current(self) -> None:
        try:
            items = self.list_widget.selectedItems()  # type: ignore[attr-defined]
            if not items:
                return
            name = items[0].text()  # type: ignore[attr-defined]
            fn = self._commands.get(name)
            if fn:
                fn()
                self.close()
        except Exception:
            pass

__all__ = ["CommandPalette"]
