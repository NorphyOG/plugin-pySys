"""Tests for enrichment cache and enrichment-related metadata fields."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import json

from mmst.plugins.media_library.enrichment_cache import EnrichmentCache, normalize_query
from mmst.plugins.media_library.time_utils import utc_now
from mmst.plugins.media_library.metadata import MediaMetadata
from mmst.plugins.media_library.providers import MusicBrainzProvider


def test_normalize_query_basic():
    assert normalize_query("  Hello   WORLD  ") == "hello world"
    assert normalize_query("") == ""
    assert normalize_query("Mixed\tCase\nWords") == "mixed case words"


def test_enrichment_cache_set_get(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache = EnrichmentCache(cache_file, ttl_days=30)
    cache.set("Test Song", "musicbrainz", {"id": 123, "title": "Test Song"})

    result = cache.get("Test Song", "musicbrainz")
    assert result is not None
    assert result["title"] == "Test Song"

    # Case / whitespace differences should resolve to same key
    result2 = cache.get("  test   song  ", "musicbrainz")
    assert result2 is not None
    assert result2["id"] == 123


def test_enrichment_cache_ttl_expiry(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.json"
    cache = EnrichmentCache(cache_file, ttl_days=7)
    cache.set("Track", "musicbrainz", {"value": 1})

    # Manipulate file to backdate created_at for expiry simulation
    raw = json.loads(cache_file.read_text(encoding="utf-8"))
    assert raw["entries"]
    raw["entries"][0]["created_at"] = (utc_now() - timedelta(days=10)).isoformat()
    cache_file.write_text(json.dumps(raw), encoding="utf-8")

    # New cache instance to reload
    cache2 = EnrichmentCache(cache_file, ttl_days=7)
    expired = cache2.get("Track", "musicbrainz")
    assert expired is None


def test_musicbrainz_provider_stub():
    provider = MusicBrainzProvider()
    results = provider.search("Example Query")
    assert len(results) >= 1
    first = results[0]
    assert first.provider == "musicbrainz"
    detail = provider.enrich(first)
    assert "musicbrainz_track_id" in detail


def test_metadata_enrichment_fields_to_dict():
    meta = MediaMetadata(
        title="Song", artist="Artist", musicbrainz_track_id="mb-track-1", original_title="Song Original"
    )
    meta.enrichment_sources.append("musicbrainz")
    meta.enrichment_confidence = 0.9
    data = meta.to_dict()
    assert data["musicbrainz_track_id"] == "mb-track-1"
    assert data["original_title"] == "Song Original"
    assert data["enrichment_sources"] == ["musicbrainz"]
    assert data["enrichment_confidence"] == 0.9
