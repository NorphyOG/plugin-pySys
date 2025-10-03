"""Tests for filesystem watcher functionality."""
import tempfile
import time
from pathlib import Path

import pytest

from mmst.plugins.media_library.watcher import FileSystemWatcher, MediaFileHandler


class TestMediaFileHandler:
    """Test media file event handler."""
    
    def test_handler_creation(self):
        """Test handler can be created."""
        handler = MediaFileHandler()
        assert handler is not None
    
    def test_is_media_file(self):
        """Test media file detection."""
        handler = MediaFileHandler()
        
        # Audio files
        assert handler._is_media_file(Path("test.mp3"))
        assert handler._is_media_file(Path("test.flac"))
        assert handler._is_media_file(Path("test.wav"))
        assert handler._is_media_file(Path("test.m4a"))
        
        # Video files
        assert handler._is_media_file(Path("test.mp4"))
        assert handler._is_media_file(Path("test.mkv"))
        assert handler._is_media_file(Path("test.avi"))
        
        # Image files
        assert handler._is_media_file(Path("test.jpg"))
        assert handler._is_media_file(Path("test.png"))
        
        # Non-media files
        assert not handler._is_media_file(Path("test.txt"))
        assert not handler._is_media_file(Path("test.doc"))
        assert not handler._is_media_file(Path("test.exe"))
    
    def test_case_insensitive_detection(self):
        """Test media file detection is case-insensitive."""
        handler = MediaFileHandler()
        
        assert handler._is_media_file(Path("TEST.MP3"))
        assert handler._is_media_file(Path("Test.Mp4"))
        assert handler._is_media_file(Path("TEST.JPG"))


class TestFileSystemWatcher:
    """Test filesystem watcher."""
    
    def test_watcher_creation(self):
        """Test watcher can be created."""
        watcher = FileSystemWatcher()
        assert watcher is not None
    
    def test_availability_check(self):
        """Test watchdog availability check."""
        watcher = FileSystemWatcher()
        # Should be True since watchdog is installed
        assert watcher.is_available is True
    
    def test_initial_state(self):
        """Test watcher initial state."""
        watcher = FileSystemWatcher()
        assert watcher.is_watching is False
        assert len(watcher.get_watched_paths()) == 0
    
    def test_start_stop(self):
        """Test starting and stopping watcher."""
        watcher = FileSystemWatcher()
        
        # Start watcher
        success = watcher.start()
        assert success is True
        assert watcher.is_watching is True
        
        # Stop watcher
        watcher.stop()
        assert watcher.is_watching is False
    
    def test_add_valid_path(self):
        """Test adding a valid directory to watch."""
        watcher = FileSystemWatcher()
        watcher.start()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            success = watcher.add_path(path)
            assert success is True
            assert path in watcher.get_watched_paths()
        
        watcher.stop()
    
    def test_add_invalid_path(self):
        """Test adding invalid path fails."""
        watcher = FileSystemWatcher()
        watcher.start()
        
        fake_path = Path("/nonexistent/directory")
        success = watcher.add_path(fake_path)
        assert success is False
        
        watcher.stop()
    
    def test_add_without_starting(self):
        """Test adding path without starting fails."""
        watcher = FileSystemWatcher()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            success = watcher.add_path(path)
            assert success is False
    
    def test_remove_path(self):
        """Test removing a watched path."""
        watcher = FileSystemWatcher()
        watcher.start()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            watcher.add_path(path)
            assert path in watcher.get_watched_paths()
            
            success = watcher.remove_path(path)
            assert success is True
            assert path not in watcher.get_watched_paths()
        
        watcher.stop()
    
    def test_multiple_paths(self):
        """Test watching multiple paths."""
        watcher = FileSystemWatcher()
        watcher.start()
        
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                path1 = Path(tmpdir1)
                path2 = Path(tmpdir2)
                
                watcher.add_path(path1)
                watcher.add_path(path2)
                
                watched = watcher.get_watched_paths()
                assert path1 in watched
                assert path2 in watched
                assert len(watched) == 2
        
        watcher.stop()
    
    def test_callbacks_registered(self):
        """Test that callbacks are registered correctly."""
        created_files = []
        modified_files = []
        deleted_files = []
        moved_files = []
        
        def on_created(path: Path):
            created_files.append(path)
        
        def on_modified(path: Path):
            modified_files.append(path)
        
        def on_deleted(path: Path):
            deleted_files.append(path)
        
        def on_moved(old_path: Path, new_path: Path):
            moved_files.append((old_path, new_path))
        
        watcher = FileSystemWatcher()
        success = watcher.start(
            on_created=on_created,
            on_modified=on_modified,
            on_deleted=on_deleted,
            on_moved=on_moved,
        )
        assert success is True
        
        # Note: We don't test actual file events here as they require
        # filesystem operations and can be flaky in tests
        
        watcher.stop()
    
    def test_double_start(self):
        """Test starting watcher twice."""
        watcher = FileSystemWatcher()
        
        assert watcher.start() is True
        assert watcher.start() is True  # Should return True, already running
        
        watcher.stop()
    
    def test_stop_without_start(self):
        """Test stopping without starting."""
        watcher = FileSystemWatcher()
        watcher.stop()  # Should not raise


class TestFileSystemWatcherIntegration:
    """Integration tests for watcher with real files."""
    
    @pytest.mark.slow
    def test_detect_new_media_file(self):
        """Test detecting newly created media file."""
        created_files = []
        
        def on_created(path: Path):
            created_files.append(path)
        
        watcher = FileSystemWatcher()
        watcher.start(on_created=on_created)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            watcher.add_path(path)
            
            # Give watcher time to initialize
            time.sleep(0.5)
            
            # Create a media file
            media_file = path / "test.mp3"
            media_file.write_text("fake mp3 data")
            
            # Give watcher time to detect
            time.sleep(1.0)
            
            # Check if file was detected
            assert media_file in created_files
        
        watcher.stop()
    
    @pytest.mark.slow
    def test_ignore_non_media_file(self):
        """Test that non-media files are ignored."""
        created_files = []
        
        def on_created(path: Path):
            created_files.append(path)
        
        watcher = FileSystemWatcher()
        watcher.start(on_created=on_created)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            watcher.add_path(path)
            
            time.sleep(0.5)
            
            # Create a non-media file
            text_file = path / "test.txt"
            text_file.write_text("not a media file")
            
            time.sleep(1.0)
            
            # Non-media file should not be detected
            assert text_file not in created_files
        
        watcher.stop()
