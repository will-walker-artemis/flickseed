# Flickseed architecture

A bird's-eye view of how the pieces fit together. The Python pipeline turns
TMDB data into a geometric subway-map layout; renderers consume that layout
through a single committed contract: `data/layout.json`.

For decisions, rationale, and build order see [`../PROJECT.md`](../PROJECT.md).

```mermaid
flowchart TB
    %% ─────────────── External ───────────────
    subgraph external["External"]
        tmdb["TMDB API<br/><i>/discover, /keywords,<br/>/credits, /recommendations</i>"]
        notes["Your notes<br/><i>(optional, per-film)</i>"]
    end

    %% ─────────────── Pipeline ───────────────
    subgraph pipeline["pipeline/ — Python (uv)"]
        direction TB
        ingest["ingest/<br/>seed query → films.json"]
        enrich["enrich/<br/>keywords · credits · recs"]
        corpus["corpus/<br/>per-film .md (overview + notes)"]
        embed["embed/<br/>multi-view vectors<br/><i>text · keyword · crew · node2vec</i>"]
        diag{{"diagnostic:<br/>top-5 similar"}}
        cluster["cluster/<br/>BERTopic → stations"]
        name["manual:<br/>name stations"]
        graph["graph/<br/>mutual k-NN +<br/>candidate paths"]
        lines["manual:<br/>curate 4–6 lines"]
        layout["layout/<br/>Vignelli solver<br/><i>(angles, spacing, transfers)</i>"]
        export["export.py"]

        ingest --> enrich --> corpus --> embed
        embed --> diag
        diag -- "go" --> cluster
        diag -- "no-go: tune weights" --> embed
        cluster --> name --> graph --> lines --> layout --> export
    end

    %% ─────────────── Data ───────────────
    subgraph data["data/"]
        raw[("raw/<br/><i>gitignored</i>")]
        corpusDir[("corpus/<br/><i>committed</i>")]
        derived[("derived/<br/>embeddings · stations ·<br/>station_graph · paths")]
        layoutJson@{ shape: doc, label: "<b>layout.json</b><br/><i>the contract</i>" }
        personal@{ shape: doc, label: "personal.json<br/><i>downstream overrides</i>" }
    end

    %% ─────────────── Renderers ───────────────
    subgraph renderers["Renderers"]
        direction TB
        subgraph app["app/ — React + TS (Vite)"]
            mapView["Map (SVG)<br/>District · Line · Transfer · Station layers"]
            side["SidePanel<br/><i>films for selected station</i>"]
            settings["SettingsPanel<br/><i>writes personal.json</i>"]
        end
        td["td/ — TouchDesigner<br/><i>cinematic render (later)</i>"]
    end

    %% ─────────────── Wiring ───────────────
    tmdb --> ingest
    tmdb --> enrich
    notes -.-> corpus

    ingest --> raw
    enrich --> raw
    corpus --> corpusDir
    embed --> derived
    cluster --> derived
    graph --> derived
    export --> layoutJson

    layoutJson --> mapView
    layoutJson --> td
    personal -.-> mapView
    settings -.-> personal
    mapView <--> side

    %% ─────────────── Styling ───────────────
    classDef contract fill:#1f2937,stroke:#f59e0b,stroke-width:2px,color:#fef3c7
    classDef manual fill:#374151,stroke:#a78bfa,color:#ede9fe
    classDef gate fill:#374151,stroke:#34d399,color:#d1fae5
    class layoutJson contract
    class name,lines manual
    class diag gate
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
