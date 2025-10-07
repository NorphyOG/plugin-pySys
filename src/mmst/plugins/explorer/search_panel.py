"""Explorer plugin search panel.

This module implements the UI components for full-text search within the Explorer plugin,
allowing users to search for text within files in the current directory and view results.
"""

import logging
from pathlib import Path
from typing import Any, Callable, List, Optional, Protocol, Union

# Import local modules
from .search_engine import SearchEngine, SearchMode, SearchResult

# Check if PySide6 is available
HAS_PYSIDE6 = False
try:
    import PySide6
    HAS_PYSIDE6 = True
except ImportError:
    pass

# Define stub classes for headless operation
class DummySignal:
    """Stub signal implementation for headless operation."""
    def __init__(self, *arg_types):
        """Initialize the dummy signal with signature arg_types."""
        self._arg_types = arg_types
    
    def emit(self, *args):
        """Stub emit method that safely handles arguments."""
        # In headless mode, we just log the emit call without validation
        pass
    
    def connect(self, func):
        """Stub connect method."""
        pass

# Define protocol classes for type checking
class ProgressEmitterProtocol(Protocol):
    """Protocol for search progress emitter."""
    progress: Any
    result: Any
    finished: Any
    error: Any

# Define implementations based on PySide6 availability
if HAS_PYSIDE6:
    # Real implementations using PySide6
    from PySide6.QtCore import Qt, Signal, QObject, QRunnable, QThreadPool, Slot
    # Import other Qt components
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
else:
    # For headless operation, create dummy classes
    QObject = object
    QRunnable = object
    QThreadPool = object
    Slot = lambda: lambda x: x  # Dummy decorator
    Signal = DummySignal  # Use our DummySignal as the Signal class in headless mode
    
    class SearchProgressEmitter(QObject):
        """Signal emitter for search progress updates."""
        progress = Signal(int, int)  # files_processed, total_files
        result = Signal(object)      # SearchResult
        finished = Signal(list)      # List[SearchResult]
        error = Signal(str)          # error message
    
    class SearchWorker(QRunnable):
        """Worker for running search operations in a background thread."""
        
        def __init__(
            self, 
            search_engine: SearchEngine, 
            directory: Path,
            search_term: str, 
            mode: SearchMode, 
            max_results: int,
            file_filter: Optional[Callable[[Path], bool]] = None
        ):
            """Initialize the search worker."""
            super().__init__()
            self.search_engine = search_engine
            self.directory = directory
            self.search_term = search_term
            self.mode = mode
            self.max_results = max_results
            self.file_filter = file_filter
            self.signals = SearchProgressEmitter()
            
        @Slot()
        def run(self):
            """Run the search operation."""
            try:
                results = self.search_engine.search_directory(
                    self.directory,
                    self.search_term,
                    self.mode,
                    self.max_results,
                    self.file_filter,
                    self.progress_callback
                )
                self.signals.finished.emit(results)
            except Exception as e:
                self.signals.error.emit(str(e))
                
        def progress_callback(self, files_processed: int, total_files: int):
            """Handle progress updates from the search engine."""
            self.signals.progress.emit(files_processed, total_files)
    
    # Define actual classes based on PySide6 availability
if HAS_PYSIDE6:
    # Import the search panel UI if available
    try:
        # Try to import the full-featured UI implementation
        from .search_gui import SearchPanelUI as SearchPanel
    except ImportError:
        # If not available, create a minimal QWidget-based implementation
        from PySide6.QtWidgets import QWidget
        
        class SearchPanel(QWidget):
            """Minimal search panel implementation when search_gui is not available."""
            result_selected = Signal(Path, int)
            
            def __init__(self, parent=None):
                """Initialize the search panel."""
                super().__init__(parent)
                self.search_engine = SearchEngine()
                self.current_directory = None
            
            def set_directory(self, directory: Path):
                """Set the directory to search in."""
                self.current_directory = directory
else:
    # Stub implementations for headless operation
    class SearchProgressEmitter:
        """Stub emitter for headless operation."""
        def __init__(self):
            """Initialize the stub emitter."""
            self.progress = DummySignal(int, int)
            self.result = DummySignal(object)
            self.finished = DummySignal(list)
            self.error = DummySignal(str)
    
    class SearchWorker:
        """Stub worker for headless operation."""
        def __init__(self, search_engine=None, directory=None, search_term=None, mode=None, max_results=None, file_filter=None):
            """Initialize the stub worker."""
            self.signals = SearchProgressEmitter()
            self.search_engine = search_engine
            self.directory = directory
            self.search_term = search_term
            self.mode = mode
            self.max_results = max_results
            self.file_filter = file_filter
        
        def run(self):
            """Stub implementation of run method."""
            # In headless mode, we don't actually run the search
            pass
        
        def progress_callback(self, files_processed: int, total_files: int):
            """Stub implementation of progress_callback method."""
            # In headless mode, we don't need to update progress
            pass
    
    class SearchPanel:
        """Stub search panel for headless operation."""
        def __init__(self, parent=None):
            """Initialize the stub search panel."""
            self.result_selected = DummySignal(Path, int)
            self.search_engine = SearchEngine()
            self.current_directory = None
        
        def set_directory(self, directory: Path):
            """Set the directory to search in."""
            self.current_directory = directory
        
        def setVisible(self, visible: bool):
            """Stub implementation of setVisible."""
            pass
        def __init__(self, parent=None):
            """Initialize the stub search panel."""
            self.result_selected = DummySignal(Path, int)
            self.search_engine = SearchEngine()
            self.current_directory = None
        
        def set_directory(self, directory: Path):
            """Set the directory to search in."""
            self.current_directory = directory
        
        def setVisible(self, visible: bool):
            """Stub implementation of setVisible."""
            pass


# End of file
    
    def __init__(self, parent=None):
        """Initialize the search panel.
        
        Args:
            parent: Parent widget
        """
        # Initialize the Signal here to avoid type errors
        if hasattr(Signal, '__call__'):
            # Create instance signal attribute instead of class attribute
            self.result_selected = Signal(Path, int)  # file_path, line_number
        else:
            # For headless operation
            class DummySignal:
                def emit(self, *args):
                    pass
                def connect(self, func):
                    pass
            self.result_selected = DummySignal()
        super().__init__(parent)
        self.setObjectName("ExplorerSearchPanel") if hasattr(self, "setObjectName") else None
        
        # Create search engine
        self.search_engine = SearchEngine()
        
        # Initialize UI
        self._build_ui()
        self._connect_signals()
        
        # Initialize thread pool for search operations
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
        if hasattr(self.results_tree, "header"):
            header = self.results_tree.header()
            if hasattr(header, "setStretchLastSection"):
                header.setStretchLastSection(True)
            if hasattr(header, "setSectionResizeMode"):
                header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
                header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        
        # Preview panel
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        
        # Add to splitter
        results_splitter.addWidget(self.results_tree)
        results_splitter.addWidget(self.preview_text)
        
        # Set initial sizes
        if hasattr(results_splitter, "setSizes"):
            results_splitter.setSizes([200, 150])
        
        # Add to main layout
        main_layout.addWidget(search_group)
        main_layout.addWidget(results_splitter)
        
    def _connect_signals(self):
        """Connect signals to slots."""
        # Connect search button
        if hasattr(self.search_button, "clicked"):
            self.search_button.clicked.connect(self._start_search)
            
        # Connect search input enter key
        if hasattr(self.search_input, "returnPressed"):
            self.search_input.returnPressed.connect(self._start_search)
            
        # Connect cancel button
        if hasattr(self.cancel_button, "clicked"):
            self.cancel_button.clicked.connect(self._cancel_search)
            
        # Connect results tree selection
        if hasattr(self.results_tree, "clicked"):
            self.results_tree.clicked.connect(self._handle_result_selection)
        if hasattr(self.results_tree, "doubleClicked"):
            self.results_tree.doubleClicked.connect(self._handle_result_double_click)
    
    def set_directory(self, directory: Path):
        """Set the directory to search in.
        
        Args:
            directory: Directory path
        """
        self.current_directory = directory
        if hasattr(self.search_button, "setText"):
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
            search_mode or SearchMode.PLAIN_TEXT,  # Default to plain text if None
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
        if hasattr(self.progress_bar, "setMaximum"):
            self.progress_bar.setMaximum(total_files)
            self.progress_bar.setValue(files_processed)
    
    def _search_finished(self, results: List[SearchResult]):
        """Handle search completion.
        
        Args:
            results: List of search results
        """
        self._populate_results(results)
        self._reset_ui_after_search()
    
    def _search_error(self, error_message: str):
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
        if hasattr(self.results_model, "clear"):
            self.results_model.clear()
            self.results_model.setHorizontalHeaderLabels(["Datei / Treffer", "Zeile", "Inhalt"])
            
        if hasattr(self.preview_text, "clear"):
            self.preview_text.clear()
    
    def _populate_results(self, results: List[SearchResult]):
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
        if hasattr(self.preview_text, "setPlainText"):
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
    
    def _show_file_summary(self, file_path: Path, match_count: int):
        """Show summary information for a file.
        
        Args:
            file_path: File path
            match_count: Number of matches in the file
        """
        if not file_path.exists():
            return
            
        summary = f"Datei: {file_path}\n"
        summary += f"Größe: {self._format_size(file_path.stat().st_size)}\n"
        summary += f"Treffer: {match_count}\n\n"
        summary += "Doppelklicken Sie auf einen Treffer, um die Datei zu öffnen."
        
        if hasattr(self.preview_text, "setPlainText"):
            self.preview_text.setPlainText(summary)
    
    def _show_match_preview(self, file_path: Path, line_number: int):
        """Show a preview of a match with context lines.
        
        Args:
            file_path: File path
            line_number: Line number of the match
        """
        context_lines = self.search_engine.get_context_lines(file_path, line_number, 3)
        
        if not context_lines:
            return
            
        # Format the preview
        preview = f"Datei: {file_path}\n"
        preview += f"Zeile {line_number}:\n\n"
        
        # Add context lines
        preview += "\n".join([f"{i}: {line}" for i, line in context_lines])
        
        if hasattr(self.preview_text, "setPlainText"):
            self.preview_text.setPlainText(preview)
            
        # Highlight the match line
        if hasattr(self.preview_text, "document"):
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
    def _format_size(size_bytes: float) -> str:
        """Format file size in human-readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string
        """
        size_float = float(size_bytes)  # Convert to float explicitly
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_float < 1024 or unit == 'TB':
                return f"{size_float:.2f} {unit}"
            size_float /= 1024
        return f"{size_float:.2f} TB"  # Fallback return to ensure all paths return a string