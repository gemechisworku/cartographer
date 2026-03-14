"""Semanticist agent: LLM-powered purpose statements from code, doc drift, domain clustering, and Day-One answers.

Consumes Surveyor + Hydrologist output; updates ModuleNode.purpose_statement and domain_cluster;
produces Day-One answers with evidence and documentation drift flags for the Archivist.
Per specs/agents/semanticist.md.
"""
import ast
import logging
import os
from pathlib import Path
from typing import Any, Callable, Optional

from src.graph.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)

# Five FDE Day-One questions (verbatim from specs/overview.md)
DAY_ONE_QUESTIONS = [
    "What is the primary data ingestion path?",
    "What are the 3–5 most critical output datasets/endpoints?",
    "What is the blast radius if the most critical module fails?",
    "Where is the business logic concentrated vs. distributed?",
    "What has changed most frequently in the last 90 days (git velocity map)?",
]

# Default token budget for LLM calls (approximate)
DEFAULT_TOKEN_BUDGET = 500_000
CHARS_PER_TOKEN = 4


class ContextWindowBudget:
    """Tracks estimated token usage and enforces a configurable budget."""

    def __init__(self, limit: int = DEFAULT_TOKEN_BUDGET) -> None:
        self.limit = limit
        self._spent = 0

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // CHARS_PER_TOKEN)

    def would_exceed(self, additional_tokens: int) -> bool:
        return (self._spent + additional_tokens) > self.limit

    def add_usage(self, tokens: int) -> None:
        self._spent += tokens

    def remaining(self) -> int:
        return max(0, self.limit - self._spent)


def _get_module_docstring(code: str, language: str) -> Optional[str]:
    """Extract module-level docstring for Python; else None."""
    if language != "python":
        return None
    try:
        tree = ast.parse(code)
        return ast.get_docstring(tree)
    except SyntaxError:
        return None


def _read_file(repo_root: Path, path: str) -> str:
    """Read file content; return empty string on error."""
    full = repo_root / path
    try:
        return full.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.debug("Could not read %s: %s", full, e)
        return ""


def generate_purpose_statement(
    repo_root: Path,
    module_path: str,
    code: str,
    language: str,
    llm_completion: Callable[[str, str, int], str],
    budget: ContextWindowBudget,
    *,
    model: str = "gpt-4o-mini",
    max_tokens: int = 300,
) -> tuple[str, bool]:
    """Generate a 2–3 sentence purpose from code (not docstring). Return (purpose, doc_drift).

    If budget would be exceeded or LLM fails, returns placeholder and False for drift.
    """
    if not code.strip():
        return "No content.", False
    estimated = budget.estimate_tokens(code) + max_tokens
    if budget.would_exceed(estimated):
        logger.warning("Budget exceeded, skipping purpose for %s", module_path)
        return "", False
    prompt = f"""Based only on the following code (do not use docstrings), write 2-3 sentences describing what this module does from a business/functional perspective. Be concise.

Path: {module_path}
Language: {language}

Code:
```
{code[:8000]}
```

Purpose (2-3 sentences):"""
    try:
        response = llm_completion(prompt, model, max_tokens)
        budget.add_usage(estimated)
        purpose = (response or "").strip() or "Purpose not generated."
    except Exception as e:
        logger.warning("LLM purpose failed for %s: %s", module_path, e)
        return "Purpose generation failed.", False
    docstring = _get_module_docstring(code, language)
    drift = bool(
        docstring
        and purpose
        and purpose != "Purpose not generated."
        and purpose != "Purpose generation failed."
        and _contradicts(docstring, purpose)
    )
    return purpose, drift


def _contradicts(docstring: str, purpose: str) -> bool:
    """Heuristic: true if docstring and purpose seem to describe different things (simple keyword overlap check)."""
    a = set(docstring.lower().split())
    b = set(purpose.lower().split())
    overlap = len(a & b) / max(1, min(len(a), len(b)))
    return overlap < 0.2 and len(a) > 5 and len(b) > 5


def cluster_into_domains(
    kg: KnowledgeGraph,
    embed_fn: Callable[[list[str]], list[list[float]]],
    *,
    k: int = 6,
    label_fn: Optional[Callable[[list[str], str], str]] = None,
) -> list[tuple[str, str]]:
    """Assign domain_cluster to each module with a purpose_statement; return list of (cluster_id, label)."""
    import numpy as np
    from scipy.cluster.vq import kmeans2

    module_paths: list[str] = []
    purposes: list[str] = []
    for nid in kg.module_graph.nodes():
        data = kg.module_graph.nodes.get(nid, {})
        if data.get("path") != nid:
            continue
        p = data.get("purpose_statement") or ""
        if not p.strip():
            continue
        module_paths.append(nid)
        purposes.append(p)
    if len(purposes) < k:
        k = max(1, len(purposes))
    if not purposes:
        return []
    try:
        vectors = np.array(embed_fn(purposes), dtype=np.float64)
    except Exception as e:
        logger.warning("Embedding failed for domain clustering: %s", e)
        return []
    if vectors.size == 0:
        return []
    try:
        centroids, labels = kmeans2(vectors, k, minit="points")
    except Exception as e:
        logger.warning("k-means failed: %s", e)
        return []
    cluster_to_paths: dict[int, list[str]] = {}
    for i, path in enumerate(module_paths):
        if i < len(labels):
            cluster_to_paths.setdefault(int(labels[i]), []).append(path)
    # Assign cluster labels (optionally via LLM)
    cluster_labels: dict[int, str] = {}
    for cid in cluster_to_paths:
        cluster_labels[cid] = f"cluster_{cid}"
        if label_fn:
            sample_purposes = [purposes[module_paths.index(p)] for p in cluster_to_paths[cid][:3]]
            cluster_labels[cid] = label_fn(sample_purposes, f"cluster_{cid}") or cluster_labels[cid]
    # Update graph
    for i, path in enumerate(module_paths):
        if i >= len(labels):
            continue
        cid = int(labels[i])
        cluster_label = cluster_labels.get(cid, f"cluster_{cid}")
        if kg.module_graph.has_node(path):
            attrs = dict(kg.module_graph.nodes[path])
            attrs["domain_cluster"] = cluster_label
            kg.module_graph.add_node(path, **attrs)
    return [(f"cluster_{cid}", cluster_labels.get(cid, f"cluster_{cid}")) for cid in sorted(cluster_to_paths.keys())]


def _build_synthesis_context(kg: KnowledgeGraph) -> str:
    """Build a text summary of module graph and lineage for Day-One synthesis."""
    parts = []
    # Module graph: top by PageRank
    module_nodes = [n for n in kg.module_graph.nodes() if kg.module_graph.nodes[n].get("path") == n]
    if module_nodes:
        pr_list = [(n, kg.module_graph.nodes[n].get("pagerank", 0)) for n in module_nodes]
        pr_list.sort(key=lambda x: x[1], reverse=True)
        parts.append("Top modules by PageRank (critical path):")
        for n, pr in pr_list[:10]:
            vel = kg.module_graph.nodes[n].get("change_velocity_30d")
            parts.append(f"  - {n} (pagerank={pr:.4f}, change_velocity_30d={vel})")
    # Lineage: sources and sinks
    from src.agents.hydrologist import find_sources, find_sinks

    sources = find_sources(kg)
    sinks = find_sinks(kg)
    parts.append("\nData lineage sources (entry points): " + ", ".join(sources[:15]) if sources else "\nData lineage sources: (none)")
    parts.append("Data lineage sinks (exit points): " + ", ".join(sinks[:15]) if sinks else "Data lineage sinks: (none)")
    # Purpose index (sample)
    purposes = []
    for n in module_nodes[:20]:
        p = kg.module_graph.nodes[n].get("purpose_statement")
        if p:
            purposes.append(f"  - {n}: {p[:200]}")
    if purposes:
        parts.append("\nSample module purposes:\n" + "\n".join(purposes))
    return "\n".join(parts)


def answer_day_one_questions(
    kg: KnowledgeGraph,
    llm_completion: Callable[[str, str, int], str],
    budget: ContextWindowBudget,
    *,
    model: str = "gpt-4o",
    max_tokens: int = 2000,
) -> list[dict[str, Any]]:
    """Synthesize Five Day-One answers with evidence citations. Returns list of {question, answer, citations}."""
    context = _build_synthesis_context(kg)
    estimated = budget.estimate_tokens(context) + max_tokens
    if budget.would_exceed(estimated):
        logger.warning("Budget exceeded for Day-One synthesis")
        return [{"question": q, "answer": "Skipped (budget).", "citations": []} for q in DAY_ONE_QUESTIONS]
    prompt = f"""You are summarizing a codebase for a new engineer (Day-One brief). Use ONLY the following context. For each of the five questions, give a short answer and cite evidence (file path and line range or module name when available). Format each answer as: "ANSWER: ..." then "CITATIONS: file:line or module name, ..."

Context:
{context}

Questions:
"""
    for i, q in enumerate(DAY_ONE_QUESTIONS, 1):
        prompt += f"{i}. {q}\n"
    prompt += "\nProvide answers 1-5 in order with ANSWER and CITATIONS for each."
    try:
        response = llm_completion(prompt, model, max_tokens)
        budget.add_usage(estimated)
    except Exception as e:
        logger.warning("Day-One synthesis failed: %s", e)
        return [{"question": q, "answer": "Synthesis failed.", "citations": []} for q in DAY_ONE_QUESTIONS]
    # Parse response into structured list (best-effort)
    block = response or ""
    results = []
    for i, q in enumerate(DAY_ONE_QUESTIONS):
        answer = "(no answer generated)"
        citations: list[str] = []
        # Look for numbered block "1." or "ANSWER:" / "CITATIONS:"
        marker = f"{i + 1}."
        if marker in block:
            segment = block.split(marker, 1)[-1].split(f"{i + 2}.")[0] if i + 2 <= len(DAY_ONE_QUESTIONS) else block.split(marker, 1)[-1]
        else:
            segment = block
        if "ANSWER:" in segment:
            answer_part = segment.split("ANSWER:")[-1].split("CITATIONS:")[0].strip()
            answer = answer_part.split("\n\n")[0].strip()[:1500] or answer
        if "CITATIONS:" in segment:
            cit_part = segment.split("CITATIONS:")[-1].strip().split("\n")[0].strip()[:500]
            citations = [c.strip() for c in cit_part.replace(",", " ").split() if c.strip() and ("/" in c or ":" in c or ".py" in c)]
        results.append({"question": q, "answer": answer, "citations": citations})
    return results


def _default_llm_completion(prompt: str, model: str, max_tokens: int) -> str:
    """Use OpenAI-compatible API when OPENAI_API_KEY or OPENROUTER_API_KEY is set; else return placeholder."""
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL") or (None if os.environ.get("OPENAI_API_KEY") else "https://openrouter.ai/api/v1")
    if not api_key:
        return "[Purpose/synthesis skipped: no OPENAI_API_KEY or OPENROUTER_API_KEY set]"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        r = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], max_tokens=max_tokens)
        return (r.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning("OpenAI/OpenRouter call failed: %s", e)
        return "[LLM call failed]"


def _default_embed(texts: list[str]) -> list[list[float]]:
    """Default embeddings: use OpenAI when key set; else deterministic pseudo-embeddings (for clustering without API)."""
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            dim = 1536
            out = []
            for i in range(0, len(texts), 100):
                batch = texts[i : i + 100]
                r = client.embeddings.create(model="text-embedding-3-small", input=batch)
                for e in r.data:
                    out.append(e.embedding)
            return out[:len(texts)]
        except Exception as e:
            logger.warning("Embedding API failed, using fallback: %s", e)
    # Fallback: deterministic 32-dim vector from hash for reproducibility in tests
    import hashlib
    dim = 32
    out = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        vec = [(int(h[i % len(h)]) - 128) / 128.0 for i in range(dim)]
        out.append(vec)
    return out


def run_semanticist(
    repo_root: str | Path,
    kg: KnowledgeGraph,
    *,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    llm_completion: Optional[Callable[[str, str, int], str]] = None,
    embed_fn: Optional[Callable[[list[str]], list[list[float]]]] = None,
    purpose_model: str = "gpt-4o-mini",
    synthesis_model: str = "gpt-4o",
    skip_purpose: bool = False,
    skip_cluster: bool = False,
    skip_day_one: bool = False,
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """Run Semanticist: purpose statements, domain clustering, Day-One answers. Updates kg in place.

    Returns (day_one_answers, documentation_drift_list).
    """
    repo_root = Path(repo_root)
    budget = ContextWindowBudget(limit=token_budget)
    llm = llm_completion or _default_llm_completion
    embed = embed_fn or _default_embed
    drift_list: list[tuple[str, str]] = []

    # 1) Purpose statements for each module (file) node
    if not skip_purpose:
        module_paths = [n for n in kg.module_graph.nodes() if kg.module_graph.nodes[n].get("path") == n]
        for path in module_paths:
            lang = kg.module_graph.nodes[path].get("language", "python")
            if lang not in ("python", "javascript", "typescript"):
                continue
            code = _read_file(repo_root, path)
            if not code.strip():
                continue
            purpose, drift = generate_purpose_statement(repo_root, path, code, lang, llm, budget, model=purpose_model)
            if purpose:
                if kg.module_graph.has_node(path):
                    attrs = dict(kg.module_graph.nodes[path])
                    attrs["purpose_statement"] = purpose
                    kg.module_graph.add_node(path, **attrs)
            if drift:
                docstring = _get_module_docstring(code, lang)
                drift_list.append((path, docstring or ""))

    # 2) Domain clustering
    if not skip_cluster:
        def _label_cluster(sample_purposes: list[str], cid: str) -> str:
            if not sample_purposes:
                return cid
            text = " ".join(sample_purposes[:3])
            est = budget.estimate_tokens(text) + 100
            if budget.would_exceed(est):
                return cid
            try:
                return llm(f"Label this domain in 1-3 words (e.g. ingestion, transformation, serving): {text}", synthesis_model, 50) or cid
            except Exception:
                return cid
        cluster_into_domains(kg, embed, k=6, label_fn=_label_cluster)

    # 3) Day-One answers
    day_one = answer_day_one_questions(kg, llm, budget, model=synthesis_model) if not skip_day_one else [{"question": q, "answer": "(skipped)", "citations": []} for q in DAY_ONE_QUESTIONS]

    return day_one, drift_list
