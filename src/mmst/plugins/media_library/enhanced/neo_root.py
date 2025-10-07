from __future__ import annotations
"""ULTRA Media Library Root (early scaffold)
Netflix / Spotify / Explorer inspired composite UI.

Goals:
- Left sidebar: navigation (sources, playlists, smart, tags) + actions
- Top bar: search, filter chips, view mode toggles, command palette trigger
- Center: stacked views (Home Dashboard, Library Grid, Table, Now Playing, Stats)
- Home: Hero banner + multiple carousels (recent, top rated, by tag)
- Bottom: player bar with queue toggle
- Non-blocking; remains headless-safe via broad try/except wrappers
"""
from typing import Any, List, Tuple, Dict, Callable
from pathlib import Path

try:  # Qt imports (guarded)
    from PySide6.QtWidgets import (  # type: ignore
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
        QStackedWidget, QFrame, QScrollArea
    )
    from PySide6.QtCore import Qt, Signal  # type: ignore
except Exception:  # pragma: no cover
    QWidget = object  # type: ignore
    QVBoxLayout = QHBoxLayout = QStackedWidget = QFrame = QScrollArea = QLabel = QPushButton = QLineEdit = object  # type: ignore
    Signal = lambda *a, **k: None  # type: ignore
    Qt = object  # type: ignore

from ..covers import CoverCache  # type: ignore
from ..core import MediaFile  # type: ignore
from ..smart_playlists import evaluate_smart_playlist  # type: ignore
from ..smart_playlists import load_smart_playlists, save_smart_playlists, SmartPlaylist  # type: ignore
from ..watcher import FileSystemWatcher  # type: ignore
from ..metadata import MediaMetadata  # type: ignore

# Reuse view components
from ..views.enhanced.hero import HeroWidget  # type: ignore
from ..views.enhanced.carousel import MediaCarousel  # type: ignore
from ..views.enhanced.sidebar import Sidebar  # type: ignore
from ..views.enhanced.command_palette import CommandPalette  # type: ignore
from .chip_bar import ChipBarWidget  # type: ignore
from .table_view import EnhancedTableWidget  # type: ignore
from .base import EnhancedRootWidget  # type: ignore
from .mini_player import MiniPlayerWidget  # type: ignore


class UltraRoot(QWidget):  # type: ignore[misc]
    library_changed = Signal()  # type: ignore

    def __init__(self, plugin: Any):
        super().__init__()
        self._plugin = plugin
        self._cover_cache = CoverCache()  # type: ignore
        self._watcher: FileSystemWatcher | None = None  # type: ignore
        self._pending_refresh = False
        self._metadata_cache: Dict[str, MediaMetadata] = {}
        # filter state (rating + tags)
        self._rating_min_filter: int = 0
        self._tag_filter_tags: List[str] = []
        try:
            self.setObjectName("UltraMediaLibraryRoot")  # type: ignore
            self.setStyleSheet(self._stylesheet())  # type: ignore
        except Exception:
            pass

        # Layout skeleton -------------------------------------------------
        try:  # GUI construction (skip silently if running headless)
            root = QVBoxLayout(self)  # type: ignore
            root.setContentsMargins(0,0,0,0)  # type: ignore
            chrome = QHBoxLayout()  # type: ignore
            root.addLayout(chrome)  # type: ignore

            # Sidebar ----------------------------------------------------
            self._sidebar = Sidebar(self._sidebar_provider)  # type: ignore
            try: self._sidebar.on_select(self._on_sidebar_select)  # type: ignore
            except Exception: pass
            # Inject callbacks for CRUD (playlists, smart playlists, tags)
            try:
                self._sidebar.set_playlist_callbacks(
                    new_cb=lambda name: self._pl_create(name),
                    rename_cb=lambda old, new: self._pl_rename(old, new),
                    delete_cb=lambda old: self._pl_delete(old),
                )  # type: ignore[attr-defined]
                self._sidebar.set_smart_callbacks(new_cb=lambda name: self._sp_create(name))  # type: ignore[attr-defined]
                self._sidebar.set_tag_callbacks(
                    new_cb=lambda name: self._tag_create(name),
                    rename_cb=lambda old, new: self._tag_rename(old, new),
                    delete_cb=lambda old: self._tag_delete(old),
                )  # type: ignore[attr-defined]
            except Exception:
                pass
            chrome.addWidget(self._sidebar)  # type: ignore

            # Main column ------------------------------------------------
            main_col = QVBoxLayout()  # type: ignore
            chrome.addLayout(main_col, 1)  # type: ignore

            # Top bar (search + command + view buttons + settings)
            top_bar = QHBoxLayout()  # type: ignore
            main_col.addLayout(top_bar)  # type: ignore
            self._search_edit = QLineEdit()  # type: ignore
            try:
                if hasattr(self._search_edit, 'setPlaceholderText'):
                    self._search_edit.setPlaceholderText("Suchen… (Ctrl+K für Befehle)")  # type: ignore
                if hasattr(self._search_edit, 'textChanged'):
                    self._search_edit.textChanged.connect(self._on_search)  # type: ignore[attr-defined]
            except Exception:
                pass
            top_bar.addWidget(self._search_edit)  # type: ignore
            self._cmd_btn = QPushButton("⌘ Palette")  # type: ignore
            try: self._cmd_btn.clicked.connect(self._open_command_palette)  # type: ignore
            except Exception: pass
            top_bar.addWidget(self._cmd_btn)  # type: ignore
            # Rating filter combo
            try:
                from PySide6.QtWidgets import QComboBox  # type: ignore
                self._rating_combo = QComboBox()  # type: ignore
                self._rating_combo.addItem("⭐ min", 0)  # type: ignore[attr-defined]
                for i in range(1,6):
                    self._rating_combo.addItem("≥ " + "★"*i, i)  # type: ignore[attr-defined]
                self._rating_combo.currentIndexChanged.connect(self._on_rating_changed)  # type: ignore[attr-defined]
                top_bar.addWidget(self._rating_combo)  # type: ignore
            except Exception:
                self._rating_combo = None  # type: ignore
            # Tag add edit
            try:
                from PySide6.QtWidgets import QLineEdit  # type: ignore
                self._tag_add_edit = QLineEdit()  # type: ignore
                self._tag_add_edit.setPlaceholderText("Tags hinzufügen (Enter)")  # type: ignore[attr-defined]
                self._tag_add_edit.returnPressed.connect(self._on_add_tags)  # type: ignore[attr-defined]
                top_bar.addWidget(self._tag_add_edit)  # type: ignore
            except Exception:
                self._tag_add_edit = None  # type: ignore
            # Chip bar lives under top bar (but inside same column for tight grouping)
            self._chip_bar = ChipBarWidget()  # type: ignore
            try:
                # listen for chip removal to clear filters
                self._chip_bar.chip_removed.connect(self._on_chip_removed)  # type: ignore[attr-defined]
            except Exception:
                pass
            main_col.addWidget(self._chip_bar)  # type: ignore
            self._view_table_btn = QPushButton("Tabelle")  # type: ignore
            self._view_grid_btn = QPushButton("Galerie")  # type: ignore
            for b in (self._view_table_btn, self._view_grid_btn):
                try: b.clicked.connect(lambda _=False, bb=b: self._switch_view(bb))  # type: ignore
                except Exception: pass
                top_bar.addWidget(b)  # type: ignore
            top_bar.addStretch(1)  # type: ignore
            self._settings_btn = QPushButton("⚙")  # type: ignore
            try: self._settings_btn.clicked.connect(self._open_settings)  # type: ignore
            except Exception: pass
            top_bar.addWidget(self._settings_btn)  # type: ignore

            # Stacked center views
            self._stack = QStackedWidget()  # type: ignore
            main_col.addWidget(self._stack, 1)  # type: ignore

            # Home dashboard (hero + carousels inside scroll)
            home_frame = QFrame()  # type: ignore
            home_layout = QVBoxLayout(home_frame)  # type: ignore
            self._hero = HeroWidget(self._recent_media_provider)  # type: ignore
            home_layout.addWidget(self._hero)  # type: ignore
            # carousels
            self._carousel_recent = MediaCarousel("Zuletzt hinzugefügt", self._recent_media_provider, chunk_size=12)  # type: ignore
            self._carousel_top = MediaCarousel("Top bewertet", self._top_rated_provider, chunk_size=12)  # type: ignore
            self._carousel_tags = MediaCarousel("Tags", self._tag_highlight_provider, chunk_size=12)  # type: ignore
            for c in (self._carousel_recent, self._carousel_top, self._carousel_tags):
                home_layout.addWidget(c)  # type: ignore
            home_layout.addStretch(1)  # type: ignore
            scroll = QScrollArea()  # type: ignore
            scroll.setWidgetResizable(True)  # type: ignore
            scroll.setWidget(home_frame)  # type: ignore
            self._stack.addWidget(scroll)  # type: ignore

            # Real table & gallery integration (reuse EnhancedTableWidget + gallery from EnhancedRootWidget)
            # Build a hidden EnhancedRootWidget to leverage existing gallery construction & filtering logic.
            try:
                self._enhanced_hidden = EnhancedRootWidget(plugin)  # type: ignore
            except Exception:
                self._enhanced_hidden = None  # type: ignore
            # Table
            try:
                self._table_view = EnhancedTableWidget(plugin)  # type: ignore
            except Exception:
                self._table_view = QLabel("(Tabelle nicht verfügbar)")  # type: ignore
            # Gallery from hidden root if available
            try:
                self._gallery_view = getattr(self._enhanced_hidden, 'gallery', QLabel("(Galerie nicht verfügbar)"))  # type: ignore[attr-defined]
            except Exception:
                self._gallery_view = QLabel("(Galerie nicht verfügbar)")  # type: ignore
            self._stack.addWidget(self._table_view)  # type: ignore
            self._stack.addWidget(self._gallery_view)  # type: ignore

            # Bottom player bar
            player_frame = QFrame()  # type: ignore
            player_frame.setObjectName("playerBar")  # type: ignore
            pf_layout = QHBoxLayout(player_frame)  # type: ignore
            pf_layout.setContentsMargins(4,2,4,2)  # type: ignore
            self._mini_player = MiniPlayerWidget(plugin)  # type: ignore
            try:
                pf_layout.addWidget(self._mini_player)  # type: ignore
            except Exception: pass
            root.addWidget(player_frame)  # type: ignore
        except Exception:
            pass

        # Post-construction service setup
        self._command_palette = None  # type: ignore
        self._commands = {}  # type: ignore
        self._register_default_commands()
        self._install_shortcuts()
        self._populate_initial()
        # Expose self as enhanced root reference so table filtering picks up rating/tag filters
        try:
            setattr(self._plugin, '_enhanced_root_ref', self)
        except Exception:
            pass

        # -------------------- queue / playback model (lightweight) --------------------
        self._queue: List[Any] = []  # holds MediaFile references
        self._current_index: int = -1
        self._is_playing: bool = False
        # Connect mini player signals
        try:
            if hasattr(self, '_mini_player'):
                mp = self._mini_player  # type: ignore
                if hasattr(mp, 'play_toggled'):
                    mp.play_toggled.connect(self._on_play_toggled)  # type: ignore[attr-defined]
                if hasattr(mp, 'next_requested'):
                    mp.next_requested.connect(lambda: self.queue_next())  # type: ignore[attr-defined]
                if hasattr(mp, 'previous_requested'):
                    mp.previous_requested.connect(lambda: self.queue_prev())  # type: ignore[attr-defined]
        except Exception:
            pass

    # -------------------- styling -------------------------
    def _stylesheet(self) -> str:
        return (
            "#UltraMediaLibraryRoot{background:#141618;color:#d0d3d5;}"
            "#UltraMediaLibraryRoot QLineEdit{background:#1e2123;border:1px solid #343a3d;padding:4px;border-radius:4px;}"
            "#UltraMediaLibraryRoot QPushButton{background:#1f2224;border:1px solid #353a3e;padding:4px 8px;border-radius:4px;}"
            "#UltraMediaLibraryRoot QPushButton:hover{border-color:#4a545a;}"
            "#UltraMediaLibraryRoot #playerBar{background:#181a1c;border-top:1px solid #2c3134;}"
            "#hero_title{color:#fff;}#carousel_heading{color:#cfd2d4;}#carousel_card{background:#232628;}"
        )

    # -------------------- data providers ------------------
    def _recent_media_provider(self) -> List[Any]:  # type: ignore
        try:
            entries = self._plugin.list_recent_detailed(limit=50)  # type: ignore[attr-defined]
            return [e[0] for e in entries]
        except Exception:
            return []

    def _top_rated_provider(self) -> List[Any]:  # type: ignore
        try:
            entries = self._plugin.list_recent_detailed(limit=None)
            out = []
            for mf, root in entries:
                if getattr(mf, 'rating', None) and mf.rating >= 4:
                    out.append(mf)
            return out[:50]
        except Exception:
            return []

    def _tag_highlight_provider(self) -> List[Any]:  # type: ignore
        try:
            entries = self._plugin.list_recent_detailed(limit=None)
            tag_map: Dict[str,int] = {}
            for mf, _ in entries:
                for t in getattr(mf, 'tags', []) or []:
                    tag_map[t] = tag_map.get(t,0)+1
            # Represent tags as lightweight objects with title attr
            class _TagObj:
                def __init__(self, name: str, count: int):
                    self.title = f"{name} ({count})"
            ranked = sorted(( _TagObj(k,v) for k,v in tag_map.items() ), key=lambda x: -int(x.title.split('(')[-1].split(')')[0]))
            return list(ranked)[:40]
        except Exception:
            return []

    def _sidebar_provider(self, section: str):  # type: ignore
        try:
            if section == 'sources':
                idx = getattr(self._plugin, '_library_index', None)
                if idx and hasattr(idx, 'list_sources'):
                    return [{"name": p} for _id, p in idx.list_sources()]
            if section == 'playlists':
                # real playlists from index
                idx = getattr(self._plugin, '_library_index', None)
                if idx and hasattr(idx, 'list_playlists'):
                    out = []
                    for pid, name, count in idx.list_playlists():
                        out.append({"name": name, "count": count, "pid": pid})
                    return out
                return []
            if section == 'smart':
                plist = self._load_cached_smart()
                return [{"name": sp.name, "sid": i} for i, sp in enumerate(plist)]
            if section == 'tags':
                entries = self._plugin.list_recent_detailed(limit=None)
                tag_set = set()
                for mf, _ in entries:
                    for t in getattr(mf, 'tags', []) or []:
                        tag_set.add(t)
                return [{"name": t} for t in sorted(tag_set)]
            if section == 'actions':
                return [{"name": "Scan"},{"name":"Refresh"}]
            return []
        except Exception:
            return []

    # -------------------- interactions --------------------
    def _populate_initial(self):  # prime hero/carousels
        try:
            self._hero.refresh()  # type: ignore[attr-defined]
            for c in (self._carousel_recent, self._carousel_top, self._carousel_tags):
                c.refresh()  # type: ignore[attr-defined]
        except Exception:
            pass

    def _on_sidebar_select(self, section: str, payload: Dict[str, Any]):  # type: ignore
        # Future: switch views / apply filters based on sidebar selection
        name = payload.get("name") if isinstance(payload, dict) else None
        if section == 'actions' and name == 'Scan':
            # delegate to existing scan dialog if available (reuse minimal path soon)
            try:
                # simplest: open OS dialog not implemented yet
                pass
            except Exception:
                pass
        elif section == 'playlists' and payload:
            # future: filter table by playlist content
            pass
        elif section == 'smart' and payload:
            # evaluate smart and maybe switch to table view
            try:
                sid = payload.get('sid')
                plist = self._load_cached_smart()
                if isinstance(sid, int) and 0 <= sid < len(plist):
                    # placeholder: simply show table
                    self._stack.setCurrentIndex(1)  # type: ignore[attr-defined]
            except Exception:
                pass
        elif section == 'tags' and payload:
            tag = payload.get('name')
            if tag:
                if tag not in self._tag_filter_tags:
                    self._tag_filter_tags.append(tag)
                self._reload_views(); self._update_filter_chips()

    def _switch_view(self, btn):  # type: ignore
        try:
            if not hasattr(self, '_stack') or not hasattr(self._stack, 'setCurrentIndex'):
                return
            if btn is self._view_table_btn:
                self._stack.setCurrentIndex(1)  # type: ignore[attr-defined]
            elif btn is self._view_grid_btn:
                self._stack.setCurrentIndex(2)  # type: ignore[attr-defined]
            else:
                self._stack.setCurrentIndex(0)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _on_search(self, text: str):  # type: ignore
        # Update chip bar and propagate to plugin (search filter attribute if available)
        try:
            self._update_filter_chips(search_override=text)
            # propagate to plugin minimal filter contract
            if hasattr(self._plugin, 'set_text_filter'):
                self._plugin.set_text_filter(text)  # type: ignore[attr-defined]
            else:
                # fallback: set attribute used by underlying query logic if exists
                setattr(self._plugin, '_search_text', text)
            # propagate to table & gallery if present
            if hasattr(self, '_table_view') and hasattr(self._table_view, '_on_search'):
                try: self._table_view._on_search(text)  # type: ignore[attr-defined]
                except Exception: pass
            if hasattr(self, '_enhanced_hidden'):
                # gallery filtering relies on rebuild; trigger underlying root refresh
                try:
                    if hasattr(self._enhanced_hidden, 'refresh'):
                        self._enhanced_hidden.refresh()  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception:
            pass

    def _on_chip_removed(self, key: str):  # type: ignore
        # Clear corresponding filter
        try:
            if key.startswith('search'):
                if hasattr(self, '_search_edit'):
                    self._search_edit.setText("")  # type: ignore[attr-defined]
                self._on_search("")
            elif key == 'rating':
                self._rating_min_filter = 0
                try:
                    if self._rating_combo is not None and hasattr(self._rating_combo, 'setCurrentIndex'):
                        self._rating_combo.setCurrentIndex(0)  # type: ignore[attr-defined]
                except Exception: pass
                self._reload_views()
            elif key.startswith('tag:'):
                tag = key.split(':',1)[1]
                self._tag_filter_tags = [t for t in self._tag_filter_tags if t.lower()!=tag.lower()]
                self._reload_views()
            elif key == 'tags':  # aggregated
                self._tag_filter_tags.clear()
                self._reload_views()
            self._update_filter_chips()
        except Exception:
            pass

    def _open_command_palette(self):  # type: ignore
        try:
            if self._command_palette is None:
                self._command_palette = CommandPalette(self._plugin, self._commands)  # type: ignore
            self._command_palette.open()  # type: ignore[attr-defined]
        except Exception:
            pass

    def _open_settings(self):  # type: ignore
        # Placeholder for settings overlay
        pass

    # -------------------- playlist CRUD ------------------
    def _pl_create(self, name: str):  # type: ignore
        idx = getattr(self._plugin, '_library_index', None)
        try:
            if idx and hasattr(idx, 'create_playlist'):
                idx.create_playlist(name)  # type: ignore[attr-defined]
        except Exception: pass
        self._sidebar.refresh()  # type: ignore[attr-defined]

    def _pl_find_id(self, name: str) -> int | None:  # helper
        idx = getattr(self._plugin, '_library_index', None)
        try:
            if not idx or not hasattr(idx, 'list_playlists'):
                return None
            for pid, n, count in idx.list_playlists():
                if n == name:
                    return pid
        except Exception: return None
        return None

    def _pl_rename(self, old: str, new: str):  # type: ignore
        pid = self._pl_find_id(old)
        if pid is None:
            return
        idx = getattr(self._plugin, '_library_index', None)
        try:
            if idx and hasattr(idx, 'rename_playlist'):
                idx.rename_playlist(pid, new)  # type: ignore[attr-defined]
        except Exception: pass
        self._sidebar.refresh()  # type: ignore[attr-defined]

    def _pl_delete(self, name: str):  # type: ignore
        pid = self._pl_find_id(name)
        if pid is None:
            return
        idx = getattr(self._plugin, '_library_index', None)
        try:
            if idx and hasattr(idx, 'delete_playlist'):
                idx.delete_playlist(pid)  # type: ignore[attr-defined]
        except Exception: pass
        self._sidebar.refresh()  # type: ignore[attr-defined]

    # -------------------- smart playlists ----------------
    def _smart_storage_path(self):  # type: ignore
        try:
            return self._plugin.services.ensure_subdirectories('smart')[0] / 'smart_playlists.json'  # type: ignore[attr-defined]
        except Exception:
            return None

    def _load_cached_smart(self) -> List[SmartPlaylist]:  # type: ignore
        if not hasattr(self, '_smart_cache'):
            self._smart_cache = None  # type: ignore
        if self._smart_cache is None:  # type: ignore
            path = self._smart_storage_path()
            if path and path.exists():
                try: self._smart_cache = load_smart_playlists(path)  # type: ignore[attr-defined]
                except Exception: self._smart_cache = []  # type: ignore[attr-defined]
            else:
                self._smart_cache = []  # type: ignore[attr-defined]
        return self._smart_cache  # type: ignore

    def _sp_create(self, name: str):  # type: ignore
        path = self._smart_storage_path()
        if not path:
            return
        plist = self._load_cached_smart()
        try:
            # simple empty smart playlist object
            sp = SmartPlaylist(name=name, description="", rules=[], limit=None, sort=None)  # type: ignore[attr-defined]
            plist.append(sp)
            save_smart_playlists(path, plist)  # type: ignore[attr-defined]
            self._smart_cache = plist  # type: ignore[attr-defined]
        except Exception: pass
        self._sidebar.refresh()  # type: ignore[attr-defined]

    # -------------------- tags (simple global tag set editing) -------------
    def _tag_create(self, name: str):  # type: ignore
        # tags are implicit; creating just ensures a chip possibility – no-op until tag is assigned via batch
        if name not in self._tag_filter_tags:
            self._tag_filter_tags.append(name)
        self._update_filter_chips(); self._sidebar.refresh()  # type: ignore[attr-defined]

    def _tag_rename(self, old: str, new: str):  # type: ignore
        # renaming tag across DB requires metadata updates; placeholder updates active filter list only
        self._tag_filter_tags = [new if t==old else t for t in self._tag_filter_tags]
        self._reload_views(); self._update_filter_chips(); self._sidebar.refresh()  # type: ignore[attr-defined]

    def _tag_delete(self, name: str):  # type: ignore
        self._tag_filter_tags = [t for t in self._tag_filter_tags if t!=name]
        self._reload_views(); self._update_filter_chips(); self._sidebar.refresh()  # type: ignore[attr-defined]

    # -------------------- filter helpers ------------------
    def _on_rating_changed(self, index: int):  # type: ignore
        try:
            if self._rating_combo is None:
                return
            data = self._rating_combo.itemData(index)  # type: ignore[attr-defined]
            self._rating_min_filter = int(data) if data is not None else 0
        except Exception:
            self._rating_min_filter = 0
        self._reload_views(); self._update_filter_chips()

    def _on_add_tags(self):  # type: ignore
        try:
            if self._tag_add_edit is None:
                return
            raw = self._tag_add_edit.text()  # type: ignore[attr-defined]
            if not raw.strip():
                return
            parts = [p.strip() for p in raw.split(',') if p.strip()]
            for p in parts:
                if p not in self._tag_filter_tags:
                    self._tag_filter_tags.append(p)
            try: self._tag_add_edit.clear()  # type: ignore[attr-defined]
            except Exception: pass
        except Exception:
            pass
        self._reload_views(); self._update_filter_chips()

    def _reload_views(self):  # type: ignore
        try:
            if hasattr(self, '_table_view') and hasattr(self._table_view, 'reload'):
                self._table_view.reload()  # type: ignore[attr-defined]
        except Exception: pass
        # Gallery refresh via hidden root if exists
        try:
            if self._enhanced_hidden and hasattr(self._enhanced_hidden, 'refresh'):
                self._enhanced_hidden.refresh()  # type: ignore[attr-defined]
        except Exception: pass

    def _update_filter_chips(self, *, search_override: str|None=None):  # type: ignore
        try:
            if not hasattr(self, '_chip_bar'):
                return
            search_text = search_override if search_override is not None else (self._search_edit.text() if hasattr(self._search_edit,'text') else "")  # type: ignore[attr-defined]
            self._chip_bar.set_state(
                search=search_text or None,
                rating_min=self._rating_min_filter or None,
                tags=list(self._tag_filter_tags) if self._tag_filter_tags else None,
            )  # type: ignore[attr-defined]
        except Exception:
            pass

    # API used by EnhancedTableWidget for rating/tag filters
    def get_active_attribute_filters(self) -> Tuple[int, str]:  # type: ignore
        tag_expr = ",".join(self._tag_filter_tags)
        return self._rating_min_filter, tag_expr

    # -------------------- commands & shortcuts -----------------
    def _register_default_commands(self):
        def _home():
            try: self._stack.setCurrentIndex(0)  # type: ignore[attr-defined]
            except Exception: pass
        def _table():
            try: self._stack.setCurrentIndex(1); self._table_view.reload()  # type: ignore[attr-defined]
            except Exception: pass
        def _grid():
            try: self._stack.setCurrentIndex(2)  # type: ignore[attr-defined]
            except Exception: pass
        def _scan():
            # delegate to plugin scan method if available
            try:
                if hasattr(self._plugin, 'open_scan_dialog'):
                    self._plugin.open_scan_dialog()  # type: ignore[attr-defined]
            except Exception:
                pass
        def _settings():
            self._open_settings()
        def _toggle_play():
            self._toggle_play_clicked()
        self._commands = {
            "Home": _home,
            "Ansicht: Tabelle": _table,
            "Ansicht: Galerie": _grid,
            "Bibliothek scannen…": _scan,
            "Einstellungen": _settings,
            "Play/Pause": _toggle_play,
        }

    def _install_shortcuts(self):
        try:
            from PySide6.QtWidgets import QShortcut  # type: ignore
            from PySide6.QtGui import QKeySequence  # type: ignore
        except Exception:
            return
        try:
            QShortcut(QKeySequence("Ctrl+K"), self, activated=self._open_command_palette)  # type: ignore
            QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self._stack.setCurrentIndex(0))  # type: ignore[attr-defined]
            QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self._stack.setCurrentIndex(1))  # type: ignore[attr-defined]
            QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self._stack.setCurrentIndex(2))  # type: ignore[attr-defined]
        except Exception:
            pass

    # -------------------- queue API --------------------
    def queue_add(self, items: List[Any], play_now: bool=False):  # type: ignore
        """Append items to queue; optionally start playing first of new batch."""
        if not items:
            return
        try:
            self._queue.extend(items)
            if play_now or self._current_index == -1:
                # start at first of newly added (tail region len before add tracked?)
                start_index = len(self._queue) - len(items)
                self._play_index(start_index)
        except Exception:
            pass

    def _play_index(self, i: int):  # type: ignore
        if i < 0 or i >= len(self._queue):
            return
        self._current_index = i
        mf = self._queue[i]
        # Update title label
        try:
            title = getattr(mf, 'title', None) or getattr(mf, 'name', None) or getattr(mf, 'path', None)
            if hasattr(self, '_mini_player') and hasattr(self._mini_player, 'set_title'):
                self._mini_player.set_title(str(title))  # type: ignore[attr-defined]
        except Exception:
            pass
        # Simulate beginning playback
        self._is_playing = True
        self._sync_play_icon()

    def queue_next(self):  # type: ignore
        if not self._queue:
            return
        ni = self._current_index + 1
        if ni >= len(self._queue):
            ni = 0  # wrap
        self._play_index(ni)

    def queue_prev(self):  # type: ignore
        if not self._queue:
            return
        pi = self._current_index - 1
        if pi < 0:
            pi = len(self._queue) - 1
        self._play_index(pi)

    def queue_clear(self):  # type: ignore
        self._queue.clear()
        self._current_index = -1
        self._is_playing = False
        try:
            if hasattr(self, '_mini_player') and hasattr(self._mini_player, 'set_title'):
                self._mini_player.set_title('(keine Warteschlange)')  # type: ignore[attr-defined]
        except Exception:
            pass
        self._sync_play_icon()

    def _toggle_play_clicked(self):  # type: ignore
        # If nothing queued, ignore
        if not self._queue:
            return
        self._is_playing = not self._is_playing
        self._sync_play_icon()

    def _sync_play_icon(self):  # type: ignore
        try:
            if hasattr(self, '_mini_player') and hasattr(self._mini_player, 'play_btn') and hasattr(self._mini_player.play_btn, 'setText'):
                self._mini_player.play_btn.setText('⏸' if self._is_playing else '▶')  # type: ignore[attr-defined]
        except Exception:
            pass

    def _on_play_toggled(self, state: bool):  # type: ignore
        # mini player emitted toggle; sync internal flag (ignore if no queue)
        if not self._queue:
            return
        self._is_playing = state
        self._sync_play_icon()


def create_ultra_widget(plugin: Any):  # factory entry
    return UltraRoot(plugin)

    # -------------------- queue API (internal) --------------------

    # NOTE: The queue methods are appended after factory for organizational clarity;
    # some linters may prefer them inside the class definition region above.


__all__ = ["UltraRoot", "create_ultra_widget"]
