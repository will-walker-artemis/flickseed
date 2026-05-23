"""Corpus: render per-film ~200-300 token text documents into data/corpus/*.md.

Template (PROJECT.md §5):
    [Title] ([Year], dir. [Director], [Country])

    [Wikipedia plot, condensed to ~80 tokens]

    Your one-liner: [1-2 sentences in your voice about texture/feel]

    Atmosphere: [5-10 affective descriptors]

    [1 vivid sentence from a critic/Letterboxd review]

Corpus quality is the #1 leverage point — embeddings are only as good as text.
This stage generates *drafts*; hand-editing the corpus is an explicit ongoing step.
"""
