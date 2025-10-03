import pytest  # type: ignore[import-not-found]

PySide6 = pytest.importorskip("PySide6")

from mmst.core.services import CoreServices
from mmst.plugins.audio_tools.plugin import AudioToolsPlugin


@pytest.fixture
def services(tmp_path):
    return CoreServices(data_dir=tmp_path)


@pytest.fixture
def plugin(services):
    return AudioToolsPlugin(services)


def test_audio_tools_default_config(plugin, services):
    config = plugin.config.get("equalizer")
    assert isinstance(config, dict)
    assert set(config.keys()) == {"output", "input"}
    for bus in ("output", "input"):
        bus_config = config[bus]
        assert bus_config["devices"] == {}
        assert bus_config["selected_device"] is None

    quality = plugin.get_quality_settings()
    assert quality == {"sample_rate": 48000, "bit_depth": 24, "channels": 2}
    assert plugin.get_recording_history() == []

    # Output directory falls back to data dir before initialization
    assert plugin.get_output_directory() == str(services.data_dir)


def test_audio_tools_initialize_sets_output_dir(plugin, services):
    plugin.initialize()
    expected = services.data_dir / "audio" / "recordings"
    assert expected.exists()
    assert plugin.get_output_directory() == str(expected)


def test_audio_tools_preset_workflow(plugin):
    device_id = "test-device"
    initial = plugin.get_device_state("output", device_id)
    assert initial["active_preset"] == "Flat"

    plugin.update_device_values("output", device_id, [1] * 10)
    updated = plugin.get_device_state("output", device_id)
    assert updated["values"] == [1] * 10

    plugin.save_preset("output", device_id, "Custom", [2] * 10)
    state = plugin.get_device_state("output", device_id)
    assert state["active_preset"] == "Custom"
    assert state["presets"]["Custom"] == [2] * 10

    loaded = plugin.load_preset("output", device_id, "Custom")
    assert loaded == [2] * 10

    plugin.delete_preset("output", device_id, "Custom")
    remaining = plugin.get_device_state("output", device_id)
    assert set(remaining["presets"].keys()) == {"Flat"}

    with pytest.raises(ValueError):
        plugin.delete_preset("output", device_id, "Flat")
