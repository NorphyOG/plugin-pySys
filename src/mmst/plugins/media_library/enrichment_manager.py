"""Enrichment manager orchestrating provider search, caching and merge.

Phase 1 implementation (no UI yet):
 - search(query, media_type) returns ranked candidates (provider + score)
 - enrich(metadata, candidate) merges chosen candidate details into MediaMetadata
 - Uses EnrichmentCache for query caching (stores provider search results payload)

Future extensions:
 - Multi-provider aggregation
 - Advanced scoring (Levenshtein / token set ratios, year proximity weighting)
 - Batch enrichment with heuristics (auto-pick above threshold)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from .time_utils import utc_now
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .enrichment_cache import EnrichmentCache, normalize_query
from .metadata import MediaMetadata
from .providers import BaseProvider, MusicBrainzProvider, Candidate
from .scoring import simple_ratio, year_proximity_score, aggregate_score


@dataclass
class RankedCandidate:
    candidate: Candidate
    aggregated_score: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "title": self.candidate.title,
            "year": self.candidate.year,
            "provider": self.candidate.provider,
            "provider_id": self.candidate.provider_id,
            "score": self.aggregated_score,
        }


class EnrichmentManager:
    """High-level API for metadata enrichment workflows."""

    def __init__(
        self,
        cache_path: Path,
        providers: Optional[Sequence[BaseProvider]] = None,
        ttl_days: int = 14,
    ) -> None:
        self.cache = EnrichmentCache(cache_path, ttl_days=ttl_days)
        self.providers: List[BaseProvider] = list(providers) if providers else [MusicBrainzProvider()]

    # ------------------------------ public methods ------------------------------
    def search(self, query: str, media_type: str = "audio", context_metadata: Optional[MediaMetadata] = None) -> List[RankedCandidate]:
        """Search across providers with caching and return ranked candidates.

        Cache strategy (phase 1): each provider caches its raw result list.
        For determinism (tests), the MusicBrainzProvider stub is used.
        """
        norm = normalize_query(query)
        ranked: List[RankedCandidate] = []
        for provider in self.providers:
            cached = self.cache.get(norm, provider.name)
            if cached is not None:
                candidates = self._deserialize_candidates(cached, provider)
            else:
                candidates = provider.search(query, media_type=media_type)
                # Store serializable representation
                self.cache.set(norm, provider.name, {
                    "candidates": [self._candidate_to_payload(c) for c in candidates]
                })
            for c in candidates:
                ranked.append(RankedCandidate(candidate=c, aggregated_score=self._aggregate_score(c, context_metadata)))
        # Simple ordering by aggregated score desc then title asc
        ranked.sort(key=lambda rc: (-rc.aggregated_score, rc.candidate.title.lower()))
        return ranked

    def enrich(self, metadata: MediaMetadata, ranked_candidate: RankedCandidate) -> MediaMetadata:
        """Merge enrichment data from selected candidate into metadata instance."""
        provider = self._get_provider(ranked_candidate.candidate.provider)
        detailed = provider.enrich(ranked_candidate.candidate)
        # Merge selected fields (non-destructive for existing strong fields)
        self._merge_fields(
            metadata,
            detailed,
            provider_name=provider.name,
            aggregated_score=ranked_candidate.aggregated_score,
        )
        return metadata

    # ------------------------------ internal helpers ----------------------------
    def _candidate_to_payload(self, c: Candidate) -> Dict[str, object]:
        return {
            "title": c.title,
            "year": c.year,
            "provider": c.provider,
            "provider_id": c.provider_id,
            "score": c.score,
            "extra": c.extra,
        }

    def _deserialize_candidates(self, data: Dict[str, object], provider: BaseProvider) -> List[Candidate]:
        raw_list = []
        if isinstance(data, dict):
            raw_list = data.get("candidates", [])  # type: ignore[assignment]
        candidates: List[Candidate] = []
        if not isinstance(raw_list, list):
            return candidates
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            try:
                candidates.append(Candidate(
                    title=str(item.get("title", "")),
                    year=item.get("year"),
                    provider=provider.name,
                    provider_id=str(item.get("provider_id", "")),
                    score=float(item.get("score", 0.0)),
                    extra=item.get("extra", {}) or {},
                ))
            except Exception:
                continue
        return candidates

    def _aggregate_score(self, candidate: Candidate, context: Optional[MediaMetadata]) -> float:
        if context is None:
            return candidate.score
        title_score = 0.0
        if context.title:
            title_score = simple_ratio(context.title, candidate.title)
        year_score = year_proximity_score(context.year, candidate.year)
        return aggregate_score(candidate.score, title_score, year_score)

    def _merge_fields(self, metadata: MediaMetadata, data: Dict[str, object], provider_name: str, aggregated_score: float) -> None:
        # Candidate extra contains MusicBrainz IDs and textual info
        changed = False
        id_track = data.get("musicbrainz_track_id")
        id_release = data.get("musicbrainz_release_id")
        if isinstance(id_track, str) and not metadata.musicbrainz_track_id:
            metadata.musicbrainz_track_id = id_track; changed = True
        if isinstance(id_release, str) and not metadata.musicbrainz_release_id:
            metadata.musicbrainz_release_id = id_release; changed = True
        if not metadata.original_title:
            ot = data.get("original_title")
            if isinstance(ot, str):
                metadata.original_title = ot; changed = True
        if not metadata.overview:
            ov = data.get("overview")
            if isinstance(ov, str):
                metadata.overview = ov; changed = True
        # Track provenance
        if provider_name not in metadata.enrichment_sources:
            metadata.enrichment_sources.append(provider_name); changed = True
        if changed:
            metadata.enrichment_fetched_at = utc_now()
            metadata.enrichment_confidence = float(aggregated_score)

    def _get_provider(self, name: str) -> BaseProvider:
        for p in self.providers:
            if p.name == name:
                return p
        raise ValueError(f"Provider '{name}' not registered")


__all__ = [
    "EnrichmentManager",
    "RankedCandidate",
]
