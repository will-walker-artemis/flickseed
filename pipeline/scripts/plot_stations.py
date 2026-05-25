"""Interactive 2D scatter of films colored by station assignment.

Projects embeddings to 2D via UMAP, colors each point by its station cluster.
Hover to see film title, station ID, and station keywords. Opens in your browser.

Usage:
    uv run python scripts/plot_stations.py
    uv run python scripts/plot_stations.py --save stations.html
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
from umap import UMAP

ROOT = Path(__file__).resolve().parent.parent.parent
EMBEDDINGS_PATH = ROOT / "data" / "derived" / "embeddings.parquet"
STATIONS_PATH = ROOT / "data" / "derived" / "stations.json"


def main():
    parser = argparse.ArgumentParser(description="Plot films colored by station")
    parser.add_argument("--save", type=str, help="Save to HTML file instead of opening")
    args = parser.parse_args()

    # Load embeddings
    df = pd.read_parquet(EMBEDDINGS_PATH)
    embeddings = np.stack(df["fused"].values)
    tmdb_ids = df["tmdb_id"].tolist()
    titles = df["title"].tolist()

    # Load station assignments
    with open(STATIONS_PATH) as f:
        stations_data = json.load(f)

    # Build lookup: tmdb_id → (station_id, keywords)
    film_to_station: dict[int, int] = {}
    station_keywords: dict[int, str] = {}
    for s in stations_data["stations"]:
        kw = ", ".join(s["keywords"][:5])
        station_keywords[s["id"]] = kw
        for film in s["films"]:
            film_to_station[film["tmdb_id"]] = s["id"]

    # UMAP to 2D for visualization
    reducer = UMAP(n_neighbors=10, n_components=2, min_dist=0.3, metric="cosine", random_state=42)
    coords = reducer.fit_transform(embeddings)

    # Build dataframe for plotly
    plot_df = pd.DataFrame({
        "x": coords[:, 0],
        "y": coords[:, 1],
        "title": titles,
        "tmdb_id": tmdb_ids,
        "station": [film_to_station.get(tid, -1) for tid in tmdb_ids],
        "station_keywords": [station_keywords.get(film_to_station.get(tid, -1), "") for tid in tmdb_ids],
    })
    # Treat station as categorical so plotly gives distinct colors
    plot_df["station_label"] = plot_df["station"].astype(str)

    fig = px.scatter(
        plot_df,
        x="x",
        y="y",
        color="station_label",
        hover_data=["title", "station", "station_keywords"],
        title=f"Film Stations ({stations_data['n_stations']} clusters, {stations_data['n_films']} films)",
        labels={"station_label": "Station"},
        width=1200,
        height=800,
    )
    fig.update_traces(marker=dict(size=8, opacity=0.85))
    fig.update_layout(
        plot_bgcolor="white",
        hoverlabel=dict(bgcolor="white", font_size=12),
    )

    if args.save:
        out = Path(args.save)
        fig.write_html(str(out))
        print(f"Saved to {out}")
    else:
        fig.show()


if __name__ == "__main__":
    main()
