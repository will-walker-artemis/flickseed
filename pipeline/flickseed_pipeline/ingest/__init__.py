"""Ingest: pull raw film data from external sources into data/raw/.

Sources (priority order, see PROJECT.md §5):
  1. Wikipedia plot + reception (free, clean API)
  2. Personal notes (highest signal for taste-aligned embeddings)
  3. TMDB metadata (title, year, director, country, keywords)
  4. Review excerpts (Letterboxd if accessible, RT blurbs otherwise)
  5. Editorial criticism (Criterion, Sight & Sound where they exist)

TMDB v3 API reference (carried over from the original src/lib/tmdb.ts):
  base:    https://api.themoviedb.org/3
  search:  GET /search/movie?query=<q>&include_adult=false
  film:    GET /movie/<id>
  images:  https://image.tmdb.org/t/p/<size><path>   (size in w185|w342|w500|original)
  auth:    api_key query param (env: TMDB_API_KEY)
"""
