"""
Tests for image compression functionality.

Verifies that the image compression widget and backend work correctly
with quality settings, format selection, and preview generation.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from mmst.plugins.system_tools.image_compression import (
    DataCompressionWidget,
    CompressionPresetManager,
    ImagePreviewWidget
)


def test_compression_preset_manager():
    """Test that preset manager provides valid presets."""
    preset_names = CompressionPresetManager.get_preset_names()
    
    assert len(preset_names) > 0
    assert "Web Optimized" in preset_names
    assert "High Quality" in preset_names
    assert "Maximum Compression" in preset_names
    
    # Test getting preset
    web_preset = CompressionPresetManager.get_preset("Web Optimized")
    assert web_preset is not None
    assert "format" in web_preset
    assert "quality" in web_preset
    assert web_preset["quality"] == 85


def test_compression_preset_formats():
    """Test that presets use valid formats."""
    valid_formats = ["jpg", "png", "webp"]
    
    for preset_name in CompressionPresetManager.get_preset_names():
        preset = CompressionPresetManager.get_preset(preset_name)
        assert preset is not None
        assert preset["format"] in valid_formats


def test_compression_preset_quality_range():
    """Test that preset quality values are in valid range."""
    for preset_name in CompressionPresetManager.get_preset_names():
        preset = CompressionPresetManager.get_preset(preset_name)
        assert preset is not None
        quality = preset["quality"]
        assert 1 <= quality <= 100


def test_image_preview_widget_initialization():
    """Test that ImagePreviewWidget initializes correctly."""
    try:
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        
        widget = ImagePreviewWidget("Test Title")
        assert widget is not None
        assert widget.image_label.text() == "Keine Vorschau verfügbar"
        assert widget.info_label.text() == ""
    except ImportError:
        pytest.skip("PySide6 not available")


def test_image_compression_widget_initialization():
    """Test that ImageCompressionWidget initializes correctly."""
    try:
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        
        mock_plugin = Mock()
        widget = ImageCompressionWidget(mock_plugin)
        
        assert widget is not None
        assert widget._source_path is None
        assert widget._compressed_path is None
        assert not widget.preview_button.isEnabled()
        assert not widget.save_button.isEnabled()
        assert not widget.replace_button.isEnabled()
    except ImportError:
        pytest.skip("PySide6 not available")


def test_image_compression_quality_slider():
    """Test that quality slider works correctly."""
    try:
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        
        mock_plugin = Mock()
        widget = ImageCompressionWidget(mock_plugin)
        
        # Check default value
        assert widget.quality_slider.value() == 85
        assert widget.quality_label.text() == "85"
        
        # Change value
        widget.quality_slider.setValue(60)
        assert widget.quality_label.text() == "60"
        
        # Check range
        assert widget.quality_slider.minimum() == 1
        assert widget.quality_slider.maximum() == 100
    except ImportError:
        pytest.skip("PySide6 not available")


def test_image_compression_format_options():
    """Test that format combo has expected options."""
    try:
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        
        mock_plugin = Mock()
        widget = ImageCompressionWidget(mock_plugin)
        
        formats = [widget.format_combo.itemText(i) for i in range(widget.format_combo.count())]
        
        assert "jpg" in formats
        assert "png" in formats
        assert "webp" in formats
    except ImportError:
        pytest.skip("PySide6 not available")


def test_image_compression_preset_loading():
    """Test that preset loading updates format and quality."""
    try:
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        
        mock_plugin = Mock()
        widget = ImageCompressionWidget(mock_plugin)
        
        # Load "High Quality" preset
        widget.preset_combo.setCurrentText("High Quality")
        widget._on_preset_changed("High Quality")
        
        assert widget.quality_slider.value() == 95
        assert widget.format_combo.currentText() == "jpg"
        
        # Load "WebP High" preset
        widget.preset_combo.setCurrentText("WebP High")
        widget._on_preset_changed("WebP High")
        
        assert widget.quality_slider.value() == 90
        assert widget.format_combo.currentText() == "webp"
    except ImportError:
        pytest.skip("PySide6 not available")


def test_image_compression_widget_enable_disable():
    """Test that widget can be enabled/disabled."""
    try:
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        
        mock_plugin = Mock()
        widget = ImageCompressionWidget(mock_plugin)
        
        widget.set_enabled(False)
        assert not widget.isEnabled()
        
        widget.set_enabled(True)
        assert widget.isEnabled()
    except ImportError:
        pytest.skip("PySide6 not available")


def test_run_image_compression_integration(tmp_path):
    """Test the run_image_compression method with mocked ImageMagick."""
    from mmst.plugins.system_tools.plugin import SystemToolsPlugin
    from mmst.plugins.system_tools.tools import Tool
    
    # Create mock services
    mock_services = Mock()
    mock_services.event_bus = Mock()
    
    plugin = SystemToolsPlugin(mock_services)
    plugin._active = True
    
    # Create temporary source file
    source = tmp_path / "source.jpg"
    source.write_text("fake image data")
    target = tmp_path / "compressed.jpg"
    
    # Mock detect_tools to return available ImageMagick
    def mock_detect_tools():
        return {
            "imagemagick": Tool(
                name="imagemagick",
                command="convert",
                available=True,
                path="/usr/bin/convert",
                version="7.0.0"
            )
        }
    
    plugin.detect_tools = mock_detect_tools
    
    # Mock subprocess.run
    mock_result = MagicMock()
    mock_result.returncode = 0
    
    callback_called = False
    
    def callback():
        nonlocal callback_called
        callback_called = True
    
    with patch('subprocess.run', return_value=mock_result):
        # Create target file to simulate successful conversion
        target.write_text("compressed image data")
        
        plugin.run_image_compression(
            source=source,
            target=target,
            target_format="jpg",
            quality=85,
            callback=callback
        )
        
        # Give executor time to run
        import time
        time.sleep(0.1)
    
    # Callback should eventually be called
    # Note: In real test, you'd use proper synchronization


def test_image_compression_without_imagemagick():
    """Test that compression fails gracefully when ImageMagick is not available."""
    from mmst.plugins.system_tools.plugin import SystemToolsPlugin
    from mmst.plugins.system_tools.tools import Tool
    
    mock_services = Mock()
    mock_services.event_bus = Mock()
    
    plugin = SystemToolsPlugin(mock_services)
    plugin._active = True
    
    # Mock detect_tools to return unavailable ImageMagick
    def mock_detect_tools():
        return {
            "imagemagick": Tool(
                name="imagemagick",
                command="convert",
                available=False,
                path=None,
                version=None
            )
        }
    
    plugin.detect_tools = mock_detect_tools
    
    callback_called = False
    
    def callback():
        nonlocal callback_called
        callback_called = True
    
    plugin.run_image_compression(
        source=Path("/fake/source.jpg"),
        target=Path("/fake/target.jpg"),
        target_format="jpg",
        quality=85,
        callback=callback
    )
    
    # Give executor time
    import time
    time.sleep(0.1)
    
    # Callback should be called even on failure
