import wave
from pathlib import Path

import pytest  # type: ignore[import-not-found]

PySide6 = pytest.importorskip("PySide6")

from mmst.core.services import CoreServices
from mmst.plugins.audio_tools.plugin import AudioToolsPlugin
from mmst.plugins.audio_tools.recording import RecordingError
from mmst.core.audio import FallbackAudioBackend


@pytest.fixture
def services(tmp_path):
    return CoreServices(data_dir=tmp_path)


@pytest.fixture(autouse=True)
def force_placeholder_mode(monkeypatch):
    monkeypatch.setenv("MMST_AUDIO_PLACEHOLDER", "1")


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


def test_audio_tools_recording_placeholder(plugin, tmp_path):
    plugin.set_output_directory(tmp_path)
    plugin.set_recorder_device("mic-1")

    path = plugin.start_recording()
    assert plugin.is_recording()
    assert path.exists() is False  # file materializes on stop

    entry = plugin.stop_recording()
    assert not plugin.is_recording()

    recorded_file = tmp_path / entry["filename"]
    assert recorded_file.exists()
    assert recorded_file.stat().st_size > 44  # WAV header + data
    with wave.open(str(recorded_file), "rb") as wav_file:
        assert wav_file.getsampwidth() in (2, 4)
        assert wav_file.getframerate() == 48000
        assert wav_file.getnchannels() == 2

    history = plugin.get_recording_history()
    assert history
    assert history[0]["filename"] == entry["filename"]
    assert history[0]["duration"].endswith("s")
    assert set(history[0]["metadata"].keys()) == {"title", "artist", "album", "genre", "comment"}
    assert all(value == "" for value in history[0]["metadata"].values())
    assert history[0]["path"].endswith(entry["filename"])


def test_audio_tools_recording_metadata(plugin, tmp_path):
    plugin.set_output_directory(tmp_path)
    plugin.set_recorder_device("mic-1")

    plugin.start_recording()
    entry = plugin.stop_recording()

    metadata = {
        "title": "Demo Track",
        "artist": "Unit Test",
        "album": "Suite",
        "genre": "Test",
        "comment": "Recorded during tests",
    }
    plugin.update_recording_metadata(entry["path"], metadata)

    stored = plugin.get_recording_metadata(entry["path"])
    assert stored["title"] == "Demo Track"
    assert stored["comment"] == "Recorded during tests"

    history = plugin.get_recording_history()
    assert history[0]["metadata"]["artist"] == "Unit Test"


def test_audio_tools_history_prunes_missing_files(plugin, tmp_path):
    plugin.set_output_directory(tmp_path)
    plugin.set_recorder_device("mic-1")

    plugin.start_recording()
    entry = plugin.stop_recording()

    recorded_path = Path(entry["path"])
    if recorded_path.exists():
        recorded_path.unlink()

    history = plugin.get_recording_history()
    assert all(item["path"] != entry["path"] for item in history)

    # Second call should remain stable after pruning
    history_again = plugin.get_recording_history()
    assert history_again == history


def test_audio_tools_recorder_mode_selection(plugin):
    assert plugin.get_recorder_mode() == "input"
    plugin.set_recorder_device("mic-1")
    assert plugin.get_recorder_device("input") == "mic-1"

    plugin.set_recorder_mode("loopback")
    plugin.set_recorder_device("out-1", mode="loopback")
    assert plugin.get_recorder_device("loopback") == "out-1"

    # Switching back should remember previous selections
    plugin.set_recorder_mode("input")
    assert plugin.get_recorder_device() == "mic-1"


def test_audio_tools_quality_settings_affect_output(plugin, tmp_path):
    plugin.set_output_directory(tmp_path)
    plugin.set_recorder_device("mic-1")
    plugin.update_quality_settings({"sample_rate": 44100, "bit_depth": 16, "channels": 1})

    plugin.start_recording()
    entry = plugin.stop_recording()

    recorded_file = tmp_path / entry["filename"]
    with wave.open(str(recorded_file), "rb") as wav_file:
        assert wav_file.getframerate() == 44100
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2


def test_audio_tools_prevents_double_start(plugin, tmp_path):
    plugin.set_output_directory(tmp_path)
    plugin.set_recorder_device("mic-1")

    plugin.start_recording()
    with pytest.raises(RecordingError):
        plugin.start_recording()
    plugin.stop_recording()


def test_audio_tools_open_recording_location_opens_directory(monkeypatch, plugin, tmp_path):
    plugin.set_output_directory(tmp_path)
    plugin.set_recorder_device("mic-1")

    plugin.start_recording()
    entry = plugin.stop_recording()

    opened = {}

    def fake_open(url):
        opened["url"] = url
        return True

    monkeypatch.setattr("mmst.plugins.audio_tools.plugin.QDesktopServices.openUrl", fake_open)

    assert plugin.open_recording_location(entry["path"])
    assert Path(opened["url"].toLocalFile()) == tmp_path


def test_audio_tools_open_recording_location_missing_returns_false(monkeypatch, plugin, tmp_path):
    missing_root = tmp_path / "missing-root"
    plugin.set_output_directory(missing_root)

    monkeypatch.setattr(
        "mmst.plugins.audio_tools.plugin.QDesktopServices.openUrl",
        lambda url: True,
    )

    assert not plugin.open_recording_location("ghost.wav")


def test_audio_tools_backend_notice_for_fallback(plugin):
    plugin.services.audio_devices.set_backend(FallbackAudioBackend())

    notice = plugin.get_device_backend_notice()
    assert notice is not None
    assert "sounddevice" in notice

    devices = plugin.get_devices("input")
    assert devices
    label = plugin.describe_device(devices[0])
    assert "Platzhalter" in label
