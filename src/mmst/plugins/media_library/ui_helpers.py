from __future__ import annotations

import re
from typing import Iterable, List, Sequence, cast

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QLineEdit,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class RatingStarBar(QWidget):
    """Interactive star rating selector."""

    ratingChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None, *, maximum: int = 5) -> None:
        super().__init__(parent)
        self._maximum = max(1, int(maximum))
        self._rating = 0
        self._updating = False
        self._suspend_signal = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._buttons: List[QToolButton] = []
        for index in range(1, self._maximum + 1):
            button = QToolButton(self)
            button.setAutoRaise(True)
            button.setCheckable(True)
            button.setToolTip(f"{index} Sterne")
            button.clicked.connect(lambda _checked, value=index: self.set_rating(value))
            layout.addWidget(button)
            self._buttons.append(button)
        clear_button = QToolButton(self)
        clear_button.setAutoRaise(True)
        clear_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
        clear_button.setToolTip("Bewertung zurücksetzen")
        clear_button.clicked.connect(lambda: self.set_rating(0))
        layout.addWidget(clear_button)
        layout.addStretch(1)
        self._refresh()

    def set_rating(self, value: int) -> None:
        value = max(0, min(int(value), self._maximum))
        if value == self._rating and not self._updating:
            return
        self._rating = value
        self._refresh()
        if not self._updating and not self._suspend_signal:
            self.ratingChanged.emit(self._rating)

    def rating(self) -> int:
        return self._rating

    def setMaximum(self, maximum: int) -> None:  # pragma: no cover - convenience
        self._maximum = max(1, int(maximum))
        self._rating = min(self._rating, self._maximum)
        self._refresh()

    def _refresh(self) -> None:
        self._updating = True
        try:
            for idx, button in enumerate(self._buttons, start=1):
                button.setText("★" if idx <= self._rating else "☆")
                button.setChecked(idx <= self._rating)
        finally:
            self._updating = False

    def update_rating(self, value: int) -> None:
        """Update rating without emitting a change signal."""
        previous_suspend = self._suspend_signal
        self._suspend_signal = True
        try:
            self.set_rating(value)
        finally:
            self._suspend_signal = previous_suspend


class FlowLayout(QLayout):
    """Flow layout adapted from Qt documentation examples."""

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 6) -> None:
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items: List[QLayoutItem] = []

    def __del__(self) -> None:  # pragma: no cover - Qt handles deletion
        while self._items:
            item = self._items.pop(0)
            if item:
                item.widget().setParent(None)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return cast(QLayoutItem, None)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0
        space_x = self.spacing()
        space_y = self.spacing()
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())

        for item in self._items:
            widget = item.widget()
            if widget is None or not widget.isVisible():
                continue
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y += line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y() + margins.bottom()


class TagChip(QFrame):
    removed = Signal(str)

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setObjectName("TagChip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(4)
        label = QLabel(text, self)
        layout.addWidget(label)
        button = QToolButton(self)
        button.setAutoRaise(True)
        button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
        button.setToolTip("Tag entfernen")
        button.clicked.connect(lambda: self.removed.emit(self._text))
        layout.addWidget(button)
        self.setStyleSheet(
            "#TagChip { border: 1px solid rgba(255,255,255,0.2); border-radius: 12px;"
            " background-color: rgba(255,255,255,0.08); }"
        )

    def text(self) -> str:
        return self._text


class TagEditor(QWidget):
    tagsChanged = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._container = QWidget(self)
        self._flow = FlowLayout(self._container, spacing=6)
        self._container.setLayout(self._flow)

        self._input = QLineEdit(self)
        self._input.setPlaceholderText("Tag hinzufügen…")
        self._input.returnPressed.connect(self._commit_input)
        self._input.textEdited.connect(self._maybe_commit_delimiter)

        layout.addWidget(self._container)
        layout.addWidget(self._input)

        self._tags: List[str] = []

    def set_tags(self, tags: Sequence[str]) -> None:
        normalized = []
        seen = set()
        for tag in tags:
            cleaned = tag.strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(cleaned)
        if normalized == self._tags:
            return
        self._tags = normalized
        self._refresh()

    def tags(self) -> List[str]:
        return list(self._tags)

    def clear(self) -> None:
        if not self._tags:
            return
        self._tags.clear()
        self._refresh()
        self.tagsChanged.emit(self.tags())

    def commit_pending_input(self) -> None:
        """Ensure the current line edit contents are turned into tags."""
        if self._input.text().strip():
            self._commit_input()

    def setEnabled(self, enabled: bool) -> None:  # pragma: no cover - Qt base override
        super().setEnabled(enabled)
        self._input.setEnabled(enabled)
        self._container.setEnabled(enabled)

    def _refresh(self) -> None:
        while self._flow.count():
            item = self._flow.takeAt(0)
            if not item:
                continue
            widget = item.widget()
            if widget:
                widget.setParent(None)
        for tag in self._tags:
            chip = TagChip(tag, self._container)
            chip.removed.connect(self._on_chip_removed)
            self._flow.addWidget(chip)

    def _on_chip_removed(self, tag: str) -> None:
        self._tags = [existing for existing in self._tags if existing.lower() != tag.lower()]
        self._refresh()
        self.tagsChanged.emit(self.tags())

    def _commit_input(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        tokens = [token.strip() for token in re.split(r"[,;]\s*", text) if token.strip()]
        changed = False
        for token in tokens:
            key = token.lower()
            if key in (existing.lower() for existing in self._tags):
                continue
            self._tags.append(token)
            changed = True
        self._input.clear()
        if changed:
            self._refresh()
            self.tagsChanged.emit(self.tags())

    def _maybe_commit_delimiter(self, text: str) -> None:
        if any(text.endswith(delim) for delim in (",", ";")):
            self._commit_input()


class BatchMetadataDialog(QDialog):
    """Dialog that lets the user apply rating/tags to multiple files."""

    def __init__(self, count: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stapelaktionen – Metadaten")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{count} Dateien ausgewählt"))

        self._rating_checkbox = QCheckBox("Bewertung setzen")
        self._rating_bar = RatingStarBar(self)
        self._rating_bar.setEnabled(False)
        self._rating_checkbox.toggled.connect(self._rating_bar.setEnabled)
        layout.addWidget(self._rating_checkbox)
        layout.addWidget(self._rating_bar)

        self._tags_checkbox = QCheckBox("Tags ersetzen")
        self._tag_editor = TagEditor(self)
        self._tag_editor.setEnabled(False)
        self._tags_checkbox.toggled.connect(self._tag_editor.setEnabled)
        layout.addWidget(self._tags_checkbox)
        layout.addWidget(self._tag_editor)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_rating(self) -> int | None:
        if not self._rating_checkbox.isChecked():
            return None
        return self._rating_bar.rating()

    def selected_tags(self) -> List[str] | None:
        if not self._tags_checkbox.isChecked():
            return None
        self._tag_editor.commit_pending_input()
        return self._tag_editor.tags()
