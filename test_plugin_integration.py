"""Test script to load and test Media Library plugin."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    print("1. Testing plugin import...")
    from mmst.plugins.media_library.plugin import MediaLibraryWidget, MediaLibraryPlugin
    print("   ✓ Plugin import successful")
    
    print("\n2. Testing PySide6...")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    print("   ✓ QApplication ready")
    
    print("\n3. Creating mock plugin service...")
    from mmst.core.services import CoreServices
    import tempfile
    
    class MockPlugin:
        def __init__(self):
            self.services = CoreServices()
            self.logger = self.services.get_logger("test")
            from mmst.plugins.media_library.core import LibraryIndex
            temp_dir = Path(tempfile.mkdtemp())
            self.index = LibraryIndex(temp_dir / "test.db")
    
    mock_plugin = MockPlugin()
    print("   ✓ Mock plugin created")
    
    print("\n4. Creating MediaLibraryWidget...")
    widget = MediaLibraryWidget(mock_plugin)
    print("   ✓ Widget created")
    
    print("\n5. Checking if card view exists...")
    if hasattr(widget, 'card_view'):
        print("   ✓ card_view attribute exists")
    else:
        print("   ✗ card_view attribute MISSING!")
    
    print("\n6. Checking if view_stack exists...")
    if hasattr(widget, 'view_stack'):
        print("   ✓ view_stack attribute exists")
    else:
        print("   ✗ view_stack attribute MISSING!")
    
    print("\n7. Checking if view_mode_button exists...")
    if hasattr(widget, 'view_mode_button'):
        print("   ✓ view_mode_button attribute exists")
    else:
        print("   ✗ view_mode_button attribute MISSING!")
    
    print("\n8. Checking if _toggle_view_mode method exists...")
    if hasattr(widget, '_toggle_view_mode'):
        print("   ✓ _toggle_view_mode method exists")
    else:
        print("   ✗ _toggle_view_mode method MISSING!")
    
    print("\n9. Checking if _update_card_view method exists...")
    if hasattr(widget, '_update_card_view'):
        print("   ✓ _update_card_view method exists")
    else:
        print("   ✗ _update_card_view method MISSING!")
    
    print("\n10. Checking if _on_card_clicked method exists...")
    if hasattr(widget, '_on_card_clicked'):
        print("   ✓ _on_card_clicked method exists")
    else:
        print("   ✗ _on_card_clicked method MISSING!")
    
    print("\n11. Showing widget...")
    widget.resize(1200, 800)
    widget.show()
    print("   ✓ Widget shown")
    
    print("\n✅ Plugin loaded successfully!")
    print("   Check the UI - you should see a '🔲 Karten' button in the Browse tab.")
    print("   Close the window to exit.")
    
    sys.exit(app.exec())
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
