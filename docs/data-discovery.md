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

Each run produces two files:
- **Markdown report** (first 20 films per query) — for quick scanning
- **CSV** (all matching films) — full data including overviews

Both default to `pipeline/reports/film-report.{md,csv}`. Use `-o` to change
the base path, or `--stdout` to print the report to the terminal only.

```bash
# Save to named files (creates scifi.md + scifi.csv)
uv run python scripts/get_films.py --params '...' -o reports/scifi.md

# Report only, no CSV
uv run python scripts/get_films.py --params '...' --no-csv

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

## Worked example: tightening a noisy genre pull

Genre alone tends to surface blockbusters at the top of the rating sort because
they accumulate disproportionate vote counts. A typical iteration that turns
"genre + quality" into a usable seed slice looks like this (sci-fi shown, but
the pattern generalises):

| Step | Added filter | Total |
|---|---|---|
| Baseline (genre + open quality) | `with_genres=878&vote_count.gte=200&vote_average.gte=7.0&sort_by=vote_average.desc` | 421 |
| Exclude one franchise studio | `&without_companies=420` (Marvel Studios = MCU) | ~395 |
| Tighten obscurity gate | `vote_count.gte=300` | ~270 |
| Tighten quality floor | `vote_average.gte=7.5` | **122** |

Each filter typically halves the result or so. The exact numbers drift as TMDB
vote counts update; the *shape* of the iteration is what generalises:

1. Strip franchise / studio bias with `without_companies` first — it's the
   fastest way to clean up "all the top films are from one shared universe."
2. Raise `vote_count.gte` to drop noise.
3. Raise `vote_average.gte` to lift canon.

### Production company IDs

Look up any company via `/search/company?query=...`. A few useful ones:

| ID | Company |
|---|---|
| 420 | Marvel Studios (MCU) |
| 1 | Lucasfilm |
| 3 | Pixar |
| 2 | Walt Disney Pictures |
| 33 | Universal Pictures |
| 25 | 20th Century Fox |
| 174 | Warner Bros. Pictures |

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
| `with_companies` | Include production company IDs | Comma-separated. Look up via `/search/company` |
| `without_companies` | Exclude production company IDs | Comma-separated. Strips franchise/studio bias (e.g. MCU = 420) |

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
| `-o PATH` | Save report + CSV to a specific base path (e.g. `-o reports/scifi.md` creates `scifi.md` + `scifi.csv`) |
| `--no-csv` | Skip CSV export, only write the markdown report |
| `--stdout` | Print report to terminal instead of saving (no CSV) |
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
- **Strip franchise bias early.** `without_companies` is the fastest way to
  clean up a sort that's dominated by one studio's shared universe (MCU, Star
  Wars, Pixar). Faster than raising the quality floor, doesn't lose canon.
- **The top 20 lies.** The markdown report only shows the first 20 rows but
  the CSV has everything. The middle and tail of a query (ranks ~50–120)
  often have the texture you actually want — deep canon, foreign cinema,
  pre-1970 films TMDB undervotes. Sample the tail before deciding the query is
  off; sometimes the query is fine and the report is misleading.
- **Comparing pulls.** `pipeline/reports/` is no longer gitignored — committed
  reports are useful for showing how a query evolved. Use `-o` with descriptive
  names (e.g. `reports/scifi-002.md`) so successive iterations sit side by
  side rather than overwriting `film-report.md`.

## What happens next

Once you've settled on a query (or combination of queries) that produces a film
list you're happy with, that query gets committed into
`pipeline/flickseed_pipeline/ingest/`. From there, the `/embed-films` skill
takes over to enrich, embed, and cluster the films.

If you used the `/data-discovery-tmdb` skill, it will guide you through this
transition.
