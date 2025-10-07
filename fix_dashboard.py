import re
import os
from pathlib import Path

def fix_dashboard_py():
    path = Path("src/mmst/plugins/media_library/enhanced/dashboard.py")
    if not path.exists():
        print(f"Cannot find {path}")
        return False
        
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Add aliases to map _QtQXXX to QXX
    fixed_content = re.sub(
        r'_QtQWidget = object  # type: ignore\s+_QtQVBoxLayout = _QtQHBoxLayout = _QtQLabel = _QtQPushButton = _QtQScrollArea = _QtQFrame = _QtQListWidget = _QtQListWidgetItem = object  # type: ignore\s+Qt = object\(\)  # type: ignore',
        '_QtQWidget = object  # type: ignore\n    _QtQVBoxLayout = _QtQHBoxLayout = _QtQLabel = _QtQPushButton = _QtQScrollArea = _QtQFrame = _QtQListWidget = _QtQListWidgetItem = object  # type: ignore\n    Qt = object()  # type: ignore\n    # Provide aliases for use in the class\n    QWidget, QVBoxLayout, QHBoxLayout = _QtQWidget, _QtQVBoxLayout, _QtQHBoxLayout\n    QLabel, QPushButton, QScrollArea = _QtQLabel, _QtQPushButton, _QtQScrollArea\n    QFrame, QListWidget, QListWidgetItem = _QtQFrame, _QtQListWidget, _QtQListWidgetItem',
        content
    )
    
    # And also add the aliases in the try block
    fixed_content = re.sub(
        r'from PySide6.QtCore import Qt  # type: ignore',
        'from PySide6.QtCore import Qt  # type: ignore\n    # Create aliases for easier usage\n    QWidget, QVBoxLayout, QHBoxLayout = _QtQWidget, _QtQVBoxLayout, _QtQHBoxLayout\n    QLabel, QPushButton, QScrollArea = _QtQLabel, _QtQPushButton, _QtQScrollArea\n    QFrame, QListWidget, QListWidgetItem = _QtQFrame, _QtQListWidget, _QtQListWidgetItem',
        fixed_content
    )
    
    if content == fixed_content:
        print("No changes made to dashboard.py")
        return False
        
    with open(path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print("Updated dashboard.py successfully")
    return True

if __name__ == "__main__":
    os.chdir(Path(__file__).parent)  # Make sure we're in the right directory
    fix_dashboard_py()