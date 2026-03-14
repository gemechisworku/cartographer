"""Knowledge graph storage layer: NetworkX wrapper bridging Pydantic schemas (src/models) to graphs.

Provides add_* methods for typed nodes/edges (ModuleNode, DatasetNode, etc.), serialize to JSON,
deserialize from JSON (including from file via load_module_graph_json/load_lineage_graph_json).
Used by Surveyor (module graph) and Hydrologist (lineage). Per specs/data-model.md.
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

    def add_produces_edge(
        self,
        transformation_id: str,
        dataset_id: str,
        *,
        transformation_type: Optional[str] = None,
        source_file: Optional[str] = None,
        line_range: Optional[tuple[int, int]] = None,
    ) -> None:
        """Add PRODUCES: transformation -> dataset. Optional edge metadata for rubric consistency."""
        attrs: dict[str, Any] = {"edge_type": EdgeType.PRODUCES.value}
        if transformation_type is not None:
            attrs["transformation_type"] = transformation_type
        if source_file is not None:
            attrs["source_file"] = source_file
        if line_range is not None:
            attrs["line_range"] = line_range
        self._lineage_graph.add_edge(transformation_id, dataset_id, **attrs)

    def add_consumes_edge(
        self,
        transformation_id: str,
        dataset_id: str,
        *,
        transformation_type: Optional[str] = None,
        source_file: Optional[str] = None,
        line_range: Optional[tuple[int, int]] = None,
    ) -> None:
        """Add CONSUMES: transformation -> dataset. Optional edge metadata for rubric consistency."""
        attrs: dict[str, Any] = {"edge_type": EdgeType.CONSUMES.value}
        if transformation_type is not None:
            attrs["transformation_type"] = transformation_type
        if source_file is not None:
            attrs["source_file"] = source_file
        if line_range is not None:
            attrs["line_range"] = line_range
        self._lineage_graph.add_edge(transformation_id, dataset_id, **attrs)

    def add_configures_edge(
        self,
        config_file: str,
        target: str,
        *,
        source_file: Optional[str] = None,
        line_range: Optional[tuple[int, int]] = None,
    ) -> None:
        """Add CONFIGURES: config_file -> module/pipeline. Optional edge metadata."""
        attrs: dict[str, Any] = {"edge_type": EdgeType.CONFIGURES.value, "transformation_type": "config"}
        if source_file is not None:
            attrs["source_file"] = source_file
        elif config_file:
            attrs["source_file"] = config_file
        if line_range is not None:
            attrs["line_range"] = line_range
        self._lineage_graph.add_edge(config_file, target, **attrs)

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

    def load_module_graph_json(self, path: str | Path) -> None:
        """Deserialize module graph from a JSON file (round-trip with write_module_graph_json)."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.load_module_graph_from_dict(data)

    def load_lineage_graph_json(self, path: str | Path) -> None:
        """Deserialize lineage graph from a JSON file (round-trip with write_lineage_graph_json)."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.load_lineage_graph_from_dict(data)

    def remove_modules(self, paths: set[str]) -> None:
        """Remove module nodes and their function nodes / IMPORTS edges for incremental update.
        paths: set of module path strings (e.g. {'src/cli.py', 'src/orchestrator.py'}).
        """
        paths_n = {p.replace("\\", "/") for p in paths}
        to_remove: set[str] = set()
        for nid in list(self._module_graph.nodes()):
            data = self._module_graph.nodes.get(nid, {})
            path_val = (data.get("path") or data.get("id") or nid).replace("\\", "/")
            if path_val in paths_n:
                to_remove.add(nid)
            elif data.get("parent_module", "").replace("\\", "/") in paths_n:
                to_remove.add(nid)
        for nid in to_remove:
            self._module_graph.remove_node(nid)
        logger.debug("Removed %d nodes from module graph (paths: %s)", len(to_remove), paths_n)

    def remove_lineage_transformations_by_source_files(self, source_files: set[str]) -> None:
        """Remove transformation nodes (and CONFIGURES edges from) whose source_file is in source_files.
        Used for incremental update before re-running Hydrologist on changed files.
        """
        source_files_n = {f.replace("\\", "/") for f in source_files}
        to_remove: list[str] = []
        for nid in list(self._lineage_graph.nodes()):
            data = self._lineage_graph.nodes.get(nid, {})
            sf = (data.get("source_file") or "").replace("\\", "/")
            if sf in source_files_n:
                to_remove.append(nid)
        for nid in to_remove:
            self._lineage_graph.remove_node(nid)
        # Remove CONFIGURES edges where config_file (source u) is in source_files
        for u, v in list(self._lineage_graph.edges()):
            if self._lineage_graph.edges[u, v].get("edge_type") == "CONFIGURES" and u.replace("\\", "/") in source_files_n:
                self._lineage_graph.remove_edge(u, v)
        logger.debug("Removed %d lineage nodes for source_files: %s", len(to_remove), source_files_n)
