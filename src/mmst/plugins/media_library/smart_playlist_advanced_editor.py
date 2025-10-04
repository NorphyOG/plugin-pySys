from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Any
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
    QWidget, QComboBox, QLineEdit, QSpinBox, QMessageBox, QCheckBox, QMenu, QInputDialog,
    QStyledItemDelegate, QTableWidget, QAbstractItemView, QHeaderView, QTableWidgetItem
)
from PySide6.QtCore import Qt, QSize, QModelIndex, QPersistentModelIndex
import time
from datetime import datetime
import json
import hashlib

from .smart_playlists import SmartPlaylist, Rule, RuleGroup, evaluate_smart_playlist

_RULE_FIELDS = [
    ("rating", "Bewertung"),
    ("kind", "Typ"),
    ("duration", "Dauer (s)"),
    ("mtime", "Geändert (Epoch)"),
    ("genre", "Genre"),
    ("tags", "Tags"),
    ("title", "Titel"),
]

# Mapping field -> plausible operators (subset / UI friendly)
_FIELD_OPS = {
    "rating": [">=", "<=", "==", ">", "<"],
    "kind": ["==", "!=", "in", "not_contains"],
    "duration": [">=", "<=", ">", "<", "between"],
    "mtime": [">=", "<=", ">", "<", "within_days"],
    "genre": ["contains", "not_contains", "=="],
    "tags": ["has_tag", "contains", "not_contains"],
    "title": ["contains", "not_contains", "startswith", "endswith", "regex"],
}


class SmartPlaylistAdvancedEditor(QDialog):
    """Tree-based editor for nested Smart Playlist rule groups.

    This initial version focuses on structure editing + preview count.
    Future enhancements: drag & drop, live inline preview list.
    """

    def __init__(self, playlist: SmartPlaylist, all_entries: Optional[List[tuple[Any, Path]]] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Erweiterter Smart Editor – {playlist.name}")
        self.resize(820, 640)
        self._original = playlist
        # Work on a shallow editable copy (we mutate object references but treat as draft)
        self._draft = playlist
        self._all_entries = all_entries or []  # Optional pre-fetched entries for preview acceleration
        
        # Delta evaluation cache
        self._last_signature = ""
        self._cached_results = []
        
        # Undo/Redo history
        self._history: List[str] = []  # JSON snapshots
        self._history_index = -1
        self._in_restore = False  # Flag to prevent history recording during restore

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit(self._draft.name)
        top.addWidget(self.name_edit, stretch=1)
        top.addWidget(QLabel("Sort:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["recent", "rating_desc", "duration_desc", "mtime_desc"])
        if self._draft.sort:
            idx = self.sort_combo.findText(self._draft.sort)
            if idx != -1:
                self.sort_combo.setCurrentIndex(idx)
        top.addWidget(self.sort_combo)
        top.addWidget(QLabel("Limit:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 100000)
        self.limit_spin.setValue(self._draft.limit or 0)
        top.addWidget(self.limit_spin)
        layout.addLayout(top)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Typ", "Match / Feld", "Operator", "Wert", "NOT"])
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._open_context_menu)
        self.tree.setColumnWidth(0, 90)
        # Drag & Drop internal reordering & regrouping
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        # Enable editing (we'll restrict via delegate)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.DoubleClicked | QTreeWidget.EditTrigger.SelectedClicked | QTreeWidget.EditTrigger.EditKeyPressed)
        layout.addWidget(self.tree, stretch=1)

        # Live preview table (top 25 results)
        preview_label = QLabel("Live Vorschau (Top 25):")
        layout.addWidget(preview_label)
        self.preview_table = QTableWidget(0, 4)
        self.preview_table.setHorizontalHeaderLabels(["Titel", "Bewertung", "Typ", "Dauer"])
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.setMaximumHeight(200)
        layout.addWidget(self.preview_table)

        # Buttons row
        row = QHBoxLayout()
        self.add_rule_btn = QPushButton("+ Regel")
        self.add_rule_btn.clicked.connect(self._add_rule)
        row.addWidget(self.add_rule_btn)
        self.add_group_btn = QPushButton("+ Gruppe")
        self.add_group_btn.clicked.connect(self._add_group)
        row.addWidget(self.add_group_btn)
        self.remove_btn = QPushButton("Entfernen")
        self.remove_btn.clicked.connect(self._remove_selected)
        row.addWidget(self.remove_btn)
        self.toggle_match_btn = QPushButton("Toggle AND/OR")
        self.toggle_match_btn.clicked.connect(self._toggle_group_mode)
        row.addWidget(self.toggle_match_btn)
        
        # Undo/Redo buttons
        self.undo_btn = QPushButton("↶ Undo")
        self.undo_btn.clicked.connect(self._undo)
        self.undo_btn.setEnabled(False)
        row.addWidget(self.undo_btn)
        self.redo_btn = QPushButton("↷ Redo")
        self.redo_btn.clicked.connect(self._redo)
        self.redo_btn.setEnabled(False)
        row.addWidget(self.redo_btn)
        
        row.addStretch(1)
        self.preview_btn = QPushButton("Vorschau aktualisieren")
        self.preview_btn.clicked.connect(self._update_preview)
        row.addWidget(self.preview_btn)
        self.preview_label = QLabel("Treffer: -")
        row.addWidget(self.preview_label)
        layout.addLayout(row)

        # Action buttons
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.cancel_btn = QPushButton("Abbrechen")
        self.cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(self.cancel_btn)
        self.ok_btn = QPushButton("Speichern")
        self.ok_btn.clicked.connect(self._on_accept)
        bottom.addWidget(self.ok_btn)
        layout.addLayout(bottom)

        # Build tree from playlist
        self._rebuild_tree()
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.setItemDelegate(_RuleDelegate(self))
        
        # Initialize history with current state
        self._save_state()

    # --- Tree Construction -------------------------------------------------
    def _rebuild_tree(self) -> None:
        self.tree.clear()
        root_group = self._draft.ensure_group()
        root_item = self._make_group_item(root_group, is_root=True)
        self.tree.addTopLevelItem(root_item)
        root_item.setExpanded(True)

    def _make_group_item(self, group: RuleGroup, *, is_root: bool = False) -> QTreeWidgetItem:
        item = QTreeWidgetItem(["Gruppe", f"{'ALL' if group.match=='all' else 'ANY'} ({len(group.rules)} Knoten)", "", "", ""])
        item.setData(0, Qt.ItemDataRole.UserRole, ("group", group))
        if group.negate:
            item.setCheckState(4, Qt.CheckState.Checked)
        else:
            item.setCheckState(4, Qt.CheckState.Unchecked)
        # Allow checkbox interaction
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        # Add direct rules
        for r in group.rules:
            item.addChild(self._make_rule_item(r))
        # Add subgroup objects
        for sg in getattr(group, 'groups', []):
            item.addChild(self._make_group_item(sg))
        return item

    def _make_rule_item(self, rule: Rule) -> QTreeWidgetItem:
        display = ["Regel", rule.field, rule.op, str(rule.value), ""]
        item = QTreeWidgetItem(display)
        item.setData(0, Qt.ItemDataRole.UserRole, ("rule", rule))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable)
        return item

    # --- Actions -----------------------------------------------------------
    def _current_item_payload(self):
        item = self.tree.currentItem()
        if not item:
            return None, None
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not payload:
            return None, None
        return payload

    def _add_rule(self) -> None:
        target_payload = self._current_item_payload()
        # Determine target group (fallback to root)
        if target_payload[0] == "group":
            group = target_payload[1]  # type: ignore[assignment]
        else:
            group = self._draft.ensure_group()
        # Default rule
        rule = Rule(field="rating", op=">=", value=3)
        if group is not None:
            group.rules.append(rule)  # type: ignore[arg-type]
        self._rebuild_tree()
        self._save_state()

    def _add_group(self) -> None:
        target_payload = self._current_item_payload()
        if target_payload[0] == "group":
            group = target_payload[1]  # type: ignore[assignment]
        else:
            group = self._draft.ensure_group()
        if group is not None:
            new_group = RuleGroup(match="all", negate=False, rules=[], groups=[])
            group.groups.append(new_group)  # type: ignore[arg-type]
            self._rebuild_tree()
            self._save_state()

    def _remove_selected(self) -> None:
        payload = self._current_item_payload()
        if not payload[0]:
            return
        root_group = self._draft.ensure_group()
        # recursive removal helper
        def prune(container: RuleGroup) -> bool:
            removed = False
            new_children = []
            for c in container.rules:
                if isinstance(c, RuleGroup):
                    if (payload[0] == "group" and c is payload[1]) or (payload[0] == "rule" and False):
                        removed = True
                        continue
                    if prune(c):
                        removed = True
                    else:
                        new_children.append(c)
                else:
                    if payload[0] == "rule" and c is payload[1]:
                        removed = True
                        continue
                    new_children.append(c)
            container.rules = new_children
            return removed
        prune(root_group)
        self._rebuild_tree()
        self._save_state()

    def _toggle_group_mode(self) -> None:
        payload = self._current_item_payload()
        if payload[0] != "group":
            return
        grp = payload[1]  # type: ignore[assignment]
        if grp is not None:
            grp.match = "any" if grp.match == "all" else "all"
            # Update label in place if possible
            item = self.tree.currentItem()
            if item:
                item.setText(1, f"{'ALL' if grp.match=='all' else 'ANY'} ({len(grp.rules)} Knoten)")
            else:
                self._rebuild_tree()
            self._save_state()
            self._maybe_auto_preview()
    
    # --- Undo/Redo State Management ----------------------------------------
    def _serialize_state(self) -> str:
        """Serialize current playlist state to JSON string."""
        try:
            def serialize_rule(r: Rule) -> dict:
                return {"field": r.field, "op": r.op, "value": r.value}
            
            def serialize_group(g: RuleGroup) -> dict:
                return {
                    "match": g.match,
                    "negate": g.negate,
                    "rules": [serialize_rule(r) for r in g.rules],
                    "groups": [serialize_group(sg) for sg in getattr(g, 'groups', [])]
                }
            
            root = self._draft.ensure_group()
            state = {
                "name": self.name_edit.text(),
                "sort": self.sort_combo.currentText(),
                "limit": self.limit_spin.value(),
                "group": serialize_group(root) if root else {}
            }
            return json.dumps(state, sort_keys=True)
        except Exception:
            return ""
    
    def _restore_state(self, state_json: str) -> None:
        """Restore playlist state from JSON string."""
        try:
            self._in_restore = True
            state = json.loads(state_json)
            
            # Restore metadata
            self.name_edit.setText(state.get("name", ""))
            sort_idx = self.sort_combo.findText(state.get("sort", "recent"))
            if sort_idx != -1:
                self.sort_combo.setCurrentIndex(sort_idx)
            self.limit_spin.setValue(state.get("limit", 0))
            
            # Restore group structure
            def deserialize_group(data: dict) -> RuleGroup:
                rules = [Rule(field=r["field"], op=r["op"], value=r["value"]) for r in data.get("rules", [])]
                groups = [deserialize_group(g) for g in data.get("groups", [])]
                return RuleGroup(
                    match=data.get("match", "all"),
                    negate=data.get("negate", False),
                    rules=rules,
                    groups=groups
                )
            
            if "group" in state and state["group"]:
                self._draft.group = deserialize_group(state["group"])
            
            self._rebuild_tree()
            self._in_restore = False
        except Exception:
            self._in_restore = False
    
    def _save_state(self) -> None:
        """Save current state to history."""
        if self._in_restore:
            return
        
        state = self._serialize_state()
        if not state:
            return
        
        # Truncate history if we're not at the end
        if self._history_index < len(self._history) - 1:
            self._history = self._history[:self._history_index + 1]
        
        # Add new state (but avoid duplicates)
        if not self._history or self._history[-1] != state:
            self._history.append(state)
            self._history_index = len(self._history) - 1
        
        self._update_undo_redo_buttons()
    
    def _update_undo_redo_buttons(self) -> None:
        """Update enabled state of undo/redo buttons."""
        self.undo_btn.setEnabled(self._history_index > 0)
        self.redo_btn.setEnabled(self._history_index < len(self._history) - 1)
    
    def _undo(self) -> None:
        """Undo last change."""
        if self._history_index > 0:
            self._history_index -= 1
            self._restore_state(self._history[self._history_index])
            self._update_undo_redo_buttons()
            self._update_preview()
    
    def _redo(self) -> None:
        """Redo last undone change."""
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._restore_state(self._history[self._history_index])
            self._update_undo_redo_buttons()
            self._update_preview()

    def _compute_signature(self) -> str:
        """Compute signature hash from playlist structure for caching."""
        try:
            # Serialize playlist structure to JSON for consistent hashing
            def serialize_rule(r: Rule) -> dict:
                return {"field": r.field, "op": r.op, "value": r.value}
            
            def serialize_group(g: RuleGroup) -> dict:
                return {
                    "match": g.match,
                    "negate": g.negate,
                    "rules": [serialize_rule(r) for r in g.rules],
                    "groups": [serialize_group(sg) for sg in getattr(g, 'groups', [])]
                }
            
            root = self._draft.ensure_group()
            structure = serialize_group(root) if root else {}
            json_str = json.dumps(structure, sort_keys=True)
            return hashlib.sha256(json_str.encode()).hexdigest()
        except Exception:
            return ""

    def _update_preview(self) -> None:
        try:
            # Check cache signature
            current_sig = self._compute_signature()
            if current_sig and current_sig == self._last_signature and self._cached_results:
                # Use cached results
                results = self._cached_results
            else:
                # Evaluate fresh
                # Use evaluation to count results; we reuse existing playlist object
                # Provide a minimal metadata provider returning an object with no extra fields
                def _meta_provider(p: Path):  # pragma: no cover - tiny closure
                    class _M:  # noqa: N801
                        pass
                    return _M()

                entries = self._all_entries or []
                results = evaluate_smart_playlist(self._draft, entries, _meta_provider)
                
                # Cache results
                self._last_signature = current_sig
                self._cached_results = results
            
            count = len(results)
            self.preview_label.setText(f"Treffer: {count}")
            
            # Update preview table with top 25
            self.preview_table.setRowCount(0)
            for idx, (media, path) in enumerate(results[:25]):
                self.preview_table.insertRow(idx)
                title = getattr(media, 'title', '') or media.name or ''
                rating = getattr(media, 'rating', 0) or 0
                kind = getattr(media, 'kind', 'unknown')
                duration = getattr(media, 'duration', 0) or 0
                self.preview_table.setItem(idx, 0, QTableWidgetItem(str(title)))
                self.preview_table.setItem(idx, 1, QTableWidgetItem(f"{'★' * rating}"))
                self.preview_table.setItem(idx, 2, QTableWidgetItem(str(kind)))
                dur_str = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "-"
                self.preview_table.setItem(idx, 3, QTableWidgetItem(dur_str))
        except Exception as exc:
            self.preview_label.setText(f"Fehler: {exc}")

    # --- Event / Editing Logic ---------------------------------------------
    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:  # pragma: no cover - UI event
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not payload:
            return
        kind, obj = payload
        if kind == "group" and column == 4:
            obj.negate = item.checkState(4) == Qt.CheckState.Checked  # type: ignore[attr-defined]
            self._save_state()
            self._maybe_auto_preview()

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:  # pragma: no cover
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not payload:
            return
        kind, obj = payload
        if kind == "rule":
            self._edit_rule(obj)  # type: ignore[arg-type]

    def _open_context_menu(self, pos) -> None:  # pragma: no cover
        menu = QMenu(self)
        item = self.tree.itemAt(pos)
        payload = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if payload:
            kind, obj = payload
            if kind == "rule":
                menu.addAction("Regel bearbeiten", lambda: self._edit_rule(obj))
            if kind == "group":
                menu.addAction("AND/OR umschalten", self._toggle_group_mode)
                menu.addAction("NOT toggeln", lambda: self._toggle_not(item))
            menu.addAction("Entfernen", self._remove_selected)
            menu.addSeparator()
        menu.addAction("Regel hinzufügen", self._add_rule)
        menu.addAction("Gruppe hinzufügen", self._add_group)
        menu.exec(self.tree.mapToGlobal(pos))

    def _toggle_not(self, item: QTreeWidgetItem) -> None:
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not payload:
            return
        kind, obj = payload
        if kind != "group":
            return
        obj.negate = not getattr(obj, "negate", False)
        item.setCheckState(4, Qt.CheckState.Checked if obj.negate else Qt.CheckState.Unchecked)
        # Keep label unchanged except maybe style in future
        self._maybe_auto_preview()

    def _edit_rule(self, rule: Rule) -> None:
        # Simple inline dialog sequence for field/op/value
        field, ok = QInputDialog.getItem(self, "Feld", "Feld wählen:", [f for f, _ in _RULE_FIELDS], 0, False)
        if not ok:
            return
        ops = _FIELD_OPS.get(field, ["==", "!="])
        op, ok = QInputDialog.getItem(self, "Operator", "Operator wählen:", ops, 0, False)
        if not ok:
            return
        if op == "between":
            first, ok1 = QInputDialog.getInt(self, "Between", "Min-Wert:", 0, 0, 1_000_000, 1)
            if not ok1:
                return
            second, ok2 = QInputDialog.getInt(self, "Between", "Max-Wert:", first, first, 1_000_000, 1)
            if not ok2:
                return
            value = [first, second]
        elif op == "within_days":
            # Offer quick macro options
            macro, ok_macro = QInputDialog.getItem(
                self, "Zeitspanne", "Wähle Makro oder 'Custom':",
                ["Custom", "Heute", "Letzte 7 Tage", "Letzte 30 Tage", "Dieses Jahr"],
                0, False
            )
            if not ok_macro:
                return
            if macro == "Heute":
                value = 1
            elif macro == "Letzte 7 Tage":
                value = 7
            elif macro == "Letzte 30 Tage":
                value = 30
            elif macro == "Dieses Jahr":
                # Calculate days since Jan 1 of current year
                now = datetime.now()
                start_of_year = datetime(now.year, 1, 1)
                value = (now - start_of_year).days + 1
            else:  # Custom
                days, okd = QInputDialog.getInt(self, "Within Days", "Tage:", 7, 1, 3650, 1)
                if not okd:
                    return
                value = days
        else:
            text, okv = QInputDialog.getText(self, "Wert", "Wert:", text=str(rule.value) if rule.value is not None else "")
            if not okv:
                return
            value = text.strip()
        # Apply
        rule.field = field
        rule.op = op
        rule.value = value
        self._rebuild_tree()
        self._save_state()
        self._maybe_auto_preview()

    def _maybe_auto_preview(self) -> None:
        # For now always auto-refresh; could add a checkbox later
        self._update_preview()

    def _on_accept(self) -> None:
        self._draft.name = self.name_edit.text().strip() or self._draft.name
        self._draft.sort = self.sort_combo.currentText()
        self._draft.limit = self.limit_spin.value() or None
        if not (self._draft.group and (self._draft.group.rules or self._draft.group.groups)):
            QMessageBox.warning(self, "Ungültig", "Mindestens eine Regel oder Gruppe erforderlich.")
            return
        self.accept()

    def playlist(self) -> SmartPlaylist:
        return self._draft

    # --- Drag & Drop Override Hook -----------------------------------------
    def dropEvent(self, event):  # pragma: no cover - GUI interaction
        super().dropEvent(event)  # type: ignore[misc]
        # After Qt rearranged items, rebuild underlying draft structure
        self._reconstruct_model_from_tree()
        self._save_state()
        self._maybe_auto_preview()

    def _reconstruct_model_from_tree(self) -> None:
        root = self._draft.ensure_group()
        root.rules.clear()

        def build_from_item(item: QTreeWidgetItem, group: RuleGroup):
            for i in range(item.childCount()):
                child_item = item.child(i)
                payload = child_item.data(0, Qt.ItemDataRole.UserRole)
                if not payload:
                    continue
                kind, obj = payload
                if kind == "group":
                    g = obj  # type: ignore[assignment]
                    new_group = RuleGroup(match=g.match, negate=g.negate, rules=list(g.rules), groups=[])
                    group.groups.append(new_group)
                    build_from_item(child_item, new_group)
                else:
                    group.rules.append(obj)  # type: ignore[arg-type]

        top = self.tree.topLevelItem(0)
        if top:
            build_from_item(top, root)
        # Refresh labels (avoid full rebuild to preserve selection)
        self._refresh_group_labels(top)

    def _refresh_group_labels(self, item: QTreeWidgetItem | None):
        if not item:
            return
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if payload and payload[0] == "group":
            grp = payload[1]
            total = len(grp.rules) + len(getattr(grp, 'groups', []))
            item.setText(1, f"{'ALL' if grp.match=='all' else 'ANY'} ({total} Knoten)")
        for i in range(item.childCount()):
            self._refresh_group_labels(item.child(i))


class _RuleDelegate(QStyledItemDelegate):
    """Delegate for inline editing of rule rows (field/operator/value).

    Columns:
      1: Field (only for rule rows)
      2: Operator (depends on field)
      3: Value (text or encoded list)
    """

    def __init__(self, editor: SmartPlaylistAdvancedEditor) -> None:  # type: ignore[name-defined]
        super().__init__(editor)
        self._editor = editor

    def _is_rule_index(self, index) -> bool:  # index can be QModelIndex or QPersistentModelIndex
        item = self._editor.tree.itemFromIndex(index)
        if not item:
            return False
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        return bool(payload and payload[0] == "rule")

    def createEditor(self, parent, option, index):  # noqa: D401
        if not self._is_rule_index(index):
            # Return a dummy line edit to satisfy base expectation
            return QLineEdit(parent)
        col = index.column()
        item = self._editor.tree.itemFromIndex(index)
        payload = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        rule = payload[1] if payload else None
        if col == 1:  # field
            combo = QComboBox(parent)
            for f, label in _RULE_FIELDS:
                combo.addItem(label, f)
            # preselect
            if rule:
                idx = combo.findData(rule.field)
                if idx != -1:
                    combo.setCurrentIndex(idx)
            return combo
        if col == 2:  # operator
            combo = QComboBox(parent)
            field = rule.field if rule else "rating"
            for op in _FIELD_OPS.get(field, ["==", "!="]):
                combo.addItem(op)
            # preselect
            if rule:
                idx = combo.findText(rule.op)
                if idx != -1:
                    combo.setCurrentIndex(idx)
            return combo
        if col == 3:  # value
            edit = QLineEdit(parent)
            if rule:
                if isinstance(rule.value, list):
                    edit.setText(",".join(str(v) for v in rule.value))
                else:
                    edit.setText(str(rule.value))
            return edit
        # Fallback
        return QLineEdit(parent)

    def setEditorData(self, editor, index):  # noqa: D401
        # Already initialized in createEditor
        return super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):  # noqa: D401
        if not self._is_rule_index(index):
            return
        item = self._editor.tree.itemFromIndex(index)
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        rule = payload[1]
        col = index.column()
        if col == 1:  # field
            field = editor.currentData() if isinstance(editor, QComboBox) else editor.currentText()
            rule.field = field
            item.setText(1, field)
            # Reset operator to first valid for new field
            ops = _FIELD_OPS.get(field, ["==", "!="])
            rule.op = ops[0]
            item.setText(2, rule.op)
        elif col == 2:  # operator
            op = editor.currentText() if isinstance(editor, QComboBox) else str(editor.text())
            rule.op = op
            item.setText(2, op)
        elif col == 3:  # value
            text = editor.text() if isinstance(editor, QLineEdit) else str(editor.text())
            if rule.op == "between":
                parts = [p.strip() for p in text.split(",") if p.strip()]
                if len(parts) == 2 and all(p.replace('.', '', 1).isdigit() for p in parts):
                    rule.value = [float(parts[0]), float(parts[1])]  # type: ignore[list-item]
                else:
                    # invalid between -> keep old value
                    pass
            else:
                rule.value = text
            item.setText(3, text)
        self._editor._maybe_auto_preview()
        return super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index):  # noqa: D401
        editor.setGeometry(option.rect)

    # No accept logic in delegate

    # End delegate

    
    # Add methods back to editor class below (patch insertion)
