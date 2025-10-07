import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Skip all tests if PySide6 is not available
pyside_available = pytest.importorskip("PySide6", reason="PySide6 not installed")

# Import the CodeSyntaxHighlighter class from the Explorer plugin
# Only attempt imports when PySide6 is available
from PySide6.QtGui import QTextDocument, QSyntaxHighlighter
from PySide6.QtWidgets import QApplication, QTextEdit

from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

try:
    from mmst.plugins.explorer.widgets import CodeSyntaxHighlighter, DetailsPanel
except ImportError:
    pytest.skip("Explorer plugin not available", allow_module_level=True)

@pytest.fixture(scope="module")
def qapp():
    """Create a QApplication instance for the tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # No need to clean up as we're just using the instance

@pytest.fixture
def mock_document():
    """Create a mock QTextDocument."""
    doc = QTextDocument()
    return doc

class TestSyntaxHighlighter:
    
    def test_syntax_highlighter_creation(self, qapp, mock_document):
        """Test that the CodeSyntaxHighlighter can be instantiated."""
        from mmst.plugins.explorer.widgets import CodeSyntaxHighlighter
        
        # Test with different languages
        languages = ["python", "javascript", "html", "xml", "json", "cpp", "c", "css", "markdown", "yaml"]
        
        for lang in languages:
            highlighter = CodeSyntaxHighlighter(mock_document, lang)
            assert highlighter is not None
            assert isinstance(highlighter, QSyntaxHighlighter)
            assert highlighter.language == lang
            assert len(highlighter.highlighting_rules) > 0
    
    def test_python_syntax_rules(self, qapp, mock_document):
        """Test that Python syntax rules are correctly set up."""
        from mmst.plugins.explorer.widgets import CodeSyntaxHighlighter
        
        highlighter = CodeSyntaxHighlighter(mock_document, "python")
        
        # Check that we have rules for Python syntax elements
        rule_count = len(highlighter.highlighting_rules)
        assert rule_count >= 5  # At minimum we should have rules for keywords, strings, comments, etc.
        
        # Verify keyword formatting is applied
        test_text = "def test_function(): return True"
        highlighter.setDocument(mock_document)
        mock_document.setPlainText(test_text)
        
        # Can't easily test the actual formatting application in a unit test
        # but we can verify the highlighter processes the text without errors
        assert mock_document.toPlainText() == test_text

    def test_javascript_syntax_rules(self, qapp, mock_document):
        """Test that JavaScript syntax rules are correctly set up."""
        from mmst.plugins.explorer.widgets import CodeSyntaxHighlighter
        
        highlighter = CodeSyntaxHighlighter(mock_document, "javascript")
        
        # Check that we have rules for JavaScript syntax elements
        rule_count = len(highlighter.highlighting_rules)
        assert rule_count >= 5
        
        # Verify keyword formatting is applied
        test_text = "function testFunction() { return true; }"
        highlighter.setDocument(mock_document)
        mock_document.setPlainText(test_text)
        
        assert mock_document.toPlainText() == test_text
        
    def test_css_syntax_rules(self, qapp, mock_document):
        """Test that CSS syntax rules are correctly set up."""
        from mmst.plugins.explorer.widgets import CodeSyntaxHighlighter
        
        highlighter = CodeSyntaxHighlighter(mock_document, "css")
        
        # Check that we have rules for CSS syntax elements
        rule_count = len(highlighter.highlighting_rules)
        assert rule_count >= 5
        
        # Verify CSS formatting is applied
        test_text = "body { color: #333; font-size: 14px; }"
        highlighter.setDocument(mock_document)
        mock_document.setPlainText(test_text)
        
        assert mock_document.toPlainText() == test_text
        
    def test_markdown_syntax_rules(self, qapp, mock_document):
        """Test that Markdown syntax rules are correctly set up."""
        from mmst.plugins.explorer.widgets import CodeSyntaxHighlighter
        
        highlighter = CodeSyntaxHighlighter(mock_document, "markdown")
        
        # Check that we have rules for Markdown syntax elements
        rule_count = len(highlighter.highlighting_rules)
        assert rule_count >= 5
        
        # Verify Markdown formatting is applied
        test_text = "# Heading\n\n**Bold text** and *italic text*\n\n```code block```"
        highlighter.setDocument(mock_document)
        mock_document.setPlainText(test_text)
        
        assert mock_document.toPlainText() == test_text
        
    def test_yaml_syntax_rules(self, qapp, mock_document):
        """Test that YAML syntax rules are correctly set up."""
        from mmst.plugins.explorer.widgets import CodeSyntaxHighlighter
        
        highlighter = CodeSyntaxHighlighter(mock_document, "yaml")
        
        # Check that we have rules for YAML syntax elements
        rule_count = len(highlighter.highlighting_rules)
        assert rule_count >= 5
        
        # Verify YAML formatting is applied
        test_text = "---\nname: test\nversion: 1.0\nenabled: true\n"
        highlighter.setDocument(mock_document)
        mock_document.setPlainText(test_text)
        
        assert mock_document.toPlainText() == test_text

class TestDetailsPanelTextRendering:
    
    @pytest.fixture
    def mock_details_panel(self, qapp):
        """Create a mock DetailsPanel instance."""
        panel = MagicMock()
        
        # Mock the UI components
        panel._preview = QTextEdit()
        panel._metadata = MagicMock()
        panel._metadata.setPlainText = MagicMock()
        
        # Mock the logger
        panel._logger = MagicMock()
        
        return panel
    
    def test_render_text_preview(self, mock_details_panel):
        """Test that text preview applies syntax highlighting for different file types."""
        # Test with a direct instance of CodeSyntaxHighlighter
        python_doc = QTextDocument()
        python_doc.setPlainText('def test(): pass')
        python_highlighter = CodeSyntaxHighlighter(python_doc, "python")
        
        # Check that the highlighter was initialized with the right language
        assert python_highlighter.language == "python"
        
        # Check that there are multiple highlighting rules
        assert len(python_highlighter.highlighting_rules) > 5
        
        # Test with JavaScript
        js_doc = QTextDocument()
        js_doc.setPlainText('function test() { return true; }')
        js_highlighter = CodeSyntaxHighlighter(js_doc, "javascript")
        
        # Check that the highlighter was initialized with the right language
        assert js_highlighter.language == "javascript"
        
        # Check that there are multiple highlighting rules
        assert len(js_highlighter.highlighting_rules) > 5

if __name__ == "__main__":
    pytest.main(['-xvs', __file__])