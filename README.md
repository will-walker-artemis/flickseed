# Flickseed

A cinematic subway-map of films. Stations are concepts (mood, texture, register);
films are listed in a side panel when you click a station. Lines are curated
journeys through embedding space.

Architecture, decisions, and build order live in [`PROJECT.md`](./PROJECT.md).
Full diagram with legend and directory table in [`docs/architecture.md`](./docs/architecture.md).

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

## Repo shape

```
app/         React + TypeScript renderer (Vite, Tailwind v4)
pipeline/    Python data pipeline (uv-managed) — writes data/layout.json
data/        layout.json (the contract) + corpus/ + derived artefacts
td/          TouchDesigner files (later)
```

## Run it

```bash
# Renderer (placeholder until the pipeline has output)
cd app && npm install && npm run dev

# Pipeline (stages are stubs in Phase 0b)
cd pipeline && uv sync && uv run python -c "import flickseed_pipeline"
```

Running entirely locally for now — no deploy.
