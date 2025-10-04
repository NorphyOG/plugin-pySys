from __future__ import annotations
"""Compatibility layer for tests expecting models module.

Provides MediaFile (re-export from core) and MediaMetadata class used in tests.
If a richer metadata implementation exists elsewhere, you can update imports here
without touching test files.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Any

from .core import MediaFile as CoreMediaFile  # re-export original

@dataclass
class MediaMetadata:
    duration: Optional[float] = None
    rating: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    width: Optional[int] = None
    height: Optional[int] = None
    codec: Optional[str] = None
    bitrate: Optional[int] = None
    samplerate: Optional[int] = None
    channels: Optional[int] = None

class MediaFile(CoreMediaFile):  # type: ignore[misc]
    """Shim subclass allowing simpler construction in legacy tests.

    Original CoreMediaFile requires size & mtime. Some tests only pass path & kind.
    We provide default values and fill missing args with 0.
    """
    def __init__(self, path: str, kind: str, size: int = 0, mtime: float = 0.0, **kwargs: Any) -> None:  # type: ignore[override]
        super().__init__(path=path, size=size, mtime=mtime, kind=kind, rating=kwargs.get('rating'), tags=kwargs.get('tags', tuple()))

__all__ = ["MediaFile", "MediaMetadata"]
