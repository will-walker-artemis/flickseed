"""Corpus: write per-film markdown documents to data/corpus/*.md.

Per PROJECT.md §5 (post-pivot), per-film text is intentionally lean: the TMDB
overview plus the user's optional notes (if data/notes/<tmdb_id>.md exists).
Atmospheric descriptors, Wikipedia plot, and critic blurbs are deferred — the
embedding stage compensates via multi-view vectorization (keywords + credits
+ recommendation node2vec), not richer text.

Template:
    # [Title] ([Year])
    Director: [Director]   Country: [Country]

    [TMDB overview]

    [Optional: contents of data/notes/<tmdb_id>.md]
"""
