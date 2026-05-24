# Flickseed

A cinematic subway-map of films. Stations are concepts (mood, texture, register);
films are listed in a side panel when you click a station. Lines are curated
journeys through embedding space.

## Repo shape

```
app/             React + TypeScript renderer (Vite, Tailwind v4)
pipeline/        Python data pipeline (uv-managed) — writes data/layout.json
data/            layout.json (the contract) + corpus/ + derived artefacts
td/              TouchDesigner files (later)
.claude/skills/  Project-local Claude Code skills (see below)
```

## Run it

```bash
# Renderer (placeholder until the pipeline has output)
cd app && npm install && npm run dev

# Pipeline (stages are stubs in Phase 0b)
cd pipeline && uv sync && uv run python -c "import flickseed_pipeline"
```

Running entirely locally for now — no deploy.

## Claude skills

Two project-local skills under `.claude/skills/` drive the data work. They
auto-load when Claude Code is opened in this workspace; invoke with a slash.

- **`/probe-tmdb`** — iterate on TMDB `/discover` filter combinations to
  settle the canonical seed query. Generates `pipeline/scripts/get_films.py`;
  outputs `pipeline/reports/film-report.md` for visual review. Edit the
  boilerplate query catalog inside the skill as your taste sharpens.
- **`/embed-films`** — run the representation-learning pipeline (enrich →
  feature-extract → embed → graph node2vec → multi-view compose, per
  [`PROJECT.md` §5](./PROJECT.md#5-the-corpus-problem-highest-leverage-decision)).
  Writes `data/derived/embeddings.parquet` plus a top-5-similar diagnostic at
  `pipeline/reports/embedding-diagnostic.md`. View weights live in
  `pipeline/config.yaml` — tweak and re-invoke.

Workflow: `/probe-tmdb` settles the query → commit it under
`pipeline/flickseed_pipeline/ingest/` → `/embed-films` consumes it.

## Architecture

The system has two halves separated by a single contract file, `data/layout.json`:

- **pipeline/** (Python, uv) — ingests films from TMDB, builds multi-view embeddings, clusters them into stations, discovers line candidates, solves a Vignelli-style layout, and exports `layout.json`.
- **app/** (React 19 + TypeScript, Vite) — consumes `layout.json` and renders an SVG subway map. Films appear in a side panel on station click, not as dots on the map.

Neither side crosses the boundary. The pipeline writes; the app reads.

### Diagram

```mermaid
flowchart TB
    subgraph external["External"]
        tmdb["TMDB API<br><i>discover · keywords<br>credits · recommendations</i>"]
        userNotes["Your notes<br><i>optional, per-film</i>"]
    end

    subgraph pipelineSub["pipeline/ — Python, uv"]
        direction TB
        ingestStage["ingest/<br>seed query → films.json"]
        enrichStage["enrich/<br>keywords · credits · recs"]
        corpusStage["corpus/<br>per-film .md"]
        embedStage["embed/<br>multi-view vectors<br><i>text · keyword · crew · node2vec</i>"]
        diagGate{{"diagnostic:<br>top-5 similar"}}
        clusterStage["cluster/<br>BERTopic → stations"]
        nameStep["manual:<br>name stations"]
        graphStage["graph/<br>mutual k-NN +<br>candidate paths"]
        lineStep["manual:<br>curate 4–6 lines"]
        layoutStage["layout/<br>Vignelli solver<br><i>angles, spacing, transfers</i>"]
        exportStep["export.py"]

        ingestStage --> enrichStage --> corpusStage --> embedStage
        embedStage --> diagGate
        diagGate -- "go" --> clusterStage
        diagGate -- "no-go: tune weights" --> embedStage
        clusterStage --> nameStep --> graphStage --> lineStep --> layoutStage --> exportStep
    end

    subgraph dataSub["data/"]
        rawDir[("raw/<br><i>gitignored</i>")]
        corpusDir[("corpus/<br><i>committed</i>")]
        derivedDir[("derived/<br>embeddings · stations ·<br>station_graph · paths")]
        layoutFile[/"layout.json<br><b>the contract</b>"\]
        personalFile[/"personal.json<br><i>downstream overrides</i>"\]
    end

    subgraph renderersSub["Renderers"]
        direction TB
        subgraph appSub["app/ — React + TS, Vite"]
            mapView["Map — SVG<br>District · Line · Transfer · Station layers"]
            sidePanel["SidePanel<br><i>films for selected station</i>"]
            settingsPanel["SettingsPanel<br><i>writes personal.json</i>"]
        end
        tdRenderer["td/ — TouchDesigner<br><i>cinematic render, later</i>"]
    end

    tmdb --> ingestStage
    tmdb --> enrichStage
    userNotes -.-> corpusStage

    ingestStage --> rawDir
    enrichStage --> rawDir
    corpusStage --> corpusDir
    embedStage --> derivedDir
    clusterStage --> derivedDir
    graphStage --> derivedDir
    exportStep --> layoutFile

    layoutFile --> mapView
    layoutFile --> tdRenderer
    personalFile -.-> mapView
    settingsPanel -.-> personalFile
    mapView <--> sidePanel

    classDef contract fill:#1f2937,stroke:#f59e0b,stroke-width:2px,color:#fef3c7
    classDef manual fill:#374151,stroke:#a78bfa,color:#ede9fe
    classDef gate fill:#374151,stroke:#34d399,color:#d1fae5
    class layoutFile contract
    class nameStep,lineStep manual
    class diagGate gate
```
