"""Top-5-similar diagnostic — the corpus go/no-go gate (PROJECT.md §5).

For N random films (default 10), prints the top-5 nearest neighbours
by cosine similarity on the fused embedding vector.

Good signal:  neighbours are tonally adjacent across genre and era.
Bad signal:   neighbours are just "same genre, same decade."

Usage:
    uv run python scripts/diagnose_embeddings.py
    uv run python scripts/diagnose_embeddings.py --n 20 --seed 42
    uv run python scripts/diagnose_embeddings.py --film 278   # query a specific film
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
EMBEDDINGS_PATH = ROOT / "data" / "derived" / "embeddings.parquet"


def cosine_similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    normed = vectors / norms
    return normed @ normed.T


def print_neighbours(
    query_idx: int,
    titles: list[str],
    tids: list[str],
    sim_matrix: np.ndarray,
    k: int = 5,
) -> None:
    sims = sim_matrix[query_idx]
    ranked = np.argsort(-sims)
    neighbours = [i for i in ranked if i != query_idx][:k]

    print(f"\n  {titles[query_idx]}  (id={tids[query_idx]})")
    for rank, idx in enumerate(neighbours, 1):
        print(f"    {rank}. {titles[idx]}  (sim={sims[idx]:.3f})")


def main() -> None:
    ap = argparse.ArgumentParser(description="Top-5-similar diagnostic for embeddings.")
    ap.add_argument("--n", type=int, default=10, help="Number of random films to query (default: 10)")
    ap.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    ap.add_argument("--film", type=str, default=None, help="Query a specific film by tmdb_id")
    ap.add_argument("--view", default="fused", choices=["fused", "overview_embed", "keyword_pca", "crew_pca", "notes_embed"],
                    help="Which embedding view to compare (default: fused)")
    args = ap.parse_args()

    if not EMBEDDINGS_PATH.exists():
        raise SystemExit(
            f"Missing {EMBEDDINGS_PATH.relative_to(ROOT)} — run "
            "`python -m flickseed_pipeline.embed` first."
        )

    df = pd.read_parquet(EMBEDDINGS_PATH)
    titles = df["title"].tolist()
    tids = df["tmdb_id"].tolist()
    vectors = np.stack(df[args.view].values)

    sim = cosine_similarity_matrix(vectors)

    print(f"Embeddings: {len(df)} films, view={args.view}, dim={vectors.shape[1]}", file=sys.stderr)

    if args.film:
        if args.film not in tids:
            raise SystemExit(f"Film {args.film} not found in embeddings.")
        idx = tids.index(args.film)
        print_neighbours(idx, titles, tids, sim)
    else:
        rng = np.random.default_rng(args.seed)
        sample = rng.choice(len(df), size=min(args.n, len(df)), replace=False)
        print(f"Querying {len(sample)} random films…\n")
        for idx in sample:
            print_neighbours(idx, titles, tids, sim)

    print()


if __name__ == "__main__":
    main()
