from __future__ import annotations
"""Lightweight settings panel for Media Library Enhanced UI.
Provides:
- View mode toggle (classic/enhanced)
- Shelf order reordering (simple up/down buttons for now)
Persists via plugin.set_view_mode / plugin.set_shelf_order.
"""
from typing import Any, List

try:  # pragma: no cover
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QHBoxLayout
    )
except Exception:  # pragma: no cover
    QWidget = object  # type: ignore
    QVBoxLayout = QLabel = QPushButton = QListWidget = QListWidgetItem = QHBoxLayout = object  # type: ignore

class SettingsPanel(QWidget):  # type: ignore[misc]
    def __init__(self, plugin: Any):
        super().__init__()
        self._plugin = plugin
        try:
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("Einstellungen"))  # type: ignore

            # View mode toggle
            self._mode_btn = QPushButton(self._mode_label())  # type: ignore
            self._mode_btn.clicked.connect(self._toggle_mode)  # type: ignore[attr-defined]
            layout.addWidget(self._mode_btn)  # type: ignore

            # Hero & Schnellfilter toggles
            try:
                from PySide6.QtWidgets import QCheckBox
                cfg = plugin.services.get_plugin_config(plugin.manifest.identifier) or {}
                hero_hidden = bool(cfg.get('hero_hidden'))
                show_filter = cfg.get('show_filter_chips', True) is not False
                self._cb_hero = QCheckBox("Hero anzeigen")  # type: ignore
                self._cb_hero.setChecked(not hero_hidden)  # type: ignore
                self._cb_filter = QCheckBox("Schnellfilter anzeigen")  # type: ignore
                self._cb_filter.setChecked(show_filter)  # type: ignore
                layout.addWidget(self._cb_hero)  # type: ignore
                layout.addWidget(self._cb_filter)  # type: ignore
                def on_hero(state):  # type: ignore
                    try:
                        plugin._set_hero_hidden(not self._cb_hero.isChecked())  # type: ignore
                        if getattr(plugin, '_enhanced_dashboard', None) and plugin._enhanced_dashboard.hero:  # type: ignore
                            plugin._enhanced_dashboard.hero.setVisible(self._cb_hero.isChecked())  # type: ignore
                            if not self._cb_hero.isChecked():
                                plugin._enhanced_dashboard._update_empty_state()  # type: ignore
                    except Exception:
                        pass
                def on_filter(state):  # type: ignore
                    try:
                        cfg = plugin.services.get_plugin_config(plugin.manifest.identifier) or {}
                        cfg['show_filter_chips'] = self._cb_filter.isChecked()
                        plugin.services.save_plugin_config(plugin.manifest.identifier, cfg)
                        dash = getattr(plugin, '_enhanced_dashboard', None)
                        if dash and hasattr(dash, '_filter_buttons'):
                            # hide row by setting each button parent invisible (row layout not easily stored)
                            for b in dash._filter_buttons:  # type: ignore
                                b.setVisible(self._cb_filter.isChecked())  # type: ignore
                    except Exception:
                        pass
                self._cb_hero.stateChanged.connect(on_hero)  # type: ignore
                self._cb_filter.stateChanged.connect(on_filter)  # type: ignore
            except Exception:
                pass

            # Shelf order list
            layout.addWidget(QLabel("Regal-Reihenfolge"))  # type: ignore
            self._shelf_list = QListWidget()  # type: ignore
            layout.addWidget(self._shelf_list)  # type: ignore
            self._populate_shelves()

            # Up/Down controls
            row = QHBoxLayout()
            up = QPushButton("▲")  # type: ignore
            dn = QPushButton("▼")  # type: ignore
            up.clicked.connect(lambda: self._move_selected(-1))  # type: ignore[attr-defined]
            dn.clicked.connect(lambda: self._move_selected(1))  # type: ignore[attr-defined]
            row.addWidget(up)  # type: ignore
            row.addWidget(dn)  # type: ignore
            layout.addLayout(row)  # type: ignore
        except Exception:
            pass

    # ---------------- internal helpers -----------------
    def _mode_label(self) -> str:
        mode = getattr(self._plugin, "_view_mode", "enhanced")
        return f"Ansicht umschalten (aktuell: {mode})"

    def _toggle_mode(self) -> None:
        try:
            current = getattr(self._plugin, "_view_mode", "enhanced")
            new_mode = "classic" if current == "enhanced" else "enhanced"
            self._plugin.set_view_mode(new_mode)
            if hasattr(self._mode_btn, 'setText'):
                self._mode_btn.setText(self._mode_label())  # type: ignore
        except Exception:
            pass

    def _populate_shelves(self) -> None:
        try:
            order: List[str] = list(getattr(self._plugin, "_shelf_order", ["recent", "top_rated"]))
            self._shelf_list.clear()  # type: ignore[attr-defined]
            title_map = {"recent": "Zuletzt hinzugefügt", "top_rated": "Top bewertet"}
            for sid in order:
                it = QListWidgetItem(title_map.get(sid, sid))  # type: ignore
                it.setData(32, sid)  # Qt.UserRole
                self._shelf_list.addItem(it)  # type: ignore
        except Exception:
            pass

    def _move_selected(self, delta: int) -> None:
        try:
            items = self._shelf_list.selectedItems()  # type: ignore[attr-defined]
            if not items:
                return
            item = items[0]
            row = self._shelf_list.row(item)  # type: ignore[attr-defined]
            new_row = row + delta
            if new_row < 0 or new_row >= self._shelf_list.count():  # type: ignore[attr-defined]
                return
            it = self._shelf_list.takeItem(row)  # type: ignore[attr-defined]
            self._shelf_list.insertItem(new_row, it)  # type: ignore[attr-defined]
            self._shelf_list.setCurrentItem(it)  # type: ignore[attr-defined]
            # Persist new order
            new_order: List[str] = []
            for i in range(self._shelf_list.count()):  # type: ignore[attr-defined]
                data = self._shelf_list.item(i).data(32)  # type: ignore[attr-defined]
                if data:
                    new_order.append(str(data))
            self._plugin.set_shelf_order(new_order)
        except Exception:
            pass

__all__ = ["SettingsPanel"]
