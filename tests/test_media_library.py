from pathlib import Path

from mmst.plugins.media_library.core import LibraryIndex, scan_source


def test_scan_source_indexes_files(tmp_path: Path) -> None:
    root = tmp_path / "lib"
    (root / "a").mkdir(parents=True)
    (root / "a" / "one.mp3").write_text("x")
    (root / "two.jpg").write_text("y")

    db = tmp_path / "db.sqlite"
    index = LibraryIndex(db)
    try:
        count = scan_source(root, index)
        assert count == 2
        files = index.list_files()
        paths = {f.path for f in files}
        assert "a/one.mp3" in paths or "a\\one.mp3" in paths
        assert "two.jpg" in paths
    finally:
        index.close()


def test_list_files_with_sources_includes_source_paths(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    (root / "song.flac").write_text("data")

    db = tmp_path / "db.sqlite"
    index = LibraryIndex(db)
    try:
        scan_source(root, index)
        detailed = index.list_files_with_sources()
        assert detailed, "Expected at least one indexed file"
        media, source_path = detailed[0]
        assert source_path == root
        abs_path = source_path / media.path
        assert abs_path.exists()
    finally:
        index.close()
