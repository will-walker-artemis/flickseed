"""Generate per-film markdown documents in data/corpus/.

Reads data/raw/films.csv (produced by get_films.py --mode finalize),
deduplicates by tmdb_id, and writes one .md file per film.

Usage:
    uv run python -m flickseed_pipeline.corpus
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CSV_PATH = ROOT / "data" / "raw" / "films.csv"
CREDITS_PATH = ROOT / "data" / "raw" / "credits.json"
CORPUS_DIR = ROOT / "data" / "corpus"
NOTES_DIR = ROOT / "data" / "notes"


def load_films() -> dict[str, dict]:
    """Read films.csv and dedupe by tmdb_id (first occurrence wins)."""
    films: dict[str, dict] = {}
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            tid = row["tmdb_id"]
            if tid not in films:
                films[tid] = row
    return films


def load_credits() -> dict[str, dict]:
    if not CREDITS_PATH.exists():
        return {}
    return json.loads(CREDITS_PATH.read_text(encoding="utf-8"))


def render_doc(film: dict, credits: dict, notes: str | None) -> str:
    title = film.get("title", "Untitled")
    year = film.get("year", "")
    directors = ", ".join(credits.get("director", []))
    country = film.get("country", "")
    overview = film.get("overview", "")

    lines = [f"# {title} ({year})"]
    meta_parts = []
    if directors:
        meta_parts.append(f"Director: {directors}")
    if country:
        meta_parts.append(f"Country: {country}")
    if meta_parts:
        lines.append("  ".join(meta_parts))

    lines.append("")
    if overview:
        lines.append(overview)

    if notes:
        lines.append("")
        lines.append(notes.strip())

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    if not CSV_PATH.exists():
        raise SystemExit(
            f"Missing {CSV_PATH.relative_to(ROOT)} — run "
            "`get_films.py --mode finalize` first."
        )

    films = load_films()
    credits = load_credits()
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    current_ids = set(films.keys())
    stale = [p for p in CORPUS_DIR.glob("*.md") if p.stem not in current_ids]
    for p in stale:
        p.unlink()
    if stale:
        print(f"Removed {len(stale)} stale corpus docs", file=sys.stderr)

    for tid, film in films.items():
        film_credits = credits.get(tid, {})

        notes_path = NOTES_DIR / f"{tid}.md"
        notes = notes_path.read_text(encoding="utf-8") if notes_path.exists() else None

        doc = render_doc(film, film_credits, notes)
        (CORPUS_DIR / f"{tid}.md").write_text(doc, encoding="utf-8")

    print(f"Wrote {len(films)} corpus docs to {CORPUS_DIR.relative_to(ROOT)}/", file=sys.stderr)


if __name__ == "__main__":
    main()
