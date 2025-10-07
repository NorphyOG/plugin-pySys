"""
Simple test script to directly test the Media Library widget outside the main app
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
    
    # Import the legacy plugin directly
    try:
        print("Loading Media Library Legacy Plugin...")
        from mmst.plugins.media_library.legacy import Plugin as MediaLibraryPlugin
        from mmst.core.services import CoreServices
        
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
            
        # Create plugin instance
        mock_services = MockServices()
        plugin = MediaLibraryPlugin(services=mock_services)
        
        # Create view
        print("Creating Media Library view...")
        widget = plugin.create_view()
        
        # Add to layout
        layout.addWidget(widget)
        window.show()
        
        # Run app
        print("Running application...")
        app.exec()
        
    except Exception as e:
        print(f"Error loading Media Library plugin: {e}")
        traceback.print_exc()
    
except Exception as e:
    print(f"Setup error: {e}")
    traceback.print_exc()