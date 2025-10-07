"""
Script to fix QWidget references in dashboard.py
"""
import os
from pathlib import Path

# Path to the dashboard.py file
dashboard_path = Path("src/mmst/plugins/media_library/enhanced/dashboard.py")

# Read the file
with open(dashboard_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace class references
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

# Apply the replacements
for old, new in replacements:
    content = content.replace(old, new)

# Write the fixed file
with open(dashboard_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Fixed {dashboard_path}")

# Now run the app with enhanced mode enabled
os.environ["MMST_DEBUG"] = "1"
os.environ["MMST_MEDIA_LIBRARY_ENHANCED"] = "1"

print("\nStarting MMST app with debug and enhanced mode...")
from mmst.core.app import main
main()