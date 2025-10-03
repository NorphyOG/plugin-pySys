from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass
class ConversionJob:
    source: Path
    target: Path
    source_format: str
    target_format: str
    tool: str


@dataclass
class ConversionResult:
    success: bool
    source: Path
    target: Path
    message: str
    output_size: int = 0


class FileConverter:
    """Execute file conversions using external tools."""

    def __init__(self) -> None:
        pass

    def convert(
        self,
        job: ConversionJob,
        progress: Optional[Callable[[str], None]] = None,
    ) -> ConversionResult:
        """Convert a file from one format to another."""
        if not job.source.exists():
            return ConversionResult(
                success=False,
                source=job.source,
                target=job.target,
                message="Quelldatei existiert nicht",
            )

        if job.tool == "ffmpeg":
            return self._convert_ffmpeg(job, progress)
        elif job.tool == "imagemagick":
            return self._convert_imagemagick(job, progress)
        else:
            return ConversionResult(
                success=False,
                source=job.source,
                target=job.target,
                message=f"Unbekanntes Tool: {job.tool}",
            )

    def _convert_ffmpeg(
        self,
        job: ConversionJob,
        progress: Optional[Callable[[str], None]] = None,
    ) -> ConversionResult:
        """Convert audio/video using ffmpeg."""
        job.target.parent.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            "ffmpeg",
            "-i", str(job.source),
            "-y",  # overwrite output
            str(job.target),
        ]

        if progress:
            progress(f"Starte ffmpeg: {job.source.name} → {job.target.name}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                check=True,
            )
            
            if job.target.exists():
                size = job.target.stat().st_size
                return ConversionResult(
                    success=True,
                    source=job.source,
                    target=job.target,
                    message="Konvertierung erfolgreich",
                    output_size=int(size),
                )
            else:
                return ConversionResult(
                    success=False,
                    source=job.source,
                    target=job.target,
                    message="Ausgabedatei wurde nicht erstellt",
                )

        except subprocess.TimeoutExpired:
            return ConversionResult(
                success=False,
                source=job.source,
                target=job.target,
                message="Timeout: Konvertierung dauerte zu lange",
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr if exc.stderr else ""
            return ConversionResult(
                success=False,
                source=job.source,
                target=job.target,
                message=f"ffmpeg-Fehler: {stderr[:200]}",
            )
        except Exception as exc:
            return ConversionResult(
                success=False,
                source=job.source,
                target=job.target,
                message=f"Fehler: {exc}",
            )

    def _convert_imagemagick(
        self,
        job: ConversionJob,
        progress: Optional[Callable[[str], None]] = None,
    ) -> ConversionResult:
        """Convert images using ImageMagick."""
        job.target.parent.mkdir(parents=True, exist_ok=True)
        
        import platform
        if platform.system() == "Windows":
            cmd = ["magick", "convert", str(job.source), str(job.target)]
        else:
            cmd = ["convert", str(job.source), str(job.target)]

        if progress:
            progress(f"Starte ImageMagick: {job.source.name} → {job.target.name}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            
            if job.target.exists():
                size = job.target.stat().st_size
                return ConversionResult(
                    success=True,
                    source=job.source,
                    target=job.target,
                    message="Konvertierung erfolgreich",
                    output_size=int(size),
                )
            else:
                return ConversionResult(
                    success=False,
                    source=job.source,
                    target=job.target,
                    message="Ausgabedatei wurde nicht erstellt",
                )

        except subprocess.TimeoutExpired:
            return ConversionResult(
                success=False,
                source=job.source,
                target=job.target,
                message="Timeout: Konvertierung dauerte zu lange",
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr if exc.stderr else ""
            return ConversionResult(
                success=False,
                source=job.source,
                target=job.target,
                message=f"ImageMagick-Fehler: {stderr[:200]}",
            )
        except Exception as exc:
            return ConversionResult(
                success=False,
                source=job.source,
                target=job.target,
                message=f"Fehler: {exc}",
            )
