from pathlib import Path
from typing import Callable, List

import pytest  # type: ignore[import-not-found]

from mmst.plugins.file_manager.backup import BackupResult, perform_backup


def _capture_progress(messages: List[str]) -> Callable[[str], None]:
    return messages.append


def test_perform_backup_copies_files_and_structure(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "root.txt").write_text("hello")
    (source / "nested").mkdir()
    (source / "nested" / "deep.txt").write_text("world")

    target = tmp_path / "target"
    messages: List[str] = []

    result = perform_backup(source, target, mirror=False, progress=_capture_progress(messages))

    assert (target / "root.txt").read_text() == "hello"
    assert (target / "nested" / "deep.txt").read_text() == "world"
    assert result.copied_files == 2
    assert result.skipped_files == 0
    assert result.removed_files == 0
    assert any("Kopiert" in msg for msg in messages)


def test_perform_backup_incremental_skip(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    file_path = source / "file.txt"
    file_path.write_text("v1")

    target = tmp_path / "target"

    perform_backup(source, target, mirror=False, progress=lambda *_: None)

    messages: List[str] = []
    result = perform_backup(source, target, mirror=False, progress=_capture_progress(messages))

    assert result.copied_files == 0
    assert result.skipped_files == 1
    assert any("Übersprungen" in msg for msg in messages)


def test_perform_backup_mirror_removes_orphans(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "keep.txt").write_text("stay")

    target = tmp_path / "target"
    target.mkdir()
    (target / "keep.txt").write_text("stay")
    (target / "remove.txt").write_text("obsolete")

    messages: List[str] = []
    result = perform_backup(source, target, mirror=True, progress=_capture_progress(messages))

    assert (target / "keep.txt").exists()
    assert not (target / "remove.txt").exists()
    assert result.removed_files >= 1
    assert any("Gelöscht" in msg or "Verzeichnis entfernt" in msg for msg in messages)


def test_perform_backup_validates_paths(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()

    with pytest.raises(ValueError):
        perform_backup(target, target, mirror=False, progress=lambda *_: None)

    source = tmp_path / "source"
    (tmp_path / "source_file").write_text("data")

    with pytest.raises(ValueError):
        perform_backup(tmp_path / "source_file", target, mirror=False, progress=lambda *_: None)
