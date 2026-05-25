"""Probe TMDB /discover/movie in two modes.

discover (default) — quick exploration: first page (~25 films), .md report only.
finalize           — full pipeline export: all pages, keywords + credits, .md + CSV.

    uv run python scripts/get_films.py canon-quality                        # discover mode
    uv run python scripts/get_films.py --mode finalize --size 150 --yes     # finalize mode
    uv run python scripts/get_films.py --mode finalize -A --yes             # all results
    uv run python scripts/get_films.py --lang ko ja                         # ad-hoc languages
    uv run python scripts/get_films.py --era 1960 1970                      # ad-hoc decades
    uv run python scripts/get_films.py --params 'vote_count.gte=200&sort_by=popularity.desc'
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qsl

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"
REPORT_PATH = REPORTS_DIR / f"film-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"

BASE = "https://api.themoviedb.org/3"

# ---------------------------------------------------------------------------
# Preset query catalog
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


def _get_with_retry(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    for attempt in range(4):
        resp = client.get(url, **kwargs)
        if resp.status_code != 429:
            return resp
        wait = float(resp.headers.get("Retry-After", 2**attempt))
        print(f"  rate-limited, retrying in {wait:.0f}s…", file=sys.stderr)
        time.sleep(wait)
    return resp


def discover_page(client: httpx.Client, api_key: str, params: dict, page: int = 1) -> dict:
    r = _get_with_retry(
        client,
        f"{BASE}/discover/movie",
        params={**params, "api_key": api_key, "page": page},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def discover_all(
    client: httpx.Client, api_key: str, params: dict, *, max_pages: int | None = None
) -> tuple[list[dict], int]:
    """Fetch pages for a query. Returns (films, total_results)."""
    first = discover_page(client, api_key, params, page=1)
    films = list(first.get("results", []))
    total = first.get("total_results", 0)
    total_pages = min(first.get("total_pages", 1), 500)
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)
    for page in range(2, total_pages + 1):
        data = discover_page(client, api_key, params, page=page)
        films.extend(data.get("results", []))
    return films, total


def fetch_keywords(client: httpx.Client, api_key: str, film_id: int) -> list[str]:
    try:
        r = _get_with_retry(
            client, f"{BASE}/movie/{film_id}/keywords", params={"api_key": api_key}, timeout=30.0
        )
        r.raise_for_status()
        return [kw["name"] for kw in r.json().get("keywords", [])]
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 404:
            print(f"    warning: keywords failed for film {film_id} (HTTP {e.response.status_code})", file=sys.stderr)
        return []


def fetch_credits(client: httpx.Client, api_key: str, film_id: int) -> dict:
    try:
        r = _get_with_retry(
            client, f"{BASE}/movie/{film_id}/credits", params={"api_key": api_key}, timeout=30.0
        )
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 404:
            print(f"    warning: credits failed for film {film_id} (HTTP {e.response.status_code})", file=sys.stderr)
        return {"director": [], "writers": [], "cinematographer": [], "composer": [], "editor": []}

    data = r.json()
    crew = data.get("crew", [])
    return {
        "director": [m["name"] for m in crew if m.get("job") == "Director"],
        "writers": [m["name"] for m in crew if m.get("job") in ("Screenplay", "Writer")],
        "cinematographer": [m["name"] for m in crew if m.get("job") == "Director of Photography"],
        "composer": [m["name"] for m in crew if m.get("job") == "Original Music Composer"],
        "editor": [m["name"] for m in crew if m.get("job") == "Editor"],
    }


def fetch_all_keywords(client: httpx.Client, api_key: str, films: list[dict]) -> None:
    total = len(films)
    for i, film in enumerate(films, 1):
        film["keywords"] = fetch_keywords(client, api_key, film["id"])
        if i % 100 == 0 or i == total:
            print(f"    keywords: {i}/{total}", file=sys.stderr)
        time.sleep(0.03)


def fetch_all_credits(client: httpx.Client, api_key: str, films: list[dict]) -> None:
    total = len(films)
    for i, film in enumerate(films, 1):
        film["crew"] = fetch_credits(client, api_key, film["id"])
        if i % 100 == 0 or i == total:
            print(f"    credits: {i}/{total}", file=sys.stderr)
        time.sleep(0.03)


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
    header = "| # | Title | Year | Lang | Vote avg | Vote count | Genres | Country | Keywords |"
    sep = "|---|---|---|---|---|---|---|---|---|"
    rows = [header, sep]
    for i, f in enumerate(films, 1):
        year = f["release_date"][:4] if f.get("release_date") else "—"
        lang = f.get("original_language", "—")
        avg = f"{f.get('vote_average', 0):.1f}"
        count = f.get("vote_count", "—")
        genre_names = ", ".join(genres.get(g, str(g)) for g in f.get("genre_ids", []))
        country = f["origin_country"][0] if f.get("origin_country") else "—"
        keywords = ", ".join(f.get("keywords", [])[:5])
        rows.append(f"| {i} | {f.get('title', '—')} | {year} | {lang} | {avg} | {count} | {genre_names} | {country} | {keywords} |")
    return "\n".join(rows)


REPORT_PREVIEW = 20


def build_report(sections: list[dict], csv_path: str | None = None) -> str:
    lines = [f"# TMDB Probe Report — {date.today().isoformat()}", ""]
    if csv_path:
        lines.append(f"Full data: `{csv_path}`")
        lines.append("")
    for s in sections:
        lines.append(f"## Query: {s['name']}")
        if s.get("description"):
            lines.append(f"**Description:** {s['description']}")
        lines.append(f"**Endpoint:** GET /3/discover/movie")
        param_str = "&".join(f"{k}={v}" for k, v in s["params"].items())
        lines.append(f"**Params:** `{param_str}`")
        lines.append(f"**Total:** {s['total']} films (showing first {min(REPORT_PREVIEW, s['total'])})")
        lines.append("")
        lines.append(s["table"])
        lines.append("")
    return "\n".join(lines)


def write_csv(sections: list[dict], genres: dict[int, str], csv_path: Path) -> int:
    """Write all films from all sections to a single CSV. Returns total row count."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "query", "tmdb_id", "title", "year", "language",
        "vote_average", "vote_count", "genres", "country",
        "keywords", "crew", "overview",
    ]
    total_rows = 0
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for s in sections:
            for f in s["all_films"]:
                writer.writerow({
                    "query": s["name"],
                    "tmdb_id": f.get("id", ""),
                    "title": f.get("title", ""),
                    "year": f["release_date"][:4] if f.get("release_date") else "",
                    "language": f.get("original_language", ""),
                    "vote_average": f.get("vote_average", ""),
                    "vote_count": f.get("vote_count", ""),
                    "genres": ", ".join(genres.get(g, str(g)) for g in f.get("genre_ids", [])),
                    "country": f["origin_country"][0] if f.get("origin_country") else "",
                    "keywords": json.dumps(f.get("keywords", [])),
                    "crew": json.dumps(f.get("crew", {})),
                    "overview": f.get("overview", ""),
                })
                total_rows += 1
    return total_rows


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
        "--mode", choices=["discover", "finalize"], default="discover",
        help="discover: quick preview (~25 films, .md only). finalize: full fetch with keywords+credits, .md + CSV.",
    )
    p.add_argument(
        "--size", type=int, default=None,
        help="Max unique films to include (finalize mode only).",
    )
    p.add_argument(
        "-A", "--all", action="store_true", dest="fetch_all",
        help="Fetch all results with no size cap (finalize mode). Prints a warning.",
    )
    p.add_argument(
        "--yes", action="store_true",
        help="Skip interactive confirmation for -A.",
    )
    p.add_argument(
        "--lang", nargs="+", metavar="CODE",
        help="Ad-hoc per-language probe (ISO 639-1 codes).",
    )
    p.add_argument(
        "--era", nargs="+", type=int, metavar="DECADE",
        help="Ad-hoc era sweep (decade start years, e.g. 1960 1970).",
    )
    p.add_argument(
        "--params", type=str,
        help="Raw discover params as a query string.",
    )
    p.add_argument(
        "-o", "--output", type=Path, default=REPORT_PATH,
        help=f"Output path stem. .md and .csv suffixes are appended. Default: {REPORT_PATH.relative_to(ROOT)}",
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

    is_finalize = args.mode == "finalize"

    if is_finalize and not args.size and not args.fetch_all:
        print("finalize mode requires --size N or -A (--all).", file=sys.stderr)
        sys.exit(1)

    if is_finalize and args.fetch_all and not args.yes:
        print(
            "WARNING: -A fetches ALL results across all queries. "
            "This may be thousands of films and many API calls.",
            file=sys.stderr,
        )
        try:
            answer = input("Proceed? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer != "y":
            print("Aborted.", file=sys.stderr)
            sys.exit(0)

    max_pages = 2 if not is_finalize else None

    sections: list[dict] = []
    with httpx.Client(timeout=30) as client:
        genres = fetch_genres(client, api_key)
        for name, params, description in queries:
            all_films, total = discover_all(client, api_key, params, max_pages=max_pages)
            print(f"  {name}: {len(all_films)} films", file=sys.stderr)
            sections.append({
                "name": name,
                "description": description,
                "params": params,
                "total": total,
                "all_films": all_films,
            })

        # Dedupe across sections
        unique_films: dict[int, dict] = {}
        for s in sections:
            for f in s["all_films"]:
                unique_films.setdefault(f["id"], f)

        # Apply size cap in finalize mode
        if is_finalize and args.size:
            film_list = list(unique_films.values())[:args.size]
            unique_films = {f["id"]: f for f in film_list}

        if is_finalize:
            print(f"  Fetching keywords for {len(unique_films)} unique films…", file=sys.stderr)
            fetch_all_keywords(client, api_key, list(unique_films.values()))
            print(f"  Fetching credits for {len(unique_films)} unique films…", file=sys.stderr)
            fetch_all_credits(client, api_key, list(unique_films.values()))

            # Filter section film lists to only include enriched films
            enriched_ids = set(unique_films.keys())
            for s in sections:
                s["all_films"] = [f for f in s["all_films"] if f["id"] in enriched_ids]

        # Build report tables (keywords shown only if fetched)
        for s in sections:
            s["table"] = format_table(s["all_films"][:REPORT_PREVIEW], genres)

    # CSV — finalize mode only
    csv_label = None
    if is_finalize and not args.stdout:
        csv_path = args.output.resolve().with_suffix(".csv")
        row_count = write_csv(sections, genres, csv_path)
        try:
            csv_label = str(csv_path.relative_to(ROOT))
        except ValueError:
            csv_label = str(csv_path)
        print(f"  CSV: {row_count} rows → {csv_label}", file=sys.stderr)

    # Markdown report
    report = build_report(sections, csv_path=csv_label)

    if args.stdout:
        print(report)
    else:
        out = args.output.resolve().with_suffix(".md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
        try:
            label = out.relative_to(ROOT)
        except ValueError:
            label = out
        print(f"  Report: {label}", file=sys.stderr)


if __name__ == "__main__":
    main()
