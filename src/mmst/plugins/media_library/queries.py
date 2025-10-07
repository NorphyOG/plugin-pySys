from __future__ import annotations
"""High-level query helpers for Enhanced UI shelves.

These functions intentionally return lightweight tuples (MediaFile, source_path)
consistent with list_recent_detailed() to reuse existing rendering logic.
"""
from pathlib import Path
from typing import List, Tuple, Optional

from .core import MediaFile, LibraryIndex  # type: ignore


def query_top_rated(index: LibraryIndex, limit: int = 20) -> List[Tuple[MediaFile, Path]]:
    try:
        conn = index._conn  # protected access, acceptable for internal UI helper
        cur = conn.cursor()
        # Order by rating desc (NULL last), then mtime desc as tie-breaker
        cur.execute("""
            SELECT f.path, f.size, f.mtime, f.kind, s.root
            FROM files f JOIN sources s ON f.source_id = s.id
            WHERE f.rating IS NOT NULL
            ORDER BY f.rating DESC, f.mtime DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        result: List[Tuple[MediaFile, Path]] = []
        for row in rows:
            rel_path, size, mtime, kind, root = row
            result.append((MediaFile(path=rel_path, size=size or 0, mtime=float(mtime or 0.0), kind=kind or "other"), Path(root)))
        return result
    except Exception:
        return []


def query_by_kind(index: LibraryIndex, kind: str, limit: int = 20) -> List[Tuple[MediaFile, Path]]:
    try:
        conn = index._conn
        cur = conn.cursor()
        cur.execute("""
            SELECT f.path, f.size, f.mtime, f.kind, s.root
            FROM files f JOIN sources s ON f.source_id = s.id
            WHERE f.kind = ?
            ORDER BY f.mtime DESC
            LIMIT ?
        """, (kind, limit))
        rows = cur.fetchall()
        result: List[Tuple[MediaFile, Path]] = []
        for row in rows:
            rel_path, size, mtime, k, root = row
            result.append((MediaFile(path=rel_path, size=size or 0, mtime=float(mtime or 0.0), kind=k or kind), Path(root)))
        return result
    except Exception:
        return []

__all__ = ["query_top_rated", "query_by_kind"]
