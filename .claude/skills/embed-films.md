---
name: embed-films
description: Run the Flickseed representation-learning pipeline — enrich the committed TMDB seed set, build multi-view per-film vectors per PROJECT.md §5, write embeddings.parquet, and emit the top-5-similar diagnostic. Invoke after the canonical /discover query is committed.
---

# Embed Films

This skill runs the **representation-learning** stage of the Flickseed pipeline:
enrichment → corpus → embedding → diagnostic.

It is the second half of the data work. The first half — settling on the
canonical TMDB `/discover` seed query — is the `data-discovery-tmdb` skill.
Once that query is finalized (`get_films.py --mode finalize` → `data/raw/films.csv`),
this skill takes over.

## When to invoke

Will invokes this with `/embed-films` when:
- The canonical seed query is committed and he wants the first embedding pass.
- He's tweaked view weights in `pipeline/config.yaml` and wants to re-embed.
- The diagnostic flagged genre-clustering and he wants to try a different mix.
- He's added/edited personal notes under `data/notes/` and wants them folded in.

## Artifacts owned by this skill

| Artifact | Path | Lifecycle |
|---|---|---|
| The skill | `.claude/skills/embed-films.md` (this file) | Durable — edit as the pipeline matures |
| Enrich module | `pipeline/flickseed_pipeline/enrich/__main__.py` | Parses CSV → JSON; no API calls |
| Corpus module | `pipeline/flickseed_pipeline/corpus/__main__.py` | Generates per-film markdown docs |
| Embed module | `pipeline/flickseed_pipeline/embed/__main__.py` | Multi-view vectorization |
| View-weight config | `pipeline/config.yaml` | Hand-edited; committed (embed reads weights from here) |
| Raw enrichment | `data/raw/{films.csv,keywords.json,credits.json}` | Committed |
| Corpus docs | `data/corpus/*.md` | Committed |
| Final vectors | `data/derived/embeddings.parquet` | Committed (small, useful in history) |
| Diagnostic script | `pipeline/scripts/diagnose_embeddings.py` | Working — top-5 neighbors with view/film options |
| Plot script | `pipeline/scripts/plot_embeddings.py` | Interactive 2D scatter (UMAP/t-SNE + Plotly) |

## Pipeline stages (PROJECT.md §5 made concrete)

1. **Enrichment.** Parse `data/raw/films.csv` (from `get_films.py --mode finalize`)
   into structured JSON. No API calls — keywords and credits are baked into the CSV.
   ```bash
   uv run python -m flickseed_pipeline.enrich
   ```
   Outputs: `data/raw/keywords.json`, `data/raw/credits.json`

2. **Corpus.** Generate per-film markdown documents from the CSV + credits.
   Includes optional personal notes from `data/notes/{tmdb_id}.md`.
   ```bash
   uv run python -m flickseed_pipeline.corpus
   ```
   Outputs: `data/corpus/*.md` (one file per film)

3. **Embedding.** Multi-view vectorization:
   - `overview` — corpus text → sentence-transformer (`all-MiniLM-L6-v2`) → 384-dim
   - `keywords` → multi-hot over vocabulary → PCA → 64-dim
   - `crew` (director + writer + DP + composer + editor) → sparse co-occurrence → PCA → 64-dim
   - `notes` (optional) — personal notes → sentence-transformer → 384-dim (zeros if absent)
   - **Upcoming:** `graph` — node2vec over TMDB `/recommendations` → ~128-dim

   Per-view weights from `pipeline/config.yaml` are applied before concatenation.
   Final vector is L2-normalized. Currently 896-dim (384+64+64+384).
   ```bash
   uv run python -m flickseed_pipeline.embed
   ```
   Outputs: `data/derived/embeddings.parquet` (one row per film with fused + per-view sub-vectors)

4. **Diagnostic.** Top-5 nearest neighbors by cosine similarity. Per PROJECT.md §5:
   if results look "same genre, same era," raise non-text view weights and re-run.
   ```bash
   uv run python scripts/diagnose_embeddings.py
   uv run python scripts/diagnose_embeddings.py --film 278    # query specific film
   uv run python scripts/diagnose_embeddings.py --view crew_pca  # isolate a view
   ```

5. **Visualization.** Interactive 2D scatter of the embedding space.
   ```bash
   uv run python scripts/plot_embeddings.py
   uv run python scripts/plot_embeddings.py --view overview_embed --method tsne
   ```

## View-weight config

`pipeline/config.yaml` (skill creates if missing):

```yaml
# Multi-view embedding weights (PROJECT.md §5).
# Per-view weight applies before concatenation and L2-norm.
# Raise non-text weights if the diagnostic shows genre-clustering.
view_weights:
  overview: 1.0
  keyword: 1.0
  crew: 1.0
  notes: 0.5

# Embedding model + dims. Change these and you'll need a full re-embed.
models:
  text_embed: "sentence-transformers/all-MiniLM-L6-v2"
  text_dim: 384
  keyword_pca_dim: 64
  crew_pca_dim: 64

# Upcoming: node2vec graph embedding
# node2vec:
#   dim: 128
#   walk_length: 30
#   num_walks: 200
#   p: 1.0
#   q: 1.0
```

These are initial values — the weights are tunable and the diagnostic gate
tells you when to adjust them.

## Behavior when invoked

### Preflight (always run first; abort the skill if it fails)

1. **Check for the API key.** In order:
   - Look for a `TMDB_API_KEY=...` line in `pipeline/.env`
   - Otherwise check the process environment `$TMDB_API_KEY`

   If found, proceed to step 3.

2. **If not found, ask Will for the key.**
   > "No `TMDB_API_KEY` found in `pipeline/.env` or your environment. Paste your TMDB v3 API key (get one at https://www.themoviedb.org/settings/api)."

   On receipt, append `TMDB_API_KEY=<key>` to `pipeline/.env` (create the file if missing) using the **Write / Edit** tools — *not* `echo "..." >> .env`, since that surfaces the key in shell-command transcripts. Do **not** echo the key back to chat. `.env` is gitignored.

3. **Reachability check.** Ping TMDB with the loaded key:

   ```bash
   set -a; source pipeline/.env; set +a
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

### Embedding workflow

4. **Verify pipeline prerequisites.**
   - `data/raw/films.csv` exists (from `get_films.py --mode finalize`)
   - `pipeline/config.yaml` exists (create with the defaults shown above if not)
   - Required deps in `pipeline/pyproject.toml`:
     `sentence-transformers`, `scikit-learn`, `pandas`, `pyarrow`, `numpy`.
     If missing, add them and run `uv sync`.
5. **Show current view weights.** Read `pipeline/config.yaml`, display.
6. **Run the pipeline stages in order:**
   ```bash
   cd pipeline
   uv run python -m flickseed_pipeline.enrich
   uv run python -m flickseed_pipeline.corpus
   uv run python -m flickseed_pipeline.embed
   ```
7. **Run the diagnostic:**
   ```bash
   uv run python scripts/diagnose_embeddings.py
   ```
   Summarize the 10 sample results. Ask if they look "tonally adjacent across
   genre/era" (good) or "same genre, same era" (tune weights, re-run).
8. **Optionally visualize:** `uv run python scripts/plot_embeddings.py`

## Module architecture

The pipeline is split into three modules (not a single script):

```
pipeline/flickseed_pipeline/enrich/__main__.py   # CSV → keywords.json + credits.json
pipeline/flickseed_pipeline/corpus/__main__.py   # CSV + credits → data/corpus/*.md
pipeline/flickseed_pipeline/embed/__main__.py    # corpus + JSON → embeddings.parquet
```

Each is invocable via `uv run python -m flickseed_pipeline.<stage>`.
The embed module reads view weights from `pipeline/config.yaml` and outputs
per-view sub-vectors alongside the fused vector for debugging and re-weighting.

## Diagnostic report format

```markdown
# Embedding Diagnostic — {{ISO date}}

**Config:** view weights = {overview: 1.0, keywords: 0.5, crew: 0.5, graph: 1.5, notes: 1.0}
**Corpus size:** N films
**Verdict (Will fills in):** [ ] tonally adjacent / [ ] same genre, same era / [ ] mixed

## Sample 1: {{Title}} ({{Year}})
Top-5 most similar:
1. {{Title}} ({{Year}}) — cosine {{0.xx}}
2. ...

## Sample 2: ...
```

## Notes for Will (edit freely as the pipeline matures)

- **PCA dims are tunable** but `64` for keywords and crew is a reasonable
  starting point — these signals are sparse, PCA-reducing too aggressively
  destroys information.
- **Re-embedding is fast.** The expensive part is the TMDB API calls (done once
  at finalize time). Re-running enrich → corpus → embed only does local
  computation — no network calls.
- **Notes are optional.** Files under `data/notes/{tmdb_id}.md` get embedded
  when present; missing → zero vector so it doesn't bias.
- **Downstream consumers.** The next pipeline stage (`cluster/`) reads
  `data/derived/embeddings.parquet`. BERTopic / k-NN / HDBSCAN expect the
  fused vector, not per-view sub-vectors — but sub-vectors are kept
  in the parquet for debugging and re-weighting without re-fetching.
- **The diagnostic is a gate, not a polish step.** Don't proceed to clustering
  until 10/10 samples feel tonally right. Per PROJECT.md §5: corpus/embedding
  quality is the #1 leverage point — failing to gate here is the single
  biggest failure mode for the whole project.
- **Node2vec is upcoming.** When implemented, it will add a graph view
  (~128-dim) from the TMDB `/recommendations` endpoint. This captures
  "people-who-liked-X-also-liked-Y" signal that no text field provides.
- **View weights are initial values.** The current defaults (all 1.0 except
  notes at 0.5) haven't been tuned yet. The diagnostic gate tells you when
  to adjust — raise non-text weights if genre-clustering appears.
