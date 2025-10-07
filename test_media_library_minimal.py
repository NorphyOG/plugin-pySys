"""
Test script for the minimal media library widget
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
    window.setWindowTitle("Media Library Minimal Test")
    window.resize(800, 600)
    
    # Import the minimal widget
    try:
        print("Loading Media Library Minimal Widget...")
        from mmst.plugins.media_library._restored_media_library import MediaLibraryWidget
        
        # Create mock plugin
        class MockPlugin:
            def __init__(self):
                self.services = MockServices()
                
            def list_files(self, *args, **kwargs):
                return []
                
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
        
        # Create widget instance
        print("Creating Media Library widget...")
        widget = MediaLibraryWidget(MockPlugin())
        
        # Add to layout
        layout.addWidget(widget)
        window.show()
        
        # Run app
        print("Running application...")
        app.exec()
        
    except Exception as e:
        print(f"Error loading Media Library widget: {e}")
        traceback.print_exc()
    
except Exception as e:
    print(f"Setup error: {e}")
    traceback.print_exc()