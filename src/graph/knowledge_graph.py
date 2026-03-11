"""NetworkX wrapper for module graph and data lineage. Serializes to JSON.

Per specs/data-model.md and pipeline. Used by Surveyor (module graph) and Hydrologist (lineage).
"""
import json
import logging
from pathlib import Path
from typing import Any, Optional

import networkx as nx

from src.models.edges import EdgeType
from src.models.nodes import (
    DatasetNode,
    FunctionNode,
    ModuleNode,
    TransformationNode,
)

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """Holds module graph (DiGraph) and lineage graph (DiGraph). Nodes are dicts or Pydantic model_dump(); edges have type and optional payload."""

    def __init__(self) -> None:
        self._module_graph: nx.DiGraph = nx.DiGraph()
        self._lineage_graph: nx.DiGraph = nx.DiGraph()

    @property
    def module_graph(self) -> nx.DiGraph:
        return self._module_graph

    @property
    def lineage_graph(self) -> nx.DiGraph:
        return self._lineage_graph

    def add_module_node(self, node: ModuleNode | dict[str, Any]) -> None:
        """Add or update a module node. Id = path."""
        data = node.model_dump() if isinstance(node, ModuleNode) else node
        nid = data.get("path") or data.get("id")
        if not nid:
            logger.warning("Module node missing path/id, skipping")
            return
        self._module_graph.add_node(nid, **data)

    def add_import_edge(self, source_path: str, target_path: str, weight: Optional[float] = None) -> None:
        """Add IMPORTS edge: source_module -> target_module."""
        self._module_graph.add_edge(source_path, target_path, edge_type=EdgeType.IMPORTS.value, weight=weight or 1.0)

    def add_function_node(self, node: FunctionNode | dict[str, Any]) -> None:
        """Add a function node to module graph (optional; keyed by qualified_name)."""
        data = node.model_dump() if isinstance(node, FunctionNode) else node
        nid = data.get("qualified_name")
        if not nid:
            return
        self._module_graph.add_node(nid, **data)

    def add_calls_edge(self, caller: str, callee: str) -> None:
        """Add CALLS edge: function -> function."""
        self._module_graph.add_edge(caller, callee, edge_type=EdgeType.CALLS.value)

    def add_dataset_node(self, node: DatasetNode | dict[str, Any]) -> None:
        """Add or update a dataset node in lineage graph. Id = name."""
        data = node.model_dump() if isinstance(node, DatasetNode) else node
        nid = data.get("name")
        if not nid:
            return
        self._lineage_graph.add_node(nid, **data)

    def add_transformation_node(self, node: TransformationNode | dict[str, Any]) -> str:
        """Add transformation node; returns an id (e.g. source_file:line_range)."""
        data = node.model_dump() if isinstance(node, TransformationNode) else node
        source_file = data.get("source_file", "")
        line_range = data.get("line_range", (0, 0))
        nid = f"{source_file}:{line_range[0]}-{line_range[1]}"
        self._lineage_graph.add_node(nid, **data)
        return nid

    def add_produces_edge(self, transformation_id: str, dataset_id: str) -> None:
        """Add PRODUCES: transformation -> dataset."""
        self._lineage_graph.add_edge(transformation_id, dataset_id, edge_type=EdgeType.PRODUCES.value)

    def add_consumes_edge(self, transformation_id: str, dataset_id: str) -> None:
        """Add CONSUMES: transformation -> dataset."""
        self._lineage_graph.add_edge(transformation_id, dataset_id, edge_type=EdgeType.CONSUMES.value)

    def add_configures_edge(self, config_file: str, target: str) -> None:
        """Add CONFIGURES: config_file -> module/pipeline."""
        self._lineage_graph.add_edge(config_file, target, edge_type=EdgeType.CONFIGURES.value)

    def serialize_module_graph(self) -> dict[str, Any]:
        """Export module graph as JSON-serializable dict (nodes + edges with keys)."""
        return nx.node_link_data(self._module_graph)

    def serialize_lineage_graph(self) -> dict[str, Any]:
        """Export lineage graph as JSON-serializable dict."""
        return nx.node_link_data(self._lineage_graph)

    def write_module_graph_json(self, path: str | Path) -> None:
        """Write module graph to .cartography/module_graph.json."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.serialize_module_graph()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Wrote %s", path)

    def write_lineage_graph_json(self, path: str | Path) -> None:
        """Write lineage graph to .cartography/lineage_graph.json."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.serialize_lineage_graph()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Wrote %s", path)

    def load_module_graph_from_dict(self, data: dict[str, Any]) -> None:
        """Load module graph from a node_link_data dict (e.g. from JSON)."""
        self._module_graph = nx.node_link_graph(data)

    def load_lineage_graph_from_dict(self, data: dict[str, Any]) -> None:
        """Load lineage graph from a node_link_data dict."""
        self._lineage_graph = nx.node_link_graph(data)
