"""Provider abstraction layer for online metadata enrichment.

Initial version supplies a BaseProvider contract and a MusicBrainzProvider
stub that returns deterministic mock data (no network). Real implementations
will replace the stub logic with HTTP calls + rate limiting + retry/backoff.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
from datetime import datetime
from .time_utils import utc_now


@dataclass
class Candidate:
    """A potential metadata match returned by a provider.

    score: Provider intrinsic confidence (0..1). Final aggregation can mix
    multiple providers; for now we use this directly for ranking.
    """
    title: str
    year: Optional[int]
    provider: str
    provider_id: str
    score: float
    extra: Dict[str, Any]


class BaseProvider(ABC):
    """Abstract base class for metadata providers."""

    name: str = "base"

    @abstractmethod
    def search(self, query: str, media_type: str = "audio") -> List[Candidate]:  # pragma: no cover - interface
        """Return a list of candidate matches for a textual query."""

    def enrich(self, candidate: Candidate) -> Dict[str, Any]:  # pragma: no cover - default no-op
        """Return detailed metadata for a selected candidate.

        By default returns the candidate.extra; concrete providers may perform
        a secondary fetch to retrieve full details.
        """
        return candidate.extra


class MusicBrainzProvider(BaseProvider):
    """Deterministic stub for MusicBrainz queries.

    Real implementation plan (future):
      - Use musicbrainz.org / ws/2 endpoints with user agent, proper rate limit
      - Map recording / release-group results to Candidate objects
      - Provide enrich() for detailed release/recording fetch (artists, tags)
    """

    name = "musicbrainz"

    def search(self, query: str, media_type: str = "audio") -> List[Candidate]:
        # Deterministic mock: derive pseudo IDs from normalized query length
        norm = " ".join(query.strip().split()).casefold()
        base_len = len(norm)
        # Two mock candidates with slightly different scores
        return [
            Candidate(
                title=norm.title() or "Unknown",
                year=2020 + (base_len % 5),
                provider=self.name,
                provider_id=f"mb-track-{base_len}",
                score=0.85,
                extra={
                    "musicbrainz_track_id": f"mb-track-{base_len}",
                    "musicbrainz_release_id": f"mb-release-{base_len}",
                    "original_title": norm.title(),
                    "overview": f"Mock overview for {norm}",
                },
            ),
            Candidate(
                title=f"{norm.title()} Alt",
                year=2019 + (base_len % 7),
                provider=self.name,
                provider_id=f"mb-track-alt-{base_len}",
                score=0.72,
                extra={
                    "musicbrainz_track_id": f"mb-track-alt-{base_len}",
                    "musicbrainz_release_id": f"mb-release-alt-{base_len}",
                    "original_title": f"{norm.title()} Alt",
                    "overview": f"Alternate mock overview for {norm}",
                },
            ),
        ]

    def enrich(self, candidate: Candidate) -> Dict[str, Any]:
        # Stub returns candidate.extra plus a synthetic fetched timestamp for tests
        data = dict(candidate.extra)
        data["enriched_at_provider"] = utc_now().isoformat()
        return data


__all__ = [
    "BaseProvider",
    "MusicBrainzProvider",
    "Candidate",
]
