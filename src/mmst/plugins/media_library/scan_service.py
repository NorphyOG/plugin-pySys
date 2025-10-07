"""Filesystem scanning & watcher service extraction.

Provides a small facade for:
  * Adding a new source (scan directory with progress callback)
  * Full rescan of all sources
  * Starting/stopping filesystem watcher and routing events back to plugin

The plugin supplies callbacks for UI (progress, completion, library refresh,
notifications) and provides access to `LibraryIndex`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Optional, Any

from .core import scan_source  # type: ignore
from .watcher import FileSystemWatcher  # type: ignore


ProgressCB = Callable[[str, int, int], None]
NotifyCB = Callable[[str, str], None]
RefreshCB = Callable[[], None]


class ScanService:
    def __init__(self, library_index, notify: NotifyCB, refresh: RefreshCB) -> None:
        self._index = library_index
        self._notify = notify
        self._refresh = refresh
        self._watcher = FileSystemWatcher()
        self._watcher_active = False

    # ------------- Scanning -------------
    def scan_new_source(self, source_path: Path, progress: Optional[ProgressCB] = None) -> int:
        count = scan_source(source_path, self._index, progress=progress)
        if self._watcher_active and self._watcher.is_watching:
            self._watcher.add_path(source_path, recursive=True)
        self._refresh()
        return count

    def full_rescan(self, progress: Optional[ProgressCB] = None) -> int:
        total = 0
        sources = self._index.list_sources()
        for _, path_str in sources:
            p = Path(path_str)
            total += scan_source(p, self._index, progress=progress)
        self._refresh()
        return total

    # ------------- Watcher -------------
    def start_watcher(self) -> bool:
        if not self._watcher.is_available:
            return False

        def on_created(path: Path) -> None:
            self._index.add_file_by_path(path); self._refresh()
        def on_modified(path: Path) -> None:
            self._index.update_file_by_path(path); self._refresh()
        def on_deleted(path: Path) -> None:
            self._index.remove_file_by_path(path); self._refresh()
        def on_moved(old: Path, new: Path) -> None:
            self._index.remove_file_by_path(old); self._index.add_file_by_path(new); self._refresh()

        if not self._watcher.start(
            on_created=on_created,
            on_modified=on_modified,
            on_deleted=on_deleted,
            on_moved=on_moved,
        ):
            return False
        for _, path_str in self._index.list_sources():
            self._watcher.add_path(Path(path_str), recursive=True)
        self._watcher_active = True
        return True

    def stop_watcher(self) -> None:
        try:
            self._watcher.stop()
        finally:
            self._watcher_active = False

    # ------------- Introspection -------------
    @property
    def watcher_active(self) -> bool:
        return self._watcher_active and self._watcher.is_watching

    def watched_path_count(self) -> int:
        try:
            return len(self._watcher.get_watched_paths()) if self.watcher_active else 0
        except Exception:
            return 0

__all__ = ["ScanService"]
