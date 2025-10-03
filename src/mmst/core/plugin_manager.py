from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import Dict, Iterable, Optional

from .plugin_base import BasePlugin, PluginManifest, PluginState
from .services import CoreServices

_logger = logging.getLogger("MMST.PluginManager")


@dataclass
class PluginRecord:
    manifest: PluginManifest
    instance: Optional[BasePlugin]
    module: ModuleType
    state: PluginState = PluginState.LOADED
    error: Optional[str] = None
    has_initialized: bool = False


class PluginManager:
    """Dynamic discovery and lifecycle management for plugins."""

    def __init__(
        self,
        services: CoreServices,
        namespace: str = "mmst.plugins",
        extra_search_paths: Optional[Iterable[str]] = None,
    ) -> None:
        self._services = services
        self._namespace = namespace
        self._records: Dict[str, PluginRecord] = {}
        self._extra_search_paths = list(extra_search_paths or [])

    @property
    def services(self) -> CoreServices:
        return self._services

    def discover(self) -> Dict[str, PluginRecord]:
        _logger.debug("Discovering plugins in namespace '%s'", self._namespace)
        try:
            package = importlib.import_module(self._namespace)
        except ModuleNotFoundError:
            _logger.warning("Plugin namespace '%s' could not be imported", self._namespace)
            return self._records

        search_paths = list(getattr(package, "__path__", []))
        search_paths.extend(self._extra_search_paths)

        for module_info in pkgutil.iter_modules(search_paths):
            package_name = f"{self._namespace}.{module_info.name}"
            plugin_module_name = f"{package_name}.plugin"
            if plugin_module_name in (record.module.__name__ for record in self._records.values()):
                continue
            try:
                plugin_module = importlib.import_module(plugin_module_name)
            except ModuleNotFoundError:
                _logger.debug("Module '%s' lacks a plugin.py, skipping", package_name)
                continue
            plugin_class = getattr(plugin_module, "Plugin", None)
            if not plugin_class or not issubclass(plugin_class, BasePlugin):
                _logger.warning(
                    "Plugin module '%s' does not expose a BasePlugin subclass named 'Plugin'",
                    plugin_module_name,
                )
                continue
            instance: Optional[BasePlugin] = None
            try:
                instance = plugin_class(self._services)
                manifest = instance.manifest
            except Exception as exc:
                manifest = PluginManifest(
                    identifier=plugin_module_name,
                    name=plugin_module_name,
                    description="Failed to load plugin",
                )
                self._records[manifest.identifier] = PluginRecord(
                    manifest=manifest,
                    instance=instance,
                    module=plugin_module,
                    state=PluginState.FAILED,
                    error=str(exc),
                )
                _logger.exception("Failed to instantiate plugin '%s'", plugin_module_name)
                continue

            if manifest.identifier in self._records:
                _logger.warning("Duplicate plugin identifier '%s'", manifest.identifier)
                continue

            self._records[manifest.identifier] = PluginRecord(
                manifest=manifest,
                instance=instance,
                module=plugin_module,
            )
            _logger.info("Loaded plugin '%s'", manifest.identifier)

        return self._records

    def iter_plugins(self) -> Iterable[PluginRecord]:
        return self._records.values()

    def get(self, identifier: str) -> Optional[PluginRecord]:
        return self._records.get(identifier)

    def start(self, identifier: str) -> PluginState:
        record = self._require_record(identifier)
        try:
            if record.instance is None:
                raise RuntimeError("Plugin instance is not available")
            if not record.has_initialized:
                record.instance.initialize()
                record.has_initialized = True
            record.instance.start()
            record.state = PluginState.STARTED
            record.error = None
        except Exception as exc:
            record.state = PluginState.FAILED
            record.error = str(exc)
            _logger.exception("Plugin '%s' failed to start", identifier)
            self._services.send_notification(
                f"Plugin '{record.manifest.name}' konnte nicht gestartet werden: {exc}",
                level="error",
                source=identifier,
            )
        return record.state

    def stop(self, identifier: str) -> PluginState:
        record = self._require_record(identifier)
        try:
            if record.instance is None:
                raise RuntimeError("Plugin instance is not available")
            record.instance.stop()
            record.state = PluginState.STOPPED
        except Exception as exc:
            record.state = PluginState.FAILED
            record.error = str(exc)
            _logger.exception("Plugin '%s' failed to stop", identifier)
        return record.state

    def shutdown(self) -> None:
        for record in self._records.values():
            try:
                if record.instance is not None:
                    record.instance.shutdown()
            except Exception:
                _logger.exception("Plugin '%s' failed during shutdown", record.manifest.identifier)

    def _require_record(self, identifier: str) -> PluginRecord:
        record = self._records.get(identifier)
        if not record:
            raise KeyError(f"Plugin '{identifier}' not found")
        return record
