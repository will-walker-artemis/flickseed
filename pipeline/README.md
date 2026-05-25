# flickseed-pipeline

Python data pipeline that produces `data/layout.json` — the contract consumed by
the React renderer in `../app/` (and, later, the TouchDesigner renderer in `../td/`).

See `../PROJECT.md` for the architectural overview. This README is operational only.

## Setup

```bash
uv sync
uv run python -c "import flickseed_pipeline"
```

## Stages

Each subpackage owns one stage of the pipeline. Stages read their inputs from
`../data/` and write outputs back to `../data/`.

```
ingest    TMDB /discover seed query   -> data/raw/films.csv
enrich    parse CSV into JSON         -> data/raw/{keywords,credits}.json
corpus    overview + optional notes   -> data/corpus/*.md
embed     multi-view vectors          -> data/derived/embeddings.parquet
cluster   embeddings -> BERTopic      -> data/derived/stations.json
graph     stations -> mutual k-NN     -> data/derived/{station_graph,candidate_paths}.json
layout    stations + lines            -> Vignelli grid positions
export    everything                  -> data/layout.json
```

See PROJECT.md §5 for the multi-view embedding strategy.

## Scripts

- `scripts/get_films.py` — TMDB `/discover` probe CLI; discover mode for exploration, finalize mode for full export with keywords + credits
- `scripts/run_pipeline.py` — end-to-end runner (stub)
- `scripts/diagnose_embeddings.py` — top-5-similar diagnostic (the go/no-go gate); supports `--view`, `--film`, `--seed` options
- `scripts/plot_embeddings.py` — interactive 2D scatter plot via UMAP/t-SNE + Plotly; supports `--view`, `--method`, `--save`
