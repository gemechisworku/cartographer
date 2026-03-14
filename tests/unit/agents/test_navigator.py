"""Tests for Navigator: find_implementation, trace_lineage, blast_radius, explain_module, load_cartography."""

import json
import tempfile
from pathlib import Path

from src.agents.navigator import (
    CITATION_SEMANTIC,
    CITATION_STATIC_LINEAGE,
    CITATION_STATIC_LINEAGE_AND_MODULE,
    blast_radius,
    explain_module,
    find_implementation,
    load_cartography,
    trace_lineage,
)
from src.graph.knowledge_graph import KnowledgeGraph


class TestFindImplementation:
    def test_returns_matches_and_citation(self):
        purpose_index = [
            {"path": "a.py", "purpose_statement": "Revenue calculation logic.", "domain_cluster": "billing"},
            {"path": "b.py", "purpose_statement": "User auth.", "domain_cluster": "security"},
        ]
        matches, cit = find_implementation("revenue", purpose_index)
        assert cit == CITATION_SEMANTIC
        assert len(matches) >= 1
        assert any(m["path"] == "a.py" for m in matches)

    def test_empty_concept_returns_empty(self):
        matches, cit = find_implementation("", [{"path": "x", "purpose_statement": "y"}])
        assert matches == []
        assert cit == CITATION_SEMANTIC


class TestTraceLineage:
    def test_unknown_dataset_returns_empty(self):
        kg = KnowledgeGraph()
        chain, cit = trace_lineage(kg, "nonexistent_table", "upstream")
        assert chain == []
        assert cit == CITATION_STATIC_LINEAGE

    def test_known_dataset_returns_chain_with_citation(self):
        kg = KnowledgeGraph()
        kg.add_dataset_node({"name": "t1", "storage_type": "table"})
        kg.add_dataset_node({"name": "t2", "storage_type": "table"})
        tid = kg.add_transformation_node({
            "source_datasets": ["t1"],
            "target_datasets": ["t2"],
            "transformation_type": "sql",
            "source_file": "models/foo.sql",
            "line_range": (1, 10),
        })
        kg.add_consumes_edge(tid, "t1")
        kg.add_produces_edge(tid, "t2")
        chain, cit = trace_lineage(kg, "t2", "upstream")
        assert cit == CITATION_STATIC_LINEAGE
        assert len(chain) >= 1
        node_ids = [c["node_id"] for c in chain]
        assert "t2" in node_ids


class TestBlastRadius:
    def test_returns_list_and_citation(self):
        kg = KnowledgeGraph()
        kg.add_dataset_node({"name": "ds1", "storage_type": "table"})
        results, cit = blast_radius(kg, "ds1")
        assert cit == CITATION_STATIC_LINEAGE_AND_MODULE
        assert isinstance(results, list)

    def test_includes_importers_from_module_graph(self):
        kg = KnowledgeGraph()
        kg.add_module_node({"path": "lib/foo.py", "language": "python"})
        kg.add_module_node({"path": "app/main.py", "language": "python"})
        kg.add_import_edge("app/main.py", "lib/foo.py")
        results, _ = blast_radius(kg, "lib/foo.py")
        assert any(r["node_id"] == "app/main.py" for r in results)


class TestExplainModule:
    def test_returns_explanation_and_citations(self):
        kg = KnowledgeGraph()
        kg.add_module_node({
            "path": "m.py",
            "language": "python",
            "purpose_statement": "Handles payments.",
            "domain_cluster": "billing",
        })
        explanation, citations = explain_module(kg, "m.py")
        assert "payment" in explanation.lower() or "Handles" in explanation
        assert len(citations) >= 1

    def test_unknown_module_returns_message(self):
        kg = KnowledgeGraph()
        explanation, citations = explain_module(kg, "nonexistent.py")
        assert "not found" in explanation.lower()
        assert len(citations) >= 1

    def test_fallback_to_purpose_index(self):
        kg = KnowledgeGraph()
        purpose_index = [{"path": "p.py", "purpose_statement": "Parses config.", "domain_cluster": "config"}]
        explanation, citations = explain_module(kg, "p.py", purpose_index=purpose_index)
        assert "config" in explanation.lower() or "Parses" in explanation
        assert len(citations) >= 1


class TestLoadCartography:
    def test_loads_kg_and_purpose_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "module_graph.json").write_text(
                '{"directed": true, "multigraph": false, "graph": {}, "nodes": [{"id": "a.py"}], "edges": []}',
                encoding="utf-8",
            )
            (root / "lineage_graph.json").write_text(
                '{"directed": true, "multigraph": false, "graph": {}, "nodes": [], "edges": []}',
                encoding="utf-8",
            )
            (root / "semantic_index").mkdir()
            (root / "semantic_index" / "purpose_index.json").write_text(
                json.dumps([{"path": "a.py", "purpose_statement": "A.", "domain_cluster": "X"}]),
                encoding="utf-8",
            )
            kg, purpose_index = load_cartography(root)
            assert kg.module_graph.number_of_nodes() >= 1
            assert len(purpose_index) == 1
            assert purpose_index[0]["path"] == "a.py"

    def test_missing_files_returns_empty_purpose_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg, purpose_index = load_cartography(tmp)
            assert purpose_index == []
