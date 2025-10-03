"""Tests for MediaLibrary metadata reader and writer."""
import wave
from pathlib import Path

import pytest

from mmst.plugins.media_library.metadata import MediaMetadata, MetadataReader, MetadataWriter


class TestMetadataReader:
    """Test metadata reading from files."""

    def test_reader_initialization(self):
        """Test reader initializes correctly."""
        reader = MetadataReader()
        assert reader is not None

    def test_read_nonexistent_file(self, tmp_path):
        """Test reading from nonexistent file returns empty metadata."""
        reader = MetadataReader()
        fake_file = tmp_path / "nonexistent.mp3"
        
        metadata = reader.read(fake_file)
        
        assert metadata.path == str(fake_file)
        assert metadata.filename == "nonexistent.mp3"
        assert metadata.filesize == 0

    def test_read_audio_file_basic(self, tmp_path):
        """Test reading basic audio file without tags."""
        # Create a minimal WAV file
        audio_file = tmp_path / "test.wav"
        with wave.open(str(audio_file), "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(b"\x00" * 44100 * 2 * 2)  # 1 second of silence
        
        reader = MetadataReader()
        metadata = reader.read(audio_file)
        
        assert metadata.path == str(audio_file)
        assert metadata.filename == "test.wav"
        assert metadata.filesize > 0
        assert metadata.format == "audio"

    def test_metadata_to_dict(self):
        """Test converting metadata to dictionary."""
        metadata = MediaMetadata(
            path="/test/file.mp3",
            filename="file.mp3",
            filesize=1024,
            title="Test Song",
            artist="Test Artist",
            year=2024,
        )
        
        data = metadata.to_dict()
        
        assert isinstance(data, dict)
        assert data["path"] == "/test/file.mp3"
        assert data["filename"] == "file.mp3"
        assert data["filesize"] == 1024
        assert data["title"] == "Test Song"
        assert data["artist"] == "Test Artist"
        assert data["year"] == 2024


class TestMetadataWriter:
    """Test metadata writing to files."""

    def test_writer_initialization(self):
        """Test writer initializes correctly."""
        writer = MetadataWriter()
        assert writer is not None

    def test_write_nonexistent_file(self, tmp_path):
        """Test writing to nonexistent file returns False."""
        writer = MetadataWriter()
        fake_file = tmp_path / "nonexistent.mp3"
        metadata = MediaMetadata(title="Test")
        
        result = writer.write(fake_file, metadata)
        
        assert result is False

    def test_write_unsupported_format(self, tmp_path):
        """Test writing to unsupported format returns False."""
        writer = MetadataWriter()
        text_file = tmp_path / "test.txt"
        text_file.write_text("test")
        metadata = MediaMetadata(title="Test")
        
        result = writer.write(text_file, metadata)
        
        assert result is False


class TestMediaMetadata:
    """Test MediaMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating metadata with default values."""
        metadata = MediaMetadata()
        
        assert metadata.path == ""
        assert metadata.filename == ""
        assert metadata.filesize == 0
        assert metadata.format == ""
        assert metadata.title is None
        assert metadata.artist is None
        assert metadata.tags == []
        assert metadata.actors == []

    def test_metadata_with_values(self):
        """Test creating metadata with specific values."""
        metadata = MediaMetadata(
            path="/music/song.mp3",
            filename="song.mp3",
            filesize=5242880,
            format="audio",
            title="My Song",
            artist="My Artist",
            album="My Album",
            year=2024,
            genre="Rock",
            track_number=3,
            track_total=12,
        )
        
        assert metadata.path == "/music/song.mp3"
        assert metadata.filename == "song.mp3"
        assert metadata.filesize == 5242880
        assert metadata.format == "audio"
        assert metadata.title == "My Song"
        assert metadata.artist == "My Artist"
        assert metadata.album == "My Album"
        assert metadata.year == 2024
        assert metadata.genre == "Rock"
        assert metadata.track_number == 3
        assert metadata.track_total == 12

    def test_metadata_to_dict_complete(self):
        """Test complete metadata conversion to dict."""
        metadata = MediaMetadata(
            path="/test.mp3",
            filename="test.mp3",
            filesize=1024,
            format="audio",
            title="Title",
            artist="Artist",
            album="Album",
            year=2024,
            genre="Genre",
            comment="Comment",
            track_number=1,
            track_total=10,
            disc_number=1,
            disc_total=2,
            composer="Composer",
            bitrate=320,
            sample_rate=48000,
            channels=2,
            codec="mp3",
            rating=5,
            tags=["tag1", "tag2"],
        )
        
        data = metadata.to_dict()
        
        assert data["path"] == "/test.mp3"
        assert data["filename"] == "test.mp3"
        assert data["filesize"] == 1024
        assert data["format"] == "audio"
        assert data["title"] == "Title"
        assert data["artist"] == "Artist"
        assert data["album"] == "Album"
        assert data["year"] == 2024
        assert data["genre"] == "Genre"
        assert data["comment"] == "Comment"
        assert data["track_number"] == 1
        assert data["track_total"] == 10
        assert data["disc_number"] == 1
        assert data["disc_total"] == 2
        assert data["composer"] == "Composer"
        assert data["bitrate"] == 320
        assert data["sample_rate"] == 48000
        assert data["channels"] == 2
        assert data["codec"] == "mp3"
        assert data["rating"] == 5
        assert data["tags"] == ["tag1", "tag2"]

    def test_metadata_video_fields(self):
        """Test video-specific metadata fields."""
        metadata = MediaMetadata(
            path="/video.mp4",
            filename="video.mp4",
            format="video",
            title="Movie Title",
            director="Director Name",
            actors=["Actor 1", "Actor 2"],
            description="Movie description",
            resolution="1920x1080",
            codec="h264",
            duration=7200.0,  # 2 hours
        )
        
        assert metadata.format == "video"
        assert metadata.director == "Director Name"
        assert metadata.actors == ["Actor 1", "Actor 2"]
        assert metadata.description == "Movie description"
        assert metadata.resolution == "1920x1080"
        assert metadata.codec == "h264"
        assert metadata.duration == 7200.0

    def test_metadata_technical_info(self):
        """Test technical information fields."""
        metadata = MediaMetadata(
            bitrate=320,
            sample_rate=48000,
            channels=2,
            codec="flac",
            resolution="1920x1080",
        )
        
        assert metadata.bitrate == 320
        assert metadata.sample_rate == 48000
        assert metadata.channels == 2
        assert metadata.codec == "flac"
        assert metadata.resolution == "1920x1080"
