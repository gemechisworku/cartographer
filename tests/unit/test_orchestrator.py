"""Tests for orchestrator: run_analysis, incremental fallback."""

import tempfile
from pathlib import Path

from src.orchestrator import LAST_RUN_COMMIT_FILE, run_analysis


class TestRunAnalysisIncremental:
    def test_incremental_with_no_prior_run_does_full_analysis(self):
        """When --incremental is used but .cartography has no prior run, fall back to full analysis."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            kg = run_analysis(
                repo_root,
                output_dir=out,
                run_semanticist_agent=False,
                incremental=True,
            )
            # Should have run full analysis and written artifacts
            assert (out / "module_graph.json").exists()
            assert (out / "lineage_graph.json").exists()
            assert (out / "CODEBASE.md").exists()
            # last_run_commit written if repo is git
            if (repo_root / ".git").is_dir():
                assert (out / LAST_RUN_COMMIT_FILE).exists()
            assert kg.module_graph.number_of_nodes() >= 1
