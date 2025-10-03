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
