from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from PySide6.QtCore import Qt  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.audio import AudioDevice
from ...core.plugin_base import BasePlugin, PluginManifest
from .recording import RecordingController, RecordingError

try:  # pragma: no cover - optional dependency
    from mutagen import MutagenError  # type: ignore[import-not-found]
    from mutagen.wave import WAVE  # type: ignore[import-not-found]
    from mutagen.id3 import (  # type: ignore[import-not-found]
        COMM,
        ID3,
        ID3NoHeaderError,
        TALB,
        TCON,
        TIT2,
        TPE1,
    )
except Exception:  # pragma: no cover - missing runtime dependency
    MutagenError = Exception  # type: ignore[assignment]
    WAVE = None  # type: ignore[assignment]
    ID3 = None  # type: ignore[assignment]
    COMM = TALB = TCON = TIT2 = TPE1 = None  # type: ignore[assignment]
    ID3NoHeaderError = Exception  # type: ignore[assignment]

_EQ_BANDS: Tuple[int, ...] = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
_FLAT_VALUES: List[int] = [0 for _ in _EQ_BANDS]


def _format_duration(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds >= 60:
        minutes = int(seconds // 60)
        remaining = seconds - minutes * 60
        return f"{minutes}m {remaining:0.1f}s"
    return f"{seconds:0.1f}s"


def _format_filesize(size_bytes: int) -> str:
    size = float(max(0, size_bytes))
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    if idx == 0:
        return f"{int(size)} {units[idx]}"
    return f"{size:0.1f} {units[idx]}"
class EqualizerPanel(QWidget):
    def __init__(self, plugin: "AudioToolsPlugin", bus: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._plugin = plugin
        self._bus = bus
        self._loading = False
        self._sliders: List[QSlider] = []
        self._value_labels: List[QLabel] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        device_box = QGroupBox("Geräteauswahl")
        device_form = QFormLayout(device_box)
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        device_form.addRow("Gerät", self.device_combo)
        layout.addWidget(device_box)

        preset_box = QGroupBox("Presets")
        preset_layout = QHBoxLayout(preset_box)
        self.preset_combo = QComboBox()
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self.preset_combo, stretch=1)

        self.preset_status = QLabel("")
        preset_layout.addWidget(self.preset_status)

        self.save_button = QPushButton("Speichern …")
        self.save_button.clicked.connect(self._save_preset)
        preset_layout.addWidget(self.save_button)

        self.delete_button = QPushButton("Löschen")
        self.delete_button.clicked.connect(self._delete_preset)
        preset_layout.addWidget(self.delete_button)

        self.reset_button = QPushButton("Zurücksetzen")
        self.reset_button.clicked.connect(self._reset_values)
        preset_layout.addWidget(self.reset_button)

        layout.addWidget(preset_box)

        sliders_box = QGroupBox("10-Band Equalizer")
        sliders_layout = QHBoxLayout(sliders_box)
        for index, freq in enumerate(_EQ_BANDS):
            column = QVBoxLayout()
            label = QLabel(f"{freq} Hz")
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            column.addWidget(label)

            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(-12, 12)
            slider.setTickInterval(1)
            slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
            slider.valueChanged.connect(partial(self._on_slider_value_changed, index))
            self._sliders.append(slider)
            column.addWidget(slider, stretch=1)

            value_label = QLabel("0 dB")
            value_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            self._value_labels.append(value_label)
            column.addWidget(value_label)

            sliders_layout.addLayout(column)
        layout.addWidget(sliders_box, stretch=1)

        layout.addStretch(1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def refresh_devices(self) -> None:
        devices = self._plugin.get_devices(self._bus)
        selected = self._plugin.get_selected_device(self._bus)
        if selected is None and devices:
            selected = devices[0].identifier
            self._plugin.set_selected_device(self._bus, selected)

        self._loading = True
        try:
            self.device_combo.clear()
            for device in devices:
                label = f"{device.name} ({device.host_api})"
                self.device_combo.addItem(label, device.identifier)
            if selected:
                index = self.device_combo.findData(selected)
                if index != -1:
                    self.device_combo.setCurrentIndex(index)
                elif self.device_combo.count() > 0:
                    self.device_combo.setCurrentIndex(0)
            self._load_device_state()
        finally:
            self._loading = False

    def current_device_id(self) -> Optional[str]:
        data = self.device_combo.currentData()
        if isinstance(data, str):
            return data
        return None

    def current_values(self) -> List[int]:
        return [slider.value() for slider in self._sliders]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_device_state(self) -> None:
        device_id = self.current_device_id()
        if not device_id:
            self.preset_combo.clear()
            return

        state = self._plugin.get_device_state(self._bus, device_id)
        if not isinstance(state, dict):
            state = {}
        presets_obj = state.get("presets")
        presets = presets_obj if isinstance(presets_obj, dict) else {}
        preset_names = sorted(name for name in presets.keys() if isinstance(name, str))
        active_obj = state.get("active_preset")
        active = active_obj if isinstance(active_obj, str) else "Flat"
        values_obj = state.get("values")
        if isinstance(values_obj, list):
            values = [int(v) if isinstance(v, (int, float)) else 0 for v in values_obj[: len(_EQ_BANDS)]]
            while len(values) < len(_EQ_BANDS):
                values.append(0)
        else:
            values = list(_FLAT_VALUES)

        self._loading = True
        try:
            self.preset_combo.clear()
            for name in preset_names:
                self.preset_combo.addItem(name)
            if self.preset_combo.count() == 0:
                self.preset_combo.addItem("Flat")
            target = active if active in preset_names else "Flat"
            index = self.preset_combo.findText(target)
            if index == -1:
                index = self.preset_combo.findText("Flat")
            if index != -1:
                self.preset_combo.setCurrentIndex(index)
        finally:
            self._loading = False

        self._apply_values(values)
        self._update_button_states()
        self._update_status_label()

    def _apply_values(self, values: List[int]) -> None:
        for slider, value_label, value in zip(self._sliders, self._value_labels, values):
            slider.blockSignals(True)
            slider.setValue(int(value))
            slider.blockSignals(False)
            value_label.setText(f"{int(value)} dB")

    def _update_button_states(self) -> None:
        self.delete_button.setEnabled(self.preset_combo.count() > 1)

    def _update_status_label(self) -> None:
        device_id = self.current_device_id()
        if not device_id:
            self.preset_status.setText("")
            return
        state = self._plugin.get_device_state(self._bus, device_id)
        if not isinstance(state, dict):
            state = {}
        active_obj = state.get("active_preset")
        active = active_obj if isinstance(active_obj, str) else "Flat"
        presets_obj = state.get("presets")
        presets = presets_obj if isinstance(presets_obj, dict) else {}
        raw_values = presets.get(active, list(_FLAT_VALUES)) if isinstance(active, str) else list(_FLAT_VALUES)
        if isinstance(raw_values, list):
            preset_values = [int(v) if isinstance(v, (int, float)) else 0 for v in raw_values[: len(_EQ_BANDS)]]
            while len(preset_values) < len(_EQ_BANDS):
                preset_values.append(0)
        else:
            preset_values = list(_FLAT_VALUES)
        current_values = self.current_values()
        if current_values == preset_values:
            self.preset_status.setText(f"Preset: {active}")
        else:
            self.preset_status.setText(f"Preset: {active} (angepasst)")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_device_changed(self) -> None:
        if self._loading:
            return
        device_id = self.current_device_id()
        if not device_id:
            return
        self._plugin.set_selected_device(self._bus, device_id)
        self._load_device_state()

    def _on_preset_changed(self) -> None:
        if self._loading:
            return
        device_id = self.current_device_id()
        if not device_id:
            return
        preset_name = self.preset_combo.currentText()
        if not preset_name:
            return
        values = self._plugin.load_preset(self._bus, device_id, preset_name)
        self._apply_values(values)
        self._plugin.set_active_preset(self._bus, device_id, preset_name)
        self._update_status_label()

    def _save_preset(self) -> None:
        device_id = self.current_device_id()
        if not device_id:
            return
        current_values = self.current_values()
        name, ok = QInputDialog.getText(self, "Preset speichern", "Name")
        if not ok or not name.strip():
            return
        name = name.strip()
        existing = self.preset_combo.findText(name)
        if existing != -1:
            overwrite = QMessageBox.question(
                self,
                "Preset überschreiben",
                f"Preset '{name}' existiert bereits. Überschreiben?",
            )
            if overwrite != QMessageBox.StandardButton.Yes:
                return
        self._plugin.save_preset(self._bus, device_id, name, current_values)
        self.refresh_devices()
        index = self.preset_combo.findText(name)
        if index != -1:
            self.preset_combo.setCurrentIndex(index)
        self._update_status_label()

    def _delete_preset(self) -> None:
        device_id = self.current_device_id()
        if not device_id:
            return
        preset_name = self.preset_combo.currentText()
        if not preset_name:
            return
        confirm = QMessageBox.question(
            self,
            "Preset löschen",
            f"Preset '{preset_name}' wirklich löschen?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._plugin.delete_preset(self._bus, device_id, preset_name)
        except ValueError as exc:
            QMessageBox.warning(self, "Preset kann nicht gelöscht werden", str(exc))
            return
        self.refresh_devices()

    def _reset_values(self) -> None:
        self._apply_values(list(_FLAT_VALUES))
        self._push_values()

    def _on_slider_value_changed(self, index: int, value: int) -> None:
        self._value_labels[index].setText(f"{value} dB")
        self._push_values()

    def _push_values(self) -> None:
        device_id = self.current_device_id()
        if not device_id:
            return
        values = self.current_values()
        self._plugin.update_device_values(self._bus, device_id, values)
        self._update_status_label()


class QualityDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], quality: Dict[str, int]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aufnahmequalität")
        form = QFormLayout(self)

        self.sample_rate = QSpinBox()
        self.sample_rate.setRange(8000, 192000)
        self.sample_rate.setSingleStep(1000)
        self.sample_rate.setValue(int(quality.get("sample_rate", 48000)))
        form.addRow("Sample Rate (Hz)", self.sample_rate)

        self.bit_depth = QSpinBox()
        self.bit_depth.setRange(8, 32)
        self.bit_depth.setSingleStep(1)
        self.bit_depth.setValue(int(quality.get("bit_depth", 24)))
        form.addRow("Bit Tiefe", self.bit_depth)

        self.channels = QSpinBox()
        self.channels.setRange(1, 8)
        self.channels.setValue(int(quality.get("channels", 2)))
        form.addRow("Kanäle", self.channels)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    def result_quality(self) -> Dict[str, int]:
        return {
            "sample_rate": int(self.sample_rate.value()),
            "bit_depth": int(self.bit_depth.value()),
            "channels": int(self.channels.value()),
        }


class MetadataDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], metadata: Dict[str, str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Metadaten bearbeiten")
        form = QFormLayout(self)

        self.title_edit = QLineEdit(metadata.get("title", ""))
        form.addRow("Titel", self.title_edit)

        self.artist_edit = QLineEdit(metadata.get("artist", ""))
        form.addRow("Künstler", self.artist_edit)

        self.album_edit = QLineEdit(metadata.get("album", ""))
        form.addRow("Album", self.album_edit)

        self.genre_edit = QLineEdit(metadata.get("genre", ""))
        form.addRow("Genre", self.genre_edit)

        self.comment_edit = QPlainTextEdit()
        self.comment_edit.setPlainText(metadata.get("comment", ""))
        form.addRow("Kommentar", self.comment_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    def result_metadata(self) -> Dict[str, str]:
        return {
            "title": self.title_edit.text().strip(),
            "artist": self.artist_edit.text().strip(),
            "album": self.album_edit.text().strip(),
            "genre": self.genre_edit.text().strip(),
            "comment": self.comment_edit.toPlainText().strip(),
        }


class RecorderPanel(QWidget):
    def __init__(self, plugin: "AudioToolsPlugin", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._plugin = plugin
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        device_box = QGroupBox("Aufnahmequelle")
        device_form = QFormLayout(device_box)
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        device_form.addRow("Gerät", self.device_combo)
        layout.addWidget(device_box)

        output_box = QGroupBox("Ausgabe")
        output_layout = QFormLayout(output_box)
        self.output_dir_edit = QLineEdit()
        browse = QPushButton("Ordner wählen")
        browse.clicked.connect(self._choose_output_dir)
        choose_layout = QHBoxLayout()
        choose_layout.setContentsMargins(0, 0, 0, 0)
        choose_layout.addWidget(self.output_dir_edit)
        choose_layout.addWidget(browse)
        container = QWidget()
        container.setLayout(choose_layout)
        output_layout.addRow("Zielordner", container)
        layout.addWidget(output_box)

        control_row = QHBoxLayout()
        self.record_button = QPushButton("Aufnahme starten")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.record_button.clicked.connect(self._start_recording)
        self.stop_button.clicked.connect(self._stop_recording)
        control_row.addWidget(self.record_button)
        control_row.addWidget(self.stop_button)

        self.quality_button = QPushButton("Qualität …")
        self.quality_button.clicked.connect(self._open_quality_dialog)
        control_row.addWidget(self.quality_button)

        self.metadata_button = QPushButton("Metadaten …")
        self.metadata_button.setEnabled(False)
        self.metadata_button.clicked.connect(self._edit_metadata)
        control_row.addWidget(self.metadata_button)

        layout.addLayout(control_row)

        self.recordings = QTreeWidget()
        self.recordings.setHeaderLabels(["Datei", "Dauer", "Größe", "Zeitpunkt"])
        self.recordings.setRootIsDecorated(False)
        self.recordings.itemSelectionChanged.connect(self._on_selection_changed)
        self.recordings.itemDoubleClicked.connect(lambda *_: self._edit_metadata())
        layout.addWidget(self.recordings, stretch=1)

        self.status_label = QLabel("Keine Aufnahmen.")
        layout.addWidget(self.status_label)

    def refresh(self) -> None:
        self._loading = True
        try:
            devices = self._plugin.get_devices("input")
            selected = self._plugin.get_recorder_device()
            self.device_combo.clear()
            for device in devices:
                label = f"{device.name} ({device.host_api})"
                self.device_combo.addItem(label, device.identifier)
            if selected:
                index = self.device_combo.findData(selected)
                if index != -1:
                    self.device_combo.setCurrentIndex(index)
            if self.device_combo.count() and self.device_combo.currentIndex() == -1:
                self.device_combo.setCurrentIndex(0)
            if not selected and self.device_combo.count():
                device_id = self.device_combo.currentData()
                if isinstance(device_id, str):
                    self._plugin.set_recorder_device(device_id)
            self.output_dir_edit.setText(self._plugin.get_output_directory())
            self._update_quality_summary()
            self._refresh_recordings()
            self._update_controls()
        finally:
            self._loading = False

    def _on_device_changed(self) -> None:
        if self._loading:
            return
        device_id = self.device_combo.currentData()
        if isinstance(device_id, str):
            self._plugin.set_recorder_device(device_id)

    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Zielordner auswählen")
        if directory:
            self.output_dir_edit.setText(directory)
            self._plugin.set_output_directory(Path(directory))

    def _open_quality_dialog(self) -> None:
        dialog = QualityDialog(self, self._plugin.get_quality_settings())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._plugin.update_quality_settings(dialog.result_quality())
            self._update_quality_summary()

    def _update_quality_summary(self) -> None:
        quality = self._plugin.get_quality_settings()
        summary = (
            f"Qualität: {quality['sample_rate']} Hz, {quality['bit_depth']}-bit, "
            f"{quality['channels']} Kanäle"
        )
        self.status_label.setText(summary)

    def _refresh_recordings(self) -> None:
        self.recordings.clear()
        for info in self._plugin.get_recording_history():
            item = QTreeWidgetItem(
                [
                    info.get("filename", ""),
                    info.get("duration", ""),
                    info.get("size", ""),
                    info.get("timestamp", ""),
                ]
            )
            identifier = info.get("path", info.get("filename", ""))
            item.setData(0, Qt.ItemDataRole.UserRole, identifier)
            self.recordings.addTopLevelItem(item)
        self._on_selection_changed()

    def _update_controls(self) -> None:
        recording = self._plugin.is_recording()
        self.record_button.setEnabled(not recording)
        self.stop_button.setEnabled(recording)
        self.metadata_button.setEnabled(False)
        if recording:
            path = self._plugin.active_recording_path()
            name = path.name if path else "laufend"
            self.status_label.setText(f"Aufnahme läuft … ({name})")
        else:
            self._update_quality_summary()

    def _on_selection_changed(self) -> None:
        selected = self._selected_identifier()
        self.metadata_button.setEnabled(selected is not None and not self._plugin.is_recording())

    def _selected_identifier(self) -> Optional[str]:
        items = self.recordings.selectedItems()
        if not items:
            return None
        value = items[0].data(0, Qt.ItemDataRole.UserRole)
        return str(value) if isinstance(value, str) and value else None

    def _edit_metadata(self) -> None:
        identifier = self._selected_identifier()
        if not identifier:
            return
        metadata = self._plugin.get_recording_metadata(identifier)
        dialog = MetadataDialog(self, metadata)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = dialog.result_metadata()
        self._plugin.update_recording_metadata(identifier, result)
        self._refresh_recordings()

    def _start_recording(self) -> None:
        if self._plugin.is_recording():
            return
        try:
            self._plugin.start_recording()
        except RecordingError as exc:
            QMessageBox.warning(self, "Aufnahme fehlgeschlagen", str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive UI feedback
            QMessageBox.critical(self, "Unerwarteter Fehler", str(exc))
            return
        self._update_controls()

    def _stop_recording(self) -> None:
        if not self._plugin.is_recording():
            return
        try:
            entry = self._plugin.stop_recording()
        except RecordingError as exc:
            QMessageBox.warning(self, "Stop fehlgeschlagen", str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive UI feedback
            QMessageBox.critical(self, "Unerwarteter Fehler", str(exc))
            return
        self._update_controls()
        self.status_label.setText(
            f"Gespeichert: {entry['filename']} ({entry['duration']}, {entry['size']})"
        )
        self._refresh_recordings()
        identifier = entry.get("path", entry.get("filename"))
        if identifier:
            self._select_identifier(identifier)
            self._edit_metadata()

    def _select_identifier(self, identifier: str) -> None:
        for row in range(self.recordings.topLevelItemCount()):
            item = self.recordings.topLevelItem(row)
            if item is None:
                continue
            value = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(value, str) and value == identifier:
                self.recordings.setCurrentItem(item)
                return


class AudioToolsWidget(QWidget):
    def __init__(self, plugin: "AudioToolsPlugin") -> None:
        super().__init__()
        self._plugin = plugin
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        self.equalizer_tabs = QTabWidget()
        self.eq_output = EqualizerPanel(plugin, "output")
        self.eq_input = EqualizerPanel(plugin, "input")
        self.equalizer_tabs.addTab(self.eq_output, "Ausgabe")
        self.equalizer_tabs.addTab(self.eq_input, "Eingabe")
        self.tabs.addTab(self.equalizer_tabs, "Equalizer")

        self.recorder_panel = RecorderPanel(plugin)
        self.tabs.addTab(self.recorder_panel, "Recorder")

    def refresh_devices(self) -> None:
        self.eq_output.refresh_devices()
        self.eq_input.refresh_devices()
        self.recorder_panel.refresh()

    def set_enabled(self, enabled: bool) -> None:
        self.setEnabled(enabled)


class AudioToolsPlugin(BasePlugin):
    IDENTIFIER = "mmst.audio_tools"

    def __init__(self, services) -> None:
        super().__init__(services)
        self._manifest = PluginManifest(
            identifier=self.IDENTIFIER,
            name="Audio Tools",
            description="Equalizer und Recorder für Ein- und Ausgänge",
            version="0.1.0",
            author="MMST Team",
            tags=("audio", "eq", "recording"),
        )
        self._logger = self.services.get_logger("AudioTools")
        self._widget: Optional[AudioToolsWidget] = None
        self._active = False
        self._eq_state: Dict[str, Dict[str, Any]] = {}
        self._recorder_state: Dict[str, Any] = {}
        placeholder_flag = os.getenv("MMST_AUDIO_PLACEHOLDER")
        force_placeholder = placeholder_flag not in (None, "", "0", "false", "False")
        self._recording = RecordingController(
            logger=self._logger.getChild("Recording"),
            force_placeholder=force_placeholder,
        )
        self._current_recording_path: Optional[Path] = None
        self._load_state()

    # ------------------------------------------------------------------
    # BasePlugin API
    # ------------------------------------------------------------------
    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def create_view(self) -> QWidget:
        if not self._widget:
            self._widget = AudioToolsWidget(self)
            self._widget.set_enabled(self._active)
            self._widget.refresh_devices()
        return self._widget

    def initialize(self) -> None:
        recordings_dir = list(self.services.ensure_subdirectories("audio/recordings"))
        default_dir = str(recordings_dir[0]) if recordings_dir else str(self.services.data_dir)
        if not self._recorder_state.get("output_dir"):
            self._recorder_state["output_dir"] = default_dir
            self._persist_recorder_state()

    def start(self) -> None:
        self._active = True
        if self._widget:
            self._widget.set_enabled(True)
            self._widget.refresh_devices()

    def stop(self) -> None:
        self._active = False
        if self.is_recording():
            self._recording.abort()
            self._current_recording_path = None
        if self._widget:
            self._widget.set_enabled(False)

    def shutdown(self) -> None:
        if self.is_recording():
            self._recording.abort()
            self._current_recording_path = None

    # ------------------------------------------------------------------
    # Public API used by widget
    # ------------------------------------------------------------------
    def get_devices(self, bus: str) -> List[AudioDevice]:
        if bus == "output":
            return self.services.audio_devices.list_playback_devices()
        return self.services.audio_devices.list_capture_devices()

    def get_selected_device(self, bus: str) -> Optional[str]:
        bus_state = self._eq_state.get(bus, {})
        selected = bus_state.get("selected_device")
        return str(selected) if isinstance(selected, str) else None

    def set_selected_device(self, bus: str, device_id: str) -> None:
        bus_state = self._ensure_bus(bus)
        bus_state["selected_device"] = device_id
        self._persist_eq_state()

    def get_device_state(self, bus: str, device_id: str) -> Dict[str, Any]:
        device_state = deepcopy(self._ensure_device(bus, device_id))
        return device_state

    def load_preset(self, bus: str, device_id: str, preset: str) -> List[int]:
        entry = self._ensure_device(bus, device_id)
        presets = cast(Dict[str, List[int]], entry.setdefault("presets", {"Flat": list(_FLAT_VALUES)}))
        values = presets.get(preset)
        if not isinstance(values, list):
            values = list(_FLAT_VALUES)
        entry["active_preset"] = preset
        entry["values"] = list(values)
        self._persist_eq_state()
        return list(values)

    def set_active_preset(self, bus: str, device_id: str, preset: str) -> None:
        entry = self._ensure_device(bus, device_id)
        entry["active_preset"] = preset
        self._persist_eq_state()

    def save_preset(self, bus: str, device_id: str, name: str, values: List[int]) -> None:
        entry = self._ensure_device(bus, device_id)
        presets = cast(Dict[str, List[int]], entry.setdefault("presets", {"Flat": list(_FLAT_VALUES)}))
        normalized = self._normalize_values(values)
        presets[name] = normalized
        entry["active_preset"] = name
        entry["values"] = list(normalized)
        self._persist_eq_state()

    def delete_preset(self, bus: str, device_id: str, name: str) -> None:
        entry = self._ensure_device(bus, device_id)
        presets = cast(Dict[str, List[int]], entry.setdefault("presets", {"Flat": list(_FLAT_VALUES)}))
        if len(presets) <= 1:
            raise ValueError("Mindestens ein Preset wird benötigt")
        if name not in presets:
            raise ValueError("Preset existiert nicht")
        del presets[name]
        new_active = next(iter(presets.keys()))
        entry["active_preset"] = new_active
        entry["values"] = list(presets[new_active])
        self._persist_eq_state()

    def update_device_values(self, bus: str, device_id: str, values: List[int]) -> None:
        entry = self._ensure_device(bus, device_id)
        entry["values"] = self._normalize_values(values)
        self._persist_eq_state()

    def get_recorder_device(self) -> Optional[str]:
        value = self._recorder_state.get("selected_device")
        return str(value) if isinstance(value, str) else None

    def set_recorder_device(self, device_id: str) -> None:
        self._recorder_state["selected_device"] = device_id
        self._persist_recorder_state()

    def get_output_directory(self) -> str:
        value = self._recorder_state.get("output_dir")
        if isinstance(value, str) and value:
            return value
        return str(self.services.data_dir)

    def set_output_directory(self, directory: Path) -> None:
        self._recorder_state["output_dir"] = str(directory)
        self._persist_recorder_state()

    def get_quality_settings(self) -> Dict[str, int]:
        quality = self._recorder_state.get("quality")
        if not isinstance(quality, dict):
            quality = self._default_quality()
            self._recorder_state["quality"] = quality
        return dict(quality)  # copy

    def update_quality_settings(self, values: Dict[str, int]) -> None:
        quality_any = self._recorder_state.setdefault("quality", self._default_quality())
        if not isinstance(quality_any, dict):
            quality_any = self._default_quality()
            self._recorder_state["quality"] = quality_any
        quality = cast(Dict[str, int], quality_any)
        quality.update({
            "sample_rate": int(values.get("sample_rate", 48000)),
            "bit_depth": int(values.get("bit_depth", 24)),
            "channels": int(values.get("channels", 2)),
        })
        self._persist_recorder_state()

    def get_recording_history(self) -> List[Dict[str, Any]]:
        records = []
        metadata_store = self._ensure_metadata_store()
        for entry in self._history_records():
            record = dict(entry)
            path = record.get("path")
            if isinstance(path, str) and path in metadata_store:
                record["metadata"] = dict(metadata_store[path])
            elif not isinstance(record.get("metadata"), dict):
                record["metadata"] = {}
            records.append(record)
        return records

    def is_recording(self) -> bool:
        return self._recording.is_recording()

    def get_recording_metadata(self, identifier: str) -> Dict[str, str]:
        path = self._resolve_identifier_to_path(identifier)
        if not path:
            return {}
        metadata_store = self._ensure_metadata_store()
        existing = metadata_store.get(path)
        if isinstance(existing, dict):
            return {k: str(v) for k, v in existing.items() if isinstance(k, str)}
        for entry in self._history_records():
            if entry.get("path") == path:
                metadata_obj = entry.get("metadata")
                if isinstance(metadata_obj, dict):
                    return {k: str(v) for k, v in metadata_obj.items() if isinstance(k, str)}
        return {}

    def update_recording_metadata(self, identifier: str, metadata: Dict[str, str]) -> None:
        path = self._resolve_identifier_to_path(identifier)
        if not path:
            return
        sanitized = self._sanitize_metadata(metadata)
        metadata_store = self._ensure_metadata_store()
        metadata_store[path] = sanitized
        self._update_history_metadata(path, sanitized)
        self._write_metadata_to_file(Path(path), sanitized)
        self._persist_recorder_state()

    def start_recording(self) -> Path:
        device_id = self.get_recorder_device()
        if not device_id:
            raise RecordingError("Es ist kein Aufnahmegerät ausgewählt")
        output_dir = Path(self.get_output_directory())
        quality = self.get_quality_settings()
        path = self._recording.start(output_dir, device_id, quality)
        self._current_recording_path = path
        return path

    def stop_recording(self) -> Dict[str, Any]:
        info = self._recording.stop()
        path = cast(Path, info.get("path"))
        if not isinstance(path, Path):
            raise RecordingError("Aufnahme konnte nicht gespeichert werden")
        size_value = info.get("size_bytes", 0)
        if isinstance(size_value, (int, float)):
            size_bytes = int(size_value)
        elif isinstance(size_value, str):
            try:
                size_bytes = int(float(size_value))
            except ValueError:
                size_bytes = 0
        else:
            size_bytes = 0

        duration_value = info.get("duration_seconds", 0.0)
        if isinstance(duration_value, (int, float)):
            duration_seconds = float(duration_value)
        elif isinstance(duration_value, str):
            try:
                duration_seconds = float(duration_value)
            except ValueError:
                duration_seconds = 0.0
        else:
            duration_seconds = 0.0
        path_str = str(path)
        metadata_store = self._ensure_metadata_store()
        existing_metadata = metadata_store.get(path_str)
        if not isinstance(existing_metadata, dict):
            existing_metadata = {}
            metadata_store[path_str] = existing_metadata
        entry = {
            "filename": path.name,
            "duration": _format_duration(duration_seconds),
            "size": _format_filesize(size_bytes),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "path": path_str,
            "metadata": dict(existing_metadata),
        }
        history = self._recorder_state.setdefault("history", [])
        history.insert(0, entry)
        del history[50:]
        self._persist_recorder_state()
        self._current_recording_path = None
        return entry

    def active_recording_path(self) -> Optional[Path]:
        return self._current_recording_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_metadata_store(self) -> Dict[str, Dict[str, str]]:
        store_obj = self._recorder_state.setdefault("metadata", {})
        if not isinstance(store_obj, dict):
            store_obj = {}
            self._recorder_state["metadata"] = store_obj
        store: Dict[str, Dict[str, str]] = {}
        for key, value in store_obj.items():
            if isinstance(key, str) and isinstance(value, dict):
                store[key] = self._sanitize_metadata(value)
        self._recorder_state["metadata"] = store
        return store

    def _history_records(self) -> List[Dict[str, Any]]:
        history_obj = self._recorder_state.get("history")
        records: List[Dict[str, Any]] = []
        if isinstance(history_obj, list):
            for item in history_obj:
                if not isinstance(item, dict):
                    continue
                record: Dict[str, Any] = dict(item)
                filename = record.get("filename")
                if not isinstance(filename, str):
                    continue
                record["filename"] = filename
                path = record.get("path")
                if isinstance(path, str) and path:
                    record["path"] = path
                else:
                    record["path"] = filename
                metadata = record.get("metadata")
                if isinstance(metadata, dict):
                    record["metadata"] = self._sanitize_metadata(metadata)
                else:
                    record["metadata"] = {}
                records.append(record)
        return records

    def _resolve_identifier_to_path(self, identifier: str) -> Optional[str]:
        if not identifier:
            return None
        identifier = identifier.strip()
        if not identifier:
            return None
        candidate = Path(identifier)
        if candidate.is_absolute():
            return str(candidate)
        store = self._ensure_metadata_store()
        if identifier in store:
            return identifier
        for entry in self._history_records():
            path = entry.get("path")
            if isinstance(path, str) and path:
                if path == identifier:
                    return path
                if entry.get("filename") == identifier:
                    return path
        potential = Path(self.get_output_directory()) / identifier
        return str(potential)

    def _update_history_metadata(self, path: str, metadata: Dict[str, str]) -> None:
        history_obj = self._recorder_state.setdefault("history", [])
        if not isinstance(history_obj, list):
            history_obj = []
            self._recorder_state["history"] = history_obj
        found = False
        for item in history_obj:
            if not isinstance(item, dict):
                continue
            item_path = item.get("path")
            if item_path == path or (not isinstance(item_path, str) and item.get("filename") == Path(path).name):
                item["path"] = path
                item["metadata"] = dict(metadata)
                found = True
        if not found:
            history_obj.insert(
                0,
                {
                    "filename": Path(path).name,
                    "duration": "",
                    "size": "",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "path": path,
                    "metadata": dict(metadata),
                },
            )
            del history_obj[50:]

    @staticmethod
    def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, str]:
        sanitized: Dict[str, str] = {}
        for key in ("title", "artist", "album", "genre", "comment"):
            value = metadata.get(key) if isinstance(metadata, dict) else None
            if isinstance(value, str):
                sanitized[key] = value.strip()
            else:
                sanitized[key] = ""
        return sanitized

    def _write_metadata_to_file(self, path: Path, metadata: Dict[str, str]) -> None:
        if not path.exists():
            return
        if WAVE is None or TIT2 is None or TPE1 is None or TALB is None or TCON is None:
            self._logger.debug("Mutagen nicht verfügbar, Metadaten werden nur intern gespeichert")
            return
        try:
            audio = WAVE(str(path))
        except MutagenError as exc:  # pragma: no cover - dependency runtime issues
            self._logger.warning("Metadaten konnten nicht gelesen werden: %s", exc)
            return
        try:
            tags = audio.tags
        except ID3NoHeaderError:  # pragma: no cover - mutagen specific
            audio.add_tags()
            tags = audio.tags
        if tags is None:
            if ID3 is not None:
                tags = ID3()
                audio.tags = tags
            else:
                return
        try:
            tags.delall("TIT2")
            tags.delall("TPE1")
            tags.delall("TALB")
            tags.delall("TCON")
            tags.delall("COMM")
            title = metadata.get("title", "")
            artist = metadata.get("artist", "")
            album = metadata.get("album", "")
            genre = metadata.get("genre", "")
            comment = metadata.get("comment", "")
            if title:
                tags.add(TIT2(encoding=3, text=title))
            if artist:
                tags.add(TPE1(encoding=3, text=artist))
            if album:
                tags.add(TALB(encoding=3, text=album))
            if genre:
                tags.add(TCON(encoding=3, text=genre))
            if comment and COMM is not None:
                tags.add(COMM(encoding=3, lang="eng", desc="", text=comment))
            audio.save()
        except MutagenError as exc:  # pragma: no cover - dependency runtime issues
            self._logger.warning("Metadaten konnten nicht geschrieben werden: %s", exc)

    def _load_state(self) -> None:
        raw_eq = self.config.get("equalizer", {})
        if not isinstance(raw_eq, dict):
            raw_eq = {}
        self._eq_state = {
            "output": self._normalize_bus(raw_eq.get("output")),
            "input": self._normalize_bus(raw_eq.get("input")),
        }
        self._persist_eq_state()

        raw_recorder = self.config.get("recorder", {})
        if not isinstance(raw_recorder, dict):
            raw_recorder = {}
        self._recorder_state = self._normalize_recorder(raw_recorder)
        self._persist_recorder_state()

    def _persist_eq_state(self) -> None:
        self.config["equalizer"] = deepcopy(self._eq_state)

    def _persist_recorder_state(self) -> None:
        self.config["recorder"] = deepcopy(self._recorder_state)

    def _ensure_bus(self, bus: str) -> Dict[str, Any]:
        if bus not in self._eq_state:
            self._eq_state[bus] = self._default_bus()
        bus_state = self._eq_state[bus]
        if "devices" not in bus_state:
            bus_state["devices"] = {}
        return bus_state

    def _ensure_device(self, bus: str, device_id: str) -> Dict[str, Any]:
        bus_state = self._ensure_bus(bus)
        devices_obj = bus_state.setdefault("devices", {})
        if not isinstance(devices_obj, dict):
            devices_obj = {}
            bus_state["devices"] = devices_obj
        devices = cast(Dict[str, Dict[str, Any]], devices_obj)
        entry = devices.get(device_id)
        if not isinstance(entry, dict):
            entry = self._default_device()
            devices[device_id] = entry
        presets_obj = entry.get("presets")
        if not isinstance(presets_obj, dict):
            presets_obj = {"Flat": list(_FLAT_VALUES)}
            entry["presets"] = presets_obj
        presets = cast(Dict[str, List[int]], presets_obj)
        active = entry.get("active_preset")
        if not isinstance(active, str) or active not in presets:
            entry["active_preset"] = next(iter(presets.keys()))
        values_obj = entry.get("values")
        if not isinstance(values_obj, list):
            entry["values"] = list(presets[entry["active_preset"]])
        return entry

    @staticmethod
    def _normalize_values(values: List[int]) -> List[int]:
        normalized: List[int] = []
        for value in list(values)[: len(_FLAT_VALUES)]:
            try:
                normalized.append(int(value))
            except (TypeError, ValueError):
                normalized.append(0)
        while len(normalized) < len(_FLAT_VALUES):
            normalized.append(0)
        return normalized

    def _normalize_bus(self, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        bus = self._default_bus()
        if not isinstance(data, dict):
            return bus
        selected = data.get("selected_device")
        if isinstance(selected, str):
            bus["selected_device"] = selected
        devices = data.get("devices")
        if isinstance(devices, dict):
            normalized_devices = {}
            for device_id, entry in devices.items():
                if not isinstance(device_id, str):
                    continue
                normalized_devices[device_id] = self._normalize_device(entry)
            bus["devices"] = normalized_devices
        return bus

    def _normalize_device(self, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        entry = self._default_device()
        if not isinstance(data, dict):
            return entry
        presets = data.get("presets")
        normalized_presets: Dict[str, List[int]] = {}
        if isinstance(presets, dict):
            for name, values in presets.items():
                if isinstance(name, str):
                    normalized_presets[name] = self._normalize_values(values if isinstance(values, list) else [])
        if not normalized_presets:
            normalized_presets = {"Flat": list(_FLAT_VALUES)}
        entry["presets"] = normalized_presets

        active = data.get("active_preset")
        if isinstance(active, str) and active in normalized_presets:
            entry["active_preset"] = active
        else:
            entry["active_preset"] = next(iter(normalized_presets.keys()))

        values = data.get("values")
        entry["values"] = self._normalize_values(values if isinstance(values, list) else list(normalized_presets[entry["active_preset"]]))
        return entry

    def _normalize_recorder(self, data: Dict[str, Any]) -> Dict[str, Any]:
        recorder = {
            "selected_device": None,
            "output_dir": "",
            "quality": self._default_quality(),
            "history": [],
            "metadata": {},
        }
        if not isinstance(data, dict):
            return recorder
        device = data.get("selected_device")
        if isinstance(device, str):
            recorder["selected_device"] = device
        output_dir = data.get("output_dir")
        if isinstance(output_dir, str):
            recorder["output_dir"] = output_dir
        quality = data.get("quality")
        if isinstance(quality, dict):
            recorder["quality"] = {
                "sample_rate": int(quality.get("sample_rate", 48000)),
                "bit_depth": int(quality.get("bit_depth", 24)),
                "channels": int(quality.get("channels", 2)),
            }
        history = data.get("history")
        if isinstance(history, list):
            normalized_history: List[Dict[str, Any]] = []
            for item in history:
                if not isinstance(item, dict):
                    continue
                entry: Dict[str, Any] = dict(item)
                filename = entry.get("filename")
                if not isinstance(filename, str):
                    continue
                path = entry.get("path")
                if isinstance(path, str):
                    entry["path"] = path
                else:
                    entry["path"] = filename
                metadata = entry.get("metadata")
                if isinstance(metadata, dict):
                    entry["metadata"] = self._sanitize_metadata(metadata)
                else:
                    entry["metadata"] = {}
                normalized_history.append(entry)
            recorder["history"] = normalized_history
        metadata_store = data.get("metadata")
        if isinstance(metadata_store, dict):
            normalized: Dict[str, Dict[str, str]] = {}
            for key, value in metadata_store.items():
                if isinstance(key, str) and isinstance(value, dict):
                    normalized[key] = self._sanitize_metadata(value)
            recorder["metadata"] = normalized
        return recorder

    @staticmethod
    def _default_bus() -> Dict[str, Any]:
        return {
            "selected_device": None,
            "devices": {},
        }

    @staticmethod
    def _default_device() -> Dict[str, Any]:
        return {
            "active_preset": "Flat",
            "presets": {"Flat": list(_FLAT_VALUES)},
            "values": list(_FLAT_VALUES),
        }

    @staticmethod
    def _default_quality() -> Dict[str, int]:
        return {"sample_rate": 48000, "bit_depth": 24, "channels": 2}


Plugin = AudioToolsPlugin
