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
ingest    TMDB seeds + Wikipedia + reviews -> data/raw/*.json
corpus    raw -> per-film ~200-300 token text -> data/corpus/*.md
embed     corpus -> data/derived/embeddings.parquet
cluster   embeddings -> data/derived/stations.json (BERTopic)
graph     stations -> data/derived/station_graph.json + candidate_paths.json
layout    stations + curated lines -> Vignelli grid positions
export    everything -> data/layout.json
```

## Scripts

- `scripts/run_pipeline.py` — end-to-end runner
- `scripts/diagnose_embeddings.py` — top-5-similar sanity check (the go/no-go gate)
