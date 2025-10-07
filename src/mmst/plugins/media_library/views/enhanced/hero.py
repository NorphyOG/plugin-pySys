from __future__ import annotations
"""Hero/Featured section skeleton.
Chooses a random recent item (title only) and displays a large label.
"""
import random, time, os
from typing import List, Any, Callable
from ...telemetry import get_telemetry_sink  # type: ignore

try:  # pragma: no cover
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
except Exception:  # pragma: no cover
    QWidget = object  # type: ignore
    QVBoxLayout = QLabel = QPushButton = object  # type: ignore

class HeroWidget(QWidget):  # type: ignore[misc]
    def __init__(self, provider: Callable[[], List[Any]]):
        super().__init__()
        self._provider = provider
        try:
            from PySide6.QtWidgets import QHBoxLayout
            layout = QVBoxLayout(self)
            header = QHBoxLayout()
            self.title_label = QLabel("–")
            self.title_label.setObjectName("hero_title")
            self.title_label.setStyleSheet("font-size:20px;font-weight:700;padding:4px 2px")
            header.addWidget(self.title_label)
            self.close_button = QPushButton("✕")
            self.close_button.setFixedWidth(26)
            self.close_button.setStyleSheet("QPushButton{background:#2b2b2b;border:1px solid #444;border-radius:3px;}QPushButton:hover{border-color:#666}")
            self.close_button.clicked.connect(self._hide_self)  # type: ignore
            header.addWidget(self.close_button)
            header.addStretch(1)
            layout.addLayout(header)
            self.refresh_button = QPushButton("↻ Aktualisieren")
            self.refresh_button.clicked.connect(self.refresh)  # type: ignore
            layout.addWidget(self.refresh_button)
        except Exception:
            self.title_label = None  # type: ignore

    def refresh(self) -> None:
        started = time.perf_counter()
        sink = get_telemetry_sink() if os.environ.get("MMST_MEDIA_TELEMETRY_UI") == "1" else None
        try:
            items = self._provider() or []
            if not items:
                # Auto-hide hero region (avoid large empty area)
                try:
                    self.setVisible(False)  # type: ignore
                except Exception:
                    pass
                return
            choice = random.choice(items)
            title = getattr(choice, 'title', getattr(choice, 'name', '–'))
            if self.title_label:
                self.title_label.setText(title)  # type: ignore
        finally:
            if sink:
                duration = time.perf_counter() - started
                sink.record("media_ui", "hero.refresh", duration, count=len(items) if 'items' in locals() else None)

    def _hide_self(self) -> None:
        try:
            self.setVisible(False)  # type: ignore
            # Persist via plugin if available
            try:
                plugin = getattr(self.parent(), '_plugin', None) or getattr(self, '_plugin', None)
                if plugin and hasattr(plugin, '_set_hero_hidden'):
                    plugin._set_hero_hidden(True)  # type: ignore
            except Exception:
                pass
        except Exception:
            pass

__all__ = ["HeroWidget"]
