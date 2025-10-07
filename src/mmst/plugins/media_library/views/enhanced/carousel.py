from __future__ import annotations

"""Reusable horizontal media carousel widget.

Initial skeleton keeps dependencies minimal so tests not depending on it remain unaffected.
Actual media population will be injected via a provider callback returning list[MediaCardData]-like objects.
"""
from typing import Callable, List, Any, Optional
import os, time

try:  # pragma: no cover
    from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QScrollArea, QFrame
    from PySide6.QtCore import Qt
except Exception:  # pragma: no cover
    QWidget = object  # type: ignore
    QHBoxLayout = QScrollArea = QLabel = QFrame = object  # type: ignore


from ...telemetry import get_telemetry_sink  # type: ignore


class MediaCarousel(QWidget):  # type: ignore[misc]
    def __init__(self, title: str, loader: Callable[[], List[Any]], *, chunk_size: int = 0):  # loader returns lightweight card data dicts
        super().__init__()
        self._loader = loader
        self._cards: List[Any] = []
        self._chunk_size = max(0, int(chunk_size))
        self._pending: List[Any] = []
        self._row_layout = None  # type: ignore
        self._batch_timer = None  # type: ignore
        self._title = title
        try:
            from PySide6.QtWidgets import QVBoxLayout
            outer = QVBoxLayout(self)
            heading = QLabel(title)
            heading.setObjectName("carousel_heading")
            heading.setStyleSheet("font-weight:600;font-size:14px")
            outer.addWidget(heading)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            frame = QFrame()
            row = QHBoxLayout(frame)
            row.setContentsMargins(0,0,0,0)
            row.setSpacing(8)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setWidget(frame)
            outer.addWidget(scroll)
            self._row_layout = row  # type: ignore
            from PySide6.QtCore import QTimer
            self._batch_timer = QTimer(self)
            self._batch_timer.setSingleShot(True)
            self._batch_timer.timeout.connect(self._consume_batch)  # type: ignore
        except Exception:
            self._row_layout = None  # type: ignore

    def refresh(self) -> None:
        started = time.perf_counter()
        sink = get_telemetry_sink() if os.environ.get("MMST_MEDIA_TELEMETRY_UI") == "1" else None
        try:
            self._cards = self._loader() or []
            if not self._row_layout:
                return
            # Auto hide if empty
            try:
                self.setVisible(bool(self._cards))  # type: ignore
            except Exception:
                pass
            # Clear existing
            while self._row_layout.count():  # type: ignore[attr-defined]
                item = self._row_layout.takeAt(0)  # type: ignore[attr-defined]
                w = getattr(item, 'widget', lambda: None)()
                if w is not None:
                    w.setParent(None)  # type: ignore
            self._pending = list(self._cards)
            if self._chunk_size and len(self._pending) > self._chunk_size and self._batch_timer:
                # Prime first chunk synchron
                self._add_cards(self._take_batch())
                self._schedule_next()
            else:
                self._add_cards(self._pending)
                self._pending.clear()
            # spacer
            self._row_layout.addStretch(1)  # type: ignore[attr-defined]
        finally:
            if sink:
                duration = time.perf_counter() - started
                sink.record("media_ui", f"carousel.refresh.{self._title}", duration, count=len(self._cards))

    # ---------------- internal helpers -----------------
    def _take_batch(self) -> List[Any]:
        if not self._pending:
            return []
        size = min(self._chunk_size, len(self._pending))
        batch, self._pending = self._pending[:size], self._pending[size:]
        return batch

    def _schedule_next(self) -> None:
        if self._batch_timer and self._pending:
            self._batch_timer.start(30)  # 30ms slice

    def _consume_batch(self) -> None:  # Qt timer callback
        batch = self._take_batch()
        if batch:
            self._add_cards(batch)
        self._schedule_next()

    def _add_cards(self, cards: List[Any]) -> None:
        try:
            if not self._row_layout:
                return
            from PySide6.QtWidgets import QLabel
            for c in cards:
                lbl = QLabel(str(getattr(c, 'title', getattr(c, 'name', c))))
                lbl.setObjectName("carousel_card")
                lbl.setMinimumWidth(120)
                lbl.setStyleSheet("border:1px solid #444;padding:6px;border-radius:4px")
                self._row_layout.addWidget(lbl)  # type: ignore[attr-defined]
        except Exception:
            pass

__all__ = ["MediaCarousel"]
