"""Tests for media library cover helpers."""
from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from mmst.plugins.media_library.covers import CoverCache, load_cover_pixmap

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    """Ensure a QApplication exists for QPixmap operations."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _write_png(path: Path) -> None:
    """Write a simple 1x1 PNG to the given path."""
    pixmap = QPixmap(1, 1)
    pixmap.fill(QColor("white"))
    pixmap.save(str(path), "PNG")


def test_load_cover_placeholder_audio(qt_app: QApplication, tmp_path: Path) -> None:
    audio_file = tmp_path / "track.mp3"
    audio_file.write_bytes(b"")

    pixmap = load_cover_pixmap(audio_file, "audio", QSize(120, 120))

    assert not pixmap.isNull()
    assert pixmap.size().width() == 120
    assert pixmap.size().height() == 120
    color = pixmap.toImage().pixelColor(0, 0)
    assert color == QColor(37, 99, 235)


def test_load_cover_image_uses_file(qt_app: QApplication, tmp_path: Path) -> None:
    image_file = tmp_path / "cover.png"
    _write_png(image_file)

    pixmap = load_cover_pixmap(image_file, "image", QSize(64, 64))

    assert not pixmap.isNull()
    # Ensure image preserves aspect ratio (1x1 scaled to square)
    assert pixmap.size().width() == 64
    assert pixmap.size().height() == 64


def test_cover_cache_caches_and_invalidates(qt_app: QApplication, tmp_path: Path) -> None:
    image_file = tmp_path / "cover.png"
    _write_png(image_file)

    cache = CoverCache(size=QSize(32, 32))

    first = cache.get(image_file, "image")
    second = cache.get(image_file, "image")
    assert first.cacheKey() == second.cacheKey()

    cache.invalidate(image_file)
    third = cache.get(image_file, "image")
    assert id(third) != id(first)
    assert third.toImage().pixelColor(0, 0) == QColor("white")

    cache.clear()
    # Ensure cache can still serve after clear
    fourth = cache.get(image_file, "image")
    assert not fourth.isNull()
