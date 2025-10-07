import sys
import os
import logging
from pathlib import Path
import traceback

# Set up logging
logging.basicConfig(level=logging.DEBUG)

try:
    print("Testing Media Library Enhanced Widget...")
    
    # Import the necessary modules
    from PySide6.QtWidgets import QApplication
    
    # Create QApplication instance
    app = QApplication([])
    print("QApplication created")
    
    # Create a mock plugin
    class MockPlugin:
        def __init__(self):
            self.services = MockServices()
            
        def load_config(self):
            return {"enhanced_enabled": True}
            
        def __getattr__(self, name):
            # Provide fallbacks for any other attributes
            return lambda *args, **kwargs: None
    
    class MockServices:
        def __init__(self):
            self.data_dir = Path("./test_data")
            os.makedirs(self.data_dir, exist_ok=True)
            
        def ensure_subdirectories(self, name):
            directory = self.data_dir / name
            os.makedirs(directory, exist_ok=True)
            return [directory]
    
    # Try to create the enhanced widget
    try:
        print("Trying to import and create enhanced widget...")
        from mmst.plugins.media_library.enhanced.factory import create_enhanced_widget
        plugin = MockPlugin()
        print("Mock plugin created")
        widget = create_enhanced_widget(plugin)
        print("Enhanced widget created successfully!")
        print(f"Widget type: {type(widget)}")
        print(f"Widget is visible: {widget.isVisible()}")
    except Exception as e:
        print(f"Error creating enhanced widget: {e}")
        traceback.print_exc()
        
    # Try to create the minimal widget for comparison
    try:
        print("\nTrying to create minimal widget...")
        from mmst.plugins.media_library._restored_media_library import MediaLibraryWidget
        widget = MediaLibraryWidget(MockPlugin())
        print("Minimal widget created successfully!")
        print(f"Widget type: {type(widget)}")
    except Exception as e:
        print(f"Error creating minimal widget: {e}")
        traceback.print_exc()
        
except Exception as e:
    print(f"Test script error: {e}")
    traceback.print_exc()