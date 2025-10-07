import sys
from pathlib import Path
import time
import pytest

from mmst.plugins.system_tools.temp_cleaner import TempCleaner

def test_temp_cleaner_directory_handling(tmp_path: Path):
    # Create a more complex structure with nested directories
    root_dir = tmp_path / "temp_root"
    root_dir.mkdir()
    
    # Create some nested directories
    dir1 = root_dir / "dir1"
    dir1.mkdir()
    dir2 = root_dir / "dir2"
    dir2.mkdir()
    nested_dir = dir1 / "nested"
    nested_dir.mkdir()
    deep_nested = nested_dir / "deep"
    deep_nested.mkdir()
    
    # Create files in various directories
    files = []
    # Root level files
    for i in range(2):
        p = root_dir / f"root_file{i}.txt"
        p.write_text(f"root file {i}")
        files.append(p)
    
    # Files in dir1
    for i in range(2):
        p = dir1 / f"dir1_file{i}.txt"
        p.write_text(f"dir1 file {i}")
        files.append(p)
    
    # Files in nested directory
    for i in range(1):
        p = nested_dir / f"nested_file{i}.txt"
        p.write_text(f"nested file {i}")
        files.append(p)
    
    # Files in deep nested directory
    for i in range(1):
        p = deep_nested / f"deep_file{i}.txt"
        p.write_text(f"deep file {i}")
        files.append(p)
        
    # Create a cleaner with our test directory as the only category
    cleaner = TempCleaner(extra_categories={"test_dirs": ("Test Directories", [root_dir])})
    
    # Run scan
    result = cleaner.scan(selected_categories=["test_dirs"])
    
    # Verify scan found all files and directories
    assert "test_dirs" in result.categories
    cat_res = result.categories["test_dirs"]
    
    # Count files and directories in our structure
    expected_file_count = len(files)
    expected_dir_count = 4  # dir1, dir2, nested, deep_nested
    
    # Count actual files and directories in the scan result
    actual_file_count = sum(1 for entry in cat_res.files if not entry.is_directory)
    actual_dir_count = sum(1 for entry in cat_res.files if entry.is_directory)
    
    # Check counts
    assert actual_file_count == expected_file_count, "Should find all files"
    assert actual_dir_count == expected_dir_count, "Should find all directories"
    
    # Test dry run delete
    report = cleaner.delete(result, dry_run=True, categories=["test_dirs"])
    
    # Check that both files and dirs are tracked
    assert "files" in report["test_dirs"]
    assert "dirs" in report["test_dirs"]
    assert report["test_dirs"]["files"] == expected_file_count
    assert report["test_dirs"]["dirs"] == expected_dir_count
    assert "deleted_files" in report["test_dirs"]
    assert "deleted_dirs" in report["test_dirs"]
    
    # Verify all files and directories still exist after dry run
    for f in files:
        assert f.exists()
    assert dir1.exists()
    assert dir2.exists()
    assert nested_dir.exists()
    assert deep_nested.exists()
    
    # Test real delete
    report = cleaner.delete(result, dry_run=False, categories=["test_dirs"])
    
    # Verify all files are gone
    for f in files:
        assert not f.exists(), f"File should be deleted: {f}"
    
    # Verify directories are gone (they should be deleted in the right order - deepest first)
    assert not deep_nested.exists()
    assert not nested_dir.exists()
    assert not dir1.exists()
    assert not dir2.exists()
    
    # Check counts in the report
    assert report["test_dirs"]["files"] == expected_file_count
    assert report["test_dirs"]["dirs"] == expected_dir_count
    assert len(report["test_dirs"]["deleted_files"]) == expected_file_count
    assert len(report["test_dirs"]["deleted_dirs"]) == expected_dir_count