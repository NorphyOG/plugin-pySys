"""
Fix for the table_view.py file in the media library enhanced module
"""
import os
from pathlib import Path

def fix_table_view_py():
    file_path = Path("src/mmst/plugins/media_library/enhanced/table_view.py")
    
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return False
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check if _apply_sort method is missing
    if "_apply_sort" not in content:
        # Add _apply_sort method
        sort_method = """
    def _apply_sort(self) -> None:
        \"\"\"Apply current sort criteria to the filtered entries.\"\"\"
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
"""
        
        # Find the location to insert (after _apply_filters method)
        insert_pos = content.find("def _apply_filters")
        if insert_pos == -1:
            # If _apply_filters is not found, insert after reload method
            insert_pos = content.find("def reload")
        
        if insert_pos != -1:
            # Find the end of the method
            method_end = content.find("def ", insert_pos + 10)
            if method_end != -1:
                # Insert our new method after the current method
                modified_content = content[:method_end] + sort_method + content[method_end:]
                
                # Write the modified file
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(modified_content)
                    
                print(f"Added _apply_sort method to {file_path}")
                return True
    
    print("No changes made to table_view.py")
    return False

if __name__ == "__main__":
    fix_table_view_py()