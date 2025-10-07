from __future__ import annotations

"""Explorer plugin filter panel.

This module implements the advanced filtering capabilities for the Explorer plugin,
allowing users to filter files by type, size, and date.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

# Import Qt components with defensive fallback for headless tests
try:
    from PySide6.QtCore import QDate, QDateTime, QSize, Qt, Signal
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox,
                                  QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                                  QPushButton, QRadioButton, QSlider, QSpinBox,
                                  QVBoxLayout, QWidget)
    HAS_PYSIDE6 = True
except (ImportError, TypeError):
    # For type checking and headless operation
    from typing import Any
    QWidget = object
    Signal = object
    HAS_PYSIDE6 = False


class FilterCriteria:
    """Container for file filtering criteria."""
    
    # File type filter constants
    FILE_TYPE_ALL = "all"
    FILE_TYPE_DOCUMENTS = "documents"
    FILE_TYPE_IMAGES = "images"
    FILE_TYPE_AUDIO = "audio"
    FILE_TYPE_VIDEO = "video"
    FILE_TYPE_ARCHIVES = "archives"
    FILE_TYPE_CODE = "code"
    
    # File extension mappings
    TYPE_EXTENSIONS = {
        FILE_TYPE_DOCUMENTS: [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".odt"],
        FILE_TYPE_IMAGES: [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".tif"],
        FILE_TYPE_AUDIO: [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".aiff"],
        FILE_TYPE_VIDEO: [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"],
        FILE_TYPE_ARCHIVES: [".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz"],
        FILE_TYPE_CODE: [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".h", ".php", ".rb", ".go", ".ts", ".json", ".xml", ".yaml", ".yml"]
    }
    
    # Size filter modes
    SIZE_MODE_ANY = "any"
    SIZE_MODE_LARGER = "larger"
    SIZE_MODE_SMALLER = "smaller"
    SIZE_MODE_BETWEEN = "between"
    
    # Date filter modes
    DATE_MODE_ANY = "any"
    DATE_MODE_NEWER = "newer"
    DATE_MODE_OLDER = "older"
    DATE_MODE_BETWEEN = "between"
    DATE_MODE_TODAY = "today"
    DATE_MODE_YESTERDAY = "yesterday"
    DATE_MODE_THIS_WEEK = "this_week"
    DATE_MODE_THIS_MONTH = "this_month"
    
    # Date attribute types
    DATE_ATTR_MODIFIED = "modified"
    DATE_ATTR_CREATED = "created"
    DATE_ATTR_ACCESSED = "accessed"
    
    def __init__(self):
        """Initialize filter criteria with default values."""
        # Type filtering
        self.file_type = self.FILE_TYPE_ALL
        self.custom_extensions = []  # For custom file type filtering
        
        # Size filtering
        self.size_mode = self.SIZE_MODE_ANY
        self.min_size_bytes = 0
        self.max_size_bytes = 0
        
        # Date filtering
        self.date_mode = self.DATE_MODE_ANY
        self.date_attribute = self.DATE_ATTR_MODIFIED
        self.date_min = datetime.now() - timedelta(days=7)  # Default: last 7 days
        self.date_max = datetime.now()
    
    def matches_file(self, path: Path, file_stats: Dict) -> bool:
        """Check if a file matches all filter criteria.
        
        Args:
            path: Path to the file
            file_stats: Dictionary with file metadata (size, dates, etc.)
            
        Returns:
            True if the file matches all criteria, False otherwise
        """
        # Type filtering
        if not self._matches_type(path):
            return False
            
        # Size filtering
        if not self._matches_size(file_stats.get("size", 0)):
            return False
            
        # Date filtering
        if not self._matches_date(file_stats):
            return False
            
        return True
    
    def _matches_type(self, path: Path) -> bool:
        """Check if file matches type criteria.
        
        Args:
            path: Path to the file
            
        Returns:
            True if the file matches type criteria
        """
        # All files match if no filtering
        if self.file_type == self.FILE_TYPE_ALL:
            return True
            
        # Check custom extensions first
        suffix = path.suffix.lower()
        if self.custom_extensions and suffix in self.custom_extensions:
            return True
            
        # Check predefined type categories
        if self.file_type in self.TYPE_EXTENSIONS:
            return suffix in self.TYPE_EXTENSIONS[self.file_type]
            
        return True
    
    def _matches_size(self, size: int) -> bool:
        """Check if file matches size criteria.
        
        Args:
            size: File size in bytes
            
        Returns:
            True if the file matches size criteria
        """
        if self.size_mode == self.SIZE_MODE_ANY:
            return True
        elif self.size_mode == self.SIZE_MODE_LARGER:
            return size >= self.min_size_bytes
        elif self.size_mode == self.SIZE_MODE_SMALLER:
            return size <= self.max_size_bytes
        elif self.size_mode == self.SIZE_MODE_BETWEEN:
            return self.min_size_bytes <= size <= self.max_size_bytes
        return True
    
    def _matches_date(self, file_stats: Dict) -> bool:
        """Check if file matches date criteria.
        
        Args:
            file_stats: Dictionary with file metadata
            
        Returns:
            True if the file matches date criteria
        """
        # Get the appropriate date from file stats
        date_key = self.date_attribute
        if date_key not in file_stats:
            return True  # If date not available, consider it a match
            
        file_date = file_stats[date_key]
        
        # Any date matches
        if self.date_mode == self.DATE_MODE_ANY:
            return True
            
        # Check specific date modes
        if self.date_mode == self.DATE_MODE_NEWER:
            return file_date >= self.date_min
        elif self.date_mode == self.DATE_MODE_OLDER:
            return file_date <= self.date_min
        elif self.date_mode == self.DATE_MODE_BETWEEN:
            return self.date_min <= file_date <= self.date_max
        elif self.date_mode == self.DATE_MODE_TODAY:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)
            return today <= file_date < tomorrow
        elif self.date_mode == self.DATE_MODE_YESTERDAY:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday = today - timedelta(days=1)
            return yesterday <= file_date < today
        elif self.date_mode == self.DATE_MODE_THIS_WEEK:
            # Start of the current week (Monday)
            today = datetime.now().date()
            start_of_week = today - timedelta(days=today.weekday())
            start_of_week = datetime.combine(start_of_week, datetime.min.time())
            end_of_week = start_of_week + timedelta(days=7)
            return start_of_week <= file_date < end_of_week
        elif self.date_mode == self.DATE_MODE_THIS_MONTH:
            today = datetime.now()
            start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Get the first day of the next month
            if today.month == 12:
                next_month = today.replace(year=today.year + 1, month=1)
            else:
                next_month = today.replace(month=today.month + 1)
            start_of_next_month = next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start_of_month <= file_date < start_of_next_month
        
        return True


class FilterPanel(QWidget):
    """Panel for advanced file filtering options.
    
    This panel provides UI controls for filtering files by type, size, and date.
    """
    
    # Signal emitted when filter criteria change
    filter_changed = Signal(object)  # Emits FilterCriteria
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the filter panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setObjectName("ExplorerFilterPanel") if hasattr(self, "setObjectName") else None
        
        # Initialize filter criteria
        self.criteria = FilterCriteria()
        
        # Build UI
        self._build_ui()
        self._connect_signals()
    
    def _build_ui(self):
        """Build the filter panel UI components."""
        # Create main layout
        main_layout = QVBoxLayout(self)
        
        # File type filtering section
        self._build_type_section(main_layout)
        
        # Size filtering section
        self._build_size_section(main_layout)
        
        # Date filtering section
        self._build_date_section(main_layout)
        
        # Action buttons
        self._build_action_buttons(main_layout)
        
        # Add stretch at the end
        main_layout.addStretch(1)
    
    def _build_type_section(self, parent_layout):
        """Build file type filtering section.
        
        Args:
            parent_layout: Parent layout to add the section to
        """
        # Create group box
        type_group = QGroupBox("Dateityp")
        type_layout = QVBoxLayout(type_group)
        
        # Create type combo box
        self._type_combo = QComboBox()
        self._type_combo.addItem("Alle Dateien", FilterCriteria.FILE_TYPE_ALL)
        self._type_combo.addItem("Dokumente", FilterCriteria.FILE_TYPE_DOCUMENTS)
        self._type_combo.addItem("Bilder", FilterCriteria.FILE_TYPE_IMAGES)
        self._type_combo.addItem("Audio", FilterCriteria.FILE_TYPE_AUDIO)
        self._type_combo.addItem("Video", FilterCriteria.FILE_TYPE_VIDEO)
        self._type_combo.addItem("Archive", FilterCriteria.FILE_TYPE_ARCHIVES)
        self._type_combo.addItem("Quellcode", FilterCriteria.FILE_TYPE_CODE)
        self._type_combo.addItem("Benutzerdefiniert", "custom")
        
        # Create custom extensions input field (initially hidden)
        custom_layout = QHBoxLayout()
        self._custom_extensions_label = QLabel("Dateierweiterungen:")
        self._custom_extensions_input = QComboBox()
        self._custom_extensions_input.setEditable(True)
        self._custom_extensions_input.setPlaceholderText(".jpg, .png, .pdf, ...")
        
        custom_layout.addWidget(self._custom_extensions_label)
        custom_layout.addWidget(self._custom_extensions_input)
        
        # Add to layout
        type_layout.addWidget(self._type_combo)
        type_layout.addLayout(custom_layout)
        
        # Add group to parent layout
        parent_layout.addWidget(type_group)
        
        # Initially hide custom extensions
        self._custom_extensions_label.setVisible(False)
        self._custom_extensions_input.setVisible(False)
    
    def _build_size_section(self, parent_layout):
        """Build file size filtering section.
        
        Args:
            parent_layout: Parent layout to add the section to
        """
        # Create group box
        size_group = QGroupBox("Dateigröße")
        size_layout = QVBoxLayout(size_group)
        
        # Create size mode combo
        self._size_mode_combo = QComboBox()
        self._size_mode_combo.addItem("Beliebig", FilterCriteria.SIZE_MODE_ANY)
        self._size_mode_combo.addItem("Größer als", FilterCriteria.SIZE_MODE_LARGER)
        self._size_mode_combo.addItem("Kleiner als", FilterCriteria.SIZE_MODE_SMALLER)
        self._size_mode_combo.addItem("Zwischen", FilterCriteria.SIZE_MODE_BETWEEN)
        
        # Size input layouts
        size_input_layout = QHBoxLayout()
        
        # Min size input
        min_size_layout = QHBoxLayout()
        self._min_size_label = QLabel("Min:")
        self._min_size_spin = QSpinBox()
        self._min_size_spin.setRange(0, 1000000)
        self._min_size_spin.setSuffix(" MB")
        min_size_layout.addWidget(self._min_size_label)
        min_size_layout.addWidget(self._min_size_spin)
        
        # Max size input
        max_size_layout = QHBoxLayout()
        self._max_size_label = QLabel("Max:")
        self._max_size_spin = QSpinBox()
        self._max_size_spin.setRange(0, 1000000)
        self._max_size_spin.setSuffix(" MB")
        max_size_layout.addWidget(self._max_size_label)
        max_size_layout.addWidget(self._max_size_spin)
        
        # Add to size input layout
        size_input_layout.addLayout(min_size_layout)
        size_input_layout.addLayout(max_size_layout)
        
        # Add to main layout
        size_layout.addWidget(self._size_mode_combo)
        size_layout.addLayout(size_input_layout)
        
        # Add group to parent layout
        parent_layout.addWidget(size_group)
        
        # Initially hide size inputs
        self._min_size_label.setVisible(False)
        self._min_size_spin.setVisible(False)
        self._max_size_label.setVisible(False)
        self._max_size_spin.setVisible(False)
    
    def _build_date_section(self, parent_layout):
        """Build date filtering section.
        
        Args:
            parent_layout: Parent layout to add the section to
        """
        # Create group box
        date_group = QGroupBox("Datum")
        date_layout = QVBoxLayout(date_group)
        
        # Date attribute selection
        attr_layout = QHBoxLayout()
        attr_label = QLabel("Attribut:")
        self._date_attr_combo = QComboBox()
        self._date_attr_combo.addItem("Geändert", FilterCriteria.DATE_ATTR_MODIFIED)
        self._date_attr_combo.addItem("Erstellt", FilterCriteria.DATE_ATTR_CREATED)
        self._date_attr_combo.addItem("Zugegriffen", FilterCriteria.DATE_ATTR_ACCESSED)
        attr_layout.addWidget(attr_label)
        attr_layout.addWidget(self._date_attr_combo)
        
        # Date mode selection
        self._date_mode_combo = QComboBox()
        self._date_mode_combo.addItem("Beliebig", FilterCriteria.DATE_MODE_ANY)
        self._date_mode_combo.addItem("Neuer als", FilterCriteria.DATE_MODE_NEWER)
        self._date_mode_combo.addItem("Älter als", FilterCriteria.DATE_MODE_OLDER)
        self._date_mode_combo.addItem("Zwischen", FilterCriteria.DATE_MODE_BETWEEN)
        self._date_mode_combo.addItem("Heute", FilterCriteria.DATE_MODE_TODAY)
        self._date_mode_combo.addItem("Gestern", FilterCriteria.DATE_MODE_YESTERDAY)
        self._date_mode_combo.addItem("Diese Woche", FilterCriteria.DATE_MODE_THIS_WEEK)
        self._date_mode_combo.addItem("Diesen Monat", FilterCriteria.DATE_MODE_THIS_MONTH)
        
        # Date inputs
        date_input_layout = QHBoxLayout()
        
        # Start date
        start_date_layout = QHBoxLayout()
        self._start_date_label = QLabel("Von:")
        self._start_date_edit = QDateEdit(QDate.currentDate().addDays(-7))
        self._start_date_edit.setCalendarPopup(True)
        start_date_layout.addWidget(self._start_date_label)
        start_date_layout.addWidget(self._start_date_edit)
        
        # End date
        end_date_layout = QHBoxLayout()
        self._end_date_label = QLabel("Bis:")
        self._end_date_edit = QDateEdit(QDate.currentDate())
        self._end_date_edit.setCalendarPopup(True)
        end_date_layout.addWidget(self._end_date_label)
        end_date_layout.addWidget(self._end_date_edit)
        
        # Add to date input layout
        date_input_layout.addLayout(start_date_layout)
        date_input_layout.addLayout(end_date_layout)
        
        # Add to main layout
        date_layout.addLayout(attr_layout)
        date_layout.addWidget(self._date_mode_combo)
        date_layout.addLayout(date_input_layout)
        
        # Add group to parent layout
        parent_layout.addWidget(date_group)
        
        # Initially hide date inputs based on mode
        self._start_date_label.setVisible(False)
        self._start_date_edit.setVisible(False)
        self._end_date_label.setVisible(False)
        self._end_date_edit.setVisible(False)
    
    def _build_action_buttons(self, parent_layout):
        """Build action buttons section.
        
        Args:
            parent_layout: Parent layout to add the section to
        """
        # Create button layout
        button_layout = QHBoxLayout()
        
        # Apply button
        self._apply_button = QPushButton("Filter anwenden")
        
        # Reset button
        self._reset_button = QPushButton("Zurücksetzen")
        
        # Add to layout
        button_layout.addWidget(self._apply_button)
        button_layout.addWidget(self._reset_button)
        
        # Add to parent layout
        parent_layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """Connect signals to slots."""
        # Type filtering signals
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        self._custom_extensions_input.editTextChanged.connect(self._on_custom_extensions_changed)
        
        # Size filtering signals
        self._size_mode_combo.currentIndexChanged.connect(self._on_size_mode_changed)
        self._min_size_spin.valueChanged.connect(self._on_size_changed)
        self._max_size_spin.valueChanged.connect(self._on_size_changed)
        
        # Date filtering signals
        self._date_mode_combo.currentIndexChanged.connect(self._on_date_mode_changed)
        self._date_attr_combo.currentIndexChanged.connect(self._on_date_attr_changed)
        self._start_date_edit.dateChanged.connect(self._on_date_changed)
        self._end_date_edit.dateChanged.connect(self._on_date_changed)
        
        # Action buttons
        self._apply_button.clicked.connect(self._apply_filter)
        self._reset_button.clicked.connect(self.reset_filters)
    
    def _on_type_changed(self, index):
        """Handle changes to the file type selection.
        
        Args:
            index: Current combo box index
        """
        # Get the selected file type
        file_type = self._type_combo.itemData(index)
        
        # Handle custom file type
        if file_type == "custom":
            self._custom_extensions_label.setVisible(True)
            self._custom_extensions_input.setVisible(True)
        else:
            self._custom_extensions_label.setVisible(False)
            self._custom_extensions_input.setVisible(False)
            self.criteria.file_type = file_type
    
    def _on_custom_extensions_changed(self, text):
        """Handle changes to custom file extensions.
        
        Args:
            text: Current text in the input field
        """
        # Parse extensions (comma or space separated)
        extensions = []
        if text:
            # Split by commas or spaces and clean up
            for ext in text.replace(',', ' ').split():
                ext = ext.strip()
                if not ext.startswith("."):
                    ext = f".{ext}"
                extensions.append(ext.lower())
        
        # Update criteria
        self.criteria.custom_extensions = extensions
    
    def _on_size_mode_changed(self, index):
        """Handle changes to the size filter mode.
        
        Args:
            index: Current combo box index
        """
        # Get the selected size mode
        size_mode = self._size_mode_combo.itemData(index)
        self.criteria.size_mode = size_mode
        
        # Update UI visibility based on mode
        if size_mode == FilterCriteria.SIZE_MODE_ANY:
            self._min_size_label.setVisible(False)
            self._min_size_spin.setVisible(False)
            self._max_size_label.setVisible(False)
            self._max_size_spin.setVisible(False)
        elif size_mode == FilterCriteria.SIZE_MODE_LARGER:
            self._min_size_label.setVisible(True)
            self._min_size_spin.setVisible(True)
            self._max_size_label.setVisible(False)
            self._max_size_spin.setVisible(False)
        elif size_mode == FilterCriteria.SIZE_MODE_SMALLER:
            self._min_size_label.setVisible(False)
            self._min_size_spin.setVisible(False)
            self._max_size_label.setVisible(True)
            self._max_size_spin.setVisible(True)
        elif size_mode == FilterCriteria.SIZE_MODE_BETWEEN:
            self._min_size_label.setVisible(True)
            self._min_size_spin.setVisible(True)
            self._max_size_label.setVisible(True)
            self._max_size_spin.setVisible(True)
    
    def _on_size_changed(self, value):
        """Handle changes to the size values.
        
        Args:
            value: Current value (not used directly)
        """
        # Convert MB to bytes
        min_bytes = self._min_size_spin.value() * 1024 * 1024
        max_bytes = self._max_size_spin.value() * 1024 * 1024
        
        # Update criteria
        self.criteria.min_size_bytes = min_bytes
        self.criteria.max_size_bytes = max_bytes
    
    def _on_date_mode_changed(self, index):
        """Handle changes to the date filter mode.
        
        Args:
            index: Current combo box index
        """
        # Get the selected date mode
        date_mode = self._date_mode_combo.itemData(index)
        self.criteria.date_mode = date_mode
        
        # Update UI visibility based on mode
        if date_mode in [FilterCriteria.DATE_MODE_NEWER, FilterCriteria.DATE_MODE_OLDER]:
            self._start_date_label.setVisible(True)
            self._start_date_edit.setVisible(True)
            self._end_date_label.setVisible(False)
            self._end_date_edit.setVisible(False)
        elif date_mode == FilterCriteria.DATE_MODE_BETWEEN:
            self._start_date_label.setVisible(True)
            self._start_date_edit.setVisible(True)
            self._end_date_label.setVisible(True)
            self._end_date_edit.setVisible(True)
        else:
            self._start_date_label.setVisible(False)
            self._start_date_edit.setVisible(False)
            self._end_date_label.setVisible(False)
            self._end_date_edit.setVisible(False)
    
    def _on_date_attr_changed(self, index):
        """Handle changes to the date attribute.
        
        Args:
            index: Current combo box index
        """
        # Update criteria with selected date attribute
        self.criteria.date_attribute = self._date_attr_combo.itemData(index)
    
    def _on_date_changed(self, qdate):
        """Handle changes to the date values.
        
        Args:
            qdate: Current date value (not used directly)
        """
        # Convert QDate to Python datetime
        start_date = self._start_date_edit.date().toPython()
        end_date = self._end_date_edit.date().toPython()
        
        # Make sure end date is at the end of the day
        end_date = datetime.combine(end_date, datetime.max.time())
        
        # Update criteria
        self.criteria.date_min = start_date
        self.criteria.date_max = end_date
    
    def _apply_filter(self):
        """Apply the current filter settings."""
        # Emit the filter changed signal with current criteria
        self.filter_changed.emit(self.criteria)
    
    def reset_filters(self):
        """Reset all filters to default values."""
        # Reset criteria
        self.criteria = FilterCriteria()
        
        # Reset UI controls
        self._type_combo.setCurrentIndex(0)  # "All Files"
        self._custom_extensions_input.clear()
        self._size_mode_combo.setCurrentIndex(0)  # "Any"
        self._min_size_spin.setValue(0)
        self._max_size_spin.setValue(0)
        self._date_mode_combo.setCurrentIndex(0)  # "Any"
        self._date_attr_combo.setCurrentIndex(0)  # "Modified"
        
        # Hide optional inputs
        self._custom_extensions_label.setVisible(False)
        self._custom_extensions_input.setVisible(False)
        self._min_size_label.setVisible(False)
        self._min_size_spin.setVisible(False)
        self._max_size_label.setVisible(False)
        self._max_size_spin.setVisible(False)
        self._start_date_label.setVisible(False)
        self._start_date_edit.setVisible(False)
        self._end_date_label.setVisible(False)
        self._end_date_edit.setVisible(False)
        
        # Emit filter changed signal
        self.filter_changed.emit(self.criteria)
    
    def get_criteria(self) -> FilterCriteria:
        """Get the current filter criteria.
        
        Returns:
            Current FilterCriteria object
        """
        return self.criteria