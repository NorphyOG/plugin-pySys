"""Enrichment cache for external metadata lookups.

Stores normalized query keys with fetched payloads and timestamps to avoid
repeated remote provider calls. Initial implementation uses a JSON file on
disk (one structure) for simplicity; future optimization could move to
SQLite if volume or query patterns require indexing.

Design goals:
 - Simple get/set API with TTL expiration
 - Normalization of text queries (casefold, trim, collapse whitespace)
 - Provider-aware: key can incorporate provider identifier
 - Safe concurrent reads: load once, write atomically

The cache value schema is intentionally flexible (Dict[str, Any]). Providers
should supply serializable data only (basic types, lists, dicts).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from .time_utils import utc_now
import json
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Optional


def _now() -> datetime:
    return utc_now()


def normalize_query(text: str) -> str:
    """Normalize a query text for stable cache keys.

    Steps: strip, lowercase (casefold), collapse internal whitespace to single
    spaces. Empty input returns empty string.
    """
    if not text:
        return ""
    # Collapse whitespace and casefold
    parts = text.strip().split()
    return " ".join(parts).casefold()


@dataclass
class CacheEntry:
    key: str
    provider: str
    created_at: datetime
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "provider": self.provider,
            "created_at": self.created_at.isoformat(),
            "payload": self.payload,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "CacheEntry":
        created_raw = data.get("created_at")
        dt: datetime
        try:
            dt = datetime.fromisoformat(created_raw) if created_raw else _now()
        except Exception:
            dt = _now()
        # Normalize to timezone-aware UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return CacheEntry(
            key=data.get("key", ""),
            provider=data.get("provider", ""),
            created_at=dt,
            payload=data.get("payload", {}) or {},
        )


class EnrichmentCache:
    """A basic TTL-based enrichment cache.

    Parameters
    ----------
    path: Path to the JSON cache file.
    ttl_days: Entries older than this many days are considered expired.
    provider_scoped: If True, provider name is included in internal key so
        different providers can have overlapping query keys independently.
    """

    def __init__(self, path: Path, ttl_days: int = 14, provider_scoped: bool = True) -> None:
        self.path = path
        self.ttl_days = ttl_days
        self.provider_scoped = provider_scoped
        self._entries: Dict[str, CacheEntry] = {}
        self._lock = RLock()
        self._loaded = False

    # ------------------------------- public API ---------------------------------
    def get(self, query: str, provider: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached payload if present and not expired."""
        norm = normalize_query(query)
        internal_key = self._make_key(norm, provider)
        with self._lock:
            self._ensure_loaded()
            entry = self._entries.get(internal_key)
            if not entry:
                return None
            if self._is_expired(entry):
                # Lazy purge
                del self._entries[internal_key]
                return None
            return entry.payload

    def set(self, query: str, provider: str, payload: Dict[str, Any]) -> None:
        """Store a payload for a query/provider."""
        norm = normalize_query(query)
        internal_key = self._make_key(norm, provider)
        with self._lock:
            self._ensure_loaded()
            self._entries[internal_key] = CacheEntry(
                key=norm,
                provider=provider,
                created_at=_now(),
                payload=payload,
            )
            self._save()

    def purge_expired(self) -> int:
        """Remove all expired entries. Returns number purged."""
        with self._lock:
            self._ensure_loaded()
            to_delete = [k for k, e in self._entries.items() if self._is_expired(e)]
            for k in to_delete:
                del self._entries[k]
            if to_delete:
                self._save()
            return len(to_delete)

    # ------------------------------ internal helpers -----------------------------
    def _make_key(self, norm_query: str, provider: str) -> str:
        return f"{provider}::{norm_query}" if self.provider_scoped else norm_query

    def _is_expired(self, entry: CacheEntry) -> bool:
        if self.ttl_days <= 0:
            return False
        # Ensure both sides are aware
        now = _now()
        created = entry.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return created < (now - timedelta(days=self.ttl_days))

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            entries = raw.get("entries", []) if isinstance(raw, dict) else []
            for item in entries:
                try:
                    entry = CacheEntry.from_dict(item)
                    internal = self._make_key(entry.key, entry.provider)
                    self._entries[internal] = entry
                except Exception:
                    continue
        except Exception:
            # Corrupt file; ignore
            pass

    def _save(self) -> None:
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        data = {"entries": [e.to_dict() for e in self._entries.values()]}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(self.path)
        except Exception:
            # Best-effort; ignore persistence errors
            pass

__all__ = [
    "EnrichmentCache",
    "normalize_query",
]
