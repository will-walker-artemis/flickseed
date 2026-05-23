"""Embed: turn data/corpus/*.md into data/derived/embeddings.parquet.

Followed by the top-5-similar diagnostic (scripts/diagnose_embeddings.py) — the
go/no-go gate before clustering. If neighbours look like "same genre, same era"
the corpus is too genre-loaded; go fix that, not the model.
"""
