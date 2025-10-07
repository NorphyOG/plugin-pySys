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
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
    
    # Create QApplication instance
    app = QApplication([])
    print("QApplication created")
    
    # Create a wrapper window to hold our widget
    window = QMainWindow()
    central = QWidget()
    window.setCentralWidget(central)
    layout = QVBoxLayout(central)
    
    # Create a mock plugin with much more functionality
    class MockPlugin:
        def __init__(self):
            self.services = MockServices()
            self._backend_ready = True
            self._library_index = None
            
        def load_config(self):
            return {"enhanced_enabled": True}
            
        def list_recent_detailed(self, limit=None):
            return []
            
        def custom_presets(self):
            return {}
            
    class MockServices:
        def __init__(self):
            self.data_dir = Path("./test_data")
            os.makedirs(self.data_dir, exist_ok=True)
            
        def ensure_subdirectories(self, name):
            directory = self.data_dir / name
            os.makedirs(directory, exist_ok=True)
            return [directory]
            
        def get_logger(self, name):
            return logging.getLogger(name)
    
    # First, try to manually import and initialize all the necessary pieces
    print("Checking imports...")
    
    try:
        from mmst.plugins.media_library.enhanced.base import EnhancedRootWidget
        print("Successfully imported EnhancedRootWidget")
    except Exception as e:
        print(f"Error importing EnhancedRootWidget: {e}")
        traceback.print_exc()
    
    try:
        from mmst.plugins.media_library.enhanced.dashboard import DashboardPlaceholder
        print("Successfully imported DashboardPlaceholder")
    except Exception as e:
        print(f"Error importing DashboardPlaceholder: {e}")
        traceback.print_exc()
    
    try:
        from mmst.plugins.media_library.enhanced.table_view import EnhancedTableWidget
        print("Successfully imported EnhancedTableWidget")
    except Exception as e:
        print(f"Error importing EnhancedTableWidget: {e}")
        traceback.print_exc()
        
    # Now try to create the widgets individually
    dashboard_widget = None
    table_widget = None
    
    try:
        print("\nTrying to create DashboardPlaceholder...")
        plugin = MockPlugin()
        if 'DashboardPlaceholder' in globals():
            dashboard_widget = DashboardPlaceholder(plugin)
            print("DashboardPlaceholder created successfully!")
        else:
            print("DashboardPlaceholder not available in globals")
    except Exception as e:
        print(f"Error creating DashboardPlaceholder: {e}")
        traceback.print_exc()
        
    try:
        print("\nTrying to create EnhancedTableWidget...")
        plugin = MockPlugin()
        if 'EnhancedTableWidget' in globals():
            table_widget = EnhancedTableWidget(plugin)
            print("EnhancedTableWidget created successfully!")
        else:
            print("EnhancedTableWidget not available in globals")
    except Exception as e:
        print(f"Error creating EnhancedTableWidget: {e}")
        traceback.print_exc()
    
    # Try to create the enhanced widget
    try:
        print("\nTrying to create EnhancedRootWidget...")
        from mmst.plugins.media_library.enhanced.factory import create_enhanced_widget
        plugin = MockPlugin()
        widget = create_enhanced_widget(plugin)
        print("Enhanced widget created successfully!")
        print(f"Widget type: {type(widget)}")
        
        # Add it to our window
        try:
            layout.addWidget(widget)
            window.setWindowTitle("Media Library Test")
            window.resize(800, 600)
            window.show()
        except Exception as e:
            print(f"Error showing widget: {e}")
            traceback.print_exc()
        
        # Run the app
        print("\nStarting Qt event loop...")
        app.exec()
    except Exception as e:
        print(f"Error creating enhanced widget: {e}")
        traceback.print_exc()
        
except Exception as e:
    print(f"Test script error: {e}")
    traceback.print_exc()