# Deliverables and Rubric

This spec lists **interim and final deliverables** (code, artifacts, PDF report) and the **evaluation rubric**. Dates and file paths are authoritative for submission.

**Depends on:** [specs/overview.md](../specs/overview.md), [specs/pipeline-and-cli.md](../specs/pipeline-and-cli.md).

**Canonical source:** [cartographer_challenge_spec.md](cartographer_challenge_spec.md).

---

## Interim — Thursday March 12, 03:00 UTC

### GitHub code

| Path | Description |
|------|-------------|
| src/cli.py | Entry point; takes repo path (local or GitHub URL); runs analysis. |
| src/orchestrator.py | Wires Surveyor + Hydrologist in sequence; serializes outputs to .cartography/ |
| src/models/ | All Pydantic schemas (Node types, Edge types, Graph types). |
| src/analyzers/tree_sitter_analyzer.py | Multi-language AST parsing with LanguageRouter. |
| src/analyzers/sql_lineage.py | sqlglot-based SQL dependency extraction. |
| src/analyzers/dag_config_parser.py | Airflow/dbt YAML config parsing. |
| src/agents/surveyor.py | Module graph, PageRank, git velocity, dead code candidates. |
| src/agents/hydrologist.py | DataLineageGraph, blast_radius, find_sources/find_sinks. |
| src/graph/knowledge_graph.py | NetworkX wrapper with serialization. |
| pyproject.toml | With locked deps (uv). |
| README.md | How to install and run; at least `analyze` command documented. |

### Cartography artifacts (at least 1 target codebase)

- .cartography/module_graph.json  
- .cartography/lineage_graph.json (partial acceptable — at minimum SQL lineage via sqlglot)

### Single PDF report

1. RECONNAISSANCE.md content (manual Day-One analysis for chosen target).  
2. Architecture diagram of the four-agent pipeline with data flow.  
3. Progress summary: what’s working, what’s in progress.  
4. Early accuracy observations: does the module graph look right? Does the lineage graph match reality?  
5. Known gaps and plan for final submission.

---

## Final — Sunday March 15, 03:00 UTC

### GitHub code (full system)

All interim files plus:

| Path | Description |
|------|-------------|
| src/cli.py | Updated with subcommands: **analyze** (full pipeline) and **query** (Navigator interactive mode). |
| src/orchestrator.py | Full pipeline: Surveyor → Hydrologist → Semanticist → Archivist. |
| src/agents/semanticist.py | LLM purpose statements, doc drift, domain clustering, Day-One answers, ContextWindowBudget. |
| src/agents/archivist.py | CODEBASE.md generation, onboarding brief, trace logging. |
| src/agents/navigator.py | LangGraph agent with 4 tools (find_implementation, trace_lineage, blast_radius, explain_module). |
| Incremental update mode | Re-analyze only changed files via git diff. |
| README.md | How to run against any GitHub URL; both analyze and query modes. |

### Cartography artifacts (2+ target codebases, each with)

- .cartography/CODEBASE.md  
- .cartography/onboarding_brief.md  
- .cartography/module_graph.json  
- .cartography/lineage_graph.json  
- .cartography/cartography_trace.jsonl  

### Single PDF report

1. RECONNAISSANCE.md: manual Day-One analysis vs. system-generated output comparison.  
2. Architecture diagram of the four-agent pipeline (finalized).  
3. Accuracy analysis: which Day-One answers were correct, which were wrong, and why.  
4. Limitations: what the Cartographer fails to understand, what remains opaque.  
5. FDE applicability: one paragraph on how you would use this tool in a real client engagement.  
6. Self-audit results: Cartographer run on your own Week 1 repo; discrepancies explained.

---

## Evaluation rubric

Scores 1–5 per metric. “Master Thinker” (5) is the target.

| Metric | 1 — The Vibe Coder | 3 — Competent Engineer | 5 — Master Thinker |
|--------|---------------------|------------------------|---------------------|
| **Static analysis depth** | Regex file scanning; no AST; “module graph” is a flat list. | tree-sitter AST for Python; module import graph; basic PageRank. | Multi-language AST (Python + SQL + YAML). Circular dependency detection. |
| **Data lineage accuracy** | No lineage graph; cannot answer upstream questions. | Python read/write detected; basic lineage for simple cases. | Full mixed-language lineage: Python + sqlglot SQL + YAML config. |
| **Semantic intelligence** | Docstring regurgitation; no code vs doc distinction; no domain clustering. | LLM purpose statements; some doc drift flags; domain clusters attempted. | Purpose from code (not docstring). Full documentation drift detection. |
| **FDE readiness (onboarding value)** | Output is file names; cannot answer Day-One questions; CODEBASE.md generic. | CODEBASE.md structured and mostly accurate; 3/5 Day-One questions. | All 5 Day-One questions answered correctly with evidence. |
| **Engineering quality** | Single script; no Pydantic; hardcoded paths; crashes on real codebases. | Modular; Pydantic models; basic error handling. | Production-grade: graceful degradation (log + skip) on unparseable files. |

---

## References

- **Overview:** [specs/overview.md](../specs/overview.md).  
- **Pipeline and CLI:** [specs/pipeline-and-cli.md](../specs/pipeline-and-cli.md).  
- **Challenge spec:** [cartographer_challenge_spec.md](cartographer_challenge_spec.md).
