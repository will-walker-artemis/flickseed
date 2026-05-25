"""Parse enriched CSV into structured JSON files for downstream stages.

Usage:
    uv run python -m flickseed_pipeline.enrich [--input PATH]

Reads the pipeline CSV (default: data/raw/films.csv) and extracts:
  keywords -> data/raw/keywords.json
  credits  -> data/raw/credits.json

No API calls. The CSV is produced by `get_films.py --mode finalize`.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CSV = ROOT / "data" / "raw" / "films.csv"
KEYWORDS_PATH = ROOT / "data" / "raw" / "keywords.json"
CREDITS_PATH = ROOT / "data" / "raw" / "credits.json"


def main() -> None:
    ap = argparse.ArgumentParser(prog="flickseed_pipeline.enrich")
    ap.add_argument(
        "--input", type=Path, default=DEFAULT_CSV,
        help=f"Path to the enriched films CSV (default: {DEFAULT_CSV.relative_to(ROOT)})",
    )
    args = ap.parse_args()

    if not args.input.exists():
        raise SystemExit(
            f"Missing {args.input.relative_to(ROOT)} — run "
            "`get_films.py --mode finalize` first."
        )

    keywords_map: dict[str, list[dict]] = {}
    credits_map: dict[str, dict] = {}

    with open(args.input, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            tid = row["tmdb_id"]
            kw_raw = row.get("keywords", "[]")
            keywords_map[tid] = [{"name": k} for k in json.loads(kw_raw)]

            crew_raw = row.get("crew", "{}")
            credits_map[tid] = json.loads(crew_raw)

    KEYWORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    KEYWORDS_PATH.write_text(json.dumps(keywords_map, indent=2, ensure_ascii=False) + "\n")
    CREDITS_PATH.write_text(json.dumps(credits_map, indent=2, ensure_ascii=False) + "\n")

    print(f"Wrote {len(keywords_map)} entries to {KEYWORDS_PATH.relative_to(ROOT)}", file=sys.stderr)
    print(f"Wrote {len(credits_map)} entries to {CREDITS_PATH.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
