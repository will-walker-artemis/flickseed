"""Probe TMDB /discover/movie. Writes pipeline/reports/film-report.md.

Used by the probe-tmdb skill AND as a standalone CLI:

    uv run python scripts/get_films.py                     # run all preset queries
    uv run python scripts/get_films.py canon-quality       # run one preset
    uv run python scripts/get_films.py long-tail era-sweep # run several
    uv run python scripts/get_films.py --pages 3           # fetch 3 pages per query (default 1)
    uv run python scripts/get_films.py --lang ko ja        # ad-hoc per-language probe
    uv run python scripts/get_films.py --era 1960 1970     # ad-hoc era sweep for specific decades
    uv run python scripts/get_films.py --params 'vote_count.gte=200&sort_by=popularity.desc'
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"
REPORT_PATH = REPORTS_DIR / "film-report.md"

BASE = "https://api.themoviedb.org/3"

# ---------------------------------------------------------------------------
# Preset query catalog (mirrors .claude/skills/probe-tmdb.md)
# ---------------------------------------------------------------------------

PRESETS: dict[str, dict] = {
    "canon-quality": {
        "description": "High-quality canonical set; mainstream-leaning.",
        "params": {
            "vote_count.gte": 500,
            "vote_average.gte": 7.5,
            "sort_by": "vote_average.desc",
            "primary_release_date.lte": "2025-12-31",
        },
    },
    "long-tail": {
        "description": "Lower obscurity gate; surfaces cult / foreign / older.",
        "params": {
            "vote_count.gte": 50,
            "vote_average.gte": 7.5,
            "sort_by": "vote_average.desc",
        },
    },
    "per-language": {
        "description": "One call per language; union of results.",
        "expand": "language",
        "languages": ["ja", "fr", "ko", "fa", "it", "de", "ru", "zh", "es"],
        "params": {
            "vote_count.gte": 100,
            "vote_average.gte": 7.0,
            "sort_by": "vote_average.desc",
        },
    },
    "era-sweep": {
        "description": "Forces pre-1980 representation (TMDB is recency-biased).",
        "expand": "decade",
        "decades": [1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020],
        "params": {
            "vote_count.gte": 200,
            "sort_by": "vote_count.desc",
        },
    },
    "zeitgeist": {
        "description": "Culturally hot, not critically loved. Useful as contrast.",
        "params": {
            "sort_by": "popularity.desc",
            "vote_count.gte": 100,
        },
    },
}

# ---------------------------------------------------------------------------
# TMDB helpers
# ---------------------------------------------------------------------------

GENRE_CACHE: dict[int, str] = {}


def load_api_key() -> str:
    load_dotenv(ROOT / ".env.local")
    load_dotenv(ROOT / ".env")
    key = os.environ.get("TMDB_API_KEY", "")
    if not key:
        print("No TMDB_API_KEY found in pipeline/.env or environment.", file=sys.stderr)
        print("Get one at https://www.themoviedb.org/settings/api", file=sys.stderr)
        sys.exit(1)
    return key


def fetch_genres(client: httpx.Client, api_key: str) -> dict[int, str]:
    if GENRE_CACHE:
        return GENRE_CACHE
    r = client.get(f"{BASE}/genre/movie/list", params={"api_key": api_key})
    r.raise_for_status()
    for g in r.json()["genres"]:
        GENRE_CACHE[g["id"]] = g["name"]
    return GENRE_CACHE


def discover(client: httpx.Client, api_key: str, params: dict, page: int = 1) -> dict:
    r = client.get(
        f"{BASE}/discover/movie",
        params={**params, "api_key": api_key, "page": page},
    )
    r.raise_for_status()
    return r.json()

# ---------------------------------------------------------------------------
# Query expansion
# ---------------------------------------------------------------------------


def expand_queries(preset: dict, cli_langs: list[str] | None = None, cli_decades: list[int] | None = None) -> list[tuple[str, dict]]:
    """Expand a preset into (sub_name, params) pairs for multi-call presets."""
    expand = preset.get("expand")
    base = dict(preset["params"])

    if expand == "language":
        langs = cli_langs or preset.get("languages", [])
        return [(f"lang-{lang}", {**base, "with_original_language": lang}) for lang in langs]

    if expand == "decade":
        decades = cli_decades or preset.get("decades", [])
        return [
            (f"{dec}s", {**base, "primary_release_date.gte": f"{dec}-01-01", "primary_release_date.lte": f"{dec + 10}-01-01"})
            for dec in decades
        ]

    return [("", base)]

# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def format_table(films: list[dict], genres: dict[int, str]) -> str:
    header = "| # | Title | Year | Lang | Vote avg | Vote count | Genres | Country |"
    sep = "|---|---|---|---|---|---|---|---|"
    rows = [header, sep]
    for i, f in enumerate(films, 1):
        year = f["release_date"][:4] if f.get("release_date") else "—"
        lang = f.get("original_language", "—")
        avg = f"{f.get('vote_average', 0):.1f}"
        count = f.get("vote_count", "—")
        genre_names = ", ".join(genres.get(g, str(g)) for g in f.get("genre_ids", []))
        country = f["origin_country"][0] if f.get("origin_country") else "—"
        rows.append(f"| {i} | {f.get('title', '—')} | {year} | {lang} | {avg} | {count} | {genre_names} | {country} |")
    return "\n".join(rows)


def build_report(sections: list[dict]) -> str:
    lines = [f"# TMDB Probe Report — {date.today().isoformat()}", ""]
    for s in sections:
        lines.append(f"## Query: {s['name']}")
        if s.get("description"):
            lines.append(f"**Description:** {s['description']}")
        lines.append(f"**Endpoint:** GET /3/discover/movie")
        param_str = "&".join(f"{k}={v}" for k, v in s["params"].items())
        lines.append(f"**Params:** `{param_str}`")
        lines.append(f"**Returned:** {s['count']} of {s['total']}")
        lines.append("")
        lines.append(s["table"])
        lines.append("")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Probe TMDB /discover/movie for Flickseed seed-query iteration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Available presets: {', '.join(PRESETS)}",
    )
    p.add_argument(
        "queries", nargs="*", default=[],
        help="Preset names to run (default: all presets).",
    )
    p.add_argument(
        "--pages", type=int, default=1,
        help="Pages to fetch per query (20 results/page). Default: 1.",
    )
    p.add_argument(
        "--lang", nargs="+", metavar="CODE",
        help="Ad-hoc per-language probe (ISO 639-1 codes). Overrides per-language preset languages.",
    )
    p.add_argument(
        "--era", nargs="+", type=int, metavar="DECADE",
        help="Ad-hoc era sweep (decade start years, e.g. 1960 1970). Overrides era-sweep preset decades.",
    )
    p.add_argument(
        "--params", type=str,
        help="Raw discover params as a query string, e.g. 'vote_count.gte=200&sort_by=popularity.desc'. Runs as a one-off custom query.",
    )
    p.add_argument(
        "-o", "--output", type=Path, default=REPORT_PATH,
        help=f"Report output path. Default: {REPORT_PATH.relative_to(ROOT)}",
    )
    p.add_argument(
        "--stdout", action="store_true",
        help="Print report to stdout instead of writing to file.",
    )
    return p.parse_args()


def resolve_queries(args: argparse.Namespace) -> list[tuple[str, dict, str]]:
    """Return list of (name, params, description) to run."""
    result: list[tuple[str, dict, str]] = []

    if args.params:
        custom_params = dict(parse_qsl(args.params))
        result.append(("custom", custom_params, "Ad-hoc CLI query"))
        return result

    if args.lang:
        preset = dict(PRESETS["per-language"])
        for sub_name, params in expand_queries(preset, cli_langs=args.lang):
            result.append((f"per-language/{sub_name}", params, preset["description"]))
        return result

    if args.era:
        preset = dict(PRESETS["era-sweep"])
        for sub_name, params in expand_queries(preset, cli_decades=args.era):
            result.append((f"era-sweep/{sub_name}", params, preset["description"]))
        return result

    names = args.queries or list(PRESETS.keys())
    for name in names:
        if name not in PRESETS:
            print(f"Unknown preset: {name}", file=sys.stderr)
            print(f"Available: {', '.join(PRESETS)}", file=sys.stderr)
            sys.exit(1)
        preset = PRESETS[name]
        for sub_name, params in expand_queries(preset):
            full_name = f"{name}/{sub_name}" if sub_name else name
            result.append((full_name, params, preset["description"]))

    return result


def main() -> None:
    args = parse_args()
    api_key = load_api_key()
    queries = resolve_queries(args)

    sections: list[dict] = []
    with httpx.Client(timeout=30) as client:
        genres = fetch_genres(client, api_key)
        for name, params, description in queries:
            all_films: list[dict] = []
            total = 0
            for page in range(1, args.pages + 1):
                data = discover(client, api_key, params, page=page)
                total = data.get("total_results", 0)
                all_films.extend(data.get("results", []))
            print(f"  {name}: {len(all_films)} films (of {total} total)")
            sections.append({
                "name": name,
                "description": description,
                "params": params,
                "count": len(all_films),
                "total": total,
                "table": format_table(all_films, genres),
            })

    report = build_report(sections)

    if args.stdout:
        print(report)
    else:
        out = args.output.resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
        try:
            label = out.relative_to(ROOT)
        except ValueError:
            label = out
        print(f"\nReport written to {label}")


if __name__ == "__main__":
    main()
