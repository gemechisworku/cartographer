"""Navigator agent: query interface to the knowledge graph with four tools and evidence citations.

Tools: find_implementation, trace_lineage, blast_radius, explain_module.
Every response cites source file, line range, and analysis method (static vs LLM).
Per specs/agents/navigator.md. No LangGraph dependency; implements a simple tool-calling REPL.
"""
import json
import logging
from pathlib import Path
from typing import Any, Literal

from src.agents.hydrologist import blast_radius as hydrologist_blast_radius
from src.graph.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)

# Evidence citation suffix for each tool
CITATION_STATIC_LINEAGE = "static analysis (lineage graph)."
CITATION_STATIC_LINEAGE_AND_MODULE = "static analysis (lineage + module graph)."
CITATION_SEMANTIC = "semantic search (LLM-derived purpose)."
CITATION_LLM = "Purpose from semantic analysis (LLM)."
CITATION_STATIC_STRUCTURE = "Structure from static analysis (tree-sitter)."


def _load_purpose_index(cartography_dir: Path) -> list[dict[str, Any]]:
    """Load semantic_index/purpose_index.json; return list of {path, purpose_statement, domain_cluster}."""
    path = cartography_dir / "semantic_index" / "purpose_index.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not load purpose index: %s", e)
        return []


def find_implementation(
    concept: str,
    purpose_index: list[dict[str, Any]],
    *,
    top_k: int = 10,
) -> tuple[list[dict[str, Any]], str]:
    """Search purpose statements for where a concept is implemented. Returns (matches, citation)."""
    concept_lower = concept.lower().strip()
    if not concept_lower:
        return [], CITATION_SEMANTIC
    # Prefix match: concept "orchestrator" should match text containing "orchestrates" (shared stem)
    def _matches(c: str, text: str) -> bool:
        if c in text:
            return True
        for w in c.split():
            if len(w) <= 2:
                continue
            if w in text:
                return True
            # 5+ char prefix of word (e.g. "orchestr" from "orchestrator") matches inside any word
            if len(w) >= 5 and w[:6] in text:
                return True
        return False
    matches: list[dict[str, Any]] = []
    for entry in purpose_index:
        path = entry.get("path", "")
        purpose = (entry.get("purpose_statement") or "").lower()
        domain = (entry.get("domain_cluster") or "").lower()
        text = f"{purpose} {domain}"
        if not _matches(concept_lower, text):
            continue
        score = 0.5
        if concept_lower in purpose:
            score = 0.9
        elif concept_lower in domain:
            score = 0.7
        elif len(concept_lower) >= 5 and concept_lower[:6] in text:
            score = 0.6
        matches.append({
                "path": path,
                "line_range": None,
                "snippet": (entry.get("purpose_statement") or "")[:200],
                "confidence": score,
            })
    matches.sort(key=lambda m: m["confidence"], reverse=True)
    return matches[:top_k], CITATION_SEMANTIC


def _edge_type(G, u: str, v: str) -> str | None:
    """Return edge type between u and v in graph G."""
    if not G.has_edge(u, v):
        return None
    return G.edges[u, v].get("edge_type")


def trace_lineage(
    kg: KnowledgeGraph,
    dataset: str,
    direction: Literal["upstream", "downstream"],
) -> tuple[list[dict[str, Any]], str]:
    """Traverse lineage graph upstream or downstream from a dataset. Returns (chain, citation)."""
    G = kg.lineage_graph
    if not G.has_node(dataset):
        for nid in G.nodes():
            if dataset.lower() in nid.lower():
                dataset = nid
                break
        else:
            return [], CITATION_STATIC_LINEAGE
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    stack = [dataset]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        data = G.nodes.get(n, {})
        node_type = "transformation" if data.get("source_file") else "dataset"
        chain.append({
            "node_id": n,
            "type": node_type,
            "source_file": data.get("source_file"),
            "line_range": data.get("line_range"),
        })
        if direction == "upstream":
            # T produces n => T is predecessor with PRODUCES; then S consumed by T => S is predecessor of T with CONSUMES
            for pred in G.predecessors(n):
                if _edge_type(G, pred, n) == "PRODUCES":
                    stack.append(pred)
                if _edge_type(G, pred, n) == "CONSUMES":
                    stack.append(pred)
        else:
            # n is consumed by T => T is successor with CONSUMES; T produces D => D is successor of T with PRODUCES
            for succ in G.successors(n):
                if _edge_type(G, n, succ) in ("PRODUCES", "CONSUMES"):
                    stack.append(succ)
    return chain, CITATION_STATIC_LINEAGE


def blast_radius(
    kg: KnowledgeGraph,
    module_path: str,
) -> tuple[list[dict[str, Any]], str]:
    """Return affected nodes if this module changes: lineage impact + modules that import it."""
    results: list[dict[str, Any]] = []
    # Lineage: blast_radius on lineage graph (node_id can be dataset or transformation id)
    lineage_affected = hydrologist_blast_radius(kg, module_path)
    for node_id, source_file, line_range in lineage_affected:
        results.append({
            "node_id": node_id,
            "source_file": source_file,
            "line_range": line_range,
        })
    # Module graph: who imports this module?
    MG = kg.module_graph
    if MG.has_node(module_path):
        for importer in MG.predecessors(module_path):
            edata = MG.edges.get((importer, module_path), {})
            if edata.get("edge_type") == "IMPORTS":
                results.append({
                    "node_id": importer,
                    "source_file": importer if MG.nodes.get(importer, {}).get("path") == importer else None,
                    "line_range": None,
                })
    return results, CITATION_STATIC_LINEAGE_AND_MODULE


def explain_module(
    kg: KnowledgeGraph,
    module_path: str,
    purpose_index: list[dict[str, Any]] | None = None,
) -> tuple[str, list[str]]:
    """Produce short explanation of a module from graph + purpose index. Returns (explanation, citations)."""
    citations: list[str] = []
    parts = []
    # From module graph
    MG = kg.module_graph
    if MG.has_node(module_path):
        data = MG.nodes[module_path]
        purpose = data.get("purpose_statement")
        domain = data.get("domain_cluster")
        if purpose:
            parts.append(purpose)
            citations.append(CITATION_LLM)
        if domain:
            parts.append(f"Domain: {domain}.")
        complexity = data.get("complexity_score")
        if complexity is not None:
            parts.append(f"Complexity: {complexity}.")
            citations.append(CITATION_STATIC_STRUCTURE)
    # Fallback: purpose index
    if not parts and purpose_index:
        for entry in purpose_index:
            if entry.get("path") == module_path:
                p = entry.get("purpose_statement")
                d = entry.get("domain_cluster")
                if p:
                    parts.append(p)
                    citations.append(CITATION_LLM)
                if d:
                    parts.append(f"Domain: {d}.")
                break
    if not parts:
        return (
            f"Module {module_path} not found in the knowledge graph. "
            "Re-run 'cartographer analyze' to include recently added or changed files."
        ), [CITATION_STATIC_STRUCTURE]
    explanation = " ".join(parts).strip()
    if not citations:
        citations.append(CITATION_STATIC_STRUCTURE)
    return explanation, citations


def load_cartography(cartography_dir: str | Path) -> tuple[KnowledgeGraph, list[dict[str, Any]]]:
    """Load knowledge graph and purpose index from .cartography/ directory. Returns (kg, purpose_index)."""
    cartography_dir = Path(cartography_dir)
    kg = KnowledgeGraph()
    mod_path = cartography_dir / "module_graph.json"
    lin_path = cartography_dir / "lineage_graph.json"
    if mod_path.exists():
        kg.load_module_graph_json(mod_path)
    if lin_path.exists():
        kg.load_lineage_graph_json(lin_path)
    purpose_index = _load_purpose_index(cartography_dir)
    return kg, purpose_index


def run_interactive(
    kg: KnowledgeGraph,
    purpose_index: list[dict[str, Any]],
    *,
    prompt: str = "Query (find/trace/blast/explain or natural language; empty to exit): ",
) -> None:
    """Simple REPL: read query, dispatch to a tool, print result with citations."""
    print("Navigator — query the codebase graph. Commands: /find <concept>, /trace <dataset> upstream|downstream, /blast <module_path>, /explain <path>. Or ask in natural language.")
    while True:
        try:
            line = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not line:
            break
        # Dispatch
        if line.startswith("/find "):
            concept = line[6:].strip()
            matches, cit = find_implementation(concept, purpose_index)
            print(f"find_implementation({concept!r}): {len(matches)} matches. Citation: {cit}")
            for m in matches[:5]:
                print(f"  - {m['path']} (confidence={m.get('confidence', 0)})")
            continue
        if line.startswith("/trace "):
            rest = line[7:].strip().split()
            if len(rest) < 2:
                print("Usage: /trace <dataset> upstream|downstream")
                continue
            dataset, dir_str = rest[0], rest[1].lower()
            if dir_str not in ("upstream", "downstream"):
                print("Direction must be upstream or downstream")
                continue
            chain, cit = trace_lineage(kg, dataset, dir_str)
            print(f"trace_lineage({dataset!r}, {dir_str}): {len(chain)} nodes. Citation: {cit}")
            for c in chain[:15]:
                sf = c.get("source_file") or c["node_id"]
                lr = c.get("line_range")
                print(f"  - {c['node_id']} ({c['type']}) @ {sf}" + (f" {lr}" if lr else ""))
            continue
        if line.startswith("/blast "):
            mod = line[7:].strip()
            results, cit = blast_radius(kg, mod)
            print(f"blast_radius({mod!r}): {len(results)} affected. Citation: {cit}")
            for r in results[:15]:
                print(f"  - {r['node_id']} @ {r.get('source_file')} {r.get('line_range')}")
            continue
        if line.startswith("/explain "):
            path = line[9:].strip()
            explanation, citations = explain_module(kg, path, purpose_index)
            print(f"explain_module({path!r}):")
            print(f"  {explanation}")
            print("  Citations:", "; ".join(citations))
            continue
        # Natural language: simple keyword routing
        line_lower = line.lower()
        if "where" in line_lower and ("implement" in line_lower or "logic" in line_lower or "code" in line_lower):
            concept = line.replace("?", "").strip()
            for w in ("where is", "where's", "where are"):
                if concept.lower().startswith(w):
                    concept = concept[len(w):].strip()
                    break
            matches, cit = find_implementation(concept, purpose_index)
            print(f"find_implementation: {len(matches)} matches. Citation: {cit}")
            for m in matches[:5]:
                print(f"  - {m['path']}")
            continue
        if "produce" in line_lower or "upstream" in line_lower or "source" in line_lower:
            words = line.replace("?", "").split()
            dataset = words[-1] if words else ""
            chain, cit = trace_lineage(kg, dataset, "upstream")
            print(f"trace_lineage upstream from {dataset}: {len(chain)} nodes. Citation: {cit}")
            for c in chain[:10]:
                print(f"  - {c['node_id']}")
            continue
        if "break" in line_lower or "blast" in line_lower or "affect" in line_lower:
            # Try to extract module path (last word or quoted)
            words = line.split()
            mod = words[-1].strip(".?") if words else ""
            if mod:
                results, cit = blast_radius(kg, mod)
                print(f"blast_radius({mod}): {len(results)} affected. Citation: {cit}")
                for r in results[:10]:
                    print(f"  - {r['node_id']}")
            else:
                print("Specify a module path for blast radius.")
            continue
        if "explain" in line_lower:
            words = line.replace("?", "").split()
            path = words[-1].strip(".?") if words else ""
            if path:
                explanation, citations = explain_module(kg, path, purpose_index)
                print(explanation)
                print("Citations:", "; ".join(citations))
            else:
                print("Specify a module path to explain.")
            continue
        # Default: try find_implementation with full line as concept
        matches, cit = find_implementation(line, purpose_index)
        print(f"find_implementation: {len(matches)} matches. Citation: {cit}")
        for m in matches[:5]:
            print(f"  - {m['path']}")


def run_query(cartography_dir: str | Path) -> None:
    """Load .cartography/ and run Navigator interactive loop."""
    cartography_dir = Path(cartography_dir)
    if not cartography_dir.is_dir():
        raise NotADirectoryError(str(cartography_dir))
    kg, purpose_index = load_cartography(cartography_dir)
    run_interactive(kg, purpose_index)
