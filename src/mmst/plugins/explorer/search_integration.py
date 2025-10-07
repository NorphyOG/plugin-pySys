from __future__ import annotations

"""Integration module for Explorer search functionality.

This module integrates the search panel into the Explorer widget.
"""

import logging
from pathlib import Path
from typing import Any, Optional, cast

# Import search engine
from .search_engine import SearchEngine

# Check if PySide6 is available
HAS_PYSIDE6 = False
try:
    import PySide6
    HAS_PYSIDE6 = True
except ImportError:
    pass

# Define Qt components based on PySide6 availability
if HAS_PYSIDE6:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QPushButton
else:
    # Create dummy Qt classes
    class DummyEnum:
        UserRole = 0
        DisplayRole = 0
    
    class DummyQt:
        ItemDataRole = DummyEnum()
        Orientation = DummyEnum()
    
    Qt = DummyQt()
    QIcon = None
    
    class DummyPushButton:
        class DummySignal:
            def connect(self, func):
                pass
                
        def __init__(self, *args, **kwargs):
            self._tooltip = None
            self._checkable = False
            self._icon = None
            self._checked = False
            self.toggled = self.DummySignal()
            
        def setCheckable(self, value):
            self._checkable = value
            
        def setIcon(self, icon):
            self._icon = icon
            
        def setToolTip(self, text):
            self._tooltip = text
            
        def setChecked(self, checked):
            self._checked = checked
    
    QPushButton = DummyPushButton

# Always import SearchPanel - it handles its own PySide6 dependency
from .search_panel import SearchPanel

def integrate_search(explorer_widget):
    """Integrate search panel into the Explorer widget.
    
    Args:
        explorer_widget: The ExplorerWidget instance
    
    Returns:
        The integrated SearchPanel instance or None if integration fails
    """
    # Skip if no PySide6 or explorer_widget has no layout
    if not HAS_PYSIDE6 or not hasattr(explorer_widget, 'layout'):
        return None
    
    # Create the search panel
    search_panel = SearchPanel(explorer_widget)
    
    # Add to main layout, initially hidden
    explorer_widget.layout().addWidget(search_panel)
    search_panel.setVisible(False)
    
    # Add search button to toolbar if it exists
    if hasattr(explorer_widget, '_toolbar'):
        # Create search button
        search_btn = QPushButton("Volltextsuche")
        search_btn.setCheckable(True)
        
        # Set icon if QIcon is available
        if QIcon:
            search_btn.setIcon(QIcon.fromTheme("search"))
            
        search_btn.setToolTip("Volltextsuche ein-/ausblenden")
        
        # Add to toolbar
        explorer_widget._toolbar.addWidget(search_btn)
        
        # Connect toggle using PySide6-specific code
        search_btn.toggled.connect(
            lambda checked: handle_toggle_search(explorer_widget, search_panel, checked)
        )
    
    # Connect signal for opening files
    if hasattr(search_panel, "result_selected") and search_panel.result_selected is not None:
        search_panel.result_selected.connect(
            lambda file_path, line_number: handle_open_file(explorer_widget, file_path, line_number)
        )
    
    return search_panel

def handle_toggle_search(explorer_widget, search_panel, checked):
    """Handler for toggling search panel visibility.
    
    Args:
        explorer_widget: The ExplorerWidget instance
        search_panel: The SearchPanel instance
        checked: Whether the button is checked
    """
    if search_panel is not None:
        search_panel.setVisible(checked)
        
        # Update current directory when showing the panel
        if checked and hasattr(search_panel, "set_directory") and hasattr(explorer_widget, "_current_path"):
            search_panel.set_directory(explorer_widget._current_path)

def handle_open_file(explorer_widget, file_path, line_number):
    """Handler for opening a file at a specific line.
    
    Args:
        explorer_widget: The ExplorerWidget instance
        file_path: Path to the file
        line_number: Line number to navigate to
    """
    # First, make sure we're in the right directory
    if hasattr(explorer_widget, "_set_directory") and hasattr(explorer_widget, "_current_path"):
        if file_path.parent != explorer_widget._current_path:
            explorer_widget._set_directory(file_path.parent)
    
    # Then find and select the file in the file list
    if hasattr(explorer_widget, "_model") and hasattr(explorer_widget, "_proxy"):
        index = find_model_index_by_path(explorer_widget, file_path)
        if index is not None and hasattr(explorer_widget, "_open_index"):
            explorer_widget._open_index(index)
    
    # Notify about the line number (in a real integration, this would navigate to the line)
    if hasattr(explorer_widget, "_plugin") and hasattr(explorer_widget._plugin, "services"):
        if hasattr(explorer_widget._plugin.services, "send_notification"):
            explorer_widget._plugin.services.send_notification(
                f"Geöffnet: {file_path.name}, Zeile {line_number}", 
                level="info",
                source=explorer_widget._plugin.manifest.identifier
            )

def find_model_index_by_path(explorer_widget, file_path):
    """Find a model index for a specific file path.
    
    Args:
        explorer_widget: The ExplorerWidget instance
        file_path: The file path to find
        
    Returns:
        The model index for the file, or None if not found
    """
    if not HAS_PYSIDE6:
        return None
        
    if not hasattr(explorer_widget, "_proxy") or not hasattr(explorer_widget, "_model"):
        return None
        
    proxy = explorer_widget._proxy
    model = explorer_widget._model
    
    # Try to find the file in the current view
    for row in range(proxy.rowCount()):
        index = proxy.index(row, 0)
        if index.isValid():
            # Check if this is the file we're looking for
            if hasattr(model, "data"):
                try:
                    # Try different approaches to match the file
                    file_data = model.data(index, Qt.ItemDataRole.UserRole)
                    display_name = model.data(index, Qt.ItemDataRole.DisplayRole)
                    
                    if file_data == str(file_path) or display_name == file_path.name:
                        return index
                except Exception:
                    # Silently handle any errors during comparison
                    pass
    
    return None
    
    # Connect to current directory changes
    if hasattr(explorer_widget, '_set_directory'):
        original_set_directory = explorer_widget._set_directory
        
        def set_directory_with_search(path):
            result = original_set_directory(path)
            if hasattr(search_panel, 'set_directory'):
                search_panel.set_directory(path)
            return result
        
        explorer_widget._set_directory = set_directory_with_search
        
    # Connect result selected signal
    if hasattr(search_panel, 'result_selected') and hasattr(search_panel.result_selected, 'connect'):
        search_panel.result_selected.connect(lambda file_path, line: _handle_result_selected(explorer_widget, file_path))
        
    # Store search panel reference
    explorer_widget._search_panel = search_panel
    
    return search_panel

def _toggle_search_panel(explorer_widget, search_panel, checked):
    """Toggle visibility of the search panel.
    
    Args:
        explorer_widget: The ExplorerWidget instance
        search_panel: The SearchPanel instance
        checked: Whether the search button is checked
    """
    if hasattr(search_panel, "setVisible"):
        search_panel.setVisible(checked)
        
def _handle_result_selected(explorer_widget, file_path):
    """Handle a search result selection.
    
    Args:
        explorer_widget: The ExplorerWidget instance
        file_path: Path to the selected file
    """
    # Navigate to the file if possible
    if hasattr(explorer_widget, '_set_directory') and file_path:
        # If the file is in a different directory, navigate to its parent
        if file_path.parent != explorer_widget._current_path:
            explorer_widget._set_directory(file_path.parent)
            
        # Select the file
        if hasattr(explorer_widget, '_select_path'):
            explorer_widget._select_path(file_path)
        elif hasattr(explorer_widget, '_content_view') and hasattr(explorer_widget._content_view, 'selectionModel'):
            # Try to find and select the item
            model = getattr(explorer_widget, '_proxy', None) or getattr(explorer_widget, '_model', None)
            if model and hasattr(model, 'index'):
                for row in range(model.rowCount()):
                    index = model.index(row, 0)
                    if model.data(index, Qt.ItemDataRole.UserRole) == str(file_path):
                        explorer_widget._content_view.selectionModel().select(
                            index, 
                            explorer_widget._content_view.selectionModel().SelectionFlag.ClearAndSelect
                        )
                        explorer_widget._content_view.scrollTo(index)
                        break