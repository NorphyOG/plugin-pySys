from __future__ import annotations

from typing import Optional, Any

from ...core.plugin_base import BasePlugin, PluginManifest

try:  # pragma: no cover - optional GUI dependency
    from PySide6.QtWidgets import QWidget
except ImportError:
    QWidget = object  # type: ignore

# Import our widgets module that contains ExplorerWidget
try:
    from .widgets import ExplorerWidget
except ImportError:
    ExplorerWidget = None  # type: ignore


class Plugin(BasePlugin):
    """Standalone Explorer plugin with three-pane file browser UI.
    
    Features:
    - Quick access sidebar with favorites and disk health monitoring
    - Main view with grid/list/details modes and breadcrumb navigation
    - Details panel with live preview and metadata extraction
    """

    def __init__(self, services):  # type: ignore[override]
        super().__init__(services)
        self._manifest = PluginManifest(
            identifier="mmst.explorer",
            name="Explorer",
            description="Drei-Spalten-Dateiexplorer mit Quick-Access, Breadcrumbs und Vorschau.",
            version="1.0.0",
            author="MMST Team",
            tags=("files", "explorer", "filesystem"),
        )
        self._widget = None  # type: Optional[Any]

    @property
    def manifest(self) -> PluginManifest:  # type: ignore[override]
        return self._manifest

    def create_view(self) -> QWidget:  # type: ignore[override]
        if self._widget is None:
            if ExplorerWidget is None:
                raise RuntimeError(
                    "ExplorerWidget ist nicht verfügbar – stellen Sie sicher, dass PySide6 installiert ist."
                )
            self._widget = ExplorerWidget(self)  # type: ignore[call-arg]
        return self._widget

    def initialize(self) -> None:  # type: ignore[override]
        self.services.ensure_subdirectories("explorer")

    def start(self) -> None:  # type: ignore[override]
        # Future: Restore last directory, view mode, favorites from config
        if hasattr(self, '_widget') and self._widget is not None:
            self.services.send_notification(
                "Explorer gestartet",
                level="info",
                source=self.manifest.identifier
            )

    def stop(self) -> None:  # type: ignore[override]
        # Future: Save state (current directory, view mode, favorites) to config
        pass


__all__ = ["Plugin"]
