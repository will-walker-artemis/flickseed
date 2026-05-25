"""Interactive 2D scatter plot of film embeddings via UMAP + Plotly.

Projects the high-dimensional embedding vectors down to 2D using UMAP,
then opens an interactive Plotly scatter plot in your browser. Hover
over points to see film titles and metadata.

Usage:
    uv run python scripts/plot_embeddings.py
    uv run python scripts/plot_embeddings.py --view overview_embed
    uv run python scripts/plot_embeddings.py --method tsne
    uv run python scripts/plot_embeddings.py --save plot.html
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px

ROOT = Path(__file__).resolve().parent.parent.parent
EMBEDDINGS_PATH = ROOT / "data" / "derived" / "embeddings.parquet"
FILMS_CSV = ROOT / "data" / "raw" / "films.csv"
KEYWORDS_PATH = ROOT / "data" / "raw" / "keywords.json"


def load_film_metadata() -> dict[str, dict]:
    """Load film metadata from CSV, deduped by tmdb_id."""
    meta: dict[str, dict] = {}
    if not FILMS_CSV.exists():
        return meta
    with open(FILMS_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            tid = row["tmdb_id"]
            if tid not in meta:
                meta[tid] = row
    return meta


def load_keywords() -> dict[str, list[str]]:
    if not KEYWORDS_PATH.exists():
        return {}
    data = json.loads(KEYWORDS_PATH.read_text(encoding="utf-8"))
    return {
        tid: [kw["name"] for kw in entries if isinstance(kw, dict)]
        for tid, entries in data.items()
    }


def reduce_umap(vectors: np.ndarray, seed: int) -> np.ndarray:
    import umap
    reducer = umap.UMAP(n_components=2, random_state=seed, n_neighbors=15, min_dist=0.1)
    return reducer.fit_transform(vectors)


def reduce_tsne(vectors: np.ndarray, seed: int) -> np.ndarray:
    from sklearn.manifold import TSNE
    perplexity = min(30, len(vectors) - 1)
    return TSNE(n_components=2, random_state=seed, perplexity=perplexity).fit_transform(vectors)


def main() -> None:
    ap = argparse.ArgumentParser(description="Interactive 2D embedding scatter plot.")
    ap.add_argument("--view", default="fused",
                    choices=["fused", "overview_embed", "keyword_pca", "crew_pca", "notes_embed"],
                    help="Which embedding view to project (default: fused)")
    ap.add_argument("--method", default="umap", choices=["umap", "tsne"],
                    help="Dimensionality reduction method (default: umap)")
    ap.add_argument("--seed", type=int, default=42, help="Random seed")
    ap.add_argument("--save", type=str, default=None, help="Save to HTML file instead of opening browser")
    args = ap.parse_args()

    if not EMBEDDINGS_PATH.exists():
        raise SystemExit(
            f"Missing {EMBEDDINGS_PATH.relative_to(ROOT)} — run "
            "`python -m flickseed_pipeline.embed` first."
        )

    df = pd.read_parquet(EMBEDDINGS_PATH)
    vectors = np.stack(df[args.view].values)

    print(f"Projecting {len(df)} films ({args.view}, dim={vectors.shape[1]}) with {args.method}…", file=sys.stderr)

    if args.method == "umap":
        coords = reduce_umap(vectors, args.seed)
    else:
        coords = reduce_tsne(vectors, args.seed)

    film_meta = load_film_metadata()
    keywords = load_keywords()

    plot_df = pd.DataFrame({
        "x": coords[:, 0],
        "y": coords[:, 1],
        "title": df["title"],
        "tmdb_id": df["tmdb_id"],
    })

    plot_df["year"] = plot_df["tmdb_id"].map(lambda tid: film_meta.get(tid, {}).get("year", ""))
    plot_df["genres"] = plot_df["tmdb_id"].map(lambda tid: film_meta.get(tid, {}).get("genres", ""))
    plot_df["language"] = plot_df["tmdb_id"].map(lambda tid: film_meta.get(tid, {}).get("language", ""))
    plot_df["keywords"] = plot_df["tmdb_id"].map(lambda tid: ", ".join(keywords.get(tid, [])[:5]))
    plot_df["label"] = plot_df["title"] + " (" + plot_df["year"] + ")"

    fig = px.scatter(
        plot_df,
        x="x", y="y",
        text="label",
        hover_data={"title": True, "year": True, "genres": True, "language": True, "keywords": True, "x": False, "y": False},
        title=f"Flickseed Embeddings — {args.view} ({args.method.upper()})",
    )
    fig.update_traces(
        textposition="top center",
        textfont_size=9,
        marker=dict(size=8, opacity=0.7),
    )
    fig.update_layout(
        width=1400,
        height=900,
        xaxis_title="",
        yaxis_title="",
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False),
    )

    if args.save:
        fig.write_html(args.save)
        print(f"Saved to {args.save}", file=sys.stderr)
    else:
        fig.show()


if __name__ == "__main__":
    main()
