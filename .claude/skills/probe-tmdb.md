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
| The probe script | `pipeline/scripts/get_films.py` | Committed, durable. **Do not rewrite** — use as-is or extend if Will asks for a new feature |
| The probe report | `pipeline/reports/film-report.md` | Output of running the script; overwritten each run |

`pipeline/reports/` is gitignored — add it to `.gitignore` if not already.

## Behavior when invoked

### Preflight (always run first; abort the skill if it fails)

1. **Check for the API key.** In order:
   - Look for a `TMDB_API_KEY=...` line in `pipeline/.env.local`
   - Otherwise look in `pipeline/.env`
   - Otherwise check the process environment `$TMDB_API_KEY`

   If found, proceed to step 3.

2. **If not found, ask Will for the key.**
   > "No `TMDB_API_KEY` found in `pipeline/.env` or your environment. Paste your TMDB v3 API key (get one at https://www.themoviedb.org/settings/api)."

   On receipt, append `TMDB_API_KEY=<key>` to `pipeline/.env.local` (create the file if missing) using the **Write / Edit** tools — *not* `echo "..." >> .env.local`, since that surfaces the key in shell-command transcripts. Do **not** echo the key back to chat. `.env.local` is gitignored.

3. **Reachability check.** Ping TMDB with the loaded key:

   ```bash
   set -a; source pipeline/.env.local 2>/dev/null; source pipeline/.env 2>/dev/null; set +a
   curl -s -o /dev/null -w "%{http_code}\n" \
     "https://api.themoviedb.org/3/configuration?api_key=$TMDB_API_KEY"
   ```

   Expected output: `200`. Otherwise troubleshoot with Will:

   | Code / signal | Likely cause | Action |
   |---|---|---|
   | `401` | Invalid / revoked key | Ask Will to regenerate at https://www.themoviedb.org/settings/api, update `pipeline/.env`, re-run preflight |
   | `404` / `5xx` | TMDB-side outage | Check https://status.themoviedb.org, retry shortly |
   | curl: network error, DNS fail, timeout | Connectivity / VPN / proxy | Run `curl -v https://api.themoviedb.org/3/configuration` to localize; ask about VPN/proxy/captive portal |
   | Anything else | Unknown | Show Will the raw curl output and stop |

   **Do not proceed past preflight without a `200`.**

### Query workflow

4. **Read the boilerplate query catalog below.** If Will hasn't said what he wants, list the catalog and ask which to run, or whether to compose a new one.
5. **Run the committed script** via uv — do **not** rewrite `get_films.py`. Pick the
   right CLI invocation based on what Will asked for:
   ```bash
   cd pipeline && uv run python scripts/get_films.py                       # all presets
   cd pipeline && uv run python scripts/get_films.py canon-quality         # one preset
   cd pipeline && uv run python scripts/get_films.py --pages 3             # more pages
   cd pipeline && uv run python scripts/get_films.py --lang ko ja          # ad-hoc languages
   cd pipeline && uv run python scripts/get_films.py --era 1960 1970       # ad-hoc decades
   cd pipeline && uv run python scripts/get_films.py --params 'vote_count.gte=200&sort_by=popularity.desc'
   ```
   If Will asks for a query shape the CLI doesn't support, add a new preset to
   the `PRESETS` dict in the script (or a new CLI flag if needed) rather than
   regenerating the file.
6. **Open `pipeline/reports/film-report.md`** and show Will the table. Ask if he wants to refine and re-run.

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

## Script reference

The committed script at `pipeline/scripts/get_films.py` is a full CLI tool.
Do **not** replace it — extend it if needed. Key internals:

- **`PRESETS` dict** — mirrors the boilerplate catalog below. Add new presets here.
- **`expand_queries()`** — handles multi-call presets (`per-language`, `era-sweep`).
- **`resolve_queries()`** — maps CLI args to `(name, params, description)` triples.
- **`--params`** — accepts raw query-string for one-off custom probes.
- **`--stdout`** — prints to terminal instead of writing the report file.

## Notes for Will (edit this skill freely as preferences change)

- Discover returns 20 per page. For more results, set `page=` and concatenate.
- This skill does **not** call `/keywords`, `/credits`, or `/recommendations`. That's the enrichment phase — different skill (`embed-films`, planned).
- Once a query is committed in `pipeline/flickseed_pipeline/ingest/`, this skill stops being load-bearing — it's only for the exploration phase before commit.
- The boilerplate catalog is meant to grow. Add named queries that you've found useful; delete ones that didn't pan out.
