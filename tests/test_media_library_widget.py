"""UI-side tests for MediaLibrary widget filtering and detail view."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, cast

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

    widget = MediaLibraryWidget(cast(Any, DummyPlugin(entries)))

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

    widget._refresh_library_views()

    # Initial population selects first entry and populates detail panel
    assert [media.path for media, _ in widget._entries] == [audio_rel, video_rel]
    assert widget.detail_heading.text() == "Orchestral Opening"
    assert widget._detail_field_labels["artist"].text() == "Test Artist"
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