import types
from pathlib import Path

from mmst.plugins.media_library.stats import compute_stats
from mmst.plugins.media_library.models import MediaFile, MediaMetadata


def dummy_metadata(duration=None, rating=None, tags=None):
    md = MediaMetadata()
    md.duration = duration
    md.rating = rating
    md.tags = tags or []
    return md


def test_compute_stats_basic(tmp_path: Path):
    # Arrange: create fake files
    a = tmp_path / "a.mp3"
    v = tmp_path / "b.mp4"
    i = tmp_path / "c.jpg"
    d = tmp_path / "d.pdf"
    for f, size in ((a, 1000), (v, 2000), (i, 500), (d, 300)):
        f.write_bytes(b"x" * size)

    entries = [
        (MediaFile(path=a.name, kind="audio"), tmp_path),
        (MediaFile(path=v.name, kind="video"), tmp_path),
        (MediaFile(path=i.name, kind="image"), tmp_path),
        (MediaFile(path=d.name, kind="doc"), tmp_path),
    ]

    meta_map = {
        a: dummy_metadata(duration=120, rating=4, tags=["fav", "music"]),
        v: dummy_metadata(duration=60, rating=5, tags=["fav", "clip"]),
        i: dummy_metadata(duration=None, rating=None, tags=["pic"]),
        d: dummy_metadata(duration=None, rating=None, tags=[]),
    }

    def metadata_loader(p: Path):
        return meta_map.get(p)

    attr_map = {
        a: (4, ("fav", "music")),
        v: (5, ("fav", "clip")),
        i: (None, ("pic",)),
        d: (None, tuple()),
    }

    def attribute_loader(p: Path):
        return attr_map.get(p, (None, tuple()))

    # Act
    stats = compute_stats(entries, metadata_loader, attribute_loader)

    # Assert
    assert stats.total_files == 4
    assert stats.kinds.get("audio") == 1
    assert stats.kinds.get("video") == 1
    assert stats.kinds.get("image") == 1
    assert stats.kinds.get("doc") == 1
    assert stats.total_size == 1000 + 2000 + 500 + 300
    assert int(stats.total_duration) == 180  # 120 + 60
    # Average rating (4 + 5) / 2
    assert abs(stats.average_rating - 4.5) < 0.001
    # Tag frequency: fav=2, music=1, clip=1, pic=1
    assert stats.tag_frequency["fav"] == 2
    assert stats.tag_frequency["music"] == 1
    assert stats.tag_frequency["clip"] == 1
    assert stats.tag_frequency["pic"] == 1
