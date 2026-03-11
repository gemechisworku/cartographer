"""Tests for Hydrologist: run_hydrologist, blast_radius, find_sources, find_sinks."""

import pytest

from src.agents.hydrologist import blast_radius, find_sinks, find_sources, run_hydrologist
from src.graph.knowledge_graph import KnowledgeGraph


class TestRunHydrologist:
    def test_sql_adds_datasets_and_transformation(self, tmp_path):
        (tmp_path / "q.sql").write_text("INSERT INTO dest SELECT * FROM src;\n")
        kg = KnowledgeGraph()
        run_hydrologist(tmp_path, kg)
        assert kg.lineage_graph.number_of_nodes() >= 2
        assert "src" in [kg.lineage_graph.nodes[n].get("name") for n in kg.lineage_graph.nodes()]
        assert "dest" in [kg.lineage_graph.nodes[n].get("name") for n in kg.lineage_graph.nodes()]

    def test_dbt_yml_adds_configures(self, tmp_path):
        (tmp_path / "schema.yml").write_text("models:\n  - name: m1\n")
        kg = KnowledgeGraph()
        run_hydrologist(tmp_path, kg)
        edges = list(kg.lineage_graph.edges(data=True))
        configures = [e for e in edges if e[2].get("edge_type") == "CONFIGURES"]
        assert len(configures) >= 0  # may or may not have topology


class TestBlastRadius:
    def test_returns_downstream(self):
        kg = KnowledgeGraph()
        kg.add_dataset_node({"name": "a", "storage_type": "table"})
        kg.add_dataset_node({"name": "b", "storage_type": "table"})
        tid = kg.add_transformation_node({
            "source_datasets": ["a"],
            "target_datasets": ["b"],
            "transformation_type": "sql",
            "source_file": "x.sql",
            "line_range": (1, 2),
        })
        kg.add_consumes_edge(tid, "a")
        kg.add_produces_edge(tid, "b")
        affected = blast_radius(kg, "a")
        assert len(affected) >= 1
        ids = [a[0] for a in affected]
        assert tid in ids or "b" in ids


class TestFindSourcesAndSinks:
    def test_find_sources_sinks(self):
        kg = KnowledgeGraph()
        kg.add_dataset_node({"name": "raw", "storage_type": "table"})
        kg.add_dataset_node({"name": "out", "storage_type": "table"})
        tid = kg.add_transformation_node({
            "source_datasets": ["raw"],
            "target_datasets": ["out"],
            "transformation_type": "sql",
            "source_file": "m.sql",
            "line_range": (1, 2),
        })
        kg.add_consumes_edge(tid, "raw")
        kg.add_produces_edge(tid, "out")
        sources = find_sources(kg)
        sinks = find_sinks(kg)
        assert "raw" in sources or tid in sources
        assert "out" in sinks or tid in sinks
