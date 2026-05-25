"""Ingest: run the canonical TMDB /discover queries, write data/raw/films.json.

Canonical queries live in `queries.py` as a list of `DiscoverQuery`
dataclasses (label + description + raw /discover params). The orchestrator
in `__main__.py` pages through each, dedupes by tmdb_id, and writes the
union with per-film slice provenance.

Iterate on candidate queries via the /data-discovery-tmdb skill, then
codify the chosen params as a new entry in QUERIES.

Usage:
    uv run python -m flickseed_pipeline.ingest

TMDB v3 reference:
  base:            https://api.themoviedb.org/3
  discover:        GET /discover/movie?<filters>&api_key=<key>
  film details:    GET /movie/<id>
  keywords:        GET /movie/<id>/keywords          (enrich stage)
  credits:         GET /movie/<id>/credits           (enrich stage)
  recommendations: GET /movie/<id>/recommendations   (enrich stage)
  images:          https://image.tmdb.org/t/p/<size><path>  (size: w185|w342|w500|original)
  auth env var:    TMDB_API_KEY  (pipeline/.env)
"""
