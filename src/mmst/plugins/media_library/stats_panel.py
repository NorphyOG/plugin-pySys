"""Statistics panel extraction for Media Library plugin.

Encapsulates dashboard statistics refresh logic so `plugin.py` can shrink.
The panel wraps the existing `StatisticsDashboard` widget and provides
`refresh(index, metadata_loader)` API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Callable, Any

from .dashboard_stats import build_dashboard_stats  # type: ignore
from .statistics_dashboard import StatisticsDashboard  # type: ignore


class StatsPanel:
    def __init__(self) -> None:
        try:
            self.widget = StatisticsDashboard()
        except Exception:  # pragma: no cover - headless fallback
            self.widget = None  # type: ignore

    def connect_refresh(self, callback) -> None:
        try:
            if self.widget is not None:
                self.widget.refresh_requested.connect(callback)  # type: ignore[attr-defined]
        except Exception:
            pass

    def refresh(self, index, metadata_reader: Callable[[Path], Any]) -> None:
        if self.widget is None:
            return
        try:
            entries = index.list_files_with_sources()

            def metadata_loader(path: Path):
                return metadata_reader(path)

            def attribute_loader(path: Path):
                for media, src in entries:
                    abs_path = (src / Path(media.path)).resolve()
                    if abs_path == path:
                        return (media.rating, media.tags)
                return (None, tuple())

            result = build_dashboard_stats(entries, metadata_loader, attribute_loader)
            self.widget.update_statistics(result.stats)  # type: ignore[attr-defined]
        except Exception:
            pass

__all__ = ["StatsPanel"]
