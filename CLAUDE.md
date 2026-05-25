# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flickseed is a cinematic subway-map visualization. Films are organized into concept-stations via embedding and clustering, connected by curated lines, and rendered as a Vignelli-style subway map. The system has two halves:

- **pipeline/** — Python (uv-managed) data pipeline that ingests films from TMDB, builds embeddings, clusters stations, discovers paths, solves layout, and exports `data/layout.json`
- **app/** — React 19 + TypeScript + Vite renderer that consumes `data/layout.json` and draws an SVG subway map

The boundary is **`data/layout.json`** — the single contract file. Pipeline produces it; the React app renders it. Neither side crosses this boundary.

## Commands

### Frontend (run from `app/`)

```bash
npm run dev         # Vite dev server at localhost:5173
npm run build       # tsc -b + vite build
npm run typecheck   # tsc -b only
npm run preview     # preview production build
```

### Pipeline (run from `pipeline/`)

```bash
uv sync                                       # install/update deps
uv run python scripts/run_pipeline.py          # full pipeline (stub)
uv run python scripts/diagnose_embeddings.py   # top-5-similar diagnostic
```

Pipeline requires `TMDB_API_KEY` — copy `pipeline/.env.example` to `pipeline/.env` and fill it in.

## Architecture

### Pipeline stages (each reads/writes `data/`)

```
ingest → enrich → corpus → embed → cluster → graph → layout → export
```

- **ingest/enrich**: TMDB API → `data/raw/films.json`, keywords, credits, recommendations
- **corpus**: per-film markdown documents in `data/corpus/`
- **embed**: multi-view vectors (sentence-transformer + PCA + node2vec) → `data/derived/embeddings.parquet`
- **cluster**: BERTopic → `data/derived/stations.json` (25-40 stations)
- **graph**: mutual k-NN → `data/derived/station_graph.json` + `candidate_paths.json`
- **layout**: Vignelli solver (0°/45°/90° angles)
- **export**: produces `data/layout.json`

### Frontend rendering pattern

React owns DOM via JSX (`<circle>`, `<path>`, `<text>`). d3 is used for math only (scales, projections, zoom) — no `d3.select()` or `.enter().append()`. Tailwind CSS v4 for styling. Vite serves `data/` as `publicDir` so `layout.json` is available at `/layout.json`.

### Planned component tree

```
<MapPage>
  <Map>  DistrictLayer / LineLayer / TransferLayer / StationLayer / OverlayLayer
  <SidePanel>  FilmList (shown on station select)
  <SettingsPanel>  StationOverrides / FilmOverrides / LineOverrides
  <SearchBox/>
```

Films appear in the side panel when a station is selected — they are not dots on the map.

## Key Decisions (locked)

- ~150 curated films, ~25-40 stations, 4-6 lines
- Clustering via BERTopic; edge type is mutual k-NN (k=5-10)
- Station names are hand-written and evocative
- Lines are manually curated from algorithmically ranked candidates
- TypeScript strict mode; no tests yet (planned for renderer phase)

## Custom Skills

- `/data-discovery-tmdb` — interactive TMDB `/discover` exploration; iterates queries with the user and writes reports under `pipeline/reports/`
- `/embed-films` — run multi-view embedding pipeline, outputs `data/derived/embeddings.parquet` + diagnostic

Both skills check TMDB_API_KEY and ping the API before running.

## PR Workflow

Before creating a PR, review this file and update it if your changes affect the architecture, commands, pipeline stages, key decisions, or skills documented here.

## Reference Documents

- **PROJECT.md** — source of truth for architecture, build order, and all decisions
- **pipeline/README.md** — operational guide for pipeline stages
- **docs/architecture.md** — mermaid diagram
