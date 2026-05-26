"""Cluster stage: BERTopic over fused embeddings → data/derived/stations.json.

BERTopic pipeline:
  1. UMAP reduces fused 896-dim vectors to a lower-dimensional space
  2. HDBSCAN finds dense clusters in that reduced space
  3. c-TF-IDF extracts representative keywords per cluster from corpus text

Each cluster becomes a "station" — a cinematic concept node on the map.
Films assigned to topic -1 (outliers) get reassigned to their nearest station.

Usage:
    uv run python -m flickseed_pipeline.cluster
    uv run python -m flickseed_pipeline.cluster --min-topic-size 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from bertopic import BERTopic
from hdbscan import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer
from umap import UMAP

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "pipeline" / "config.yaml"
EMBEDDINGS_PATH = ROOT / "data" / "derived" / "embeddings.parquet"
CORPUS_DIR = ROOT / "data" / "corpus"
OUTPUT_PATH = ROOT / "data" / "derived" / "stations.json"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_corpus_texts(tmdb_ids: list[int]) -> list[str]:
    """Load corpus markdown for each film, used by BERTopic for keyword extraction."""
    texts = []
    for tid in tmdb_ids:
        path = CORPUS_DIR / f"{tid}.md"
        if path.exists():
            texts.append(path.read_text())
        else:
            texts.append("")
    return texts


def reassign_outliers(
    topics: np.ndarray, embeddings: np.ndarray, topic_embeddings: dict[int, np.ndarray]
) -> np.ndarray:
    """Assign outlier films (topic -1) to their nearest station by cosine similarity."""
    outlier_mask = topics == -1
    if not outlier_mask.any():
        return topics

    topics = topics.copy()
    valid_topics = sorted(t for t in topic_embeddings if t != -1)
    centroids = np.stack([topic_embeddings[t] for t in valid_topics])
    # Normalize for cosine similarity
    centroids_norm = centroids / np.linalg.norm(centroids, axis=1, keepdims=True)

    for idx in np.where(outlier_mask)[0]:
        vec = embeddings[idx]
        vec_norm = vec / np.linalg.norm(vec)
        sims = vec_norm @ centroids_norm.T
        topics[idx] = valid_topics[int(np.argmax(sims))]

    return topics


def compute_topic_centroids(
    embeddings: np.ndarray, topics: np.ndarray
) -> dict[int, np.ndarray]:
    """Compute mean embedding per topic (excluding -1)."""
    centroids = {}
    for t in set(topics):
        if t == -1:
            continue
        mask = topics == t
        centroids[t] = embeddings[mask].mean(axis=0)
    return centroids


def run(min_topic_size: int | None = None, nr_topics: int | None = None) -> None:
    cfg = load_config()
    cluster_cfg = cfg.get("cluster", {})

    min_topic_size = min_topic_size or cluster_cfg.get("min_topic_size", 4)
    nr_topics = nr_topics or cluster_cfg.get("nr_topics")

    # Load embeddings
    df = pd.read_parquet(EMBEDDINGS_PATH)
    embeddings = np.stack(df["fused"].values)
    tmdb_ids = df["tmdb_id"].tolist()
    titles = df["title"].tolist()

    # Load corpus text for keyword extraction
    docs = load_corpus_texts(tmdb_ids)

    print(f"Clustering {len(df)} films (min_topic_size={min_topic_size})")

    # Configure BERTopic sub-models
    umap_model = UMAP(
        n_neighbors=cluster_cfg.get("umap_n_neighbors", 10),
        n_components=cluster_cfg.get("umap_n_components", 5),
        min_dist=cluster_cfg.get("umap_min_dist", 0.0),
        metric="cosine",
        random_state=42,
    )

    hdbscan_model = HDBSCAN(
        min_cluster_size=min_topic_size,
        min_samples=cluster_cfg.get("hdbscan_min_samples", 1),
        metric="euclidean",
        prediction_data=True,
    )

    # Filter out noise: years, "director", and short tokens that don't help naming
    noise_words = [
        "director", "directors", "film", "films", "movie", "movies",
        "story", "original", "new", "one", "two", "three",
    ]
    # Add years 1950-2030 as stop words
    year_words = [str(y) for y in range(1950, 2031)]
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    custom_stops = list(ENGLISH_STOP_WORDS) + noise_words + year_words

    vectorizer = CountVectorizer(
        stop_words=custom_stops, min_df=2, ngram_range=(1, 2),
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b",  # letters only, 2+ chars
    )

    topic_model = BERTopic(
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
        nr_topics=nr_topics if nr_topics else None,
        top_n_words=10,
        verbose=True,
    )

    # Fit — pass pre-computed embeddings so BERTopic skips its own embedding step
    topics, probs = topic_model.fit_transform(docs, embeddings=embeddings)
    topics = np.array(topics)

    n_outliers = (topics == -1).sum()
    n_topics = len(set(topics)) - (1 if -1 in topics else 0)
    print(f"Found {n_topics} topics, {n_outliers} outliers")

    # Reassign outliers to nearest station
    if n_outliers > 0:
        centroids = compute_topic_centroids(embeddings, topics)
        topics = reassign_outliers(topics, embeddings, centroids)
        print(f"Reassigned {n_outliers} outliers → all films now have a station")

    # Build output structure
    topic_info = topic_model.get_topic_info()
    stations = []

    for topic_id in sorted(set(topics)):
        if topic_id == -1:
            continue

        mask = topics == topic_id
        film_indices = np.where(mask)[0]

        # Get BERTopic keywords for this topic
        topic_words = topic_model.get_topic(topic_id)
        keywords = [word for word, _ in topic_words[:10]] if topic_words else []

        # Get the topic name from BERTopic's auto-labeling
        info_row = topic_info[topic_info["Topic"] == topic_id]
        auto_name = info_row["Name"].values[0] if len(info_row) > 0 else ""

        films = []
        for idx in film_indices:
            films.append({"tmdb_id": tmdb_ids[idx], "title": titles[idx]})

        stations.append(
            {
                "id": int(topic_id),
                "keywords": keywords,
                "auto_label": auto_name,
                "films": sorted(films, key=lambda f: f["title"]),
                "size": len(films),
            }
        )

    output = {
        "n_stations": len(stations),
        "n_films": len(df),
        "min_topic_size": min_topic_size,
        "stations": stations,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nWrote {OUTPUT_PATH} ({len(stations)} stations)")
    print("\nStation summary:")
    print(f"{'ID':>4}  {'Size':>4}  Keywords")
    print("-" * 60)
    for s in stations:
        kw = ", ".join(s["keywords"][:5])
        print(f"{s['id']:>4}  {s['size']:>4}  {kw}")


def main():
    parser = argparse.ArgumentParser(description="Cluster films into stations")
    parser.add_argument(
        "--min-topic-size",
        type=int,
        default=None,
        help="Minimum films per station (overrides config.yaml)",
    )
    parser.add_argument(
        "--nr-topics",
        type=int,
        default=None,
        help="Force this many topics (BERTopic merges down)",
    )
    args = parser.parse_args()
    run(min_topic_size=args.min_topic_size, nr_topics=args.nr_topics)


if __name__ == "__main__":
    main()
