"""Run the canonical TMDB /discover queries and write data/raw/films.json.

Usage:
    uv run python -m flickseed_pipeline.ingest [--out PATH]

Reads TMDB_API_KEY from pipeline/.env or pipeline/.env.local (or the
process environment). Pages through each query, dedupes by tmdb_id, and
writes the slim film records plus slice provenance.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from .queries import QUERIES, DiscoverQuery

TMDB_BASE = "https://api.themoviedb.org/3"

# pipeline/flickseed_pipeline/ingest/__main__.py -> parents[3] = repo root.
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = ROOT / "data" / "raw" / "films.json"


def _api_key() -> str:
    load_dotenv(ROOT / "pipeline" / ".env")
    load_dotenv(ROOT / "pipeline" / ".env.local")
    key = os.environ.get("TMDB_API_KEY")
    if not key:
        raise SystemExit(
            "TMDB_API_KEY not set. Add it to pipeline/.env(.local) or export it."
        )
    return key


def _fetch_query(client: httpx.Client, q: DiscoverQuery, api_key: str) -> list[dict]:
    results: list[dict] = []
    page = 1
    while True:
        resp = client.get(
            f"{TMDB_BASE}/discover/movie",
            params={**q.params, "api_key": api_key, "page": str(page)},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results.extend(data["results"])
        total_pages = data.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1
    return results


def _slim(film: dict, slices: set[str]) -> dict:
    return {
        "tmdb_id": film["id"],
        "title": film["title"],
        "original_title": film.get("original_title", film["title"]),
        "year": (film.get("release_date") or "")[:4] or None,
        "language": film.get("original_language"),
        "overview": film.get("overview"),
        "vote_average": film.get("vote_average"),
        "vote_count": film.get("vote_count"),
        "genre_ids": film.get("genre_ids", []),
        "popularity": film.get("popularity"),
        "slices": sorted(slices),
    }


def main() -> None:
    ap = argparse.ArgumentParser(prog="flickseed_pipeline.ingest")
    ap.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output path (default: {DEFAULT_OUT.relative_to(ROOT)})",
    )
    args = ap.parse_args()

    api_key = _api_key()

    seen: dict[int, dict] = {}
    seen_slices: dict[int, set[str]] = {}

    with httpx.Client() as client:
        for q in QUERIES:
            films = _fetch_query(client, q, api_key)
            print(f"  {q.label}: {len(films)} films", file=sys.stderr)
            for f in films:
                fid = f["id"]
                seen.setdefault(fid, f)
                seen_slices.setdefault(fid, set()).add(q.label)

    output = [_slim(seen[fid], seen_slices[fid]) for fid in sorted(seen)]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")

    print(f"Wrote {len(output)} films to {args.out.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
