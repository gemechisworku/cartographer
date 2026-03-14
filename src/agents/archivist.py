"""Archivist agent: produces and maintains .cartography/ artifacts — CODEBASE.md, onboarding_brief.md, lineage_graph.json, semantic_index/, cartography_trace.jsonl. Supports incremental update (changed files). Per specs/agents/archivist.md."""
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from src.agents.hydrologist import find_sources, find_sinks
from src.graph.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)

# Trace record: agent, action, input, output_summary, confidence (optional)
TRACE_ACTION_WRITE_ARTIFACT = "write_artifact"
TRACE_ACTION_INCREMENTAL_DIFF = "incremental_diff"


def _module_nodes_sorted_by_pagerank(kg: KnowledgeGraph, top_n: int = 5) -> list[tuple[str, float]]:
    """Return list of (module_path, pagerank) for module nodes, top N by PageRank."""
    module_nodes = [
        n for n in kg.module_graph.nodes()
        if kg.module_graph.nodes[n].get("path") == n
    ]
    with_pr = [(n, kg.module_graph.nodes[n].get("pagerank", 0.0)) for n in module_nodes]
    with_pr.sort(key=lambda x: x[1], reverse=True)
    return with_pr[:top_n]


def _modules_in_cycles(kg: KnowledgeGraph) -> list[str]:
    """Return module paths that are in a strongly connected component (cycle)."""
    module_nodes = [
        n for n in kg.module_graph.nodes()
        if kg.module_graph.nodes[n].get("path") == n
    ]
    return [n for n in module_nodes if kg.module_graph.nodes[n].get("in_cycle")]


def _top_velocity_modules(kg: KnowledgeGraph, top_n: int = 10) -> list[tuple[str, float]]:
    """Return (path, change_velocity_30d) for top N by velocity."""
    module_nodes = [
        n for n in kg.module_graph.nodes()
        if kg.module_graph.nodes[n].get("path") == n
    ]
    with_vel = [
        (n, kg.module_graph.nodes[n].get("change_velocity_30d") or 0.0)
        for n in module_nodes
    ]
    with_vel.sort(key=lambda x: x[1], reverse=True)
    return with_vel[:top_n]


def _build_architecture_overview(kg: KnowledgeGraph) -> str:
    """One paragraph summary from module graph + lineage high level."""
    mod_count = sum(1 for n in kg.module_graph.nodes() if kg.module_graph.nodes[n].get("path") == n)
    lineage_nodes = kg.lineage_graph.number_of_nodes()
    lineage_edges = kg.lineage_graph.number_of_edges()
    sources = find_sources(kg)
    sinks = find_sinks(kg)
    parts = [
        f"This codebase has {mod_count} analyzed modules and a data lineage graph with {lineage_nodes} nodes and {lineage_edges} edges.",
        f"Data entry points (sources): {len(sources)}; exit points (sinks): {len(sinks)}.",
    ]
    if sources:
        parts.append(f" Representative sources: {', '.join(sources[:5])}.")
    if sinks:
        parts.append(f" Representative sinks: {', '.join(sinks[:5])}.")
    return " ".join(parts).strip()


def generate_CODEBASE_md(
    kg: KnowledgeGraph,
    documentation_drift: list[tuple[str, str]],
    *,
    top_pagerank_n: int = 5,
    top_velocity_n: int = 10,
) -> str:
    """Build CODEBASE.md content: Architecture Overview, Critical Path, Data Sources & Sinks, Known Debt, Recent Change Velocity, Module Purpose Index."""
    sections: list[str] = []

    # 1. Architecture Overview
    sections.append("## Architecture Overview\n")
    sections.append(_build_architecture_overview(kg))
    sections.append("\n")

    # 2. Critical Path (top 5 by PageRank)
    sections.append("## Critical Path\n")
    critical = _module_nodes_sorted_by_pagerank(kg, top_n=top_pagerank_n)
    if critical:
        for path, pr in critical:
            sections.append(f"- {path} (PageRank: {pr:.4f})\n")
    else:
        sections.append("(No PageRank data available.)\n")
    sections.append("\n")

    # 3. Data Sources & Sinks
    sections.append("## Data Sources & Sinks\n")
    sources = find_sources(kg)
    sinks = find_sinks(kg)
    sections.append("**Sources (entry points):**\n")
    for s in sources[:20]:
        sections.append(f"- {s}\n")
    if not sources:
        sections.append("(None identified.)\n")
    sections.append("\n**Sinks (exit points):**\n")
    for s in sinks[:20]:
        sections.append(f"- {s}\n")
    if not sinks:
        sections.append("(None identified.)\n")
    sections.append("\n")

    # 4. Known Debt (circular deps + documentation drift)
    sections.append("## Known Debt\n")
    cycles = _modules_in_cycles(kg)
    if cycles:
        sections.append("**Circular dependencies (SCCs):**\n")
        for p in cycles[:15]:
            sections.append(f"- {p}\n")
        sections.append("\n")
    drift_paths = [p for p, _ in documentation_drift]
    if drift_paths:
        sections.append("**Documentation drift (docstring vs. inferred purpose):**\n")
        for p in drift_paths[:15]:
            sections.append(f"- {p}\n")
        sections.append("\n")
    if not cycles and not drift_paths:
        sections.append("(No circular dependencies or documentation drift flagged.)\n\n")

    # 5. Recent Change Velocity
    sections.append("## Recent Change Velocity\n")
    vel_list = _top_velocity_modules(kg, top_n=top_velocity_n)
    if vel_list:
        for path, vel in vel_list:
            sections.append(f"- {path} (change_velocity_30d: {vel:.2f})\n")
    else:
        sections.append("(No git velocity data available.)\n")
    sections.append("\n")

    # 6. Module Purpose Index
    sections.append("## Module Purpose Index\n")
    module_nodes = [
        n for n in kg.module_graph.nodes()
        if kg.module_graph.nodes[n].get("path") == n
    ]
    for path in sorted(module_nodes):
        purpose = (kg.module_graph.nodes[path].get("purpose_statement") or "").strip()
        if purpose:
            # One line per module for quick lookup
            purpose_escaped = purpose.replace("\n", " ").strip()[:300]
            sections.append(f"- **{path}**: {purpose_escaped}\n")
    if not any(kg.module_graph.nodes[n].get("purpose_statement") for n in module_nodes):
        sections.append("(No purpose statements generated.)\n")

    return "# CODEBASE.md\n\n" + "".join(sections)


def generate_onboarding_brief_md(day_one_answers: list[dict[str, Any]]) -> str:
    """Produce onboarding_brief.md from Semanticist Day-One answers (five questions + evidence)."""
    lines = ["# Day-One Brief\n", "\n"]
    for i, item in enumerate(day_one_answers, 1):
        q = item.get("question", "")
        a = item.get("answer", "(no answer)")
        citations = item.get("citations", [])
        lines.append(f"## {i}. {q}\n\n")
        lines.append(f"{a}\n\n")
        if citations:
            lines.append("**Citations:** " + ", ".join(citations) + "\n\n")
    return "".join(lines)


def get_changed_files(repo_path: str | Path, since_ref: str = "HEAD~1") -> list[str]:
    """Return list of file paths (relative to repo) changed since since_ref. Uses git diff --name-only."""
    repo_path = Path(repo_path)
    if not (repo_path / ".git").is_dir():
        logger.debug("Not a git repo: %s", repo_path)
        return []
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", since_ref, "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            return []
        return [line.strip().replace("\\", "/") for line in r.stdout.strip().splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("git diff failed: %s", e)
        return []


def run_archivist(
    repo_path: str | Path,
    kg: KnowledgeGraph,
    output_dir: str | Path,
    day_one_answers: list[dict[str, Any]],
    documentation_drift: list[tuple[str, str]],
    *,
    trace_entries: list[dict[str, Any]] | None = None,
    write_module_graph: bool = True,
    write_lineage_graph: bool = True,
    write_day_one_json: bool = True,
    write_documentation_drift_json: bool = True,
) -> list[dict[str, Any]]:
    """Write all .cartography/ artifacts. Returns list of trace records (including new ones) for cartography_trace.jsonl.

    Writes: CODEBASE.md, onboarding_brief.md, module_graph.json, lineage_graph.json,
    day_one_answers.json, documentation_drift.json, semantic_index/, cartography_trace.jsonl.
    """
    repo_path = Path(repo_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    trace: list[dict[str, Any]] = list(trace_entries) if trace_entries else []

    def append_trace(agent: str, action: str, input_summary: str, output_summary: str, confidence: str | None = None) -> None:
        rec = {
            "agent": agent,
            "action": action,
            "input": input_summary,
            "output_summary": output_summary,
        }
        if confidence is not None:
            rec["confidence"] = confidence
        trace.append(rec)

    # CODEBASE.md
    codebase_md = generate_CODEBASE_md(kg, documentation_drift)
    (out / "CODEBASE.md").write_text(codebase_md, encoding="utf-8")
    append_trace("archivist", TRACE_ACTION_WRITE_ARTIFACT, "knowledge_graph", "CODEBASE.md", "static")
    logger.info("Wrote %s/CODEBASE.md", out)

    # onboarding_brief.md
    onboarding_md = generate_onboarding_brief_md(day_one_answers)
    (out / "onboarding_brief.md").write_text(onboarding_md, encoding="utf-8")
    append_trace("archivist", TRACE_ACTION_WRITE_ARTIFACT, "day_one_answers", "onboarding_brief.md", "static")
    logger.info("Wrote %s/onboarding_brief.md", out)

    # module_graph.json
    if write_module_graph:
        kg.write_module_graph_json(out / "module_graph.json")
        append_trace("archivist", TRACE_ACTION_WRITE_ARTIFACT, "module_graph", "module_graph.json", "static")

    # lineage_graph.json
    if write_lineage_graph:
        kg.write_lineage_graph_json(out / "lineage_graph.json")
        append_trace("archivist", TRACE_ACTION_WRITE_ARTIFACT, "lineage_graph", "lineage_graph.json", "static")

    # day_one_answers.json
    if write_day_one_json:
        (out / "day_one_answers.json").write_text(json.dumps(day_one_answers, indent=2), encoding="utf-8")
        append_trace("archivist", TRACE_ACTION_WRITE_ARTIFACT, "day_one_answers", "day_one_answers.json", "static")

    # documentation_drift.json
    if write_documentation_drift_json:
        drift_json = [{"module_path": p, "docstring_excerpt": d[:500]} for p, d in documentation_drift]
        (out / "documentation_drift.json").write_text(json.dumps(drift_json, indent=2), encoding="utf-8")
        append_trace("archivist", TRACE_ACTION_WRITE_ARTIFACT, "documentation_drift", "documentation_drift.json", "static")

    # semantic_index/ (purpose index for Navigator find_implementation)
    semantic_dir = out / "semantic_index"
    semantic_dir.mkdir(parents=True, exist_ok=True)
    purpose_index: list[dict[str, Any]] = []
    for nid in kg.module_graph.nodes():
        data = kg.module_graph.nodes.get(nid, {})
        if data.get("path") != nid:
            continue
        purpose = data.get("purpose_statement") or ""
        domain = data.get("domain_cluster") or ""
        if purpose or domain:
            purpose_index.append({"path": nid, "purpose_statement": purpose, "domain_cluster": domain})
    (semantic_dir / "purpose_index.json").write_text(json.dumps(purpose_index, indent=2), encoding="utf-8")
    append_trace("archivist", TRACE_ACTION_WRITE_ARTIFACT, "purpose_index", "semantic_index/purpose_index.json", "static")
    logger.info("Wrote %s/semantic_index/purpose_index.json", out)

    # cartography_trace.jsonl
    trace_path = out / "cartography_trace.jsonl"
    with open(trace_path, "w", encoding="utf-8") as f:
        for rec in trace:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("Wrote %s/cartography_trace.jsonl (%d records)", out, len(trace))

    return trace
