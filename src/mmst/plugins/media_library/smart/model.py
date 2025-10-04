from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Iterable, Optional, Callable, Tuple

# A smart playlist rule is a simple predicate on a MediaFile + metadata
# Supported operators kept deliberately small for first iteration.

@dataclass
class SmartPlaylistRule:
    field: str               # e.g. 'kind', 'rating', 'genre', 'tag', 'text', 'mtime_days', 'size_gt', 'duration_gt'
    op: str                  # one of '==', '>=', '<=', 'contains'
    value: Any

    def matches(self, context: Dict[str, Any]) -> bool:
        try:
            current = context.get(self.field)
            if self.op == '==':
                return current == self.value
            if self.op == '>=':
                return current is not None and current >= self.value  # type: ignore
            if self.op == '<=':
                return current is not None and current <= self.value  # type: ignore
            if self.op == 'contains':
                if current is None:
                    return False
                if isinstance(current, (list, tuple, set)):
                    return str(self.value) in {str(v) for v in current}
                return str(self.value).lower() in str(current).lower()
        except Exception:
            return False
        return False

@dataclass
class SmartPlaylist:
    name: str
    rules: List[SmartPlaylistRule] = field(default_factory=list)
    sort: Optional[str] = None   # reuse existing sort keys (e.g. 'rating_desc')
    limit: Optional[int] = None

    def matches(self, context: Dict[str, Any]) -> bool:
        return all(rule.matches(context) for rule in self.rules)


def evaluate_smart_playlist(
    playlist: SmartPlaylist,
    items: Iterable[Tuple[Any, Path]],
    *,
    metadata_loader: Callable[[Path], Any],
    attribute_loader: Callable[[Path], Tuple[Optional[int], Iterable[str]]],
    sort_func: Callable[[List[Tuple[Any, Path]]], List[Tuple[Any, Path]]],
) -> List[Tuple[Any, Path]]:
    """Filter + optional sort + limit.

    items: iterable of (MediaFile, source_path)
    metadata_loader: function returning metadata object with attributes (title, genre, duration, rating, tags, etc.)
    attribute_loader: returns (rating, tags) from DB override
    sort_func: existing sort strategy from widget (will apply after filtering if playlist.sort is not None by tweaking a temporary filter key)
    """
    collected: List[Tuple[Any, Path]] = []
    for media, source_path in items:
        abs_path = (source_path / Path(media.path)).resolve(strict=False)
        meta = metadata_loader(abs_path)
        db_rating, db_tags = attribute_loader(abs_path)
        rating = db_rating if db_rating is not None else getattr(meta, 'rating', None)
        tags = list(db_tags) if db_tags else list(getattr(meta, 'tags', []) or [])
        ctx: Dict[str, Any] = {
            'kind': getattr(media, 'kind', None),
            'rating': rating,
            'genre': getattr(meta, 'genre', None),
            'tag': tags,  # for 'contains'
            'tags': tags,
            'text': ' '.join(
                str(v) for v in [getattr(meta, 'title', ''), getattr(meta, 'album', ''), getattr(meta, 'artist', '')]
            ).lower(),
            'mtime_days': _days_ago(getattr(media, 'mtime', 0.0)),
            'size_gt': getattr(media, 'size', 0),
            'duration_gt': getattr(meta, 'duration', 0) or 0,
        }
        if playlist.matches(ctx):
            collected.append((media, source_path))

    if playlist.sort:
        # naive approach: reuse existing sort by temporarily faking filter key not altering widget state
        collected = sort_func(collected)
    if playlist.limit is not None and playlist.limit >= 0:
        collected = collected[: playlist.limit]
    return collected


def _days_ago(mtime: float) -> int:
    import time
    try:
        delta = time.time() - float(mtime)
        if delta < 0:
            return 0
        return int(delta // 86400)
    except Exception:
        return 0
