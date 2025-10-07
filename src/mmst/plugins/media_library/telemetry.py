"""Lightweight telemetry helpers for the MediaLibrary plugin."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

__all__ = [
    "TelemetrySink",
    "get_telemetry_sink",
    "reset_telemetry_sink",
]

_ENV_VAR = "MMST_MEDIA_LIBRARY_TELEMETRY"


class TelemetrySink:
    """Thread-safe sink that appends telemetry events to a JSON lines file."""

    def __init__(self, target: Path) -> None:
        self._target = target
        self._lock = threading.Lock()
        target.parent.mkdir(parents=True, exist_ok=True)

    def record(self, category: str, name: str, duration: float, count: Optional[int] = None) -> None:
        payload: dict[str, Any] = {
            "ts": time.time(),
            "category": str(category),
            "name": str(name),
            "duration": float(duration),
        }
        if count is not None:
            payload["count"] = int(count)
        try:
            with self._lock, self._target.open("a", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False)
                handle.write("\n")
        except OSError:
            # Telemetry must never break the app; drop the sample on failure.
            pass


_sink_lock = threading.Lock()
_sink: Optional[TelemetrySink] = None


def get_telemetry_sink() -> Optional[TelemetrySink]:
    """Return a singleton telemetry sink if the environment enables it."""

    global _sink
    if _sink is not None:
        return _sink
    path = os.environ.get(_ENV_VAR)
    if not path:
        return None
    candidate = Path(path).expanduser()
    with _sink_lock:
        if _sink is None:
            try:
                _sink = TelemetrySink(candidate)
            except OSError:
                _sink = None
        return _sink


def reset_telemetry_sink() -> None:
    """Reset the cached telemetry sink (useful for tests)."""

    global _sink
    with _sink_lock:
        _sink = None
