# Data Discovery

How to find and pull films from TMDB for the Flickseed corpus.

The easiest way to get started is the **`/data-discovery-tmdb`** Claude skill.
It walks you through the process interactively — just tell it what kind of
films you're looking for and it handles the queries, shows you results, and
helps you refine. Use it in any Claude Code workspace opened in this repo.

Everything below documents the underlying CLI tool if you want to run queries
directly.

## Setup

1. Get a TMDB v3 API key at https://www.themoviedb.org/settings/api
2. Add it to `pipeline/.env.local`:
   ```
   TMDB_API_KEY=your_key_here
   ```
   No quotes, no spaces. Use the **API Key (v3 auth)**, not the longer
   "API Read Access Token."

## Quick start

All commands run from the `pipeline/` directory.

```bash
# Run a preset
uv run python scripts/get_films.py canon-quality

# Run all 5 presets at once
uv run python scripts/get_films.py

# Run a custom query with raw TMDB filters
uv run python scripts/get_films.py --params 'with_genres=878&vote_count.gte=100&vote_average.gte=7.5&sort_by=vote_average.desc'
```

Reports are saved to `pipeline/reports/film-report.md` by default. Use `-o` to
save to a different file, or `--stdout` to print to the terminal (does **not**
also save to file).

```bash
# Save to a named file
uv run python scripts/get_films.py --params '...' -o reports/scifi-100.md

# Print to terminal only (nothing saved)
uv run python scripts/get_films.py --params '...' --stdout
```

## Presets

The script has 5 built-in presets — named shortcuts for common filter
combinations. These are defined in the `PRESETS` dict inside `get_films.py`,
not TMDB concepts.

| Preset | What it does |
|---|---|
| `canon-quality` | Well-known, high-rated (500+ votes, 7.5+ avg) |
| `long-tail` | Deeper cuts (50+ votes, 7.5+ avg) |
| `per-language` | One query per language (ja, fr, ko, fa, it, de, ru, zh, es) |
| `era-sweep` | One query per decade, 1950s-2020s |
| `zeitgeist` | Most popular right now regardless of quality |

## Custom queries with `--params`

For anything the presets don't cover, pass raw TMDB filters as a query string:

```bash
# Sci-fi films with 100+ votes, sorted by rating
uv run python scripts/get_films.py --params 'with_genres=878&vote_count.gte=100&vote_average.gte=7.5&sort_by=vote_average.desc'

# Korean dramas from the 2010s
uv run python scripts/get_films.py --params 'with_genres=18&with_original_language=ko&primary_release_date.gte=2010-01-01&primary_release_date.lte=2020-01-01&vote_count.gte=100&sort_by=vote_average.desc'
```

## TMDB filter reference

TMDB's `/discover/movie` is a filter+sort over their entire database. It has no
concept of taste or recommendations — it only knows metadata.

| Filter | What it does | Notes |
|---|---|---|
| `vote_count.gte` | Obscurity gate | Biggest lever. 1000+ = mainstream, 50-200 = long tail |
| `vote_average.gte` | Quality floor | 7.5+ restrictive, 7.0+ open |
| `with_genres` | Include genre IDs | See genre ID list below |
| `without_genres` | Exclude genre IDs | Comma-separated |
| `with_original_language` | Language code | ISO 639-1 (ko, ja, fr, etc.) |
| `primary_release_date.gte/lte` | Era | YYYY-MM-DD format |
| `sort_by` | Ranking | `vote_average.desc`, `popularity.desc`, `vote_count.desc` |
| `with_keywords` | TMDB keyword IDs | Look up via `/search/keyword` |
| `with_runtime.gte/lte` | Runtime in minutes | Exclude shorts or epics |

### Genre IDs

| ID | Genre | ID | Genre |
|---|---|---|---|
| 28 | Action | 10749 | Romance |
| 12 | Adventure | 878 | Science Fiction |
| 16 | Animation | 10770 | TV Movie |
| 35 | Comedy | 53 | Thriller |
| 80 | Crime | 10752 | War |
| 99 | Documentary | 37 | Western |
| 18 | Drama | 27 | Horror |
| 10751 | Family | 10402 | Music |
| 14 | Fantasy | 9648 | Mystery |
| 36 | History | | |

## Other flags

| Flag | What it does |
|---|---|
| `--pages N` | Fetch N pages (20 films per page, default 1) |
| `-o PATH` | Save report to a specific file |
| `--stdout` | Print to terminal instead of saving |
| `--lang CODE [CODE ...]` | Ad-hoc per-language pulls (e.g. `--lang ko ja`) |
| `--era DECADE [DECADE ...]` | Ad-hoc per-decade pulls (e.g. `--era 1960 1970`) |

## Tips

- **Start broad, then narrow.** Run a preset to see the shape of the data, then
  use `--params` to target what you actually want.
- **`vote_count.gte` is the biggest lever.** Too high and you only get
  blockbusters. Too low and you get noise (concert films, obscure docs).
  100-200 is a good middle ground for finding interesting films.
- **Combine strategies.** Union multiple pulls — e.g. a quality backbone +
  language-specific pulls + genre-targeted pulls — rather than looking for one
  magic query.
- **Reports are disposable.** `pipeline/reports/` is gitignored. Run as many
  pulls as you want; use `-o` with descriptive names to compare side by side.

## What happens next

Once you've settled on a query (or combination of queries) that produces a film
list you're happy with, that query gets committed into
`pipeline/flickseed_pipeline/ingest/`. From there, the `/embed-films` skill
takes over to enrich, embed, and cluster the films.

If you used the `/data-discovery-tmdb` skill, it will guide you through this
transition.
