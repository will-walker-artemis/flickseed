
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
TMDB discover seed query (+ your notes, optional)
        │
        ▼  pipeline/flickseed_pipeline/ingest/
data/raw/films.json
        │
        ▼  pipeline/flickseed_pipeline/enrich/   (TMDB /keywords, /credits, /recommendations per film)
data/raw/{keywords,credits,recommendations}.json
        │
        ▼  pipeline/flickseed_pipeline/corpus/
data/corpus/*.md  (TMDB overview + optional notes per film)
        │
        ▼  pipeline/flickseed_pipeline/embed/    (multi-view: text + keyword + crew + graph node2vec)
data/derived/embeddings.parquet  (concatenated, L2-normalized per §5)
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
        ├─► React renderer (app/, local Vite dev server)
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
├── CLAUDE.md                      ← Claude Code orientation
│
├── app/                           ← React/TS app
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── routes/
│   │   │   └── map/               ← the metro map view
│   │   ├── lib/                   ← (planned) layout.ts loads /layout.json
│   │   └── components/            ← (planned)
│   ├── package.json
│   ├── vite.config.ts             ← publicDir: ../data
│   └── index.html
│
├── pipeline/                      ← Python, uv-managed, self-contained
│   ├── pyproject.toml
│   ├── README.md
│   ├── flickseed_pipeline/
│   │   ├── ingest/                ← canonical /discover query
│   │   ├── enrich/                ← per-film TMDB endpoints
│   │   ├── corpus/
│   │   ├── embed/
│   │   ├── cluster/
│   │   ├── graph/
│   │   ├── layout/
│   │   └── export.py
│   └── scripts/
│       ├── get_films.py           ← TMDB /discover probe CLI
│       ├── run_pipeline.py        ← (stub)
│       └── diagnose_embeddings.py ← (stub)
│
├── data/
│   ├── raw/                       ← committed (TMDB /discover output + per-film enrichment)
│   ├── corpus/                    ← committed (TMDB overview + optional notes)
│   ├── derived/                   ← committed (embeddings, stations, graph)
│   └── layout.json                ← committed, the contract
│
├── docs/
│   ├── architecture.md
│   └── data-discovery.md
│
├── .claude/skills/
│   ├── data-discovery-tmdb.md
│   └── embed-films.md
│
├── td/                            ← TouchDesigner files (later)
│
├── .gitignore
└── pipeline/.env.example          ← TMDB_API_KEY
```

**Done in Phase 0 (commit history if you want details):**
- Stripped `src/pages/`, `src/lib/{auth,github,tmdb}.ts`, `data/users/`, `src/components/Layout.tsx`
- TMDB URL patterns ported into `pipeline/flickseed_pipeline/ingest/__init__.py` docstring
- Moved Vite/Tailwind/TS scaffolding under `app/`
- Dropped `.github/workflows/deploy.yml` (no GH Pages for now)

---

## 5. The corpus problem (highest-leverage decision)

Embeddings are only as good as the signal we give them. TMDB overviews alone
tend toward genre-recognizer output. The mitigation is **multi-view
vectorization** across multiple TMDB signals, not richer text.

**Signals, in priority order:**
1. **TMDB metadata** — overview, keywords, credits, genres, country, language, year
2. **TMDB recommendation graph** — node2vec over `/recommendations` captures
   "people-who-liked-X-also-liked-Y" texture not present in any text field
3. **Your own notes** *(optional)* — 1–2 sentences per film in your voice;
   injected into corpus text before embedding so they shift the map's geometry
4. **Deferred** — Wikipedia plot + reception, Letterboxd reviews

**Per-film vector** (concatenated, L2-normalized):
```
[ overview_embed | keyword_multihot_PCA | crew_sparse_PCA
  | recommendation_node2vec | your_notes_embed (optional) ]
```

Tunable weights per view. Raise `recommendation_node2vec` if the diagnostic
shows genre-clustering.

**Diagnostic test** (run after every embedding revision):
- For 10 random films, print top-5 most similar
- If results = "same genre, same era" → raise non-text view weights and add notes
- If results = "tonally adjacent across genre/era" → proceed

**Two personalization paths** (intentional, separate concerns):
- **Upstream (geometry):** your notes enter signal #3 above and are embedded
  with the rest. Changes which films cluster.
- **Downstream (presentation):** a `<SettingsPanel>` in the React app lets you
  override station names, reorder films within a station, pin/hide films, and
  curate line definitions. Changes how the map *reads*, not its shape.
  See §8 and §12.

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
  <SettingsPanel>                ← downstream personalization (see §5)
    <StationOverrides />         ← rename, pin, hide stations
    <FilmOverrides />            ← reorder/pin films within a station
    <LineOverrides />            ← curate / edit lines
  </SettingsPanel>
  <SearchBox />                  ← typeahead → camera pan
</MapPage>
```

**Downstream personalization storage.** Settings panel writes to
`data/personal.json` — a small overlay file the renderer merges on top of
`layout.json` at load time. The renderer reads two files: `layout.json` (the
geometry contract from the pipeline) + `personal.json` (your downstream
overrides). Commit status of `personal.json` is a pending decision (§12).

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
| 1 | 1 | TMDB ingestion via committed `/discover` seed query (iterate using `/data-discovery-tmdb` skill, then bake the query into `pipeline/flickseed_pipeline/ingest/`) |
| 2 | 1 | Enrichment pass — `/keywords`, `/credits`, `/recommendations` per seed (via `/embed-films` skill) |
| 3 | 1 | Multi-view embedding (overview + keyword + crew + node2vec) + top-5 diagnostic |
| 3b | ongoing | *Optional:* hand-write 1–2 sentence notes per film, re-embed; signal #3 in §5 |
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

- **`personal.json` commit status** — committed to git (shared, versioned) vs gitignored (private overlay)
- **Topic count target** — let BERTopic decide vs. manual sweep
- **District definition** — clusters of stations? hand-drawn polygons? color regions?
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
