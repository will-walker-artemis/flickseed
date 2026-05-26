"""Print candidate paths in a human-readable format for line curation.

Shows each candidate path with station keywords and film lists,
making it easy to judge which paths feel like coherent "journeys."

Usage:
    uv run python scripts/print_candidates.py
    uv run python scripts/print_candidates.py --top 20
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
STATIONS_PATH = ROOT / "data" / "derived" / "stations.json"
PATHS_PATH = ROOT / "data" / "derived" / "candidate_paths.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=15, help="How many candidates to show")
    args = parser.parse_args()

    with open(STATIONS_PATH) as f:
        stations_data = json.load(f)
    with open(PATHS_PATH) as f:
        paths_data = json.load(f)

    # Build station lookup
    station_map = {s["id"]: s for s in stations_data["stations"]}

    print(f"{'=' * 80}")
    print(f"CANDIDATE SUBWAY LINES — top {args.top} of {paths_data['n_candidates']}")
    print(f"{'=' * 80}")
    print()

    for candidate in paths_data["paths"][: args.top]:
        rank = candidate["rank"]
        score = candidate["score"]
        coherence = candidate["local_coherence"]
        drift = candidate["drift"]
        mono = candidate["monotonicity"]
        path = candidate["path"]

        print(f"{'─' * 80}")
        print(f"  Line #{rank}  (score={score:.3f}  coherence={coherence:.2f}  "
              f"drift={drift:.2f}  monotonicity={mono:.2f})")
        print(f"{'─' * 80}")

        for i, station_id in enumerate(path):
            s = station_map[station_id]
            name = s.get("name", f"Station {station_id}")
            films = ", ".join(f["title"] for f in s["films"][:4])
            more = f" +{s['size'] - 4} more" if s["size"] > 4 else ""
            connector = "  ●" if i == 0 or i == len(path) - 1 else "  │"
            print(f"{connector} {name}")
            print(f"  {'│':}   {films}{more}")
            if i < len(path) - 1:
                print(f"  │")

        print()
        print()


if __name__ == "__main__":
    main()
