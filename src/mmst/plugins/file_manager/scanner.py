from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional


@dataclass
class DuplicateEntry:
    path: Path
    size: int
    checksum: str


@dataclass
class DuplicateGroup:
    checksum: str
    entries: List[DuplicateEntry]


class DuplicateScanner:
    """Identify duplicate files inside a directory by comparing size and content."""

    def __init__(self, algorithm: str = "sha256", chunk_size: int = 1 << 20) -> None:
        self.algorithm = algorithm
        self.chunk_size = chunk_size

    def scan(
        self,
        root: Path,
        progress: Optional[Callable[[Path, int, int], None]] = None,
    ) -> List[DuplicateGroup]:
        if not root.exists() or not root.is_dir():
            raise ValueError("Der ausgewählte Ordner existiert nicht oder ist kein Verzeichnis")

        files_by_size: Dict[int, List[Path]] = {}
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                filepath = Path(dirpath) / filename
                try:
                    size = filepath.stat().st_size
                except OSError:
                    continue
                files_by_size.setdefault(size, []).append(filepath)

        potential_duplicates = [paths for paths in files_by_size.values() if len(paths) > 1]
        groups: Dict[str, List[DuplicateEntry]] = {}

        total_candidates = sum(len(paths) for paths in potential_duplicates)
        processed = 0

        for paths in potential_duplicates:
            for path in paths:
                checksum = self._hash_file(path)
                groups.setdefault(checksum, []).append(
                    DuplicateEntry(path=path, size=path.stat().st_size, checksum=checksum)
                )
                processed += 1
                if progress:
                    try:
                        progress(path, processed, total_candidates)
                    except Exception:
                        continue

        duplicate_groups = [
            DuplicateGroup(checksum=checksum, entries=entries)
            for checksum, entries in groups.items()
            if len(entries) > 1
        ]
        duplicate_groups.sort(key=lambda group: (-len(group.entries), group.entries[0].size))
        return duplicate_groups

    def _hash_file(self, path: Path) -> str:
        digest = hashlib.new(self.algorithm)
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(self.chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
