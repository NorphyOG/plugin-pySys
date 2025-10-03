"""Cover art utilities for the MediaLibrary plugin."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency handling
    import mutagen

    MUTAGEN_AVAILABLE = True
except ImportError:  # pragma: no cover - handled gracefully in tests
    mutagen = None  # type: ignore
    MUTAGEN_AVAILABLE = False


PLACEHOLDER_COLORS = {
    "audio": QColor(37, 99, 235),
    "video": QColor(239, 68, 68),
    "image": QColor(16, 185, 129),
    "other": QColor(107, 114, 128),
}


def placeholder_pixmap(kind: str, size: QSize) -> QPixmap:
    """Create a placeholder pixmap for media kinds with optional glyphs."""
    if size.isEmpty():
        size = QSize(240, 240)
    color = PLACEHOLDER_COLORS.get(kind, PLACEHOLDER_COLORS["other"])
    pixmap = QPixmap(size)
    pixmap.fill(color)

    if kind == "audio":
        _draw_music_note(pixmap)

    return pixmap


def _draw_music_note(pixmap: QPixmap) -> None:
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    accent = QColor(255, 255, 255, 235)
    painter.setBrush(accent)

    width = pixmap.width()
    height = pixmap.height()
    if width <= 0 or height <= 0:
        painter.end()
        return

    radius = max(6.0, min(width, height) * 0.18)
    base_y = height * 0.7
    left_center = QPointF(width * 0.38, base_y)
    right_center = QPointF(width * 0.6, base_y * 0.98)

    painter.drawEllipse(left_center, radius, radius * 0.9)
    painter.drawEllipse(right_center, radius, radius * 0.9)

    stem_width = max(4.0, width * 0.1)
    stem_height = height * 0.5
    stem_rect = QRectF(right_center.x() - stem_width * 0.5, height * 0.22, stem_width, stem_height)
    painter.drawRoundedRect(stem_rect, stem_width * 0.3, stem_width * 0.3)

    beam_height = max(4.0, height * 0.08)
    beam_rect = QRectF(left_center.x() - radius * 1.4, height * 0.18, radius * 3.0, beam_height)
    painter.drawRoundedRect(beam_rect, beam_height * 0.4, beam_height * 0.4)

    painter.end()


def _load_audio_cover_bytes(path: Path) -> Optional[bytes]:
    """Attempt to extract embedded cover art from an audio file."""
    if not MUTAGEN_AVAILABLE:
        return None

    try:
        audio = mutagen.File(str(path))  # type: ignore[call-arg]
    except Exception as exc:  # pragma: no cover - logging side effect
        logger.debug("Mutagen failed to open %s: %s", path, exc)
        return None

    if audio is None:
        return None

    # FLAC & similar formats with .pictures attribute
    pictures = getattr(audio, "pictures", None)
    if pictures:
        try:
            picture = pictures[0]
            data = getattr(picture, "data", None)
            if isinstance(data, (bytes, bytearray)):
                return bytes(data)
        except Exception:  # pragma: no cover - defensive
            pass

    tags = getattr(audio, "tags", None)
    if tags:
        # ID3 (MP3) APIC frames
        getall = getattr(tags, "getall", None)
        if callable(getall):
            apic_frames = getall("APIC")
            if isinstance(apic_frames, (list, tuple)):
                for frame in apic_frames:
                    data = getattr(frame, "data", None)
                    if isinstance(data, (bytes, bytearray)):
                        return bytes(data)

        # MP4/M4A cover art stored in "covr"
        if "covr" in tags:
            covr = tags["covr"]
            if isinstance(covr, (list, tuple)) and covr:
                first = covr[0]
                if hasattr(first, "data"):
                    first = first.data  # type: ignore[assignment]
                if isinstance(first, (bytes, bytearray)):
                    return bytes(first)

        # OGG/Vorbis pictures may be stored under this key
        if "metadata_block_picture" in tags:
            data_list = tags["metadata_block_picture"]
            if isinstance(data_list, (list, tuple)) and data_list:
                raw = data_list[0]
                if isinstance(raw, bytes):
                    return raw

    return None


def _find_sidecar_image(path: Path) -> Optional[Path]:
    stem = path.stem
    candidates = []
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
        candidates.append(path.with_suffix(ext))
        candidates.append(path.with_name(f"{stem}.cover{ext}"))
        candidates.append(path.with_name(f"{stem}.poster{ext}"))
        candidates.append(path.with_name(f"{stem}.thumb{ext}"))
        candidates.append(path.with_name(f"{stem}.thumbnail{ext}"))

    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except OSError:
            continue
    return None


def load_cover_pixmap(path: Path, kind: str, size: QSize) -> QPixmap:
    """Load a pixmap for the given media file and type."""
    if size.isEmpty():
        size = QSize(240, 240)

    if kind == "image" and path.exists():
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            return pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    if kind == "audio":
        cover_bytes = _load_audio_cover_bytes(path)
        if cover_bytes:
            pixmap = QPixmap()
            if pixmap.loadFromData(cover_bytes):
                return pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        sidecar = _find_sidecar_image(path)
        if sidecar is not None:
            pixmap = QPixmap(str(sidecar))
            if not pixmap.isNull():
                return pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    if kind == "video":
        poster = _find_sidecar_image(path)
        if poster is not None:
            pixmap = QPixmap(str(poster))
            if not pixmap.isNull():
                return pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    # For videos: no embedded support yet, fall back to placeholder
    return placeholder_pixmap(kind, size)


@dataclass
class CoverCache:
    """Simple in-memory cache for cover pixmaps."""

    size: QSize = QSize(240, 240)
    _cache: Dict[str, QPixmap] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._cache is None:
            self._cache = {}

    def get(self, path: Path, kind: str) -> QPixmap:
        key = str(path)
        pixmap = self._cache.get(key)
        if pixmap is not None:
            return pixmap

        pixmap = load_cover_pixmap(path, kind, self.size)
        self._cache[key] = pixmap
        return pixmap

    def invalidate(self, path: Path) -> None:
        self._cache.pop(str(path), None)

    def clear(self) -> None:
        self._cache.clear()