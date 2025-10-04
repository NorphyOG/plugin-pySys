from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtCore import Qt
else:  # pragma: no cover - provide runtime fallback when PySide6 is absent
    try:
        from PySide6.QtCore import Qt  # type: ignore[import-not-found]
    except Exception:  # pragma: no cover
        class _QtFallback:
            AlignLeft = AlignVCenter = AlignCenter = 0
            UserRole = 32
            DisplayRole = 0

        Qt = _QtFallback()  # type: ignore[assignment]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .plugin_base import PluginState
from .plugin_manager import PluginManager, PluginRecord
from .services import CoreServices, Notification


@dataclass
class PluginView:
    widget: QWidget
    is_initialized: bool = False


class PluginListItem(QListWidgetItem):
    def __init__(self, record: PluginRecord) -> None:
        name = record.manifest.name
        super().__init__(name)
        self.identifier = record.manifest.identifier
        self.setData(Qt.UserRole, self.identifier)  # type: ignore[attr-defined]
        self.refresh(record)

    def refresh(self, record: PluginRecord) -> None:
        status = record.state.value
        if record.state is PluginState.STARTED:
            color = "#2e8b57"  # sea green
        elif record.state is PluginState.FAILED:
            color = "#b22222"  # firebrick
        else:
            color = "#444444"
        subtitle = record.manifest.description
        text = f"{record.manifest.name}\n<span style='color:{color}'>Status: {status}</span>"
        if record.error:
            text += f"<br/><span style='color:{color}'>{record.error}</span>"
        self.setData(Qt.DisplayRole, record.manifest.name)  # type: ignore[attr-defined]
        self.setToolTip(f"{subtitle}\nStatus: {status}")
        self.setData(Qt.UserRole + 1, text)  # type: ignore[attr-defined]


class DashboardWindow(QMainWindow):
    def __init__(self, services: CoreServices, manager: PluginManager) -> None:
        super().__init__()
        self._services = services
        self._manager = manager
        self._views: Dict[str, PluginView] = {}
        self._app_settings = self._services.get_app_config()

        self.setWindowTitle("MMST Dashboard")
        self.resize(1200, 760)

        container = QWidget()
        root_layout = QHBoxLayout(container)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        # Sidebar with plugins
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(6)

        title = QLabel("Plugins")
        title.setObjectName("SidebarTitle")
        sidebar_layout.addWidget(title)

        self.plugin_list = QListWidget()
        try:
            selection_mode = QListWidget.SelectionMode.SingleSelection
        except AttributeError:  # pragma: no cover - fallback for bindings without enum
            selection_mode = QListWidget.SingleSelection  # type: ignore[attr-defined]
        self.plugin_list.setSelectionMode(selection_mode)
        self.plugin_list.currentItemChanged.connect(self._on_plugin_selected)
        sidebar_layout.addWidget(self.plugin_list, stretch=1)

        actions_layout = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self._start_selected)
        actions_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self._stop_selected)
        actions_layout.addWidget(self.stop_button)

        self.configure_button = QPushButton("Konfigurieren")
        self.configure_button.clicked.connect(self._configure_selected)
        actions_layout.addWidget(self.configure_button)

        sidebar_layout.addLayout(actions_layout)
        
        # Progress dialog button
        progress_button_layout = QHBoxLayout()
        self.progress_button = QPushButton("📊 Fortschritt anzeigen")
        self.progress_button.clicked.connect(self._toggle_progress_dialog)
        progress_button_layout.addWidget(self.progress_button)
        sidebar_layout.addLayout(progress_button_layout)
        
        # Settings button (for debug console)
        settings_button = QPushButton("⚙️ Einstellungen")
        settings_button.clicked.connect(self._show_settings)
        sidebar_layout.addWidget(settings_button)

        self.status_label = QLabel("Bereit")
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # type: ignore[attr-defined]
        sidebar_layout.addWidget(self.status_label)
        self._set_status("Bereit")

        root_layout.addWidget(sidebar, stretch=0)

        # Central stacked view
        self.view_stack = QStackedWidget()
        placeholder = QLabel("Plugin auswählen, um das Interface zu laden.")
        placeholder.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        self.view_stack.addWidget(placeholder)
        root_layout.addWidget(self.view_stack, stretch=1)

        self.setCentralWidget(container)

        self._services.notifications.subscribe(self._on_notification)
        
        # Initialize progress dialog
        from .progress import ProgressDialog
        self._progress_dialog = ProgressDialog(self)
        self._services.progress.set_dialog(self._progress_dialog)
        
        # Initialize debug console and attach to root logger immediately
        from .debug_console import DebugConsole
        import logging
        self._debug_console = DebugConsole()
        self._debug_console.attach_to_logger(logging.getLogger())  # Attach to root logger
        self._settings_dialog: Optional[QWidget] = None

        self._restore_window_settings()

        self._populate_plugins()
        restored = self._restore_dashboard_state()
        if not restored and self.plugin_list.count() > 0:
            self.plugin_list.setCurrentRow(0)
            self._auto_start_selected()

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _populate_plugins(self) -> None:
        self.plugin_list.clear()
        records = self._manager.discover()
        for record in records.values():
            item = PluginListItem(record)
            self.plugin_list.addItem(item)

    def _current_identifier(self) -> Optional[str]:
        current = self.plugin_list.currentItem()
        if current:
            return current.data(Qt.UserRole)  # type: ignore[attr-defined]
        return None

    def _current_record(self) -> Optional[PluginRecord]:
        identifier = self._current_identifier()
        if not identifier:
            return None
        return self._manager.get(identifier)

    def _ensure_view(self, identifier: str) -> QWidget:
        view = self._views.get(identifier)
        if view and view.widget:
            return view.widget

        record = self._manager.get(identifier)
        if not record or record.instance is None:
            placeholder = QLabel("Plugin konnte nicht initialisiert werden.")
            placeholder.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
            return placeholder

        widget = record.instance.create_view()
        plugin_view = PluginView(widget=widget)
        self._views[identifier] = plugin_view
        self.view_stack.addWidget(widget)
        return widget

    def _update_buttons(self, record: Optional[PluginRecord]) -> None:
        if not record:
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.configure_button.setEnabled(False)
            return
        self.start_button.setEnabled(record.state != PluginState.STARTED)
        self.stop_button.setEnabled(record.state == PluginState.STARTED)
        self.configure_button.setEnabled(record.instance is not None)

    def _restore_window_settings(self) -> None:
        size = self._app_settings.get("window_size", None)
        if isinstance(size, (list, tuple)) and len(size) == 2:
            try:
                width, height = int(size[0]), int(size[1])
            except (TypeError, ValueError):
                width = height = 0
            if width > 0 and height > 0:
                self.resize(width, height)

        position = self._app_settings.get("window_pos", None)
        if isinstance(position, (list, tuple)) and len(position) == 2:
            try:
                x, y = int(position[0]), int(position[1])
            except (TypeError, ValueError):
                x = y = None
            else:
                if x is not None and y is not None:
                    self.move(x, y)

        if bool(self._app_settings.get("window_maximized", False)):
            self.showMaximized()

    def _update_app_settings(self, **kwargs: Any) -> None:
        payload: Dict[str, Any] = {}
        for key, value in kwargs.items():
            current = self._app_settings.get(key, None)
            if current != value:
                payload[key] = value
        if payload:
            self._app_settings.update(payload)

    def _restore_dashboard_state(self) -> bool:
        restored = False
        started_plugins = self._app_settings.get("started_plugins", [])
        if isinstance(started_plugins, list):
            for identifier in started_plugins:
                if not isinstance(identifier, str):
                    continue
                record = self._manager.get(identifier)
                if not record or record.state == PluginState.STARTED:
                    continue
                state = self._manager.start(identifier)
                self._refresh_record(identifier)
                if state == PluginState.STARTED:
                    restored = True

        selected = self._app_settings.get("selected_plugin")
        if isinstance(selected, str):
            if self._select_plugin(selected):
                restored = True

        self._persist_started_plugins()
        return restored

    def _select_plugin(self, identifier: str) -> bool:
        for index in range(self.plugin_list.count()):
            item = self.plugin_list.item(index)
            if item and item.data(Qt.UserRole) == identifier:  # type: ignore[attr-defined]
                self.plugin_list.setCurrentRow(index)
                return True
        return False

    def _persist_started_plugins(self) -> None:
        started = [
            record.manifest.identifier
            for record in self._manager.iter_plugins()
            if record.state == PluginState.STARTED
        ]
        self._update_app_settings(started_plugins=started)

    def _remember_selection(self) -> None:
        self._update_app_settings(selected_plugin=self._current_identifier())

    def _save_dashboard_state(self) -> None:
        rect = self.normalGeometry() if self.isMaximized() else self.geometry()
        if rect.width() <= 0 or rect.height() <= 0:
            size_obj = self.size()
            pos_obj = self.pos()
        else:
            size_obj = rect.size()
            pos_obj = rect.topLeft()

        state = {
            "window_size": [int(size_obj.width()), int(size_obj.height())],
            "window_pos": [int(pos_obj.x()), int(pos_obj.y())],
            "window_maximized": self.isMaximized(),
            "selected_plugin": self._current_identifier(),
            "started_plugins": [
                record.manifest.identifier
                for record in self._manager.iter_plugins()
                if record.state == PluginState.STARTED
            ],
        }
        self._update_app_settings(**state)

    def _on_plugin_selected(self, current: Optional[QListWidgetItem]) -> None:
        record = self._current_record()
        self._update_buttons(record)
        if record and record.state == PluginState.STARTED:
            widget = self._ensure_view(record.manifest.identifier)
            self.view_stack.setCurrentWidget(widget)
        else:
            self.view_stack.setCurrentIndex(0)
        self._remember_selection()

    def _start_selected(self) -> None:
        record = self._current_record()
        if not record:
            return
        state = self._manager.start(record.manifest.identifier)
        self._refresh_record(record.manifest.identifier)
        if state == PluginState.STARTED:
            widget = self._ensure_view(record.manifest.identifier)
            self.view_stack.setCurrentWidget(widget)
            self._set_status(f"{record.manifest.name} gestartet", level="success")
        else:
            self.view_stack.setCurrentIndex(0)
            self._show_error(record)
        self._update_buttons(self._current_record())
        self._persist_started_plugins()

    def _auto_start_selected(self) -> None:
        record = self._current_record()
        if not record or record.state == PluginState.STARTED:
            return
        state = self._manager.start(record.manifest.identifier)
        self._refresh_record(record.manifest.identifier)
        if state == PluginState.STARTED:
            widget = self._ensure_view(record.manifest.identifier)
            self.view_stack.setCurrentWidget(widget)
            self._set_status(
                f"{record.manifest.name} automatisch gestartet",
                level="success",
            )
        else:
            self.view_stack.setCurrentIndex(0)
            self._show_error(record)
        self._update_buttons(self._current_record())
        self._persist_started_plugins()

    def _stop_selected(self) -> None:
        record = self._current_record()
        if not record:
            return
        self._manager.stop(record.manifest.identifier)
        self._refresh_record(record.manifest.identifier)
        self.view_stack.setCurrentIndex(0)
        self._set_status(f"{record.manifest.name} gestoppt")
        self._update_buttons(self._current_record())
        self._persist_started_plugins()

    def _configure_selected(self) -> None:
        record = self._current_record()
        if not record or record.instance is None:
            QMessageBox.warning(
                self,
                "Plugin nicht geladen",
                "Das Plugin muss erst gestartet werden, bevor es konfiguriert werden kann.",
            )
            return
        try:
            record.instance.configure(self)
        except NotImplementedError:
            QMessageBox.information(
                self,
                "Keine Einstellungen",
                "Dieses Plugin stellt keine Konfigurationsoberfläche bereit.",
            )
        except Exception as exc:  # pragma: no cover - UI feedback only
            self._services.logger.exception("Config dialog failed for plugin %s", record.manifest.identifier)
            QMessageBox.critical(self, "Fehler", f"Konfigurationsfehler: {exc}")
    
    def _toggle_progress_dialog(self) -> None:
        """Show or hide progress dialog."""
        if self._progress_dialog.isVisible():
            self._progress_dialog.hide()
            self.progress_button.setText("📊 Fortschritt anzeigen")
        else:
            self._progress_dialog.show()
            self._progress_dialog.raise_()
            self._progress_dialog.activateWindow()
            self.progress_button.setText("📊 Fortschritt ausblenden")
    
    def _show_settings(self) -> None:
        """Show settings dialog with debug console."""
        if self._settings_dialog and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        
        # Create settings dialog
        from PySide6.QtWidgets import QDialog, QTabWidget
        
        dialog = QDialog(self)
        dialog.setWindowTitle("MMST Einstellungen")
        dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(dialog)
        
        tabs = QTabWidget()
        
        # Debug Console tab (already initialized and attached in __init__)
        tabs.addTab(self._debug_console, "🐛 Debug-Console")
        
        # Future: Add more settings tabs here
        # tabs.addTab(general_settings, "⚙️ Allgemein")
        # tabs.addTab(appearance_settings, "🎨 Darstellung")
        
        layout.addWidget(tabs)
        
        # Close button
        from PySide6.QtWidgets import QDialogButtonBox
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(dialog.close)
        layout.addWidget(button_box)
        
        self._settings_dialog = dialog
        dialog.show()

    def _refresh_record(self, identifier: str) -> None:
        record = self._manager.get(identifier)
        if not record:
            return
        for index in range(self.plugin_list.count()):
            item = self.plugin_list.item(index)
            if item and item.data(Qt.UserRole) == identifier:  # type: ignore[attr-defined]
                if isinstance(item, PluginListItem):
                    item.refresh(record)
                break

    def _show_error(self, record: PluginRecord) -> None:
        if record.error:
            QMessageBox.critical(self, record.manifest.name, record.error)

    # ------------------------------------------------------------------
    # Qt events
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._save_dashboard_state()
        self._services.notifications.unsubscribe(self._on_notification)
        self._manager.shutdown()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Status & notifications
    # ------------------------------------------------------------------
    def _set_status(
        self,
        message: str,
        *,
        level: str = "info",
        source: Optional[str] = None,
    ) -> None:
        color_map = {
            "info": "#d0d0d0",
            "success": "#2e8b57",
            "warning": "#d19a00",
            "error": "#b22222",
        }
        color = color_map.get(level.lower(), color_map["info"])
        if source:
            message = f"[{source}] {message}"
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color};")

    def _on_notification(self, notification: Notification) -> None:
        self._set_status(
            notification.message,
            level=notification.level,
            source=notification.source,
        )


def main() -> int:
    app = QApplication(sys.argv)
    services = CoreServices()
    manager = PluginManager(services=services)
    window = DashboardWindow(services=services, manager=manager)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
