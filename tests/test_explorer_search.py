"""Tests for the Explorer search functionality."""
import logging
import os
from pathlib import Path
import pytest
import tempfile
import shutil
from unittest.mock import MagicMock, patch

# Skip if PySide6 not available
pytest.importorskip("PySide6")

from mmst.plugins.explorer.search_engine import SearchEngine, SearchMode, SearchResult, SearchMatch


class TestSearchEngine:
    """Test the search engine for the Explorer plugin."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files with content
            files = {
                "test1.txt": "This is a test file with some content.\nLine 2 has additional content.",
                "test2.txt": "Another file with different content.\nThis line mentions test keyword.",
                "test3.py": "def test_function():\n    # This is a test comment\n    print('test')\n    return True",
                "binary.exe": b"\x7F\x45\x4C\x46\x01\x01\x01\x00"  # Mock binary file
            }
            
            for name, content in files.items():
                path = Path(temp_dir) / name
                if isinstance(content, bytes):
                    with open(path, 'wb') as f:
                        f.write(content)
                else:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
            # Create a subdirectory with a nested file
            nested_dir = Path(temp_dir) / "subdir"
            nested_dir.mkdir()
            with open(nested_dir / "nested.txt", 'w', encoding='utf-8') as f:
                f.write("This is a nested file with test content.")
                
            yield Path(temp_dir)
    
    def test_search_plain_text(self, temp_dir):
        """Test basic plain text search functionality."""
        engine = SearchEngine()
        
        # Search for a term that should be found in multiple files
        results = engine.search_directory(temp_dir, "test", SearchMode.PLAIN_TEXT)
        
        # Verify we found matches in the expected files
        assert len(results) >= 3  # Should find in at least 3 files
        
        # Verify file paths are correct
        result_paths = [result.file_path.name for result in results]
        assert "test1.txt" in result_paths
        assert "test2.txt" in result_paths
        assert "test3.py" in result_paths
        
        # Verify we have the correct number of matches in a specific file
        test1_result = next(r for r in results if r.file_path.name == "test1.txt")
        assert len(test1_result.matches) == 1  # Should find "test" once in test1.txt
    
    def test_search_case_sensitive(self, temp_dir):
        """Test case-sensitive search."""
        engine = SearchEngine()
        
        # Search for "Test" with case sensitivity
        results = engine.search_directory(temp_dir, "Test", SearchMode.CASE_SENSITIVE)
        
        # Should only find matches with proper case
        result_paths = [result.file_path.name for result in results]
        assert "test1.txt" in result_paths  # Contains "This is a Test file"
        assert "test2.txt" not in result_paths  # Contains "test" lowercase only
    
    def test_search_regex(self, temp_dir):
        """Test regex search functionality."""
        engine = SearchEngine()
        
        # Search for pattern that matches function definition
        results = engine.search_directory(temp_dir, r"def\s+\w+\(\)", SearchMode.REGEX)
        
        # Should only find matches in the Python file
        assert len(results) == 1
        assert results[0].file_path.name == "test3.py"
        
        # Verify we found the function definition
        match = results[0].matches[0]
        assert "def test_function()" in match.line_text
    
    def test_binary_file_detection(self, temp_dir):
        """Test that binary files are properly excluded from search."""
        engine = SearchEngine()
        
        # Search for a generic term that might be found in binary by accident
        results = engine.search_directory(temp_dir, "ELF", SearchMode.PLAIN_TEXT)
        
        # Should not find matches in binary.exe
        result_paths = [result.file_path.name for result in results]
        assert "binary.exe" not in result_paths
    
    def test_recursive_search(self, temp_dir):
        """Test that search finds files in subdirectories."""
        engine = SearchEngine()
        
        # Search for term in nested file
        results = engine.search_directory(temp_dir, "nested", SearchMode.PLAIN_TEXT)
        
        # Should find the nested file
        assert len(results) == 1
        assert results[0].file_path.name == "nested.txt"
        assert "subdir" in str(results[0].file_path)
    
    def test_context_lines(self, temp_dir):
        """Test getting context lines around a match."""
        engine = SearchEngine()
        
        # First find the match in a specific file
        results = engine.search_directory(temp_dir, "Line 2", SearchMode.PLAIN_TEXT)
        assert len(results) == 1
        match = results[0].matches[0]
        
        # Get context lines (2 before and 2 after)
        context = engine.get_context_lines(results[0].file_path, match.line_number, 2)
        
        # Should get at least the match line and possibly before/after lines
        assert len(context) >= 1
        assert any("Line 2" in line for _, line in context)


# Add more test classes for SearchPanel if needed
class TestSearchPanel:
    """Test the search panel UI functionality."""
    # These tests would require Qt test framework and would be more integration-focused
    pass