# Flickseed architecture

A bird's-eye view of how the pieces fit together. The Python pipeline turns
TMDB data into a geometric subway-map layout; renderers consume that layout
through a single committed contract: `data/layout.json`.

For decisions, rationale, and build order see [`../PROJECT.md`](../PROJECT.md).

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

## Reading the diagram

- **Solid arrows** = data flow committed to disk or fetched from the network.
- **Dashed arrows** = optional inputs / overlays that don't change pipeline geometry.
- **Amber outline** marks `layout.json`, the single contract between pipeline
  and renderers — neither renderer computes layout.
- **Purple outlines** mark the two manual curation steps (station naming, line
  selection). Everything else runs unattended.
- **Green outline** is the go/no-go diagnostic gate; failing it loops back into
  embedding-weight tuning rather than continuing downstream.

## What lives where

| Path | Role |
|---|---|
| `pipeline/flickseed_pipeline/` | Stage packages (ingest, enrich, corpus, embed, cluster, graph, layout) + `export.py` |
| `pipeline/scripts/` | CLI entry points (`run_pipeline.py`, `diagnose_embeddings.py`) |
| `data/raw/` | TMDB responses — large, regenerable, gitignored |
| `data/corpus/` | Per-film markdown — committed; the hand-curated asset |
| `data/derived/` | Embeddings, stations, station graph, candidate paths — committed |
| `data/layout.json` | The contract. Pipeline writes, renderers read |
| `data/personal.json` | Renderer-side overrides (renames, pins, hides). Commit status pending — see PROJECT.md §12 |
| `app/src/` | React renderer; Vite serves `data/` as `publicDir` so layout changes reload without rebuilding |
| `td/` | TouchDesigner renderer, parallel consumer of `layout.json` (later phase) |
