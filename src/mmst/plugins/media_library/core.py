from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class MediaFile:
    path: str
    size: int
    mtime: float
    kind: str


class LibraryIndex:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                path TEXT NOT NULL,
                size INTEGER NOT NULL,
                mtime REAL NOT NULL,
                kind TEXT NOT NULL,
                UNIQUE(source_id, path),
                FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
            );
            """
        )
        self._conn.commit()

    def add_source(self, path: Path) -> int:
        cur = self._conn.cursor()
        cur.execute("INSERT OR IGNORE INTO sources(path) VALUES (?)", (str(path),))
        self._conn.commit()
        cur.execute("SELECT id FROM sources WHERE path=?", (str(path),))
        row = cur.fetchone()
        return int(row[0]) if row else -1

    def remove_source(self, path: Path) -> None:
        self._conn.execute("DELETE FROM sources WHERE path=?", (str(path),))
        self._conn.commit()

    def list_sources(self) -> List[Tuple[int, str]]:
        cur = self._conn.cursor()
        cur.execute("SELECT id, path FROM sources ORDER BY id")
        return [(int(r[0]), str(r[1])) for r in cur.fetchall()]

    def upsert_file(self, source_id: int, rel_path: str, meta: MediaFile) -> None:
        self._conn.execute(
            """
            INSERT INTO files(source_id, path, size, mtime, kind)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_id, path) DO UPDATE SET
              size=excluded.size,
              mtime=excluded.mtime,
              kind=excluded.kind
            """,
            (source_id, rel_path, meta.size, meta.mtime, meta.kind),
        )
        self._conn.commit()

    def list_files(self, limit: int = 100) -> List[MediaFile]:
        cur = self._conn.cursor()
        cur.execute("SELECT path, size, mtime, kind FROM files ORDER BY id DESC LIMIT ?", (limit,))
        return [MediaFile(path=str(r[0]), size=int(r[1]), mtime=float(r[2]), kind=str(r[3])) for r in cur.fetchall()]


def infer_kind(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext in {"mp3", "wav", "flac", "aac", "m4a", "ogg"}:
        return "audio"
    if ext in {"mp4", "mkv", "mov", "avi", "webm"}:
        return "video"
    if ext in {"jpg", "jpeg", "png", "gif", "webp", "bmp"}:
        return "image"
    if ext in {"pdf", "epub", "mobi"}:
        return "doc"
    return "other"


def scan_source(
    root: Path,
    index: LibraryIndex,
    progress: Optional[Callable[[str, int, int], None]] = None,
) -> int:
    if not root.exists() or not root.is_dir():
        raise ValueError("Ungültige Bibliotheksquelle")
    source_id = index.add_source(root)
    total = 0
    for _, _, files in os.walk(root):
        total += len(files)
    processed = 0
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            full = Path(dirpath) / filename
            try:
                stat = full.stat()
                rel = str(full.relative_to(root))
                meta = MediaFile(path=rel, size=int(stat.st_size), mtime=float(stat.st_mtime), kind=infer_kind(full))
                index.upsert_file(source_id, rel, meta)
            except Exception:
                # skip unreadable entries but continue
                pass
            processed += 1
            if progress:
                try:
                    progress(str(full), processed, total)
                except Exception:
                    pass
    return processed
