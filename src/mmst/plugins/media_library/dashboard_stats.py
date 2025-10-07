"""Robust dashboard statistics computation for MediaLibrary.

Provides a single entry point `build_dashboard_stats` that never raises and
returns a dict suitable for `StatisticsDashboard.update_statistics`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import time

from .core import MediaFile  # type: ignore
from .telemetry import get_telemetry_sink

try:  # pragma: no cover - best effort import
    from .metadata import MediaMetadata  # type: ignore
except Exception:  # pragma: no cover
    class MediaMetadata:  # type: ignore
        pass

@dataclass
class DashboardBuildResult:
    stats: Dict[str, Any]
    errors: int
    processed: int
    duration: float


def build_dashboard_stats(
    entries: Iterable[Tuple[MediaFile, Path]],
    metadata_loader,
    attribute_loader,
    *,
    max_errors: int = 50,
    limit: Optional[int] = None,
) -> DashboardBuildResult:
    start = time.perf_counter()
    total_files = 0
    audio = video = image = 0
    total_size = 0
    rating_sum = 0
    rating_count = 0
    rating_distribution: Dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    genre_counts: Dict[str, int] = {}
    artist_counts: Dict[str, int] = {}
    added_last_7_days = 0
    modified_last_7_days = 0
    errors = 0
    processed = 0

    import datetime as _dt
    now = _dt.datetime.now()
    week_ago = now - _dt.timedelta(days=7)

    for media, root in entries:
        if limit is not None and processed >= limit:
            break
        processed += 1
        total_files += 1
        kind = media.kind or "other"
        if kind == "audio":
            audio += 1
        elif kind == "video":
            video += 1
        elif kind == "image":
            image += 1

        abs_path = (root / Path(media.path)).resolve()
        try:
            st = abs_path.stat()
            total_size += getattr(st, "st_size", 0)
            # time based stats
            try:
                if _dt.datetime.fromtimestamp(getattr(st, "st_ctime", 0)) > week_ago:
                    added_last_7_days += 1
                if _dt.datetime.fromtimestamp(getattr(st, "st_mtime", 0)) > week_ago:
                    modified_last_7_days += 1
            except Exception:
                pass
        except Exception:
            # File missing -> skip size/time contributions
            pass

        try:
            md: Optional[MediaMetadata] = metadata_loader(abs_path)
        except Exception:
            md = None
            errors += 1
            if errors >= max_errors:
                break

        # rating / distribution
        file_rating = None
        try:
            db_rating, db_tags = attribute_loader(abs_path)
            file_rating = db_rating
        except Exception:
            db_tags = []
            errors += 1
            if errors >= max_errors:
                break

        if file_rating is None and md is not None:
            file_rating = getattr(md, "rating", None)
        if isinstance(file_rating, int) and 0 <= file_rating <= 5:
            rating_sum += file_rating
            rating_count += 1
            rating_distribution[file_rating] += 1
        else:
            rating_distribution[0] += 1

        # genres / artists (best effort)
        if md is not None:
            genre = getattr(md, "genre", None)
            if isinstance(genre, str) and genre.strip():
                g = genre.strip()[:100]
                genre_counts[g] = genre_counts.get(g, 0) + 1
            artist = getattr(md, "artist", None)
            if isinstance(artist, str) and artist.strip():
                a = artist.strip()[:100]
                artist_counts[a] = artist_counts.get(a, 0) + 1

    avg_rating = (rating_sum / rating_count) if rating_count else 0.0

    # top lists
    def _top(n: int, mapping: Dict[str, int]) -> List[Tuple[str, int]]:
        return sorted(mapping.items(), key=lambda kv: (-kv[1], kv[0]))[:n]

    stats = {
        "total_files": total_files,
        "total_size": total_size,
        "audio_count": audio,
        "video_count": video,
        "image_count": image,
        "avg_rating": avg_rating,
        "added_last_7_days": added_last_7_days,
        "modified_last_7_days": modified_last_7_days,
        "rating_distribution": rating_distribution,
        "top_genres": _top(10, genre_counts),
        "top_artists": _top(10, artist_counts),
        "error_count": errors,
        "processed": processed,
    }

    duration = time.perf_counter() - start
    sink = get_telemetry_sink()
    if sink is not None:
        try:
            sink.record("stats", "build_dashboard", duration, processed)
        except Exception:
            pass
    return DashboardBuildResult(stats=stats, errors=errors, processed=processed, duration=duration)
