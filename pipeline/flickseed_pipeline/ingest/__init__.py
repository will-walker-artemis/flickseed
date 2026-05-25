"""Ingest: run the canonical TMDB /discover query, write data/raw/films.json.

The seed query is the output of the /data-discovery-tmdb skill: iterate via
pipeline/scripts/get_films.py until results feel right, then bake the chosen
filter parameters into this package as the committed canonical query.

Downstream stages (enrich/, embed/) read films.json.

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
