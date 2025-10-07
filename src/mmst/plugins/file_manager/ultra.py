"""Ultra (Explorer-inspired) UI scaffold for the File Manager plugin.

This is an initial, non-functional visual skeleton implementing the 3-pane
layout described in the specification:

    ┌─────────────┬──────────────────────────┬─────────────────┐
    │   Sidebar   │   Main (breadcrumb+view) │  Details Panel  │
    └─────────────┴──────────────────────────┴─────────────────┘
    └──────────────────────── Bottom Status Bar ─────────────────┘

Focus of this first iteration:
 - Layout containers & placeholder widgets
 - View toggle (Grid / List / Details) switching stacked area
 - Breadcrumb bar with stub update mechanism
 - Search line edit (no fuzzy engine yet)
 - Status bar (selection count, free space placeholder, settings button)
 - Styling with dark theme constants (can be refined later)

Non-goals for this patch (future todos 18–23):
 - Real filesystem model & navigation
 - Dynamic drive / favorites population
 - Context menus & actions
 - Detail preview rendering (thumbnails, waveform etc.)
 - Metadata extraction
 - Live free space updates & disk health graphs
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize  # type: ignore[import-not-found]
from PySide6.QtGui import QIcon  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTreeWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


BG_PRIMARY = "#1e1f22"
BG_SECONDARY = "#2b2d31"
BG_TERTIARY = "#383a40"
ACCENT = "#5865f2"
ACCENT_HOVER = "#4752c4"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#b5bac1"
TEXT_MUTED = "#80848e"
BORDER = "#3f4147"


class _BreadcrumbBar(QWidget):
    """Simple breadcrumb bar with buttons for each path segment.

    Emits navigation via the provided callback. Real navigation & overflow
    handling (smart collapsing) will be implemented in a later iteration.
    """

    def __init__(self, navigate_cb, parent: Optional[QWidget] = None):  # type: ignore[override]
        super().__init__(parent)
        self._navigate_cb = navigate_cb
        self._current = Path.home()
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self.refresh()

    def set_path(self, path: Path) -> None:
        if path != self._current:
            self._current = path
            self.refresh()

    def refresh(self) -> None:
        # Clear old buttons
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        parts = list(self._current.parts)
        if not parts:
            parts = ['/']

        # Collapse: show first + ellipsis + last two if deep (>5)
        hidden: list[tuple[str, Path]] = []
        if len(parts) > 5:
            visible = [parts[0], '…', *parts[-2:]]
            hidden = [(seg, Path(*parts[:i+1])) for i, seg in enumerate(parts[1:-2], start=1)]
        else:
            visible = parts

        from PySide6.QtWidgets import QMenu  # type: ignore
        accumulated = Path(visible[0]) if visible else Path('/')
        for idx, seg in enumerate(visible):
            if seg == '…':
                btn = QPushButton('…')
                btn.setObjectName('BreadcrumbButton')
                try:
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)  # type: ignore[attr-defined]
                except Exception:
                    pass
                menu = QMenu(btn)
                for label, real_path in hidden:
                    act = menu.addAction(label or '/')
                    act.triggered.connect(lambda _=False, p=real_path: self._navigate_cb(p))
                btn.clicked.connect(menu.popup)
            else:
                btn = QPushButton(seg or '/')
                btn.setObjectName('BreadcrumbButton')
                path_copy = accumulated
                try:
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)  # type: ignore[attr-defined]
                except Exception:
                    pass
                btn.clicked.connect(lambda _=False, p=path_copy: self._navigate_cb(p))
            self._layout.addWidget(btn)
            if idx < len(visible) - 1:
                sep = QLabel('›')
                sep.setObjectName('BreadcrumbSep')
                self._layout.addWidget(sep)
            # Advance accumulated if not ellipsis
            if seg != '…' and idx + 1 < len(visible):
                # Map segment back to original index to append following part
                try:
                    original_index = parts.index(seg)
                    next_seg = parts[original_index + 1] if original_index + 1 < len(parts) else None
                    if next_seg:
                        accumulated = accumulated / next_seg
                except ValueError:
                    pass
        self._layout.addStretch(1)


class _PlaceholderView(QWidget):
    """Simple labeled placeholder for each content representation."""

    def __init__(self, label: str, parent: Optional[QWidget] = None):  # type: ignore[override]
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(1)
        lab = QLabel(label)
        lab.setObjectName("PlaceholderLabel")
        try:
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore[attr-defined]
        except Exception:
            pass
        lay.addWidget(lab)
        lay.addStretch(1)


class FileManagerUltraWidget(QWidget):
    """Three-pane ultra UI for file management.

    Public convenience methods (stable surface for future integration):
      - set_directory(path: Path)
      - update_selection(count: int, total_bytes: int)
      - refresh_free_space(path?: Path)
    """

    def __init__(self, plugin, parent: Optional[QWidget] = None):  # type: ignore[override]
        super().__init__(parent)
        self._plugin = plugin
        self._current_dir = Path.home()
        self._tool_mode = None  # type: Optional[str]

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Central 3-pane frame
        frame = QWidget()
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # Sidebar ---------------------------------------------------------
        self.sidebar = QTreeWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setHeaderHidden(True)
        self.sidebar.setFixedWidth(220)
        self._populate_sidebar_placeholders()
        self.sidebar.itemSelectionChanged.connect(self._on_sidebar_selection)
        frame_layout.addWidget(self.sidebar)

        # Main area (vertical): breadcrumb/tool bar + content stacked -------
        main_container = QWidget()
        main_v = QVBoxLayout(main_container)
        main_v.setContentsMargins(8, 8, 8, 8)
        main_v.setSpacing(8)

        # Toolbar (breadcrumb row + actions)
        toolbar = QWidget()
        toolbar_h = QHBoxLayout(toolbar)
        toolbar_h.setContentsMargins(0, 0, 0, 0)
        toolbar_h.setSpacing(8)

        self.breadcrumb = _BreadcrumbBar(self._on_breadcrumb_navigate)
        toolbar_h.addWidget(self.breadcrumb, stretch=1)

        self.view_grid_btn = QToolButton()
        self.view_grid_btn.setText("🔲")
        self.view_grid_btn.setCheckable(True)
        self.view_grid_btn.setChecked(True)
        self.view_grid_btn.clicked.connect(lambda: self._set_view_mode(0))
        toolbar_h.addWidget(self.view_grid_btn)

        self.view_list_btn = QToolButton()
        self.view_list_btn.setText("📋")
        self.view_list_btn.setCheckable(True)
        self.view_list_btn.clicked.connect(lambda: self._set_view_mode(1))
        toolbar_h.addWidget(self.view_list_btn)

        self.view_details_btn = QToolButton()
        self.view_details_btn.setText("📊")
        self.view_details_btn.setCheckable(True)
        self.view_details_btn.clicked.connect(lambda: self._set_view_mode(2))
        toolbar_h.addWidget(self.view_details_btn)

        self.sort_combo = QListWidget()
        # Placeholder sort list (will be replaced by QComboBox for real impl)
        for label in ["Name", "Datum", "Größe", "Typ"]:
            QListWidgetItem(label, self.sort_combo)
        self.sort_combo.setMaximumHeight(70)
        self.sort_combo.setFixedWidth(90)
        toolbar_h.addWidget(self.sort_combo)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Suchen… (Fuzzy bald)")
        toolbar_h.addWidget(self.search_edit)

        main_v.addWidget(toolbar)

        # Content stacked views
        self.content_stack = QStackedWidget()
        self.grid_view = _PlaceholderView("Grid Ansicht – (Icons, Hover Preview)")
        self.list_view = QTreeWidget()
        self.list_view.setHeaderLabels(["Name", "Größe", "Typ", "Geändert"])
        self.list_view.setRootIsDecorated(False)
        self.details_view = QTreeWidget()
        self.details_view.setHeaderLabels(["Name", "Größe", "Typ", "Geändert", "Pfad"])
        self.details_view.setRootIsDecorated(False)
        self.content_stack.addWidget(self.grid_view)
        self.content_stack.addWidget(self.list_view)
        self.content_stack.addWidget(self.details_view)
        main_v.addWidget(self.content_stack, stretch=1)

        frame_layout.addWidget(main_container, stretch=1)

        # Details panel ---------------------------------------------------
        self.detail_panel = QWidget()
        self.detail_panel.setObjectName("DetailPanel")
        dp_v = QVBoxLayout(self.detail_panel)
        dp_v.setContentsMargins(8, 8, 8, 8)
        dp_v.setSpacing(8)

        preview_box = QGroupBox("Vorschau")
        pv_lay = QVBoxLayout(preview_box)
        self.preview_label = QLabel("(Keine Auswahl)")
        try:
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore[attr-defined]
        except Exception:
            pass
        self.preview_label.setObjectName("PreviewLabel")
        pv_lay.addWidget(self.preview_label, stretch=1)
        dp_v.addWidget(preview_box, stretch=2)

        meta_box = QGroupBox("Metadaten")
        meta_lay = QVBoxLayout(meta_box)
        self.meta_label = QLabel("–")
        self.meta_label.setObjectName("MetaLabel")
        try:
            self.meta_label.setAlignment(
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft  # type: ignore[attr-defined]
            )
        except Exception:
            pass
        meta_lay.addWidget(self.meta_label)
        dp_v.addWidget(meta_box, stretch=3)

        props_box = QGroupBox("Eigenschaften")
        props_lay = QVBoxLayout(props_box)
        self.props_label = QLabel("–")
        try:
            self.props_label.setAlignment(
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft  # type: ignore[attr-defined]
            )
        except Exception:
            pass
        self.props_label.setObjectName("PropsLabel")
        props_lay.addWidget(self.props_label)
        dp_v.addWidget(props_box, stretch=2)

        dp_v.addStretch(1)
        frame_layout.addWidget(self.detail_panel)

        root_layout.addWidget(frame, stretch=1)

        # Bottom status bar -----------------------------------------------
        status = QWidget()
        status.setObjectName("StatusBar")
        status_h = QHBoxLayout(status)
        status_h.setContentsMargins(8, 4, 8, 4)
        status_h.setSpacing(16)

        self.selection_label = QLabel("0 Objekte ausgewählt (0 B)")
        self.space_label = QLabel("Freier Speicher: –")
        self.settings_btn = QPushButton("⚙️ Einstellungen")
        self.settings_btn.setObjectName("SettingsButton")
        self.settings_btn.setFixedHeight(28)
        self.settings_btn.clicked.connect(self._open_settings_dialog)
        status_h.addWidget(self.selection_label)
        status_h.addWidget(self.space_label)
        status_h.addStretch(1)
        status_h.addWidget(self.settings_btn)
        root_layout.addWidget(status)

        # Finalize styling & data init
        self._apply_styles()
        self.refresh_free_space()
        self._entries: list[dict] = []
        self._load_directory_entries(self._current_dir)
        self.search_edit.textChanged.connect(self._apply_search_filter)

    # ------------------------------------------------------------------
    # Public helpers (future integration points)
    # ------------------------------------------------------------------
    def set_directory(self, path: Path) -> None:
        if not path.exists() or not path.is_dir():
            return
        self._current_dir = path
        self.breadcrumb.set_path(path)
        self.refresh_free_space(path)

    def update_selection(self, count: int, total_bytes: int) -> None:
        self.selection_label.setText(
            f"{count} Objekte ausgewählt ({self._format_size(total_bytes)})"
        )

    def refresh_free_space(self, path: Optional[Path] = None) -> None:
        path = path or self._current_dir
        try:
            free = None
            try:
                usage = os.statvfs(str(path))  # type: ignore[attr-defined]
                free = usage.f_bavail * usage.f_frsize
            except Exception:
                pass
            if free is None:
                try:
                    import shutil
                    disk = shutil.disk_usage(str(path))
                    free = disk.free
                except Exception:
                    free = None
            if free is not None:
                self.space_label.setText(f"Freier Speicher: {self._format_size(int(free))}")
            else:
                self.space_label.setText("Freier Speicher: –")
        except Exception:
            self.space_label.setText("Freier Speicher: –")

    # ------------------------------------------------------------------
    # Internal callbacks
    # ------------------------------------------------------------------
    def _on_breadcrumb_navigate(self, target: Path) -> None:
        # For now just set directory (real model update later)
        self.set_directory(target)

    def _set_view_mode(self, index: int) -> None:
        self.content_stack.setCurrentIndex(index)
        self.view_grid_btn.setChecked(index == 0)
        self.view_list_btn.setChecked(index == 1)
        self.view_details_btn.setChecked(index == 2)

    def _populate_sidebar_placeholders(self) -> None:
        self.sidebar.clear()
        quick = QTreeWidgetItem(["Schnellzugriff"])
        for label in ["🏠 Home", "⭐ Favoriten", "📁 Zuletzt", "🗑️ Papierkorb"]:
            QTreeWidgetItem(quick, [label])
        devices = QTreeWidgetItem(["Dieser PC"])
        # Enumerate Windows drives (basic) or mount points on *nix
        drives = []
        if os.name == 'nt':  # Windows drive letters
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                drive_path = f"{letter}:/"
                if os.path.exists(drive_path):
                    drives.append(f"💾 Laufwerk {letter}:")
        else:  # POSIX - use root & home
            drives.append("📂 /")
            drives.append(f"🏠 {Path.home()}")
        for label in drives[:8]:  # cap initial listing
            QTreeWidgetItem(devices, [label])
        QTreeWidgetItem(devices, ["🔌 Externes Gerät (Stub)"])
        health = QTreeWidgetItem(["Geräte Gesundheit (SMART)"])
        QTreeWidgetItem(health, ["✅ Drive C: OK"])
        QTreeWidgetItem(health, ["⚠️ Drive D: Warnung"])
        tools = QTreeWidgetItem(["Werkzeuge"])
        QTreeWidgetItem(tools, ["🔍 Duplikate Scanner"])
        QTreeWidgetItem(tools, ["💾 Backup Modul"])
        self.sidebar.addTopLevelItem(quick)
        self.sidebar.addTopLevelItem(devices)
        self.sidebar.addTopLevelItem(health)
        self.sidebar.addTopLevelItem(tools)
        self.sidebar.expandAll()

    # ------------------------------------------------------------------
    # Sidebar selection handling
    # ------------------------------------------------------------------
    def _on_sidebar_selection(self) -> None:
        items = self.sidebar.selectedItems()
        if not items:
            return
        item = items[0]
        text = item.text(0)
        parent = item.parent().text(0) if item.parent() else ""

        # Tools section
        if parent == "Werkzeuge":
            if text.startswith("🔍"):
                self._enter_tool_mode("duplicates")
            elif text.startswith("💾"):
                self._enter_tool_mode("backup")
            return

        # Quick access
        if parent == "Schnellzugriff":
            if "Home" in text:
                self._tool_mode = None
                self.set_directory(Path.home())
                return
            # Favoriten / Zuletzt / Papierkorb currently placeholders
            self.preview_label.setText("(Platzhalter – Favoriten / Zuletzt bald)")
            return

        # Drives
        if parent == "Dieser PC":
            if "Laufwerk" in text:
                # Extract drive letter
                letter = text.split("Laufwerk", 1)[1].strip().rstrip(":")[:1]
                candidate = Path(f"{letter}:/")
                if candidate.exists():
                    self._tool_mode = None
                    self.set_directory(candidate)
                    return
            elif text.startswith("📂 /"):
                self.set_directory(Path("/"))
                return
        # Health nodes ignored for navigation (future smart panel)

    def _enter_tool_mode(self, kind: str) -> None:
        self._tool_mode = kind
        if kind == "duplicates":
            self.preview_label.setText("Duplikat-Scanner Integration folgt – klassisches Modul wird eingebettet.")
            self.meta_label.setText("Aktion: Scannen nach doppelten Dateien. Geplante Features: Intelligente Auswahl, Stapellöschen.")
            self.props_label.setText("Backend: Reuse DuplicateScanner via Plugin API")
        elif kind == "backup":
            self.preview_label.setText("Backup-Modul Integration folgt – Profile & Zeitplan verfügbar.")
            self.meta_label.setText("Aktion: Backup ausführen / Dry-Run / Spiegelung. Zeitplan-Verwaltung in Planung.")
            self.props_label.setText("Backend: perform_backup & Scheduler werden gekapselt.")

    # ------------------------------------------------------------------
    # Directory & search helpers
    # ------------------------------------------------------------------
    def _load_directory_entries(self, path: Path) -> None:
        self._entries.clear()
        try:
            with os.scandir(path) as it:
                for idx, entry in enumerate(it):
                    if idx > 2000:  # safety cap for UI performance
                        break
                    try:
                        stat = entry.stat()
                        size = stat.st_size
                        mtime = stat.st_mtime
                    except Exception:
                        size = 0
                        mtime = 0
                    kind = 'Ordner' if entry.is_dir() else (entry.name.split('.')[-1].upper() if '.' in entry.name else 'Datei')
                    self._entries.append({
                        'name': entry.name,
                        'path': Path(entry.path),
                        'size': size,
                        'mtime': mtime,
                        'kind': kind,
                        'is_dir': entry.is_dir(),
                    })
        except Exception:
            pass
        self._refresh_views()

    def _apply_search_filter(self) -> None:
        self._refresh_views()

    def _refresh_views(self) -> None:
        term = self.search_edit.text().strip().lower()
        if term:
            filtered = [r for r in self._entries if term in r['name'].lower()]
        else:
            filtered = list(self._entries)

        # Update grid placeholder label text
        for child in self.grid_view.findChildren(QLabel):
            if child.objectName() == "PlaceholderLabel":
                child.setText(f"Grid Ansicht – {len(filtered)} Einträge (von {len(self._entries)})")

        # List view
        self.list_view.setUpdatesEnabled(False)
        self.list_view.clear()
        for rec in filtered:
            item = QTreeWidgetItem([
                rec['name'],
                self._format_size(rec['size']) if not rec['is_dir'] else "<Ordner>",
                rec['kind'],
                self._format_mtime(rec['mtime']),
            ])
            self.list_view.addTopLevelItem(item)
        self.list_view.setUpdatesEnabled(True)

        # Details view
        self.details_view.setUpdatesEnabled(False)
        self.details_view.clear()
        for rec in filtered:
            item = QTreeWidgetItem([
                rec['name'],
                self._format_size(rec['size']) if not rec['is_dir'] else "<Ordner>",
                rec['kind'],
                self._format_mtime(rec['mtime']),
                str(rec['path']),
            ])
            self.details_view.addTopLevelItem(item)
        self.details_view.setUpdatesEnabled(True)

    # ------------------------------------------------------------------
    # Settings / backend integration dialog
    # ------------------------------------------------------------------
    def _open_settings_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Dateiverwaltung – Einstellungen & Backend")
        lay = QVBoxLayout(dlg)
        info = QLabel(
            "<b>Ultra Modus</b><br>Backend-Funktionen Duplikate & Backup werden demnächst direkt eingebettet.\n"
            "Bis dahin können Sie das klassische Modul nutzen, indem Sie den Ultra Flag entfernen."  # guidance
        )
        info.setWordWrap(True)
        lay.addWidget(info)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)  # type: ignore[attr-defined]
        dlg.resize(520, 260)
        dlg.exec()

    # ------------------------------------------------------------------
    # Styling helpers
    # ------------------------------------------------------------------
    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget#Sidebar, QWidget#DetailPanel, QWidget#StatusBar {{
                background: {BG_SECONDARY};
            }}
            QWidget {{
                color: {TEXT_PRIMARY};
                background: {BG_PRIMARY};
                font-size: 13px;
            }}
            QGroupBox {{
                border: 1px solid {BORDER};
                border-radius: 4px;
                margin-top: 14px;
                padding: 4px 6px 6px 6px;
                background: {BG_SECONDARY};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: {TEXT_SECONDARY};
            }}
            QPushButton, QToolButton {{
                background: {BG_TERTIARY};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QPushButton:hover, QToolButton:hover {{
                background: {ACCENT_HOVER};
            }}
            QPushButton:checked, QToolButton:checked {{
                background: {ACCENT};
            }}
            QLineEdit {{
                background: {BG_SECONDARY};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 4px 6px;
                selection-background-color: {ACCENT};
            }}
            QLabel#PlaceholderLabel {{
                color: {TEXT_MUTED};
                font-size: 15px;
            }}
            QLabel#PreviewLabel {{
                background: {BG_TERTIARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 12px;
            }}
            QPushButton#SettingsButton {{
                background: {BG_TERTIARY};
            }}
            QPushButton#BreadcrumbButton {{
                background: transparent;
                border: none;
                padding: 2px 4px;
            }}
            QPushButton#BreadcrumbButton:hover {{
                background: {BG_TERTIARY};
                border-radius: 4px;
            }}
            QLabel#BreadcrumbSep {{
                color: {TEXT_MUTED};
            }}
        """
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    @staticmethod
    def _format_size(size: int) -> str:
        v = float(size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if v < 1024:
                return f"{v:.1f} {unit}"
            v /= 1024
        return f"{v:.1f} PB"

    @staticmethod
    def _format_mtime(mtime: float) -> str:
        try:
            import datetime as _dt
            if not mtime:
                return "--"
            dt = _dt.datetime.fromtimestamp(mtime)
            return dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            return "--"


__all__ = ["FileManagerUltraWidget"]
