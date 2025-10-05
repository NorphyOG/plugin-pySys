"""Tests for EnrichmentManager orchestration."""
from __future__ import annotations

from pathlib import Path
from mmst.plugins.media_library.enrichment_manager import EnrichmentManager
from mmst.plugins.media_library.metadata import MediaMetadata


def test_search_returns_ranked_candidates(tmp_path):
    cache_file = tmp_path / "enrich_cache.json"
    mgr = EnrichmentManager(cache_file)
    meta = MediaMetadata(title="Example Query", year=2022)
    results = mgr.search("Example Query", context_metadata=meta)
    assert results, "Expected at least one candidate"
    # Scores should be sorted descending
    scores = [r.aggregated_score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_uses_cache(tmp_path):
    cache_file = tmp_path / "enrich_cache.json"
    mgr = EnrichmentManager(cache_file)
    _ = mgr.search("Cache Test")
    # Inspect raw file to ensure stored
    assert cache_file.exists()
    size_first = cache_file.stat().st_size
    # Second search should not change size (no mutation expected)
    _ = mgr.search("  cache   test ")
    size_second = cache_file.stat().st_size
    assert size_first == size_second


def test_enrich_merges_fields(tmp_path):
    cache_file = tmp_path / "enrich_cache.json"
    mgr = EnrichmentManager(cache_file)
    base_meta = MediaMetadata(title="Song Title", year=2023)
    ranked = mgr.search("Song Title", context_metadata=base_meta)
    assert ranked
    mgr.enrich(base_meta, ranked[0])
    # Post conditions: IDs and provenance set
    assert base_meta.musicbrainz_track_id is not None
    assert "musicbrainz" in base_meta.enrichment_sources
    assert base_meta.enrichment_fetched_at is not None
    assert base_meta.enrichment_confidence is not None
