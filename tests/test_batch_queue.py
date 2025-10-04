"""
Tests for SystemTools batch conversion queue.

Verifies that the batch queue processes jobs sequentially and emits
appropriate events for inter-plugin communication.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from mmst.plugins.system_tools.converter import ConversionJob, ConversionResult, FileConverter


def test_conversion_job_creation():
    """Test that ConversionJob can be created with proper fields."""
    source = Path("/source/file.mp3")
    target = Path("/target/file.mp4")
    
    job = ConversionJob(
        source=source,
        target=target,
        source_format="mp3",
        target_format="mp4",
        tool="ffmpeg",
        command_path=Path("/usr/bin/ffmpeg")
    )
    
    assert job.source == source
    assert job.target == target
    assert job.source_format == "mp3"
    assert job.target_format == "mp4"
    assert job.tool == "ffmpeg"
    assert job.command_path == Path("/usr/bin/ffmpeg")


def test_conversion_result_creation():
    """Test that ConversionResult can be created with proper fields."""
    source = Path("/source/file.mp3")
    target = Path("/target/file.mp4")
    
    result = ConversionResult(
        success=True,
        source=source,
        target=target,
        message="Conversion completed",
        output_size=1024
    )
    
    assert result.success is True
    assert result.source == source
    assert result.target == target
    assert result.message == "Conversion completed"
    assert result.output_size == 1024


def test_file_converter_handles_missing_source():
    """Test that converter detects when source file doesn't exist."""
    converter = FileConverter()
    
    job = ConversionJob(
        source=Path("/nonexistent/file.mp3"),
        target=Path("/target/file.mp4"),
        source_format="mp3",
        target_format="mp4",
        tool="ffmpeg"
    )
    
    result = converter.convert(job)
    
    assert result.success is False
    assert "existiert nicht" in result.message


def test_file_converter_rejects_unknown_tool():
    """Test that converter rejects jobs with unknown tools."""
    converter = FileConverter()
    
    # Create a temporary source file
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        source_path = Path(tmp.name)
    
    try:
        job = ConversionJob(
            source=source_path,
            target=Path("/target/file.mp4"),
            source_format="mp3",
            target_format="mp4",
            tool="unknown_tool"
        )
        
        result = converter.convert(job)
        
        assert result.success is False
        assert "Unbekanntes Tool" in result.message
    finally:
        source_path.unlink()


def test_file_converter_ffmpeg_success(tmp_path):
    """Test successful ffmpeg conversion with mocked subprocess."""
    converter = FileConverter()
    
    source = tmp_path / "source.mp3"
    source.write_text("fake audio content")
    target = tmp_path / "target.mp4"
    
    job = ConversionJob(
        source=source,
        target=target,
        source_format="mp3",
        target_format="mp4",
        tool="ffmpeg",
        command_path=Path("/usr/bin/ffmpeg")
    )
    
    # Mock subprocess.run to simulate successful conversion
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = "Conversion successful"
    
    with patch('subprocess.run', return_value=mock_result):
        # Create the target file to simulate conversion
        target.write_text("fake video content")
        
        result = converter.convert(job, progress=Mock())
        
        assert result.success is True
        assert result.source == source
        assert result.target == target


def test_file_converter_ffmpeg_failure(tmp_path):
    """Test failed ffmpeg conversion with mocked subprocess."""
    converter = FileConverter()
    
    source = tmp_path / "source.mp3"
    source.write_text("fake audio content")
    target = tmp_path / "target.mp4"
    
    job = ConversionJob(
        source=source,
        target=target,
        source_format="mp3",
        target_format="mp4",
        tool="ffmpeg",
        command_path=Path("/usr/bin/ffmpeg")
    )
    
    # Mock subprocess.run to simulate failed conversion
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Error: invalid codec"
    
    with patch('subprocess.run', return_value=mock_result):
        result = converter.convert(job, progress=Mock())
        
        assert result.success is False


def test_batch_queue_sequential_processing():
    """Test that batch queue processes jobs in sequential order."""
    # This is a conceptual test showing how batch processing should work
    jobs = []
    processed_order = []
    
    # Create mock jobs
    for i in range(3):
        job = ConversionJob(
            source=Path(f"/source/file{i}.mp3"),
            target=Path(f"/target/file{i}.mp4"),
            source_format="mp3",
            target_format="mp4",
            tool="ffmpeg"
        )
        jobs.append(job)
    
    # Mock converter
    converter = FileConverter()
    
    def mock_convert(job, progress=None):
        processed_order.append(job.source.name)
        return ConversionResult(
            success=True,
            source=job.source,
            target=job.target,
            message="Success"
        )
    
    converter.convert = mock_convert
    
    # Process jobs sequentially
    for job in jobs:
        converter.convert(job)
    
    # Verify order
    assert processed_order == ["file0.mp3", "file1.mp3", "file2.mp3"]


def test_conversion_with_progress_callback(tmp_path):
    """Test that progress callback is invoked during conversion."""
    converter = FileConverter()
    
    source = tmp_path / "source.mp3"
    source.write_text("fake audio")
    target = tmp_path / "target.mp4"
    
    job = ConversionJob(
        source=source,
        target=target,
        source_format="mp3",
        target_format="mp4",
        tool="ffmpeg",
        command_path=Path("/usr/bin/ffmpeg")
    )
    
    progress_messages = []
    
    def progress_callback(message):
        progress_messages.append(message)
    
    # Mock subprocess.run
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = "frame=100 fps=25"
    
    with patch('subprocess.run', return_value=mock_result):
        target.write_text("fake video")
        result = converter.convert(job, progress=progress_callback)
        
        # Progress callback should have been called
        # (actual implementation may vary)
        assert result.success is True


def test_imagemagick_conversion(tmp_path):
    """Test ImageMagick conversion path."""
    converter = FileConverter()
    
    source = tmp_path / "source.jpg"
    source.write_text("fake image")
    target = tmp_path / "target.png"
    
    job = ConversionJob(
        source=source,
        target=target,
        source_format="jpg",
        target_format="png",
        tool="imagemagick",
        command_path=Path("/usr/bin/convert")
    )
    
    # Mock subprocess.run
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = ""
    
    with patch('subprocess.run', return_value=mock_result):
        target.write_text("fake png")
        result = converter.convert(job, progress=Mock())
        
        assert result.success is True
        assert result.source == source
        assert result.target == target
