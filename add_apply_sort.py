"""
This script adds the missing _apply_sort method to table_view.py
"""
import os
from pathlib import Path

def fix_table_view():
    file_path = Path("src/mmst/plugins/media_library/enhanced/table_view.py")
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Add _apply_sort method implementation before _rebuild method
    search_string = "    def _rebuild(self) -> None:"
    sort_method = '''
    def _apply_sort(self) -> None:
        try:
            if not self._filtered:
                return
                
            if self._sort_key == "recent":
                # Sort by modification time (newest first)
                self._filtered.sort(key=lambda x: getattr(x[0], 'mtime', 0) or 0, reverse=True)
            elif self._sort_key == "name":
                # Sort by filename
                self._filtered.sort(key=lambda x: Path(getattr(x[0], 'path', '')).name.lower())
            elif self._sort_key == "rating":
                # Sort by rating (highest first)
                self._filtered.sort(key=lambda x: getattr(x[0], 'rating', 0) or 0, reverse=True)
        except Exception:
            # Fallback - do nothing on sort error
            pass

    '''
    
    if search_string in content:
        new_content = content.replace(search_string, sort_method + search_string)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Added _apply_sort method to {file_path}")
    else:
        print(f"Could not find insertion point in {file_path}")

# Run the fix
fix_table_view()
print("Now try running the app with enhanced mode enabled")