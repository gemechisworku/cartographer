"""Hydrologist agent: data lineage DAG from SQL, dbt, Airflow/dbt config. blast_radius, find_sources, find_sinks.

Per specs/agents/hydrologist.md. Populates knowledge graph lineage_graph with DatasetNode, TransformationNode, PRODUCES, CONSUMES.
"""
import logging
from pathlib import Path
from typing import Any, Optional

from src.analyzers.dag_config_parser import analyze_dag_config
from src.analyzers.sql_lineage import extract_lineage_from_file
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.nodes import DatasetNode, TransformationNode

logger = logging.getLogger(__name__)

# File patterns for lineage
SQL_EXTENSIONS = {".sql"}
YAML_EXTENSIONS = {".yml", ".yaml"}
DAG_PY_PATTERN = "dags"  # path containing "dags" or "dag"


def _collect_lineage_files(repo_root: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """Return (sql_files, yaml_files, dag_py_files) under repo_root."""
    sql_files: list[Path] = []
    yaml_files: list[Path] = []
    dag_py_files: list[Path] = []
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv"}
    for p in repo_root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in p.parts for part in skip):
            continue
        try:
            rel = p.relative_to(repo_root)
        except ValueError:
            continue
        s = str(rel).replace("\\", "/")
        if rel.suffix.lower() in SQL_EXTENSIONS:
            sql_files.append(rel)
        if rel.suffix.lower() in YAML_EXTENSIONS:
            yaml_files.append(rel)
        if rel.suffix.lower() == ".py" and ("dag" in s.lower() or "dags" in p.parts):
            dag_py_files.append(rel)
    return sql_files, yaml_files, dag_py_files


def run_hydrologist(
    repo_root: str | Path,
    kg: KnowledgeGraph,
    *,
    sql_dialect: str = "postgres",
) -> None:
    """Run SQL lineage and DAG config analyzers; merge into kg.lineage_graph."""
    repo_root = Path(repo_root)
    sql_files, yaml_files, dag_py_files = _collect_lineage_files(repo_root)

    for rel in sql_files:
        try:
            deps_list = extract_lineage_from_file(str(repo_root), str(rel), dialect=sql_dialect)
        except Exception as e:
            logger.warning("sql_lineage failed for %s: %s", rel, e)
            continue
        for d in deps_list:
            for t in d.get("source_tables", []):
                kg.add_dataset_node(DatasetNode(name=t, storage_type="table"))
            for t in d.get("target_tables", []):
                kg.add_dataset_node(DatasetNode(name=t, storage_type="table"))
            trans = TransformationNode(
                source_datasets=d.get("source_tables", []),
                target_datasets=d.get("target_tables", []),
                transformation_type="sql",
                source_file=str(rel).replace("\\", "/"),
                line_range=d.get("line_range", (0, 0)),
                sql_query_if_applicable=d.get("sql_snippet"),
            )
            tid = kg.add_transformation_node(trans)
            for src in d.get("source_tables", []):
                kg.add_consumes_edge(tid, src)
            for tgt in d.get("target_tables", []):
                kg.add_produces_edge(tid, tgt)

    for rel in yaml_files:
        try:
            out = analyze_dag_config(repo_root, rel)
        except Exception as e:
            logger.warning("dag_config failed for %s: %s", rel, e)
            continue
        config_file = out.get("config_file", str(rel))
        for m in out.get("models", []):
            kg.add_dataset_node(DatasetNode(name=m, storage_type="table"))
        for up, down in out.get("topology", []):
            kg.add_dataset_node(DatasetNode(name=up, storage_type="table"))
            kg.add_dataset_node(DatasetNode(name=down, storage_type="table"))
            kg.add_configures_edge(config_file, down)

    for rel in dag_py_files:
        try:
            out = analyze_dag_config(repo_root, rel)
        except Exception as e:
            logger.warning("dag_config failed for %s: %s", rel, e)
            continue
        for tid in out.get("task_ids", []):
            kg.add_dataset_node(DatasetNode(name=tid, storage_type="table"))  # treat task as node
        for up, down in out.get("topology", []):
            kg.add_configures_edge(out.get("config_file", str(rel)), down)


def blast_radius(kg: KnowledgeGraph, node_id: str) -> list[tuple[str, Optional[str], Optional[tuple[int, int]]]]:
    """Return list of (affected_node_id, source_file, line_range) that depend on node_id (downstream)."""
    G = kg.lineage_graph
    if not G.has_node(node_id):
        return []
    # Downstream = nodes that consume this node (in_edges) and what they produce (out_edges from those)
    affected: list[tuple[str, Optional[str], Optional[tuple[int, int]]]] = []
    seen = {node_id}
    stack = [node_id]
    while stack:
        n = stack.pop()
        for u, _v in G.in_edges(n):
            if u in seen:
                continue
            seen.add(u)
            data = G.nodes.get(u, {})
            affected.append((u, data.get("source_file"), data.get("line_range")))
            stack.append(u)
        for _u, v in G.out_edges(n):
            if v in seen:
                continue
            seen.add(v)
            data = G.nodes.get(v, {})
            affected.append((v, data.get("source_file"), data.get("line_range")))
            stack.append(v)
    return affected


def find_sources(kg: KnowledgeGraph) -> list[str]:
    """Return node ids with in-degree 0 (entry points of the data system)."""
    G = kg.lineage_graph
    return [n for n in G.nodes() if G.in_degree(n) == 0]


def find_sinks(kg: KnowledgeGraph) -> list[str]:
    """Return node ids with out-degree 0 (exit points)."""
    G = kg.lineage_graph
    return [n for n in G.nodes() if G.out_degree(n) == 0]
