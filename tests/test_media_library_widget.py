"""UI-side tests for MediaLibrary widget filtering and detail view."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast

import pytest
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from mmst.plugins.media_library.core import MediaFile
from mmst.plugins.media_library.metadata import MediaMetadata
from mmst.plugins.media_library.plugin import MediaLibraryWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


class DummyPlugin:
    def __init__(self, entries):
        self._entries = entries
        self.watch_available = True
        self.watch_enabled = False
        self.is_watching = False
        self._pixmap = QPixmap(32, 32)
        self._pixmap.fill(QColor("gray"))
        self.custom_presets: Dict[str, Dict[str, Any]] = {}
        self.attributes: Dict[str, Tuple[Any, List[str]]] = {}
        self.rating_calls: List[Tuple[Path, Any]] = []
        self.tags_calls: List[Tuple[Path, Tuple[str, ...]]] = []
        self.external_players: Dict[str, Dict[str, str]] = {}
        self.external_player_calls: List[Path] = []
        self.view_state: Dict[str, Any] = {}

    def list_recent_detailed(self):
        return list(self._entries)

    def cover_pixmap(self, path: Path, kind: str) -> QPixmap:
        return self._pixmap

    def list_sources(self):
        return []

    def add_source(self, path: Path) -> None:  # pragma: no cover - not used in test
        return None

    def remove_source(self, path: Path) -> None:  # pragma: no cover - not used in test
        return None

    def enable_watching(self, enabled: bool) -> None:
        self.watch_enabled = enabled

    def watched_sources_count(self) -> int:
        return 0

    # new helper APIs -------------------------------------------------

    def load_custom_presets(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.custom_presets)

    def save_custom_presets(self, presets: Dict[str, Dict[str, Any]]) -> None:
        self.custom_presets = dict(presets)

    def load_view_state(self) -> Dict[str, Any]:
        return dict(self.view_state)

    def save_view_state(self, state: Dict[str, Any]) -> None:
        self.view_state = dict(state)

    def set_rating(self, path: Path, rating: Any) -> None:
        self.rating_calls.append((Path(path), rating))
        current = self.attributes.get(str(path), (None, []))
        self.attributes[str(path)] = (rating, list(current[1]))

    def set_tags(self, path: Path, tags: List[str]) -> None:
        self.tags_calls.append((Path(path), tuple(tags)))
        current = self.attributes.get(str(path), (None, []))
        self.attributes[str(path)] = (current[0], list(tags))

    def get_file_attributes(self, path: Path) -> Tuple[Any, Tuple[str, ...]]:
        rating, tags = self.attributes.get(str(path), (None, []))
        return rating, tuple(tags)

    def invalidate_cover(self, path: Path) -> None:
        self.attributes.setdefault("_invalidated", ([], []))

    def refresh_metadata(self, path: Path) -> bool:
        return True

    def resolve_external_player(self, path: Path) -> Dict[str, str] | None:
        return self.external_players.get(path.suffix.lstrip("."))

    def set_external_player(self, extension: str, label: str, command: str) -> None:
        self.external_players[extension] = {"label": label, "command": command}

    def remove_external_player(self, extension: str) -> None:
        self.external_players.pop(extension, None)

    def open_with_external_player(self, path: Path) -> bool:
        self.external_player_calls.append(Path(path))
        return True


class StubMetadataReader:
    def __init__(self, metadata_map: Dict[str, MediaMetadata]) -> None:
        self.metadata_map = metadata_map
        self.calls: Dict[str, int] = {}

    def read(self, path: Path) -> MediaMetadata:
        key = str(path)
        self.calls[key] = self.calls.get(key, 0) + 1
        return self.metadata_map.get(key, MediaMetadata(title=Path(key).stem))


def test_media_library_filters_and_detail_view(qt_app: QApplication, tmp_path: Path) -> None:
    source = tmp_path / "library"
    source.mkdir()

    audio_rel = "audio/song.mp3"
    video_rel = "video/movie.mkv"
    entries = [
        (MediaFile(path=audio_rel, size=2048, mtime=1_000.0, kind="audio"), source),
        (MediaFile(path=video_rel, size=4096, mtime=2_000.0, kind="video"), source),
    ]

    plugin = DummyPlugin(entries)
    plugin.custom_presets = {"cinema": {"label": "Kino", "kind": "video", "sort": "mtime_desc"}}

    widget = MediaLibraryWidget(cast(Any, plugin))

    audio_abs = (source / Path(audio_rel)).resolve(strict=False)
    video_abs = (source / Path(video_rel)).resolve(strict=False)

    metadata_map = {
        str(audio_abs): MediaMetadata(
            title="Orchestral Opening",
            artist="Test Artist",
            album="Live Album",
            genre="Classical",
            comment="Recorded live",
            rating=5,
        ),
        str(video_abs): MediaMetadata(
            title="Sample Movie",
            genre="Drama",
        ),
    }
    stub_reader = StubMetadataReader(metadata_map)
    widget._metadata_reader = cast(Any, stub_reader)
    plugin.attributes[str(audio_abs)] = (5, ["orchestral"])

    widget._refresh_library_views()

    assert widget.view_combo.findData("custom:cinema") >= 0

    # Initial population selects first entry and populates detail panel
    assert [media.path for media, _ in widget._entries] == [audio_rel, video_rel]
    assert widget.detail_heading.text() == "Orchestral Opening"
    assert widget._detail_field_labels["artist"].text() == "Test Artist"
    assert widget._rating_bar is not None and widget._rating_bar.rating() == 5
    assert stub_reader.calls[str(audio_abs)] == 1
    assert stub_reader.calls.get(str(video_abs), 0) == 0

    # Kind filter reduces to video items and updates detail view
    video_index = widget.kind_combo.findData("video")
    widget._on_kind_changed(video_index)
    assert len(widget._entries) == 1
    assert widget._entries[0][0].path == video_rel
    assert widget.detail_heading.text() == "Sample Movie"
    assert stub_reader.calls[str(video_abs)] == 1

    # Reset and use metadata-backed text search (no extra read for cached audio metadata)
    widget._reset_filters()
    row = widget._row_by_path[str(audio_abs)]
    widget.table.selectRow(row)
    widget._current_metadata_path = audio_abs
    widget._on_search_text_changed("orchestral")
    assert len(widget._entries) == 1
    assert widget._entries[0][0].path == audio_rel
    assert stub_reader.calls[str(audio_abs)] == 1  # cached result reused

    # Search for movie twice, ensure metadata reader is only used once for video entry
    widget._on_search_text_changed("movie")
    assert len(widget._entries) == 1
    assert widget._entries[0][0].path == video_rel
    assert stub_reader.calls[str(video_abs)] == 1

    widget._on_search_text_changed("movie")
    assert stub_reader.calls[str(video_abs)] == 1

    # Inline rating/tags propagate through plugin helpers
    widget._reset_filters()
    row = widget._row_by_path[str(audio_abs)]
    widget.table.selectRow(row)
    widget._set_current_path(str(audio_abs), source="table")
    assert widget._current_metadata_path == audio_abs

    widget._on_rating_changed(3)
    assert plugin.rating_calls and plugin.rating_calls[-1] == (audio_abs, 3)

    widget._on_tags_changed(["Live", "Highlight"])
    assert plugin.tags_calls and plugin.tags_calls[-1] == (audio_abs, ("Live", "Highlight"))

    widget.table.selectRow(0)
    if widget.gallery.count():
        widget.gallery.setCurrentRow(0)
    widget._update_batch_button_state()
    selected_paths = {path for path in widget._selected_paths()}
    assert audio_abs in selected_paths
    assert widget.batch_button.isEnabled()

    widget.tabs.setCurrentIndex(2)
    state = plugin.view_state
    assert state.get("selected_path") == str(audio_abs)
    filters_state = cast(Dict[str, Any], state.get("filters", {}))
    assert filters_state.get("text") == ""
    assert filters_state.get("preset") == "recent"
    assert state.get("active_tab") == 2