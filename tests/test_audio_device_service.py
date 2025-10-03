from typing import List

from mmst.core.audio import AudioDevice, AudioDeviceService, FallbackAudioBackend


class StubBackend:
    def __init__(self, playback: List[AudioDevice], capture: List[AudioDevice]) -> None:
        self._playback = playback
        self._capture = capture

    def list_playback_devices(self) -> List[AudioDevice]:
        return list(self._playback)

    def list_capture_devices(self) -> List[AudioDevice]:
        return list(self._capture)

    def backend_name(self) -> str:
        return "stub"


def _device(identifier: str, *, in_ch: int, out_ch: int, default: bool) -> AudioDevice:
    return AudioDevice(
        identifier=identifier,
        name=f"Device {identifier}",
        host_api="stub",
        is_default=default,
        input_channels=in_ch,
        output_channels=out_ch,
        default_samplerate=44100.0,
    )


def test_service_uses_custom_backend() -> None:
    backend = StubBackend(
        playback=[_device("p1", in_ch=0, out_ch=2, default=True)],
        capture=[_device("c1", in_ch=2, out_ch=0, default=True)],
    )
    service = AudioDeviceService(backend=backend)

    playback = service.list_playback_devices()
    capture = service.list_capture_devices()

    assert len(playback) == 1
    assert playback[0].identifier == "p1"
    assert len(capture) == 1
    assert capture[0].identifier == "c1"
    assert service.backend_name == "stub"


def test_service_falls_back_when_backend_returns_empty() -> None:
    backend = StubBackend(playback=[], capture=[])
    service = AudioDeviceService(backend=backend)

    playback = service.list_playback_devices()
    capture = service.list_capture_devices()

    assert playback  # fallback device provided
    assert capture
    assert playback[0].name == "System Default Output"
    assert capture[0].name == "System Default Input"


def test_fallback_backend_describe() -> None:
    service = AudioDeviceService(backend=FallbackAudioBackend("test"))
    description = service.describe()

    assert "backend=fallback:test" in description
    assert "playback=1" in description
    assert "capture=1" in description
