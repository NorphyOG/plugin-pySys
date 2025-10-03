import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mmst.plugins.system_tools.converter import ConversionJob, ConversionResult, FileConverter
from mmst.plugins.system_tools.tools import (
    CONVERSION_FORMATS,
    Tool,
    ToolDetector,
    get_supported_formats,
    infer_format,
)


class TestToolDetector:
    """Test tool detection logic."""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_detect_ffmpeg_available(self, mock_run, mock_which):
        """Test ffmpeg detection when available."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ffmpeg version 4.4.2"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        detector = ToolDetector()
        tool = detector.detect("ffmpeg")

        assert tool.available
        assert tool.name == "ffmpeg"
        assert tool.command == "ffmpeg"
        assert "4.4.2" in tool.version
        assert tool.path == "/usr/bin/ffmpeg"

    @patch("shutil.which")
    def test_detect_ffmpeg_not_available(self, mock_which):
        """Test ffmpeg detection when not available."""
        mock_which.return_value = None

        detector = ToolDetector()
        tool = detector.detect("ffmpeg")

        assert not tool.available
        assert tool.name == "ffmpeg"
        assert tool.version is None
        assert tool.path is None

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_detect_imagemagick_available(self, mock_run, mock_which):
        """Test ImageMagick detection when available."""
        mock_which.return_value = "/usr/bin/magick"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Version: ImageMagick 7.1.0-47"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        detector = ToolDetector()
        tool = detector.detect("imagemagick")

        assert tool.available
        assert tool.name == "imagemagick"
        assert tool.command == "magick"
        assert "7.1.0" in tool.version

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_detect_all_tools(self, mock_run, mock_which):
        """Test detecting all tools."""
        mock_which.return_value = "/usr/bin/tool"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "version 1.0.0"
        mock_run.return_value = mock_result

        detector = ToolDetector()
        tools = detector.detect_all()

        assert "ffmpeg" in tools
        assert "imagemagick" in tools
        assert len(tools) == 2

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_version_parsing_timeout(self, mock_run, mock_which):
        """Test version parsing when subprocess times out."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 5)

        detector = ToolDetector()
        tool = detector.detect("ffmpeg")

        assert tool.available  # Still available since which found it
        assert tool.version is None  # But version is unknown


class TestFormatHelpers:
    """Test format helper functions."""

    def test_get_supported_formats_ffmpeg(self):
        """Test getting supported formats for ffmpeg."""
        formats = get_supported_formats("ffmpeg")
        assert len(formats) > 0
        
        # Check that we have both audio and video formats
        extensions = [f.extension for f in formats]
        assert "mp3" in extensions  # Audio
        assert "mp4" in extensions  # Video
        
        # Check specific formats
        mp3_format = next((f for f in formats if f.extension == "mp3"), None)
        assert mp3_format is not None
        assert mp3_format.tool == "ffmpeg"

    def test_get_supported_formats_imagemagick(self):
        """Test getting supported formats for ImageMagick."""
        formats = get_supported_formats("imagemagick")
        assert len(formats) > 0
        
        for fmt in formats:
            assert fmt.tool == "imagemagick"

    def test_infer_format_audio(self):
        """Test format inference for audio files."""
        assert infer_format(Path("song.mp3")) == "audio"
        assert infer_format(Path("track.wav")) == "audio"
        assert infer_format(Path("audio.flac")) == "audio"

    def test_infer_format_video(self):
        """Test format inference for video files."""
        assert infer_format(Path("movie.mp4")) == "video"
        assert infer_format(Path("clip.mkv")) == "video"
        assert infer_format(Path("video.avi")) == "video"

    def test_infer_format_image(self):
        """Test format inference for image files."""
        assert infer_format(Path("photo.jpg")) == "image"
        assert infer_format(Path("picture.png")) == "image"
        assert infer_format(Path("graphic.webp")) == "image"

    def test_infer_format_unknown(self):
        """Test format inference for unknown files."""
        assert infer_format(Path("document.txt")) is None
        assert infer_format(Path("data.bin")) is None


class TestFileConverter:
    """Test file conversion logic."""

    @patch("subprocess.run")
    def test_convert_ffmpeg_success(self, mock_run, tmp_path):
        """Test successful ffmpeg conversion."""
        source = tmp_path / "input.mp3"
        target = tmp_path / "output.wav"
        source.touch()  # Create dummy file

        # Mock muss die Zieldatei erstellen
        def create_target(*args, **kwargs):
            target.write_text("fake output")
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result
        
        mock_run.side_effect = create_target

        converter = FileConverter()
        job = ConversionJob(
            source=source,
            target=target,
            source_format="mp3",
            target_format="wav",
            tool="ffmpeg",
        )

        progress_calls = []
        result = converter.convert(job, progress=lambda msg: progress_calls.append(msg))

        assert result.success
        assert "erfolgreich" in result.message.lower()
        assert len(progress_calls) > 0

    @patch("subprocess.run")
    def test_convert_ffmpeg_failure(self, mock_run, tmp_path):
        """Test failed ffmpeg conversion."""
        source = tmp_path / "input.mp3"
        target = tmp_path / "output.wav"
        source.touch()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: invalid codec"
        mock_run.return_value = mock_result

        converter = FileConverter()
        job = ConversionJob(
            source=source,
            target=target,
            source_format="mp3",
            target_format="wav",
            tool="ffmpeg",
        )

        result = converter.convert(job)

        assert not result.success
        # Converter meldet dass Ausgabedatei nicht erstellt wurde
        assert "ausgabedatei" in result.message.lower() or "error" in result.message.lower()

    @patch("subprocess.run")
    def test_convert_imagemagick_success(self, mock_run, tmp_path):
        """Test successful ImageMagick conversion."""
        source = tmp_path / "image.png"
        target = tmp_path / "image.jpg"
        source.touch()

        # Mock muss die Zieldatei erstellen
        def create_target(*args, **kwargs):
            target.write_text("fake image")
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result
        
        mock_run.side_effect = create_target

        converter = FileConverter()
        job = ConversionJob(
            source=source,
            target=target,
            source_format="png",
            target_format="jpg",
            tool="imagemagick",
        )

        result = converter.convert(job)

        assert result.success
        assert "erfolgreich" in result.message.lower()

    @patch("subprocess.run")
    def test_convert_timeout(self, mock_run, tmp_path):
        """Test conversion timeout handling."""
        source = tmp_path / "input.mp3"
        target = tmp_path / "output.wav"
        source.touch()

        mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 300)

        converter = FileConverter()
        job = ConversionJob(
            source=source,
            target=target,
            source_format="mp3",
            target_format="wav",
            tool="ffmpeg",
        )

        result = converter.convert(job)

        assert not result.success
        assert "timeout" in result.message.lower()

    def test_convert_source_not_exists(self, tmp_path):
        """Test conversion when source file doesn't exist."""
        source = tmp_path / "nonexistent.mp3"
        target = tmp_path / "output.wav"

        converter = FileConverter()
        job = ConversionJob(
            source=source,
            target=target,
            source_format="mp3",
            target_format="wav",
            tool="ffmpeg",
        )

        result = converter.convert(job)

        assert not result.success
        assert "existiert nicht" in result.message.lower()

    def test_convert_invalid_tool(self, tmp_path):
        """Test conversion with invalid tool."""
        source = tmp_path / "input.mp3"
        target = tmp_path / "output.wav"
        source.touch()

        converter = FileConverter()
        job = ConversionJob(
            source=source,
            target=target,
            source_format="mp3",
            target_format="wav",
            tool="invalid_tool",
        )

        result = converter.convert(job)

        assert not result.success
        assert "unbekanntes" in result.message.lower() or "tool" in result.message.lower()


class TestConversionFormats:
    """Test conversion format definitions."""

    def test_conversion_formats_structure(self):
        """Test that CONVERSION_FORMATS has expected formats."""
        assert "mp3" in CONVERSION_FORMATS
        assert "mp4" in CONVERSION_FORMATS
        assert "png" in CONVERSION_FORMATS

    def test_audio_formats(self):
        """Test audio format definitions."""
        assert "mp3" in CONVERSION_FORMATS
        assert "wav" in CONVERSION_FORMATS
        assert "flac" in CONVERSION_FORMATS

        mp3 = CONVERSION_FORMATS["mp3"]
        assert mp3.tool == "ffmpeg"
        assert mp3.extension == "mp3"
        assert mp3.display_name == "MP3 Audio"

    def test_video_formats(self):
        """Test video format definitions."""
        assert "mp4" in CONVERSION_FORMATS
        assert "mkv" in CONVERSION_FORMATS

        mp4 = CONVERSION_FORMATS["mp4"]
        assert mp4.tool == "ffmpeg"
        assert mp4.extension == "mp4"

    def test_image_formats(self):
        """Test image format definitions."""
        assert "png" in CONVERSION_FORMATS
        assert "jpg" in CONVERSION_FORMATS
        assert "webp" in CONVERSION_FORMATS

        png = CONVERSION_FORMATS["png"]
        assert png.tool == "imagemagick"
        assert png.extension == "png"
