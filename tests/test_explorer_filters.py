import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from pathlib import Path

# Skip all tests if PySide6 is not installed
pytest.importorskip("PySide6")

# Create a simple test for FilterCriteria
class TestFilterCriteria:
    def test_file_type_filtering(self):
        """Test filtering by file type."""
        from mmst.plugins.explorer.filter_panel import FilterCriteria
        
        # Create criteria for documents
        criteria = FilterCriteria()
        criteria.file_type = FilterCriteria.FILE_TYPE_DOCUMENTS
        
        # Check if PDF file matches
        pdf_path = Path("test.pdf")
        assert criteria._matches_type(pdf_path)
        
        # Check if image file does not match
        img_path = Path("test.jpg")
        assert not criteria._matches_type(img_path)
        
        # Test custom extensions
        criteria.file_type = "custom"
        criteria.custom_extensions = [".jpg", ".png"]
        assert criteria._matches_type(img_path)
        assert not criteria._matches_type(pdf_path)
    
    def test_file_size_filtering(self):
        """Test filtering by file size."""
        from mmst.plugins.explorer.filter_panel import FilterCriteria
        
        # Create criteria for files larger than 1MB
        criteria = FilterCriteria()
        criteria.size_mode = FilterCriteria.SIZE_MODE_LARGER
        criteria.min_size_bytes = 1024 * 1024  # 1MB
        
        # Check if 2MB file matches
        assert criteria._matches_size(2 * 1024 * 1024)
        
        # Check if 500KB file does not match
        assert not criteria._matches_size(500 * 1024)
        
        # Test between mode
        criteria.size_mode = FilterCriteria.SIZE_MODE_BETWEEN
        criteria.min_size_bytes = 1024 * 1024  # 1MB
        criteria.max_size_bytes = 5 * 1024 * 1024  # 5MB
        
        # Check if 3MB file matches
        assert criteria._matches_size(3 * 1024 * 1024)
        
        # Check if 10MB file does not match
        assert not criteria._matches_size(10 * 1024 * 1024)
    
    def test_date_filtering(self):
        """Test filtering by date."""
        from mmst.plugins.explorer.filter_panel import FilterCriteria
        
        # Create criteria for files newer than a week
        criteria = FilterCriteria()
        criteria.date_mode = FilterCriteria.DATE_MODE_NEWER
        criteria.date_min = datetime.now() - timedelta(days=7)
        
        # Check if today's file matches
        file_stats = {
            "modified": datetime.now()
        }
        assert criteria._matches_date(file_stats)
        
        # Check if older file does not match
        file_stats = {
            "modified": datetime.now() - timedelta(days=30)
        }
        assert not criteria._matches_date(file_stats)
        
        # Test today filter
        criteria.date_mode = FilterCriteria.DATE_MODE_TODAY
        
        # Today's file should match
        file_stats = {
            "modified": datetime.now()
        }
        assert criteria._matches_date(file_stats)
        
        # Yesterday's file should not match
        file_stats = {
            "modified": datetime.now() - timedelta(days=1)
        }
        assert not criteria._matches_date(file_stats)

# Test FuzzyFilterProxyModel with mock objects
@pytest.fixture
def mock_filter_criteria():
    from mmst.plugins.explorer.filter_panel import FilterCriteria
    return FilterCriteria()

@pytest.fixture
def mock_model():
    model = MagicMock()
    model.filePath.return_value = "/test/path/file.txt"
    model.fileName.return_value = "file.txt"
    model.isDir.return_value = False
    return model

@pytest.fixture
def mock_fs_manager():
    fs_manager = MagicMock()
    fs_manager.get_file_size.return_value = 1024  # 1KB
    fs_manager.get_file_times.return_value = {
        "modified": datetime.now(),
        "created": datetime.now() - timedelta(days=1),
        "accessed": datetime.now() - timedelta(hours=1)
    }
    return fs_manager

class TestFuzzyFilterProxyModel:
    def test_text_filtering(self):
        """Test text-based filtering."""
        from mmst.plugins.explorer.widgets import FuzzyFilterProxyModel
        
        # Create model and proxy
        model = MagicMock()
        model.fileName.return_value = "testfile.txt"
        
        proxy = FuzzyFilterProxyModel()
        proxy.sourceModel = MagicMock(return_value=model)
        
        # Test with matching pattern
        proxy.set_search_pattern("test")
        assert proxy._matches_text_filter(model, MagicMock())
        
        # Test with non-matching pattern
        proxy.set_search_pattern("xyz")
        assert not proxy._matches_text_filter(model, MagicMock())
    
    def test_advanced_filtering(self, mock_filter_criteria, mock_fs_manager):
        """Test advanced filtering."""
        from mmst.plugins.explorer.widgets import FuzzyFilterProxyModel
        from mmst.plugins.explorer.filter_panel import FilterCriteria
        
        # Create proxy
        proxy = FuzzyFilterProxyModel()
        proxy.set_filesystem_manager(mock_fs_manager)
        
        # Configure criteria for text files larger than 500 bytes
        criteria = mock_filter_criteria
        criteria.file_type = FilterCriteria.FILE_TYPE_DOCUMENTS
        criteria.size_mode = FilterCriteria.SIZE_MODE_LARGER
        criteria.min_size_bytes = 500
        
        # Set criteria and check filtering
        proxy.set_filter_criteria(criteria)
        
        # Test with Path that should match
        path = Path("/test/file.txt")
        mock_fs_manager.get_file_size.return_value = 1024  # 1KB
        
        # The file should match
        assert proxy._matches_advanced_filter(path)
        
        # Test with Path that should not match (too small)
        mock_fs_manager.get_file_size.return_value = 100  # 100B
        assert not proxy._matches_advanced_filter(path)

# Test the FilterPanel UI integration
@pytest.fixture
def filter_panel():
    from mmst.plugins.explorer.filter_panel import FilterPanel
    return FilterPanel()

class TestFilterPanel:
    def test_filter_panel_initialization(self, filter_panel):
        """Test filter panel initialization."""
        # Check if filter criteria is created
        assert hasattr(filter_panel, "criteria")
        
        # Check default values
        from mmst.plugins.explorer.filter_panel import FilterCriteria
        assert filter_panel.criteria.file_type == FilterCriteria.FILE_TYPE_ALL
        assert filter_panel.criteria.size_mode == FilterCriteria.SIZE_MODE_ANY
        assert filter_panel.criteria.date_mode == FilterCriteria.DATE_MODE_ANY
    
    @pytest.mark.skipif(sys.platform != "win32", reason="GUI test only on Windows")
    def test_filter_panel_ui_interactions(self, filter_panel):
        """Test filter panel UI interactions."""
        # Type filter change
        if hasattr(filter_panel, "_type_combo") and hasattr(filter_panel._type_combo, "setCurrentIndex"):
            filter_panel._type_combo.setCurrentIndex(1)  # Documents
            assert filter_panel.criteria.file_type == FilterCriteria.FILE_TYPE_DOCUMENTS
        
        # Size filter change
        if hasattr(filter_panel, "_size_mode_combo") and hasattr(filter_panel._size_mode_combo, "setCurrentIndex"):
            filter_panel._size_mode_combo.setCurrentIndex(1)  # Larger than
            assert filter_panel.criteria.size_mode == FilterCriteria.SIZE_MODE_LARGER
        
        # Date filter change
        if hasattr(filter_panel, "_date_mode_combo") and hasattr(filter_panel._date_mode_combo, "setCurrentIndex"):
            filter_panel._date_mode_combo.setCurrentIndex(4)  # Today
            assert filter_panel.criteria.date_mode == FilterCriteria.DATE_MODE_TODAY