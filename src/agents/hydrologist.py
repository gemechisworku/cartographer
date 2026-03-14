"""Hydrologist agent: merges data flow from Python (AST pandas/PySpark/SQLAlchemy), SQL lineage (sqlglot), and DAG config into a single NetworkX lineage DiGraph. Provides blast_radius(node_id), find_sources(), find_sinks(). Logs unresolved dynamic references. Per specs/agents/hydrologist.md."""
import logging
from pathlib import Path
from typing import Any, Optional

from src.analyzers.dag_config_parser import analyze_dag_config
from src.analyzers.sql_lineage import extract_lineage_from_file
from src.analyzers.tree_sitter_analyzer import parse_file, extract_python_data_flow, get_language_for_path
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.nodes import DatasetNode, TransformationNode

logger = logging.getLogger(__name__)

# File patterns for lineage
SQL_EXTENSIONS = {".sql"}
YAML_EXTENSIONS = {".yml", ".yaml"}
DAG_PY_PATTERN = "dags"


def _collect_lineage_files(repo_root: Path) -> tuple[list[Path], list[Path], list[Path], list[Path]]:
    """Return (sql_files, yaml_files, dag_py_files, all_py_files) under repo_root."""
    sql_files: list[Path] = []
    yaml_files: list[Path] = []
    dag_py_files: list[Path] = []
    all_py_files: list[Path] = []
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
        if rel.suffix.lower() == ".py":
            all_py_files.append(rel)
            if "dag" in s.lower() or "dags" in p.parts:
                dag_py_files.append(rel)
    return sql_files, yaml_files, dag_py_files, all_py_files


def run_hydrologist(
    repo_root: str | Path,
    kg: KnowledgeGraph,
    *,
    sql_dialect: str = "postgres",
    file_list: Optional[list[str]] = None,
) -> None:
    """Run sql_lineage and dag_config_parser; merge into kg.lineage_graph (single DiGraph).
    If file_list is provided, only process those paths (for incremental update).
    """
    repo_root = Path(repo_root)
    sql_files, yaml_files, dag_py_files, all_py_files = _collect_lineage_files(repo_root)
    if file_list is not None:
        file_list_set = {p.replace("\\", "/") for p in file_list}
        def _in_list(rel: Path) -> bool:
            return str(rel).replace("\\", "/") in file_list_set
        sql_files = [f for f in sql_files if _in_list(f)]
        yaml_files = [f for f in yaml_files if _in_list(f)]
        dag_py_files = [f for f in dag_py_files if _in_list(f)]
        all_py_files = [f for f in all_py_files if _in_list(f)]
        logger.info("Hydrologist: incremental mode, %d SQL, %d YAML, %d DAG Python, %d Python files", len(sql_files), len(yaml_files), len(dag_py_files), len(all_py_files))
    else:
        logger.info("Hydrologist: found %d SQL, %d YAML, %d DAG Python, %d Python files", len(sql_files), len(yaml_files), len(dag_py_files), len(all_py_files))

    # Python AST data-flow (pandas, PySpark, SQLAlchemy)
    python_flow_count = 0
    all_dynamic_refs: list[str] = []
    for rel in all_py_files:
        if get_language_for_path(rel) is None:
            continue
        try:
            tree = parse_file(repo_root, rel)
            if tree is None:
                continue
            source_bytes = (repo_root / rel).read_bytes()
            path_str = str(rel).replace("\\", "/")
            trans_list, dynamic_refs = extract_python_data_flow(source_bytes, tree, path_str)
            all_dynamic_refs.extend(dynamic_refs)
            for t in trans_list:
                for s in t.get("sources", []):
                    kg.add_dataset_node(DatasetNode(name=s, storage_type="file"))
                for s in t.get("targets", []):
                    kg.add_dataset_node(DatasetNode(name=s, storage_type="file"))
                trans_node = TransformationNode(
                    source_datasets=t.get("sources", []),
                    target_datasets=t.get("targets", []),
                    transformation_type=t.get("transformation_type", "python"),
                    source_file=t["source_file"],
                    line_range=tuple(t.get("line_range", (0, 0))),
                )
                tid = kg.add_transformation_node(trans_node)
                sf, lr = t.get("source_file"), t.get("line_range")
                tt = t.get("transformation_type", "python")
                for src in t.get("sources", []):
                    kg.add_consumes_edge(tid, src, transformation_type=tt, source_file=sf, line_range=lr)
                for tgt in t.get("targets", []):
                    kg.add_produces_edge(tid, tgt, transformation_type=tt, source_file=sf, line_range=lr)
                python_flow_count += 1
        except Exception as e:
            logger.warning("Python data-flow failed for %s: %s", rel, e)
    for ref in all_dynamic_refs:
        logger.debug("Dynamic ref (unresolved): %s", ref)
    if all_dynamic_refs:
        logger.info("Hydrologist: logged %d unresolved dynamic references (Python)", len(all_dynamic_refs))
    logger.info("Hydrologist: extracted %d Python data-flow steps", python_flow_count)

    sql_deps_count = 0
    for rel in sql_files:
        try:
            deps_list = extract_lineage_from_file(str(repo_root), str(rel), dialect=sql_dialect)
        except Exception as e:
            logger.warning("sql_lineage failed for %s: %s", rel, e)
            continue
        if not deps_list:
            logger.debug("No dependencies extracted from %s", rel)
            continue
        sql_deps_count += len(deps_list)
        path_str = str(rel).replace("\\", "/")
        for d in deps_list:
            for t in d.get("source_tables", []):
                kg.add_dataset_node(DatasetNode(name=t, storage_type="table"))
            for t in d.get("target_tables", []):
                kg.add_dataset_node(DatasetNode(name=t, storage_type="table"))
            trans = TransformationNode(
                source_datasets=d.get("source_tables", []),
                target_datasets=d.get("target_tables", []),
                transformation_type="sql",
                source_file=path_str,
                line_range=d.get("line_range", (0, 0)),
                sql_query_if_applicable=d.get("sql_snippet"),
            )
            tid = kg.add_transformation_node(trans)
            lr = d.get("line_range", (0, 0))
            for src in d.get("source_tables", []):
                kg.add_consumes_edge(tid, src, transformation_type="sql", source_file=path_str, line_range=lr)
            for tgt in d.get("target_tables", []):
                kg.add_produces_edge(tid, tgt, transformation_type="sql", source_file=path_str, line_range=lr)
    
    logger.info("Hydrologist: extracted %d SQL dependencies", sql_deps_count)
    
    yaml_deps_count = 0
    for rel in yaml_files:
        try:
            out = analyze_dag_config(repo_root, rel)
        except Exception as e:
            logger.warning("dag_config failed for %s: %s", rel, e)
            continue
        config_file = out.get("config_file", str(rel))
        models = out.get("models", [])
        topology = out.get("topology", [])
        if not models and not topology:
            logger.debug("No models or topology found in %s", rel)
            continue
        yaml_deps_count += len(models) + len(topology)
        for m in models:
            kg.add_dataset_node(DatasetNode(name=m, storage_type="table"))
        for up, down in topology:
            kg.add_dataset_node(DatasetNode(name=up, storage_type="table"))
            kg.add_dataset_node(DatasetNode(name=down, storage_type="table"))
            kg.add_configures_edge(config_file, down, source_file=config_file)
    
    logger.info("Hydrologist: extracted %d YAML dependencies", yaml_deps_count)
    
    dag_deps_count = 0
    for rel in dag_py_files:
        try:
            out = analyze_dag_config(repo_root, rel)
        except Exception as e:
            logger.warning("dag_config failed for %s: %s", rel, e)
            continue
        task_ids = out.get("task_ids", [])
        topology = out.get("topology", [])
        if not task_ids and not topology:
            logger.debug("No task_ids or topology found in %s", rel)
            continue
        dag_deps_count += len(task_ids) + len(topology)
        cfg = out.get("config_file", str(rel))
        cfg_str = str(cfg).replace("\\", "/")
        for tid in task_ids:
            kg.add_dataset_node(DatasetNode(name=tid, storage_type="table"))
        for up, down in topology:
            kg.add_configures_edge(cfg_str, down, source_file=cfg_str)
    
    logger.info("Hydrologist: extracted %d DAG Python dependencies", dag_deps_count)
    total_nodes = kg.lineage_graph.number_of_nodes()
    total_edges = kg.lineage_graph.number_of_edges()
    logger.info("Hydrologist: lineage graph has %d nodes, %d edges", total_nodes, total_edges)


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
