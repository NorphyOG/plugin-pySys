"""
Fix for the table_view.py file in the enhanced media library module
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
    
    # Add _apply_sort method right after _apply_filters method
    if "_apply_filters" in content and "_apply_sort" not in content:
        # Find the end of the _apply_filters method
        apply_filters_end = content.find("    def _rebuild", content.find("def _apply_filters"))
        
        if apply_filters_end > 0:
            # Create the _apply_sort method
            sort_method = """    def _apply_sort(self) -> None:
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
            
            # Insert the sort method
            new_content = content[:apply_filters_end] + sort_method + content[apply_filters_end:]
            
            # Write the modified content
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
                
            print(f"Added _apply_sort method to {file_path}")
            return True
    
    print("No changes needed or could not find insertion point in table_view.py")
    return False

# Run the fix
if fix_table_view_py():
    print("\nNow try running the app with enhanced mode enabled:")
    print("$env:MMST_MEDIA_LIBRARY_ENHANCED=\"1\"; python -m mmst.core.app")