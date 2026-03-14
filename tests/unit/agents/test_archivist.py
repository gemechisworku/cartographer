"""Tests for Archivist: generate_CODEBASE_md, generate_onboarding_brief_md, get_changed_files, run_archivist."""

import json
import tempfile
from pathlib import Path

from src.agents.archivist import (
    generate_CODEBASE_md,
    generate_onboarding_brief_md,
    get_changed_files,
    run_archivist,
)
from src.graph.knowledge_graph import KnowledgeGraph


class TestGenerateCODEBASEMd:
    def test_contains_all_sections(self):
        kg = KnowledgeGraph()
        kg.add_module_node({"path": "a.py", "language": "python", "pagerank": 0.1})
        kg.add_module_node({"path": "b.py", "language": "python", "pagerank": 0.2, "purpose_statement": "Does B."})
        kg.add_dataset_node({"name": "src_table", "storage_type": "table"})
        kg.add_dataset_node({"name": "tgt_table", "storage_type": "table"})
        kg.add_import_edge("a.py", "b.py")
        # Ensure we have sources/sinks (nodes with in/out degree 0)
        drift = []
        md = generate_CODEBASE_md(kg, drift)
        assert "## Architecture Overview" in md
        assert "## Critical Path" in md
        assert "## Data Sources & Sinks" in md
        assert "## Known Debt" in md
        assert "## Recent Change Velocity" in md
        assert "## Module Purpose Index" in md

    def test_critical_path_uses_pagerank(self):
        kg = KnowledgeGraph()
        kg.add_module_node({"path": "low.py", "language": "python", "pagerank": 0.05})
        kg.add_module_node({"path": "high.py", "language": "python", "pagerank": 0.9})
        md = generate_CODEBASE_md(kg, [])
        assert "high.py" in md
        assert "0.9000" in md or "0.9" in md

    def test_known_debt_lists_cycles_and_drift(self):
        kg = KnowledgeGraph()
        kg.add_module_node({"path": "cycle_a.py", "language": "python", "in_cycle": True})
        kg.add_module_node({"path": "clean.py", "language": "python", "in_cycle": False})
        drift = [("drift.py", "Old docstring")]
        md = generate_CODEBASE_md(kg, drift)
        assert "cycle_a.py" in md
        assert "drift.py" in md
        assert "Circular" in md or "SCC" in md or "cycle" in md.lower()
        assert "Documentation drift" in md or "drift" in md.lower()

    def test_module_purpose_index_includes_purpose_statements(self):
        kg = KnowledgeGraph()
        kg.add_module_node({"path": "p.py", "language": "python", "purpose_statement": "Handles payments."})
        md = generate_CODEBASE_md(kg, [])
        assert "p.py" in md
        assert "payments" in md or "Handles" in md


class TestGenerateOnboardingBriefMd:
    def test_five_questions_and_answers(self):
        day_one = [
            {"question": f"Q{i}", "answer": f"A{i}", "citations": [f"file{i}.py:1"]}
            for i in range(1, 6)
        ]
        md = generate_onboarding_brief_md(day_one)
        for i in range(1, 6):
            assert f"Q{i}" in md
            assert f"A{i}" in md
        assert "Day-One Brief" in md or "Brief" in md

    def test_handles_empty_citations(self):
        day_one = [{"question": "Q?", "answer": "A.", "citations": []}]
        md = generate_onboarding_brief_md(day_one)
        assert "Q?" in md and "A." in md


class TestGetChangedFiles:
    def test_returns_empty_for_non_git_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert get_changed_files(tmp) == []


class TestRunArchivist:
    def test_writes_all_artifacts(self):
        kg = KnowledgeGraph()
        kg.add_module_node({"path": "m.py", "language": "python", "purpose_statement": "A module."})
        kg.add_dataset_node({"name": "t", "storage_type": "table"})
        day_one = [{"question": "Q?", "answer": "A.", "citations": []}]
        drift: list[tuple[str, str]] = []
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            out = repo / ".cartography"
            run_archivist(repo, kg, out, day_one, drift)
            assert (out / "CODEBASE.md").exists()
            assert (out / "onboarding_brief.md").exists()
            assert (out / "module_graph.json").exists()
            assert (out / "lineage_graph.json").exists()
            assert (out / "day_one_answers.json").exists()
            assert (out / "documentation_drift.json").exists()
            assert (out / "semantic_index" / "purpose_index.json").exists()
            assert (out / "cartography_trace.jsonl").exists()

    def test_trace_records_returned_and_written(self):
        kg = KnowledgeGraph()
        kg.add_module_node({"path": "x.py", "language": "python"})
        day_one = [{"question": "Q", "answer": "A", "citations": []}]
        with tempfile.TemporaryDirectory() as tmp:
            trace = run_archivist(Path(tmp), kg, Path(tmp) / ".cartography", day_one, [])
            assert len(trace) >= 6  # CODEBASE, onboarding, module_graph, lineage, day_one, drift, semantic_index, trace
            lines = (Path(tmp) / ".cartography" / "cartography_trace.jsonl").read_text().strip().splitlines()
            assert len(lines) == len(trace)
            for line in lines:
                rec = json.loads(line)
                assert "agent" in rec and rec["agent"] == "archivist"
                assert rec["action"] == "write_artifact"
