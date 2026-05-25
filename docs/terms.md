# Flickseed Terms

A glossary of concepts, pipeline stages, and vocabulary used in this project. Terms are grouped by domain — start with **Core Concepts** if you're reading top-to-bottom.

---

## Core Concepts

**Station**
A thematic cluster of films that share some combination of tone, themes, and creative DNA. Stations are the nodes on the subway map — each one represents a concept, not an individual film. The project targets ~25–40 stations. Station shapes on the map encode how many lines pass through them: solid dot (1 line), ring (2 lines / transfer), double ring (3+ lines / hub).

**Film**
One of ~150 curated entries sourced from TMDB. Films don't appear as dots on the map. They live inside stations and show up in the side panel when you click a station. A film's station assignment comes from clustering its embedding vector.

**Line**
A curated path connecting 4–6 stations through the station graph. Lines are the spine of the visualization — they define journeys through embedding space. Each line follows a single geometric angle (0, 45, 90, or 135 degrees). Not every station has to be on a line.

**Station Graph**
The network of stations connected by edges. Edges come from mutual k-nearest-neighbors (k=5–10): two stations are connected only if each considers the other a neighbor. This avoids hubs and orphans. The graph is what line discovery searches through.

**Layout**
The final geometric arrangement of stations and lines on the map, solved under Vignelli constraints (uniform spacing, fixed angles, no overlaps). The layout is exported to `data/layout.json`, which is the single contract file between the pipeline and the renderer.

---

## Pipeline Stages

The pipeline runs in order: **ingest → enrich → corpus → embed → cluster → graph → layout → export**. Each stage reads from and writes to `data/`.

**Ingest**
Fetches films from the TMDB `/discover` endpoint using `get_films.py --mode finalize`. Outputs `data/raw/films.csv` with keywords and credits baked in.

**Enrich**
Parses `data/raw/films.csv` into structured JSON for downstream stages. No API calls — keywords and credits are baked into the CSV at finalize time. Outputs `data/raw/keywords.json` and `data/raw/credits.json`.

**Corpus**
Generates one markdown document per film in `data/corpus/`. Each doc contains the TMDB overview plus optional hand-written personal notes. These documents are the text input to the embedding stage.

**Embed**
Converts each film into an 896-dimensional vector by combining four signal views (see Multi-View Embedding below). A graph view via node2vec is upcoming and will add ~128 dimensions. Outputs `data/derived/embeddings.parquet`. This is the most consequential stage — everything downstream depends on embedding quality.

**Cluster**
Runs BERTopic on the embedding vectors to group films into stations. The `min_topic_size` parameter controls how many stations you get (target 25–40). Outputs `data/derived/stations.json` with film-to-station mappings and auto-generated keywords per station. After clustering, you hand-write evocative station names.

**Graph**
Builds the station graph via mutual k-NN and discovers candidate paths through it. Outputs `data/derived/station_graph.json` and `data/derived/candidate_paths.json` (top-50 ranked paths). You then hand-select 4–6 lines from the candidates.

**Layout**
Solves geometric constraints for the Vignelli-style map: line angles, uniform spacing, transfer station coincidence, no overlaps. Uses UMAP positions as hints but doesn't follow them literally.

**Export**
Produces `data/layout.json` — the contract file. The pipeline writes it; the React app reads it. Neither side crosses this boundary.

---

## Multi-View Embedding

The embed stage doesn't just look at plot summaries. It combines four parallel signals into one vector per film, which is what prevents stations from collapsing into genre buckets.

**Overview View** (384 dimensions)
Text semantics from the TMDB overview, embedded via `sentence-transformers/all-MiniLM-L6-v2`. Risk: overviews tend to emphasize genre, so this view alone would cluster by genre rather than texture.

**Keywords View** (64 dimensions)
TMDB community-tagged keywords (e.g., "dystopia," "time travel"), multi-hot encoded then PCA-reduced. Finer-grained than genre — keywords capture specific thematic motifs.

**Crew View** (64 dimensions)
Creative fingerprint based on director, writer, DP, composer, and editor co-occurrence. Captures shared sensibilities — e.g., all Roger Deakins films register as similar because they share a DP. Sparse co-occurrence matrix, PCA-reduced.

**Notes View** (384 dimensions, optional)
Personal hand-written annotations (1–2 sentences per film in `data/notes/{tmdb_id}.md`). Embedded like Overview. Produces a zero vector if no note exists. This is the upstream personalization lever — your notes shift where films land in embedding space.

**Graph View** (upcoming, ~128 dimensions)
Node2vec random walks over the TMDB `/recommendations` graph. Captures "people-who-liked-X-also-liked-Y" texture that no text field provides. Not yet implemented — tracked as FLI-40.

**Vector Composition**
Each view is weighted (configurable in `pipeline/config.yaml`), the weighted views are concatenated into a single vector (currently 896-dim; will grow when graph view lands), and the result is L2-normalized to unit length. Current weights are initial values — the diagnostic gate tells you when to tune them.

---

## Quality Gates

**Seed Curation**
Looking at the ~150 films and removing entries that aren't traditional films — things like concert films (TAYLOR SWIFT | THE ERAS TOUR), music videos (Michael Jackson's Thriller), TV specials (Doctor Who: The Day of the Doctor), or documentaries (BLACKPINK: Light Up the Sky). These show up because the TMDB discover queries cast a wide net (the zeitgeist preset grabs whatever's popular). They create noise in the embedding space — you'll see nonsensical nearest-neighbor results like The Wild Robot's closest match being the Taylor Swift Eras Tour. Cleaning these out means cleaner clusters downstream. It's optional but worth a quick pass, and it matters because bad seed entries cascade: noisy embeddings lead to incoherent clusters lead to a subway map where stations don't make intuitive sense.

**Embedding Diagnostic** (the go/no-go gate)
Sample 10 random films, compute their top-5 most-similar neighbors by cosine similarity, and check whether the neighbors make intuitive sense. The verdict:
- "Tonally adjacent across genre/era" → proceed to clustering
- "Same genre, same era" → the embedding is genre-dominated; tune view weights and re-embed
- "Mixed" → investigate per-view signals

This diagnostic is your chance to catch problems before they compound. The embedding plot shows you what the clustering stage will see — if neighbors don't make sense here, stations won't make sense either.

**Signal Tuning**
If the diagnostic shows genre clustering, raise non-text weights (crew, keywords) and lower the overview weight. Weights live in `pipeline/config.yaml`. Re-running the embedding doesn't require re-calling TMDB because per-view sub-vectors are cached in the parquet file.

---

## Personalization

**Upstream Personalization** (geometry)
Personal notes injected into the corpus before embedding. These change which films cluster together and are baked into the final layout. Affects the shape of the map itself.

**Downstream Personalization** (presentation)
Runtime overrides in the React app's SettingsPanel — renaming stations, reordering films within a station, pinning/hiding films, editing line definitions. Stored in `data/personal.json`. Does not change map geometry, only how it reads.

---

## Rendering

**Vignelli Aesthetic**
The visual discipline of the map, inspired by Massimo Vignelli's 1972 NYC subway map. Geometric, abstract, high whitespace. Lines at fixed angles (0/45/90 degrees). Station shapes encode connectivity. Labels are hand-placed (no algorithmic collision solving).

**React + SVG Pattern**
React owns the DOM via JSX (`<circle>`, `<path>`, `<text>`). d3 is used for math only — scales, projections, zoom transforms. No `d3.select()` or `.enter().append()`. This keeps rendering declarative and avoids the React-vs-d3 DOM fight.

**Contract File** (`data/layout.json`)
The single artifact that connects the pipeline to the renderer. The pipeline writes it; the React app reads it. Vite serves it at `/layout.json`. No intermediate computation happens in the renderer — it draws what the file says.

---

## Data Discovery

**TMDB Discover**
The `/discover/movie` endpoint that seeds the film list. Key filters:
- `vote_count.gte` — the biggest lever; controls how mainstream vs. obscure the results are
- `vote_average.gte` — quality floor
- `with_genres` / `without_genres` — genre IDs
- `with_keywords` / `without_keywords` — TMDB keyword IDs
- `without_companies` — strips franchise/studio bias (e.g., excluding MCU's company ID 420)

**Presets**
Pre-configured discover query templates: *canon-quality* (well-known, high-rated), *long-tail* (deeper cuts), *per-language*, *era-sweep* (one query per decade), *zeitgeist* (most popular regardless of quality).

---

## Line Discovery

**Path Scoring**
Candidate paths through the station graph are scored on three criteria:
- **Local coherence** — consecutive stations are highly similar
- **Global drift** — endpoint stations are semantically distant (the line covers ground)
- **Monotonicity** — the path moves forward through embedding space without doubling back

A diversity filter ensures selected lines don't overlap too much (max 30% shared stations between any two lines).

---

## Key Algorithms

**BERTopic**
The topic modeling algorithm used to cluster film embeddings into stations. It finds natural groupings in high-dimensional space. The `min_topic_size` parameter is the main tuning lever for controlling station count.

**Mutual k-NN**
The edge rule for the station graph. Two stations are connected only if each independently considers the other a k-nearest neighbor. This is stricter than one-directional k-NN and avoids creating hub stations that connect to everything.

**UMAP**
Dimensionality reduction used for visualization and as layout hints. Projects 896-dim vectors down to 2D so you can see the embedding space. The layout solver uses UMAP positions as starting points but overrides them with Vignelli constraints.

**PCA**
Principal Component Analysis, used to reduce the dimensionality of the keywords and crew views before concatenation. Keeps the most informative signal while compressing sparse high-dimensional data.

---

## Directory Structure

| Path | What's in it | Git status |
|------|-------------|------------|
| `data/raw/films.csv` | Seed films with keywords + credits baked in | committed |
| `data/raw/keywords.json` | Per-film keyword tags (parsed from CSV) | committed |
| `data/raw/credits.json` | Per-film crew (parsed from CSV) | committed |
| `data/corpus/` | Per-film markdown documents | committed — hand-curated |
| `data/notes/` | Optional personal notes per film | committed |
| `data/derived/` | Embeddings, stations, graph, candidate paths | committed |
| `data/layout.json` | The contract file | committed |
| `data/personal.json` | Downstream overrides | TBD |
| `pipeline/config.yaml` | View weights and model parameters | committed |
