# Topology Pipeline

The topology stage takes the embedding vectors from the previous stage and turns
them into the *structure* of the subway map: stations (clusters of films),
edges (connections between stations), and candidate lines (paths through the
network). This is where the map's shape comes from.

## Big picture

```mermaid
flowchart LR
    embeddings["data/derived/<br>embeddings.parquet<br><i>150 films × 896-dim</i>"]
    cluster["<b>Cluster</b><br>BERTopic"]
    stations["data/derived/<br>stations.json<br><i>32 stations</i>"]
    graph["<b>Graph</b><br>mutual k-NN"]
    graph_out["data/derived/<br>station_graph.json"]
    paths_out["data/derived/<br>candidate_paths.json"]

    embeddings --> cluster --> stations --> graph --> graph_out
    graph --> paths_out
```

## Stage 1: Clustering (films → stations)

**What it does:** Groups ~150 films into ~25-40 "stations" — each station is a
cluster of films that feel similar in embedding space. The station becomes a node
on the subway map.

**How it works (BERTopic):**

1. **UMAP** reduces the 896-dim fused vectors down to 5 dimensions. This makes
   the clustering tractable without losing too much structure. Think of it as
   "squishing" a high-dimensional cloud into something you can see patterns in.

2. **HDBSCAN** finds dense clusters in that reduced space. Unlike k-means, it
   doesn't force a fixed number of clusters — it finds natural groupings based
   on density, and marks sparse points as "outliers" (topic -1).

3. **c-TF-IDF** extracts keywords per cluster from the corpus text. This gives
   each station a set of representative words (used for auto-labeling, though
   we hand-name stations later).

4. **Outlier reassignment** — films that HDBSCAN couldn't confidently place get
   assigned to their nearest station by cosine similarity. No film is left
   without a home.

**Key parameters** (in `pipeline/config.yaml`):

| Parameter | Default | Effect |
|-----------|---------|--------|
| `min_topic_size` | 3 | Minimum films per station. Lower = more stations |
| `umap_n_neighbors` | 5 | How "local" UMAP's view is. Lower = tighter clusters |
| `umap_n_components` | 5 | Dimensions after reduction |
| `hdbscan_min_samples` | 1 | How conservative clustering is. Lower = more clusters |

**Tuning intuition:** If you get too few stations, lower `min_topic_size` and
`umap_n_neighbors`. If you get too many, raise them. The target is 25-40.

**Run it:**
```bash
cd pipeline
uv run python -m flickseed_pipeline.cluster
uv run python -m flickseed_pipeline.cluster --min-topic-size 4  # override config
```

**Output:** `data/derived/stations.json` — contains each station's ID, name,
keywords, and film list.

## Stage 2: Graph (stations → edges + candidate lines)

**What it does:** Connects stations into a network, then finds the best paths
through that network to use as subway lines.

**Part A — Mutual k-NN edges:**

1. Compute a **centroid** for each station (mean of its films' embedding vectors,
   L2-normalized).
2. For each station, find its **k nearest neighbors** by cosine similarity.
3. Keep only **mutual** edges: station A connects to B only if B *also* has A in
   its top-k. This prevents "hub" stations from connecting to everything —
   connections must be reciprocal.

**Why mutual k-NN?** A plain similarity threshold creates hubs (stations that
connect to 15 others) and orphans (stations with 0 connections). Mutual k-NN
gives uniform local density — every station has a similar number of connections.

**Part B — Path ranking:**

Once we have a station graph, we search for paths that would make good subway
lines. A good line:

- Has **high local coherence** — consecutive stations are similar to each other
- Has **high drift** — the endpoints are very different (it's a *journey*)
- Is **monotonic** — it moves "forward" through embedding space (doesn't backtrack)
- Is **long enough** to be interesting (length bonus)

The scoring formula: `score = coherence × drift × monotonicity × log₂(length)`

A **diversity filter** ensures selected paths don't overlap too much (max 40%
shared nodes). This gives you variety in your candidates.

**Key parameters** (in `pipeline/config.yaml`):

| Parameter | Default | Effect |
|-----------|---------|--------|
| `k` | 8 | Neighbors per station. Higher = denser graph, more paths |
| `max_path_length` | 8 | Longest path to consider |
| `top_n_paths` | 50 | How many diverse candidates to keep |

**Run it:**
```bash
cd pipeline
uv run python -m flickseed_pipeline.graph
uv run python -m flickseed_pipeline.graph --k 10  # try denser graph
```

**Output:**
- `data/derived/station_graph.json` — nodes + edges with similarity weights
- `data/derived/candidate_paths.json` — ranked paths with scores

## Station naming

Station names live in `data/derived/stations.json` in the `name` field. They're
meant to be evocative and poetic, not genre labels. Edit them directly in the
JSON file whenever you want.

## Visualization

See your stations in the browser:
```bash
cd pipeline
uv run python scripts/plot_stations.py          # opens interactive Plotly scatter
uv run python scripts/plot_stations.py --save reports/stations.html  # save to file
```

Read candidate lines:
```bash
uv run python scripts/print_candidates.py         # top 15 with film titles
uv run python scripts/print_candidates.py --top 34  # all candidates
```

## What comes next

After this stage, you manually curate 4-6 lines from the candidates (pick paths
that feel like interesting journeys) and save them to `data/lines.json`. Then the
layout solver places everything on a Vignelli grid.

## Exercises

1. **Re-cluster with different parameters:** Try `--min-topic-size 5` and see how
   the station count changes. Does it merge stations that should stay separate?

2. **Inspect a noisy station:** Look at Station 31 (Hidden Wires). The films don't
   obviously belong together — can you see what the embeddings found in common?
   (Hint: run `uv run python scripts/diagnose_embeddings.py` and check their
   top-5 neighbors.)

3. **Try a denser graph:** Run `uv run python -m flickseed_pipeline.graph --k 10`.
   Do you get more candidates? Are they better or just noisier?

4. **Rename a station:** Open `data/derived/stations.json`, change a name, and
   re-run `print_candidates.py` to see it in context.
