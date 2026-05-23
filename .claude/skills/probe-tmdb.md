---
name: probe-tmdb
description: Explore TMDB /discover/movie filter combinations for the Flickseed seed query. Compose, run, and refine queries; output a Markdown report Will can review and iterate on.
---

# Probe TMDB

This skill helps Will explore the TMDB `/discover/movie` endpoint to settle on
the canonical seed query for Flickseed (Phase 1 of PROJECT.md §10).

**It is a probing tool, not the ingestion pipeline.** Once a query feels right,
that query gets committed into the actual ingest code under
`pipeline/flickseed_pipeline/ingest/`. The probe skill exists to figure out
*which* query is "right."

## When to invoke

Will invokes this with `/probe-tmdb` when:
- He wants to try new TMDB filter combinations.
- He wants to compare what different queries return side by side.
- He's iterating toward the canonical seed query.

## Artifacts owned by this skill

| Artifact | Path | Lifecycle |
|---|---|---|
| The skill itself | `.claude/skills/probe-tmdb.md` (this file) | Durable — Will edits the boilerplate over time |
| The probe script | `pipeline/scripts/get_films.py` | Created/edited by this skill each run |
| The probe report | `pipeline/reports/film-report.md` | Output of running the script; overwritten each run |

`pipeline/reports/` is gitignored — add it to `.gitignore` if not already.

## Behavior when invoked

1. **Read the boilerplate query catalog below.** If Will hasn't said what he wants, list the catalog and ask which to run, or whether to compose a new one.
2. **Create or edit `pipeline/scripts/get_films.py`** to issue the selected query/queries. Reads `TMDB_API_KEY` from `pipeline/.env`. Uses `httpx` (already a likely pipeline dep) or `requests`.
3. **Run the script** via uv: `cd pipeline && uv run python scripts/get_films.py`.
4. **Open `pipeline/reports/film-report.md`** and show Will the table. Ask if he wants to refine and re-run.

## Output contract — `film-report.md`

One section per query. Format:

```markdown
# TMDB Probe Report — {{ISO date}}

## Query: {{name}}
**Description:** {{short note}}
**Endpoint:** GET /3/discover/movie
**Params:** `vote_count.gte=500&vote_average.gte=7.5&sort_by=vote_average.desc`
**Returned:** 20 of N

| # | Title | Year | Lang | Vote avg | Vote count | Genres | Country |
|---|---|---|---|---|---|---|---|
| 1 | ... | ... | ... | ... | ... | ... | ... |

## Query: {{next}}
...
```

Tables are visually scannable. Will reads them, decides which filter shape
gets him closer to "this feels like Flickseed."

## Boilerplate query catalog

Edit freely. Each entry has a name, description, and the discover params used.

### canon-quality
- **Description:** High-quality canonical set; mainstream-leaning.
- **Params:** `vote_count.gte=500, vote_average.gte=7.5, sort_by=vote_average.desc, primary_release_date.lte=2025-12-31`

### long-tail
- **Description:** Lower obscurity gate; surfaces cult / foreign / older that `canon-quality` misses.
- **Params:** `vote_count.gte=50, vote_average.gte=7.5, sort_by=vote_average.desc`

### per-language
- **Description:** One call per language; union of results. Forces non-English representation (TMDB defaults heavily English).
- **Params (per language):** `with_original_language={code}, vote_count.gte=100, vote_average.gte=7.0, sort_by=vote_average.desc`
- **Languages:** ja, fr, ko, fa, it, de, ru, zh, es

### era-sweep
- **Description:** Forces pre-1980 representation (TMDB is recency-biased; without this you'll get an 80%-post-2000 corpus).
- **Params (per decade):** `primary_release_date.gte={dec}-01-01, primary_release_date.lte={dec+10}-01-01, vote_count.gte=200, sort_by=vote_count.desc`
- **Decades:** 1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020

### zeitgeist
- **Description:** What's culturally hot, not what's critically loved. Useful as a contrast.
- **Params:** `sort_by=popularity.desc, vote_count.gte=100`

## Filter reference (TMDB /discover/movie)

| Filter | Effect | Notes |
|---|---|---|
| `vote_count.gte` | Obscurity gate | Biggest lever. ~1000+ = mainstream, ~50–200 = long tail |
| `vote_average.gte` | Quality floor | 7.5+ restrictive, 7.0+ open |
| `with_original_language` | Single language code | ISO 639-1; chain calls per language for multi-lang |
| `primary_release_date.gte`/`lte` | Era | YYYY-MM-DD |
| `sort_by` | Ranking | `vote_average.desc`, `popularity.desc`, `vote_count.desc`, `primary_release_date.desc` |
| `with_keywords` | Comma-separated keyword IDs | Powerful but inconsistent; look up IDs at `/search/keyword` |
| `with_genres` / `without_genres` | Comma-separated genre IDs | Genre IDs at `/genre/movie/list` |
| `with_runtime.gte` / `lte` | Minutes | Exclude shorts or epics |
| `page` | 1-based | 20 per page; total pages capped at 500 |

## Script shape (for `get_films.py`)

Outline only — the skill generates/edits the actual file each run.

```python
# pipeline/scripts/get_films.py
"""Probe TMDB /discover/movie. Writes pipeline/reports/film-report.md.

Driven by the probe-tmdb skill. Edit the QUERIES list (or let the skill
edit it for you) and re-run.
"""
import os, httpx
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
TMDB_KEY = os.environ["TMDB_API_KEY"]
BASE = "https://api.themoviedb.org/3"

QUERIES = [
    {"name": "canon-quality", "params": {
        "vote_count.gte": 500,
        "vote_average.gte": 7.5,
        "sort_by": "vote_average.desc",
        "primary_release_date.lte": "2025-12-31",
    }},
    # ... add more from the catalog above
]

def fetch(params):
    r = httpx.get(f"{BASE}/discover/movie",
                  params={**params, "api_key": TMDB_KEY})
    r.raise_for_status()
    return r.json()

def format_row(film, genres_lookup):
    return (f"| {film['rank']} | {film['title']} | "
            f"{film['release_date'][:4] if film.get('release_date') else '—'} | "
            f"{film.get('original_language', '—')} | "
            f"{film.get('vote_average', '—'):.1f} | "
            f"{film.get('vote_count', '—')} | "
            f"{', '.join(genres_lookup.get(g, str(g)) for g in film.get('genre_ids', []))} | "
            f"{film.get('origin_country', ['—'])[0] if film.get('origin_country') else '—'} |")

# ... assemble report, write to pipeline/reports/film-report.md
```

## Notes for Will (edit this skill freely as preferences change)

- Discover returns 20 per page. For more results, set `page=` and concatenate.
- This skill does **not** call `/keywords`, `/credits`, or `/recommendations`. That's the enrichment phase — different skill (`embed-films`, planned).
- Once a query is committed in `pipeline/flickseed_pipeline/ingest/`, this skill stops being load-bearing — it's only for the exploration phase before commit.
- The boilerplate catalog is meant to grow. Add named queries that you've found useful; delete ones that didn't pan out.
