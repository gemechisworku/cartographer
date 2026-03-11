"""Surveyor agent: builds module import graph (NetworkX DiGraph), runs PageRank and strongly connected components, analyzes git history for change velocity, and flags dead-code candidates (exported symbols with no import references).

Per specs/agents/surveyor.md. Populates knowledge graph with ModuleNode, FunctionNode, IMPORTS.
"""
import logging
import subprocess
from pathlib import Path
from typing import Any, Optional

import networkx as nx

from src.analyzers.tree_sitter_analyzer import analyze_module as analyzer_analyze_module
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.nodes import FunctionNode, ModuleNode

logger = logging.getLogger(__name__)

# Default dirs to skip when discovering files (like .gitignore)
DEFAULT_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "vendor", "dist", "build"}


def _discover_files(repo_root: Path, extensions: Optional[set[str]] = None) -> list[Path]:
    """Yield file paths under repo_root, skipping DEFAULT_SKIP_DIRS. If extensions given, filter by suffix."""
    repo_root = Path(repo_root)
    out: list[Path] = []
    for p in repo_root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in p.parts for part in DEFAULT_SKIP_DIRS):
            continue
        if extensions and p.suffix.lower() not in extensions:
            continue
        try:
            rel = p.relative_to(repo_root)
        except ValueError:
            continue
        out.append(rel)
    return out


def analyze_module(
    repo_root: str | Path,
    file_path: str | Path,
    kg: Optional[KnowledgeGraph] = None,
) -> tuple[Optional[ModuleNode], list[FunctionNode], list[tuple[str, str]]]:
    """Analyze one file; optionally add to kg. Returns (ModuleNode, list of FunctionNode, list of (source,target) imports)."""
    repo_root = Path(repo_root)
    file_path = Path(file_path)
    raw = analyzer_analyze_module(repo_root, file_path)
    path_str = str(file_path).replace("\\", "/")
    language = raw.get("language", file_path.suffix or "unknown")
    if language == "unknown" or (not raw["imports"] and not raw["functions"] and not raw["classes"]):
        # Unsupported or empty parse
        mod = ModuleNode(path=path_str, language=language, complexity_score=raw.get("complexity"))
        funcs: list[FunctionNode] = []
        imports: list[tuple[str, str]] = list(raw.get("imports", []))
        if kg:
            kg.add_module_node(mod)
            for imp in imports:
                kg.add_import_edge(imp[0], imp[1])
        return mod, funcs, imports

    complexity = raw.get("complexity")
    mod = ModuleNode(path=path_str, language=language, complexity_score=complexity)
    funcs = []
    for f in raw.get("functions", []):
        qname = f"{path_str}::{f['name']}"
        fn = FunctionNode(
            qualified_name=qname,
            parent_module=path_str,
            signature=f.get("signature"),
            is_public_api=True,
        )
        funcs.append(fn)
        if kg:
            kg.add_function_node(fn)
    for c in raw.get("classes", []):
        qname = f"{path_str}::{c['name']}"
        fn = FunctionNode(
            qualified_name=qname,
            parent_module=path_str,
            signature=None,
            is_public_api=True,
        )
        funcs.append(fn)
        if kg:
            kg.add_function_node(fn)

    imports = list(raw.get("imports", []))
    if kg:
        kg.add_module_node(mod)
        for imp in imports:
            kg.add_import_edge(imp[0], imp[1])
    return mod, funcs, imports


def extract_git_velocity(repo_root: str | Path, days: int = 30) -> dict[str, dict[str, Any]]:
    """Run git log --follow per file; return map file_path -> {change_velocity_30d, last_modified}."""
    repo_root = Path(repo_root)
    if not (repo_root / ".git").exists():
        logger.debug("Not a git repo: %s", repo_root)
        return {}

    result: dict[str, dict[str, Any]] = {}
    try:
        # Single git log for all files in window, then count by file
        cmd = ["git", "log", f"--since={days} days ago", "--follow", "--name-only", "--format=%H"]
        r = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return result
        lines = r.stdout.strip().splitlines()
        current_commit = None
        for line in lines:
            if len(line) == 40 and line.isalnum():
                current_commit = line
                continue
            if current_commit and line.strip():
                fp = line.strip().replace("\\", "/")
                if fp not in result:
                    result[fp] = {"commits": 0, "last_commit": current_commit}
                result[fp]["commits"] += 1
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("git velocity failed: %s", e)
        return result

    for fp, data in result.items():
        data["change_velocity_30d"] = data["commits"] / max(days, 1)
    return result


def run_surveyor(
    repo_root: str | Path,
    kg: KnowledgeGraph,
    *,
    days_velocity: int = 30,
    file_extensions: Optional[set[str]] = None,
) -> None:
    """Build module import graph (DiGraph), run PageRank, attach git velocity, detect SCCs and dead-code candidates."""
    repo_root = Path(repo_root)
    if file_extensions is None:
        file_extensions = {".py", ".sql", ".yml", ".yaml", ".js", ".ts", ".tsx"}
    files = _discover_files(repo_root, file_extensions)
    velocity_map = extract_git_velocity(repo_root, days=days_velocity)

    all_exported: set[str] = set()  # qualified_name of public functions/classes
    for fp in files:
        mod, funcs, imports = analyze_module(repo_root, fp, kg)
        for f in funcs:
            all_exported.add(f.qualified_name)
        # Attach velocity to module node
        fp_str = str(fp).replace("\\", "/")
        if fp_str in velocity_map:
            v = velocity_map[fp_str]
            if kg.module_graph.has_node(fp_str):
                attrs = dict(kg.module_graph.nodes[fp_str])
                attrs["change_velocity_30d"] = v.get("change_velocity_30d")
                kg.module_graph.add_node(fp_str, **attrs)

    # PageRank and SCCs (on module graph: only module path nodes, not function nodes)
    module_nodes = [n for n in kg.module_graph.nodes() if kg.module_graph.nodes[n].get("path") == n]
    if module_nodes:
        subg = kg.module_graph.subgraph(module_nodes)
        try:
            pr = nx.pagerank(subg, weight="weight")
            for nid in module_nodes:
                if nid in pr and kg.module_graph.has_node(nid):
                    attrs = dict(kg.module_graph.nodes[nid])
                    attrs["pagerank"] = pr[nid]
                    kg.module_graph.add_node(nid, **attrs)
        except Exception as e:
            logger.warning("PageRank failed: %s", e)
        try:
            sccs = list(nx.strongly_connected_components(subg))
            cycles = [c for c in sccs if len(c) > 1]
            if cycles:
                for nid in module_nodes:
                    if kg.module_graph.has_node(nid):
                        attrs = dict(kg.module_graph.nodes[nid])
                        attrs["in_cycle"] = any(nid in c for c in cycles)
                        kg.module_graph.add_node(nid, **attrs)
        except Exception as e:
            logger.warning("SCC failed: %s", e)

    # Dead-code: exported symbol with no incoming IMPORTS (simplified: no refs from other modules)
    import_targets = set()
    for _u, v in kg.module_graph.edges():
        edata = kg.module_graph.edges.get((_u, v), {})
        if edata.get("edge_type") == "IMPORTS":
            import_targets.add(v)
    for nid in list(kg.module_graph.nodes()):
        data = kg.module_graph.nodes.get(nid, {})
        if data.get("path") != nid:
            continue
        # Heuristic: module is dead-code candidate if it's never imported (and has no or few outgoing edges)
        if nid not in import_targets and kg.module_graph.out_degree(nid) == 0:
            if kg.module_graph.has_node(nid):
                attrs = dict(kg.module_graph.nodes[nid])
                attrs["is_dead_code_candidate"] = True
                kg.module_graph.add_node(nid, **attrs)
