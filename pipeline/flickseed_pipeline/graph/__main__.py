"""Graph stage: station centroids → mutual k-NN edges + candidate path ranking.

How it works:
  1. Compute a centroid (mean embedding) for each station
  2. For each station, find its k nearest neighbors by cosine similarity
  3. Keep only MUTUAL edges — A→B exists only if B also has A in its top-k
     (this prevents hub stations from connecting to everything)
  4. Score candidate paths through the graph for line curation

Outputs:
    data/derived/station_graph.json     — nodes + edges
    data/derived/candidate_paths.json   — top ~50 ranked paths

Usage:
    uv run python -m flickseed_pipeline.graph
    uv run python -m flickseed_pipeline.graph --k 7
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
import networkx as nx

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "pipeline" / "config.yaml"
EMBEDDINGS_PATH = ROOT / "data" / "derived" / "embeddings.parquet"
STATIONS_PATH = ROOT / "data" / "derived" / "stations.json"
GRAPH_OUTPUT = ROOT / "data" / "derived" / "station_graph.json"
PATHS_OUTPUT = ROOT / "data" / "derived" / "candidate_paths.json"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def compute_station_centroids(
    stations: list[dict], embeddings: np.ndarray, tmdb_ids: list[int]
) -> dict[int, np.ndarray]:
    """Mean embedding vector per station."""
    tid_to_idx = {tid: i for i, tid in enumerate(tmdb_ids)}
    centroids = {}
    for s in stations:
        indices = [tid_to_idx[f["tmdb_id"]] for f in s["films"] if f["tmdb_id"] in tid_to_idx]
        if indices:
            centroid = embeddings[indices].mean(axis=0)
            centroid = centroid / np.linalg.norm(centroid)  # L2-normalize
            centroids[s["id"]] = centroid
    return centroids


def build_mutual_knn(centroids: dict[int, np.ndarray], k: int) -> list[tuple[int, int, float]]:
    """Build mutual k-NN graph. Returns edges as (station_a, station_b, similarity)."""
    ids = sorted(centroids.keys())
    vecs = np.stack([centroids[i] for i in ids])

    # Cosine similarity matrix (vectors are already L2-normalized)
    sim_matrix = vecs @ vecs.T

    # For each station, find top-k neighbors (excluding self)
    neighbors: dict[int, set[int]] = {}
    for i, sid in enumerate(ids):
        sims = sim_matrix[i].copy()
        sims[i] = -1  # exclude self
        top_k_indices = np.argsort(sims)[-k:]
        neighbors[sid] = {ids[j] for j in top_k_indices}

    # Keep only mutual edges
    edges = []
    seen = set()
    for sid_a, nbrs in neighbors.items():
        for sid_b in nbrs:
            if sid_a in neighbors.get(sid_b, set()):
                edge_key = (min(sid_a, sid_b), max(sid_a, sid_b))
                if edge_key not in seen:
                    seen.add(edge_key)
                    # Look up similarity
                    idx_a = ids.index(sid_a)
                    idx_b = ids.index(sid_b)
                    edges.append((sid_a, sid_b, float(sim_matrix[idx_a, idx_b])))

    return edges


def score_path(
    path: list[int], centroids: dict[int, np.ndarray]
) -> dict:
    """Score a candidate line path.

    Metrics:
      - local_coherence: average similarity between consecutive stations
      - drift: 1 - similarity between endpoints (higher = more diverse journey)
      - monotonicity: fraction of steps that move "forward" (away from start)
      - length_bonus: slight preference for longer paths (more interesting journeys)
    """
    if len(path) < 3:
        return {"score": 0, "local_coherence": 0, "drift": 0, "monotonicity": 0}

    vecs = [centroids[s] for s in path]

    # Local coherence: mean cosine sim between consecutive stations
    consecutive_sims = [
        float(np.dot(vecs[i], vecs[i + 1])) for i in range(len(vecs) - 1)
    ]
    local_coherence = np.mean(consecutive_sims)

    # Drift: how different are the endpoints
    endpoint_sim = float(np.dot(vecs[0], vecs[-1]))
    drift = 1.0 - endpoint_sim

    # Monotonicity: fraction of steps where distance from start increases
    start_vec = vecs[0]
    distances = [1.0 - float(np.dot(start_vec, v)) for v in vecs]
    forward_steps = sum(
        1 for i in range(1, len(distances)) if distances[i] > distances[i - 1]
    )
    monotonicity = forward_steps / (len(distances) - 1)

    # Length bonus: gently reward longer paths (log scale)
    length_bonus = np.log2(len(path))

    score = local_coherence * drift * monotonicity * length_bonus

    return {
        "score": float(score),
        "local_coherence": float(local_coherence),
        "drift": float(drift),
        "monotonicity": float(monotonicity),
        "length": len(path),
    }


def find_candidate_paths(
    G: nx.Graph, centroids: dict[int, np.ndarray], max_length: int = 8, top_n: int = 50
) -> list[dict]:
    """Find and rank candidate line paths through the station graph.

    Strategy: pick high-centrality endpoints in different regions, find all
    simple paths between them (up to max_length), score each, return top_n
    with diversity filtering.
    """
    # Use betweenness centrality to prioritize important stations as endpoints
    centrality = nx.betweenness_centrality(G)
    all_stations = sorted(G.nodes())

    # Find paths between pairs, prioritizing high-centrality endpoints
    # Use all stations (not just top-15) since our graph is small (~32 nodes)
    all_paths: list[dict] = []
    seen_pairs = set()

    for i, start in enumerate(all_stations):
        for end in all_stations[i + 1:]:
            pair_key = (min(start, end), max(start, end))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            # Find simple paths up to max_length
            try:
                paths = list(nx.all_simple_paths(G, start, end, cutoff=max_length))
            except nx.NetworkXError:
                continue

            for path in paths:
                if len(path) < 3:
                    continue
                metrics = score_path(path, centroids)
                all_paths.append({
                    "path": path,
                    "start": start,
                    "end": end,
                    **metrics,
                })

    # Sort by score
    all_paths.sort(key=lambda p: p["score"], reverse=True)

    # Diversity filter: reject paths with >40% node overlap with already-selected
    selected: list[dict] = []
    for candidate in all_paths:
        if len(selected) >= top_n:
            break
        candidate_nodes = set(candidate["path"])
        too_similar = False
        for existing in selected:
            existing_nodes = set(existing["path"])
            overlap = len(candidate_nodes & existing_nodes) / min(
                len(candidate_nodes), len(existing_nodes)
            )
            if overlap > 0.40:
                too_similar = True
                break
        if not too_similar:
            selected.append(candidate)

    return selected


def run(k: int | None = None) -> None:
    cfg = load_config()
    graph_cfg = cfg.get("graph", {})
    k = k or graph_cfg.get("k", 6)

    # Load stations
    with open(STATIONS_PATH) as f:
        stations_data = json.load(f)
    stations = stations_data["stations"]

    # Load embeddings for centroid computation
    df = pd.read_parquet(EMBEDDINGS_PATH)
    embeddings = np.stack(df["fused"].values)
    tmdb_ids = df["tmdb_id"].tolist()

    print(f"Building graph: {len(stations)} stations, k={k} (mutual k-NN)")

    # Compute centroids
    centroids = compute_station_centroids(stations, embeddings, tmdb_ids)

    # Build mutual k-NN edges
    edges = build_mutual_knn(centroids, k)
    print(f"Mutual k-NN edges: {len(edges)}")

    # Build networkx graph for path finding
    G = nx.Graph()
    for s in stations:
        G.add_node(s["id"], keywords=s["keywords"][:5], size=s["size"])
    for a, b, sim in edges:
        G.add_edge(a, b, weight=sim)

    # Check connectivity
    components = list(nx.connected_components(G))
    isolated = [s["id"] for s in stations if s["id"] not in G or G.degree(s["id"]) == 0]
    print(f"Connected components: {len(components)}")
    if isolated:
        print(f"Isolated stations (no mutual edges): {isolated}")

    # Write station graph
    graph_output = {
        "n_stations": len(stations),
        "n_edges": len(edges),
        "k": k,
        "nodes": [
            {
                "id": s["id"],
                "keywords": s["keywords"][:5],
                "size": s["size"],
                "degree": G.degree(s["id"]) if s["id"] in G else 0,
            }
            for s in stations
        ],
        "edges": [
            {"source": a, "target": b, "similarity": round(sim, 4)}
            for a, b, sim in sorted(edges)
        ],
    }

    GRAPH_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(GRAPH_OUTPUT, "w") as f:
        json.dump(graph_output, f, indent=2)
    print(f"Wrote {GRAPH_OUTPUT}")

    # Find candidate paths
    max_length = graph_cfg.get("max_path_length", 8)
    top_n = graph_cfg.get("top_n_paths", 50)
    print(f"\nRanking candidate paths (max_length={max_length}, top_n={top_n})...")
    candidates = find_candidate_paths(G, centroids, max_length=max_length, top_n=top_n)
    print(f"Found {len(candidates)} diverse candidate paths")

    # Enrich with station keywords for readability
    station_kw = {s["id"]: s["keywords"][:3] for s in stations}
    paths_output = {
        "n_candidates": len(candidates),
        "k": k,
        "paths": [
            {
                "rank": i + 1,
                "path": c["path"],
                "path_keywords": [station_kw.get(sid, []) for sid in c["path"]],
                "score": round(c["score"], 4),
                "local_coherence": round(c["local_coherence"], 4),
                "drift": round(c["drift"], 4),
                "monotonicity": round(c["monotonicity"], 4),
                "length": c["length"],
            }
            for i, c in enumerate(candidates)
        ],
    }

    with open(PATHS_OUTPUT, "w") as f:
        json.dump(paths_output, f, indent=2)
    print(f"Wrote {PATHS_OUTPUT}")

    # Print top 10
    print(f"\nTop 10 candidate lines:")
    print(f"{'Rank':>4}  {'Score':>6}  {'Len':>3}  Path (station keywords)")
    print("-" * 80)
    for c in paths_output["paths"][:10]:
        journey = " → ".join(
            "/".join(kws[:2]) for kws in c["path_keywords"]
        )
        print(f"{c['rank']:>4}  {c['score']:>6.3f}  {c['length']:>3}  {journey}")


def main():
    parser = argparse.ArgumentParser(description="Build station graph + rank candidate paths")
    parser.add_argument(
        "--k", type=int, default=None,
        help="Number of neighbors for k-NN (overrides config.yaml)",
    )
    args = parser.parse_args()
    run(k=args.k)


if __name__ == "__main__":
    main()
