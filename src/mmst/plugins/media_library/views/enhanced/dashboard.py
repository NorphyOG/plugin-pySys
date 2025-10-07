from __future__ import annotations
"""Composed enhanced dashboard combining hero + carousels.
Activated only when environment variable MMST_MEDIA_ENHANCED_DASHBOARD=1.
"""
import os
from typing import Any, List, Callable, Dict, Tuple, Optional

try:  # pragma: no cover
    from PySide6.QtWidgets import QWidget, QVBoxLayout
except Exception:  # pragma: no cover
    QWidget = object  # type: ignore

from .carousel import MediaCarousel  # type: ignore
from .hero import HeroWidget  # type: ignore
from .sidebar import Sidebar  # type: ignore
from .settings_panel import SettingsPanel  # type: ignore

class EnhancedDashboard(QWidget):  # type: ignore[misc]
    """Composite dashboard hosting hero + a dynamic set of carousels.

    Shelves (carousels) are defined by tuples: (shelf_id, title, provider_callable).
    This enables persisted ordering & future enable/disable without code edits.
    """

    def __init__(
        self,
        shelf_definitions: List[Tuple[str, str, Callable[[], List[Any]]]],
        *,
        hero_provider: Optional[Callable[[], List[Any]]] = None,
        plugin: Optional[Any] = None,
    ) -> None:
        super().__init__()
        self._shelf_defs: List[Tuple[str, str, Callable[[], List[Any]]]] = list(shelf_definitions)
        self._shelves: Dict[str, MediaCarousel] = {}
        self._plugin = plugin
        try:
            from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QHBoxLayout
            outer = QHBoxLayout(self)
            # Sidebar
            self.sidebar = Sidebar(self._sidebar_data_provider)
            try:
                self.sidebar.on_select(self._on_sidebar_select)  # type: ignore
            except Exception:
                pass
            outer.addWidget(self.sidebar, 0)  # type: ignore
            # Main content stack
            main_col = QVBoxLayout()
            # Compact header (status + actions in one row)
            header = QHBoxLayout()
            self._stats_label = QLabel("📁 Lädt…")  # type: ignore
            self._stats_label.setStyleSheet("color:#bbb;font-size:11px")  # type: ignore
            header.addWidget(self._stats_label)  # type: ignore
            sep1 = QLabel("·")  # type: ignore
            sep1.setStyleSheet("color:#555;padding:0 4px;font-size:11px")  # type: ignore
            header.addWidget(sep1)  # type: ignore
            self._watcher_label = QLabel("👁 Initialisiere…")  # type: ignore
            self._watcher_label.setStyleSheet("color:#bbb;font-size:11px")  # type: ignore
            header.addWidget(self._watcher_label)  # type: ignore
            sep2 = QLabel("·")  # type: ignore
            sep2.setStyleSheet("color:#555;padding:0 4px;font-size:11px")  # type: ignore
            header.addWidget(sep2)  # type: ignore
            self._now_playing_label = QLabel("")  # type: ignore
            self._now_playing_label.setStyleSheet("color:#bbb;font-size:11px")  # type: ignore
            header.addWidget(self._now_playing_label)  # type: ignore
            sep3 = QLabel("·")  # type: ignore
            sep3.setStyleSheet("color:#555;padding:0 4px;font-size:11px")  # type: ignore
            header.addWidget(sep3)  # type: ignore
            # Scan progress cluster (label + bar)
            self._scan_label = QLabel("")  # type: ignore
            self._scan_label.setStyleSheet("color:#bbb;font-size:11px")  # type: ignore
            header.addWidget(self._scan_label)  # type: ignore
            try:
                from PySide6.QtWidgets import QProgressBar  # type: ignore
                self._scan_bar = QProgressBar()  # type: ignore
                self._scan_bar.setMaximumHeight(10)  # type: ignore[attr-defined]
                self._scan_bar.setMaximum(100)  # percent based
                self._scan_bar.setValue(0)  # type: ignore[attr-defined]
                self._scan_bar.setTextVisible(False)  # type: ignore[attr-defined]
                self._scan_bar.setStyleSheet("QProgressBar{background:#222;border:1px solid #333;border-radius:3px;}QProgressBar::chunk{background:#4b6;}" )  # type: ignore
                self._scan_bar.setVisible(False)  # hidden until scan starts
                header.addWidget(self._scan_bar)  # type: ignore
            except Exception:
                self._scan_bar = None  # type: ignore
            header.addStretch(1)  # type: ignore
            # Actions
            try:
                from PySide6.QtWidgets import QPushButton
                def mk(btn: QPushButton):  # type: ignore
                    btn.setStyleSheet("QPushButton{background:#2b2b2b;border:1px solid #3d3d3d;padding:2px 6px;font-size:11px;border-radius:3px;}QPushButton:hover{border-color:#666}")  # type: ignore
                    return btn
                self.btn_add_source = mk(QPushButton("✚ Quelle"))  # type: ignore
                self.btn_rescan = mk(QPushButton("↻ Rescan"))  # type: ignore
                self.btn_toggle_watcher = mk(QPushButton("👁 Start"))  # type: ignore
                self.btn_stats = mk(QPushButton("📊 Statistik"))  # type: ignore
                self.btn_add_source.setToolTip("Medienquelle hinzufügen")  # type: ignore
                self.btn_rescan.setToolTip("Alle Quellen erneut scannen")  # type: ignore
                self.btn_toggle_watcher.setToolTip("Dateisystem-Überwachung starten/stoppen")  # type: ignore
                self.btn_stats.setToolTip("Statistik aktualisieren")  # type: ignore
                for b in (self.btn_add_source, self.btn_rescan, self.btn_toggle_watcher, self.btn_stats):
                    header.addWidget(b)  # type: ignore
                # Wire lazily
                try:
                    if plugin and getattr(plugin, '_widget', None):
                        if hasattr(plugin._widget, '_on_add_source'):
                            self.btn_add_source.clicked.connect(plugin._widget._on_add_source)  # type: ignore
                        if hasattr(plugin._widget, '_run_full_scan'):
                            self.btn_rescan.clicked.connect(plugin._widget._run_full_scan)  # type: ignore
                        if hasattr(plugin, '_toggle_watcher'):
                            self.btn_toggle_watcher.clicked.connect(plugin._toggle_watcher)  # type: ignore
                        if hasattr(plugin._widget, '_refresh_statistics'):
                            self.btn_stats.clicked.connect(plugin._widget._refresh_statistics)  # type: ignore
                except Exception:
                    pass
            except Exception:
                pass
            # Quick filter chips row (Audio / Video / Bilder / Alle)
            try:
                from PySide6.QtWidgets import QPushButton
                chip_row = QHBoxLayout()
                kinds = [
                    ("Alle", None),
                    ("Audio", "audio"),
                    ("Video", "video"),
                    ("Bilder", "image"),
                ]
                self._filter_buttons = []  # type: ignore
                for label, key in kinds:
                    btn = QPushButton(label)
                    btn.setCheckable(True)
                    btn.setStyleSheet("QPushButton{background:#2b2b2b;border:1px solid #333;padding:2px 8px;font-size:10px;border-radius:10px;}QPushButton:checked{background:#446;}")
                    if key is None:
                        btn.setChecked(True)
                    def make_cb(k):  # closure
                        def _cb():
                            try:
                                # uncheck others
                                for b in self._filter_buttons:  # type: ignore
                                    if b is not btn:
                                        b.setChecked(False)
                                if self._plugin and getattr(self._plugin, '_widget', None):
                                    w = self._plugin._widget
                                    if k is None:
                                        # Reset to All
                                        if hasattr(w, 'kind_combo'):
                                            idx = 0
                                            w.kind_combo.setCurrentIndex(idx)  # type: ignore
                                    else:
                                        # find matching kind in combo
                                        try:
                                            combo = w.kind_combo  # type: ignore
                                            for i in range(combo.count()):  # type: ignore[attr-defined]
                                                if combo.itemData(i) == k:  # type: ignore[attr-defined]
                                                    combo.setCurrentIndex(i)  # type: ignore[attr-defined]
                                                    break
                                        except Exception:
                                            pass
                                    if hasattr(w, '_apply_filters'):
                                        w._apply_filters()  # type: ignore
                                    if hasattr(w, '_rebuild_table'):
                                        w._rebuild_table()  # type: ignore
                            except Exception:
                                pass
                        return _cb
                    btn.clicked.connect(make_cb(key))  # type: ignore
                    chip_row.addWidget(btn)
                    self._filter_buttons.append(btn)  # type: ignore
                chip_row.addStretch(1)
                main_col.addLayout(header)  # status/actions
                main_col.addLayout(chip_row)  # chips
            except Exception:
                main_col.addLayout(header)  # fallback only header
            if hero_provider:
                self.hero = HeroWidget(hero_provider)
                main_col.addWidget(self.hero)  # type: ignore
            else:
                self.hero = None  # type: ignore
            # Build shelves in given order
            for shelf_id, title, provider in self._shelf_defs:
                carousel = MediaCarousel(title, provider)
                self._shelves[shelf_id] = carousel
                main_col.addWidget(carousel)  # type: ignore
            outer.addLayout(main_col, 1)  # type: ignore
        except Exception:
            self.hero = None  # type: ignore
        # Placeholder guidance label (created lazily)
        self._empty_label = None  # type: ignore
        # If plugin config indicates hero hidden, hide it now
        try:
            if plugin and getattr(plugin, '_is_hero_hidden', None) and self.hero:
                if plugin._is_hero_hidden():  # type: ignore
                    self.hero.setVisible(False)  # type: ignore
        except Exception:
            pass

    def reorder_shelves(self, order: List[str]) -> None:
        """Rebuild the shelves layout according to new order.

        Unknown ids are ignored; missing ones keep their previous relative order.
        """
        try:
            # Only if we have Qt layout objects
            from PySide6.QtWidgets import QVBoxLayout
            # Determine new ordered definitions
            existing = {sid: (sid, title, prov) for sid, title, prov in self._shelf_defs}
            new_defs: List[Tuple[str, str, Callable[[], List[Any]]]] = []
            seen = set()
            for sid in order:
                if sid in existing and sid not in seen:
                    new_defs.append(existing[sid])
                    seen.add(sid)
            # Append any shelves not explicitly listed to preserve them
            for sid, tup in existing.items():
                if sid not in seen:
                    new_defs.append(tup)
            if new_defs == self._shelf_defs:
                return  # nothing to do
            self._shelf_defs = new_defs
            # Remove old carousel widgets from layout
            # Assume parent layout structure: sidebar + main_col (VBox) where shelves live under hero
            # Re-create carousels dictionary & add widgets at end of layout
            # Simplest approach: destroy & rebuild carousels (cheap; lightweight labels only now)
            for sid, widget in list(self._shelves.items()):
                try:
                    widget.setParent(None)  # type: ignore
                except Exception:
                    pass
            self._shelves.clear()
            # Find main_col: it's second item in outer layout
            outer_layout = getattr(self, 'layout', lambda: None)()
            # We stored hero as first shelf (if exists) followed by carousels; easiest is to append anew
            if outer_layout:
                # Outer is QHBoxLayout; main_col is last added layout
                try:
                    main_col = outer_layout.itemAt(1).layout()  # type: ignore
                except Exception:
                    main_col = None
                if main_col:
                    for sid, title, provider in self._shelf_defs:
                        carousel = MediaCarousel(title, provider)
                        self._shelves[sid] = carousel
                        main_col.addWidget(carousel)  # type: ignore
        except Exception:
            pass

    def refresh(self) -> None:
        try:
            if self.hero:
                self.hero.refresh()  # type: ignore
            for shelf in self._shelves.values():
                shelf.refresh()  # type: ignore
            if getattr(self, 'sidebar', None):
                self.sidebar.refresh()  # type: ignore
            self._update_empty_state()
        except Exception:
            pass

    # ----------- Status bar updates -----------
    def update_quick_stats(self, counts: Dict[str, int]) -> None:
        try:
            total = counts.get("total", 0)
            parts = [f"📁 {total} Dateien"]
            label_map = {"audio": "Audio", "video": "Video", "image": "Bilder", "other": "Andere"}
            for k in ("audio", "video", "image", "other"):
                if k in counts:
                    parts.append(f"{label_map.get(k, k.title())} {counts[k]}")
            if hasattr(self, "_stats_label"):
                self._stats_label.setText(" | ".join(parts))  # type: ignore
        except Exception:
            pass

    def update_watcher_state(self, active: bool, watched: int) -> None:
        try:
            if hasattr(self, "_watcher_label"):
                txt = f"👁 {'Aktiv' if active else 'Inaktiv'}"
                if watched:
                    txt += f" ({watched})"
                self._watcher_label.setText(txt)  # type: ignore
        except Exception:
            pass

    def update_now_playing(self, title: str) -> None:
        try:
            if hasattr(self, "_now_playing_label"):
                self._now_playing_label.setText(title and f"▶ {title}" or "")  # type: ignore
            self._update_empty_state()
        except Exception:
            pass

    def update_scan_progress(self, current: int | None = None, total: int | None = None, *, done: bool = False) -> None:
        try:
            if not hasattr(self, '_scan_label'):
                return
            # Update textual part
            if done:
                self._scan_label.setText("")  # type: ignore
                if getattr(self, '_scan_bar', None):
                    try:
                        self._scan_bar.setVisible(False)  # type: ignore[attr-defined]
                        self._scan_bar.setValue(0)  # type: ignore[attr-defined]
                    except Exception:
                        pass
                return
            if current is not None and total:
                self._scan_label.setText(f"🔄 Scan {current}/{total}")  # type: ignore
                if getattr(self, '_scan_bar', None) and total > 0:
                    try:
                        pct = int((current / max(total, 1)) * 100)
                        self._scan_bar.setVisible(True)  # type: ignore[attr-defined]
                        self._scan_bar.setValue(min(max(pct,0),100))  # type: ignore[attr-defined]
                    except Exception:
                        pass
            elif current is not None:
                self._scan_label.setText(f"🔄 Scan {current}")  # type: ignore
        except Exception:
            pass

    # ----------- Empty placeholder logic -----------
    def _update_empty_state(self) -> None:
        try:
            visible_shelf = any(getattr(s, 'isVisible', lambda: False)() for s in self._shelves.values())
            hero_visible = bool(self.hero and getattr(self.hero, 'isVisible', lambda: False)())
            need_placeholder = not hero_visible and not visible_shelf
            if need_placeholder and not self._empty_label:
                from PySide6.QtWidgets import QLabel, QHBoxLayout, QWidget, QPushButton
                container = QWidget()
                lay = QHBoxLayout(container)
                lay.setContentsMargins(0,40,0,40)
                lbl = QLabel("Keine Inhalte – füge eine Quelle hinzu ✚")
                lbl.setStyleSheet("color:#666;font-size:14px")
                lay.addWidget(lbl)
                # Hero restore button
                btn = QPushButton("Hero anzeigen")
                btn.setStyleSheet("QPushButton{background:#2b2b2b;border:1px solid #444;padding:4px 10px;border-radius:4px;}QPushButton:hover{border-color:#666}")
                def restore():  # closure
                    try:
                        if self._plugin and hasattr(self._plugin, '_set_hero_hidden'):
                            self._plugin._set_hero_hidden(False)  # type: ignore
                        if self.hero:
                            self.hero.setVisible(True)  # type: ignore
                        # remove placeholder
                        if self._empty_label:
                            self._empty_label.setParent(None)  # type: ignore
                            self._empty_label = None  # type: ignore
                    except Exception:
                        pass
                btn.clicked.connect(restore)  # type: ignore
                lay.addWidget(btn)
                lay.addStretch(1)
                self._empty_label = container  # type: ignore
                # Insert near top after header + chips: layout index 2 (0 header,1 chips)
                try:
                    outer_layout = getattr(self, 'layout', lambda: None)()
                    if outer_layout:
                        main_col = outer_layout.itemAt(1).layout()  # type: ignore
                        if main_col:
                            main_col.addWidget(self._empty_label)  # type: ignore
                except Exception:
                    pass
            if not need_placeholder and self._empty_label:
                try:
                    self._empty_label.setParent(None)  # type: ignore
                except Exception:
                    pass
                self._empty_label = None  # type: ignore
        except Exception:
            pass

    # ---------------- Sidebar data provider -----------------
    def _sidebar_data_provider(self, section: str):
        plugin = self._plugin
        if not plugin:
            return []
        try:
            index = plugin.get_library_index()
        except Exception:
            return []
        try:
            if section == "actions":
                return [
                    {"name": "Quelle hinzufügen", "action": "add_source"},
                    {"name": "Alle Quellen scannen", "action": "rescan"},
                    {"name": "Statistik aktualisieren", "action": "stats_refresh"},
                    {"name": "Ansicht umschalten", "action": "toggle_view"},
                    {"name": "Einstellungen", "action": "open_settings"},
                ]
            if section == "sources":
                # list_sources returns tuples (id, path)
                return [{"id": sid, "name": path} for sid, path in index.list_sources()]  # type: ignore[attr-defined]
            if section == "playlists":
                return [
                    {"id": pid, "name": name, "count": count}
                    for pid, name, count in index.list_playlists()
                ]  # type: ignore[attr-defined]
            if section == "smart":
                # Attempt to load smart playlists from plugin data dir
                from pathlib import Path
                from ..smart_playlists import load_smart_playlists  # type: ignore
                data_dir = plugin.services.data_dir / "media_library"
                sp_path = data_dir / "smart_playlists.json"
                plist = load_smart_playlists(sp_path)
                return [{"name": sp.name, "limit": sp.limit} for sp in plist]
            if section == "tags":
                # Aggregate distinct tags via direct query (simple + lightweight)
                conn = index._conn  # protected access acceptable internally
                cur = conn.cursor()
                cur.execute("SELECT tags FROM files WHERE tags IS NOT NULL")
                seen = set()
                import json
                for row in cur.fetchall():
                    raw = row[0]
                    if not raw:
                        continue
                    try:
                        parsed = json.loads(str(raw))
                        if isinstance(parsed, list):
                            for t in parsed:
                                ts = str(t).strip()
                                if ts:
                                    seen.add(ts)
                    except Exception:
                        # Fallback: comma-split
                        for part in str(raw).split(","):
                            ts = part.strip()
                            if ts:
                                seen.add(ts)
                return [{"name": tag} for tag in sorted(seen, key=str.lower)]
        except Exception:
            return []
        return []

    # ---------------- Sidebar selection handling -----------------
    def _on_sidebar_select(self, section: str, payload: Dict[str, Any]) -> None:
        if section != "actions":
            return
        action = payload.get("action")
        plugin = self._plugin
        if not plugin or not action:
            return
        try:
            if action == "add_source" and hasattr(plugin._widget, "_on_add_source"):
                plugin._widget._on_add_source()  # type: ignore[attr-defined]
            elif action == "rescan" and hasattr(plugin._widget, "_run_full_scan"):
                plugin._widget._run_full_scan()  # type: ignore[attr-defined]
            elif action == "stats_refresh" and hasattr(plugin._widget, "_refresh_statistics"):
                plugin._widget._refresh_statistics()  # type: ignore[attr-defined]
            elif action == "toggle_view":
                # Toggle persistent view mode
                current = getattr(plugin, "_view_mode", "enhanced")
                new_mode = "classic" if current == "enhanced" else "enhanced"
                plugin.set_view_mode(new_mode)
                # Force recreation if needed
                try:
                    if plugin._widget:
                        # User must restart / or we rebuild? For now send notification
                        plugin.services.send_notification(f"View Mode umgestellt auf {new_mode} (Neuladen ggf. nötig)", source=plugin.manifest.identifier)
                except Exception:
                    pass
            elif action == "open_settings":
                try:
                    panel = SettingsPanel(plugin)
                    panel.setWindowTitle("Media Library Einstellungen")  # type: ignore[attr-defined]
                    panel.resize(320, 420)  # type: ignore[attr-defined]
                    panel.show()  # type: ignore[attr-defined]
                    self._settings_panel = panel  # keep reference
                except Exception:
                    pass
        except Exception:
            pass


def enhanced_dashboard_enabled(plugin: Any | None = None) -> bool:  # type: ignore[name-defined]
    """Determine if enhanced dashboard should be enabled.

    Priority:
      1. Explicit env var MMST_MEDIA_ENHANCED_DASHBOARD=1 forces enable.
      2. MMST_MEDIA_ENHANCED_DASHBOARD=0 forces disable.
      3. Plugin config key view_mode == 'enhanced' enables.
      4. Default: enabled (for visibility of new features).
    """
    env = os.environ.get("MMST_MEDIA_ENHANCED_DASHBOARD")
    if env == "1":
        return True
    if env == "0":
        return False
    # Try plugin config
    try:
        if plugin is not None:
            vm = getattr(plugin, "_view_mode", None)
            if vm == "enhanced":
                return True
            if vm == "classic":
                return False
    except Exception:
        pass
    return True  # default enable to surface improvements

__all__ = ["EnhancedDashboard", "enhanced_dashboard_enabled"]
