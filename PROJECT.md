
# Flickseed — Project Overview

A cinematic subway-map of films. Concept stations, hand-curated lines,
React/SVG renderer over a Python pipeline.

This document is the source of truth for architectural decisions. Update it as
you make them. Bring it into new conversations to skip re-explaining the project.

---

## 1. The shape of the thing

**What it is.** An interactive map where stations are *cinematic concepts* (mood,
texture, register) and films are listed in a side panel when you click a station.
Lines connect concepts as journeys through embedding space.

**What it is not.** Not an IMDb visualization. Not one-station-per-film.
Not a recommendation engine. Not the original Letterboxd-style logging app
this repo started as — that's being stripped out.

**Aesthetic anchor.** Vignelli NYC subway — geometric, abstract, angles at
0°/45°/90°, lines as the dominant visual element, whitespace as structural.

**End use.** Local web app for now (Vite dev server). Hosting decision deferred —
will revisit once the renderer + a real pipeline run produce something worth
sharing. TouchDesigner as parallel cinematic-render output (later).

---

## 2. Core architectural decisions (locked)

| Decision | Choice | Why |
|---|---|---|
| What is a station? | Concept centroid in embedding space, ~25–40 total | Map of cinematic affect, not of films |
| What is a film? | Sublist content at a station, shown in side panel | Films don't appear on the map itself |
| Dataset size | Start ~150 curated films, grow if it works | Vignelli works at small scale |
| Curation philosophy | Mostly algorithmic, curate edges | Algorithm proposes, you select |
| Renderer stack | React + SVG (JSX), d3 for math only, Tailwind for styles | Matches existing repo; React owns DOM, d3 owns numbers |
| Pipeline stack | Python in `pipeline/` subdirectory, uv-managed | Right tool for embeddings/clustering; isolated from app |
| Pipeline → app contract | `data/layout.json` committed to repo | Pipeline writes, app reads, neither owns the data dir |
| Hosting | Local Vite dev server (for now) | Iterating locally until there's something worth sharing; deploy choice deferred |
| Edge type for graph | Mutual k-NN (k=5–10) | Uniform local density; thresholds create hubs+orphans |
| Clustering | BERTopic (stations + keywords in one pass) | Solves naming problem |
| Station naming | Hand-written, evocative, not genre-y | This is where the project's voice lives |
| Line definition | 4–6 curated paths through station graph | Lines are the spine; not all stations need to be on one |
| TouchDesigner | Parallel render, reads same `layout.json` | Cinematic medium, web is the navigable one |

---

## 3. Pipeline

```
TMDB seeds + Wikipedia + your notes + reviews
        │
        ▼  pipeline/flickseed_pipeline/ingest/
data/raw/*.json
        │
        ▼  pipeline/flickseed_pipeline/corpus/
data/corpus/*.md  (~200–300 token text per film)
        │
        ▼  pipeline/flickseed_pipeline/embed/
data/derived/embeddings.parquet
        │
        ├─► diagnostic: top-5-similar test  ◄── go/no-go gate
        │
        ▼  pipeline/flickseed_pipeline/cluster/
data/derived/stations.json
        │
        ▼  manual: name_stations.md
        │
        ▼  pipeline/flickseed_pipeline/graph/
data/derived/station_graph.json
data/derived/candidate_paths.json
        │
        ▼  manual: lines.json (curate 4–6 from candidates)
        │
        ▼  pipeline/flickseed_pipeline/layout/
        │
        ▼  pipeline/flickseed_pipeline/export.py
data/layout.json   ← the contract
        │
        ├─► React renderer (app/, GitHub Pages)
        └─► TouchDesigner renderer (td/, later)
```

**The contract.** `data/layout.json` is the boundary between pipeline and renderers.
Pipeline produces it; renderers consume it; neither renderer computes layout.

---

## 4. Repo layout

```
flickseed/
├── README.md                      ← public-facing; what this is
├── PROJECT.md                     ← this file, architecture doc
│
├── app/                           ← React/TS app (renamed from src/)
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── routes/
│   │   │   └── map/               ← the metro map view
│   │   ├── lib/
│   │   │   ├── layout.ts          ← loads data/layout.json
│   │   │   └── github.ts          ← reused from old code if needed
│   │   └── components/
│   ├── package.json
│   ├── vite.config.ts
│   └── index.html
│
├── pipeline/                      ← Python, uv-managed, self-contained
│   ├── pyproject.toml
│   ├── README.md
│   ├── flickseed_pipeline/
│   │   ├── ingest/
│   │   ├── corpus/
│   │   ├── embed/
│   │   ├── cluster/
│   │   ├── graph/
│   │   ├── layout/
│   │   └── export.py
│   └── scripts/
│       ├── run_pipeline.py
│       └── diagnose_embeddings.py
│
├── data/
│   ├── raw/                       ← gitignored (large, regenerable)
│   ├── corpus/                    ← committed (hand-written, the asset)
│   ├── derived/                   ← committed (small, useful in history)
│   └── layout.json                ← committed, the contract
│
├── td/                            ← TouchDesigner files (later)
│
├── .gitignore
└── pipeline/.env.example          ← TMDB_API_KEY for ingest
```

**Done in Phase 0 (commit history if you want details):**
- Stripped `src/pages/`, `src/lib/{auth,github,tmdb}.ts`, `data/users/`, `src/components/Layout.tsx`
- TMDB URL patterns ported into `pipeline/flickseed_pipeline/ingest/__init__.py` docstring
- Moved Vite/Tailwind/TS scaffolding under `app/`
- Dropped `.github/workflows/deploy.yml` (no GH Pages for now)

---

## 5. The corpus problem (highest-leverage decision)

Embeddings are only as good as text. TMDB overviews → genre-recognizer, boring.

**Sources, in priority order:**
1. **Wikipedia plot + reception** — free, clean API, surprisingly rich
2. **Your own notes** — 1–2 sentences per film in your voice; pushes embedding space toward *your* taste axes
3. **TMDB metadata** — title, year, director, country, keywords
4. **Review excerpts** — Letterboxd if accessible (gray area), RT blurbs if not
5. **Editorial criticism** — Criterion, Sight & Sound where they exist

**Per-film text template** (~200–300 tokens):
```
[Title] ([Year], dir. [Director], [Country])

[Wikipedia plot, condensed to ~80 tokens]

Your one-liner: [1–2 sentences in your voice about texture/feel]

Atmosphere: [5–10 affective descriptors]

[1 vivid sentence from a critic/Letterboxd review]
```

**Diagnostic test** (run after every corpus revision):
- For 10 random films, print top-5 most similar
- If results = "same genre, same era" → corpus too genre-loaded; add more affective text
- If results = "tonally adjacent across genre/era" → embeddings working; proceed

---

## 6. Subway lines

**Definition.** A line is a path through the station graph (station-to-station,
not film-to-film) where:
- Local coherence high: consecutive stations are highly similar
- Global drift high: endpoint stations are semantically distant
- Monotonicity preserved: path moves forward through embedding space

**Algorithm:**
1. Pick endpoint pairs: high-centrality stations in different "regions"
2. For each pair: find all simple paths up to length 8, compute
   `score = local_coherence × drift × monotonicity × length_bonus`
3. Apply diversity filter (≤30% node overlap between selected paths)
4. Output top 50 ranked candidate paths

**Curation:** read the top 50, pick 4–6 that resonate. ~1 hour of work.

**Station shape encodes line membership:**
- 1 line: solid dot
- 2 lines: ring (transfer station)
- 3+ lines: double ring (major hub)

---

## 7. The Vignelli layout problem

~25–40 stations on a constrained grid.

**Inputs:** station list, line definitions, UMAP positions (used as *hints* only).

**Constraints:**
- Each line follows a single angle (0°, 45°, 90°, 135°)
- Stations on a line have uniform spacing
- Transfer stations coincide between lines
- Lines fan out, don't overlap
- Districts (clusters of stations) stay roughly coherent

**Approach:** greedy. Place longest line first along its preferred angle. Anchor
each subsequent line at its transfer station and rotate. Resolve collisions by
sliding lines along axis.

**Manual label placement.** Store per-station `labelOffset` in layout.json. One
hour by hand vs. weeks of solver tuning.

---

## 8. Rendering — React + SVG

**Discipline:** structure is fixed, decoration breathes.
- Animate: hover glow, station pulse on selection, train-traversal on selected line
- Don't animate: station positions, line angles, district shapes

**React + d3 pattern:**
- React renders all SVG elements declaratively (JSX `<circle>`, `<path>`, `<text>`)
- d3 used only for math: scales, projections, zoom math
- No `d3.select`, no `.enter().append()`, no d3 DOM mutation
- Tailwind for static styles; CSS transitions for hover; React state for selection

**Component tree:**
```
<MapPage>
  <Map>                          ← stateless, renders from layout.json + selection
    <defs>                       ← gradients, glow filters
    <DistrictLayer />            ← background polygons/shading
    <LineLayer />                ← strokes + glow doubles per line
    <TransferLayer />            ← rings at junctions
    <StationLayer />             ← halo + body + core per station
    <OverlayLayer />             ← selection/hover indicators
  </Map>
  <SidePanel>                    ← stateless, renders selected station's films
    <FilmList />
  </SidePanel>
  <SearchBox />                  ← typeahead → camera pan
</MapPage>
```

State management: React context or a small Zustand store, depending on what
already exists in the codebase. Selection state syncs to URL (`?station=...`).

**Interaction model:**
- Hover station → halo brightens, passing lines highlight, *side panel does not change*
- Click station → selection locks; lines through it brighten, others dim 30%; side panel populates
- Click line → side panel switches to journey view; map dims everything else
- Search → autocomplete by film/station name → camera pans to home station

**Loading layout.json:** fetched at runtime from `/layout.json`. Vite serves
the repo's `data/` directory as the dev `publicDir` (see `app/vite.config.ts`),
so pipeline runs are picked up on next page reload without rebuilding the app.

---

## 9. Rendering — TouchDesigner (parallel, later)

Reads same `data/layout.json`. Provides cinematic affordances web can't.

**Architecture:**
- DAT loads layout.json
- CHOPs derive per-instance position/color/animation phase
- Geometry COMP instances station-template.tox N times
- Line SOPs render polylines per line
- Bloom/glow TOPs composite final image

**Use cases:** video exports, installation mode, large-format renders, VJ backdrop.

---

## 10. Build order

| Phase | Days | What |
|---|---|---|
| 0 | done | Strip the existing logging features; move `src/` → `app/src/`; verify build still works |
| 0b | done | Scaffold `pipeline/` with uv; empty package; verify pipeline builds and imports |
| 1 | 1 | TMDB ingestion of 150 seed-derived films (Python port of existing tmdb.ts) |
| 2 | 1 | Corpus template generator (Wikipedia + RT pull, draft .md per film) |
| 3 | 0.5 | First embedding pass + top-5 diagnostic |
| 3b | ongoing | **Hand-edit corpus, 10–20 films/evening, in parallel** |
| 4 | 1 | BERTopic → stations + keywords |
| 5 | 0.5 | Hand-name stations |
| 6 | 1 | Station graph + path-discovery CLI |
| 7 | 0.5 | Curate lines |
| 8 | 2–3 | Vignelli layout solver |
| 9 | 0.5 | Export layout.json |
| 10 | 4–5 | React renderer: static first, then interactions |
| 11 | parallel | TouchDesigner renderer |

**Total:** ~2 weeks of focused work + background corpus editing.

---

## 11. Known risks + mitigations

| Risk | Mitigation |
|---|---|
| Embeddings cluster by genre, not texture | Corpus augmentation; diagnostic catches early |
| Top candidate paths feel boring | Means corpus problem upstream; don't fix in algorithm |
| BERTopic produces wrong topic count | Sweep `min_topic_size`; aim for 25–40 |
| Vignelli solver fails | Reduce line count; lines ≤6 to be solvable |
| Mixed-stack repo confusion | Clear `app/` vs `pipeline/` boundary, separate READMEs |
| Label collisions | Hand-place; don't solve |
| Corpus work feels endless | 5–10 min/film; uneven detail is fine |

---

## 12. Decisions still pending

- **Letterboxd corpus access** — gray-area scraping vs. forgoing
- **Topic count target** — let BERTopic decide vs. manual sweep
- **District definition** — clusters of stations? hand-drawn polygons? color regions?
- **Film ordering within station** — closeness-to-centroid? year? personal?
- **Off-line stations** — show stations not on any named line? how?
- **Mobile layout** — abandon the map, list-only? rotate-only?
- **Cold-start UX** — what does the user see before clicking?
- **Search match scope** — titles only, or +directors +station names?
- **Color palette** — anchored to which references?
- **Typography** — geometric sans-serif (Vignelli) vs. cinematic alternative
- **Hosting** — deferred until there's something worth deploying (was GH Pages)

---

## 13. Deferred to later phases

- Audio reactivity (TD only)
- User-input "find a journey between these two films" feature
- Public film submissions / community corpus
- Annotations / shareable saved routes
- Multi-user instances
- Animation polish, transition choreography
- About / credits page

---

## 14. Conversational context (for re-priming Claude)

This project's architecture was developed across several rounds of conversation.
Key decisions that took place:

1. Started from a plan where every film = a station (too many nodes, too IMDb-like)
2. Reframed to concept-stations with films as sublist content
3. Decided side panel for films, not film-dots on the map
4. Chose mutual k-NN over similarity threshold for graph edges
5. Identified corpus quality as the #1 bottleneck
6. Locked Vignelli geometric abstraction as aesthetic anchor
7. **Pivoted from a separate vanilla d3 renderer to building on top of the existing
   Flickseed React/TS scaffold; stripped out the original Letterboxd-style logging
   features but kept the Vite/Tailwind/GitHub-Pages infrastructure**
8. Pipeline in Python lives in `pipeline/`, communicates with React app only
   via committed `data/layout.json`
9. **Dropped the GitHub Pages constraint** — running entirely locally until the
   thing reaches a good working state. Vite serves `data/` directly; no deploy
   plumbing. Source control still lives on GitHub.

When bringing this doc into a new conversation, that's enough background.

---

*Last updated: 2026-05-23*
