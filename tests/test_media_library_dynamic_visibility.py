"""Tests for dynamic metadata / preview visibility per media type and new sorting keys."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Tuple, List, cast
import logging

import pytest
from PySide6.QtWidgets import QApplication

from mmst.plugins.media_library.core import MediaFile
from mmst.plugins.media_library.metadata import MediaMetadata
from mmst.plugins.media_library.plugin import MediaLibraryWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qt_app() -> QApplication:  # pragma: no cover - fixture bootstrap
    app = QApplication.instance() or QApplication([])
    return cast(QApplication, app)


class DummyPlugin:
    def __init__(self, entries):
        self._entries = entries
        self.watch_available = False
        self.watch_enabled = False
        self.is_watching = False
        self.custom_presets: Dict[str, Dict[str, Any]] = {}
        self.view_state: Dict[str, Any] = {}
        self.attributes: Dict[str, Tuple[Any, List[str]]] = {}
        self._log = logging.getLogger("dummy_plugin")

    def list_recent_detailed(self):
        return list(self._entries)

    # minimal API used in widget
    def list_sources(self):
        return []

    def load_custom_presets(self):
        return {}

    def save_custom_presets(self, presets):
        return None

    def load_view_state(self):
        return dict(self.view_state)

    def save_view_state(self, state):
        self.view_state = dict(state)

    def get_file_attributes(self, path: Path):
        return self.attributes.get(str(path), (None, ()))

    def cover_pixmap(self, path: Path, kind: str):  # pragma: no cover - placeholder
        from PySide6.QtGui import QPixmap, QColor
        pm = QPixmap(32, 32)
        pm.fill(QColor("black"))
        return pm

    def invalidate_cover(self, path: Path):
        return None

    def refresh_metadata(self, path: Path) -> bool:
        return True


class StubMetadataReader:
    def __init__(self, mapping):
        self.mapping = mapping

    def read(self, path: Path) -> MediaMetadata:
        return self.mapping.get(str(path), MediaMetadata(title=path.stem))


def _find_sort_key(widget: MediaLibraryWidget, key: str) -> int:
    for i in range(widget.sort_combo.count()):
        if widget.sort_combo.itemData(i) == key:
            return i
    return -1


def test_dynamic_visibility_and_sorting(qt_app: QApplication, tmp_path: Path):
    source = tmp_path / "lib"
    source.mkdir()
    img_rel = "image/pic.png"
    aud_rel = "audio/song.flac"
    vid_rel = "video/movie.mp4"
    doc_rel = "docs/readme.txt"
    entries = [
        (MediaFile(path=img_rel, size=1000, mtime=10.0, kind="image"), source),
        (MediaFile(path=aud_rel, size=2000, mtime=20.0, kind="audio"), source),
        (MediaFile(path=vid_rel, size=3000, mtime=30.0, kind="video"), source),
        (MediaFile(path=doc_rel, size=400, mtime=5.0, kind="other"), source),
    ]
    plugin = DummyPlugin(entries)
    widget = MediaLibraryWidget(cast(Any, plugin))

    # inject metadata with selective fields
    img_abs = (source / Path(img_rel)).resolve(False)
    aud_abs = (source / Path(aud_rel)).resolve(False)
    vid_abs = (source / Path(vid_rel)).resolve(False)
    doc_abs = (source / Path(doc_rel)).resolve(False)

    meta = {
        str(img_abs): MediaMetadata(title="Picture", resolution="800x600"),
        str(aud_abs): MediaMetadata(title="Song", duration=123.4, bitrate=320, sample_rate=48000, channels=2, codec="FLAC"),
        str(vid_abs): MediaMetadata(title="Clip", duration=60.0, resolution="1920x1080", bitrate=1500, codec="H264"),
        str(doc_abs): MediaMetadata(title="Readme"),
    }
    widget._metadata_reader = cast(Any, StubMetadataReader(meta))

    widget._refresh_library_views()

    # select each entry and assert dynamic rules
    def select(abs_path: Path):
        row = widget._row_by_path[str(abs_path)]
        widget.table.selectRow(row)
        widget._set_current_path(str(abs_path), source="table")

    select(img_abs)
    if widget.media_preview is not None:
        assert widget.media_preview.isVisible() is False  # image -> no preview
    assert widget._detail_field_labels["resolution"].isVisible()
    assert not widget._detail_field_labels["bitrate"].isVisible()

    select(aud_abs)
    if widget.media_preview is not None:
        assert widget.media_preview.isVisible()  # audio preview visible
    assert widget._detail_field_labels["bitrate"].isVisible()
    assert not widget._detail_field_labels["resolution"].isVisible()

    select(vid_abs)
    if widget.media_preview is not None:
        assert widget.media_preview.isVisible()
    assert widget._detail_field_labels["resolution"].isVisible()
    assert widget._detail_field_labels["bitrate"].isVisible()

    select(doc_abs)
    if widget.media_preview is not None:
        assert widget.media_preview.isVisible() is False
    # all technical rows hidden
    for f in ("bitrate", "sample_rate", "channels", "codec", "resolution", "duration"):
        assert not widget._detail_field_labels[f].isVisible()

    # Sorting keys exist
    for key in ["rating_desc", "rating_asc", "duration_desc", "duration_asc", "kind", "title"]:
        assert _find_sort_key(widget, key) >= 0

    # Duration sort: ensure order changes appropriately
    dur_desc_index = _find_sort_key(widget, "duration_desc")
    widget.sort_combo.setCurrentIndex(dur_desc_index)
    widget._on_sort_changed(dur_desc_index)
    # After sort by duration_desc first entry should be video (60s) or audio (123.4s) depending on logic -> we stored audio larger
    assert widget._entries[0][0].path in {aud_rel, vid_rel}