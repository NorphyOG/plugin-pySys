from __future__ import annotations

from typing import List, Any, Tuple
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QSpinBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QWidget,
)
from PySide6.QtCore import Qt  # type: ignore[import-not-found]

from .smart_playlists import SmartPlaylist, Rule  # type: ignore

try:  # optional internal imports (underscored constants)
    from .smart_playlists import _ALLOWED_FIELDS, _OPS  # type: ignore
except Exception:  # pragma: no cover
    _ALLOWED_FIELDS = set()
    _OPS = {}


_SORT_KEYS = [
    "recent",
    "mtime_desc",
    "mtime_asc",
    "rating_desc",
    "rating_asc",
    "duration_desc",
    "duration_asc",
    "title_asc",
    "title_desc",
    "kind_asc",
    "kind_desc",
]


class SmartPlaylistEditor(QDialog):
    """Dialog zum Bearbeiten / Erstellen einer Smart Playlist."""

    def __init__(self, playlist: SmartPlaylist, parent: QWidget | None = None) -> None:  # type: ignore[override]
        super().__init__(parent)
        self.setWindowTitle("Smart Playlist bearbeiten")
        self.setModal(True)
        self._original_name = playlist.name
        self._playlist = playlist

        main = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(playlist.name)
        form.addRow("Name:", self.name_edit)
        self.desc_edit = QLineEdit(playlist.description or "")
        form.addRow("Beschreibung:", self.desc_edit)
        self.match_combo = QComboBox()
        self.match_combo.addItem("Alle (UND)", "all")
        self.match_combo.addItem("Mindestens eine (ODER)", "any")
        m_index = 0 if playlist.match == "all" else 1
        self.match_combo.setCurrentIndex(m_index)
        form.addRow("Match Modus:", self.match_combo)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 1_000_000)
        self.limit_spin.setSpecialValueText("(Keine Begrenzung)")
        self.limit_spin.setValue(playlist.limit if playlist.limit is not None else 0)
        form.addRow("Limit:", self.limit_spin)
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("(Unverändert)", "")
        for key in _SORT_KEYS:
            self.sort_combo.addItem(key, key)
        if playlist.sort:
            idx = self.sort_combo.findData(playlist.sort)
            if idx >= 0:
                self.sort_combo.setCurrentIndex(idx)
        form.addRow("Sortierung:", self.sort_combo)
        main.addLayout(form)

        # Rules table
        self.rules_table = QTableWidget(0, 3, self)
        self.rules_table.setHorizontalHeaderLabels(["Feld", "Operator", "Wert"])
        self.rules_table.verticalHeader().setVisible(False)
        self.rules_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rules_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.rules_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        main.addWidget(self.rules_table, stretch=1)

        for r in playlist.rules:
            self._append_rule_row(r.field, r.op, r.value)

        # Buttons
        row = QHBoxLayout()
        self.add_btn = QPushButton("Regel hinzufügen")
        self.add_btn.clicked.connect(self._add_rule)
        row.addWidget(self.add_btn)
        self.del_btn = QPushButton("Entfernen")
        self.del_btn.clicked.connect(self._remove_rule)
        row.addWidget(self.del_btn)
        self.up_btn = QPushButton("Hoch")
        self.up_btn.clicked.connect(self._move_up)
        row.addWidget(self.up_btn)
        self.down_btn = QPushButton("Runter")
        self.down_btn.clicked.connect(self._move_down)
        row.addWidget(self.down_btn)
        row.addStretch(1)
        main.addLayout(row)

        # Action buttons
        actions = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#c66;font-size:11px;")
        actions.addWidget(self.status_label, stretch=1)
        self.cancel_btn = QPushButton("Abbrechen")
        self.cancel_btn.clicked.connect(self.reject)
        actions.addWidget(self.cancel_btn)
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self._accept)
        actions.addWidget(self.ok_btn)
        main.addLayout(actions)

        self.resize(680, 460)

    # --- internal helpers -------------------------------------------------
    def _append_rule_row(self, field: str = "", op: str = "==", value: Any = "") -> None:
        row = self.rules_table.rowCount()
        self.rules_table.insertRow(row)
        self.rules_table.setItem(row, 0, QTableWidgetItem(str(field)))
        self.rules_table.setItem(row, 1, QTableWidgetItem(str(op)))
        self.rules_table.setItem(row, 2, QTableWidgetItem(str(value)))

    def _add_rule(self) -> None:
        self._append_rule_row()

    def _remove_rule(self) -> None:
        rows = self.rules_table.selectionModel().selectedRows() if self.rules_table.selectionModel() else []
        if not rows:
            return
        self.rules_table.removeRow(rows[0].row())

    def _move_up(self) -> None:
        rows = self.rules_table.selectionModel().selectedRows() if self.rules_table.selectionModel() else []
        if not rows:
            return
        r = rows[0].row()
        if r <= 0:
            return
        self._swap_rows(r, r - 1)
        self.rules_table.selectRow(r - 1)

    def _move_down(self) -> None:
        rows = self.rules_table.selectionModel().selectedRows() if self.rules_table.selectionModel() else []
        if not rows:
            return
        r = rows[0].row()
        if r >= self.rules_table.rowCount() - 1:
            return
        self._swap_rows(r, r + 1)
        self.rules_table.selectRow(r + 1)

    def _swap_rows(self, a: int, b: int) -> None:
        for col in range(3):
            ia = self.rules_table.item(a, col)
            ib = self.rules_table.item(b, col)
            ta = ia.text() if ia else ""
            tb = ib.text() if ib else ""
            if ia:
                ia.setText(tb)
            else:
                self.rules_table.setItem(a, col, QTableWidgetItem(tb))
            if ib:
                ib.setText(ta)
            else:
                self.rules_table.setItem(b, col, QTableWidgetItem(ta))

    # --- validation / extraction -----------------------------------------
    def _collect_rules(self) -> Tuple[List[Rule], List[str]]:
        problems: List[str] = []
        result: List[Rule] = []
        for r in range(self.rules_table.rowCount()):
            field_item = self.rules_table.item(r, 0)
            op_item = self.rules_table.item(r, 1)
            val_item = self.rules_table.item(r, 2)
            field = (field_item.text().strip() if field_item else "")
            op = (op_item.text().strip() if op_item else "")
            raw_value = (val_item.text().strip() if val_item else "")
            if not field and not op and not raw_value:
                continue  # allow blank trailing row
            if field not in _ALLOWED_FIELDS:
                problems.append(f"Ungültiges Feld in Zeile {r+1}: {field}")
                continue
            if op not in _OPS:
                problems.append(f"Ungültiger Operator in Zeile {r+1}: {op}")
                continue
            value: Any = raw_value
            if op == "between":
                parts = [p.strip() for p in raw_value.replace(";", ",").split(",") if p.strip()]
                if len(parts) != 2:
                    problems.append(f"between erwartet 2 Werte (Zeile {r+1})")
                    continue
                try:
                    low = float(parts[0]) if parts[0].replace('.', '', 1).isdigit() else parts[0]
                    high = float(parts[1]) if parts[1].replace('.', '', 1).isdigit() else parts[1]
                    value = [low, high]
                except Exception:
                    problems.append(f"between Werte ungültig (Zeile {r+1})")
                    continue
            else:
                # numeric coercion attempt
                if raw_value.replace('.', '', 1).isdigit():
                    try:
                        if '.' in raw_value:
                            value = float(raw_value)
                        else:
                            value = int(raw_value)
                    except Exception:
                        value = raw_value
            result.append(Rule(field=field, op=op, value=value))
        return result, problems

    def _accept(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            self.status_label.setText("Name darf nicht leer sein.")
            return
        rules, problems = self._collect_rules()
        if problems:
            self.status_label.setText("; ".join(problems[:2]))
            return
        limit_value = self.limit_spin.value()
        limit = limit_value if limit_value > 0 else None
        match_mode = self.match_combo.currentData() or "all"
        sort_data = self.sort_combo.currentData() or None
        self._playlist.name = name
        self._playlist.description = self.desc_edit.text().strip() or None
        self._playlist.match = match_mode
        self._playlist.limit = limit
        self._playlist.sort = sort_data
        self._playlist.rules = rules
        self.accept()

    # Expose the possibly modified playlist object
    def playlist(self) -> SmartPlaylist:
        return self._playlist
