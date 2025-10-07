"""Event loop monitoring helpers for the MediaLibrary plugin."""

from __future__ import annotations

import time
from typing import Optional

from .telemetry import get_telemetry_sink

try:  # pragma: no cover - PySide6 may be unavailable during tests
    from PySide6.QtCore import QObject, QTimer, Qt
except Exception:  # pragma: no cover - headless fallback
    QObject = object  # type: ignore
    QTimer = None  # type: ignore
    Qt = None  # type: ignore


class _NullMonitor:
    """Fallback monitor when Qt is unavailable."""

    def start(self) -> None:  # pragma: no cover - trivial
        pass

    def stop(self) -> None:  # pragma: no cover - trivial
        pass


class _QtEventLoopMonitor(QObject):
    """Record event loop stalls above a configurable threshold."""

    def __init__(self, interval_ms: int, threshold_ms: int) -> None:
        super().__init__()
        self._interval_ms = max(1, int(interval_ms))
        self._threshold_sec = max(0.0, float(threshold_ms) / 1000.0)
        self._timer = QTimer(self)  # type: ignore[arg-type]
        if Qt is not None:  # pragma: no branch - guard for mypy
            try:
                self._timer.setTimerType(Qt.PreciseTimer)  # type: ignore[attr-defined]
            except Exception:
                pass
        self._timer.setInterval(self._interval_ms)
        try:
            self._timer.timeout.connect(self._on_tick)  # type: ignore[attr-defined]
        except Exception:
            pass
        self._last_tick: Optional[float] = None

    def start(self) -> None:
        self._last_tick = None
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _on_tick(self) -> None:
        now = time.perf_counter()
        if self._last_tick is None:
            self._last_tick = now
            return
        elapsed = now - self._last_tick
        self._last_tick = now
        if elapsed <= 0:
            return
        expected = self._interval_ms / 1000.0
        delay = elapsed - expected
        if delay < self._threshold_sec:
            return
        sink = get_telemetry_sink()
        if sink is None:
            return
        try:
            sink.record("event_loop", "block", delay, None)
        except Exception:
            # Telemetry must stay best-effort.
            pass


def create_event_loop_monitor(interval_ms: int = 16, threshold_ms: int = 16):
    """Create an event loop monitor for the current environment."""

    if QTimer is None:
        return _NullMonitor()
    return _QtEventLoopMonitor(interval_ms=interval_ms, threshold_ms=threshold_ms)
