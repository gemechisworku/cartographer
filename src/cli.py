"""CLI entry point. analyze subcommand accepts repo path (local or GitHub URL); delegates to orchestrator; outputs written to .cartography/ or -o path."""
import argparse
import logging
import sys
from pathlib import Path

from src.orchestrator import resolve_repo_path, run_analysis

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Brownfield Cartographer — codebase intelligence")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_p = subparsers.add_parser("analyze", help="Run analysis on a repo (local path or GitHub URL)")
    analyze_p.add_argument("target", help="Local directory path or GitHub repo URL")
    analyze_p.add_argument("-o", "--output-dir", default=None, help="Output directory (default: <repo>/.cartography)")
    analyze_p.add_argument("--days", type=int, default=30, help="Days for git velocity (default: 30)")
    analyze_p.add_argument("--sql-dialect", default="postgres", choices=["postgres", "bigquery", "snowflake", "duckdb"])

    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s")

    if args.command == "analyze":
        repo_path = resolve_repo_path(args.target)
        if repo_path is None:
            sys.exit(1)
        try:
            run_analysis(
                repo_path,
                output_dir=args.output_dir,
                days_velocity=args.days,
                sql_dialect=args.sql_dialect,
            )
            print("Analysis complete. Outputs in", repo_path / ".cartography" if not args.output_dir else args.output_dir)
        except Exception as e:
            logger.exception("%s", e)
            sys.exit(1)


if __name__ == "__main__":
    main()
