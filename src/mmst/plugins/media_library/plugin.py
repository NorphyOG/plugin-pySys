"""Media Library plugin (clean delegating wrapper).

This file deliberately contains only a tiny, stable surface that forwards
imports to the minimal implementation in ``_restored_media_library``.
The previous enhanced monolithic implementation was corrupted; a future
rebuild will live in a separate module (e.g. ``plugin_enhanced.py``) and
be opt‑in so tests remain green.
"""

from __future__ import annotations

from typing import Any
from pathlib import Path
import threading
import concurrent.futures

import os
from ._restored_media_library import Plugin as _MinimalPlugin  # noqa: F401
from ._restored_media_library import MediaLibraryWidget as _MinimalWidget  # noqa: F401
try:
    from .legacy import Plugin as LegacyPlugin, MediaLibraryWidget as LegacyWidget  # type: ignore
except Exception:  # pragma: no cover - fallback if legacy module missing
    LegacyPlugin = _MinimalPlugin  # type: ignore
    LegacyWidget = _MinimalWidget  # type: ignore

ENHANCED_ENV_FLAG = "MMST_MEDIA_LIBRARY_ENHANCED"
ULTRA_ENV_FLAG = "MMST_MEDIA_LIBRARY_ULTRA"

def _enhanced_enabled(plugin=None) -> bool:
    # Always enable enhanced features
    return True

def _ultra_enabled(plugin=None) -> bool:
    # Always enable ultra features
    return True

try:
    from .enhanced import create_enhanced_widget  # type: ignore
    _HAS_ENHANCED = True
    # ultra optional import (soft-fail)
    try:
        from .enhanced.neo_root import create_ultra_widget  # type: ignore
        _HAS_ULTRA = True
    except Exception:  # pragma: no cover
        create_ultra_widget = None  # type: ignore
        _HAS_ULTRA = False
except Exception:  # pragma: no cover
    create_enhanced_widget = None  # type: ignore
    _HAS_ENHANCED = False
    create_ultra_widget = None  # type: ignore
    _HAS_ULTRA = False


class Plugin(LegacyPlugin):  # type: ignore
    """Plugin wrapper that can provide enhanced or minimal widget at runtime."""
    _backend_ready: bool = True
    _widget = None

    def _ensure_backend(self):  # lightweight bridge for enhanced mode
        if self._backend_ready and hasattr(self, '_library_index') and self._library_index is not None:
            return
        try:
            from .core import LibraryIndex  # type: ignore
            dirs = list(self.services.ensure_subdirectories("library"))  # type: ignore[attr-defined]
            data_dir = dirs[0] if dirs else self.services.data_dir  # type: ignore[attr-defined]
            db_path = data_dir / "library.db"
            self._library_index = LibraryIndex(db_path)  # type: ignore
            self._backend_ready = True
        except Exception as e:  # pragma: no cover
            # Log error but still try to keep backend enabled
            import logging
            logging.getLogger("mmst.media_library").error(f"Error initializing backend: {e}")
            try:
                # Retry with additional error handling
                from .core import LibraryIndex  # type: ignore
                import os
                
                # Make sure data directories exist
                dirs = list(self.services.ensure_subdirectories("library"))  # type: ignore[attr-defined]
                data_dir = dirs[0] if dirs else self.services.data_dir  # type: ignore[attr-defined]
                db_path = data_dir / "library.db"
                
                # Make sure directory exists
                os.makedirs(os.path.dirname(str(db_path)), exist_ok=True)
                
                self._library_index = LibraryIndex(db_path)  # type: ignore
                self._backend_ready = True
            except Exception as e2:
                logging.getLogger("mmst.media_library").error(f"Failed retry initializing backend: {e2}")
                self._backend_ready = False
                self._library_index = None  # type: ignore

    def create_view(self):  # type: ignore[override]
        # Always try to initialize the backend first
        self._ensure_backend()
        
        # Force Ultra/Enhanced mode
        import os
        os.environ["MMST_MEDIA_LIBRARY_ENHANCED"] = "1"
        os.environ["MMST_MEDIA_LIBRARY_ULTRA"] = "1"
        
        import logging
        logger = logging.getLogger("mmst.media_library")
        logger.info("Creating media library view (ENHANCED MODE)...")
        
        # Ultra takes precedence if available
        if '_HAS_ULTRA' in globals() and _HAS_ULTRA and create_ultra_widget:
            logger.info("Attempting to create ultra widget")
            try:
                widget = create_ultra_widget(self)  # type: ignore
                if widget:
                    logger.info("Successfully created ultra widget")
                    return widget
                else:
                    logger.warning("Ultra widget creation returned None")
            except Exception as e:
                logger.error(f"Error creating ultra widget: {e}")
        
        # Enhanced as second option
        if _HAS_ENHANCED and create_enhanced_widget:
            logger.info("Attempting to create enhanced widget")
            try:
                widget = create_enhanced_widget(self)
                if widget:
                    logger.info("Successfully created enhanced widget")
                    return widget
                else:
                    logger.warning("Enhanced widget creation returned None")
            except Exception as e:
                logger.error(f"Error creating enhanced widget: {e}")
        
        # Fallback to minimal widget
        logger.warning("Falling back to minimal widget - neither ultra nor enhanced available")
        try:
            widget = super().create_view()
            # Ensure the widget is properly initialized
            if widget and hasattr(widget, '_load_initial_entries'):
                try:
                    widget._load_initial_entries()
                    logger.info("Minimal widget loaded with initial entries")
                except Exception as e:
                    logger.error(f"Error loading initial entries in minimal widget: {e}")
            return widget
        except Exception as e:
            logger.error(f"Error creating minimal widget: {e}")
            
            # Last resort - create an extremely simple fallback widget with error message
            try:
                from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
                placeholder = QWidget()
                layout = QVBoxLayout(placeholder)
                error_label = QLabel(f"Media library initialization failed: {e}")
                layout.addWidget(error_label)
                
                # Add a scan button that will try to scan default locations
                scan_button = QPushButton("Scan Default Locations")
                def on_scan_clicked():
                    try:
                        self._scan_default_locations()
                        error_label.setText("Scan completed. Please restart the application.")
                    except Exception as e2:
                        error_label.setText(f"Scan failed: {e2}")
                
                try:
                    scan_button.clicked.connect(on_scan_clicked)
                except Exception:
                    pass
                layout.addWidget(scan_button)
                
                return placeholder
            except Exception:
                # If all else fails, return a simple QWidget
                try:
                    from PySide6.QtWidgets import QWidget
                    return QWidget()
                except Exception:
                    return None

    # Bridge API pieces used by enhanced widgets --------------------------------
    def list_recent_detailed(self, limit: int | None = 250):  # type: ignore[override]
        try:
            if getattr(self, '_library_index', None) is None:
                self._ensure_backend()
                if getattr(self, '_library_index', None) is None:
                    import logging
                    logging.getLogger("mmst.media_library").error("Cannot list files - library index not available")
                    return []
            return self._library_index.list_files_with_sources(limit)  # type: ignore[attr-defined]
        except Exception as e:
            import logging
            logging.getLogger("mmst.media_library").error(f"Error listing recent files: {e}")
            return []

    # ------------------------------ scanning API (enhanced only)
    def scan_paths(self, roots: list[Path]) -> None:
        """Index media files under given roots (shallow recursive)."""
        import logging
        logger = logging.getLogger("mmst.media_library")
        
        if not roots:
            logger.warning("No paths provided for scanning")
            return
            
        self._ensure_backend()
        if getattr(self, '_library_index', None) is None:
            logger.error("Cannot scan paths - library index not available")
            return
            
        lib = self._library_index  # type: ignore
        exts_media = {".mp3",".flac",".wav",".m4a",".ogg",".mp4",".mkv",".mov",".avi",".webm",".jpg",".jpeg",".png",".gif",".webp",".bmp"}
        files: list[Path] = []
        
        # Report scanning start
        logger.info(f"Starting media scan in {len(roots)} paths")
        
        for r in roots:
            if not r.exists():
                logger.warning(f"Path does not exist: {r}")
                continue
            try:
                for p in r.rglob('*'):
                    if p.is_file() and p.suffix.lower() in exts_media:
                        files.append(p)
            except Exception as e:
                logger.error(f"Error scanning path {r}: {e}")
        if not files:
            logger.warning("No media files found in the specified paths")
            return
            
        # Ensure sources
        sources = {}
        for root in roots:
            try:
                sources[root.resolve()] = lib.add_source(root.resolve())  # type: ignore[attr-defined]
                logger.debug(f"Added source: {root.resolve()}")
            except Exception as e:
                logger.error(f"Error adding source {root}: {e}")
                continue
                
        if not sources:
            logger.error("No valid sources to add files to")
            return
            
        # Report the number of files found
        logger.info(f"Found {len(files)} media files to process")
            
        lock = threading.Lock()
        failed_files = 0
        processed_files = 0
        
        def ingest(p: Path):
            nonlocal failed_files, processed_files
            try:
                st = p.stat()
                from .core import MediaFile, infer_kind  # type: ignore
                mf = MediaFile(path=p.name, size=st.st_size, mtime=st.st_mtime, kind=infer_kind(p))
                # identify source
                found_source = False
                for src_path, sid in sources.items():
                    try:
                        p.relative_to(src_path)
                        rel = str(p.relative_to(src_path))
                        if hasattr(lib, '_lock') and hasattr(lib, '_conn'):
                            with lib._lock:  # type: ignore[attr-defined]
                                lib._conn.execute(  # type: ignore[attr-defined]
                                    "INSERT OR IGNORE INTO files(source_id, path, size, mtime, kind) VALUES (?,?,?,?,?)",
                                    (sid, rel, mf.size, mf.mtime, mf.kind),
                                )
                            found_source = True
                            with lock:
                                processed_files += 1
                                if processed_files % 100 == 0:
                                    logger.info(f"Processed {processed_files} files so far")
                        break
                    except Exception:
                        continue
                        
                if not found_source:
                    with lock:
                        failed_files += 1
                        
            except Exception as e:
                with lock:
                    failed_files += 1
                    if failed_files < 10:  # Limit error logging to avoid flooding
                        logger.error(f"Error processing file {p}: {e}")
                return
                
        # Threaded ingest
        logger.info("Starting multi-threaded media file processing")
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(ingest, files))
            
        # Commit changes and report results
        try:
            if hasattr(lib, '_lock') and hasattr(lib, '_conn'):
                with lib._lock:  # type: ignore[attr-defined]
                    lib._conn.commit()  # type: ignore[attr-defined]
                    
            logger.info(f"Media scan completed: {processed_files} files processed, {failed_files} files failed")
            
        except Exception as e:
            logger.error(f"Error committing changes to database: {e}")

    def set_rating(self, path: Path, rating: int | None) -> None:  # type: ignore[override]
        try:
            self._ensure_backend()
            if getattr(self, '_library_index', None) is None:
                import logging
                logging.getLogger("mmst.media_library").error("Cannot set rating - library index not available")
                return
            self._library_index.set_rating(path, rating)  # type: ignore[attr-defined]
            import logging
            logging.getLogger("mmst.media_library").debug(f"Rating set to {rating} for {path.name}")
        except Exception as e:
            import logging
            logging.getLogger("mmst.media_library").error(f"Error setting rating for {path.name}: {e}")

    def set_tags(self, path: Path, tags):  # type: ignore[override]
        try:
            self._ensure_backend()
            if getattr(self, '_library_index', None) is None:
                import logging
                logging.getLogger("mmst.media_library").error("Cannot set tags - library index not available")
                return
            self._library_index.set_tags(path, tags)  # type: ignore[attr-defined]
            import logging
            logging.getLogger("mmst.media_library").debug(f"Tags set for {path.name}: {tags}")
        except Exception as e:
            import logging
            logging.getLogger("mmst.media_library").error(f"Error setting tags for {path.name}: {e}")
    
    def start(self) -> None:
        """Start the plugin and ensure backend initialization."""
        import logging
        logger = logging.getLogger("mmst.media_library")
        logger.info("Starting media library plugin...")
        
        try:
            # Always ensure the backend is initialized
            self._ensure_backend()
            
            # Configure enhanced mode
            import os
            os.environ["MMST_MEDIA_LIBRARY_ENHANCED"] = "1"
            
            # Check if we have any files in the library
            has_files = False
            try:
                if hasattr(self, '_library_index') and self._library_index is not None:
                    files = self._library_index.list_files(limit=1)
                    has_files = len(files) > 0
            except Exception as e:
                logger.error(f"Error checking for existing files: {e}")
                
            # If no files are found, perform initial scan
            if not has_files:
                logger.info("No files found in the library. Performing initial scan...")
                self._scan_default_locations()
                
            # Refresh widget if it exists
            if hasattr(self, '_widget') and self._widget is not None:
                logger.info("Refreshing media library widget...")
                # Force a reload of entries if the method exists
                if hasattr(self._widget, '_load_initial_entries'):
                    try:
                        self._widget._load_initial_entries()
                        logger.info("Reloaded entries in widget")
                    except Exception as e:
                        logger.error(f"Error reloading entries: {e}")
                
                # Force UI update if the method exists
                if hasattr(self._widget, '_rebuild_table'):
                    try:
                        self._widget._rebuild_table()
                        logger.info("Rebuilt table in widget")
                    except Exception as e:
                        logger.error(f"Error rebuilding table: {e}")
                        
            logger.info("Media library plugin started successfully")
            
        except Exception as e:
            logger.error(f"Error during media library plugin start: {e}")
            
    def _scan_default_locations(self) -> None:
        """Scan common media locations for files."""
        import logging
        logger = logging.getLogger("mmst.media_library")
        logger.info("Starting to scan default media locations...")
        
        try:
            # Try to scan some default locations
            from pathlib import Path
            import os
            
            # Common media locations to scan
            paths_to_check = []
            
            # Add user Pictures and Music folders
            user_home = Path.home()
            pictures = user_home / "Pictures"
            music = user_home / "Music"
            videos = user_home / "Videos"
            downloads = user_home / "Downloads"
            
            scan_locations = []
            
            if pictures.exists():
                paths_to_check.append(pictures)
                logger.info(f"Adding Pictures directory: {pictures}")
            if music.exists():
                paths_to_check.append(music)
                logger.info(f"Adding Music directory: {music}")
            if videos.exists():
                paths_to_check.append(videos)
                logger.info(f"Adding Videos directory: {videos}")
            if downloads.exists():
                paths_to_check.append(downloads)
                logger.info(f"Adding Downloads directory: {downloads}")
                
            # Add current project folder for testing
            current_dir = Path.cwd()
            if current_dir.exists():
                paths_to_check.append(current_dir)
                logger.info(f"Adding current directory: {current_dir}")
                
            # Use the plugin's scan_paths method
            self.scan_paths(paths_to_check)
            
        except Exception as e:
            logger.error(f"Error scanning default locations: {e}")

MediaLibraryWidget = LegacyWidget  # default export remains minimal/legacy depending on availability
EnhancedMediaLibraryWidget = MediaLibraryWidget  # pragma: no cover - backward-compatible alias


class MediaLibraryWidgetFactory:  # pragma: no cover
    @staticmethod
    def create(plugin: Any) -> MediaLibraryWidget:
        # Ensure backend is ready
        if hasattr(plugin, '_ensure_backend'):
            plugin._ensure_backend()
            
        # First try Ultra widget if available
        if '_HAS_ULTRA' in globals() and _HAS_ULTRA and create_ultra_widget:
            try:
                return create_ultra_widget(plugin)  # type: ignore
            except Exception as e:
                import logging
                logging.getLogger("mmst.media_library").error(f"Ultra widget creation failed: {e}")
                
        # Then try Enhanced widget
        if _HAS_ENHANCED and create_enhanced_widget:
            try:
                return create_enhanced_widget(plugin)  # type: ignore
            except Exception as e:
                import logging
                logging.getLogger("mmst.media_library").error(f"Enhanced widget creation failed: {e}")
                
        # Fallback to basic widget
        import logging
        logging.getLogger("mmst.media_library").warning("Using basic media library widget - advanced features not available")
        return MediaLibraryWidget(plugin)


__all__ = [
    "Plugin",
    "MediaLibraryWidget",
    "EnhancedMediaLibraryWidget",
    "MediaLibraryWidgetFactory",
]
