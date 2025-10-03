"""Real-time filesystem monitoring for MediaLibrary."""
import logging
from pathlib import Path
from typing import Callable, Optional

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None  # type: ignore
    FileSystemEventHandler = object  # type: ignore
    FileSystemEvent = None  # type: ignore


logger = logging.getLogger(__name__)


class MediaFileHandler(FileSystemEventHandler):
    """Handles filesystem events for media files."""
    
    # Supported media extensions
    MEDIA_EXTENSIONS = {
        # Audio
        ".mp3", ".flac", ".m4a", ".wav", ".ogg", ".aac", ".wma",
        # Video
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
        # Images
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff",
    }
    
    def __init__(
        self,
        on_created: Optional[Callable[[Path], None]] = None,
        on_modified: Optional[Callable[[Path], None]] = None,
        on_deleted: Optional[Callable[[Path], None]] = None,
        on_moved: Optional[Callable[[Path, Path], None]] = None,
    ):
        """Initialize handler with callbacks.
        
        Args:
            on_created: Called when a new file is created
            on_modified: Called when a file is modified
            on_deleted: Called when a file is deleted
            on_moved: Called when a file is moved (old_path, new_path)
        """
        super().__init__()
        self._on_created = on_created
        self._on_modified = on_modified
        self._on_deleted = on_deleted
        self._on_moved = on_moved
    
    def _is_media_file(self, path: Path) -> bool:
        """Check if path is a supported media file."""
        return path.suffix.lower() in self.MEDIA_EXTENSIONS
    
    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        if self._is_media_file(path) and self._on_created:
            logger.debug(f"File created: {path}")
            self._on_created(path)
    
    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        if self._is_media_file(path) and self._on_modified:
            logger.debug(f"File modified: {path}")
            self._on_modified(path)
    
    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        if self._is_media_file(path) and self._on_deleted:
            logger.debug(f"File deleted: {path}")
            self._on_deleted(path)
    
    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move/rename."""
        if event.is_directory:
            return
        
        old_path = Path(event.src_path)
        new_path = Path(event.dest_path)
        
        # Only trigger if at least one is a media file
        if (self._is_media_file(old_path) or self._is_media_file(new_path)) and self._on_moved:
            logger.debug(f"File moved: {old_path} -> {new_path}")
            self._on_moved(old_path, new_path)


class FileSystemWatcher:
    """Monitors filesystem changes in media library sources."""
    
    def __init__(self):
        """Initialize the filesystem watcher."""
        if not WATCHDOG_AVAILABLE:
            logger.warning("watchdog library not available, filesystem monitoring disabled")
        
        self._observer: Optional[Observer] = None
        self._watched_paths: dict[str, object] = {}  # path -> watch handle
        self._handler: Optional[MediaFileHandler] = None
    
    @property
    def is_available(self) -> bool:
        """Check if watchdog is available."""
        return WATCHDOG_AVAILABLE
    
    @property
    def is_watching(self) -> bool:
        """Check if currently watching any paths."""
        return self._observer is not None and self._observer.is_alive()
    
    def start(
        self,
        on_created: Optional[Callable[[Path], None]] = None,
        on_modified: Optional[Callable[[Path], None]] = None,
        on_deleted: Optional[Callable[[Path], None]] = None,
        on_moved: Optional[Callable[[Path, Path], None]] = None,
    ) -> bool:
        """Start the filesystem observer with callbacks.
        
        Args:
            on_created: Called when a new file is created
            on_modified: Called when a file is modified
            on_deleted: Called when a file is deleted
            on_moved: Called when a file is moved (old_path, new_path)
        
        Returns:
            True if started successfully, False otherwise
        """
        if not self.is_available:
            logger.error("Cannot start watcher: watchdog not available")
            return False
        
        if self.is_watching:
            logger.warning("Watcher already running")
            return True
        
        try:
            self._handler = MediaFileHandler(
                on_created=on_created,
                on_modified=on_modified,
                on_deleted=on_deleted,
                on_moved=on_moved,
            )
            self._observer = Observer()
            self._observer.start()
            logger.info("Filesystem watcher started")
            return True
        except Exception as e:
            logger.error(f"Failed to start watcher: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the filesystem observer."""
        if not self.is_watching:
            return
        
        try:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._watched_paths.clear()
            self._observer = None
            self._handler = None
            logger.info("Filesystem watcher stopped")
        except Exception as e:
            logger.error(f"Error stopping watcher: {e}")
    
    def add_path(self, path: Path, recursive: bool = True) -> bool:
        """Add a path to watch.
        
        Args:
            path: Directory path to watch
            recursive: Watch subdirectories recursively
        
        Returns:
            True if added successfully, False otherwise
        """
        if not self.is_watching:
            logger.error("Cannot add path: watcher not started")
            return False
        
        if not path.exists() or not path.is_dir():
            logger.error(f"Cannot watch path: {path} (not a directory)")
            return False
        
        path_str = str(path)
        if path_str in self._watched_paths:
            logger.debug(f"Path already watched: {path}")
            return True
        
        try:
            watch = self._observer.schedule(self._handler, path_str, recursive=recursive)
            self._watched_paths[path_str] = watch
            logger.info(f"Now watching: {path} (recursive={recursive})")
            return True
        except Exception as e:
            logger.error(f"Failed to add watch for {path}: {e}")
            return False
    
    def remove_path(self, path: Path) -> bool:
        """Remove a path from watching.
        
        Args:
            path: Directory path to stop watching
        
        Returns:
            True if removed successfully, False otherwise
        """
        if not self.is_watching:
            return False
        
        path_str = str(path)
        watch = self._watched_paths.get(path_str)
        
        if not watch:
            logger.debug(f"Path not watched: {path}")
            return False
        
        try:
            self._observer.unschedule(watch)
            del self._watched_paths[path_str]
            logger.info(f"Stopped watching: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove watch for {path}: {e}")
            return False
    
    def get_watched_paths(self) -> list[Path]:
        """Get list of currently watched paths."""
        return [Path(p) for p in self._watched_paths.keys()]
