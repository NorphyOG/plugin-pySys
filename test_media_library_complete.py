"""
Complete test script for the media library widget
"""
import sys
from pathlib import Path
import os
import traceback

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
    
    # Create QApplication
    app = QApplication(sys.argv)
    
    # Create main window
    window = QMainWindow()
    central = QWidget()
    layout = QVBoxLayout(central)
    window.setCentralWidget(central)
    window.setWindowTitle("Media Library Test")
    window.resize(800, 600)
    
    # Create mock structures for plugin
    class MockMediaFile:
        def __init__(self, path, size=0, mtime=0, kind="audio", rating=None, tags=None):
            self.path = str(path)
            self.size = size
            self.mtime = mtime
            self.kind = kind
            self.rating = rating
            self.tags = tags or tuple()
    
    class MockPlugin:
        def __init__(self):
            self.services = MockServices()
            self._backend_ready = True
            
        def load_config(self):
            return {"enhanced_enabled": True}
            
        def list_files(self, *args, **kwargs):
            return []
        
        def list_recent_detailed(self, limit=None):
            # Create some test files
            test_files = [
                (MockMediaFile("C:/Music/test1.mp3", kind="audio", rating=5, tags=("rock", "2020")), 
                 Path("C:/Music/test1.mp3")),
                (MockMediaFile("C:/Music/test2.mp3", kind="audio", rating=3, tags=("jazz",)), 
                 Path("C:/Music/test2.mp3")),
                (MockMediaFile("C:/Videos/movie.mp4", kind="video", rating=4), 
                 Path("C:/Videos/movie.mp4")),
            ]
            return test_files
        
        @property
        def custom_presets(self):
            return {}
    
    # Setup data directory
    data_dir = Path("./test_data")
    data_dir.mkdir(exist_ok=True)
    
    # Create mock services
    class MockServices:
        def __init__(self):
            self.data_dir = data_dir
            
        def ensure_subdirectories(self, name):
            subdir = self.data_dir / name
            subdir.mkdir(exist_ok=True)
            return [subdir]
            
        def send_notification(self, message, level="info", source=None):
            print(f"[{level}] {source}: {message}")
            
        def get_logger(self, name):
            import logging
            return logging.getLogger(name)
    
    # Try different implementation modes
    
    # 1. First try the minimal widget
    try:
        print("\nTesting minimal implementation...")
        from mmst.plugins.media_library._restored_media_library import MediaLibraryWidget
        
        widget = MediaLibraryWidget(MockPlugin())
        layout.addWidget(widget)
        print("Minimal widget created successfully!")
    except Exception as e:
        print(f"Error loading minimal widget: {e}")
        traceback.print_exc()
    
    # 2. Try enhanced mode
    try:
        print("\nTesting enhanced implementation...")
        from mmst.plugins.media_library.enhanced.factory import create_enhanced_widget
        
        # Update layout - remove previous widget
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        widget = create_enhanced_widget(MockPlugin())
        layout.addWidget(widget)
        print("Enhanced widget created successfully!")
    except Exception as e:
        print(f"Error loading enhanced widget: {e}")
        traceback.print_exc()
    
    # Show window and run app
    window.show()
    print("\nRunning application...")
    app.exec()
    
except Exception as e:
    print(f"Setup error: {e}")
    traceback.print_exc()