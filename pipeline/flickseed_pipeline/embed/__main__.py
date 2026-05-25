"""Multi-view embedding: corpus docs + structured metadata → embeddings.parquet.

Views (PROJECT.md §5):
  1. overview_embed   — sentence-transformer on corpus text      → 384-dim
  2. keyword_pca      — multi-hot keyword matrix → PCA            → 64-dim
  3. crew_pca         — multi-hot crew matrix → PCA               → 64-dim
  4. notes_embed      — sentence-transformer on optional notes    → 384-dim (zeros if absent)
  (node2vec is deferred to FLI-40)

Output: data/derived/embeddings.parquet
  Columns: tmdb_id, title, fused (the final L2-normalized vector),
           plus per-view columns for diagnostics.

Usage:
    uv run python -m flickseed_pipeline.embed
    uv run python -m flickseed_pipeline.embed --model all-MiniLM-L6-v2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import PCA

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "pipeline" / "config.yaml"
CORPUS_DIR = ROOT / "data" / "corpus"
KEYWORDS_PATH = ROOT / "data" / "raw" / "keywords.json"
CREDITS_PATH = ROOT / "data" / "raw" / "credits.json"
NOTES_DIR = ROOT / "data" / "notes"
OUTPUT_PATH = ROOT / "data" / "derived" / "embeddings.parquet"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


CFG = load_config()
DEFAULT_MODEL = CFG.get("models", {}).get("text_embed", "sentence-transformers/all-MiniLM-L6-v2").replace("sentence-transformers/", "")
KEYWORD_PCA_DIM = CFG.get("models", {}).get("keyword_pca_dim", 64)
CREW_PCA_DIM = CFG.get("models", {}).get("crew_pca_dim", 64)
VIEW_WEIGHTS = CFG.get("view_weights", {
    "overview": 1.0,
    "keyword": 1.0,
    "crew": 1.0,
    "notes": 0.5,
})


def load_corpus(corpus_dir: Path) -> list[tuple[str, str, str]]:
    """Return [(tmdb_id, title, full_text)] sorted by id."""
    docs = []
    for md in sorted(corpus_dir.glob("*.md")):
        tid = md.stem
        text = md.read_text(encoding="utf-8")
        title_line = text.split("\n", 1)[0]
        title = title_line.lstrip("# ").strip()
        docs.append((tid, title, text))
    return docs


def embed_texts(model: SentenceTransformer, texts: list[str]) -> np.ndarray:
    return model.encode(texts, show_progress_bar=True, normalize_embeddings=True)


def build_multihot(items_per_film: list[list[str]], min_count: int = 2) -> tuple[np.ndarray, list[str]]:
    """Build a multi-hot matrix from per-film item lists.

    Items appearing fewer than min_count times across films are dropped
    to reduce noise.  Returns (matrix, vocab).
    """
    counts: dict[str, int] = {}
    for items in items_per_film:
        for item in items:
            counts[item] = counts.get(item, 0) + 1

    vocab = sorted(k for k, v in counts.items() if v >= min_count)
    vocab_idx = {w: i for i, w in enumerate(vocab)}

    matrix = np.zeros((len(items_per_film), len(vocab)), dtype=np.float32)
    for row, items in enumerate(items_per_film):
        for item in items:
            if item in vocab_idx:
                matrix[row, vocab_idx[item]] = 1.0

    return matrix, vocab


def pca_reduce(matrix: np.ndarray, n_components: int) -> np.ndarray:
    """PCA-reduce a matrix. If fewer features than n_components, zero-pad."""
    if matrix.shape[1] == 0:
        return np.zeros((matrix.shape[0], n_components), dtype=np.float32)
    actual_dim = min(n_components, matrix.shape[1], matrix.shape[0])
    pca = PCA(n_components=actual_dim)
    reduced = pca.fit_transform(matrix)
    if reduced.shape[1] < n_components:
        pad = np.zeros((reduced.shape[0], n_components - reduced.shape[1]), dtype=np.float32)
        reduced = np.hstack([reduced, pad])
    return reduced.astype(np.float32)


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return vectors / norms


def weight_and_fuse(views: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    parts = []
    for name, vec in views.items():
        w = weights.get(name, 1.0)
        parts.append(vec * w)
    fused = np.hstack(parts)
    return l2_normalize(fused)


def main() -> None:
    ap = argparse.ArgumentParser(prog="flickseed_pipeline.embed")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"Sentence-transformer model (default: {DEFAULT_MODEL})")
    args = ap.parse_args()

    if not CORPUS_DIR.exists() or not list(CORPUS_DIR.glob("*.md")):
        raise SystemExit("No corpus docs found. Run `python -m flickseed_pipeline.corpus` first.")

    docs = load_corpus(CORPUS_DIR)
    tids = [d[0] for d in docs]
    titles = [d[1] for d in docs]
    texts = [d[2] for d in docs]
    n = len(docs)
    print(f"Loaded {n} corpus docs", file=sys.stderr)

    # --- View 1: overview text embedding ---
    print(f"Encoding text with {args.model}…", file=sys.stderr)
    st_model = SentenceTransformer(args.model)
    overview_vecs = embed_texts(st_model, texts)
    print(f"  overview_embed: {overview_vecs.shape}", file=sys.stderr)

    # --- View 2: keyword multi-hot → PCA ---
    keywords_data: dict[str, list[dict]] = {}
    if KEYWORDS_PATH.exists():
        keywords_data = json.loads(KEYWORDS_PATH.read_text(encoding="utf-8"))

    keyword_lists = []
    for tid in tids:
        kw_entries = keywords_data.get(tid, [])
        keyword_lists.append([entry["name"] for entry in kw_entries if isinstance(entry, dict)])

    kw_matrix, kw_vocab = build_multihot(keyword_lists, min_count=2)
    keyword_vecs = pca_reduce(kw_matrix, KEYWORD_PCA_DIM)
    print(f"  keyword_pca: {keyword_vecs.shape} (vocab size: {len(kw_vocab)})", file=sys.stderr)

    # --- View 3: crew multi-hot → PCA ---
    credits_data: dict[str, dict] = {}
    if CREDITS_PATH.exists():
        credits_data = json.loads(CREDITS_PATH.read_text(encoding="utf-8"))

    crew_lists = []
    for tid in tids:
        crew = credits_data.get(tid, {})
        names = []
        for role in ("director", "writers", "cinematographer", "composer", "editor"):
            for name in crew.get(role, []):
                names.append(f"{role}:{name}")
        crew_lists.append(names)

    crew_matrix, crew_vocab = build_multihot(crew_lists, min_count=2)
    crew_vecs = pca_reduce(crew_matrix, CREW_PCA_DIM)
    print(f"  crew_pca: {crew_vecs.shape} (vocab size: {len(crew_vocab)})", file=sys.stderr)

    # --- View 4: optional notes embedding ---
    notes_texts = []
    has_notes = []
    for tid in tids:
        notes_path = NOTES_DIR / f"{tid}.md"
        if notes_path.exists():
            notes_texts.append(notes_path.read_text(encoding="utf-8"))
            has_notes.append(True)
        else:
            notes_texts.append("")
            has_notes.append(False)

    notes_count = sum(has_notes)
    if notes_count > 0:
        print(f"  Encoding {notes_count} notes…", file=sys.stderr)
        notes_vecs = embed_texts(st_model, notes_texts)
        for i, flag in enumerate(has_notes):
            if not flag:
                notes_vecs[i] = 0.0
    else:
        notes_vecs = np.zeros((n, overview_vecs.shape[1]), dtype=np.float32)
    print(f"  notes_embed: {notes_vecs.shape} ({notes_count} films have notes)", file=sys.stderr)

    # --- Fuse ---
    views = {
        "overview": overview_vecs,
        "keyword": keyword_vecs,
        "crew": crew_vecs,
        "notes": notes_vecs,
    }
    fused = weight_and_fuse(views, VIEW_WEIGHTS)
    print(f"  fused: {fused.shape}", file=sys.stderr)

    # --- Write parquet ---
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({
        "tmdb_id": tids,
        "title": titles,
        "overview_embed": list(overview_vecs),
        "keyword_pca": list(keyword_vecs),
        "crew_pca": list(crew_vecs),
        "notes_embed": list(notes_vecs),
        "fused": list(fused),
    })
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nWrote {OUTPUT_PATH.relative_to(ROOT)} ({len(df)} films, fused dim={fused.shape[1]})", file=sys.stderr)


if __name__ == "__main__":
    main()
