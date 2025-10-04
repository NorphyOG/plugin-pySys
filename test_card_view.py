"""Test script to verify card view functionality."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    print("1. Testing media_card_view import...")
    from mmst.plugins.media_library.media_card_view import DualView, MediaCardData, MediaCard
    print("   ✓ Import successful")
    
    print("\n2. Testing MediaCardData creation...")
    data = MediaCardData(
        path=Path("test.mp3"),
        title="Test Song",
        subtitle="Test Artist",
        kind="audio",
        rating=4,
        duration=180
    )
    print(f"   ✓ Created: {data.title}")
    
    print("\n3. Testing PySide6 imports...")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    print("   ✓ PySide6 imports OK")
    
    print("\n4. Creating QApplication...")
    app = QApplication.instance() or QApplication(sys.argv)
    print("   ✓ QApplication created")
    
    print("\n5. Creating DualView widget...")
    view = DualView()
    print("   ✓ DualView created")
    
    print("\n6. Setting test data...")
    test_items = [
        MediaCardData(Path("test1.mp3"), "Song 1", "Artist 1", "audio", 5, 200),
        MediaCardData(Path("test2.mp4"), "Video 1", "1920x1080", "video", 4, 3600),
        MediaCardData(Path("test3.jpg"), "Photo 1", "", "image", 3, 0),
    ]
    view.set_media_items(test_items)
    print("   ✓ Test data set")
    
    print("\n7. Showing widget...")
    view.resize(800, 600)
    view.show()
    print("   ✓ Widget shown")
    
    print("\n✅ All tests passed! Card view is working.")
    print("   Close the window to exit.")
    
    sys.exit(app.exec())
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
