from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple, Optional

from .core import MediaFile  # type: ignore
try:  # Prefer real MediaMetadata if available
    from .metadata import MediaMetadata  # type: ignore
except Exception:  # pragma: no cover - fallback for type hints
    class MediaMetadata:  # type: ignore
        pass


@dataclass
class LibraryStats:
    total_files: int
    kinds: Dict[str, int]
    total_size: int
    total_duration: float
    average_rating: Optional[float]
    tag_frequency: Dict[str, int]

    def as_dict(self) -> Dict[str, object]:
        return {
            "total_files": self.total_files,
            "kinds": self.kinds,
            "total_size": self.total_size,
            "total_duration": self.total_duration,
            "average_rating": self.average_rating,
            "tag_frequency": self.tag_frequency,
        }


def compute_stats(
    entries: Iterable[Tuple[MediaFile, Path]],
    metadata_loader,
    attribute_loader,
) -> LibraryStats:
    kinds: Dict[str, int] = {}
    total_size = 0
    total_duration = 0.0
    rating_sum = 0
    rating_count = 0
    tag_frequency: Dict[str, int] = {}

    for media, src in entries:
        kind = (media.kind or "").lower() or "unknown"
        kinds[kind] = kinds.get(kind, 0) + 1
        abs_path = (src / Path(media.path)).resolve()
        try:
            st = abs_path.stat()
            total_size += st.st_size
        except OSError:
            pass
        md: Optional[MediaMetadata] = metadata_loader(abs_path)
        dur = getattr(md, "duration", None) if md else None
        if dur:
            try:
                total_duration += float(dur or 0)
            except Exception:
                pass
        db_rating, db_tags = attribute_loader(abs_path)
        rating = db_rating or (getattr(md, "rating", None) if md else None)
        if rating:
            rating_sum += rating
            rating_count += 1
        tags = db_tags or (getattr(md, "tags", []) if md else []) or []
        for t in tags:
            tag_frequency[t] = tag_frequency.get(t, 0) + 1

    avg_rating = (rating_sum / rating_count) if rating_count else None
    # sort tags by frequency desc then name
    tag_frequency_sorted = dict(sorted(tag_frequency.items(), key=lambda kv: (-kv[1], kv[0])))
    return LibraryStats(
        total_files=sum(kinds.values()),
        kinds=kinds,
        total_size=total_size,
        total_duration=total_duration,
        average_rating=avg_rating,
        tag_frequency=tag_frequency_sorted,
    )
