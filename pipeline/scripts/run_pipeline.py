"""End-to-end pipeline runner.

Runs each stage sequentially: ingest → enrich → corpus → embed → cluster → graph.
Layout and export stages are not yet implemented and will be skipped.

Usage:
    uv run python scripts/run_pipeline.py              # run all stages
    uv run python scripts/run_pipeline.py --from embed  # resume from embed stage
    uv run python scripts/run_pipeline.py --only cluster # run one stage
    uv run python scripts/run_pipeline.py --dry-run     # show what would run
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

STAGES = [
    ("ingest", ["-m", "flickseed_pipeline.ingest"]),
    ("enrich", ["-m", "flickseed_pipeline.enrich"]),
    ("corpus", ["-m", "flickseed_pipeline.corpus"]),
    ("embed", ["-m", "flickseed_pipeline.embed"]),
    ("cluster", ["-m", "flickseed_pipeline.cluster"]),
    ("graph", ["-m", "flickseed_pipeline.graph"]),
]

STAGE_NAMES = [name for name, _ in STAGES]


def run_stage(name: str, args: list[str]) -> bool:
    """Run a single pipeline stage. Returns True on success."""
    print(f"\n{'=' * 60}")
    print(f"  Stage: {name}")
    print(f"{'=' * 60}\n")

    start = time.time()
    result = subprocess.run([sys.executable, *args])
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"\n[FAILED] {name} exited with code {result.returncode} ({elapsed:.1f}s)")
        return False

    print(f"\n[OK] {name} ({elapsed:.1f}s)")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Flickseed data pipeline end-to-end"
    )
    parser.add_argument(
        "--from", dest="from_stage", choices=STAGE_NAMES,
        help="Resume from this stage (skips earlier stages)",
    )
    parser.add_argument(
        "--only", choices=STAGE_NAMES,
        help="Run only this stage",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print stages that would run without executing them",
    )
    args = parser.parse_args()

    # Determine which stages to run
    if args.only:
        stages_to_run = [(n, a) for n, a in STAGES if n == args.only]
    elif args.from_stage:
        start_idx = STAGE_NAMES.index(args.from_stage)
        stages_to_run = STAGES[start_idx:]
    else:
        stages_to_run = STAGES

    if args.dry_run:
        print("Stages that would run:")
        for name, _ in stages_to_run:
            print(f"  - {name}")
        return

    print(f"Running {len(stages_to_run)} stage(s): {', '.join(n for n, _ in stages_to_run)}")

    total_start = time.time()
    for name, stage_args in stages_to_run:
        if not run_stage(name, stage_args):
            print(f"\nPipeline stopped at {name}. Fix the error and resume with:")
            print(f"  uv run python scripts/run_pipeline.py --from {name}")
            sys.exit(1)

    total_elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"  Pipeline complete ({total_elapsed:.1f}s)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
