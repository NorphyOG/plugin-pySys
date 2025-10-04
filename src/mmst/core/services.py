from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from .config import ConfigStore, PluginConfig
from .audio import AudioDeviceService
from .events import EventBus
from .progress import ProgressTracker


class NotificationCenter:
    """Lightweight pub/sub mechanism for core-to-plugin notifications."""

    def __init__(self) -> None:
        self._subscribers: List[Callable[["Notification"], None]] = []

    def subscribe(self, callback: Callable[["Notification"], None]) -> None:
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[["Notification"], None]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def publish(self, notification: "Notification") -> None:
        for subscriber in list(self._subscribers):
            try:
                subscriber(notification)
            except Exception:  # pragma: no cover - defensive logging occurs via core logger
                logging.getLogger("MMST.NotificationCenter").exception(
                    "Notification subscriber failed"
                )


@dataclass(frozen=True)
class Notification:
    message: str
    level: str = "info"
    source: Optional[str] = None


class CoreServices:
    """Shared services made available to plugins."""

    def __init__(
        self,
        app_name: str = "MMST",
        data_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.app_name = app_name
        self.data_dir = data_dir or self._resolve_data_dir(app_name)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logger or self._configure_logger(app_name)
        self.notifications = NotificationCenter()
        self._config_store = ConfigStore(self.data_dir / "config.json")
        self.audio_devices = AudioDeviceService(self.get_logger("AudioDeviceService"))
        self.event_bus = EventBus()
        self.progress = ProgressTracker()

    @staticmethod
    def _resolve_data_dir(app_name: str) -> Path:
        if os.name == "nt":
            base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / app_name.lower()

    @staticmethod
    def _configure_logger(app_name: str) -> logging.Logger:
        logger = logging.getLogger(app_name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def get_logger(self, name: str) -> logging.Logger:
        return self._logger.getChild(name)

    def send_notification(
        self, message: str, level: str = "info", *, source: Optional[str] = None
    ) -> None:
        notification = Notification(message=message, level=level, source=source)
        self.notifications.publish(notification)
        log_method = getattr(self._logger, level, self._logger.info)
        log_method("%s", message)

    def ensure_subdirectories(self, *relative_paths: str) -> Iterable[Path]:
        created = []
        for relative in relative_paths:
            target = self.data_dir / relative
            target.mkdir(parents=True, exist_ok=True)
            created.append(target)
        return created

    def get_plugin_config(self, identifier: str) -> PluginConfig:
        return self._config_store.get_plugin(identifier)

    def save_plugin_config(self, identifier: str, values: Dict[str, Any]) -> None:
        self._config_store.write_plugin(identifier, values)

    @property
    def config_store(self) -> ConfigStore:
        return self._config_store

    def get_app_config(self) -> PluginConfig:
        """Return the configuration bucket reserved for core dashboard state."""
        return self._config_store.get_plugin("__dashboard__")
