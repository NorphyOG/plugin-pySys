from __future__ import annotations

from pathlib import Path

from mmst.plugins.media_library.core import LibraryIndex


def test_library_index_stores_rating_and_tags(tmp_path: Path) -> None:
    db_path = tmp_path / "library.db"
    index = LibraryIndex(db_path)
    try:
        source = tmp_path / "media"
        source.mkdir()
        media_file = source / "song.mp3"
        media_file.write_bytes(b"data")

        index.add_source(source)
        assert index.add_file_by_path(media_file)

        rating, tags = index.get_attributes(media_file)
        assert rating is None
        assert tags == tuple()

        assert index.set_rating(media_file, 4)
        assert index.set_tags(media_file, ["rock", "live"])

        rating, tags = index.get_attributes(media_file)
        assert rating == 4
        assert tags == ("rock", "live")

        entries = index.list_files_with_sources()
        assert entries[0][0].rating == 4
        assert entries[0][0].tags == ("rock", "live")

        renamed = source / "song-renamed.mp3"
        media_file.rename(renamed)
        index.move_file(media_file, renamed)
        moved_rating, moved_tags = index.get_attributes(renamed)
        assert moved_rating == 4
        assert moved_tags == ("rock", "live")

        # Clearing tags should persist
        assert index.set_tags(renamed, [])
        _, cleared_tags = index.get_attributes(renamed)
        assert cleared_tags == tuple()
    finally:
        index.close()
