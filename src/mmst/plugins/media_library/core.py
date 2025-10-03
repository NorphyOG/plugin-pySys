from __future__ import annotations

import logging
import os
import sqlite3
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MediaFile:
    path: str
    size: int
    mtime: float
    kind: str
    rating: Optional[int] = None
    tags: Tuple[str, ...] = tuple()


class LibraryIndex:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    def _ensure_schema(self) -> None:
        with self._lock:
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
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created REAL NOT NULL DEFAULT (strftime('%s','now')),
                updated REAL NOT NULL DEFAULT (strftime('%s','now'))
            );
            CREATE TABLE IF NOT EXISTS playlist_items (
                playlist_id INTEGER NOT NULL,
                source_id INTEGER NOT NULL,
                path TEXT NOT NULL,
                position INTEGER NOT NULL,
                PRIMARY KEY (playlist_id, source_id, path),
                FOREIGN KEY(playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
            );
                """
            )
            cur.execute("PRAGMA table_info(files)")
            existing_columns = {str(row[1]) for row in cur.fetchall()}
            if "rating" not in existing_columns:
                cur.execute("ALTER TABLE files ADD COLUMN rating INTEGER")
            if "tags" not in existing_columns:
                cur.execute("ALTER TABLE files ADD COLUMN tags TEXT")
            self._conn.commit()

    def add_source(self, path: Path) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("INSERT OR IGNORE INTO sources(path) VALUES (?)", (str(path),))
            self._conn.commit()
            cur.execute("SELECT id FROM sources WHERE path= ?", (str(path),))
            row = cur.fetchone()
            return int(row[0]) if row else -1

    def remove_source(self, path: Path) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM sources WHERE path= ?", (str(path),))
            self._conn.commit()

    def list_sources(self) -> List[Tuple[int, str]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT id, path FROM sources ORDER BY id")
            return [(int(r[0]), str(r[1])) for r in cur.fetchall()]

    def upsert_file(self, source_id: int, rel_path: str, meta: MediaFile) -> None:
        with self._lock:
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

    def list_files(self, limit: Optional[int] = None) -> List[MediaFile]:
        return [entry[0] for entry in self.list_files_with_sources(limit)]

    def list_files_with_sources(self, limit: Optional[int] = None) -> List[Tuple[MediaFile, Path]]:
        with self._lock:
            cur = self._conn.cursor()
            if limit is not None:
                cur.execute(
                    """
                SELECT f.path, f.size, f.mtime, f.kind, s.path, f.rating, f.tags
                FROM files AS f
                JOIN sources AS s ON s.id = f.source_id
                ORDER BY f.id DESC
                LIMIT ?
                    """,
                    (int(limit),),
                )
            else:
                cur.execute(
                    """
                SELECT f.path, f.size, f.mtime, f.kind, s.path, f.rating, f.tags
                FROM files AS f
                JOIN sources AS s ON s.id = f.source_id
                ORDER BY f.id DESC
                    """
                )
            rows = cur.fetchall()
        results: List[Tuple[MediaFile, Path]] = []
        for row in rows:
            tags_value: Tuple[str, ...] = tuple()
            if row[6]:
                try:
                    parsed = json.loads(str(row[6]))
                    if isinstance(parsed, list):
                        tags_value = tuple(str(tag) for tag in parsed if str(tag).strip())
                except json.JSONDecodeError:
                    tags_value = tuple(filter(None, str(row[6]).split(",")))
            rating_value = row[5]
            media = MediaFile(
                path=str(row[0]),
                size=int(row[1]),
                mtime=float(row[2]),
                kind=str(row[3]),
                rating=int(rating_value) if rating_value is not None else None,
                tags=tags_value,
            )
            source_path = Path(str(row[4]))
            results.append((media, source_path))
        return results

    def list_playlists(self) -> List[Tuple[int, str, int]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
            SELECT p.id, p.name, COUNT(pi.path) AS item_count
            FROM playlists AS p
            LEFT JOIN playlist_items AS pi ON pi.playlist_id = p.id
            GROUP BY p.id, p.name
            ORDER BY LOWER(p.name)
                """
            )
            rows = cur.fetchall()
        return [(int(row[0]), str(row[1]), int(row[2])) for row in rows]

    def create_playlist(self, name: str) -> Optional[int]:
        clean = name.strip()
        if not clean:
            return None
        with self._lock:
            cur = self._conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO playlists(name, created, updated) VALUES (?, strftime('%s','now'), strftime('%s','now'))",
                    (clean,),
                )
                self._conn.commit()
                row_id = cur.lastrowid
                return int(row_id) if row_id is not None else None
            except sqlite3.IntegrityError:
                return None

    def rename_playlist(self, playlist_id: int, new_name: str) -> bool:
        clean = new_name.strip()
        if not clean:
            return False
        with self._lock:
            cur = self._conn.cursor()
            try:
                cur.execute(
                    "UPDATE playlists SET name = ?, updated = strftime('%s','now') WHERE id = ?",
                    (clean, int(playlist_id)),
                )
                self._conn.commit()
                return cur.rowcount > 0
            except sqlite3.IntegrityError:
                return False

    def delete_playlist(self, playlist_id: int) -> bool:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM playlists WHERE id = ?", (int(playlist_id),))
            self._conn.commit()
            return cur.rowcount > 0

    def list_playlist_items(self, playlist_id: int) -> List[Tuple[MediaFile, Path]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
            SELECT f.path, f.size, f.mtime, f.kind, s.path, f.rating, f.tags, pi.position
            FROM playlist_items AS pi
            JOIN sources AS s ON s.id = pi.source_id
            JOIN files AS f ON f.source_id = pi.source_id AND f.path = pi.path
            WHERE pi.playlist_id = ?
            ORDER BY pi.position ASC, LOWER(f.path)
                """,
                (int(playlist_id),),
            )
            rows = cur.fetchall()
        results: List[Tuple[MediaFile, Path]] = []
        for row in rows:
            tags_value: Tuple[str, ...] = tuple()
            if row[6]:
                try:
                    parsed = json.loads(str(row[6]))
                    if isinstance(parsed, list):
                        tags_value = tuple(str(tag) for tag in parsed if str(tag).strip())
                except json.JSONDecodeError:
                    tags_value = tuple(filter(None, str(row[6]).split(",")))
            rating_value = row[5]
            media = MediaFile(
                path=str(row[0]),
                size=int(row[1]),
                mtime=float(row[2]),
                kind=str(row[3]),
                rating=int(rating_value) if rating_value is not None else None,
                tags=tags_value,
            )
            source_path = Path(str(row[4]))
            results.append((media, source_path))
        return results

    def add_to_playlist(self, playlist_id: int, file_path: Path) -> bool:
        resolved = self._resolve_source(file_path)
        if resolved is None:
            return False
        source_id, rel_path = resolved
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT 1 FROM playlists WHERE id = ?", (int(playlist_id),))
            if cur.fetchone() is None:
                return False
            cur.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM playlist_items WHERE playlist_id = ?",
                (int(playlist_id),),
            )
            row = cur.fetchone()
            position = int(row[0]) if row and row[0] is not None else 1
            cur.execute(
                """
            INSERT OR IGNORE INTO playlist_items(playlist_id, source_id, path, position)
            VALUES (?, ?, ?, ?)
                """,
                (int(playlist_id), int(source_id), str(rel_path), position),
            )
            inserted = cur.rowcount > 0
            if inserted:
                cur.execute(
                    "UPDATE playlists SET updated = strftime('%s','now') WHERE id = ?",
                    (int(playlist_id),),
                )
            self._conn.commit()
            return inserted

    def remove_from_playlist(self, playlist_id: int, file_path: Path) -> bool:
        resolved = self._resolve_source(file_path)
        if resolved is None:
            return False
        source_id, rel_path = resolved
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "DELETE FROM playlist_items WHERE playlist_id = ? AND source_id = ? AND path = ?",
                (int(playlist_id), int(source_id), str(rel_path)),
            )
            removed = cur.rowcount > 0
            if removed:
                cur.execute(
                    "UPDATE playlists SET updated = strftime('%s','now') WHERE id = ?",
                    (int(playlist_id),),
                )
            self._conn.commit()
            return removed
    
    def add_file_by_path(self, file_path: Path) -> bool:
        """Add a single file to the index by absolute path.
        
        Finds the appropriate source and adds the file.
        Returns True if successful, False otherwise.
        """
        # Find which source this file belongs to
        resolved = self._resolve_source(file_path)
        if resolved is None:
            logger.warning(f"File not in any source: {file_path}")
            return False

        source_id, rel_path = resolved
        try:
            stat = file_path.stat()
        except OSError as exc:
            logger.debug("Failed to stat %s: %s", file_path, exc)
            return False

        meta = MediaFile(
            path=rel_path,
            size=int(stat.st_size),
            mtime=float(stat.st_mtime),
            kind=infer_kind(file_path),
        )
        self.upsert_file(source_id, rel_path, meta)
        logger.debug("Added file to index: %s", file_path)
        return True
    
    def remove_file_by_path(self, file_path: Path) -> bool:
        """Remove a single file from the index by absolute path.
        
        Finds the appropriate source and removes the file.
        Returns True if successful, False otherwise.
        """
        resolved = self._resolve_source(file_path)
        if resolved is None:
            logger.warning(f"File not in any source: {file_path}")
            return False

        source_id, rel_path = resolved
        with self._lock:
            self._conn.execute(
                "DELETE FROM files WHERE source_id=? AND path=?",
                (source_id, rel_path),
            )
            self._conn.commit()
        logger.debug("Removed file from index: %s", file_path)
        return True
    
    def update_file_by_path(self, file_path: Path) -> bool:
        """Update a file's metadata in the index by absolute path.
        
        This is essentially the same as add_file_by_path (uses upsert).
        Returns True if successful, False otherwise.
        """
        return self.add_file_by_path(file_path)

    # attribute management -------------------------------------------------

    def set_rating(self, file_path: Path, rating: Optional[int]) -> bool:
        resolved = self._resolve_source(file_path)
        if resolved is None:
            logger.warning("Cannot set rating for unknown file: %s", file_path)
            return False
        source_id, rel_path = resolved
        normalized = None if rating is None else max(0, min(int(rating), 5))
        with self._lock:
            self._conn.execute(
                "UPDATE files SET rating=? WHERE source_id=? AND path=?",
                (normalized, source_id, rel_path),
            )
            self._conn.commit()
        return True

    def set_tags(self, file_path: Path, tags: Iterable[str]) -> bool:
        resolved = self._resolve_source(file_path)
        if resolved is None:
            logger.warning("Cannot set tags for unknown file: %s", file_path)
            return False
        source_id, rel_path = resolved
        cleaned = [tag.strip() for tag in tags if tag and tag.strip()]
        payload = json.dumps(cleaned, ensure_ascii=False) if cleaned else None
        with self._lock:
            self._conn.execute(
                "UPDATE files SET tags=? WHERE source_id=? AND path=?",
                (payload, source_id, rel_path),
            )
            self._conn.commit()
        return True

    def get_attributes(self, file_path: Path) -> Tuple[Optional[int], Tuple[str, ...]]:
        resolved = self._resolve_source(file_path)
        if resolved is None:
            return (None, tuple())
        source_id, rel_path = resolved
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT rating, tags FROM files WHERE source_id=? AND path=?",
                (source_id, rel_path),
            )
            row = cur.fetchone()
        if not row:
            return (None, tuple())
        rating_value = int(row[0]) if row[0] is not None else None
        tags_value: Tuple[str, ...] = tuple()
        if row[1]:
            try:
                parsed = json.loads(str(row[1]))
                if isinstance(parsed, list):
                    tags_value = tuple(str(tag) for tag in parsed if str(tag).strip())
            except json.JSONDecodeError:
                tags_value = tuple(filter(None, str(row[1]).split(",")))
        return (rating_value, tags_value)

    def move_file(self, old_path: Path, new_path: Path) -> None:
        rating, tags = self.get_attributes(old_path)
        self.remove_file_by_path(old_path)
        self.add_file_by_path(new_path)
        if rating is not None:
            self.set_rating(new_path, rating)
        if tags:
            self.set_tags(new_path, tags)

    # helpers --------------------------------------------------------------

    def _resolve_source(self, file_path: Path) -> Optional[Tuple[int, str]]:
        for source_id, source_path in self.list_sources():
            source_path_obj = Path(source_path)
            try:
                if file_path.is_relative_to(source_path_obj):
                    rel_path = str(file_path.relative_to(source_path_obj))
                    return (int(source_id), rel_path)
            except (ValueError, OSError) as exc:
                logger.debug("Failed to check source %s: %s", source_path, exc)
                continue
        return None


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
