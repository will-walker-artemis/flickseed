"""Enrich: parse the finalized CSV into structured JSON for embedding.

Reads data/raw/films.csv (produced by `get_films.py --mode finalize`) and
extracts per-film data into files consumed by downstream stages:
  keywords -> data/raw/keywords.json   (multi-hot -> PCA in embed/)
  credits  -> data/raw/credits.json    (co-occurrence -> PCA in embed/)

No API calls — all data is already in the CSV.
"""
