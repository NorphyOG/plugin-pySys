from __future__ import annotations

import types
from pathlib import Path
from typing import Dict, Iterable, Optional

from PySide6.QtWidgets import QApplication, QWidget

from mmst.core.app import DashboardWindow
from mmst.core.plugin_base import BasePlugin, PluginManifest, PluginState
from mmst.core.plugin_manager import PluginRecord
from mmst.core.services import CoreServices


def ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class StubPlugin(BasePlugin):
    def __init__(self, services: CoreServices) -> None:
        super().__init__(services)
        self._manifest = PluginManifest(
            identifier="stub.plugin",
            name="Stub Plugin",
            description="Stub plugin for dashboard tests",
        )
        self.started = False

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def create_view(self) -> QWidget:
        return QWidget()

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


class StubPluginManager:
    def __init__(self, services: CoreServices) -> None:
        self._services = services
        self._plugin = StubPlugin(services)
        module = types.SimpleNamespace(__name__="stub.plugin")
        self._record = PluginRecord(
            manifest=self._plugin.manifest,
            instance=self._plugin,
            module=module,
        )

    def discover(self) -> Dict[str, PluginRecord]:
        return {self._record.manifest.identifier: self._record}

    def get(self, identifier: str) -> Optional[PluginRecord]:
        if identifier == self._record.manifest.identifier:
            return self._record
        return None

    def iter_plugins(self) -> Iterable[PluginRecord]:
        return [self._record]

    def start(self, identifier: str) -> PluginState:
        record = self.get(identifier)
        if not record:
            raise KeyError(identifier)
        if record.instance and record.state != PluginState.STARTED:
            record.instance.start()
            record.state = PluginState.STARTED
            record.error = None
        return record.state

    def stop(self, identifier: str) -> PluginState:
        record = self.get(identifier)
        if not record:
            raise KeyError(identifier)
        if record.instance and record.state == PluginState.STARTED:
            record.instance.stop()
            record.state = PluginState.STOPPED
        return record.state

    def shutdown(self) -> None:
        if self._record.instance and self._record.state == PluginState.STARTED:
            self._record.instance.stop()
            self._record.state = PluginState.STOPPED


def test_dashboard_persists_selection_and_started_plugins(tmp_path: Path) -> None:
    ensure_qapp()
    data_dir = tmp_path / "mmst-data"
    services = CoreServices(app_name="MMST-Tests", data_dir=data_dir)
    manager = StubPluginManager(services)

    window = DashboardWindow(services=services, manager=manager)
    identifier = manager._record.manifest.identifier
    assert manager._record.state == PluginState.STARTED

    window.resize(640, 480)
    window.move(32, 48)
    window.close()

    snapshot = services.config_store.get_snapshot().get("__dashboard__", {})
    assert snapshot.get("selected_plugin") == identifier
    assert snapshot.get("started_plugins") == [identifier]
    assert snapshot.get("window_size") == [640, 480]

    services_new = CoreServices(app_name="MMST-Tests", data_dir=data_dir)
    manager_new = StubPluginManager(services_new)
    window_new = DashboardWindow(services=services_new, manager=manager_new)
    assert manager_new._record.state == PluginState.STARTED
    assert window_new._current_identifier() == identifier
    window_new.close()
