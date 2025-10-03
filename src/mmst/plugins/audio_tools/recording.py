from __future__ import annotations

import datetime as _dt
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


class RecordingError(RuntimeError):
    """Raised when recording start/stop operations fail."""


@dataclass
class _RecordingSession:
    device_id: str
    start_time: float
    output_path: Path
    quality: Dict[str, int]


class RecordingController:
    """Minimal recording controller writing silent WAV placeholders.

    This scaffold focuses on wiring, lifecycle, and deterministic testability. It prepares
    the ground for real audio capture backends that will replace the silent placeholder
    writer in future milestones.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._session: Optional[_RecordingSession] = None

    def is_recording(self) -> bool:
        with self._lock:
            return self._session is not None

    def start(self, target_dir: Path, device_id: str, quality: Dict[str, int]) -> Path:
        """Start a new recording placeholder.

        Ensures only one session can run at a time and creates a future output path.
        """
        with self._lock:
            if self._session is not None:
                raise RecordingError("Eine Aufnahme läuft bereits")
            target_dir.mkdir(parents=True, exist_ok=True)
            timestamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"recording-{timestamp}.wav"
            output_path = target_dir / filename
            self._session = _RecordingSession(
                device_id=device_id,
                start_time=time.time(),
                output_path=output_path,
                quality=dict(quality),
            )
            return output_path

    def stop(self) -> Dict[str, object]:
        """Stop the current recording and materialize the silent WAV placeholder."""
        with self._lock:
            if self._session is None:
                raise RecordingError("Es läuft keine Aufnahme")
            session = self._session
            self._session = None

        duration_seconds = max(time.time() - session.start_time, 0.1)
        info = self._write_silent_wav(session.output_path, session.quality, duration_seconds)
        info["device_id"] = session.device_id
        info["duration_seconds"] = duration_seconds
        info["path"] = session.output_path
        return info

    def abort(self) -> None:
        """Abort without writing any file."""
        with self._lock:
            self._session = None

    @staticmethod
    def _write_silent_wav(path: Path, quality: Dict[str, int], duration_seconds: float) -> Dict[str, object]:
        sample_rate = int(quality.get("sample_rate", 48000))
        channels = max(1, int(quality.get("channels", 2)))
        bit_depth = int(quality.get("bit_depth", 24))
        sample_width = max(1, min(4, bit_depth // 8 or 1))

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
