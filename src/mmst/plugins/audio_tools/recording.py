from __future__ import annotations

import contextlib
import datetime as _dt
import logging
import os
import queue as queue_module
import platform
import re
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

try:  # pragma: no cover - optional dependency
    import sounddevice as sd  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - missing runtime dependency
    sd = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    import numpy as np  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - missing runtime dependency
    np = None  # type: ignore[assignment]


class RecordingError(RuntimeError):
    """Raised when recording start/stop operations fail."""


@dataclass
class _RecordingSession:
    device_id: str
    start_time: float
    output_path: Path
    quality: Dict[str, int]
    mode: str = "placeholder"
    capture_mode: str = "input"
    queue: Optional["queue_module.Queue[bytes]"] = None
    stop_event: Optional[threading.Event] = None
    stream: Optional[Any] = None
    writer_thread: Optional[threading.Thread] = None
    sample_width: int = 2
    bit_depth: int = 16
    frames_captured: int = 0
    uses_raw_stream: bool = True


class RecordingController:
    """Recording controller with auto-selected backend.

    When a compatible :mod:`sounddevice` installation is available (and no placeholder
    override is active) the controller captures real audio input into a WAV file. If the
    backend cannot be used it falls back to generating a silent placeholder recording to
    keep the workflow functional in test environments.
    """

    def __init__(self, *, logger: Optional[logging.Logger] = None, force_placeholder: Optional[bool] = None) -> None:
        self._lock = threading.RLock()
        self._session: Optional[_RecordingSession] = None
        self._logger = logger or logging.getLogger("MMST.AudioTools.Recording")
        if force_placeholder is None:
            env_value = os.getenv("MMST_AUDIO_PLACEHOLDER")
            force_placeholder = env_value not in (None, "", "0", "false", "False")
        self._force_placeholder = bool(force_placeholder)

    def is_recording(self) -> bool:
        with self._lock:
            return self._session is not None

    def start(
        self,
        target_dir: Path,
        device_id: str,
        quality: Dict[str, int],
        *,
        mode: str = "input",
    ) -> Path:
        """Start a new recording session.

        Ensures only one session can run at a time, prepares the output directory and
        selects the best available backend.
        """
        with self._lock:
            if self._session is not None:
                raise RecordingError("Eine Aufnahme läuft bereits")
            target_dir.mkdir(parents=True, exist_ok=True)
            timestamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            device_slug = re.sub(r"[^a-z0-9]+", "-", device_id.lower()).strip("-") or "device"
            base_name = f"recording-{timestamp}-{device_slug}"
            output_path = target_dir / f"{base_name}.wav"
            counter = 1
            while output_path.exists():
                output_path = target_dir / f"{base_name}-{counter:02d}.wav"
                counter += 1
            capture_mode = mode if mode in {"input", "loopback"} else "input"
            session = _RecordingSession(
                device_id=device_id,
                start_time=time.time(),
                output_path=output_path,
                quality=dict(quality),
                capture_mode=capture_mode,
            )
            if not self._force_placeholder:
                try:
                    self._activate_sounddevice_backend(session)
                except Exception as exc:  # pragma: no cover - best effort fallback
                    self._logger.warning("Realer Audiobackend-Start fehlgeschlagen, verwende Platzhalter: %s", exc)
                    self._cleanup_sounddevice_session(session, delete_file=True)
                else:
                    self._session = session
                    return output_path

            self._session = session
            return output_path

    def stop(self) -> Dict[str, object]:
        """Stop the current recording and materialize the captured audio."""
        with self._lock:
            if self._session is None:
                raise RecordingError("Es läuft keine Aufnahme")
            session = self._session
            self._session = None

        if session.mode == "sounddevice":
            try:
                info = self._finalize_sounddevice_session(session)
                raw_duration = info.get("duration_seconds")
                if isinstance(raw_duration, (int, float)):
                    duration_seconds = float(raw_duration)
                else:
                    duration_seconds = max(time.time() - session.start_time, 0.1)
            except Exception as exc:  # pragma: no cover - defensive fallback
                self._logger.error("Aufnahme konnte nicht sauber beendet werden, schreibe Platzhalter: %s", exc)
                self._cleanup_sounddevice_session(session, delete_file=True)
                duration_seconds = max(time.time() - session.start_time, 0.1)
                info = self._write_silent_wav(session.output_path, session.quality, duration_seconds)
        else:
            duration_seconds = max(time.time() - session.start_time, 0.1)
            info = self._write_silent_wav(session.output_path, session.quality, duration_seconds)

        info["device_id"] = session.device_id
        info["duration_seconds"] = duration_seconds
        info["path"] = session.output_path
        info["capture_mode"] = session.capture_mode
        return info

    def abort(self) -> None:
        """Abort without writing any file."""
        with self._lock:
            session = self._session
            self._session = None
        if session and session.mode == "sounddevice":
            self._cleanup_sounddevice_session(session, delete_file=True)
        elif session:
            self._silent_abort(session)

    @staticmethod
    def _resolve_sample_format(quality: Dict[str, int]) -> tuple[int, int, str]:
        requested = int(quality.get("bit_depth", 24))
        if requested <= 16:
            return 16, 2, "int16"
        return 32, 4, "int32"

    @staticmethod
    def _write_silent_wav(path: Path, quality: Dict[str, int], duration_seconds: float) -> Dict[str, object]:
        sample_rate = int(quality.get("sample_rate", 48000))
        channels = max(1, int(quality.get("channels", 2)))
        bit_depth, sample_width, _ = RecordingController._resolve_sample_format(quality)

        total_frames = max(1, int(duration_seconds * sample_rate))
        frames_written = 0
        chunk_frames = 4096
        silence_chunk = bytes(sample_width * channels * chunk_frames)

        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            while frames_written < total_frames:
                remaining = total_frames - frames_written
                use_frames = min(chunk_frames, remaining)
                if use_frames != chunk_frames:
                    silence = bytes(sample_width * channels * use_frames)
                    wav_file.writeframes(silence)
                else:
                    wav_file.writeframes(silence_chunk)
                frames_written += use_frames

        size = path.stat().st_size if path.exists() else 0
        return {
            "size_bytes": int(size),
            "sample_rate": sample_rate,
            "channels": channels,
            "bit_depth": bit_depth,
        }

    # ------------------------------------------------------------------
    # Silent fallback helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _silent_abort(session: _RecordingSession) -> None:
        if session.output_path.exists():
            with contextlib.suppress(FileNotFoundError):
                session.output_path.unlink()

    # ------------------------------------------------------------------
    # Sounddevice backend helpers
    # ------------------------------------------------------------------
    def _activate_sounddevice_backend(self, session: _RecordingSession) -> None:
        if sd is None:
            raise RuntimeError("sounddevice ist nicht verfügbar")

        sample_rate = int(session.quality.get("sample_rate", 48000))
        channels = max(1, int(session.quality.get("channels", 2)))
        bit_depth, sample_width, dtype = self._resolve_sample_format(session.quality)
        use_float_stream = session.capture_mode == "loopback" and np is not None

        session.sample_width = sample_width
        session.bit_depth = bit_depth
        session.queue = queue_module.Queue()
        session.stop_event = threading.Event()
        session.frames_captured = 0
        session.uses_raw_stream = not use_float_stream

        def _callback(indata, frames, _time_info, status):  # pragma: no cover - interacts with hardware
            if status:
                self._logger.warning("Audio Callback Status: %s", status)
            if not session.queue:
                return
            if session.uses_raw_stream:
                session.queue.put(bytes(indata))
            else:
                chunk = self._convert_float_buffer(indata, sample_width)
                if chunk:
                    session.queue.put(chunk)

        device_index = self._resolve_device_identifier(session.device_id)
        device_argument: Any = device_index if device_index is not None else session.device_id

        extra_settings = None
        if session.capture_mode == "loopback":
            if platform.system() != "Windows":
                raise RuntimeError("Desktop-Audio-Aufnahme wird derzeit nur unter Windows unterstützt")
            if not hasattr(sd, "WasapiSettings"):
                raise RuntimeError("sounddevice unterstützt kein WASAPI Loopback in dieser Umgebung")
            extra_settings = sd.WasapiSettings()  # type: ignore[attr-defined]
            setattr(extra_settings, "loopback", True)
            try:
                info = sd.query_devices(device_argument)
                max_output = None
                if isinstance(info, dict):
                    max_output = info.get("max_output_channels")
                else:
                    max_output = getattr(info, "max_output_channels", None)
                if isinstance(max_output, (int, float)):
                    max_output = int(max_output)
                    if max_output > 0:
                        channels = max(1, min(channels, max_output))
                default_rate = None
                if isinstance(info, dict):
                    default_rate = info.get("default_samplerate")
                else:
                    default_rate = getattr(info, "default_samplerate", None)
                if isinstance(default_rate, (int, float)) and default_rate > 0:
                    sample_rate = int(default_rate)
            except Exception as exc:  # pragma: no cover - defensive logging
                self._logger.warning("Konnte Ausgabegerät für Loopback nicht lesen: %s", exc)

        session.quality["channels"] = channels
        session.quality["sample_rate"] = sample_rate

        session.output_path.parent.mkdir(parents=True, exist_ok=True)
        if session.uses_raw_stream:
            stream = sd.RawInputStream(
                device=device_argument,
                samplerate=sample_rate,
                channels=channels,
                dtype=dtype,
                callback=_callback,
                blocksize=0,
                extra_settings=extra_settings,
            )
        else:
            stream = sd.InputStream(
                device=device_argument,
                samplerate=sample_rate,
                channels=channels,
                dtype="float32",
                callback=_callback,
                blocksize=0,
                extra_settings=extra_settings,
            )
        session.stream = stream

        def _writer_loop() -> None:  # pragma: no cover - interacts with hardware
            if not session.queue or not session.stop_event:
                return
            with wave.open(str(session.output_path), "wb") as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                while True:
                    if session.stop_event.is_set() and session.queue.empty():
                        break
                    try:
                        chunk = session.queue.get(timeout=0.25)
                    except queue_module.Empty:
                        continue
                    if not chunk:
                        continue
                    wav_file.writeframes(chunk)
                    frame_chunk = len(chunk) // (sample_width * channels)
                    session.frames_captured += frame_chunk

        session.writer_thread = threading.Thread(
            target=_writer_loop,
            name="AudioRecordingWriter",
            daemon=True,
        )
        session.writer_thread.start()

        try:
            stream.start()
        except Exception:
            session.stop_event.set()
            session.writer_thread.join(timeout=1.0)
            self._cleanup_sounddevice_session(session, delete_file=True)
            raise

        session.mode = "sounddevice"

    def _convert_float_buffer(self, buffer: Any, sample_width: int) -> bytes:
        """Convert a float32 numpy buffer into PCM bytes."""
        if np is None:
            return bytes(buffer)
        array = np.asarray(buffer, dtype=np.float32)
        if array.size == 0:
            return b""
        clipped = np.clip(array, -1.0, 1.0).astype(np.float64)
        if sample_width <= 2:
            scaled = clipped * 32767.0
            pcm = np.clip(scaled, -32768, 32767).astype("<i2")
        else:
            scaled = clipped * 2147483647.0
            pcm = np.clip(scaled, -2147483648, 2147483647).astype("<i4")
        return pcm.tobytes()

    def _finalize_sounddevice_session(self, session: _RecordingSession) -> Dict[str, object]:
        sample_rate = int(session.quality.get("sample_rate", 48000))
        channels = max(1, int(session.quality.get("channels", 2)))
        bit_depth = session.bit_depth if isinstance(session.bit_depth, int) else session.sample_width * 8

        self._stop_sounddevice_stream(session)

        if not session.output_path.exists():
            raise RecordingError("Aufnahme-Datei wurde nicht erstellt")

        size = session.output_path.stat().st_size
        if sample_rate > 0 and session.frames_captured > 0:
            duration_seconds = session.frames_captured / float(sample_rate)
        else:
            duration_seconds = max(time.time() - session.start_time, 0.0)
        return {
            "size_bytes": int(size),
            "sample_rate": sample_rate,
            "channels": channels,
            "bit_depth": bit_depth,
            "duration_seconds": duration_seconds,
        }

    def _stop_sounddevice_stream(self, session: _RecordingSession, *, delete_file: bool = False) -> None:
        if session.stream is not None:
            with contextlib.suppress(Exception):  # pragma: no cover - defensive
                session.stream.stop()
            with contextlib.suppress(Exception):  # pragma: no cover - defensive
                session.stream.close()
        if session.stop_event is not None:
            session.stop_event.set()
        if session.writer_thread is not None:
            session.writer_thread.join(timeout=2.0)
        if delete_file and session.output_path.exists():
            with contextlib.suppress(FileNotFoundError):
                session.output_path.unlink()
        session.stream = None
        session.writer_thread = None
        session.queue = None
        session.stop_event = None

    def _cleanup_sounddevice_session(self, session: _RecordingSession, *, delete_file: bool = False) -> None:
        self._stop_sounddevice_stream(session, delete_file=delete_file)

    @staticmethod
    def _resolve_device_identifier(device_id: str) -> Optional[int]:
        try:
            return int(device_id)
        except (TypeError, ValueError):
            return None
