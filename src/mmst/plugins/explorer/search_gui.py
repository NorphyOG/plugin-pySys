from __future__ import annotations

"""GUI implementation for Explorer plugin search panel.

This module provides the Qt-based implementation of the search panel UI.
It is only imported when PySide6 is available.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union, cast

# Import Qt
from PySide6.QtCore import Qt, Signal, QObject, QSize, Slot
from PySide6.QtGui import (
    QIcon, QTextCharFormat, QColor, QFont, QStandardItemModel, QStandardItem
)
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton, QTreeView, QSpinBox,
    QSplitter, QTextEdit, QVBoxLayout, QWidget, QHeaderView, QAbstractItemView,
    QMenu, QProgressBar
)

# Import local modules
from .search_panel import SearchProgressEmitter, SearchWorker
from .search_engine import SearchEngine, SearchMode, SearchResult, SearchMatch

class SearchPanelUI(QWidget):
    """Panel for full-text search within files.
    
    This panel provides UI controls for searching text within files in the current directory
    and displaying the results in a structured view.
    """
    
    # Signal emitted when a search result is selected
    result_selected = Signal(Path, int)  # file_path, line_number
    
    def __init__(self, parent=None):
        """Initialize the search panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setObjectName("ExplorerSearchPanel")
        
        # Create search engine
        self.search_engine = SearchEngine()
        
        # Initialize UI
        self._build_ui()
        self._connect_signals()
        
        # Initialize thread pool for search operations
        from PySide6.QtCore import QThreadPool
        self.thread_pool = QThreadPool.globalInstance()
        
        # Current directory being searched
        self.current_directory = None
        
    def _build_ui(self):
        """Build the search panel UI components."""
        # Create main layout
        main_layout = QVBoxLayout(self)
        
        # Search input and options
        search_group = QGroupBox("Volltext-Suche")
        search_layout = QVBoxLayout(search_group)
        
        # Search input row
        input_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Suchtext eingeben...")
        
        self.search_button = QPushButton("Suchen")
        self.search_button.setIcon(QIcon.fromTheme("search"))
        
        input_layout.addWidget(self.search_input)
        input_layout.addWidget(self.search_button)
        
        # Search options row
        options_layout = QHBoxLayout()
        
        # Search mode
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Normaler Text", "plain")
        self.mode_combo.addItem("Regulärer Ausdruck", "regex")
        self.mode_combo.addItem("Groß-/Kleinschreibung", "case_sensitive")
        
        # Max results
        max_results_layout = QHBoxLayout()
        max_results_layout.addWidget(QLabel("Max. Ergebnisse:"))
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(10, 10000)
        self.max_results_spin.setValue(1000)
        self.max_results_spin.setSingleStep(100)
        max_results_layout.addWidget(self.max_results_spin)
        
        options_layout.addWidget(QLabel("Modus:"))
        options_layout.addWidget(self.mode_combo)
        options_layout.addLayout(max_results_layout)
        options_layout.addStretch(1)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # Cancel button
        self.cancel_button = QPushButton("Abbrechen")
        self.cancel_button.setVisible(False)
        
        # Add to search layout
        search_layout.addLayout(input_layout)
        search_layout.addLayout(options_layout)
        search_layout.addWidget(self.progress_bar)
        
        # Cancel button row
        cancel_layout = QHBoxLayout()
        cancel_layout.addStretch(1)
        cancel_layout.addWidget(self.cancel_button)
        search_layout.addLayout(cancel_layout)
        
        # Results splitter
        results_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Results tree
        self.results_tree = QTreeView()
        self.results_tree.setHeaderHidden(False)
        self.results_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_tree.setExpandsOnDoubleClick(True)
        self.results_model = QStandardItemModel()
        self.results_model.setHorizontalHeaderLabels(["Datei / Treffer", "Zeile", "Inhalt"])
        self.results_tree.setModel(self.results_model)
        
        # Set up header and column widths
        header = self.results_tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        
        # Preview panel
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        
        # Add to splitter
        results_splitter.addWidget(self.results_tree)
        results_splitter.addWidget(self.preview_text)
        
        # Set initial sizes
        results_splitter.setSizes([200, 150])
        
        # Add to main layout
        main_layout.addWidget(search_group)
        main_layout.addWidget(results_splitter)
        
    def _connect_signals(self):
        """Connect signals to slots."""
        # Connect search button
        self.search_button.clicked.connect(self._start_search)
            
        # Connect search input enter key
        self.search_input.returnPressed.connect(self._start_search)
            
        # Connect cancel button
        self.cancel_button.clicked.connect(self._cancel_search)
            
        # Connect results tree selection
        self.results_tree.clicked.connect(self._handle_result_selection)
        self.results_tree.doubleClicked.connect(self._handle_result_double_click)
        
    def set_directory(self, directory: Path):
        """Set the directory to search in.
        
        Args:
            directory: Directory path
        """
        self.current_directory = directory
        self.search_button.setText(f"Suchen in {directory.name}")
    
    def _start_search(self):
        """Start a search operation based on current inputs."""
        if not self.current_directory:
            return
            
        search_term = self.search_input.text()
        if not search_term:
            return
            
        # Get search mode
        mode_value = self.mode_combo.currentData()
        search_mode = None
        if mode_value == "plain":
            search_mode = SearchMode.PLAIN_TEXT
        elif mode_value == "regex":
            search_mode = SearchMode.REGEX
        elif mode_value == "case_sensitive":
            search_mode = SearchMode.CASE_SENSITIVE
            
        # Get max results
        max_results = self.max_results_spin.value()
        
        # Clear previous results
        self._clear_results()
        
        # Show progress UI
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.cancel_button.setVisible(True)
        
        # Disable search controls
        self.search_input.setEnabled(False)
        self.search_button.setEnabled(False)
        self.mode_combo.setEnabled(False)
        self.max_results_spin.setEnabled(False)
        
        # Create and start worker
        worker = SearchWorker(
            self.search_engine,
            self.current_directory,
            search_term,
            search_mode,
            max_results
        )
        
        # Connect worker signals
        worker.signals.progress.connect(self._update_progress)
        worker.signals.finished.connect(self._search_finished)
        worker.signals.error.connect(self._search_error)
        
        # Start worker
        self.thread_pool.start(worker)
    
    def _cancel_search(self):
        """Cancel the current search operation."""
        self.search_engine.cancel_search()
        self._reset_ui_after_search()
        
    def _update_progress(self, files_processed, total_files):
        """Update the progress bar.
        
        Args:
            files_processed: Number of files processed
            total_files: Total number of files to process
        """
        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(files_processed)
    
    def _search_finished(self, results):
        """Handle search completion.
        
        Args:
            results: List of search results
        """
        self._populate_results(results)
        self._reset_ui_after_search()
    
    def _search_error(self, error_message):
        """Handle search errors.
        
        Args:
            error_message: Error message
        """
        self.preview_text.setPlainText(f"Fehler bei der Suche: {error_message}")
        self._reset_ui_after_search()
    
    def _reset_ui_after_search(self):
        """Reset UI elements after search completion."""
        # Hide progress UI
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        
        # Enable search controls
        self.search_input.setEnabled(True)
        self.search_button.setEnabled(True)
        self.mode_combo.setEnabled(True)
        self.max_results_spin.setEnabled(True)
    
    def _clear_results(self):
        """Clear the search results tree and preview."""
        self.results_model.clear()
        self.results_model.setHorizontalHeaderLabels(["Datei / Treffer", "Zeile", "Inhalt"])
        self.preview_text.clear()
    
    def _populate_results(self, results):
        """Populate the results tree with search results.
        
        Args:
            results: List of search results
        """
        if not results:
            root_item = QStandardItem("Keine Treffer gefunden")
            root_item.setEditable(False)
            self.results_model.appendRow(root_item)
            return
            
        # Group results by file
        for result in results:
            # Create file item
            file_item = QStandardItem(result.file_path.name)
            file_item.setEditable(False)
            file_item.setData(str(result.file_path), Qt.ItemDataRole.UserRole)
            
            # Set file item font to bold
            font = file_item.font()
            font.setBold(True)
            file_item.setFont(font)
            
            # Add child items for each match
            for match in result.matches:
                # Create match row
                match_item = QStandardItem(f"Treffer {match.line_number}")
                match_item.setEditable(False)
                match_item.setData(match.line_number, Qt.ItemDataRole.UserRole)
                
                # Line number item
                line_item = QStandardItem(str(match.line_number))
                line_item.setEditable(False)
                
                # Line content item
                content_item = QStandardItem(match.line_text)
                content_item.setEditable(False)
                
                # Add match items as a row to the file item
                file_item.appendRow([match_item, line_item, content_item])
            
            # Add file item to model
            self.results_model.appendRow(file_item)
            
        # Update summary in preview
        self.preview_text.setPlainText(f"{len(results)} Dateien mit Treffern gefunden.")
    
    def _handle_result_selection(self, index):
        """Handle selection of a result in the tree.
        
        Args:
            index: Selected model index
        """
        if not index.isValid():
            return
            
        # Get parent item to determine if this is a file or match
        parent = index.parent()
        
        if not parent.isValid():
            # This is a file item, show file summary
            file_path_str = self.results_model.data(index, Qt.ItemDataRole.UserRole)
            if file_path_str:
                file_path = Path(file_path_str)
                match_count = self.results_model.item(index.row()).rowCount()
                self._show_file_summary(file_path, match_count)
        else:
            # This is a match item, show match preview
            file_path_str = self.results_model.data(parent, Qt.ItemDataRole.UserRole)
            line_number = self.results_model.data(index, Qt.ItemDataRole.UserRole)
            
            if file_path_str and line_number:
                file_path = Path(file_path_str)
                self._show_match_preview(file_path, line_number)
    
    def _handle_result_double_click(self, index):
        """Handle double-click on a result in the tree.
        
        Args:
            index: Double-clicked model index
        """
        if not index.isValid():
            return
            
        # Get parent item to determine if this is a file or match
        parent = index.parent()
        
        file_path = None
        line_number = 1
        
        if not parent.isValid():
            # This is a file item, open the file
            file_path_str = self.results_model.data(index, Qt.ItemDataRole.UserRole)
            if file_path_str:
                file_path = Path(file_path_str)
        else:
            # This is a match item, open the file at the match line
            file_path_str = self.results_model.data(parent, Qt.ItemDataRole.UserRole)
            line_number = self.results_model.data(index, Qt.ItemDataRole.UserRole)
            
            if file_path_str:
                file_path = Path(file_path_str)
        
        # Emit signal to open the file
        if file_path:
            self.result_selected.emit(file_path, line_number)
    
    def _show_file_summary(self, file_path, match_count):
        """Show summary information for a file.
        
        Args:
            file_path: File path
            match_count: Number of matches in the file
        """
        if not file_path.exists():
            return
            
        summary = f"Datei: {file_path}\\n"
        summary += f"Größe: {self._format_size(file_path.stat().st_size)}\\n"
        summary += f"Treffer: {match_count}\\n\\n"
        summary += "Doppelklicken Sie auf einen Treffer, um die Datei zu öffnen."
        
        self.preview_text.setPlainText(summary)
    
    def _show_match_preview(self, file_path, line_number):
        """Show a preview of a match with context lines.
        
        Args:
            file_path: File path
            line_number: Line number of the match
        """
        context_lines = self.search_engine.get_context_lines(file_path, line_number, 3)
        
        if not context_lines:
            return
            
        # Format the preview
        preview = f"Datei: {file_path}\\n"
        preview += f"Zeile {line_number}:\\n\\n"
        
        # Add context lines
        preview += "\\n".join([f"{i}: {line}" for i, line in context_lines])
        
        self.preview_text.setPlainText(preview)
            
        # Highlight the match line
        cursor = self.preview_text.textCursor()
        format = QTextCharFormat()
        format.setBackground(QColor(255, 255, 0, 100))  # Light yellow background
        
        # Find and highlight the match line
        doc = self.preview_text.document()
        
        for i, (ctx_line_num, _) in enumerate(context_lines):
            if ctx_line_num == line_number:
                # Find the block for this line
                block = doc.findBlockByLineNumber(i + 2)  # +2 for the header lines
                if block.isValid():
                    cursor.setPosition(block.position())
                    cursor.setPosition(block.position() + block.length() - 1, 
                                     mode=cursor.MoveMode.KeepAnchor)
                    selection = QTextEdit.ExtraSelection()
                    selection.format = format
                    selection.cursor = cursor
                    self.preview_text.setExtraSelections([selection])
                break
    
    @staticmethod
    def _format_size(size_bytes):
        """Format file size in human-readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024 or unit == 'TB':
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"