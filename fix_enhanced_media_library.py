"""
Comprehensive script to fix Qt class references in the media library enhanced module
"""
import os
from pathlib import Path

def fix_dashboard_py():
    dashboard_path = Path("src/mmst/plugins/media_library/enhanced/dashboard.py")
    if not dashboard_path.exists():
        print(f"File not found: {dashboard_path}")
        return False
        
    with open(dashboard_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Add aliases for Qt classes
    replacements = [
        ("root = QVBoxLayout(self)", "root = _QtQVBoxLayout(self)"),
        ("header = QHBoxLayout()", "header = _QtQHBoxLayout()"),
        ("self._title = QLabel(", "self._title = _QtQLabel("),
        ("self.refresh_button = QPushButton(", "self.refresh_button = _QtQPushButton("),
        ("scroll = QScrollArea()", "scroll = _QtQScrollArea()"),
        ("container = QFrame()", "container = _QtQFrame()"),
        ("self._body_layout = QVBoxLayout(", "self._body_layout = _QtQVBoxLayout("),
        ("lbl = QLabel(", "lbl = _QtQLabel("),
        ("list_widget = QListWidget()", "list_widget = _QtQListWidget()"),
        ("list_item = QListWidgetItem(", "list_item = _QtQListWidgetItem("),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
        
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Fixed {dashboard_path}")
    return True

def fix_base_py():
    base_path = Path("src/mmst/plugins/media_library/enhanced/base.py")
    if not base_path.exists():
        print(f"File not found: {base_path}")
        return False
        
    with open(base_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Fix imports and class references in the base.py file
    replacements = [
        ("container = QVBoxLayout()", "container = QVBoxLayout()" if "QVBoxLayout" in content and "import QVBoxLayout" in content else "container = QtWidgetBase()"),
        ("self._view_mode_combo = QComboBox()", "self._view_mode_combo = QComboBox()" if "QComboBox" in content and "import QComboBox" in content else "self._view_mode_combo = QtWidgetBase()"),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
        
    with open(base_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Fixed {base_path}")
    return True

# Fix the files
dashboard_fixed = fix_dashboard_py()
base_fixed = fix_base_py()

if dashboard_fixed or base_fixed:
    print("\nUpdated enhanced media library files. Attempting to run MMST app...")
    
    # Set environment variables
    os.environ["MMST_DEBUG"] = "1"
    os.environ["MMST_MEDIA_LIBRARY_ENHANCED"] = "1"
    
    # Run the app
    try:
        from mmst.core.app import main
        main()
    except Exception as e:
        import traceback
        print(f"Error running MMST app: {e}")
        traceback.print_exc()
else:
    print("No files were fixed.")