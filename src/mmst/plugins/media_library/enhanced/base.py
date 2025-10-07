from __future__ import annotations
from typing import Any, Dict, List, Tuple, TYPE_CHECKING
from pathlib import Path

try:  # GUI imports
    from PySide6.QtCore import Qt, Signal  # type: ignore
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel  # type: ignore
    QtWidgetBase = QWidget  # type: ignore
except Exception:  # pragma: no cover
    class QtWidgetBase:  # minimal stub, used as base type
        def __init__(self, *a, **k): pass
        def __getattr__(self, _): return lambda *a, **k: None
    class QVBoxLayout:  # type: ignore
        def __init__(self, *a, **k): pass
        def addWidget(self, *a, **k): pass
        def addLayout(self, *a, **k): pass
    class QHBoxLayout(QVBoxLayout):  # type: ignore
        def addStretch(self, *a, **k): pass
    class QLabel:  # type: ignore
        def __init__(self, *a, **k): pass
        def setText(self, *a, **k): pass
        def setStyleSheet(self, *a, **k): pass
    Qt = object()  # type: ignore
    Signal = lambda *a, **k: None  # type: ignore

from ..core import MediaFile  # type: ignore
from ..metadata import MediaMetadata  # type: ignore
from .table_view import EnhancedTableWidget  # type: ignore
from .dashboard import DashboardPlaceholder  # type: ignore
from ..smart_playlists import load_smart_playlists, SmartPlaylist  # type: ignore
from .mini_player import MiniPlayerWidget  # type: ignore
from ..covers import CoverCache  # type: ignore
from ..watcher import FileSystemWatcher  # type: ignore

try:
    from PySide6.QtWidgets import (
        QStackedWidget,
        QListWidget,
        QListWidgetItem,
        QSplitter,
        QPushButton,
        QComboBox,
    )
except Exception:  # pragma: no cover
    class _Stub2:
        def __getattr__(self, _): return lambda *a, **k: None
    QStackedWidget = QListWidget = QListWidgetItem = QSplitter = QPushButton = QComboBox = _Stub2  # type: ignore

class EnhancedRootWidget(QtWidgetBase):
    """Root container for the enhanced media library (phase 1).

    Responsibilities (current phase):
      * Host top control bar placeholder
      * Provide pluggable regions: table area, detail panel area
      * Simple API parity with minimal widget so higher-level plugin wiring stays stable
    """
    scan_progress = Signal(str, int, int)  # type: ignore
    library_changed = Signal()  # type: ignore

    def __init__(self, plugin: Any):
        super().__init__()
        self._plugin = plugin
        self._entries: List[Tuple[MediaFile, Path]] = []
        self._all_entries: List[Tuple[MediaFile, Path]] = [] 
        self._metadata_cache: Dict[str, MediaMetadata] = {}
        
        # Set object name for stylesheet targeting
        self.setObjectName("EnhancedMediaLibraryRoot")  # type: ignore[attr-defined]
        root = QVBoxLayout(self)  # type: ignore
        # Global stylesheet for enhanced mode
        try:
            self.setStyleSheet(
                """
                #EnhancedMediaLibraryRoot { background:#1b1d1f; }
                #EnhancedMediaLibraryRoot QLabel { color:#c8c8c8; }
                #EnhancedMediaLibraryRoot QComboBox, #EnhancedMediaLibraryRoot QPushButton { background:#25282a; border:1px solid #343a3d; padding:3px 6px; border-radius:3px; }
                #EnhancedMediaLibraryRoot QComboBox:hover, #EnhancedMediaLibraryRoot QPushButton:hover { border-color:#4b5559; }
                #EnhancedMediaLibraryRoot QTableWidget { background:#202325; gridline-color:#303538; color:#d0d0d0; }
                #EnhancedMediaLibraryRoot QTableWidget::item:selected { background:#3a5f7a; color:#fff; }
                #EnhancedMediaLibraryRoot QTableWidget::item:hover { background:#2c3336; }
                #EnhancedMediaLibraryRoot .subtle-hint { color:#6d7377; font-size:11px; }
                #EnhancedMediaLibraryRoot QSplitter::handle { background:#2d3133; }
                #EnhancedMediaLibraryRoot .toolbar-label { font-weight:600; }
                #EnhancedMediaLibraryRoot .header-bar { background:#222527; border-bottom:1px solid #303336; }
                #EnhancedMediaLibraryRoot .footer-bar { background:#202325; border-top:1px solid #303336; }
                """
            )  # type: ignore
        except Exception:
            pass
        # Header bar (title + view mode + dashboard toggle inline)
        try:
            header_bar = QHBoxLayout()  # type: ignore
            self._header = QLabel("Medienbibliothek – Enhanced")  # type: ignore
            self._header.setObjectName("headerLabel")  # type: ignore
            self._header.setStyleSheet("font-weight:600;padding:4px 6px;")  # type: ignore
            header_bar.addWidget(self._header)  # type: ignore
            header_bar.addStretch(1)  # type: ignore
            # Scan button (opens directory dialog and triggers plugin scan)
            self._scan_btn = QPushButton("Scan…")  # type: ignore
            try:
                self._scan_btn.clicked.connect(self._trigger_scan)  # type: ignore[attr-defined]
            except Exception:
                pass
            header_bar.addWidget(self._scan_btn)  # type: ignore
            
            # Add a debug information label
            self._debug_label = QLabel("Loading media library...")  # type: ignore
            header_bar.addWidget(self._debug_label)  # type: ignore
            self._view_mode_combo = QtWidgetBase()  # type: ignore
            self._view_mode_combo.addItem("Tabelle", "table")  # type: ignore
            self._view_mode_combo.addItem("Galerie", "gallery")  # type: ignore
            self._view_mode_combo.addItem("Geteilt", "split")  # type: ignore
            self._view_mode_combo.currentIndexChanged.connect(self._on_view_mode_changed)  # type: ignore
            header_bar.addWidget(self._view_mode_combo)  # type: ignore
            self._dashboard_toggle = QPushButton("▼ Dashboard")  # type: ignore
            self._dashboard_toggle.clicked.connect(self._toggle_dashboard)  # type: ignore
            header_bar.addWidget(self._dashboard_toggle)  # type: ignore
            # Smart playlist selector
            self._playlist_combo = QComboBox()  # type: ignore
            self._playlist_combo.addItem("Alle Medien", None)  # type: ignore
            try:
                self._playlist_combo.currentIndexChanged.connect(self._on_playlist_changed)  # type: ignore[attr-defined]
            except Exception:
                pass
            header_bar.addWidget(self._playlist_combo)  # type: ignore
            # Rating minimum filter
            self._rating_filter_combo = QComboBox()  # type: ignore
            self._rating_filter_combo.addItem("⭐ min", 0)  # type: ignore
            for i in range(1,6):
                self._rating_filter_combo.addItem("≥ " + "★"*i, i)  # type: ignore
            try:
                self._rating_filter_combo.currentIndexChanged.connect(self._on_rating_filter_changed)  # type: ignore[attr-defined]
            except Exception:
                pass
            header_bar.addWidget(self._rating_filter_combo)  # type: ignore
            # Tag filter edit (simple comma separated OR search)
            from PySide6.QtWidgets import QLineEdit  # type: ignore
            self._tag_filter_edit = QLineEdit()  # type: ignore
            self._tag_filter_edit.setPlaceholderText("Tags filtern…")  # type: ignore
            try:
                self._tag_filter_edit.textChanged.connect(self._on_tag_filter_changed)  # type: ignore[attr-defined]
            except Exception:
                pass
            header_bar.addWidget(self._tag_filter_edit)  # type: ignore
            container = QtWidgetBase()  # type: ignore
            root.addLayout(header_bar)  # type: ignore
        except Exception:
            self._view_mode_combo = QtWidgetBase()  # fallback
            root.addWidget(self._view_mode_combo)  # type: ignore

        # Dashboard placeholder
        self._dashboard = DashboardPlaceholder(plugin)  # type: ignore
        root.addWidget(self._dashboard)  # type: ignore
        # Core components & layout follow

        # Core components
        self.table = EnhancedTableWidget(plugin)  # type: ignore
        # expose root back-reference for table filtering hooks
        try:
            setattr(plugin, '_enhanced_root_ref', self)
        except Exception:
            pass
        try:
            self.table.selection_changed.connect(self._on_selection_changed)  # type: ignore[attr-defined]
        except Exception:
            pass
        self.gallery = self._build_gallery_placeholder()
        self.detail_panel = self._build_detail_panel()
        self._detail_current_path = None  # type: ignore
        self._cover_cache = CoverCache()  # type: ignore
        self._gallery_items_by_path = {}  # path -> QListWidgetItem
        # Filesystem watcher (lazy start if watchdog present)
        self._watcher: FileSystemWatcher | None = None  # type: ignore
        self._pending_refresh = False  # debounce flag

        # Stacked modes
        self._stack = QStackedWidget()  # type: ignore
        try:
            self._stack.addWidget(self.table)  # type: ignore
            self._stack.addWidget(self.gallery)  # type: ignore
        except Exception:
            pass

        # Split view
        try:
            self._split = QSplitter()  # type: ignore
            self._split.addWidget(self.table)  # type: ignore
            self._split.addWidget(self.detail_panel)  # type: ignore
        except Exception:
            self._split = self.table  # fallback

        root.addWidget(self._stack)  # type: ignore
        root.addWidget(self.detail_panel)  # type: ignore
        self._detail_placeholder = QLabel("(Detail panel placeholder)")  # type: ignore
        self._detail_placeholder.setStyleSheet("color:#656b6f;padding:8px 18px;border-top:1px solid #303336;font-size:11px;")  # type: ignore
        root.addWidget(self._detail_placeholder)  # type: ignore
        try:
            self.setObjectName("EnhancedMediaLibraryRoot")  # type: ignore
        except Exception:
            pass

        # Footer: move mini player to bottom for better hierarchy
        self._mini_player = MiniPlayerWidget(plugin)  # type: ignore
        try:
            self._mini_player.setStyleSheet("padding:3px 6px;")  # type: ignore
        except Exception:
            pass
        root.addWidget(self._mini_player)  # type: ignore

        # Restore persisted enhanced state (view mode, dashboard visibility, selection)
        self._restore_state()
        # Attempt to start filesystem watcher after UI constructed
        self._maybe_start_watcher()
        # Load smart playlists (after potential state restore so selection can be applied)
        self._load_smart_playlists()
        self._apply_restored_playlist_selection()

    # Compatibility no-ops used by plugin logic or tests (future expansion)
    def refresh(self) -> None:  # pragma: no cover - placeholder
        self.library_changed.emit()  # type: ignore
        # also refresh dashboard shelves when data changes
        try:
            if hasattr(self._dashboard, 'refresh'):
                self._dashboard.refresh()  # type: ignore[attr-defined]
        except Exception:
            pass

    def apply_external_update(self) -> None:  # pragma: no cover
        pass
    def _toggle_dashboard(self):  # pragma: no cover - simple UI toggle
        try:
            vis = self._dashboard.isVisible()  # type: ignore[attr-defined]
            self._dashboard.setVisible(not vis)  # type: ignore[attr-defined]
            self._dashboard_toggle.setText("▲ Dashboard" if vis else "▼ Dashboard")  # type: ignore[attr-defined]
            self._save_state()
        except Exception:
            pass

    # --- gallery ---
    def _build_gallery_placeholder(self):
        try:
            from PySide6.QtWidgets import QListWidget, QListWidgetItem  # type: ignore
            from PySide6.QtCore import QSize  # type: ignore
        except Exception:
            return QLabel("(Gallery not available)")  # type: ignore
        lst = QListWidget()  # type: ignore
        try:
            lst.setViewMode(QListWidget.ViewMode.IconMode)  # type: ignore[attr-defined]
            lst.setIconSize(QSize(160,160))  # type: ignore[attr-defined]
            lst.setResizeMode(QListWidget.ResizeMode.Adjust)  # type: ignore[attr-defined]
            lst.setSpacing(12)  # type: ignore[attr-defined]
            lst.itemSelectionChanged.connect(self._on_gallery_selection_changed)  # type: ignore[attr-defined]
        except Exception:
            pass
        return lst

    def _rebuild_gallery(self):  # pragma: no cover
        lst = self.gallery
        try:
            from PySide6.QtWidgets import QListWidgetItem  # type: ignore
            from PySide6.QtGui import QIcon  # type: ignore
            from PySide6.QtCore import QTimer  # type: ignore
        except Exception:
            return
        if not hasattr(lst, 'clear'):
            return
        try:
            lst.blockSignals(True)  # type: ignore
        except Exception:
            pass
        try:
            lst.clear()  # type: ignore
        except Exception:
            return
        if hasattr(self, '_gallery_items_by_path'):
            try:
                self._gallery_items_by_path.clear()  # type: ignore
            except Exception:
                self._gallery_items_by_path = {}
        try:
            entries = self._plugin.list_recent_detailed(limit=None)  # type: ignore[attr-defined]
        except Exception:
            entries = []
        # initial batch size
        initial = 40
        remaining: list[tuple[Any, Path]] = []  # type: ignore
        from PySide6.QtGui import QPixmap  # type: ignore
        for idx, (mf, root) in enumerate(entries):
            if idx >= initial:
                remaining.append((mf, root))
                continue
            abs_path = (root / mf.path).resolve(False)
            icon = None
            try:
                pix = self._cover_cache.get(abs_path, mf.kind)  # type: ignore
                icon = QIcon(pix)
            except Exception:
                pass
            item = QListWidgetItem(icon, abs_path.name if icon else mf.path)  # type: ignore
            item.setData(256, str(abs_path))  # type: ignore[attr-defined]
            try:
                lst.addItem(item)  # type: ignore
                self._gallery_items_by_path[str(abs_path)] = item  # type: ignore
            except Exception:
                continue

        def _load_remaining(batch=remaining):  # type: ignore
            try:
                for mf, root in batch:
                    abs_path = (root / mf.path).resolve(False)
                    icon = None
                    try:
                        pix = self._cover_cache.get(abs_path, mf.kind)  # type: ignore
                        icon = QIcon(pix)
                    except Exception:
                        pass
                    item = QListWidgetItem(icon, abs_path.name if icon else mf.path)  # type: ignore
                    item.setData(256, str(abs_path))  # type: ignore[attr-defined]
                    try:
                        lst.addItem(item)  # type: ignore
                        self._gallery_items_by_path[str(abs_path)] = item  # type: ignore
                    except Exception:
                        continue
            except Exception:
                pass
        # schedule remaining batch asynchronous so UI draws initial set first
        try:
            if remaining:
                QTimer.singleShot(10, _load_remaining)  # type: ignore[attr-defined]
        except Exception:
            _load_remaining()
        try:
            lst.blockSignals(False)  # type: ignore
        except Exception:
            pass

    def _on_gallery_selection_changed(self):  # pragma: no cover
        # when gallery selection changes, update table selection & detail
        try:
            sel_paths = []
            for item in self.gallery.selectedItems():  # type: ignore[attr-defined]
                p = item.data(256)  # type: ignore[attr-defined]
                if p:
                    from pathlib import Path as _P
                    sel_paths.append(_P(p))
            # naive: just update detail with first
            if sel_paths:
                self._update_detail_panel(sel_paths[0])
        except Exception:
            pass

    # --- detail panel ---
    def _build_detail_panel(self):
        # lazy simple panel; upgraded to interactive if Qt present
        try:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QLineEdit  # type: ignore
        except Exception:
            return QLabel("(Detail: wähle einen Eintrag)")  # type: ignore
        panel = QWidget(self)  # type: ignore
        panel.setObjectName("detailPanel")  # type: ignore
        layout = QVBoxLayout(panel)  # type: ignore
        layout.setContentsMargins(8,6,8,6)  # type: ignore
        title = QLabel("(Keine Auswahl)")  # type: ignore
        title.setObjectName("detailTitle")  # type: ignore
        title.setStyleSheet("font-weight:600;font-size:13px;color:#ddd;")  # type: ignore
        layout.addWidget(title)  # type: ignore
        info = QLabel("Wähle eine Datei…")  # type: ignore
        info.setObjectName("detailInfo")  # type: ignore
        info.setStyleSheet("color:#888;font-size:11px;")  # type: ignore
        info.setWordWrap(True)  # type: ignore
        layout.addWidget(info)  # type: ignore

        # rating bar
        rating_bar_container = QHBoxLayout()  # type: ignore
        rating_label = QLabel("Bewertung:")  # type: ignore
        rating_label.setStyleSheet("color:#aaa;font-size:11px;")  # type: ignore
        rating_bar_container.addWidget(rating_label)  # type: ignore
        stars = []  # runtime list; avoid strict typing to keep stub compatibility
        for i in range(5):
            star = QLabel("☆")  # type: ignore
            star.setStyleSheet("font-size:16px;color:#666;padding:0 2px;")  # type: ignore
            star.setProperty("star_index", i+1)  # type: ignore
            def _mk_handler(val: int):  # closure
                def _handler(event=None, v=val):  # type: ignore
                    if self._detail_current_path is not None:
                        try:
                            self._plugin.set_rating(self._detail_current_path, v)  # type: ignore[attr-defined]
                        except Exception:
                            pass
                        self._update_detail_panel(self._detail_current_path)  # refresh
                return _handler
            try:
                star.mousePressEvent = _mk_handler(i+1)  # type: ignore
            except Exception:
                pass
            stars.append(star)
            rating_bar_container.addWidget(star)  # type: ignore
        rating_bar_container.addStretch(1)  # type: ignore
        layout.addLayout(rating_bar_container)  # type: ignore

        # tags edit
        tag_row = QHBoxLayout()  # type: ignore
        tag_label = QLabel("Tags:")  # type: ignore
        tag_label.setStyleSheet("color:#aaa;font-size:11px;")  # type: ignore
        tag_row.addWidget(tag_label)  # type: ignore
        tag_edit = QLineEdit()  # type: ignore
        tag_edit.setPlaceholderText("tag1, tag2 …")  # type: ignore
        tag_edit.setObjectName("detailTagsEdit")  # type: ignore
        def _commit_tags():  # type: ignore
            if self._detail_current_path is None:
                return
            raw = tag_edit.text()  # type: ignore[attr-defined]
            tags = [t.strip() for t in raw.split(',') if t.strip()]
            try:
                self._plugin.set_tags(self._detail_current_path, tags)  # type: ignore[attr-defined]
            except Exception:
                pass
            self._update_detail_panel(self._detail_current_path)
        try:
            tag_edit.editingFinished.connect(_commit_tags)  # type: ignore[attr-defined]
        except Exception:
            pass
        tag_row.addWidget(tag_edit)  # type: ignore
        layout.addLayout(tag_row)  # type: ignore

        # store refs
        self._detail_title = title  # type: ignore
        self._detail_info = info  # type: ignore
        self._detail_stars = stars  # type: ignore
        self._detail_tag_edit = tag_edit  # type: ignore
        panel.setStyleSheet("#detailPanel{border-top:1px solid #303336;background:#1f2224;}")  # type: ignore
        return panel

    # --- view mode switching ---
    def _on_view_mode_changed(self, index: int) -> None:  # type: ignore
        try:
            mode = self._view_mode_combo.itemData(index)  # type: ignore
        except Exception:
            mode = "table"
        if mode == "table":
            try:
                self._stack.setCurrentIndex(0)  # type: ignore
                self.detail_panel.setVisible(True)  # type: ignore[attr-defined]
            except Exception:
                pass
        elif mode == "gallery":
            try:
                self._stack.setCurrentIndex(1)  # type: ignore
                self.detail_panel.setVisible(False)  # type: ignore[attr-defined]
            except Exception:
                pass
        elif mode == "split":
            # Replace stack with splitter lazily
            try:
                parent_layout = self.layout()  # type: ignore
                if parent_layout is not None:
                    # Hide stack if present
                    self._stack.setVisible(False)  # type: ignore
                    self.detail_panel.setVisible(False)  # type: ignore
                    if getattr(self, '_split_added', False) is False:
                        parent_layout.addWidget(self._split)  # type: ignore
                        self._split_added = True
            except Exception:
                pass
        # Persist view mode change
        self._save_state()

    # --- persistence helpers (simple dict under config key "enhanced_state")
    def _save_state(self):  # pragma: no cover - trivial
        try:
            cfg = self._plugin.config  # type: ignore[attr-defined]
            state = cfg.get("enhanced_state", {}) or {}
            # capture mode
            mode = None
            try:
                idx = self._view_mode_combo.currentIndex()  # type: ignore
                mode = self._view_mode_combo.itemData(idx)  # type: ignore
            except Exception:
                mode = "table"
            state.update({
                "view_mode": mode,
                "dashboard_visible": bool(self._dashboard.isVisible()),  # type: ignore[attr-defined]
                "selected_path": self._get_single_selection(),
                "smart_playlist": getattr(self, '_active_playlist_name', None),
                "rating_filter_min": getattr(self, '_rating_filter_min', 0),
                "tag_filter": getattr(self, '_tag_filter_expr', ""),
            })
            cfg["enhanced_state"] = state
        except Exception:
            pass

    def _restore_state(self):  # pragma: no cover - trivial
        try:
            cfg = self._plugin.config  # type: ignore[attr-defined]
            state = cfg.get("enhanced_state", {}) or {}
            # restore dashboard visibility
            if "dashboard_visible" in state:
                vis = bool(state.get("dashboard_visible"))
                self._dashboard.setVisible(vis)  # type: ignore[attr-defined]
                self._dashboard_toggle.setText("▼ Dashboard ausblenden" if vis else "▲ Dashboard einblenden")  # type: ignore[attr-defined]
            # restore view mode
            desired = state.get("view_mode")
            if desired:
                try:
                    for i in range(self._view_mode_combo.count()):  # type: ignore[attr-defined]
                        if self._view_mode_combo.itemData(i) == desired:  # type: ignore[attr-defined]
                            self._view_mode_combo.setCurrentIndex(i)  # type: ignore[attr-defined]
                            break
                except Exception:
                    pass
        except Exception:
            pass
        # store playlist desired name temporarily for later application (after load)
        try:
            self._restored_playlist_name = state.get('smart_playlist')  # type: ignore
        except Exception:
            self._restored_playlist_name = None  # type: ignore
        # restore filters
        try:
            _st = locals().get('state', {}) or {}
            self._rating_filter_min = int(_st.get('rating_filter_min', 0)) if isinstance(_st.get('rating_filter_min'), (int, float)) else 0
            self._tag_filter_expr = str(_st.get('tag_filter', ""))
        except Exception:
            self._rating_filter_min = 0
            self._tag_filter_expr = ""
        try:
            if hasattr(self, '_rating_filter_combo'):
                # find matching index
                for i in range(self._rating_filter_combo.count()):  # type: ignore[attr-defined]
                    if int(self._rating_filter_combo.itemData(i)) == self._rating_filter_min:  # type: ignore[attr-defined]
                        self._rating_filter_combo.setCurrentIndex(i)  # type: ignore[attr-defined]
                        break
            if getattr(self, '_tag_filter_expr', "") and hasattr(self, '_tag_filter_edit'):
                self._tag_filter_edit.setText(self._tag_filter_expr)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _get_single_selection(self):  # pragma: no cover - simple helper
        try:
            selected = self.table.selected_paths()  # type: ignore[attr-defined]
            if len(selected) == 1:
                return str(selected[0])
        except Exception:
            pass
        return None

    # --- scan integration -------------------------------------------------
    def _load_initial_entries(self) -> None:
        """Load initial media entries from the plugin."""
        try:
            import logging
            logger = logging.getLogger("mmst.media_library")
            logger.info("Enhanced widget loading initial entries...")
            
            if hasattr(self, '_debug_label'):
                self._debug_label.setText("Loading media entries...")  # type: ignore[attr-defined]
            
            # Try to get entries from plugin
            if hasattr(self._plugin, 'list_recent_detailed'):
                entries = self._plugin.list_recent_detailed()
                logger.info(f"Found {len(entries)} entries from plugin")
                
                if hasattr(self, '_debug_label'):
                    self._debug_label.setText(f"Loaded {len(entries)} media entries")  # type: ignore[attr-defined]
                    
                self._entries = list(entries)
                self._all_entries = list(entries)
                
                # Update UI components if they exist
                if hasattr(self, 'table') and hasattr(self.table, 'reload'):
                    try:
                        self.table.reload()  # type: ignore[attr-defined]
                        logger.info("Table reloaded with entries")
                    except Exception as e:
                        logger.error(f"Error reloading table: {e}")
                
                if hasattr(self, '_rebuild_gallery'):
                    try:
                        self._rebuild_gallery()
                        logger.info("Gallery rebuilt with entries")
                    except Exception as e:
                        logger.error(f"Error rebuilding gallery: {e}")
            else:
                logger.error("Plugin doesn't have list_recent_detailed method")
                if hasattr(self, '_debug_label'):
                    self._debug_label.setText("Error: Plugin API missing list_recent_detailed")  # type: ignore[attr-defined]
                
        except Exception as e:
            import logging
            logger = logging.getLogger("mmst.media_library")
            logger.error(f"Error loading initial entries: {e}")
            if hasattr(self, '_debug_label'):
                self._debug_label.setText(f"Error loading media: {str(e)}")  # type: ignore[attr-defined]
            
            # If no entries were found, try to scan default locations
            if hasattr(self._plugin, '_scan_default_locations'):
                try:
                    logger.info("Trying to scan default locations...")
                    if hasattr(self, '_debug_label'):
                        self._debug_label.setText("Scanning default locations...")  # type: ignore[attr-defined]
                    self._plugin._scan_default_locations()
                    
                    # Try to reload entries after scan
                    if hasattr(self._plugin, 'list_recent_detailed'):
                        entries = self._plugin.list_recent_detailed()
                        self._entries = list(entries)
                        self._all_entries = list(entries)
                        
                        if hasattr(self, '_debug_label'):
                            self._debug_label.setText(f"Found {len(entries)} entries after scan")  # type: ignore[attr-defined]
                            
                        # Update UI components
                        if hasattr(self, 'table') and hasattr(self.table, 'reload'):
                            self.table.reload()  # type: ignore[attr-defined]
                        if hasattr(self, '_rebuild_gallery'):
                            self._rebuild_gallery()
                except Exception as e2:
                    logger.error(f"Error during default scan: {e2}")
                    if hasattr(self, '_debug_label'):
                        self._debug_label.setText(f"Scan error: {str(e2)}")  # type: ignore[attr-defined]
    
    def _trigger_scan(self):  # pragma: no cover - UI interaction
        try:
            # Update debug label
            if hasattr(self, '_debug_label'):
                self._debug_label.setText("Opening directory dialog...")  # type: ignore[attr-defined]
            
            from PySide6.QtWidgets import QFileDialog, QMessageBox  # type: ignore
            directory = QFileDialog.getExistingDirectory(self, "Verzeichnis scannen")  # type: ignore[attr-defined]
            
            if directory:
                # Update debug label
                if hasattr(self, '_debug_label'):
                    self._debug_label.setText(f"Scanning {directory}...")  # type: ignore[attr-defined]
                
                roots = [Path(directory)]
                try:
                    # Ensure the plugin has scan_paths method
                    if hasattr(self._plugin, 'scan_paths'):
                        self._plugin.scan_paths(roots)  # type: ignore[attr-defined]
                        
                        # Update UI components
                        if hasattr(self, 'table') and hasattr(self.table, 'reload'):
                            self.table.reload()  # type: ignore[attr-defined]
                        if hasattr(self, '_rebuild_gallery'):
                            self._rebuild_gallery()
                            
                        # Try to emit signal safely
                        try:
                            if hasattr(self, 'library_changed') and callable(getattr(self, 'library_changed', None)):
                                self.library_changed.emit()  # type: ignore[attr-defined]
                        except Exception:
                            pass
                            
                        # Update debug label
                        if hasattr(self, '_debug_label'):
                            self._debug_label.setText(f"Scan of {directory} completed")  # type: ignore[attr-defined]
                        
                        # ensure watcher covers new root
                        if hasattr(self, '_add_paths_to_watcher'):
                            try:
                                self._add_paths_to_watcher(roots)
                            except Exception:
                                pass
                            
                    else:
                        if hasattr(self, '_debug_label'):
                            self._debug_label.setText("Error: Plugin missing scan_paths method")  # type: ignore[attr-defined]
                        QMessageBox.warning(self, "Scan Error", "The scan_paths method is not available in the plugin.")  # type: ignore[attr-defined]
                        
                except Exception as e:
                    import logging
                    logging.getLogger("mmst.media_library").error(f"Error scanning directory {directory}: {e}")
                    if hasattr(self, '_debug_label'):
                        self._debug_label.setText(f"Error: {str(e)}")  # type: ignore[attr-defined]
                    QMessageBox.critical(self, "Scan Error", f"An error occurred while scanning: {str(e)}")  # type: ignore[attr-defined]
                    
                # refresh playlist-filtered view if active
                    try:
                        self.table.reload()  # type: ignore[attr-defined]
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            return

    # --- selection handling / detail update -------------------------------
    def _on_selection_changed(self):  # pragma: no cover - UI logic
        # persist selection
        self._save_state()
        # update detail panel with basic metadata for now
        try:
            sel = self.table.selected_paths()  # type: ignore[attr-defined]
            if not sel:
                self._set_detail_empty()
                return
            if len(sel) > 1:
                self._set_detail_multi(len(sel))
                return
            self._update_detail_panel(sel[0])
        except Exception:
            pass

    # -- detail panel helpers ----------------------------------------------
    def _set_detail_empty(self):  # pragma: no cover
        try:
            if hasattr(self, '_detail_title'):
                self._detail_title.setText("(Keine Auswahl)")  # type: ignore[attr-defined]
                self._detail_info.setText("Wähle eine Datei…")  # type: ignore[attr-defined]
                self._detail_tag_edit.setText("")  # type: ignore[attr-defined]
                for s in getattr(self, '_detail_stars', []):
                    s.setText("☆")  # type: ignore
        except Exception:
            pass

    def _set_detail_multi(self, count: int):  # pragma: no cover
        try:
            if hasattr(self, '_detail_title'):
                self._detail_title.setText(f"{count} Dateien ausgewählt")  # type: ignore[attr-defined]
                self._detail_info.setText("Batch-Aktionen (Bewertung/Tags) folgen …")  # type: ignore[attr-defined]
                self._detail_tag_edit.setText("")  # type: ignore[attr-defined]
                for s in getattr(self, '_detail_stars', []):
                    s.setText("☆")  # type: ignore
        except Exception:
            pass

    def _update_detail_panel(self, target: Path):  # pragma: no cover - UI logic
        self._detail_current_path = target
        size = None; mtime = None
        try:
            st = target.stat(); size = st.st_size; mtime = st.st_mtime
        except Exception: pass
        rating = None; tags = []
        try:
            if getattr(self._plugin, '_library_index', None) is not None:
                rating, tags = self._plugin._library_index.get_attributes(target)  # type: ignore[attr-defined]
        except Exception: pass
        pretty_size = self._fmt_size(size) if size is not None else "?"
        from datetime import datetime
        ts = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M') if mtime else "?"
        try:
            if hasattr(self, '_detail_title'):
                self._detail_title.setText(target.name)  # type: ignore[attr-defined]
                self._detail_info.setText(f"Größe: {pretty_size} | Geändert: {ts}")  # type: ignore[attr-defined]
                self._detail_tag_edit.setText(", ".join(tags))  # type: ignore[attr-defined]
                # update stars
                for s in getattr(self, '_detail_stars', []):
                    idx = int(getattr(s, 'property', lambda x:0)('star_index')) if hasattr(s,'property') else 0  # type: ignore
                    filled = rating is not None and rating >= idx
                    s.setText('★' if filled else '☆')  # type: ignore
                    s.setStyleSheet("font-size:16px;" + ("color:#e0b100;" if filled else "color:#555;"))  # type: ignore
        except Exception:
            pass

    def _fmt_size(self, size: int) -> str:  # pragma: no cover - helper
        try:
            value = float(size)
            for unit in ['B','KB','MB','GB','TB']:
                if value < 1024 or unit == 'TB':
                    if unit == 'B':
                        return f"{int(value)} {unit}"
                    return f"{value:.1f} {unit}"
                value /= 1024.0
        except Exception:
            return "?"
        return f"{value:.1f} PB"

    # --------------------------- filesystem watcher -------------------------
    def _maybe_start_watcher(self):  # pragma: no cover - runtime integration
        try:
            if self._watcher is not None:
                return
            w = FileSystemWatcher()  # type: ignore
            if not w.is_available:  # type: ignore[attr-defined]
                return
            started = w.start(
                on_created=lambda p: self._on_fs_event('created', p),
                on_modified=lambda p: self._on_fs_event('modified', p),
                on_deleted=lambda p: self._on_fs_event('deleted', p),
                on_moved=lambda a, b: self._on_fs_event('moved', b),
            )
            if not started:
                return
            self._watcher = w
            # Add existing sources from backend if present
            try:
                idx = getattr(self._plugin, '_library_index', None)
                if idx is not None and hasattr(idx, 'list_sources'):
                    for _sid, spath in idx.list_sources():  # type: ignore[attr-defined]
                        self._add_paths_to_watcher([Path(spath)])
            except Exception:
                pass
        except Exception:
            self._watcher = None

    def _add_paths_to_watcher(self, roots):  # pragma: no cover - helper
        if not self._watcher:
            return
        for r in roots:
            try:
                self._watcher.add_path(Path(r))  # type: ignore[attr-defined]
            except Exception:
                continue

    def _on_fs_event(self, kind: str, path: Path):  # pragma: no cover - callback
        # Debounce multiple rapid events (especially on large moves/copies)
        try:
            self._pending_refresh = True
            from PySide6.QtCore import QTimer  # type: ignore
            # Use singleShot to schedule after short delay (250ms)
            def _do_refresh():  # type: ignore
                if not self._pending_refresh:
                    return
                self._pending_refresh = False
                self._refresh_after_fs()
            # cancel logic not needed; simply schedule new ones
            QTimer.singleShot(250, _do_refresh)  # type: ignore[attr-defined]
        except Exception:
            # Fallback: immediate refresh
            self._refresh_after_fs()

    def _refresh_after_fs(self):  # pragma: no cover
        try:
            # Re-read listing & rebuild UI facets
            self.table.reload()  # type: ignore[attr-defined]
            self._rebuild_gallery()
            if hasattr(self._dashboard, 'refresh'):
                self._dashboard.refresh()  # type: ignore[attr-defined]
            self.library_changed.emit()  # type: ignore[attr-defined]
        except Exception:
            pass

    # --------------------------- smart playlists ----------------------------
    def _load_smart_playlists(self):  # pragma: no cover - IO
        self._smart_playlists: list[SmartPlaylist] = []  # type: ignore
        self._active_playlist_name: str | None = None  # type: ignore
        # Attempt user config dir first (data dir / smart_playlists.json)
        paths_to_try = []
        try:
            data_dir = self._plugin.services.data_dir  # type: ignore[attr-defined]
            paths_to_try.append(data_dir / 'smart_playlists.json')
        except Exception:
            pass
        try:
            # bundled default (repo root relative) – climb up until 'smart_playlists.json'
            base = Path(__file__).resolve().parent.parent.parent.parent
            paths_to_try.append(base / 'smart_playlists.json')
        except Exception:
            pass
        seen = set()
        for p in paths_to_try:
            if not p or p in seen:
                continue
            seen.add(p)
            try:
                pls = load_smart_playlists(p)  # type: ignore[attr-defined]
                if pls:
                    self._smart_playlists.extend(pls)
            except Exception:
                continue
        # populate combo
        try:
            if hasattr(self, '_playlist_combo'):
                for sp in self._smart_playlists:
                    self._playlist_combo.addItem(sp.name, sp.name)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _apply_restored_playlist_selection(self):  # pragma: no cover
        name = getattr(self, '_restored_playlist_name', None)
        if not name:
            return
        try:
            for i in range(self._playlist_combo.count()):  # type: ignore[attr-defined]
                if self._playlist_combo.itemData(i) == name:  # type: ignore[attr-defined]
                    self._playlist_combo.setCurrentIndex(i)  # type: ignore[attr-defined]
                    break
        except Exception:
            pass

    def _on_playlist_changed(self):  # pragma: no cover - UI callback
        try:
            idx = self._playlist_combo.currentIndex()  # type: ignore[attr-defined]
            val = self._playlist_combo.itemData(idx)  # type: ignore[attr-defined]
            self._active_playlist_name = val if val else None  # type: ignore
            # refresh table to apply filter
            self.table.reload()  # type: ignore[attr-defined]
            self._save_state()
        except Exception:
            pass

    def get_active_playlist(self) -> SmartPlaylist | None:  # used by table
        try:
            if not getattr(self, '_active_playlist_name', None):
                return None
            for sp in getattr(self, '_smart_playlists', []):
                if sp.name == self._active_playlist_name:
                    return sp
        except Exception:
            return None
        return None

    # rating / tag filter handlers
    def _on_rating_filter_changed(self):  # pragma: no cover
        try:
            idx = self._rating_filter_combo.currentIndex()  # type: ignore[attr-defined]
            self._rating_filter_min = int(self._rating_filter_combo.itemData(idx))  # type: ignore[attr-defined]
            self.table.reload()  # type: ignore[attr-defined]
            self._save_state()
        except Exception:
            pass

    def _on_tag_filter_changed(self):  # pragma: no cover
        try:
            self._tag_filter_expr = self._tag_filter_edit.text().strip()  # type: ignore[attr-defined]
            self.table.reload()  # type: ignore[attr-defined]
            self._save_state()
        except Exception:
            pass

    def get_active_attribute_filters(self):  # consumed by table filtering
        return getattr(self, '_rating_filter_min', 0), getattr(self, '_tag_filter_expr', "")
