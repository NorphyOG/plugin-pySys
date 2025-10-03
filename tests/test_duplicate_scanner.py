from pathlib import Path

import pytest  # type: ignore[import-not-found]

from mmst.plugins.file_manager.scanner import DuplicateScanner


def test_scanner_finds_duplicate_groups(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    (root / "a.txt").write_text("hello world")
    (root / "b.txt").write_text("hello world")
    (root / "c.txt").write_text("unique")

    scanner = DuplicateScanner()
    groups = scanner.scan(root)

    assert len(groups) == 1
    group = groups[0]
    checksums = {entry.checksum for entry in group.entries}
    assert len(group.entries) == 2
    assert len(checksums) == 1
    paths = sorted(entry.path.name for entry in group.entries)
    assert paths == ["a.txt", "b.txt"]


def test_scanner_invalid_directory(tmp_path: Path) -> None:
    scanner = DuplicateScanner()
    with pytest.raises(ValueError):
        scanner.scan(tmp_path / "missing")
