# Metadata Enrichment System

## Overview
The enrichment subsystem augments locally extracted `MediaMetadata` with external data (initially mocked MusicBrainz). It introduces:

* New optional fields on `MediaMetadata`: external IDs (MusicBrainz track/release), `original_title`, `overview`, provenance (`enrichment_sources`), timestamp (`enrichment_fetched_at`), and confidence (`enrichment_confidence`).
* A provider abstraction (`providers.py`) with a stub `MusicBrainzProvider` returning deterministic mock candidates for offline testing.
* A TTL-based JSON cache (`EnrichmentCache`) preventing redundant external lookups.
* A scoring module (`scoring.py`) combining provider score, title similarity, and year proximity into an aggregated score.
* An orchestration layer (`EnrichmentManager`) that coordinates cache usage, provider searches, ranking, and merging selected candidate data into `MediaMetadata`.

## Data Model Extensions
`MediaMetadata` (in `metadata.py`) gained the following optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `musicbrainz_track_id` | str? | Track recording ID |
| `musicbrainz_release_id` | str? | Release (album) ID |
| `tmdb_id` | str? | Placeholder for future movie/TV integration |
| `imdb_id` | str? | Cross reference ID (future) |
| `original_title` | str? | Canonical title from provider |
| `overview` | str? | Long-form description/summary |
| `enrichment_sources` | list[str] | Providers that contributed data |
| `enrichment_fetched_at` | datetime? | Last merge timestamp (timezone-aware UTC) |
| `enrichment_confidence` | float? | Aggregated confidence (0..1) |

Serialization via `to_dict()` includes these fields; absence keeps backward compatibility.

## Cache Architecture
File: `enrichment_cache.py`

* Structure: Single JSON file containing an array of entries.
* Entry fields: `key` (normalized query), `provider`, `created_at` (UTC ISO), `payload` (list of candidates).
* Normalization: Lowercase, whitespace collapsed (see `normalize_query`).
* TTL: Configurable (`ttl_days`, default 14). Expired entries lazily purged on access or via `purge_expired()`.
* Timezone: Uses `utc_now()` (timezone-aware) to avoid naive/aware comparison issues.
* Future Enhancements: Optional migration to SQLite for large-scale libraries; adaptive eviction (LRU on memory pressure).

## Provider Abstraction
File: `providers.py`

`BaseProvider` defines:

```python
search(query: str, media_type: str = "audio") -> list[Candidate]
enrich(candidate: Candidate) -> dict
```

`MusicBrainzProvider` (stub) returns deterministic mock results derived from query length to support reproducible tests. Real implementation will:

* Issue HTTP requests to MusicBrainz WS/2 with proper User-Agent & rate limiting.
* Map recordings / releases to `Candidate` objects.
* Optionally perform a second fetch for detailed enrichment on selection.

## Scoring
File: `scoring.py`

Current scoring = weighted linear combination:

```text
aggregate = provider_score*0.6 + title_similarity*0.3 + year_proximity*0.1
```

* `title_similarity`: simple token overlap (Jaccard) placeholder.
* `year_proximity`: 1.0 (exact), 0.7 (±1), 0.4 (±2), else 0.0.

Planned upgrades:

* RapidFuzz token set / partial ratio (optional dependency) with graceful fallback.
* Field-based weighting adaptation (e.g., boost if album artist matches).
* Confidence calibration and threshold-based auto-apply.

## Orchestration
File: `enrichment_manager.py`

Responsibilities:

1. Normalize query and consult cache per provider.
2. Invoke provider `search` if cache miss; serialize candidates into cache.
3. Compute aggregated score using scoring utilities (optionally using context metadata: title/year).
4. Return sorted `RankedCandidate` list.
5. `enrich()` merges selected candidate details into `MediaMetadata` (non-destructive: only fills empty enrichment fields). Updates provenance, timestamp, and sets `enrichment_confidence` to aggregated score.

## Time Handling
`time_utils.utc_now()` centralizes generation of timezone-aware UTC datetimes. All enrichment components now avoid deprecated `datetime.utcnow()` usage.

## Testing
Added tests:

* `test_enrichment_cache.py` – normalization, TTL expiry (aware datetimes), provider stub integration, metadata dict enrichment fields.
* `test_enrichment_manager.py` – ranking order, cache write reuse, merge semantics (IDs + provenance + confidence).

Totals after integration: 211 tests passing.

## Roadmap (Next Steps)
 
| Phase | Goal | Key Tasks |
|-------|------|-----------|
| Provider Realization | Real MusicBrainz HTTP integration | HTTP client, rate limiter, retry, error notifications |
| Additional Providers | TMDb for video, maybe Discogs | Abstraction extension, provider registry config |
| Advanced Scoring | Better similarity & weighting | RapidFuzz optional dependency, configurable weights |
| Batch UI | Multi-file enrichment panel | Qt view, progress callbacks, cancel, confidence thresholds |
| Conflict Resolution | User diff dialog | Highlight proposed vs existing fields, selective apply |
| Cover Art | Fetch artwork | Add image caching under `covers/`, integrate with existing cover loader |
| Config & Settings | User controls | TTL, min confidence, provider enable/disable, API keys |
| Telemetry (Optional) | Diagnostics | Count misses/hits, average scores (local only) |

## Integration Points
 
* Library UI: Add an "Enrich Metadata" action for selected items.
* Background Execution: Use a thread pool; emit progress via Qt signals to avoid blocking.
* Notifications: Use `CoreServices.send_notification` for success/failure summaries.

## Notes & Considerations
 
* Enrichment is additive: it never overwrites strong existing tags without explicit user confirmation in future UI.
* Cache invalidation strategy can evolve (e.g., manual purge button, automatic purge on version changes).
* All new fields are optional to maintain backward compatibility for persisted library entries and existing tests.

---
Last updated: 2025-10-05
