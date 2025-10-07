"""Explorer view factory.

This module implements the ViewFactory class that creates different views
for the Explorer plugin following the factory pattern. This decouples the
view creation from the ExplorerWidget class.
"""

from typing import Any, Optional
from pathlib import Path

# Check if PySide6 is available
try:
    from PySide6.QtCore import QModelIndex, Qt, QSize
    from PySide6.QtWidgets import (
        QListView, QTreeView, QAbstractItemView, QWidget,
        QTableView, QHeaderView
    )
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False
    QListView = QTreeView = QAbstractItemView = QWidget = object
    QTableView = QHeaderView = object
    QModelIndex = QSize = Any
    Qt = object


class ViewFactory:
    """Factory for creating different view types for the Explorer plugin.
    
    This class implements the factory pattern to create different view types
    (grid, list, details) that can be used to display files and folders.
    """
    
    @staticmethod
    def create_grid_view(parent: QWidget, model: Any) -> Optional[QListView]:
        """Create a grid view for displaying files and folders as icons.
        
        Args:
            parent: The parent widget
            model: The model containing the data to display
            
        Returns:
            A QListView configured for icon display, or None if PySide6 is not available
        """
        if not HAS_PYSIDE6:
            return None
            
        view = QListView(parent)
        view.setModel(model)
        view.setViewMode(QListView.ViewMode.IconMode)
        if hasattr(Qt, "QSize"):
            try:
                view.setGridSize(QSize(100, 100))
            except:
                pass  # Ignore if QSize is not properly initialized
        view.setResizeMode(QListView.ResizeMode.Adjust)
        view.setWrapping(True)
        view.setSpacing(10)
        view.setUniformItemSizes(True)
        view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        return view
    
    @staticmethod
    def create_list_view(parent: QWidget, model: Any) -> Optional[QListView]:
        """Create a list view for displaying files and folders as a simple list.
        
        Args:
            parent: The parent widget
            model: The model containing the data to display
            
        Returns:
            A QListView configured for list display, or None if PySide6 is not available
        """
        if not HAS_PYSIDE6:
            return None
            
        view = QListView(parent)
        view.setModel(model)
        view.setViewMode(QListView.ViewMode.ListMode)
        view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        return view
    
    @staticmethod
    def create_details_view(parent: QWidget, model: Any) -> Optional[QTreeView]:
        """Create a details view for displaying files and folders with additional columns.
        
        Args:
            parent: The parent widget
            model: The model containing the data to display
            
        Returns:
            A QTreeView configured for details display, or None if PySide6 is not available
        """
        if not HAS_PYSIDE6:
            return None
            
        view = QTreeView(parent)
        view.setModel(model)
        view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Show all columns
        if hasattr(view, "header") and hasattr(view.header(), "setSectionResizeMode"):
            view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for col in range(1, 4):
                view.header().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        
        return view