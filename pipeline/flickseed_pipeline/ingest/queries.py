"""Canonical TMDB /discover queries for the Flickseed seed set.

Each entry is one slice. The ingest orchestrator (__main__.py) runs every
query, dedupes by tmdb_id, and writes the union to data/raw/films.json.

Add slices here as the corpus expands; the union grows monotonically.
Each film in films.json carries a `slices` list (the labels that returned
it) so downstream stages can reason about provenance.

The /data-discovery-tmdb skill produces candidate query params — once a
query feels right, codify it here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoverQuery:
    label: str
    description: str
    params: dict[str, str]


SCIFI_CANON = DiscoverQuery(
    label="scifi-canon",
    description="Sci-fi, well-rated and well-watched, excluding the MCU",
    params={
        "with_genres": "878",
        "without_companies": "420",  # Marvel Studios = MCU
        "vote_count.gte": "300",
        "vote_average.gte": "7.5",
        "sort_by": "vote_average.desc",
    },
)


QUERIES: list[DiscoverQuery] = [
    SCIFI_CANON,
]
