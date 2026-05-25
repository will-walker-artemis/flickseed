"""Enrich: per-film TMDB endpoint pulls, cached under data/raw/.

Reads data/raw/films.json (from ingest/) and for each film fetches:
  /movie/<id>/keywords         -> data/raw/keywords.json
  /movie/<id>/credits          -> data/raw/credits.json
  /movie/<id>/recommendations  -> data/raw/recommendations.json

Cache-on-disk; re-runs skip endpoints already fetched unless --refresh.
Feeds the multi-view embedding stage (PROJECT.md §5):
  keywords -> multi-hot -> PCA
  credits  -> sparse co-occurrence -> PCA
  recs     -> directed graph -> node2vec
"""
