---
name: data-discovery-tmdb
description: Interactive TMDB data discovery for Flickseed. Asks what the user is looking for, runs queries, reads the report, discusses findings, and iterates until the seed set feels right.
---

# Data Discovery — TMDB

An interactive skill for exploring TMDB's `/discover/movie` endpoint to build
the Flickseed seed corpus. The goal is a back-and-forth conversation: ask what
the user wants, pull data, review results together, refine, repeat.

**This is a probing tool, not the ingestion pipeline.** Once a query feels
right, it gets committed into `pipeline/flickseed_pipeline/ingest/`.

## Behavior when invoked

### 1. Preflight (always run first; abort if it fails)

1. **Check for the API key.** In order:
   - Look for a `TMDB_API_KEY=...` line in `pipeline/.env.local`
   - Otherwise look in `pipeline/.env`
   - Otherwise check the process environment `$TMDB_API_KEY`

   If found, proceed to step 3.

2. **If not found, ask for the key.**
   > "No `TMDB_API_KEY` found in `pipeline/.env.local` or your environment. Paste your TMDB v3 API key (get one at https://www.themoviedb.org/settings/api)."

   On receipt, write `TMDB_API_KEY=<key>` to `pipeline/.env.local` (create if
   missing) using the **Write / Edit** tools — *not* shell echo. Do **not**
   echo the key back to chat. `.env.local` is gitignored.

3. **Reachability check.** Ping TMDB with the loaded key:

   ```bash
   set -a; source pipeline/.env.local 2>/dev/null; source pipeline/.env 2>/dev/null; set +a
   curl -s -o /dev/null -w "%{http_code}\n" \
     "https://api.themoviedb.org/3/configuration?api_key=$TMDB_API_KEY"
   ```

   Expected: `200`. Otherwise troubleshoot:

   | Code | Likely cause | Action |
   |---|---|---|
   | `401` | Invalid / revoked key | Ask to regenerate at https://www.themoviedb.org/settings/api |
   | `404` / `5xx` | TMDB outage | Check https://status.themoviedb.org |
   | Network error | Connectivity | Ask about VPN/proxy |

   **Do not proceed past preflight without a `200`.**

### 2. Ask what the user is looking for

**Do not run queries unprompted.** Start by asking what kind of films they want
to explore. Examples of good opening questions:

- "What genre or vibe are you looking for? (e.g. sci-fi, slow-burn dramas, Korean thrillers)"
- "Any specific era, language, or mood you want to target?"
- "Want to start broad with a preset, or do you have something specific in mind?"

If the user gives a vague answer ("just show me some stuff"), suggest starting
with `canon-quality` or ask them to name a few films that feel like what they
want — then work backward to filters.

### 3. Run the query

Use `pipeline/scripts/get_films.py` — do **not** rewrite it. Pick the right
CLI invocation based on what the user asked for:

```bash
cd pipeline && uv run python scripts/get_films.py canon-quality              # preset
cd pipeline && uv run python scripts/get_films.py --pages 3                  # more pages
cd pipeline && uv run python scripts/get_films.py --lang ko ja               # ad-hoc languages
cd pipeline && uv run python scripts/get_films.py --era 1960 1970            # ad-hoc decades
cd pipeline && uv run python scripts/get_films.py --params 'with_genres=878&vote_count.gte=100&vote_average.gte=7.5&sort_by=vote_average.desc'
```

Save results with `-o reports/<descriptive-name>.md` so different pulls can be
compared side by side. Don't use `--stdout` — always save to a file so the
user can find results later in `pipeline/reports/`.

If the user asks for a query shape the CLI doesn't support, add a new preset
to the `PRESETS` dict in the script rather than regenerating the file.

### 4. Read the report and discuss findings

After running a query, **always read the generated report file** and present
findings to the user. Don't just say "report written" — actually discuss the
results:

- Summarize what came back (count, era spread, language mix, genre breakdown)
- Call out interesting films and patterns
- Flag potential issues (franchise bloat, noise from low vote counts, genre
  imbalance, missing representation)
- Explain what the filters did and didn't catch — TMDB `/discover` is just
  metadata filtering, it has no concept of taste or texture

### 5. Ask how to refine

After discussing, **always ask** what to change. Guide the conversation:

- "Too many blockbusters? We can raise the quality floor or exclude certain genres."
- "Missing non-English films? We can run per-language pulls."
- "Want to see deeper cuts? We can lower the vote threshold — but expect more noise."
- "Should I exclude animation/family to cut the franchise stuff, then backfill anime separately?"

### 6. Repeat steps 3–5

Keep iterating until the user is happy with the shape of the data. Each cycle:
run → read → discuss → refine. Save each pull to a different file so nothing
gets lost.

### 7. When the user is satisfied

Once a query (or combination) feels right, explain the next step: that query
gets committed into `pipeline/flickseed_pipeline/ingest/`, and from there the
`/embed-films` skill takes over for enrichment and embedding.

## Available presets

| Preset | What it pulls |
|---|---|
| `canon-quality` | Well-known, high-rated (500+ votes, 7.5+ avg) |
| `long-tail` | Deeper cuts (50+ votes, 7.5+ avg) |
| `per-language` | One query per language (ja, fr, ko, fa, it, de, ru, zh, es) |
| `era-sweep` | One query per decade, 1950s–2020s |
| `zeitgeist` | Most popular right now regardless of quality |

## TMDB filter reference

| Filter | Effect | Notes |
|---|---|---|
| `vote_count.gte` | Obscurity gate | Biggest lever. 1000+ = mainstream, 50–200 = long tail |
| `vote_average.gte` | Quality floor | 7.5+ restrictive, 7.0+ open |
| `with_original_language` | Single language code | ISO 639-1 |
| `primary_release_date.gte`/`lte` | Era | YYYY-MM-DD |
| `sort_by` | Ranking | `vote_average.desc`, `popularity.desc`, `vote_count.desc` |
| `with_keywords` | Comma-separated keyword IDs | Look up at `/search/keyword` |
| `with_genres` / `without_genres` | Comma-separated genre IDs | See `docs/data-discovery.md` for full ID list |
| `with_runtime.gte` / `lte` | Minutes | Exclude shorts or epics |
| `page` | 1-based | 20 per page; max 500 pages |

## Genre IDs (quick reference)

| ID | Genre | ID | Genre |
|---|---|---|---|
| 28 | Action | 10749 | Romance |
| 12 | Adventure | 878 | Science Fiction |
| 16 | Animation | 53 | Thriller |
| 35 | Comedy | 10752 | War |
| 80 | Crime | 37 | Western |
| 99 | Documentary | 27 | Horror |
| 18 | Drama | 10402 | Music |
| 10751 | Family | 9648 | Mystery |
| 14 | Fantasy | 36 | History |

## Script reference

The committed script at `pipeline/scripts/get_films.py` is a full CLI tool.
Do **not** replace it — extend if needed. Key internals:

- **`PRESETS` dict** — mirrors the presets above. Add new presets here.
- **`expand_queries()`** — handles multi-call presets (`per-language`, `era-sweep`).
- **`resolve_queries()`** — maps CLI args to `(name, params, description)` triples.
- **`--params`** — accepts raw query-string for one-off custom probes.

## Notes

- Discover returns 20 per page. For more results, use `--pages N`.
- This skill does **not** call `/keywords`, `/credits`, or `/recommendations`.
  That's the enrichment phase — see `/embed-films`.
- Once a query is committed in `pipeline/flickseed_pipeline/ingest/`, this
  skill stops being load-bearing — it's only for the exploration phase.
- The presets are meant to evolve. Add queries that worked; remove ones that didn't.
