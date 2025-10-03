from __future__ import annotations

from pathlib import Path

from mmst.plugins.media_library.core import LibraryIndex


def test_reorder_playlist_items(tmp_path: Path) -> None:
    db_path = tmp_path / "library.db"
    index = LibraryIndex(db_path)
    try:
        source = tmp_path / "media"
        source.mkdir()
        files = [
            source / "song1.mp3",
            source / "song2.mp3",
            source / "song3.mp3",
        ]
        for file in files:
            file.write_text("data")

        index.add_source(source)
        for file in files:
            assert index.add_file_by_path(file)

        playlist_id = index.create_playlist("Meine Playlist")
        assert playlist_id is not None

        for file in files:
            assert index.add_to_playlist(playlist_id, file)

        initial = index.list_playlist_items(playlist_id)
        initial_paths = [source_path / Path(media.path) for media, source_path in initial]
        assert initial_paths == files

        new_order = [files[2], files[0], files[1]]
        assert index.reorder_playlist_items(playlist_id, new_order)

        reordered = index.list_playlist_items(playlist_id)
        reordered_paths = [source_path / Path(media.path) for media, source_path in reordered]
        assert reordered_paths == new_order
    finally:
        index.close()
