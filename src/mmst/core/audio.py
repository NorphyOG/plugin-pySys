from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol

try:  # pragma: no cover - optional dependency
    import sounddevice as sd  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - missing runtime dependency
    sd = None  # type: ignore[assignment]


@dataclass(frozen=True)
class AudioDevice:
    identifier: str
    name: str
    host_api: str
    is_default: bool
    input_channels: int
    output_channels: int
    default_samplerate: Optional[float]


class AudioBackend(Protocol):
    def list_playback_devices(self) -> List[AudioDevice]: ...

    def list_capture_devices(self) -> List[AudioDevice]: ...

    def backend_name(self) -> str: ...


class FallbackAudioBackend:
    def __init__(self, reason: str = "sounddevice-unavailable") -> None:
        self._reason = reason

    def list_playback_devices(self) -> List[AudioDevice]:
        return [
            AudioDevice(
                identifier="default-output",
                name="System Default Output",
                host_api=self._reason,
                is_default=True,
                input_channels=0,
                output_channels=2,
                default_samplerate=None,
            )
        ]

    def list_capture_devices(self) -> List[AudioDevice]:
        return [
            AudioDevice(
                identifier="default-input",
                name="System Default Input",
                host_api=self._reason,
                is_default=True,
                input_channels=2,
                output_channels=0,
                default_samplerate=None,
            )
        ]

    def backend_name(self) -> str:
        return f"fallback:{self._reason}"


class SoundDeviceBackend:
    def __init__(self, logger: logging.Logger) -> None:
        if sd is None:  # pragma: no cover - defensive guard
            raise RuntimeError("sounddevice backend requested but library not available")
        self._logger = logger
        self._hostapis = self._query_hostapis()

    @staticmethod
    def is_available() -> bool:
        return sd is not None

    def _query_hostapis(self) -> List[str]:
        hostapis: List[str] = []
        if sd is None:
            return hostapis
        try:
            api_info = sd.query_hostapis()
        except Exception as exc:  # pragma: no cover - propagate but log
            self._logger.warning("sounddevice.query_hostapis failed: %s", exc)
            return hostapis
        if isinstance(api_info, list):
            for entry in api_info:
                hostapis.append(str(entry.get("name", f"Host API {len(hostapis)}")))
        else:  # pragma: no cover - alternative return structure
            hostapis.append("Default Host API")
        return hostapis

    def _list_devices(self, *, kind: str) -> List[AudioDevice]:
        devices: List[AudioDevice] = []
        if sd is None:
            return devices
        try:
            device_infos = sd.query_devices()
            default_input, default_output = self._resolve_defaults()
        except Exception as exc:  # pragma: no cover - propagate but log
            self._logger.warning("sounddevice.query_devices failed: %s", exc)
            return devices

        for index, info in enumerate(device_infos):
            max_input = int(info.get("max_input_channels", 0))
            max_output = int(info.get("max_output_channels", 0))
            if kind == "playback" and max_output <= 0:
                continue
            if kind == "capture" and max_input <= 0:
                continue

            hostapi_index = info.get("hostapi")
            if isinstance(hostapi_index, int) and 0 <= hostapi_index < len(self._hostapis):
                host_api_name = self._hostapis[hostapi_index]
            else:
                host_api_name = str(hostapi_index)

            is_default = (
                index == default_output if kind == "playback" else index == default_input
            )
            devices.append(
                AudioDevice(
                    identifier=str(index),
                    name=str(info.get("name", f"Device {index}")),
                    host_api=host_api_name,
                    is_default=is_default,
                    input_channels=max_input,
                    output_channels=max_output,
                    default_samplerate=self._get_default_samplerate(info),
                )
            )
        return devices

    def _resolve_defaults(self) -> tuple[Optional[int], Optional[int]]:
        if sd is None:
            return None, None
        device_defaults = getattr(sd.default, "device", None)
        if isinstance(device_defaults, (list, tuple)) and len(device_defaults) == 2:
            default_input = self._safe_index(device_defaults[0])
            default_output = self._safe_index(device_defaults[1])
            return default_input, default_output
        return None, None

    @staticmethod
    def _safe_index(value: object) -> Optional[int]:
        if isinstance(value, int) and value >= 0:
            return value
        return None

    @staticmethod
    def _get_default_samplerate(info: dict) -> Optional[float]:
        rate = info.get("default_samplerate")
        if isinstance(rate, (int, float)):
            return float(rate)
        return None

    def list_playback_devices(self) -> List[AudioDevice]:
        return self._list_devices(kind="playback")

    def list_capture_devices(self) -> List[AudioDevice]:
        return self._list_devices(kind="capture")

    def backend_name(self) -> str:
        return "sounddevice"


class AudioDeviceService:
    """Provide cross-platform audio device enumeration for plugins."""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        backend: Optional[AudioBackend] = None,
    ) -> None:
        self._logger = logger or logging.getLogger("MMST.AudioDeviceService")
        self._backend = backend or self._auto_detect_backend()

    def _auto_detect_backend(self) -> AudioBackend:
        if SoundDeviceBackend.is_available():
            try:
                return SoundDeviceBackend(self._logger)
            except Exception as exc:  # pragma: no cover - fallback on failure
                self._logger.warning("SoundDevice backend unavailable: %s", exc)
        return FallbackAudioBackend()

    @property
    def backend_name(self) -> str:
        return self._backend.backend_name()

    def list_playback_devices(self) -> List[AudioDevice]:
        devices = self._backend.list_playback_devices()
        if not devices:
            self._logger.debug("Playback device list empty; using fallback")
            devices = FallbackAudioBackend().list_playback_devices()
        return devices

    def list_capture_devices(self) -> List[AudioDevice]:
        devices = self._backend.list_capture_devices()
        if not devices:
            self._logger.debug("Capture device list empty; using fallback")
            devices = FallbackAudioBackend().list_capture_devices()
        return devices

    def set_backend(self, backend: AudioBackend) -> None:
        self._backend = backend

    def refresh_backend(self) -> None:
        self._backend = self._auto_detect_backend()

    def describe(self) -> str:
        playback = len(self.list_playback_devices())
        capture = len(self.list_capture_devices())
        return f"backend={self.backend_name}, playback={playback}, capture={capture}"