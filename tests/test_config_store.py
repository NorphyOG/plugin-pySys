from __future__ import annotations

import json
from pathlib import Path

from mmst.core.config import ConfigStore


def test_config_store_persists_plugin_values(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    store = ConfigStore(config_path)

    config = store.get_plugin("ExamplePlugin")
    config["enabled"] = True
    config.update({"threshold": 5})

    reload_store = ConfigStore(config_path)
    reload_config = reload_store.get_plugin("ExamplePlugin")

    assert reload_config["enabled"] is True
    assert reload_config["threshold"] == 5
    assert reload_config.as_dict() == {"enabled": True, "threshold": 5}


def test_plugin_config_deletion_and_clear(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    store = ConfigStore(config_path)
    config = store.get_plugin("PluginX")

    config.update({"url": "https://example.com", "timeout": 10})
    del config["timeout"]

    assert "timeout" not in config
    assert config.as_dict() == {"url": "https://example.com"}

    config.clear()
    assert len(config) == 0

    reload_store = ConfigStore(config_path)
    assert reload_store.get_plugin("PluginX").as_dict() == {}


def test_config_store_handles_invalid_json(tmp_path: Path) -> None:
    config_path = tmp_path / "broken.json"
    config_path.write_text("{ invalid json")

    store = ConfigStore(config_path)
    assert store.get_snapshot() == {}

    config = store.get_plugin("demo")
    config["mode"] = "test"
    assert json.loads(config_path.read_text())["demo"] == {"mode": "test"}
