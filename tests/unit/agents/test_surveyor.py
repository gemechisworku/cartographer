"""Tests for Surveyor: analyze_module, extract_git_velocity, run_surveyor."""

import pytest
from pathlib import Path

from src.agents.surveyor import analyze_module, extract_git_velocity, run_surveyor
from src.graph.knowledge_graph import KnowledgeGraph


class TestAnalyzeModule:
    def test_analyze_python_file(self, tmp_path):
        (tmp_path / "m.py").write_text("import os\ndef foo(): pass\n")
        kg = KnowledgeGraph()
        mod, funcs, imports = analyze_module(tmp_path, "m.py", kg)
        assert mod is not None
        assert mod.path == "m.py"
        assert mod.language == "python"
        assert any(f.qualified_name.endswith("foo") for f in funcs)
        assert kg.module_graph.has_node("m.py")
        assert kg.module_graph.number_of_edges() >= 1  # at least one import

    def test_analyze_unsupported_extension(self, tmp_path):
        (tmp_path / "f.xyz").write_text("x")
        kg = KnowledgeGraph()
        mod, funcs, imports = analyze_module(tmp_path, "f.xyz", kg)
        assert mod.path == "f.xyz"
        assert mod.language != "python"
        assert len(funcs) == 0


class TestExtractGitVelocity:
    def test_non_git_dir_returns_empty(self, tmp_path):
        assert extract_git_velocity(tmp_path) == {}

    def test_git_repo_returns_map(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / "a.py").write_text("x")
        subprocess.run(["git", "add", "a.py"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
        out = extract_git_velocity(tmp_path, days=30)
        assert isinstance(out, dict)


class TestRunSurveyor:
    def test_run_surveyor_populates_kg(self, tmp_path):
        (tmp_path / "a.py").write_text("from b import x\n")
        (tmp_path / "b.py").write_text("def x(): pass\n")
        kg = KnowledgeGraph()
        run_surveyor(tmp_path, kg)
        assert kg.module_graph.number_of_nodes() >= 2
        assert kg.module_graph.number_of_edges() >= 1
