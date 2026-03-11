"""Tests for KnowledgeGraph: add nodes/edges, serialize, write JSON."""

import json
import tempfile
from pathlib import Path

import pytest

from src.graph.knowledge_graph import KnowledgeGraph
from src.models.nodes import DatasetNode, ModuleNode, TransformationNode
from src.models.edges import EdgeType


class TestKnowledgeGraphModuleGraph:
    def test_add_module_node_and_import_edge(self):
        kg = KnowledgeGraph()
        kg.add_module_node(ModuleNode(path="a.py", language="python"))
        kg.add_module_node(ModuleNode(path="b.py", language="python"))
        kg.add_import_edge("a.py", "b.py", weight=2.0)
        assert kg.module_graph.number_of_nodes() == 2
        assert kg.module_graph.number_of_edges() == 1
        assert kg.module_graph.has_edge("a.py", "b.py")
        data = kg.serialize_module_graph()
        assert "nodes" in data
        assert "links" in data or "edges" in data  # NetworkX version may use "edges"
        assert any(n.get("id") == "a.py" or n.get("path") == "a.py" for n in data["nodes"])

    def test_add_function_and_calls(self):
        kg = KnowledgeGraph()
        kg.add_module_node(ModuleNode(path="m.py", language="python"))
        kg.add_function_node({"qualified_name": "m.foo", "parent_module": "m.py"})
        kg.add_function_node({"qualified_name": "m.bar", "parent_module": "m.py"})
        kg.add_calls_edge("m.foo", "m.bar")
        assert kg.module_graph.number_of_nodes() == 3
        assert kg.module_graph.has_edge("m.foo", "m.bar")


class TestKnowledgeGraphLineageGraph:
    def test_add_dataset_and_transformation(self):
        kg = KnowledgeGraph()
        kg.add_dataset_node(DatasetNode(name="raw", storage_type="table"))
        kg.add_dataset_node(DatasetNode(name="clean", storage_type="table"))
        tid = kg.add_transformation_node(
            TransformationNode(
                source_datasets=["raw"],
                target_datasets=["clean"],
                transformation_type="sql",
                source_file="models/clean.sql",
                line_range=(1, 10),
            )
        )
        kg.add_consumes_edge(tid, "raw")
        kg.add_produces_edge(tid, "clean")
        assert kg.lineage_graph.number_of_nodes() == 3
        assert kg.lineage_graph.number_of_edges() == 2

    def test_serialize_lineage_roundtrip(self):
        kg = KnowledgeGraph()
        kg.add_dataset_node(DatasetNode(name="t1", storage_type="table"))
        data = kg.serialize_lineage_graph()
        kg2 = KnowledgeGraph()
        kg2.load_lineage_graph_from_dict(data)
        assert kg2.lineage_graph.number_of_nodes() == 1


class TestKnowledgeGraphSerialization:
    def test_write_and_read_module_graph_json(self, tmp_path):
        kg = KnowledgeGraph()
        kg.add_module_node(ModuleNode(path="x.py", language="python"))
        out_file = tmp_path / "module_graph.json"
        kg.write_module_graph_json(out_file)
        assert out_file.exists()
        loaded = json.loads(out_file.read_text())
        assert "nodes" in loaded

    def test_write_lineage_graph_json(self, tmp_path):
        kg = KnowledgeGraph()
        kg.add_dataset_node(DatasetNode(name="d", storage_type="table"))
        out_file = tmp_path / "lineage_graph.json"
        kg.write_lineage_graph_json(out_file)
        assert out_file.exists()
        loaded = json.loads(out_file.read_text())
        assert "nodes" in loaded
