from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtWidgets import QWidget
    from .services import CoreServices
    from .config import PluginConfig
else:  # pragma: no cover - fallback for tooling without PySide6
    QWidget = Any  # type: ignore[assignment]


@dataclass(frozen=True)
class PluginManifest:
    """Describes metadata required for every MMST plugin."""

    identifier: str
    name: str
    description: str
    version: str = "0.1.0"
    author: Optional[str] = None
    tags: Tuple[str, ...] = field(default_factory=tuple)


class PluginState(enum.Enum):
    """Lifecycle states reported by the plugin manager."""

    LOADED = "loaded"
    STARTED = "started"
    STOPPED = "stopped"
    FAILED = "failed"


class BasePlugin(ABC):
    """Base contract every plugin must implement."""

    def __init__(self, services: "CoreServices") -> None:
        self._services = services

    @property
    @abstractmethod
    def manifest(self) -> PluginManifest:
        """Return plugin metadata."""

    @abstractmethod
    def create_view(self) -> "QWidget":
        """Return the primary widget to embed in the dashboard."""

    def initialize(self) -> None:
        """Perform expensive setup tasks once after instantiation."""

    @abstractmethod
    def start(self) -> None:
        """Begin the plugin's active work."""

    def stop(self) -> None:
        """Stop the plugin and release transient resources."""

    def configure(self, parent: Optional["QWidget"] = None) -> None:
        """Open or execute configuration flows."""

    def shutdown(self) -> None:
        """Called when the application is closing."""

    @property
    def services(self) -> "CoreServices":
        return self._services

    @property
    def config(self) -> "PluginConfig":
        return self._services.get_plugin_config(self.manifest.identifier)
