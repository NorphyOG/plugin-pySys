import pytest  # type: ignore[import-not-found]

PySide6 = pytest.importorskip("PySide6")

from mmst.core.plugin_manager import PluginManager
from mmst.core.services import CoreServices


def test_plugin_discovery(tmp_path):
    services = CoreServices(data_dir=tmp_path)
    manager = PluginManager(services=services)
    plugins = manager.discover()

    assert "mmst.file_manager" in plugins
    fm_record = plugins["mmst.file_manager"]
    assert fm_record.manifest.name == "Dateiverwaltung"
    assert fm_record.instance is not None

    assert "mmst.audio_tools" in plugins
    audio_record = plugins["mmst.audio_tools"]
    assert audio_record.manifest.name == "Audio Tools"
    assert audio_record.instance is not None
