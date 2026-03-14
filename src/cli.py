"""CLI entry point. analyze: run analysis; query: interactive Navigator on .cartography/."""
import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.agents.navigator import run_query
from src.orchestrator import resolve_repo_path, run_analysis

logger = logging.getLogger(__name__)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Brownfield Cartographer — codebase intelligence")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_p = subparsers.add_parser("analyze", help="Run analysis on a repo (local path or GitHub URL)")
    analyze_p.add_argument("target", help="Local directory path or GitHub repo URL")
    analyze_p.add_argument("-o", "--output-dir", default=None, help="Output directory (default: <repo>/.cartography)")
    analyze_p.add_argument("--days", type=int, default=30, help="Days for git velocity (default: 30)")
    analyze_p.add_argument("--sql-dialect", default="postgres", choices=["postgres", "bigquery", "snowflake", "duckdb"])
    analyze_p.add_argument("--no-semanticist", action="store_true", help="Skip Semanticist (no purpose/domain/Day-One; faster, no LLM)")

    query_p = subparsers.add_parser("query", help="Interactive query mode (Navigator) on existing .cartography/")
    query_p.add_argument("target", help="Repo path (to use <repo>/.cartography) or path to .cartography directory")
    query_p.add_argument("-o", "--output-dir", default=None, help="Path to .cartography/ (overrides target repo)")

    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s")
    for _logger in ("httpx", "httpcore", "openai"):
        logging.getLogger(_logger).setLevel(logging.WARNING)

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
                run_semanticist_agent=not args.no_semanticist,
            )
            print("Analysis complete. Outputs in", repo_path / ".cartography" if not args.output_dir else args.output_dir)
        except Exception as e:
            logger.exception("%s", e)
            sys.exit(1)
    elif args.command == "query":
        cartography_dir = args.output_dir or args.target
        # If target looks like a repo (directory), use target/.cartography
        if not args.output_dir:
            repo_path = resolve_repo_path(args.target)
            if repo_path is not None:
                cartography_dir = str(repo_path / ".cartography")
        path = Path(cartography_dir)
        if not path.is_dir():
            logger.error("Cartography directory not found: %s. Run 'analyze' first.", path)
            sys.exit(1)
        try:
            run_query(path)
        except (KeyboardInterrupt, EOFError):
            pass
        except Exception as e:
            logger.exception("%s", e)
            sys.exit(1)


if __name__ == "__main__":
    main()
