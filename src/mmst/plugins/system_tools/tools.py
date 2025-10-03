from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Tool:
    name: str
    command: str
    available: bool
    version: Optional[str] = None
    path: Optional[str] = None


@dataclass(frozen=True)
class ConversionFormat:
    extension: str
    display_name: str
    tool: str
    mime_type: Optional[str] = None


class ToolDetector:
    """Detect available external tools for file conversion."""

    TOOLS = {
        "ffmpeg": ["ffmpeg", "-version"],
        "imagemagick": ["magick", "-version"] if platform.system() == "Windows" else ["convert", "-version"],
    }

    def __init__(self) -> None:
        self._cache: Dict[str, Tool] = {}

    def detect(self, tool_name: str) -> Tool:
        if tool_name in self._cache:
            return self._cache[tool_name]

        if tool_name not in self.TOOLS:
            result = Tool(name=tool_name, command="", available=False)
            self._cache[tool_name] = result
            return result

        command_parts = self.TOOLS[tool_name]
        command = command_parts[0]
        
        path = shutil.which(command)

        # Additional lookup for ImageMagick on Windows installations that
        # do not add "magick" to the PATH.
        if not path and tool_name == "imagemagick" and platform.system() == "Windows":
            path = self._find_imagemagick_windows()
            if path:
                command_parts = [path] + command_parts[1:]
                command = path

        if not path:
            result = Tool(name=tool_name, command=command, available=False)
            self._cache[tool_name] = result
            return result

        version = self._get_version(command_parts)
        result = Tool(name=tool_name, command=command, available=True, version=version, path=path)
        self._cache[tool_name] = result
        return result

    def _find_imagemagick_windows(self) -> Optional[str]:
        candidates: List[Path] = []
        program_files = os.environ.get("PROGRAMFILES")
        program_files_x86 = os.environ.get("PROGRAMFILES(X86)")
        local_programs = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"

        for base in (program_files, program_files_x86):
            if base:
                candidates.append(Path(base))
        candidates.append(local_programs)

        for base in candidates:
            if not base.exists():
                continue
            for folder in base.glob("ImageMagick*"):
                magick_exe = folder / "magick.exe"
                if magick_exe.exists():
                    return str(magick_exe)
        return None

    def _get_version(self, command_parts: List[str]) -> Optional[str]:
        try:
            result = subprocess.run(
                command_parts,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            output = result.stdout + result.stderr
            lines = output.split("\n")
            if lines:
                return lines[0].strip()[:100]
        except Exception:
            pass
        return None

    def detect_all(self) -> Dict[str, Tool]:
        return {name: self.detect(name) for name in self.TOOLS.keys()}


# Supported conversion formats
CONVERSION_FORMATS = {
    # Audio conversions
    "mp3": ConversionFormat("mp3", "MP3 Audio", "ffmpeg", "audio/mpeg"),
    "wav": ConversionFormat("wav", "WAV Audio", "ffmpeg", "audio/wav"),
    "flac": ConversionFormat("flac", "FLAC Audio", "ffmpeg", "audio/flac"),
    "aac": ConversionFormat("aac", "AAC Audio", "ffmpeg", "audio/aac"),
    "ogg": ConversionFormat("ogg", "OGG Vorbis", "ffmpeg", "audio/ogg"),
    
    # Video conversions
    "mp4": ConversionFormat("mp4", "MP4 Video", "ffmpeg", "video/mp4"),
    "mkv": ConversionFormat("mkv", "Matroska Video", "ffmpeg", "video/x-matroska"),
    "avi": ConversionFormat("avi", "AVI Video", "ffmpeg", "video/x-msvideo"),
    "webm": ConversionFormat("webm", "WebM Video", "ffmpeg", "video/webm"),
    
    # Image conversions
    "png": ConversionFormat("png", "PNG Image", "imagemagick", "image/png"),
    "jpg": ConversionFormat("jpg", "JPEG Image", "imagemagick", "image/jpeg"),
    "jpeg": ConversionFormat("jpeg", "JPEG Image", "imagemagick", "image/jpeg"),
    "webp": ConversionFormat("webp", "WebP Image", "imagemagick", "image/webp"),
    "gif": ConversionFormat("gif", "GIF Image", "imagemagick", "image/gif"),
    "bmp": ConversionFormat("bmp", "BMP Image", "imagemagick", "image/bmp"),
}


def get_supported_formats(tool_name: str) -> List[ConversionFormat]:
    """Get all formats supported by a specific tool."""
    return [fmt for fmt in CONVERSION_FORMATS.values() if fmt.tool == tool_name]


def infer_format(path: Path) -> Optional[str]:
    """Infer the format category from file extension."""
    ext = path.suffix.lower().lstrip(".")
    if ext in {"mp3", "wav", "flac", "aac", "ogg", "m4a"}:
        return "audio"
    if ext in {"mp4", "mkv", "mov", "avi", "webm"}:
        return "video"
    if ext in {"png", "jpg", "jpeg", "gif", "webp", "bmp"}:
        return "image"
    return None
