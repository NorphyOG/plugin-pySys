from __future__ import annotations
"""Mini player skeleton (phase placeholder).

Responsibilities now:
  * Provide basic transport buttons (prev / play-pause / next)
  * Disabled progress slider placeholder (future: waveform / position)
  * Track label for currently "selected" media item (integrates later)

Kept intentionally logic-light so tests for the minimal widget remain
unaffected. Enhanced mode is optional and guarded by feature flag.
"""

from typing import Any

try:  # GUI imports
    from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QSlider
    from PySide6.QtCore import Qt, Signal
except Exception:  # pragma: no cover - headless fallback
    class _Stub:
        def __init__(self, *a, **k): pass
        def __getattr__(self, _): return lambda *a, **k: None
        def setText(self, *a, **k): pass
        def text(self): return ""
        def setFixedWidth(self, *a, **k): pass
        def setEnabled(self, *a, **k): pass
        def addWidget(self, *a, **k): pass
        def addStretch(self, *a, **k): pass
        def setStyleSheet(self, *a, **k): pass
    QWidget = QHBoxLayout = QPushButton = QLabel = QSlider = _Stub  # type: ignore
    class _Qt:  # type: ignore
        class Orientation: Horizontal = 0
    Qt = _Qt()  # type: ignore
    Signal = lambda *a, **k: None  # type: ignore


try:
    from PySide6.QtWidgets import QWidget as QtWidget  # type: ignore
    class MiniPlayerWidget(QtWidget):  # pragma: no cover - UI / stub friendly
        # Signal attributes if Qt present else simple lambdas
        try:
            play_toggled = Signal(bool)  # type: ignore
            previous_requested = Signal()  # type: ignore
            next_requested = Signal()  # type: ignore
        except Exception:  # type: ignore
            play_toggled = lambda *a, **k: None  # type: ignore
            previous_requested = lambda *a, **k: None  # type: ignore
            next_requested = lambda *a, **k: None  # type: ignore

        def __init__(self, plugin: Any):
            super().__init__()
            self._plugin = plugin
            self.setObjectName("MiniPlayerWidget")
            try:
                root = QHBoxLayout(self)  # type: ignore
            except Exception:
                self.root = QHBoxLayout()  # type: ignore
except Exception:
    # Fallback to non-QWidget for headless mode
    class MiniPlayerWidget:  # pragma: no cover - UI / stub friendly
        # Signal attributes if Qt present else simple lambdas
        try:
            play_toggled = Signal(bool)  # type: ignore
            previous_requested = Signal()  # type: ignore
            next_requested = Signal()  # type: ignore
        except Exception:  # type: ignore
            play_toggled = lambda *a, **k: None  # type: ignore
            previous_requested = lambda *a, **k: None  # type: ignore
            next_requested = lambda *a, **k: None  # type: ignore

        def __init__(self, plugin: Any):
            self._plugin = plugin
            self._widget_parent: Any = QWidget() if isinstance(QWidget, type) else QWidget  # type: ignore
            try:
                # When QWidget is real class set object name
                if hasattr(self._widget_parent, 'setObjectName'):
                    self._widget_parent.setObjectName("MiniPlayerWidget")  # type: ignore
            except Exception:
                pass
            try:
                self.root = QHBoxLayout(self._widget_parent)  # type: ignore
            except Exception:
                self.root = QHBoxLayout()  # type: ignore
        self.prev_btn = QPushButton("⏮")  # type: ignore
        self.play_btn = QPushButton("▶")  # type: ignore
        self.next_btn = QPushButton("⏭")  # type: ignore
        self.title_lbl = QLabel("– Kein Titel –")  # type: ignore
        self.slider = QSlider(getattr(Qt, 'Orientation', getattr(Qt, 'orientation', object())).Horizontal)  # type: ignore
        try:
            if hasattr(self.slider, 'setEnabled'):
                self.slider.setEnabled(False)  # placeholder disabled
            if hasattr(self.title_lbl, 'setStyleSheet'):
                self.title_lbl.setStyleSheet("color:#aaa;padding:0 6px;")  # type: ignore
            if isinstance(self.play_btn, QPushButton) and hasattr(self.play_btn, 'clicked'):
                try: self.play_btn.clicked.connect(self._on_play_clicked)  # type: ignore[attr-defined]
                except Exception: pass
            if isinstance(self.prev_btn, QPushButton) and hasattr(self.prev_btn, 'clicked'):
                try: self.prev_btn.clicked.connect(lambda: self.previous_requested.emit())  # type: ignore[attr-defined]
                except Exception: pass
            if isinstance(self.next_btn, QPushButton) and hasattr(self.next_btn, 'clicked'):
                try: self.next_btn.clicked.connect(lambda: self.next_requested.emit())  # type: ignore[attr-defined]
                except Exception: pass
        except Exception:
            pass
        for w in (self.prev_btn, self.play_btn, self.next_btn, self.title_lbl, self.slider):
            try:
                root.addWidget(w)  # type: ignore
            except Exception:
                pass
        try: root.addStretch(1)  # type: ignore
        except Exception: pass

    # Expose widget-like methods used by layout code
    def __getattr__(self, item):  # pragma: no cover - thin proxy
        return getattr(self._widget_parent, item)

    # ----------------------------------------------------------------- actions
    def set_title(self, title: str) -> None:
        try:
            self.title_lbl.setText(title or "– Kein Titel –")  # type: ignore
        except Exception:
            pass

    def _on_play_clicked(self) -> None:
        try:
            is_playing = self.play_btn.text() == "⏸"  # type: ignore
            new_state = not is_playing
            self.play_btn.setText("⏸" if new_state else "▶")  # type: ignore
            self.play_toggled.emit(new_state)  # type: ignore
        except Exception:
            pass
