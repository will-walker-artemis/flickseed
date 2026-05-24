---
name: embed-films
description: Run the Flickseed representation-learning pipeline — enrich the committed TMDB seed set, build multi-view per-film vectors per PROJECT.md §5, write embeddings.parquet, and emit the top-5-similar diagnostic. Invoke after the canonical /discover query is committed.
---

# Embed Films

This skill runs the **representation-learning** stage of the Flickseed pipeline:
ingestion → enrichment → feature extraction → embedding → graph construction →
graph embedding → vector composition → diagnostic.

It is the second half of the data work. The first half — settling on the
canonical TMDB `/discover` seed query — is the `probe-tmdb` skill. Once that
query is committed, this skill takes over.

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
| Pipeline script | `pipeline/scripts/enrich_and_embed.py` | Created/edited by this skill |
| View-weight config | `pipeline/config.yaml` | Hand-edited; committed |
| Raw enrichment | `data/raw/{films,keywords,credits,recommendations}.json` | Gitignored (large, regenerable) |
| Final vectors | `data/derived/embeddings.parquet` | Committed (small, useful in history) |
| Diagnostic report | `pipeline/reports/embedding-diagnostic.md` | Gitignored |

## Pipeline stages (PROJECT.md §5 made concrete)

1. **Ingestion.** Run the committed `/discover` query (lives in
   `pipeline/flickseed_pipeline/ingest/`). Get film IDs + base metadata.
2. **Enrichment.** Per film, call `/movie/{id}`, `/movie/{id}/keywords`,
   `/movie/{id}/credits`, `/movie/{id}/recommendations`. Cache to
   `data/raw/*.json`. Skip endpoints whose cache exists unless `--refresh`.
3. **Feature extraction:**
   - `overview` (string) → sentence-transformer (e.g. `all-MiniLM-L6-v2`) → 384-dim
   - `keywords` → multi-hot over the full vocabulary → PCA → 64-dim
   - `credits` (director + writer + DP + composer + editor) → sparse co-occurrence → PCA → 64-dim
4. **Graph construction.** Build a directed graph where nodes are films and
   edges come from `/recommendations` (and optionally `/similar`). For films
   outside the seed set referenced as recommendations, decide: include as
   "anchor neighbors" (extends graph) or drop. Default: include 1-hop neighbors
   only, drop nodes not reachable from any seed.
5. **Graph embedding.** Run node2vec over the graph → 128-dim per film.
   Library options: `gensim` + `node2vec` package, or `pecanpy`, or `karateclub`.
6. **Personal notes (optional).** If `data/notes/{tmdb_id}.md` exists for a
   film, embed it with the same sentence-transformer → 384-dim. Otherwise, a
   zero vector (mask handled by view weight = 0 when missing).
7. **Vector composition.** Concatenate all views per film, apply per-view
   weights from `pipeline/config.yaml`, L2-normalize the result.
8. **Output.** Write `data/derived/embeddings.parquet` — one row per film,
   columns: `tmdb_id`, `title`, `vector` (list of floats), plus per-view
   sub-vectors for debugging (`vector_overview`, `vector_keyword`, etc.).
9. **Diagnostic.** Sample 10 random films, compute top-5 nearest neighbors by
   cosine similarity, write a markdown report. Per PROJECT.md §5: if
   results look "same genre, same era," **raise non-text view weights** and
   re-run before retreating to richer text.

## View-weight config

`pipeline/config.yaml` (skill creates if missing):

```yaml
# Multi-view embedding weights (PROJECT.md §5).
# Per-view weight applies before concatenation and L2-norm.
# Raise `graph` and lower `overview` if the diagnostic shows genre-clustering.
view_weights:
  overview: 1.0
  keywords: 0.5
  crew: 0.5
  graph: 1.5
  notes: 1.0

# Embedding model + dims. Change these and you'll need a full re-embed.
models:
  text_embed: "sentence-transformers/all-MiniLM-L6-v2"
  text_dim: 384
  keyword_pca_dim: 64
  crew_pca_dim: 64
  node2vec:
    dim: 128
    walk_length: 30
    num_walks: 200
    p: 1.0
    q: 1.0

# Graph construction.
graph:
  edges_from: ["recommendations"]  # could add "similar"
  include_one_hop_neighbors: true
```

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
   - The canonical query is committed under `pipeline/flickseed_pipeline/ingest/`
   - `pipeline/config.yaml` exists (create with the defaults shown above if not)
   - Required deps in `pipeline/pyproject.toml`:
     `httpx`, `sentence-transformers`, `networkx`, `node2vec` (or `pecanpy`),
     `scikit-learn`, `pandas`, `pyarrow`. If missing, add them and run `uv sync`.
5. **Show current view weights.** Read `pipeline/config.yaml`, display.
6. **Ask whether to refresh enrichment.** TMDB calls are slow and rate-limited
   (~40/sec). Default: use cached `data/raw/*.json` if present, only fetch
   missing endpoints. Offer `--refresh` to force re-fetch.
7. **Create / edit `pipeline/scripts/enrich_and_embed.py`** to run stages 1–9.
8. **Run it:** `cd pipeline && uv run python scripts/enrich_and_embed.py`.
9. **Show the diagnostic.** Open `pipeline/reports/embedding-diagnostic.md`,
   summarize the 10 sample results, ask if they look "tonally adjacent across
   genre/era" (good) or "same genre, same era" (raise graph weight, re-run).

## Script shape (for `enrich_and_embed.py`)

Outline only — skill generates / edits the real file each run.

```python
# pipeline/scripts/enrich_and_embed.py
"""Run the Flickseed representation-learning pipeline.

Driven by the embed-films skill. Reads pipeline/config.yaml for view weights.
"""
from pathlib import Path
import json, yaml, httpx, pandas as pd, numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import PCA
import networkx as nx
from node2vec import Node2Vec

ROOT = Path(__file__).parent.parent.parent
CFG = yaml.safe_load((ROOT / "pipeline/config.yaml").read_text())

def ingest() -> list[dict]: ...        # run committed /discover query
def enrich(films) -> dict: ...         # /keywords, /credits, /recommendations
def text_vectors(films, model) -> np.ndarray: ...
def keyword_vectors(films) -> np.ndarray: ...     # multi-hot → PCA
def crew_vectors(films) -> np.ndarray: ...         # sparse → PCA
def build_graph(films, recs) -> nx.DiGraph: ...
def graph_vectors(graph, films) -> np.ndarray: ...  # node2vec
def notes_vectors(films, model) -> np.ndarray: ...  # optional, zeros if missing
def compose(views: dict, weights: dict) -> np.ndarray: ...  # weight, concat, L2-norm
def diagnose(vectors, films) -> str: ...           # top-5 for 10 random → markdown

def main():
    films = ingest()
    enriched = enrich(films)
    model = SentenceTransformer(CFG["models"]["text_embed"])
    views = {
        "overview": text_vectors(films, model),
        "keywords": keyword_vectors(films),
        "crew":     crew_vectors(films),
        "graph":    graph_vectors(build_graph(films, enriched), films),
        "notes":    notes_vectors(films, model),
    }
    final = compose(views, CFG["view_weights"])
    pd.DataFrame({"tmdb_id": [...], "title": [...], "vector": list(final)}) \
      .to_parquet(ROOT / "data/derived/embeddings.parquet")
    (ROOT / "pipeline/reports/embedding-diagnostic.md").write_text(diagnose(final, films))

if __name__ == "__main__":
    main()
```

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

- **node2vec hyperparams matter.** `p` and `q` shift the random walk between
  BFS-like (community-finding) and DFS-like (structural-role-finding). Start
  with defaults; tweak if graph embedding feels off.
- **PCA dims are tunable** but `64` for keywords and crew is a reasonable
  starting point — these signals are sparse, PCA-reducing too aggressively
  destroys information.
- **Caching is your friend.** `data/raw/` is gitignored and the script should
  short-circuit on existing cache files. Re-embed cycles should be fast (only
  re-running stages 3–9) unless you `--refresh`.
- **Notes are optional.** Files under `data/notes/{tmdb_id}.md` get embedded
  when present; missing → zero vector with weight=0 applied so it doesn't bias.
- **Downstream consumers.** The next pipeline stage (`cluster/`) reads
  `data/derived/embeddings.parquet`. BERTopic / k-NN / HDBSCAN expect the
  final composed vector, not per-view sub-vectors — but sub-vectors are kept
  in the parquet for debugging and re-weighting without re-fetching.
- **The diagnostic is a gate, not a polish step.** Don't proceed to clustering
  until 10/10 samples feel tonally right. Per PROJECT.md §5: corpus/embedding
  quality is the #1 leverage point — failing to gate here is the single
  biggest failure mode for the whole project.
