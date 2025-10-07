from __future__ import annotations

"""Explorer plugin widgets.

This module implements the Explorer-inspired three-pane layout requested by
product design. It offers a quick-access sidebar, a breadcrumb-driven content
browser with grid/list/detail modes, rich metadata previews, fuzzy search, and
basic disk health summaries. The implementation is defensive: when PySide6 is
absent (for example during headless test runs) the module still imports by
falling back to ``typing.Any`` stubs so unit tests that do not touch the GUI can
proceed.

The code is organized following SOLID principles:
- Single Responsibility: UI components, filesystem operations, and configuration 
  are handled by separate classes
- Open/Closed: View rendering is extensible through the ViewFactory pattern
- Interface Segregation: Components communicate through focused interfaces
- Dependency Inversion: High-level components depend on abstractions
"""

# Import ViewFactory for creating different view types
try:
    from .view_factory import ViewFactory
except ImportError:
    # For type checking and headless operation
    class ViewFactory:
        @staticmethod
        def create_grid_view(*args, **kwargs):
            return None
            
        @staticmethod
        def create_list_view(*args, **kwargs):
            return None
            
        @staticmethod
        def create_details_view(*args, **kwargs):
            return None

# Import filter panel functionality
try:
    from .filter_panel import FilterPanel, FilterCriteria
except ImportError:
    # For type checking and headless operation
    FilterPanel = object
    FilterCriteria = object

# Import required modules for syntax highlighting
try:
    from PySide6.QtCore import QDate, Qt
    from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
    from PySide6.QtWidgets import QToolButton
    import re

    class CodeSyntaxHighlighter(QSyntaxHighlighter):
        """Syntax highlighter for code files."""
        
        def __init__(self, document, language="generic"):
            super().__init__(document)
            self.language = language.lower()
            self.highlighting_rules = []
            
            # Format for different syntax elements
            self.formats = {
                "keyword": self._create_format(QColor("#569CD6"), bold=True),  # blue keywords
                "class": self._create_format(QColor("#4EC9B0"), bold=True),    # teal class/types
                "function": self._create_format(QColor("#DCDCAA")),            # yellow functions
                "string": self._create_format(QColor("#CE9178")),              # orange strings
                "comment": self._create_format(QColor("#6A9955"), italic=True), # green comments
                "number": self._create_format(QColor("#B5CEA8")),              # light green numbers
                "operator": self._create_format(QColor("#D4D4D4")),            # gray operators
                "bracket": self._create_format(QColor("#D4D4D4")),             # gray brackets
                "decorator": self._create_format(QColor("#DCDCAA"))            # yellow decorators
            }
            
            # Initialize language rules
            self._initialize_rules()
        
        def _create_format(self, color, bold=False, italic=False):
            """Create a text format with the specified attributes."""
            text_format = QTextCharFormat()
            text_format.setForeground(color)
            if bold:
                text_format.setFontWeight(QFont.Weight.Bold)
            if italic:
                text_format.setFontItalic(True)
            return text_format
        
        def _initialize_rules(self):
            """Initialize the syntax highlighting rules for the selected language."""
            # Common patterns for multiple languages
            self.highlighting_rules.append((re.compile(r'\b\d+\b'), self.formats["number"]))  # Numbers
            self.highlighting_rules.append((re.compile(r'[\[\]{}()]'), self.formats["bracket"]))  # Brackets
            
            # Language-specific patterns
            if self.language == "python":
                # Python keywords
                keywords = [
                    'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
                    'def', 'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
                    'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'None',
                    'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True', 'try',
                    'while', 'with', 'yield'
                ]
                self.highlighting_rules.append(
                    (re.compile(r'\b(?:' + '|'.join(keywords) + r')\b'), self.formats["keyword"])
                )
                # Python class/function definitions
                self.highlighting_rules.append((re.compile(r'\bclass\s+(\w+)'), self.formats["class"]))
                self.highlighting_rules.append((re.compile(r'\bdef\s+(\w+)'), self.formats["function"]))
                # Python decorators
                self.highlighting_rules.append((re.compile(r'@\w+'), self.formats["decorator"]))
                # Python strings
                self.highlighting_rules.append((re.compile(r'[\'"].*?[\'"]'), self.formats["string"]))
                # Python comments
                self.highlighting_rules.append((re.compile(r'#.*'), self.formats["comment"]))
                # Python self/cls parameter
                self.highlighting_rules.append((re.compile(r'\b(?:self|cls)\b'), self.formats["keyword"]))
                
            elif self.language == "javascript" or self.language == "typescript":
                # JavaScript/TypeScript keywords
                keywords = [
                    'break', 'case', 'catch', 'class', 'const', 'continue', 'debugger',
                    'default', 'delete', 'do', 'else', 'export', 'extends', 'false',
                    'finally', 'for', 'function', 'if', 'import', 'in', 'instanceof',
                    'let', 'new', 'null', 'return', 'static', 'super', 'switch',
                    'this', 'throw', 'true', 'try', 'typeof', 'var', 'void', 'while',
                    'with', 'yield', 'async', 'await'
                ]
                # Add TypeScript-specific keywords
                if self.language == "typescript":
                    keywords.extend(['interface', 'type', 'namespace', 'readonly', 'private', 'protected', 'public'])
                    
                self.highlighting_rules.append(
                    (re.compile(r'\b(?:' + '|'.join(keywords) + r')\b'), self.formats["keyword"])
                )
                # JS/TS class definitions
                self.highlighting_rules.append((re.compile(r'\bclass\s+(\w+)'), self.formats["class"]))
                # JS/TS function definitions
                self.highlighting_rules.append((re.compile(r'\bfunction\s+(\w+)'), self.formats["function"]))
                # JS/TS strings
                self.highlighting_rules.append((re.compile(r'[\'"`].*?[\'"`]'), self.formats["string"]))
                # JS/TS comments (single line)
                self.highlighting_rules.append((re.compile(r'//.*'), self.formats["comment"]))
                # JS/TS this keyword
                self.highlighting_rules.append((re.compile(r'\bthis\b'), self.formats["keyword"]))
                
            elif self.language == "html" or self.language == "xml":
                # HTML/XML tags
                self.highlighting_rules.append((re.compile(r'<[!?]?[a-zA-Z0-9_:-]+'), self.formats["keyword"]))
                self.highlighting_rules.append((re.compile(r'</[a-zA-Z0-9_:-]+>'), self.formats["keyword"]))
                self.highlighting_rules.append((re.compile(r'/>'), self.formats["keyword"]))
                # HTML/XML attributes
                self.highlighting_rules.append((re.compile(r'[a-zA-Z0-9_:-]+(?==)'), self.formats["function"]))
                # HTML/XML attribute values
                self.highlighting_rules.append((re.compile(r'="[^"]*"'), self.formats["string"]))
                # HTML/XML comments
                self.highlighting_rules.append((re.compile(r'<!--.*?-->'), self.formats["comment"]))
                
            elif self.language == "json":
                # JSON keywords
                keywords = ['true', 'false', 'null']
                self.highlighting_rules.append(
                    (re.compile(r'\b(?:' + '|'.join(keywords) + r')\b'), self.formats["keyword"])
                )
                # JSON strings (keys)
                self.highlighting_rules.append((re.compile(r'"[^"]*"\s*:'), self.formats["function"]))
                # JSON strings (values)
                self.highlighting_rules.append((re.compile(r':\s*"[^"]*"'), self.formats["string"]))
                
            elif self.language == "cpp" or self.language == "c":
                # C/C++ keywords
                keywords = [
                    'auto', 'break', 'case', 'char', 'const', 'continue', 'default',
                    'do', 'double', 'else', 'enum', 'extern', 'float', 'for',
                    'goto', 'if', 'inline', 'int', 'long', 'register', 'return',
                    'short', 'signed', 'sizeof', 'static', 'struct', 'switch',
                    'typedef', 'union', 'unsigned', 'void', 'volatile', 'while'
                ]
                # Add C++-specific keywords
                if self.language == "cpp":
                    keywords.extend([
                        'bool', 'catch', 'class', 'constexpr', 'const_cast', 'delete',
                        'dynamic_cast', 'explicit', 'false', 'friend', 'mutable',
                        'namespace', 'new', 'nullptr', 'operator', 'private', 'protected',
                        'public', 'reinterpret_cast', 'static_cast', 'template',
                        'this', 'throw', 'true', 'try', 'typeid', 'typename',
                        'virtual', 'using'
                    ])
                    
                self.highlighting_rules.append(
                    (re.compile(r'\b(?:' + '|'.join(keywords) + r')\b'), self.formats["keyword"])
                )
                # C/C++ class definitions
                self.highlighting_rules.append((re.compile(r'\bclass\s+(\w+)'), self.formats["class"]))
                # C/C++ function definitions
                self.highlighting_rules.append((re.compile(r'\b\w+\s+(\w+)\s*\('), self.formats["function"]))
                # C/C++ strings
                self.highlighting_rules.append((re.compile(r'[\'"].*?[\'"]'), self.formats["string"]))
                # C/C++ comments (single line)
                self.highlighting_rules.append((re.compile(r'//.*'), self.formats["comment"]))
                # C/C++ preprocessor directives
                self.highlighting_rules.append((re.compile(r'#\w+'), self.formats["decorator"]))
                
            elif self.language == "css":
                # CSS properties and values
                css_properties = [
                    'color', 'background', 'margin', 'padding', 'font', 'border',
                    'display', 'position', 'width', 'height', 'top', 'left',
                    'right', 'bottom', 'text-align', 'flex', 'grid', 'transition',
                    'animation', 'transform', 'opacity', 'visibility', 'z-index'
                ]
                # CSS at-rules
                css_at_rules = ['@media', '@import', '@keyframes', '@font-face', '@supports', '@page']
                
                # CSS properties
                self.highlighting_rules.append(
                    (re.compile(r'\b(?:' + '|'.join(css_properties) + r')\s*:'), self.formats["function"])
                )
                # CSS at-rules
                self.highlighting_rules.append(
                    (re.compile(r'(?:' + '|'.join(css_at_rules) + r')\b'), self.formats["keyword"])
                )
                # CSS selectors
                self.highlighting_rules.append((re.compile(r'[.#][-_\w]+'), self.formats["class"]))
                # CSS values
                self.highlighting_rules.append((re.compile(r':\s*[^;{]+'), self.formats["string"]))
                # CSS comments
                self.highlighting_rules.append((re.compile(r'/\*.*?\*/'), self.formats["comment"]))
                # CSS units
                self.highlighting_rules.append((re.compile(r'\d+(?:px|em|rem|%|vh|vw|pt|cm|mm|in)'), self.formats["number"]))
                # CSS color values
                self.highlighting_rules.append((re.compile(r'#[0-9a-fA-F]{3,6}'), self.formats["number"]))
                # CSS important
                self.highlighting_rules.append((re.compile(r'!important'), self.formats["keyword"]))
                
            # Markdown
            elif self.language == "markdown":
                # Headers
                self.highlighting_rules.append((re.compile(r'^#\s+.*$', re.MULTILINE), self.formats["keyword"]))
                self.highlighting_rules.append((re.compile(r'^##\s+.*$', re.MULTILINE), self.formats["keyword"]))
                self.highlighting_rules.append((re.compile(r'^###\s+.*$', re.MULTILINE), self.formats["keyword"]))
                self.highlighting_rules.append((re.compile(r'^####\s+.*$', re.MULTILINE), self.formats["keyword"]))
                self.highlighting_rules.append((re.compile(r'^#####\s+.*$', re.MULTILINE), self.formats["keyword"]))
                
                # Bold and italic
                self.highlighting_rules.append((re.compile(r'\*\*.*?\*\*'), self.formats["class"]))
                self.highlighting_rules.append((re.compile(r'__.*?__'), self.formats["class"]))
                self.highlighting_rules.append((re.compile(r'\*.*?\*'), self.formats["function"]))
                self.highlighting_rules.append((re.compile(r'_.*?_'), self.formats["function"]))
                
                # Code blocks and inline code
                self.highlighting_rules.append((re.compile(r'```.*?```', re.DOTALL), self.formats["string"]))
                self.highlighting_rules.append((re.compile(r'`.*?`'), self.formats["string"]))
                
                # Links and images
                self.highlighting_rules.append((re.compile(r'!\[.*?\]\(.*?\)'), self.formats["decorator"]))
                self.highlighting_rules.append((re.compile(r'\[.*?\]\(.*?\)'), self.formats["decorator"]))
                
                # Lists
                self.highlighting_rules.append((re.compile(r'^\s*[\*\-+]\s+', re.MULTILINE), self.formats["number"]))
                self.highlighting_rules.append((re.compile(r'^\s*\d+\.\s+', re.MULTILINE), self.formats["number"]))

            # YAML
            elif self.language == "yaml":
                # YAML keys
                self.highlighting_rules.append((re.compile(r'^[\s\-]*([a-zA-Z0-9_\-]+)\s*:', re.MULTILINE), self.formats["function"]))
                # YAML values
                self.highlighting_rules.append((re.compile(r':\s*(.+)$', re.MULTILINE), self.formats["string"]))
                # YAML comments
                self.highlighting_rules.append((re.compile(r'#.*$', re.MULTILINE), self.formats["comment"]))
                # YAML document markers
                self.highlighting_rules.append((re.compile(r'^---$', re.MULTILINE), self.formats["keyword"]))
                self.highlighting_rules.append((re.compile(r'^\.\.\.?$', re.MULTILINE), self.formats["keyword"]))
                # YAML anchors and aliases
                self.highlighting_rules.append((re.compile(r'&[a-zA-Z0-9_\-]+'), self.formats["class"]))
                self.highlighting_rules.append((re.compile(r'\*[a-zA-Z0-9_\-]+'), self.formats["class"]))
                # YAML boolean values
                self.highlighting_rules.append((re.compile(r'\b(?:true|false|null|yes|no|on|off)\b', re.IGNORECASE), self.formats["keyword"]))
        
        def highlightBlock(self, text):
            """Apply highlighting to the given block of text."""
            # Apply all rules to the current text block
            for pattern, format in self.highlighting_rules:
                # Find all matches in the text
                for match in pattern.finditer(text):
                    start = match.start()
                    length = match.end() - start
                    self.setFormat(start, length, format)
            
            # Process multiline comments for languages that support them
            if self.language in ["javascript", "typescript", "cpp", "c", "java", "css"]:
                self._highlight_multiline_comment(text)
        
        def _highlight_multiline_comment(self, text):
            """Process multiline comments with state tracking between blocks."""
            # Get the previous block state (0 = not in comment, 1 = in comment)
            previous_block_state = self.previousBlockState()
            
            start_index = 0
            # If we're continuing from a comment block
            if previous_block_state == 1:
                # We're already in a comment, find the end
                end_index = text.find("*/", start_index)
                if end_index == -1:
                    # No end found, entire block is part of comment
                    self.setFormat(0, len(text), self.formats["comment"])
                    self.setCurrentBlockState(1)  # Still in comment
                    return
                else:
                    # End found, format the part until the end
                    length = end_index - start_index + 2  # +2 for */
                    self.setFormat(0, length, self.formats["comment"])
                    start_index = end_index + 2  # Move past the comment end
            
            # Look for new comment starts from start_index
            while start_index < len(text):
                start_index = text.find("/*", start_index)
                if start_index == -1:
                    # No more comments in this block
                    break
                
                end_index = text.find("*/", start_index)
                if end_index == -1:
                    # Comment continues beyond this block
                    self.setFormat(start_index, len(text) - start_index, self.formats["comment"])
                    self.setCurrentBlockState(1)  # In comment
                    return
                else:
                    # Comment ends within this block
                    length = end_index - start_index + 2  # +2 for */
                    self.setFormat(start_index, length, self.formats["comment"])
                    start_index = end_index + 2  # Move past the comment end
except ImportError:
    # Define a stub class if PySide6 is not available
    class CodeSyntaxHighlighter:
        """Stub class for CodeSyntaxHighlighter when PySide6 is not available."""
        def __init__(self, *args, **kwargs):
            pass

from dataclasses import dataclass
import datetime
import difflib
import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union, cast

# ---------------------------------------------------------------------------
# DependencyManager - Handles optional dependencies cleanly
# ---------------------------------------------------------------------------

class DependencyManager:
    """Manages optional dependencies with consistent fallback mechanisms.
    
    This class implements the Dependency Inversion Principle by providing
    a clean abstraction over optional dependencies like PySide6, allowing
    the rest of the code to work with a stable interface.
    """
    
    _DEPENDENCIES_LOADED = False
    _QT_AVAILABLE = False
    _QT_CLASSES = {}
    
    @classmethod
    def ensure_loaded(cls) -> bool:
        """Ensure dependencies are loaded if available.
        
        Returns:
            True if PySide6 is available, False otherwise
        """
        if cls._DEPENDENCIES_LOADED:
            return cls._QT_AVAILABLE
            
        cls._DEPENDENCIES_LOADED = True
        
        try:
            # Core Qt classes
            from PySide6.QtCore import (
                QModelIndex,
                QPoint,
                QSortFilterProxyModel,
                Qt,
                QTimer,
                QSize,
                Signal,
                QDir,
                QUrl,
                QObject,
            )
            
            # Qt GUI classes
            from PySide6.QtGui import (
                QDesktopServices,
                QPixmap, 
                QImage,
                QIcon,
                QColor,
                QPalette,
                QAction,
            )
            
            # Qt Widget classes
            from PySide6.QtWidgets import (
                QAbstractItemView,
                QComboBox,
                QFrame,
                QHBoxLayout,
                QInputDialog,
                QLabel,
                QLineEdit,
                QListView,
                QMenu,
                QMessageBox,
                QPushButton,
                QSizePolicy,
                QSplitter,
                QStackedWidget,
                QTextEdit,
                QToolButton,
                QTreeView,
                QTreeWidget,
                QTreeWidgetItem,
                QVBoxLayout,
                QWidget,
                QFileIconProvider,
                QFileSystemModel,
                QHeaderView,
                QDialog,
                QGridLayout,
                QCheckBox,
            )
            
            # Store all classes in the dictionary
            for name, cls_obj in locals().items():
                if name.startswith('Q'):
                    cls._QT_CLASSES[name] = cls_obj
                    
            cls._QT_AVAILABLE = True
            return True
            
        except ImportError:
            cls._QT_AVAILABLE = False
            return False
    
    @classmethod
    def get(cls, class_name: str) -> Any:
        """Get a Qt class by name with fallback to Any stub.
        
        Args:
            class_name: Name of the Qt class to get
            
        Returns:
            The Qt class if available, otherwise a stub
        """
        cls.ensure_loaded()
        return cls._QT_CLASSES.get(class_name, cast(Any, object))
        
    @classmethod
    def is_available(cls) -> bool:
        """Check if PySide6 is available.
        
        Returns:
            True if PySide6 is available, False otherwise
        """
        return cls.ensure_loaded()
        

# Import Qt classes through the dependency manager
Qt = DependencyManager.get('Qt')
QModelIndex = DependencyManager.get('QModelIndex')
QPoint = DependencyManager.get('QPoint')
QSortFilterProxyModel = DependencyManager.get('QSortFilterProxyModel')
QTimer = DependencyManager.get('QTimer')
QSize = DependencyManager.get('QSize')
Signal = DependencyManager.get('Signal')
QDir = DependencyManager.get('QDir')

# Qt GUI classes
QDesktopServices = DependencyManager.get('QDesktopServices')
QPixmap = DependencyManager.get('QPixmap')
QImage = DependencyManager.get('QImage')

# Qt Widget classes
QAbstractItemView = DependencyManager.get('QAbstractItemView')
QComboBox = DependencyManager.get('QComboBox')
QFrame = DependencyManager.get('QFrame')
QHBoxLayout = DependencyManager.get('QHBoxLayout')
QInputDialog = DependencyManager.get('QInputDialog')
QLabel = DependencyManager.get('QLabel')
QLineEdit = DependencyManager.get('QLineEdit')
QListView = DependencyManager.get('QListView')
QMenu = DependencyManager.get('QMenu')
QMessageBox = DependencyManager.get('QMessageBox')
QPushButton = DependencyManager.get('QPushButton')
QSizePolicy = DependencyManager.get('QSizePolicy')
QSplitter = DependencyManager.get('QSplitter')
QStackedWidget = DependencyManager.get('QStackedWidget')
QTextEdit = DependencyManager.get('QTextEdit')
QToolButton = DependencyManager.get('QToolButton')
QTreeView = DependencyManager.get('QTreeView')
QTreeWidget = DependencyManager.get('QTreeWidget')
QTreeWidgetItem = DependencyManager.get('QTreeWidgetItem')
QVBoxLayout = DependencyManager.get('QVBoxLayout')
QWidget = DependencyManager.get('QWidget')
QFileIconProvider = DependencyManager.get('QFileIconProvider')
QFileSystemModel = DependencyManager.get('QFileSystemModel')
QHeaderView = DependencyManager.get('QHeaderView')

try:  # optional dependency for disk information
    from ..system_tools.disk_monitor import DiskMonitorLinux, DiskMonitorWindows, DiskInfo
except Exception:  # pragma: no cover
    DiskMonitorLinux = DiskMonitorWindows = DiskInfo = cast(Any, object)


BG_PRIMARY = "#1e1f22"
BG_SECONDARY = "#2b2d31"
BG_TERTIARY = "#383a40"
ACCENT_PRIMARY = "#5865f2"
ACCENT_HOVER = "#4752c4"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#b5bac1"
TEXT_MUTED = "#80848e"
BORDER_COLOR = "#3f4147"


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _human_size(num_bytes: int) -> str:
    """Format a byte count into a human-readable size string.
    
    Args:
        num_bytes: Number of bytes to format
        
    Returns:
        Human-readable size string (e.g., "1.2 MB")
    """
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024.0:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} EB"


def _safe_stat(path: Path):
    """Safely get file/directory stats without raising exceptions.
    
    Args:
        path: Path to check
        
    Returns:
        os.stat_result or None if the operation failed
    """
    try:
        return path.stat()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# FileSystemManager - Handles filesystem operations (SRP)
# ---------------------------------------------------------------------------

class FileSystemManager:
    """Handles filesystem operations and provides a clean interface for UI components.
    
    This class applies the Single Responsibility Principle by extracting all
    filesystem-related logic from the UI classes.
    """
    
    def __init__(self, plugin_services=None):
        """Initialize the filesystem manager.
        
        Args:
            plugin_services: Optional services from the plugin for notifications
        """
        self._services = plugin_services
        self._logger = logging.getLogger("mmst.explorer.filesystem")
    
    def get_directory_contents(self, path: Path) -> List[Path]:
        """Get the contents of a directory.
        
        Args:
            path: Directory path to scan
            
        Returns:
            List of Path objects for files and subdirectories
        """
        try:
            return sorted(list(path.iterdir()), key=lambda p: (p.is_file(), p.name.lower()))
        except Exception as e:
            self._logger.error(f"Error accessing directory {path}: {e}")
            return []
            
    def get_file_size(self, path: Path) -> int:
        """Get the size of a file in bytes.
        
        Args:
            path: File path
            
        Returns:
            File size in bytes or 0 if unavailable
        """
        stats = _safe_stat(path)
        return stats.st_size if stats else 0
        
    def get_file_times(self, path: Path) -> Dict[str, datetime.datetime]:
        """Get file timestamp information.
        
        Args:
            path: File path
            
        Returns:
            Dictionary with created, modified, and accessed timestamps
        """
        stats = _safe_stat(path)
        result = {}
        
        if not stats:
            return result
            
        try:
            result["created"] = datetime.datetime.fromtimestamp(stats.st_ctime)
            result["modified"] = datetime.datetime.fromtimestamp(stats.st_mtime)
            result["accessed"] = datetime.datetime.fromtimestamp(stats.st_atime)
        except Exception:
            pass
            
        return result
        
    def create_directory(self, path: Path) -> bool:
        """Create a new directory.
        
        Args:
            path: Directory path to create
            
        Returns:
            True if successful, False otherwise
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            self._logger.error(f"Failed to create directory {path}: {e}")
            self._notify_error(f"Fehler beim Erstellen des Ordners: {e}")
            return False
            
    def delete_path(self, path: Path, use_trash: bool = True) -> bool:
        """Delete a file or directory.
        
        Args:
            path: Path to delete
            use_trash: Whether to use the system trash/recycle bin
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if use_trash:
                try:
                    from send2trash import send2trash
                    send2trash(str(path))
                    return True
                except ImportError:
                    self._logger.warning("send2trash not available, falling back to permanent delete")
                    # Fall through to permanent delete
            
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            return True
        except Exception as e:
            self._logger.error(f"Failed to delete {path}: {e}")
            self._notify_error(f"Fehler beim Löschen: {e}")
            return False
            
    def copy_path(self, source: Path, destination: Path) -> bool:
        """Copy a file or directory.
        
        Args:
            source: Source path
            destination: Destination path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(source, destination)
            return True
        except Exception as e:
            self._logger.error(f"Failed to copy {source} to {destination}: {e}")
            self._notify_error(f"Fehler beim Kopieren: {e}")
            return False
            
    def move_path(self, source: Path, destination: Path) -> bool:
        """Move a file or directory.
        
        Args:
            source: Source path
            destination: Destination path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            shutil.move(source, destination)
            return True
        except Exception as e:
            self._logger.error(f"Failed to move {source} to {destination}: {e}")
            self._notify_error(f"Fehler beim Verschieben: {e}")
            return False
    
    def _notify_error(self, message: str) -> None:
        """Send an error notification if services are available.
        
        Args:
            message: Error message
        """
        if self._services and hasattr(self._services, "send_notification"):
            self._services.send_notification(message, level="error", source="mmst.explorer")


# ---------------------------------------------------------------------------
# Breadcrumb navigation with overflow
# ---------------------------------------------------------------------------


class BreadcrumbBar(QWidget):  # type: ignore[misc]
    # Use Signal only if PySide6 is available, otherwise use a stub
    try:
        path_selected = Signal(Path)  # type: ignore
    except (NameError, TypeError):
        path_selected = None  # Stub for when PySide6 is unavailable

    def __init__(self, parent: Optional[QWidget] = None):  # type: ignore[override]
        super().__init__(parent)
        self._layout = QHBoxLayout(self)  # type: ignore
        if hasattr(self._layout, "setContentsMargins"):
            self._layout.setContentsMargins(0, 0, 0, 0)
            self._layout.setSpacing(6)
        self._current = Path.home()
        self._overflow: list[tuple[str, Path]] = []
        self.refresh()

    def set_path(self, path: Path) -> None:
        if path != self._current:
            self._current = path
            self.refresh()

    def refresh(self) -> None:
        if not hasattr(self._layout, "count"):
            return
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = getattr(item, "widget", lambda: None)()
            if widget:
                widget.deleteLater()
        self._overflow.clear()

        parts = list(self._current.parts)
        if not parts:
            parts = [self._current.anchor or os.sep]

        max_visible = 4
        if len(parts) > max_visible:
            hidden = parts[1 : len(parts) - (max_visible - 1)]
            self._overflow = [
                (segment or os.sep, Path(*parts[: index + 2]))
                for index, segment in enumerate(hidden)
            ]
            visible = [parts[0], "…", *parts[-(max_visible - 1):]]
        else:
            visible = parts

        accumulated = Path(visible[0]) if visible else Path.home()
        for index, segment in enumerate(visible):
            button = QToolButton()  # type: ignore
            if hasattr(button, "setObjectName"):
                button.setObjectName("ExplorerBreadcrumb")
            button.setText(segment or os.sep)
            if segment == "…":
                menu = QMenu(button)  # type: ignore
                for label, target in self._overflow:
                    action = menu.addAction(label)
                    if hasattr(action, "triggered") and hasattr(self.path_selected, "emit"):
                        action.triggered.connect(lambda _=False, p=target: self.path_selected.emit(p))  # type: ignore[attr-defined]
                button.setPopupMode(QToolButton.InstantPopup) if hasattr(button, "setPopupMode") else None  # type: ignore[attr-defined]
                button.setMenu(menu) if hasattr(button, "setMenu") else None  # type: ignore[attr-defined]
            else:
                if hasattr(button, "clicked") and hasattr(self.path_selected, "emit"):
                    button.clicked.connect(lambda _=False, p=accumulated: self.path_selected.emit(p))  # type: ignore[attr-defined]
                if index == 0:
                    accumulated = Path(segment)
                else:
                    accumulated = accumulated / segment
            self._layout.addWidget(button)
            if index < len(visible) - 1:
                separator = QLabel("›")  # type: ignore
                if hasattr(separator, "setObjectName"):
                    separator.setObjectName("ExplorerBreadcrumbSeparator")
                self._layout.addWidget(separator)
        self._layout.addStretch(1)


# ---------------------------------------------------------------------------
# Fuzzy proxy model for live search
# ---------------------------------------------------------------------------


class FuzzyFilterProxyModel(QSortFilterProxyModel):  # type: ignore[misc]
    def __init__(self, parent: Optional[QWidget] = None):  # type: ignore[override]
        super().__init__(parent)
        self._pattern = ""
        self._threshold = 0.42
        self._filter_criteria = None
        self._fs_manager = None  # Will be set from ExplorerWidget
    
    def set_filesystem_manager(self, fs_manager) -> None:
        """Set filesystem manager to access file metadata.
        
        Args:
            fs_manager: FileSystemManager instance
        """
        self._fs_manager = fs_manager
        
    def set_search_pattern(self, pattern: str) -> None:
        """Set text search pattern.
        
        Args:
            pattern: Search text
        """
        self._pattern = (pattern or "").strip().lower()
        self.invalidateFilter()
        
    def set_filter_criteria(self, criteria) -> None:
        """Set advanced filter criteria.
        
        Args:
            criteria: FilterCriteria object
        """
        self._filter_criteria = criteria
        self.invalidateFilter()

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:  # type: ignore[override]
        model = self.sourceModel()
        if not model:
            return True
            
        index = model.index(row, 0, parent)
        
        # Get file info
        try:
            # Skip directories from advanced filtering
            if hasattr(model, "isDir") and model.isDir(index):
                # Only apply text filtering to directories
                return self._matches_text_filter(model, index)
                
            # Get the full file path
            file_path = None
            if hasattr(model, "filePath"):
                file_path = model.filePath(index)
                
            if not file_path:
                return True
                
            # Apply text filter first (faster)
            if not self._matches_text_filter(model, index):
                return False
                
            # Apply advanced filter if criteria is set
            if self._filter_criteria:
                return self._matches_advanced_filter(Path(file_path))
                
            return True
            
        except Exception:
            # In case of errors, accept the row
            return True
    
    def _matches_text_filter(self, model, index) -> bool:
        """Check if row matches text filter.
        
        Args:
            model: Source model
            index: Model index
            
        Returns:
            True if the row matches text filter or no filter is set
        """
        if not self._pattern:
            return True
            
        try:
            candidate = model.fileName(index)  # type: ignore[attr-defined]
        except Exception:
            return True
            
        value = (candidate or "").lower()
        
        # Fast check for substring
        if self._pattern in value:
            return True
            
        # Fuzzy matching
        return difflib.SequenceMatcher(None, value, self._pattern).ratio() >= self._threshold
    
    def _matches_advanced_filter(self, path: Path) -> bool:
        """Check if file matches advanced filter criteria.
        
        Args:
            path: File path
            
        Returns:
            True if the file matches all filter criteria or no filter is set
        """
        if not self._filter_criteria or not self._fs_manager:
            return True
            
        # Get file metadata for filtering
        file_stats = {}
        
        # File size
        try:
            file_stats["size"] = self._fs_manager.get_file_size(path)
        except Exception:
            file_stats["size"] = 0
            
        # File dates
        try:
            file_times = self._fs_manager.get_file_times(path)
            file_stats.update(file_times)
        except Exception:
            pass
            
        # Apply filter criteria
        return self._filter_criteria.matches_file(path, file_stats)


# ---------------------------------------------------------------------------
# Disk health overview (integrated SystemTools monitor)
# ---------------------------------------------------------------------------


@dataclass
class DiskHealth:
    label: str
    capacity_bytes: int
    free_bytes: int
    status: str

    @property
    def percent_free(self) -> float:
        if self.capacity_bytes <= 0:
            return 0.0
        return max(0.0, min(1.0, self.free_bytes / self.capacity_bytes))


class DiskHealthWidget(QWidget):  # type: ignore[misc]
    def __init__(self, parent: Optional[QWidget] = None):  # type: ignore[override]
        super().__init__(parent)
        self.setObjectName("ExplorerDiskHealth") if hasattr(self, "setObjectName") else None
        self._layout = QVBoxLayout(self)  # type: ignore
        if hasattr(self._layout, "setContentsMargins"):
            self._layout.setContentsMargins(8, 8, 8, 8)
            self._layout.setSpacing(6)
        self._monitor = self._resolve_monitor()
        self._timer = QTimer(self)
        if hasattr(self._timer, "setInterval"):
            self._timer.setInterval(60_000)
            self._timer.timeout.connect(self.refresh)  # type: ignore[attr-defined]
            try:
                self._timer.start()
            except Exception:
                pass
        self.refresh()

    def _resolve_monitor(self):
        system = platform.system().lower()
        if system.startswith("win") and DiskMonitorWindows not in (None, object):
            try:
                return DiskMonitorWindows()
            except Exception:
                return None
        if system.startswith("linux") and DiskMonitorLinux not in (None, object):
            try:
                return DiskMonitorLinux()
            except Exception:
                return None
        return None

    def refresh(self) -> None:
        if not hasattr(self._layout, "count"):
            return
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = getattr(item, "widget", lambda: None)()
            if widget:
                widget.deleteLater()

        for health in self._gather_health():
            row = QWidget()  # type: ignore
            layout = QHBoxLayout(row)  # type: ignore
            if hasattr(layout, "setContentsMargins"):
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(6)

            icon_label = QLabel(self._status_icon(health.status))  # type: ignore
            layout.addWidget(icon_label)

            label = QLabel(health.label)  # type: ignore
            label.setObjectName("ExplorerDiskLabel") if hasattr(label, "setObjectName") else None
            layout.addWidget(label, 1)

            usage_bar = QFrame()  # type: ignore
            usage_bar.setObjectName("ExplorerDiskUsage") if hasattr(usage_bar, "setObjectName") else None
            percent = max(10, int(health.percent_free * 100))
            if hasattr(usage_bar, "setStyleSheet"):
                usage_bar.setStyleSheet(
                    "background:#1d1e21;border:1px solid #303136;border-radius:4px;"
                    f"QFrame::indicator{{width:{percent}px;height:6px;}}"
                )
            usage_bar.setFixedHeight(8) if hasattr(usage_bar, "setFixedHeight") else None
            usage_bar.setMinimumWidth(80) if hasattr(usage_bar, "setMinimumWidth") else None
            layout.addWidget(usage_bar)

            info = QLabel(f"{_human_size(health.free_bytes)} frei")  # type: ignore
            info.setObjectName("ExplorerDiskInfo") if hasattr(info, "setObjectName") else None
            layout.addWidget(info)

            self._layout.addWidget(row)
        self._layout.addStretch(1)

    def _gather_health(self) -> list[DiskHealth]:
        results: list[DiskHealth] = []
        monitor = self._monitor
        if monitor and getattr(monitor, "is_available", False):
            try:
                disks = monitor.get_disks()  # Iterable of DiskInfo objects
                for entry in disks:
                    label = f"{entry.model or 'Laufwerk'} ({entry.index})"
                    total = int(entry.size_gb * 1024 ** 3)
                    free = self._free_bytes(Path(f"{entry.index}:/")) if platform.system() == "Windows" else total
                    results.append(DiskHealth(label, total, free, getattr(entry, "status", "HEALTHY") or "HEALTHY"))
                if results:
                    return results
            except Exception:
                results.clear()

        for label, path in self._fallback_mounts():
            usage = self._disk_usage(path)
            if not usage:
                continue
            results.append(DiskHealth(label, usage.total, usage.free, "HEALTHY"))
        return results

    def _fallback_mounts(self) -> list[tuple[str, Path]]:
        entries: list[tuple[str, Path]] = []
        system = platform.system().lower()
        if system == "windows":
            from string import ascii_uppercase

            for letter in ascii_uppercase:
                drive = Path(f"{letter}:/")
                if drive.exists():
                    entries.append((f"{letter}:", drive))
        else:
            for mount in (Path("/"), Path("/home"), Path("/media"), Path("/mnt")):
                if mount.exists():
                    entries.append((str(mount), mount))
        return entries

    def _disk_usage(self, path: Path):
        try:
            return shutil.disk_usage(str(path))
        except Exception:
            return None

    def _free_bytes(self, path: Path) -> int:
        usage = self._disk_usage(path)
        return usage.free if usage else 0

    @staticmethod
    def _status_icon(status: str) -> str:
        status = (status or "").upper()
        if status.startswith("CRIT"):
            return "❌"
        if status.startswith("WARN"):
            return "⚠️"
        return "✅"


# ---------------------------------------------------------------------------
# Details panel with preview & metadata stubs
# ---------------------------------------------------------------------------


class DetailsPanel(QWidget):  # type: ignore[misc]
    def __init__(self, parent: Optional[QWidget] = None):  # type: ignore[override]
        super().__init__(parent)
        layout = QVBoxLayout(self)  # type: ignore
        if hasattr(layout, "setContentsMargins"):
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(10)

        # Try to use QTextEdit for preview (better for text files)
        try:
            from PySide6.QtWidgets import QTextEdit
            self._preview = QTextEdit()
            if hasattr(self._preview, "setReadOnly"):
                self._preview.setReadOnly(True)
            if hasattr(self._preview, "setObjectName"):
                self._preview.setObjectName("ExplorerPreview")
            if hasattr(self._preview, "setPlaceholderText"):
                self._preview.setPlaceholderText("Keine Auswahl")
            if hasattr(self._preview, "setMinimumHeight"):
                self._preview.setMinimumHeight(220)
        except ImportError:
            # Fallback to QLabel if QTextEdit is not available
            self._preview = QLabel("Keine Auswahl")  # type: ignore
            if hasattr(self._preview, "setAlignment") and hasattr(Qt, "AlignCenter"):
                self._preview.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
            if hasattr(self._preview, "setObjectName"):
                self._preview.setObjectName("ExplorerPreview")
            if hasattr(self._preview, "setWordWrap"):
                self._preview.setWordWrap(True)
            if hasattr(self._preview, "setMinimumHeight"):
                self._preview.setMinimumHeight(220)
        if hasattr(layout, "addWidget"):
            layout.addWidget(self._preview, 2)

        self._metadata = QTextEdit()  # type: ignore
        if hasattr(self._metadata, "setReadOnly"):
            self._metadata.setReadOnly(True)
        if hasattr(self._metadata, "setObjectName"):
            self._metadata.setObjectName("ExplorerMetadata")
        if hasattr(layout, "addWidget"):
            layout.addWidget(self._metadata, 1)

        self._properties = QTextEdit()  # type: ignore
        if hasattr(self._properties, "setReadOnly"):
            self._properties.setReadOnly(True)
        if hasattr(self._properties, "setObjectName"):
            self._properties.setObjectName("ExplorerProperties")
        if hasattr(layout, "addWidget"):
            layout.addWidget(self._properties, 1)

    def clear(self) -> None:
        # Clear preview based on widget type
        if hasattr(self._preview, "setPlainText"):
            self._preview.setPlainText("Keine Auswahl")
        elif hasattr(self._preview, "setText"):
            self._preview.setText("Keine Auswahl")
        
        # Clear metadata and properties
        if hasattr(self._metadata, "setPlainText"):
            self._metadata.setPlainText("")
        if hasattr(self._properties, "setPlainText"):
            self._properties.setPlainText("")

    def update_for_path(self, path: Path) -> None:
        if not path.exists():
            self.clear()
            return
        self._render_preview(path)
        self._render_metadata(path)
        self._render_properties(path)

    def _render_preview(self, path: Path) -> None:
        if path.is_dir():
            # Handle directory preview
            if hasattr(self._preview, "setPlainText"):
                self._preview.setPlainText("📁 Ordner")
            elif hasattr(self._preview, "setText"):
                self._preview.setText("📁 Ordner")
            return
        suffix = path.suffix.lower()
        try:
            from PySide6.QtGui import QPixmap
            image_supported = True
        except (ImportError, TypeError):
            image_supported = False
            
        if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".gif"} and image_supported:
            try:
                pix = QPixmap(str(path))  # type: ignore
                if hasattr(pix, "isNull") and pix.isNull():
                    raise ValueError("invalid pixmap")
                if hasattr(Qt, "KeepAspectRatio") and hasattr(Qt, "SmoothTransformation"):
                    scaled = pix.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # type: ignore[attr-defined]
                else:
                    scaled = pix.scaled(320, 320)  # Fallback without transformation flags  # type: ignore[attr-defined]
                # Handle based on preview widget type
                if hasattr(self._preview, "setPixmap"):
                    # Direct pixmap setting for QLabel
                    self._preview.setPixmap(scaled)
                    if hasattr(self._preview, "setText"):
                        self._preview.setText("")
                elif hasattr(self._preview, "setPlainText"):
                    # For QTextEdit, display image details
                    self._preview.setPlainText(f"🖼️ Bild: {path.name}\nGröße: {pix.width()}x{pix.height()} Pixel")
                return
            except Exception as e:
                # Handle error based on widget type
                msg = f"Fehler beim Laden des Bildes: {str(e)}"
                if hasattr(self._preview, "setPlainText"):
                    self._preview.setPlainText(msg)
                elif hasattr(self._preview, "setText"):
                    self._preview.setText(msg)
        # Handle different file types with appropriate preview
        if suffix in {".mp3", ".wav", ".flac"}:
            if hasattr(self._preview, "setPlainText"):
                self._preview.setPlainText(f"🎵 Audio-Datei: {path.name}")
            elif hasattr(self._preview, "setText"):
                self._preview.setText("🎵 Audio-Datei")
        elif suffix in {".mp4", ".mkv", ".mov"}:
            if hasattr(self._preview, "setPlainText"):
                self._preview.setPlainText(f"🎬 Video-Datei: {path.name}")
            elif hasattr(self._preview, "setText"):
                self._preview.setText("🎬 Video-Datei")
        elif suffix in {".pdf"}:
            if hasattr(self._preview, "setPlainText"):
                self._preview.setPlainText(f"📄 PDF Datei: {path.name}")
            elif hasattr(self._preview, "setText"):
                self._preview.setText("📄 PDF Vorschau")
        elif suffix in {".txt", ".md", ".py", ".json", ".xml", ".html", ".css", ".js", ".ts", ".yml", ".yaml", ".ini", ".cfg", ".conf", ".log", ".sh", ".bat", ".ps1", ".c", ".cpp", ".h", ".hpp", ".cs", ".java"}:
            self._render_text_preview(path)
        else:
            # Generic file type - display filename
            if hasattr(self._preview, "setPlainText"):
                self._preview.setPlainText(path.name)
            elif hasattr(self._preview, "setText"):
                    self._preview.setText(path.name)

    def _render_metadata(self, path: Path) -> None:
        if hasattr(self._metadata, "setPlainText"):
            if path.is_file():
                self._metadata.setPlainText(f"Dateityp: {path.suffix or 'n/a'}")
            else:
                self._metadata.setPlainText("Ordner")

    def _render_text_preview(self, path: Path) -> None:
        """Render a preview of a text file with syntax highlighting if possible."""
        # Use QTextEdit for text previews instead of QLabel
        try:
            # Read file content with line limitation for very large files
            max_lines = 500
            max_size = 100 * 1024  # 100KB
            
            file_size = path.stat().st_size
            if file_size > max_size:
                content = f"Datei ist zu groß für Vorschau (> 100KB)\nErste {max_lines} Zeilen werden angezeigt:\n\n"
                with path.open("r", encoding="utf-8", errors="ignore") as f:
                    content += "".join([next(f) for _ in range(max_lines) if f])
                
                # For very large files (> 1MB), disable syntax highlighting to maintain performance
                disable_highlighting = file_size > 1024 * 1024
            else:
                content = path.read_text(encoding="utf-8", errors="ignore")
                disable_highlighting = False            # Use syntax highlighting if available
            try:
                # Set appropriate metadata based on file type
                suffix = path.suffix.lower()
                language = "generic"
                
                if suffix == ".py":
                    self._metadata.setPlainText(f"Python-Datei: {path.name}")
                    language = "python"
                elif suffix in [".js", ".jsx"]:
                    self._metadata.setPlainText(f"JavaScript-Datei: {path.name}")
                    language = "javascript"
                elif suffix in [".ts", ".tsx"]:
                    self._metadata.setPlainText(f"TypeScript-Datei: {path.name}")
                    language = "typescript"
                elif suffix in [".json"]:
                    self._metadata.setPlainText(f"JSON-Datei: {path.name}")
                    language = "json"
                elif suffix in [".html", ".htm"]:
                    self._metadata.setPlainText(f"HTML-Datei: {path.name}")
                    language = "html"
                elif suffix in [".xml", ".xhtml", ".svg"]:
                    self._metadata.setPlainText(f"XML-Datei: {path.name}")
                    language = "xml"
                elif suffix in [".c", ".h"]:
                    self._metadata.setPlainText(f"C-Datei: {path.name}")
                    language = "c"
                elif suffix in [".cpp", ".hpp", ".cc", ".cxx"]:
                    self._metadata.setPlainText(f"C++-Datei: {path.name}")
                    language = "cpp"
                elif suffix in [".css"]:
                    self._metadata.setPlainText(f"CSS-Datei: {path.name}")
                    language = "css"
                elif suffix in [".md", ".markdown"]:
                    self._metadata.setPlainText(f"Markdown-Datei: {path.name}")
                    language = "markdown"
                elif suffix in [".yml", ".yaml"]:
                    self._metadata.setPlainText(f"YAML-Datei: {path.name}")
                    language = "yaml"
                else:
                    self._metadata.setPlainText(f"Text-Datei: {path.name}")
                    language = "generic"
                
                # Set text content
                if hasattr(self._preview, "setPlainText"):
                    self._preview.setPlainText(content)
                    
                    # Apply syntax highlighting if document is available and not disabled for large files
                    if hasattr(self._preview, "document") and not disable_highlighting:
                        document = self._preview.document()
                        highlighter = CodeSyntaxHighlighter(document, language)
                else:
                    # Fallback to setText if setPlainText is not available
                    if hasattr(self._preview, "setText"):
                        self._preview.setText(content[:1000] + ("..." if len(content) > 1000 else ""))
            except ImportError as e:
                # Fallback if PySide6 advanced components are not available
                if hasattr(self._preview, "setText"):
                    self._preview.setText(content[:1000] + ("..." if len(content) > 1000 else ""))
                if hasattr(self._metadata, "setPlainText"):
                    self._metadata.setPlainText(f"Text-Datei: {path.name}")
                print(f"Syntax highlighting not available: {e}")
                    
        except Exception as e:
            # Fallback for any errors
            if hasattr(self._preview, "setText"):
                self._preview.setText(f"Fehler beim Laden der Datei: {str(e)}")
            if hasattr(self._metadata, "setPlainText"):
                self._metadata.setPlainText(f"Text-Datei: {path.name}")

    def _render_properties(self, path: Path) -> None:
        stat_info = _safe_stat(path)
        lines = [f"Pfad: {path}"]
        if stat_info:
            lines.append(f"Größe: {_human_size(stat_info.st_size)}")
            try:
                import datetime

                lines.append(
                    "Geändert: " + datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime("%d.%m.%Y %H:%M")
                )
            except Exception:
                pass
        if hasattr(self._properties, "setPlainText"):
            self._properties.setPlainText("\n".join(lines))


# ---------------------------------------------------------------------------
# ConfigurationManager - Manages explorer settings
# ---------------------------------------------------------------------------

class ConfigurationManager:
    """Manages Explorer configuration settings and preferences.
    
    This class applies the Single Responsibility Principle by extracting
    all configuration-related logic into a dedicated component.
    """
    
    DEFAULT_VIEW_MODE = "grid"
    DEFAULT_SORT_MODE = "name"
    DEFAULT_FAVORITES = ["home", "desktop", "documents", "downloads"]
    
    def __init__(self, plugin_services=None):
        """Initialize the configuration manager.
        
        Args:
            plugin_services: Optional services from the plugin for configuration storage
        """
        self._services = plugin_services
        self._config = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from the plugin services."""
        if self._services and hasattr(self._services, "get_plugin_config"):
            try:
                config = self._services.get_plugin_config("mmst.explorer")
                if isinstance(config, dict):
                    self._config = config
            except Exception:
                pass
                
        # Ensure defaults for required settings
        if "view_mode" not in self._config:
            self._config["view_mode"] = self.DEFAULT_VIEW_MODE
        if "sort_mode" not in self._config:
            self._config["sort_mode"] = self.DEFAULT_SORT_MODE
        if "favorites" not in self._config or not isinstance(self._config["favorites"], list):
            self._config["favorites"] = self._get_default_favorites()
            
    def _get_default_favorites(self) -> List[Dict[str, str]]:
        """Get default favorite locations based on the user's home directory.
        
        Returns:
            List of favorite location dictionaries
        """
        favorites = []
        home = Path.home()
        
        # Add home directory
        favorites.append({
            "name": "Home",
            "path": str(home),
            "icon": "🏠"
        })
        
        # Add common subdirectories if they exist
        common_dirs = {
            "Desktop": "desktop",
            "Documents": "documents", 
            "Downloads": "downloads",
            "Pictures": "pictures",
            "Music": "music",
            "Videos": "videos"
        }
        
        for name, folder in common_dirs.items():
            path = home / folder
            if path.exists() and path.is_dir():
                favorites.append({
                    "name": name,
                    "path": str(path),
                    "icon": "📁"
                })
                
        # Add root drives on Windows
        if platform.system().lower() == "windows":
            for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:\\"
                if Path(drive).exists():
                    favorites.append({
                        "name": f"{letter}:",
                        "path": drive,
                        "icon": "💿" 
                    })
                    
        return favorites
            
    def save_config(self) -> bool:
        """Save current configuration to plugin services.
        
        Returns:
            True if successful, False otherwise
        """
        if self._services and hasattr(self._services, "save_plugin_config"):
            try:
                self._services.save_plugin_config("mmst.explorer", self._config)
                return True
            except Exception:
                return False
        return False
        
    def get_view_mode(self) -> str:
        """Get preferred view mode.
        
        Returns:
            View mode string ("grid", "list", or "details")
        """
        return self._config.get("view_mode", self.DEFAULT_VIEW_MODE)
        
    def set_view_mode(self, mode: str) -> None:
        """Set preferred view mode.
        
        Args:
            mode: View mode string ("grid", "list", or "details")
        """
        if mode in ("grid", "list", "details"):
            self._config["view_mode"] = mode
            self.save_config()
            
    def get_sort_mode(self) -> str:
        """Get preferred sort mode.
        
        Returns:
            Sort mode string ("name", "date", "size", "type")
        """
        return self._config.get("sort_mode", self.DEFAULT_SORT_MODE)
        
    def set_sort_mode(self, mode: str) -> None:
        """Set preferred sort mode.
        
        Args:
            mode: Sort mode string ("name", "date", "size", "type")
        """
        if mode in ("name", "date", "size", "type"):
            self._config["sort_mode"] = mode
            self.save_config()
            
    def get_favorites(self) -> List[Dict[str, str]]:
        """Get list of favorite locations.
        
        Returns:
            List of favorite location dictionaries
        """
        return self._config.get("favorites", [])
        
    def add_favorite(self, name: str, path: str, icon: str = "📁") -> None:
        """Add a new favorite location.
        
        Args:
            name: Display name for the favorite
            path: Filesystem path
            icon: Optional emoji icon
        """
        if not "favorites" in self._config:
            self._config["favorites"] = []
            
        # Avoid duplicates
        for fav in self._config["favorites"]:
            if fav.get("path") == path:
                return
                
        self._config["favorites"].append({
            "name": name,
            "path": path,
            "icon": icon
        })
        self.save_config()
        
    def remove_favorite(self, path: str) -> None:
        """Remove a favorite location.
        
        Args:
            path: Path to remove from favorites
        """
        if not "favorites" in self._config:
            return
            
        self._config["favorites"] = [
            fav for fav in self._config["favorites"]
            if fav.get("path") != path
        ]
        self.save_config()
        
    def get_last_directory(self) -> Optional[str]:
        """Get last visited directory.
        
        Returns:
            Last directory path or None
        """
        return self._config.get("last_directory")
        
    def set_last_directory(self, path: str) -> None:
        """Set last visited directory.
        
        Args:
            path: Directory path to remember
        """
        self._config["last_directory"] = path
        self.save_config()


# ---------------------------------------------------------------------------
# ViewFactory - Factory pattern for creating file views
# ---------------------------------------------------------------------------

def show_drop_context_menu(widget, event, fs_manager=None, target_path=None):
    """Show a context menu for drag and drop operations.
    
    Args:
        widget: Widget to show the context menu on
        event: The drop event
        fs_manager: FileSystemManager instance for file operations
        target_path: Path to the target directory
        
    Returns:
        True if the operation was handled, False otherwise
    """
    # Safety checks
    if widget is None or event is None:
        print("Error: Missing widget or event")
        return False
        
    if fs_manager is None or target_path is None:
        print("Error: Missing filesystem manager or target path")
        return False
        
    try:
        from PySide6.QtWidgets import QMenu
        
        # Check if this is an internal drag (source paths within the explorer)
        if not hasattr(event.mimeData(), "hasFormat") or not event.mimeData().hasFormat("application/x-mmst-explorer-paths"):
            return False
            
        # Parse source paths
        source_paths_data = event.mimeData().data("application/x-mmst-explorer-paths")
        if source_paths_data is None:
            print("Error: No source paths data")
            return False
            
        source_paths_str = source_paths_data.data().decode("utf-8")
        if not source_paths_str:
            print("Error: Empty source paths string")
            return False
            
        source_paths = [Path(p) for p in source_paths_str.split(",") if p.strip()]
        if not source_paths:
            print("Error: No valid source paths")
            return False
            
        # Create context menu with copy/move options
        menu = QMenu(widget)
        
        # Add copy action
        copy_action = menu.addAction("Kopieren")
        copy_action.triggered.connect(lambda: _process_drop_operation(fs_manager, source_paths, target_path, "copy"))
        
        # Add move action
        move_action = menu.addAction("Verschieben")
        move_action.triggered.connect(lambda: _process_drop_operation(fs_manager, source_paths, target_path, "move"))
        
        # Add cancel action
        menu.addAction("Abbrechen")
        
        # Show menu at cursor position
        viewport = widget.viewport() if hasattr(widget, "viewport") else widget
        try:
            pos = viewport.mapToGlobal(event.position().toPoint()) if hasattr(event, "position") and hasattr(event.position(), "toPoint") else viewport.mapToGlobal(event.pos())
            menu.exec(pos)
        except Exception as menu_err:
            print(f"Error showing menu: {menu_err}")
            return False
            
        event.accept()
        return True
    except Exception as e:
        print(f"Error showing context menu: {e}")
        return False
    
def _process_drop_operation(fs_manager, source_paths, target_path, operation):
    """Process a drop operation (copy or move).
    
    Args:
        fs_manager: FileSystemManager instance for file operations
        source_paths: List of source paths to copy or move
        target_path: Target directory path
        operation: Operation to perform ("copy" or "move")
    """
    # Safety checks
    if fs_manager is None or target_path is None:
        print("Error: Missing filesystem manager or target path")
        return
        
    if not isinstance(source_paths, list) or not source_paths:
        print("Error: No source paths provided")
        return
        
    success_count = 0
    fail_count = 0
    
    try:
        for source_path in source_paths:
            if not source_path.exists():
                continue
                
            # Don't move/copy to the same directory
            if source_path.parent == target_path:
                continue
                
            # Create target path
            target = target_path / source_path.name
            
            # Skip if target is a subdirectory of source (would create infinite recursion)
            if source_path.is_dir() and str(target).startswith(str(source_path)):
                print(f"Skipping {source_path} - would create recursive copy")
                continue
                
            success = False
            if operation == "copy":
                success = fs_manager.copy_path(source_path, target)
            elif operation == "move":
                success = fs_manager.move_path(source_path, target)
            else:
                print(f"Unknown operation: {operation}")
                continue
                
            if success:
                success_count += 1
            else:
                fail_count += 1
    except Exception as e:
        print(f"Error during {operation} operation: {e}")
            
    # Log or display results as needed
    op_name = "kopiert" if operation == "copy" else "verschoben"
    print(f"{success_count} Elemente erfolgreich {op_name}, {fail_count} fehlgeschlagen")

class DraggableListView(QListView):  # type: ignore[misc]
    """Custom QListView with enhanced drag and drop capabilities."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self._fs_manager = None
        self._current_path = None
        
    def startDrag(self, supportedActions):  # type: ignore[override]
        """Start a drag operation with the selected items.
        
        Args:
            supportedActions: Supported drag actions
        """
        try:
            from PySide6.QtCore import QMimeData, QUrl, Qt, QPoint
            from PySide6.QtGui import QDrag, QPixmap, QPainter, QColor
            
            # Get selected indexes
            indexes = self.selectedIndexes()
            if not indexes:
                return
                
            # Create mime data
            mime_data = QMimeData()
            
            # Add URLs for external drops
            urls = []
            paths = []
            
            for index in indexes:
                if not index.isValid():
                    continue
                    
                # Get the model
                model = self.model()
                if hasattr(model, "mapToSource"):
                    source_index = model.mapToSource(index)
                    file_model = model.sourceModel()
                else:
                    source_index = index
                    file_model = model
                    
                # Get the path    
                path = Path(file_model.filePath(source_index))
                if not path.exists():
                    continue
                    
                # Add URL and path
                urls.append(QUrl.fromLocalFile(str(path)))
                paths.append(str(path))
                
            # Set URLs for external drops
            mime_data.setUrls(urls)
            
            # Add custom format for internal drops
            if hasattr(mime_data, "setData"):
                mime_data.setData("application/x-mmst-explorer-paths", ",".join(paths).encode())
                
            # Start drag with visual feedback
            drag = QDrag(self)
            drag.setMimeData(mime_data)
            
            # Add visual feedback with pixmap if first item is valid
            if urls and hasattr(drag, "setPixmap") and hasattr(indexes[0], "data"):
                try:
                    # Get icon from model
                    icon_data = indexes[0].data(Qt.DecorationRole)  # type: ignore[attr-defined]
                    
                    if icon_data:
                        # Create pixmap for drag visual feedback
                        pixmap = QPixmap(32, 32)
                        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background
                        
                        # Draw icon on pixmap
                        painter = QPainter(pixmap)
                        icon_data.paint(painter, 0, 0, 32, 32)  # type: ignore[attr-defined]
                        
                        # Add counter badge if multiple items
                        if len(indexes) > 1:
                            # Draw a badge with number of items
                            painter.setPen(QColor(255, 255, 255))
                            painter.setBrush(QColor(0, 120, 215))
                            painter.drawEllipse(20, 20, 12, 12)
                            painter.setPen(QColor(255, 255, 255))
                            painter.drawText(20, 20, 12, 12, Qt.AlignCenter, str(len(indexes)))  # type: ignore[attr-defined]
                            
                        painter.end()
                        drag.setPixmap(pixmap)
                        drag.setHotSpot(QPoint(16, 16))  # Center hotspot
                except Exception:
                    # Fallback to default drag visual
                    pass
            
            # Set default action
            if hasattr(drag, "exec") and hasattr(supportedActions, "CopyAction"):
                drag.exec(supportedActions)
                
        except Exception as e:
            print(f"Error starting drag: {e}")
    
    def set_context(self, fs_manager, current_path):
        """Set the filesystem manager and current path for drag and drop operations.
        
        Args:
            fs_manager: FileSystemManager instance
            current_path: Current directory path
        """
        self._fs_manager = fs_manager
        self._current_path = current_path
            
    def dragEnterEvent(self, event):  # type: ignore[override]
        """Handle drag enter events to accept file URLs."""
        if hasattr(event.mimeData(), "hasUrls") and event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dragMoveEvent(self, event):  # type: ignore[override]
        """Handle drag move events to provide visual feedback."""
        if hasattr(event.mimeData(), "hasUrls") and event.mimeData().hasUrls():
            # Get the index at the current position
            index = self.indexAt(event.pos())
            
            # Accept if we're dropping directly on the view (not on an item)
            if not index.isValid():
                event.acceptProposedAction()
                return
                
            # Get the file path from the model
            model = self.model()
            if hasattr(model, "mapToSource"):
                source_index = model.mapToSource(index)
                file_model = model.sourceModel()
            else:
                source_index = index
                file_model = model
                
            # Get the path
            file_path = Path(file_model.filePath(source_index))
            
            # Accept if the target is a directory
            if file_path.is_dir():
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
            
    def dropEvent(self, event):  # type: ignore[override]
        """Handle drop events for both external and internal drags."""
        if not hasattr(event.mimeData(), "hasUrls") or not event.mimeData().hasUrls():
            event.ignore()
            return
            
        # Get the target path - either the item under the cursor or the current path
        target_path = self._current_path
        if target_path is None:
            # If no current path is set, we can't perform the drop operation
            event.ignore()
            return
            
        index = self.indexAt(event.pos())
        
        if index.isValid():
            # Get the file path from the model
            model = self.model()
            if hasattr(model, "mapToSource"):
                source_index = model.mapToSource(index)
                file_model = model.sourceModel()
            else:
                source_index = index
                file_model = model
                
            # Get the path
            try:
                file_path = Path(file_model.filePath(source_index))
                
                # If it's a directory, use it as the target
                if file_path.is_dir():
                    target_path = file_path
            except Exception:
                # If we can't get the file path, just use the current path
                pass
                
        # Check for internal drag (source paths within the explorer)
        if hasattr(self, "_fs_manager") and self._fs_manager is not None and target_path is not None:
            # Try to handle with context menu
            if show_drop_context_menu(self, event, self._fs_manager, target_path):
                return
                
        # External drop (from outside the explorer)
        if target_path is not None:
            urls = event.mimeData().urls()
            for url in urls:
                path = Path(url.toLocalFile())
                if not path.exists():
                    continue
                    
                target = target_path / path.name
                if hasattr(self, "_fs_manager") and self._fs_manager is not None:
                    self._fs_manager.copy_path(path, target)
        
        event.acceptProposedAction()
            
            
class DraggableTreeView(QTreeView):  # type: ignore[misc]
    """Custom QTreeView with enhanced drag and drop capabilities."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self._fs_manager = None
        self._current_path = None
        
    def startDrag(self, supportedActions):  # type: ignore[override]
        """Start a drag operation with the selected items.
        
        Args:
            supportedActions: Supported drag actions
        """
        try:
            from PySide6.QtCore import QMimeData, QUrl, Qt, QPoint
            from PySide6.QtGui import QDrag, QPixmap, QPainter, QColor
            
            # Get selected indexes
            indexes = self.selectedIndexes()
            if not indexes:
                return
                
            # Filter to only include first column
            column_zero_indexes = [idx for idx in indexes if idx.column() == 0]
            
            # Create mime data
            mime_data = QMimeData()
            
            # Add URLs for external drops
            urls = []
            paths = []
            
            for index in column_zero_indexes:
                if not index.isValid():
                    continue
                    
                # Get the model
                model = self.model()
                if hasattr(model, "mapToSource"):
                    source_index = model.mapToSource(index)
                    file_model = model.sourceModel()
                else:
                    source_index = index
                    file_model = model
                    
                # Get the path    
                path = Path(file_model.filePath(source_index))
                if not path.exists():
                    continue
                    
                # Add URL and path
                urls.append(QUrl.fromLocalFile(str(path)))
                paths.append(str(path))
                
            # Set URLs for external drops
            mime_data.setUrls(urls)
            
            # Add custom format for internal drops
            if hasattr(mime_data, "setData"):
                mime_data.setData("application/x-mmst-explorer-paths", ",".join(paths).encode())
                
            # Start drag with visual feedback
            drag = QDrag(self)
            drag.setMimeData(mime_data)
            
            # Add visual feedback with pixmap if first item is valid
            if urls and hasattr(drag, "setPixmap") and len(column_zero_indexes) > 0 and hasattr(column_zero_indexes[0], "data"):
                try:
                    # Get icon from model
                    icon_data = column_zero_indexes[0].data(Qt.DecorationRole)  # type: ignore[attr-defined]
                    
                    if icon_data:
                        # Create pixmap for drag visual feedback
                        pixmap = QPixmap(32, 32)
                        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background
                        
                        # Draw icon on pixmap
                        painter = QPainter(pixmap)
                        icon_data.paint(painter, 0, 0, 32, 32)  # type: ignore[attr-defined]
                        
                        # Add counter badge if multiple items
                        if len(column_zero_indexes) > 1:
                            # Draw a badge with number of items
                            painter.setPen(QColor(255, 255, 255))
                            painter.setBrush(QColor(0, 120, 215))
                            painter.drawEllipse(20, 20, 12, 12)
                            painter.setPen(QColor(255, 255, 255))
                            painter.drawText(20, 20, 12, 12, Qt.AlignCenter, str(len(column_zero_indexes)))  # type: ignore[attr-defined]
                            
                        painter.end()
                        drag.setPixmap(pixmap)
                        drag.setHotSpot(QPoint(16, 16))  # Center hotspot
                except Exception:
                    # Fallback to default drag visual
                    pass
            
            # Set default action
            if hasattr(drag, "exec") and hasattr(supportedActions, "CopyAction"):
                drag.exec(supportedActions)
                
        except Exception as e:
            print(f"Error starting drag: {e}")
    
    def set_context(self, fs_manager, current_path):
        """Set the filesystem manager and current path for drag and drop operations.
        
        Args:
            fs_manager: FileSystemManager instance
            current_path: Current directory path
        """
        self._fs_manager = fs_manager
        self._current_path = current_path
            
    def dragEnterEvent(self, event):  # type: ignore[override]
        """Handle drag enter events to accept file URLs."""
        if hasattr(event.mimeData(), "hasUrls") and event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dragMoveEvent(self, event):  # type: ignore[override]
        """Handle drag move events to provide visual feedback."""
        if hasattr(event.mimeData(), "hasUrls") and event.mimeData().hasUrls():
            # Get the index at the current position
            index = self.indexAt(event.pos())
            
            # Accept if we're dropping directly on the view (not on an item)
            if not index.isValid():
                event.acceptProposedAction()
                return
                
            # Get the file path from the model
            model = self.model()
            if hasattr(model, "mapToSource"):
                source_index = model.mapToSource(index)
                file_model = model.sourceModel()
            else:
                source_index = index
                file_model = model
                
            # Get the path
            file_path = Path(file_model.filePath(source_index))
            
            # Accept if the target is a directory
            if file_path.is_dir():
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
            
    def dropEvent(self, event):  # type: ignore[override]
        """Handle drop events for both external and internal drags."""
        if not hasattr(event.mimeData(), "hasUrls") or not event.mimeData().hasUrls():
            event.ignore()
            return
            
        # Get the target path - either the item under the cursor or the current path
        target_path = self._current_path if hasattr(self, "_current_path") else None
        if target_path is None:
            # If no current path is set, we can't perform the drop operation
            event.ignore()
            return
            
        index = self.indexAt(event.pos())
        
        if index.isValid():
            # Get the file path from the model
            model = self.model()
            if hasattr(model, "mapToSource"):
                source_index = model.mapToSource(index)
                file_model = model.sourceModel()
            else:
                source_index = index
                file_model = model
                
            # Get the path
            try:
                file_path = Path(file_model.filePath(source_index))
                
                # If it's a directory, use it as the target
                if file_path.is_dir():
                    target_path = file_path
            except Exception:
                # If we can't get the file path, just use the current path
                pass
                
        # Check for internal drag (source paths within the explorer)
        fs_manager = self._fs_manager if hasattr(self, "_fs_manager") else None
        if fs_manager is not None and target_path is not None:
            # Try to handle with context menu
            if show_drop_context_menu(self, event, fs_manager, target_path):
                return
                
        # External drop (from outside the explorer)
        if target_path is not None:
            urls = event.mimeData().urls()
            for url in urls:
                path = Path(url.toLocalFile())
                if not path.exists():
                    continue
                    
                target = target_path / path.name
                if hasattr(self, "_fs_manager") and self._fs_manager is not None:
                    self._fs_manager.copy_path(path, target)
        
        event.acceptProposedAction()


class ViewFactory:
    """Factory for creating file views in different modes.
    
    This class implements the Factory pattern to create and configure
    different view types (grid, list, details) while hiding implementation
    details from the consumer. This follows Open/Closed principle by making
    it easy to add new view types without modifying existing code.
    """
    
    @staticmethod
    def create_grid_view(parent=None, model=None) -> Any:
        """Create a grid (icon) view for files.
        
        Args:
            parent: Parent widget
            model: Model to use for the view
            
        Returns:
            QListView configured for grid/icon mode
        """
        try:
            from PySide6.QtCore import Qt, QSize
            from PySide6.QtWidgets import QAbstractItemView
            
            view = DraggableListView(parent)
            if hasattr(view, "setViewMode") and hasattr(QListView, "IconMode"):
                view.setViewMode(QListView.IconMode)  # type: ignore[attr-defined]
                view.setIconSize(QSize(128, 128))
                if hasattr(QListView, "Adjust"):
                    view.setResizeMode(QListView.Adjust)  # type: ignore[attr-defined]
                view.setSpacing(12)
            if hasattr(view, "setSelectionMode") and hasattr(QAbstractItemView, "ExtendedSelection"):
                view.setSelectionMode(QAbstractItemView.ExtendedSelection)  # type: ignore[attr-defined]
            if hasattr(view, "setContextMenuPolicy") and hasattr(Qt, "CustomContextMenu"):
                view.setContextMenuPolicy(Qt.CustomContextMenu)  # type: ignore[attr-defined]
            if model is not None and hasattr(view, "setModel"):
                view.setModel(model)
            return view
        except ImportError:
            return None
    
    @staticmethod
    def create_list_view(parent=None, model=None) -> Any:
        """Create a simple list view for files.
        
        Args:
            parent: Parent widget
            model: Model to use for the view
            
        Returns:
            QTreeView configured for list mode
        """
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QAbstractItemView
            
            view = DraggableTreeView(parent)
            if hasattr(view, "setRootIsDecorated"):
                view.setRootIsDecorated(False)
            if hasattr(view, "setSortingEnabled"):
                view.setSortingEnabled(True)
            if hasattr(view, "setSelectionMode") and hasattr(QAbstractItemView, "ExtendedSelection"):
                view.setSelectionMode(QAbstractItemView.ExtendedSelection)  # type: ignore[attr-defined]
            if hasattr(view, "setContextMenuPolicy") and hasattr(Qt, "CustomContextMenu"):
                view.setContextMenuPolicy(Qt.CustomContextMenu)  # type: ignore[attr-defined]
            if model is not None and hasattr(view, "setModel"):
                view.setModel(model)
            return view
        except ImportError:
            return None
    
    @staticmethod
    def create_details_view(parent=None, model=None) -> Any:
        """Create a detailed list view with columns.
        
        Args:
            parent: Parent widget
            model: Model to use for the view
            
        Returns:
            QTreeView configured for detailed column view
        """
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QAbstractItemView, QHeaderView
            
            view = DraggableTreeView(parent)
            if hasattr(view, "setRootIsDecorated"):
                view.setRootIsDecorated(False)
            if hasattr(view, "setSortingEnabled"):
                view.setSortingEnabled(True)
            if hasattr(view, "setSelectionMode") and hasattr(QAbstractItemView, "ExtendedSelection"):
                view.setSelectionMode(QAbstractItemView.ExtendedSelection)  # type: ignore[attr-defined]
            if hasattr(view, "setContextMenuPolicy") and hasattr(Qt, "CustomContextMenu"):
                view.setContextMenuPolicy(Qt.CustomContextMenu)  # type: ignore[attr-defined]
            if hasattr(view, "header") and hasattr(view.header(), "setSectionResizeMode"):
                if hasattr(QHeaderView, "Stretch"):
                    view.header().setSectionResizeMode(0, QHeaderView.Stretch)  # type: ignore[attr-defined]
                if hasattr(QHeaderView, "ResizeToContents"):
                    view.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # type: ignore[attr-defined]
            if model is not None and hasattr(view, "setModel"):
                view.setModel(model)
                
                # Enable drag and drop capabilities
                ViewFactory._setup_drag_drop(view)
            return view
        except ImportError:
            return None
    
    @staticmethod
    def _setup_drag_drop(view):
        """Set up drag and drop capabilities for a view.
        
        Args:
            view: View to set up drag and drop for
        """
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QAbstractItemView
            
            if hasattr(view, "setDragEnabled"):
                view.setDragEnabled(True)
            if hasattr(view, "setAcceptDrops"):
                view.setAcceptDrops(True)
            if hasattr(view, "setDropIndicatorShown"):
                view.setDropIndicatorShown(True)
            if hasattr(view, "setDragDropMode") and hasattr(QAbstractItemView, "DragDrop"):
                view.setDragDropMode(QAbstractItemView.DragDrop)  # type: ignore[attr-defined]
            if hasattr(view, "setDefaultDropAction") and hasattr(Qt, "CopyAction"):
                view.setDefaultDropAction(Qt.CopyAction)  # type: ignore[attr-defined]
        except ImportError:
            pass


# ---------------------------------------------------------------------------
# Main Explorer widget
# ---------------------------------------------------------------------------


class ExplorerWidget(QWidget):  # type: ignore[misc]
    """Main Explorer widget with three-pane layout.
    
    This widget integrates the sidebar, content area, and details panel
    into a cohesive UI. It delegates filesystem operations to the FileSystemManager
    and UI construction to specialized builder methods.
    """
    
    def __init__(self, plugin, parent: Optional[QWidget] = None):  # type: ignore[override]
        """Initialize the Explorer widget.
        
        Args:
            plugin: The parent Explorer plugin
            parent: Optional parent widget
        """
        super().__init__(parent)
        if QFileSystemModel is cast(Any, object):
            raise RuntimeError("PySide6 ist nicht verfügbar.")
            
        # Store plugin reference
        self._plugin = plugin
        
        # Get plugin services if available
        self._services = plugin.services if hasattr(plugin, "services") else None
        
        # Create configuration manager (SRP - separates config from UI logic)
        self._config_manager = ConfigurationManager(self._services)
        
        # Create filesystem manager (SRP - separates filesystem logic from UI)
        self._fs_manager = FileSystemManager(self._services)
        
        # Setup file system model
        self._model = QFileSystemModel(self)  # type: ignore
        if hasattr(self._model, "setFilter"):
            from PySide6.QtCore import QDir  # type: ignore
            self._model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)  # type: ignore[attr-defined]
        
        # Set initial path (from saved config or default to home)
        last_dir = self._config_manager.get_last_directory()
        self._current_path = Path(last_dir) if last_dir and Path(last_dir).exists() else Path.home()
        if hasattr(self._model, "setRootPath"):
            self._model.setRootPath(str(self._current_path))

        # Setup search proxy model
        self._proxy = FuzzyFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.set_filesystem_manager(self._fs_manager)

        # Build UI and connect signals
        self._build_ui()
        
        # Create filter panel (hidden by default)
        self._init_filter_panel()
        
        self._connect_signals()
        self._populate_sidebar_from_config()
        self._set_directory(self._current_path)
        self._update_free_space()
        
        # Set initial view mode from config
        self._restore_view_preferences()
        
        # Initialize search functionality
        self._init_search_panel()
        
        # Apply styling
        if hasattr(self, "setStyleSheet"):
            self.setStyleSheet(self._stylesheet())

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the main UI layout by delegating to specialized component builders.
        
        This method follows the SRP (Single Responsibility Principle) by delegating
        specific UI component creation to dedicated methods, making the code more
        maintainable and easier to understand.
        """
        root_layout = QVBoxLayout(self)  # type: ignore
        if hasattr(root_layout, "setContentsMargins"):
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)

        # Build toolbar (breadcrumb, view controls, search)
        toolbar = self._build_toolbar()
        root_layout.addWidget(toolbar)
        
        # Create advanced filter button for toolbar
        if hasattr(QToolButton, "setCheckable"):
            self._filter_btn = QToolButton()
            self._filter_btn.setText("🔍 Filter")
            self._filter_btn.setToolTip("Erweiterte Filter ein-/ausblenden")
            self._filter_btn.setCheckable(True)
            self._filter_btn.setAutoRaise(True)
            
            # Add to toolbar (if toolbar has layout)
            if hasattr(toolbar, "layout") and toolbar.layout() is not None:
                toolbar_layout = toolbar.layout()
                if hasattr(toolbar_layout, "addWidget"):
                    toolbar_layout.addWidget(self._filter_btn)

        # Create main splitter with sidebar, content area, and details panel
        splitter = QSplitter()  # type: ignore
        if hasattr(splitter, "setChildrenCollapsible"):
            splitter.setChildrenCollapsible(False)
        root_layout.addWidget(splitter, 1)

        # Add sidebar with tree and disk health
        sidebar = self._build_sidebar()
        splitter.addWidget(sidebar)

        # Add main content area with stacked views
        main_container = self._build_content_area()
        splitter.addWidget(main_container)

        # Add details panel
        self._details_panel = DetailsPanel()
        splitter.addWidget(self._details_panel)

        # Configure splitter proportions
        if hasattr(splitter, "setStretchFactor"):
            splitter.setStretchFactor(0, 0)  # Sidebar: don't stretch
            splitter.setStretchFactor(1, 1)  # Content: stretch to fill
            splitter.setStretchFactor(2, 0)  # Details: don't stretch

        # Add status bar
        status = self._build_status_bar()
        root_layout.addWidget(status)
        
    def _build_toolbar(self) -> Any:  # Return QWidget when available
        """Create the toolbar with breadcrumb, view controls and search.
        
        Returns:
            QWidget: The toolbar container widget
        """
        toolbar = QWidget()  # type: ignore
        toolbar_layout = QHBoxLayout(toolbar)  # type: ignore
        if hasattr(toolbar_layout, "setContentsMargins"):
            toolbar_layout.setContentsMargins(8, 8, 8, 8)
            toolbar_layout.setSpacing(8)

        # Breadcrumb navigation
        self._breadcrumb = BreadcrumbBar()
        toolbar_layout.addWidget(self._breadcrumb, 1)

        # View mode buttons
        self._grid_btn = self._create_view_button("🔲", is_default=True)
        self._list_btn = self._create_view_button("📋")
        self._details_btn = self._create_view_button("📊")
        
        toolbar_layout.addWidget(self._grid_btn)
        toolbar_layout.addWidget(self._list_btn)
        toolbar_layout.addWidget(self._details_btn)

        # Sorting options
        self._sort_combo = QComboBox()  # type: ignore
        if hasattr(self._sort_combo, "addItems"):
            self._sort_combo.addItems(["Name", "Datum", "Größe", "Typ"])
        toolbar_layout.addWidget(self._sort_combo)

        # Search box for filtering
        self._search_edit = QLineEdit()  # type: ignore
        self._search_edit.setPlaceholderText("Dateiname filtern …") if hasattr(self._search_edit, "setPlaceholderText") else None
        toolbar_layout.addWidget(self._search_edit, 1)
        
        # Full-text search button
        self._search_btn = QPushButton("Volltextsuche")  # type: ignore
        if hasattr(self._search_btn, "setCheckable"):
            self._search_btn.setCheckable(True)
            self._search_btn.setToolTip("Volltextsuche ein-/ausblenden")
            try:
                from PySide6.QtGui import QIcon
                self._search_btn.setIcon(QIcon.fromTheme("search"))
            except (ImportError, TypeError):
                pass
        toolbar_layout.addWidget(self._search_btn)
        
        return toolbar
        
    def _create_view_button(self, text: str, is_default: bool = False) -> Any:  # Return QToolButton when available
        """Create a standardized view mode button.
        
        Args:
            text: The button text/icon
            is_default: Whether this is the default selected button
            
        Returns:
            QToolButton: Configured view mode button
        """
        button = QToolButton()  # type: ignore
        button.setText(text) if hasattr(button, "setText") else None
        button.setCheckable(True) if hasattr(button, "setCheckable") else None
        button.setChecked(is_default) if hasattr(button, "setChecked") else None
        return button
        
    def _build_sidebar(self) -> Any:  # Return QWidget when available
        """Create the sidebar with favorites tree and disk health widget.
        
        Returns:
            QWidget: The sidebar container widget
        """
        sidebar_container = QWidget()  # type: ignore
        sidebar_layout = QVBoxLayout(sidebar_container)  # type: ignore
        if hasattr(sidebar_layout, "setContentsMargins"):
            sidebar_layout.setContentsMargins(8, 8, 8, 8)
            sidebar_layout.setSpacing(6)

        # Navigation tree - use DraggableTreeView for drag and drop support
        self._sidebar_model = QFileSystemModel(self)  # type: ignore
        if hasattr(self._sidebar_model, "setFilter"):
            from PySide6.QtCore import QDir  # type: ignore
            self._sidebar_model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)  # type: ignore[attr-defined]
        if hasattr(self._sidebar_model, "setRootPath"):
            self._sidebar_model.setRootPath("")  # Show all drives/root
            
        self._sidebar = DraggableTreeView()  # type: ignore
        if hasattr(self._sidebar, "setHeaderHidden"):
            self._sidebar.setHeaderHidden(True)
        if hasattr(self._sidebar, "setObjectName"):
            self._sidebar.setObjectName("ExplorerSidebar")
        if hasattr(self._sidebar, "setModel"):
            self._sidebar.setModel(self._sidebar_model)
        sidebar_layout.addWidget(self._sidebar, 1)

        # Disk health monitor
        self._disk_health = DiskHealthWidget()
        sidebar_layout.addWidget(self._disk_health)
        
        return sidebar_container
        
    def _build_content_area(self) -> Any:
        """Create the main content area with stacked view modes.
        
        Uses the ViewFactory to create different view types, following
        the dependency inversion principle.
        
        Returns:
            QWidget: The content container widget
        """
        main_container = QWidget() if QWidget is not cast(Any, object) else None  # type: ignore
        main_layout = QVBoxLayout(main_container)  # type: ignore
        if hasattr(main_layout, "setContentsMargins"):
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)

        self._content_stack = QStackedWidget()  # type: ignore
        main_layout.addWidget(self._content_stack, 1)

        # Use ViewFactory to create views (Dependency Inversion Principle)
        # This decouples the view creation logic from the Explorer widget
        
        # Add grid view (icons)
        self._grid_view = ViewFactory.create_grid_view(self, self._proxy)
        if self._grid_view:
            self._content_stack.addWidget(self._grid_view)

        # Add list view (simple list)
        self._list_view = ViewFactory.create_list_view(self, self._proxy)
        if self._list_view:
            self._content_stack.addWidget(self._list_view)

        # Add details view (with columns)
        self._details_view = ViewFactory.create_details_view(self, self._proxy)
        if self._details_view:
            self._content_stack.addWidget(self._details_view)
        
        return main_container
        
    def _build_status_bar(self) -> Any:  # Return QWidget when available
        """Create the status bar with selection info and buttons.
        
        Returns:
            QWidget: The status bar container widget
        """
        status = QWidget()  # type: ignore
        status_layout = QHBoxLayout(status)  # type: ignore
        if hasattr(status_layout, "setContentsMargins"):
            status_layout.setContentsMargins(8, 4, 8, 4)
            status_layout.setSpacing(16)

        # Selection status
        self._selection_label = QLabel("0 Objekte ausgewählt (0 B)")  # type: ignore
        self._space_label = QLabel("Freier Speicher: –")  # type: ignore
        
        # Settings button
        self._settings_btn = QPushButton("⚙️ Einstellungen")  # type: ignore
        
        status_layout.addWidget(self._selection_label)
        status_layout.addWidget(self._space_label)
        status_layout.addStretch(1)
        status_layout.addWidget(self._settings_btn)
        
        return status

    def _stylesheet(self) -> str:
        return (
            f"QWidget#ExplorerSidebar{{background:{BG_SECONDARY};color:{TEXT_PRIMARY};}}"
            f"QWidget{{background:{BG_PRIMARY};color:{TEXT_PRIMARY};}}"
            f"QLineEdit{{background:{BG_TERTIARY};border:1px solid {BORDER_COLOR};padding:4px;border-radius:4px;}}"
            f"QToolButton{{background:{BG_TERTIARY};border:1px solid {BORDER_COLOR};border-radius:4px;padding:4px;}}"
            f"QToolButton:checked{{background:{ACCENT_PRIMARY};border-color:{ACCENT_PRIMARY};}}"
            f"QToolButton:hover{{background:{ACCENT_HOVER};}}"
            f"QComboBox{{background:{BG_TERTIARY};border:1px solid {BORDER_COLOR};padding:4px;border-radius:4px;}}"
            f"QPushButton{{background:{ACCENT_PRIMARY};border:1px solid {ACCENT_PRIMARY};border-radius:4px;padding:6px 12px;}}"
            f"QPushButton:hover{{background:{ACCENT_HOVER};border-color:{ACCENT_HOVER};}}"
            f"#ExplorerPreview{{border:1px solid {BORDER_COLOR};border-radius:6px;padding:12px;}}"
        )

    def _connect_signals(self) -> None:
        # Connect signals safely by checking if they exist first
        if hasattr(self._breadcrumb, "path_selected") and self._breadcrumb.path_selected is not None:
            self._breadcrumb.path_selected.connect(self._set_directory)  # type: ignore[attr-defined]
        
        if hasattr(self._grid_btn, "clicked"):
            self._grid_btn.clicked.connect(lambda: self._set_view_mode(0))  # type: ignore[attr-defined]
            
        if hasattr(self._list_btn, "clicked"):
            self._list_btn.clicked.connect(lambda: self._set_view_mode(1))  # type: ignore[attr-defined]
            
        if hasattr(self._details_btn, "clicked"):
            self._details_btn.clicked.connect(lambda: self._set_view_mode(2))  # type: ignore[attr-defined]
        if hasattr(self._search_edit, "textChanged"):
            self._search_edit.textChanged.connect(self._proxy.set_search_pattern)  # type: ignore[attr-defined]
            
        # Connect search button if available
        if hasattr(self, "_search_btn") and hasattr(self._search_btn, "toggled"):
            self._search_btn.toggled.connect(self._toggle_search_panel)
            
        if hasattr(self._sort_combo, "currentIndexChanged"):
            self._sort_combo.currentIndexChanged.connect(self._apply_sort)  # type: ignore[attr-defined]
            
        if hasattr(self._grid_view, "doubleClicked"):
            self._grid_view.doubleClicked.connect(self._open_index)  # type: ignore[attr-defined]
            
        if hasattr(self._list_view, "doubleClicked"):
            self._list_view.doubleClicked.connect(self._open_index)  # type: ignore[attr-defined]
            
        if hasattr(self._details_view, "doubleClicked"):
            self._details_view.doubleClicked.connect(self._open_index)  # type: ignore[attr-defined]
        # Connect context menu signals safely
        if hasattr(self._grid_view, "customContextMenuRequested"):
            self._grid_view.customContextMenuRequested.connect(self._show_context_menu)  # type: ignore[attr-defined]
            
        if hasattr(self._list_view, "customContextMenuRequested"):
            self._list_view.customContextMenuRequested.connect(self._show_context_menu)  # type: ignore[attr-defined]
            
        if hasattr(self._details_view, "customContextMenuRequested"):
            self._details_view.customContextMenuRequested.connect(self._show_context_menu)  # type: ignore[attr-defined]
        
        # Connect selection model signals safely
        if hasattr(self._grid_view, "selectionModel") and self._grid_view.selectionModel() is not None:
            self._grid_view.selectionModel().selectionChanged.connect(self._update_selection)  # type: ignore[attr-defined]
            
        if hasattr(self._list_view, "selectionModel") and self._list_view.selectionModel() is not None:
            self._list_view.selectionModel().selectionChanged.connect(self._update_selection)  # type: ignore[attr-defined]
            
        if hasattr(self._details_view, "selectionModel") and self._details_view.selectionModel() is not None:
            self._details_view.selectionModel().selectionChanged.connect(self._update_selection)  # type: ignore[attr-defined]
        
        # Connect sidebar and settings signals
        if hasattr(self._sidebar, "itemActivated"):
            self._sidebar.itemActivated.connect(self._on_sidebar_item)  # type: ignore[attr-defined]
            
        if hasattr(self._settings_btn, "clicked"):
            self._settings_btn.clicked.connect(self._open_settings_dialog)  # type: ignore[attr-defined]

    def _set_view_mode(self, index: int) -> None:
        if hasattr(self._content_stack, "setCurrentIndex"):
            self._content_stack.setCurrentIndex(index)
        if hasattr(self._grid_btn, "setChecked"):
            self._grid_btn.setChecked(index == 0)
        if hasattr(self._list_btn, "setChecked"):
            self._list_btn.setChecked(index == 1)
        if hasattr(self._details_btn, "setChecked"):
            self._details_btn.setChecked(index == 2)

    def _apply_sort(self, index: int) -> None:
        column_map = {0: 0, 1: 3, 2: 1, 3: 2}
        column = column_map.get(index, 0)
        order = Qt.AscendingOrder if hasattr(Qt, "AscendingOrder") else 0  # type: ignore[attr-defined]
        if hasattr(self._list_view, "sortByColumn"):
            self._list_view.sortByColumn(column, order)
        if hasattr(self._details_view, "sortByColumn"):
            self._details_view.sortByColumn(column, order)

    def _open_index(self, index: QModelIndex) -> None:  # type: ignore[override]
        source_index = self._proxy.mapToSource(index) if hasattr(self._proxy, "mapToSource") else index
        path = Path(self._model.filePath(source_index)) if hasattr(self._model, "filePath") else Path.home()  # type: ignore
        if path.is_dir():
            self._set_directory(path)
            return
        try:
            QDesktopServices.openUrl(path.as_uri())  # type: ignore[attr-defined]
        except Exception:
            QMessageBox.warning(self, "Fehler", "Datei konnte nicht geöffnet werden.")  # type: ignore

    def _update_selection(self, *_args) -> None:
        view = self._current_view()
        selection = view.selectionModel().selectedRows() if hasattr(view, "selectionModel") else []  # type: ignore[attr-defined]
        total_size = 0
        paths: list[Path] = []
        for index in selection:
            source = self._proxy.mapToSource(index) if hasattr(self._proxy, "mapToSource") else index
            path = Path(self._model.filePath(source)) if hasattr(self._model, "filePath") else Path.home()  # type: ignore
            paths.append(path)
            if path.is_file():
                info = _safe_stat(path)
                if info:
                    total_size += info.st_size
        if hasattr(self._selection_label, "setText"):
            self._selection_label.setText(f"{len(paths)} Objekte ausgewählt ({_human_size(total_size)})")
        if len(paths) == 1:
            self._details_panel.update_for_path(paths[0])
        elif not paths:
            self._details_panel.clear()

    def _current_view(self):
        index = self._content_stack.currentIndex() if hasattr(self._content_stack, "currentIndex") else 0  # type: ignore[attr-defined]
        return {0: self._grid_view, 1: self._list_view, 2: self._details_view}.get(index, self._grid_view)

    def _show_context_menu(self, position: QPoint) -> None:  # type: ignore[override]
        view = self._current_view()
        index = view.indexAt(position) if hasattr(view, "indexAt") else QModelIndex()  # type: ignore[attr-defined]
        if not hasattr(index, "isValid") or not index.isValid():  # type: ignore[attr-defined]
            return
        source_index = self._proxy.mapToSource(index) if hasattr(self._proxy, "mapToSource") else index
        path = Path(self._model.filePath(source_index)) if hasattr(self._model, "filePath") else Path.home()  # type: ignore

        menu = QMenu(self)  # type: ignore
        
        # Basic file operations
        menu.addAction("Öffnen", lambda: self._open_path(path))
        
        # File operations submenu
        file_menu = QMenu("Dateioperationen", menu)  # type: ignore
        file_menu.addAction("Kopieren", lambda: self._copy_path(path))
        file_menu.addAction("Ausschneiden", lambda: self._cut_path(path))
        file_menu.addAction("Einfügen", lambda: self._paste_path(self._current_dir))
        file_menu.addSeparator()
        file_menu.addAction("Löschen", lambda: self._delete_path(path))
        file_menu.addSeparator()
        file_menu.addAction("Umbenennen", lambda: self._rename_path(path))
        menu.addMenu(file_menu)
        
        menu.addSeparator()
        
        # Advanced operations
        menu.addAction("Duplikate finden", lambda: self._delegate_action("duplicate", path))
        menu.addAction("Backup erstellen", lambda: self._delegate_action("backup", path))
        
        menu.addSeparator()
        
        # Utilities
        menu.addAction("In Ordner anzeigen", lambda: self._reveal_path(path))
        menu.addAction("Eigenschaften", lambda: self._details_panel.update_for_path(path))
        viewport = view.viewport() if hasattr(view, "viewport") else None
        if viewport and hasattr(viewport, "mapToGlobal") and hasattr(menu, "exec"):
            menu.exec(viewport.mapToGlobal(position))

    def _open_path(self, path: Path) -> None:
        if path.is_dir():
            self._set_directory(path)
            return
        try:
            QDesktopServices.openUrl(path.as_uri())  # type: ignore[attr-defined]
        except Exception:
            QMessageBox.warning(self, "Fehler", "Datei konnte nicht geöffnet werden.")  # type: ignore

    def _rename_path(self, path: Path) -> None:
        if not path.exists() or QInputDialog in (None, object):
            return
        new_name, ok = QInputDialog.getText(self, "Umbenennen", "Neuer Name", text=path.name)  # type: ignore[attr-defined]
        if not ok or not new_name:
            return
        target = path.with_name(new_name)
        try:
            path.rename(target)
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", f"Umbenennen fehlgeschlagen: {exc}")  # type: ignore
        if hasattr(self._model, "refresh"):
            self._model.refresh()

    # Clipboard operations for file management
    _clipboard_path: Optional[Path] = None
    _clipboard_operation: str = ""  # 'copy' or 'cut'
    
    def _copy_path(self, path: Path) -> None:
        """Copy a file or folder path to the clipboard."""
        if not path.exists():
            return
        
        ExplorerWidget._clipboard_path = path
        ExplorerWidget._clipboard_operation = "copy"
        
        try:
            self._plugin.services.send_notification(  # type: ignore[attr-defined]
                f"{path.name} in die Zwischenablage kopiert",
                level="info",
                source=self._plugin.manifest.identifier,  # type: ignore[attr-defined]
            )
        except Exception:
            pass

    def _cut_path(self, path: Path) -> None:
        """Cut a file or folder path to the clipboard."""
        if not path.exists():
            return
        
        ExplorerWidget._clipboard_path = path
        ExplorerWidget._clipboard_operation = "cut"
        
        try:
            self._plugin.services.send_notification(  # type: ignore[attr-defined]
                f"{path.name} ausgeschnitten (in Zwischenablage)",
                level="info",
                source=self._plugin.manifest.identifier,  # type: ignore[attr-defined]
            )
        except Exception:
            pass

    def _paste_path(self, target_dir: Path) -> None:
        """Paste a previously copied or cut file/folder to the target directory."""
        if not target_dir.is_dir() or not ExplorerWidget._clipboard_path:
            return
            
        source = ExplorerWidget._clipboard_path
        if not source.exists():
            QMessageBox.warning(self, "Fehler", "Die Quelldatei existiert nicht mehr.")  # type: ignore
            return
            
        target = target_dir / source.name
        
        if target.exists():
            if QMessageBox in (None, object):
                return
            response = QMessageBox.question(  # type: ignore[attr-defined]
                self, 
                "Datei existiert bereits",
                f"{target.name} existiert bereits. Überschreiben?",
                QMessageBox.Yes | QMessageBox.No,  # type: ignore[attr-defined]
            )
            if response != QMessageBox.Yes:  # type: ignore[attr-defined]
                return
        
        try:
            operation = ExplorerWidget._clipboard_operation
            import shutil
            
            if operation == "copy":
                if source.is_dir():
                    shutil.copytree(source, target)
                else:
                    shutil.copy2(source, target)
                self._plugin.services.send_notification(  # type: ignore[attr-defined]
                    f"{source.name} nach {target_dir.name} kopiert",
                    level="info",
                    source=self._plugin.manifest.identifier,  # type: ignore[attr-defined]
                )
            elif operation == "cut":
                if target.exists():
                    target.unlink() if target.is_file() else shutil.rmtree(target)
                source.rename(target)
                ExplorerWidget._clipboard_path = None  # Clear after cut+paste
                ExplorerWidget._clipboard_operation = ""
                self._plugin.services.send_notification(  # type: ignore[attr-defined]
                    f"{source.name} nach {target_dir.name} verschoben",
                    level="info",
                    source=self._plugin.manifest.identifier,  # type: ignore[attr-defined]
                )
                
            # Refresh the model to show changes
            if hasattr(self._model, "refresh"):
                self._model.refresh()
                
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", f"Einfügen fehlgeschlagen: {exc}")  # type: ignore

    def _delete_path(self, path: Path) -> None:
        """Delete a file or folder."""
        if not path.exists():
            return
            
        if QMessageBox in (None, object):
            return
        
        # Ask for confirmation
        response = QMessageBox.question(  # type: ignore[attr-defined]
            self, 
            "Löschen bestätigen",
            f"Möchten Sie '{path.name}' wirklich löschen?",
            QMessageBox.Yes | QMessageBox.No,  # type: ignore[attr-defined]
        )
        if response != QMessageBox.Yes:  # type: ignore[attr-defined]
            return
            
        try:
            # Try to use send2trash if available for safer deletion
            try:
                import send2trash
                send2trash.send2trash(str(path))
                deletion_type = "in Papierkorb verschoben"
            except ImportError:
                # Fallback to permanent deletion if send2trash is not available
                import shutil
                path.unlink() if path.is_file() else shutil.rmtree(path)
                deletion_type = "gelöscht"
                
            self._plugin.services.send_notification(  # type: ignore[attr-defined]
                f"{path.name} {deletion_type}",
                level="info",
                source=self._plugin.manifest.identifier,  # type: ignore[attr-defined]
            )
            
            # Refresh the model to show changes
            if hasattr(self._model, "refresh"):
                self._model.refresh()
                
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", f"Löschen fehlgeschlagen: {exc}")  # type: ignore

    def _delegate_action(self, action: str, path: Path) -> None:
        try:
            self._plugin.services.send_notification(  # type: ignore[attr-defined]
                f"{action.title()} für {path.name} wird vorbereitet…",
                level="info",
                source=self._plugin.manifest.identifier,
            )
        except Exception:
            pass

    def _reveal_path(self, path: Path) -> None:
        system = platform.system().lower()
        try:
            if system == "windows":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif system == "darwin":
                os.system(f"open '{path}'")
            else:
                os.system(f"xdg-open '{path}'")
        except Exception:
            QMessageBox.warning(self, "Fehler", "Pfad konnte nicht geöffnet werden.")  # type: ignore

    def _set_directory(self, path: Path) -> None:
        if not path.exists():
            return
        self._current_path = path
        root_index = self._model.index(str(path)) if hasattr(self._model, "index") else QModelIndex()  # type: ignore[attr-defined]
        proxy_index = self._proxy.mapFromSource(root_index) if hasattr(self._proxy, "mapFromSource") else root_index
        for view in (self._grid_view, self._list_view, self._details_view):
            if hasattr(view, "setRootIndex"):
                view.setRootIndex(proxy_index)
            
            # Update drag and drop context for the view
            if hasattr(view, "set_context"):
                view.set_context(self._fs_manager, path)
                
        # Also set the context for the sidebar tree
        if hasattr(self._sidebar, "set_context"):
            self._sidebar.set_context(self._fs_manager, path.parent if path != Path.home() else path)
                
        self._breadcrumb.set_path(path)
        self._update_free_space()

    def _populate_sidebar_from_config(self) -> None:
        """Populate sidebar with favorites from configuration and system locations.
        
        This follows the Single Responsibility Principle by delegating configuration
        loading to the ConfigurationManager class.
        """
        if not hasattr(self._sidebar, "clear"):
            return
            
        self._sidebar.clear()
        
        # Quick Access section
        quick_root = QTreeWidgetItem(["Schnellzugriff"])  # type: ignore
        if hasattr(quick_root, "setFlags") and hasattr(Qt, "ItemIsSelectable"):
            quick_root.setFlags(quick_root.flags() & ~Qt.ItemIsSelectable)  # type: ignore[attr-defined]
            
        # Add favorites from configuration
        for favorite in self._config_manager.get_favorites():
            try:
                path_str = favorite.get("path")
                name = favorite.get("name", "")
                icon = favorite.get("icon", "📁")
                
                # Skip if path is invalid
                if not path_str:
                    continue
                    
                path = Path(path_str)
                label = f"{icon} {name}"
                
                item = QTreeWidgetItem([label])  # type: ignore
                item.setData(0, Qt.UserRole, path) if hasattr(item, "setData") else None  # type: ignore[attr-defined]
                quick_root.addChild(item)
            except Exception:
                # Skip invalid entries
                continue
                
        self._sidebar.addTopLevelItem(quick_root)

        # Devices section
        devices_root = QTreeWidgetItem(["Dieser PC"])  # type: ignore
        if hasattr(devices_root, "setFlags") and hasattr(Qt, "ItemIsSelectable"):
            devices_root.setFlags(devices_root.flags() & ~Qt.ItemIsSelectable)  # type: ignore[attr-defined]
            
        # Add drives (these aren't stored in config since they're dynamic)
        for label, target in self._drive_entries():
            item = QTreeWidgetItem([label])  # type: ignore
            item.setData(0, Qt.UserRole, target) if hasattr(item, "setData") else None  # type: ignore[attr-defined]
            devices_root.addChild(item)
            
        self._sidebar.addTopLevelItem(devices_root)
        
        # Expand all tree items
        if hasattr(self._sidebar, "expandAll"):
            self._sidebar.expandAll()
            
    def _restore_view_preferences(self) -> None:
        """Restore view mode and sort settings from configuration."""
        # Set view mode from configuration
        view_mode = self._config_manager.get_view_mode()
        if view_mode == "grid":
            self._set_view_mode(0)
        elif view_mode == "list":
            self._set_view_mode(1)
        elif view_mode == "details":
            self._set_view_mode(2)
            
        # Set sort mode from configuration
        sort_mode = self._config_manager.get_sort_mode()
        sort_index = {"name": 0, "date": 1, "size": 2, "type": 3}.get(sort_mode, 0)
        if hasattr(self._sort_combo, "setCurrentIndex"):
            self._sort_combo.setCurrentIndex(sort_index)
        self._apply_sort(sort_index)

    def _init_filter_panel(self):
        """Initialize and set up the filter panel."""
        if not FilterPanel or not isinstance(FilterPanel, type):
            return
        
        # Create filter panel
        self._filter_panel = FilterPanel(self)
        
        # Add to main layout, initially hidden
        if hasattr(self.layout(), "addWidget"):
            self.layout().addWidget(self._filter_panel)
            if hasattr(self._filter_panel, "setVisible"):
                self._filter_panel.setVisible(False)
                
        # Connect filter panel signals
        if hasattr(self._filter_panel, "filter_changed"):
            self._filter_panel.filter_changed.connect(self._on_filter_criteria_changed)
            
        # Connect filter button toggle
        if hasattr(self, "_filter_btn") and hasattr(self._filter_btn, "toggled"):
            self._filter_btn.toggled.connect(self._toggle_filter_panel)
    
    def _toggle_filter_panel(self, checked):
        """Toggle visibility of the filter panel.
        
        Args:
            checked: Whether the filter button is checked
        """
        if hasattr(self, "_filter_panel") and hasattr(self._filter_panel, "setVisible"):
            self._filter_panel.setVisible(checked)
    
    def _on_filter_criteria_changed(self, criteria):
        """Handle changes to filter criteria.
        
        Args:
            criteria: New FilterCriteria object
        """
        if hasattr(self._proxy, "set_filter_criteria"):
            self._proxy.set_filter_criteria(criteria)
    
    def _toggle_search_panel(self, checked):
        """Toggle visibility of the search panel.
        
        Args:
            checked: Whether the search button is checked
        """
        if hasattr(self, "_search_panel") and self._search_panel is not None:
            # Only try to toggle visibility if the search panel exists
            if hasattr(self._search_panel, "setVisible"):
                self._search_panel.setVisible(checked)
                
                # Set directory if needed
                if checked and hasattr(self._search_panel, "set_directory"):
                    self._search_panel.set_directory(self._current_path)
            
    def _init_search_panel(self):
        """Initialize and set up the search panel.
        
        This method imports and integrates the search functionality into the Explorer widget.
        """
        try:
            # Import search integration dynamically
            from .search_integration import integrate_search, HAS_PYSIDE6
            
            # Skip if PySide6 is not available
            if not HAS_PYSIDE6:
                # Log warning if search functionality is not available
                logger = logging.getLogger("mmst.explorer")
                logger.warning("Search functionality not available, PySide6 not found")
                return
                
            # Create and integrate the search panel
            self._search_panel = integrate_search(self)
            
            # Store the search panel for later use
            if self._search_panel is not None and hasattr(self._search_panel, "set_directory"):
                self._search_panel.set_directory(self._current_path)
        except ImportError:
            # Log warning if search functionality is not available
            logger = logging.getLogger("mmst.explorer")
            logger.warning("Search functionality not available, missing dependencies")
            
            # Try to notify the user through services if available
            if hasattr(self._plugin, "services") and hasattr(self._plugin.services, "send_notification"):
                self._plugin.services.send_notification(
                    "Suchfunktion nicht verfügbar, fehlende Abhängigkeiten",
                    level="warning",
                    source=self._plugin.manifest.identifier
                )
    
    def _drive_entries(self) -> list[tuple[str, Path]]:
        entries: list[tuple[str, Path]] = []
        system = platform.system().lower()
        if system == "windows":
            from string import ascii_uppercase

            for letter in ascii_uppercase:
                drive = Path(f"{letter}:/")
                if drive.exists():
                    usage = self._disk_usage(drive)
                    label = f"{letter}: ({_human_size(usage.total)})" if usage else f"{letter}:"
                    entries.append((label, drive))
        else:
            for mount in (Path("/"), Path("/home"), Path("/media"), Path("/mnt")):
                if mount.exists():
                    usage = self._disk_usage(mount)
                    label = f"{mount} ({_human_size(usage.total)})" if usage else str(mount)
                    entries.append((label, mount))
        return entries

    def _disk_usage(self, path: Path):
        try:
            return shutil.disk_usage(str(path))
        except Exception:
            return None

    def _recycle_bin_path(self) -> Optional[Path]:
        system = platform.system().lower()
        if system == "windows":
            return Path.home() / "AppData/Roaming/Microsoft/Windows/Recent"
        if system == "darwin":
            return Path.home() / ".Trash"
        return Path.home() / ".local/share/Trash"

    def _update_free_space(self) -> None:
        usage = self._disk_usage(self._current_path)
        if hasattr(self._space_label, "setText"):
            if usage:
                self._space_label.setText(
                    f"Freier Speicher: {_human_size(usage.free)} von {_human_size(usage.total)}"
                )
            else:
                self._space_label.setText("Freier Speicher: –")

    def _on_sidebar_item(self, item: QTreeWidgetItem, _column: int) -> None:  # type: ignore[override]
        target = item.data(0, Qt.UserRole) if hasattr(item, "data") else None  # type: ignore[attr-defined]
        if isinstance(target, Path):
            self._set_directory(target)

    def _open_settings_dialog(self) -> None:
        QMessageBox.information(self, "Explorer", "Weitere Einstellungen folgen demnächst.")  # type: ignore

    def dragEnterEvent(self, event):  # type: ignore[override]
        if hasattr(event, "mimeData") and event.mimeData().hasUrls():  # type: ignore[attr-defined]
            event.acceptProposedAction()  # type: ignore[attr-defined]
            
    def dragMoveEvent(self, event):  # type: ignore[override]
        """Handle drag move events to provide feedback when dragging over valid drop targets."""
        if not hasattr(event, "mimeData") or not hasattr(event.mimeData(), "hasUrls"):
            return
            
        if event.mimeData().hasUrls():  # type: ignore[attr-defined]
            # Check if the target is a directory or an empty area
            event.acceptProposedAction()  # type: ignore[attr-defined]
            
    def dragLeaveEvent(self, event):  # type: ignore[override]
        """Handle drag leave events."""
        if hasattr(event, "accept"):
            event.accept()  # type: ignore[attr-defined]

    def dropEvent(self, event):  # type: ignore[override]
        """Handle drop events for both external and internal drags."""
        if not hasattr(event, "mimeData") or not hasattr(event.mimeData(), "hasUrls"):
            return
            
        urls = event.mimeData().urls()  # type: ignore[attr-defined]
        
        # Check for internal drag (source paths within the explorer)
        if hasattr(event.mimeData(), "hasFormat") and event.mimeData().hasFormat("application/x-mmst-explorer-paths"):  # type: ignore[attr-defined]
            # This is an internal drag operation
            source_paths_data = event.mimeData().data("application/x-mmst-explorer-paths")  # type: ignore[attr-defined]
            
            # Show context menu to let the user decide copy or move
            menu = QMenu(self)  # type: ignore
            menu.addAction("Kopieren", lambda: self._process_internal_drop(urls, "copy"))
            menu.addAction("Verschieben", lambda: self._process_internal_drop(urls, "move"))
            menu.addAction("Abbrechen", lambda: None)
            
            viewport = self.viewport() if hasattr(self, "viewport") else self
            if hasattr(viewport, "mapToGlobal") and hasattr(event, "pos") and hasattr(menu, "exec"):
                pos = viewport.mapToGlobal(event.pos())  # type: ignore[attr-defined]
                menu.exec(pos)  # type: ignore[attr-defined]
            event.accept()  # type: ignore[attr-defined]
            return
            
        # External drop (from outside the explorer)
        for url in urls:
            path = Path(url.toLocalFile())  # type: ignore[attr-defined]
            if not path.exists():
                continue
                
            target = self._current_path / path.name
            success = self._fs_manager.copy_path(path, target)
            
            if success and hasattr(self._plugin, "services") and hasattr(self._plugin.services, "send_notification"):
                self._plugin.services.send_notification(  # type: ignore[attr-defined]
                    f"{path.name} nach {self._current_path.name} kopiert",
                    level="info",
                    source=self._plugin.manifest.identifier,  # type: ignore[attr-defined]
                )
            
        if hasattr(self._model, "refresh"):
            self._model.refresh()
            
    def _process_internal_drop(self, urls, operation="copy"):
        """Process an internal drag and drop operation.
        
        Args:
            urls: List of QUrls to process
            operation: Operation to perform ("copy" or "move")
        """
        success_count = 0
        fail_count = 0
        
        for url in urls:
            path = Path(url.toLocalFile())  # type: ignore[attr-defined]
            if not path.exists():
                continue
                
            # Don't move/copy to the same directory
            if path.parent == self._current_path:
                continue
                
            target = self._current_path / path.name
            
            # Skip if target is a subdirectory of source (would create infinite recursion)
            if path.is_dir() and target.is_relative_to(path):
                if hasattr(self._plugin, "services") and hasattr(self._plugin.services, "send_notification"):
                    self._plugin.services.send_notification(  # type: ignore[attr-defined]
                        f"Kann {path.name} nicht in einen Unterordner von sich selbst verschieben",
                        level="error",
                        source=self._plugin.manifest.identifier,  # type: ignore[attr-defined]
                    )
                continue
                
            success = False
            if operation == "copy":
                success = self._fs_manager.copy_path(path, target)
            elif operation == "move":
                success = self._fs_manager.move_path(path, target)
                
            if success:
                success_count += 1
            else:
                fail_count += 1
                
        # Report results
        if hasattr(self._plugin, "services") and hasattr(self._plugin.services, "send_notification"):
            op_name = "kopiert" if operation == "copy" else "verschoben"
            
            if success_count > 0 and fail_count == 0:
                self._plugin.services.send_notification(  # type: ignore[attr-defined]
                    f"{success_count} Elemente erfolgreich {op_name}",
                    level="info",
                    source=self._plugin.manifest.identifier,  # type: ignore[attr-defined]
                )
            elif success_count > 0 and fail_count > 0:
                self._plugin.services.send_notification(  # type: ignore[attr-defined]
                    f"{success_count} Elemente {op_name}, {fail_count} fehlgeschlagen",
                    level="warning",
                    source=self._plugin.manifest.identifier,  # type: ignore[attr-defined]
                )
            elif fail_count > 0:
                self._plugin.services.send_notification(  # type: ignore[attr-defined]
                    f"Fehler beim {op_name} von {fail_count} Elementen",
                    level="error",
                    source=self._plugin.manifest.identifier,  # type: ignore[attr-defined]
                )
                
        if hasattr(self._model, "refresh"):
            self._model.refresh()


__all__ = [
    "ExplorerWidget",
    "BreadcrumbBar",
    "FuzzyFilterProxyModel",
    "DiskHealthWidget",
    "DetailsPanel",
]
