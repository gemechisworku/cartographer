# Cartographer Implementation Plan

This plan breaks down implementation into **interim** (by **Thursday March 12, 03:00 UTC**) and **final** (by **Sunday March 15, 03:00 UTC**) phases, ordered by dependency. Each task maps to deliverables in [deliverables-and-rubric.md](deliverables-and-rubric.md). Specs live in [specs/](../specs/); use [specs/README.md](../specs/README.md) as the index.

---

## Overview

| Phase | Goal | Key deliverables |
|-------|------|-------------------|
| **Interim** | Surveyor + Hydrologist running; CLI `analyze`; at least module_graph + lineage_graph for 1 codebase. | Working static + lineage analysis, 1 target codebase, interim PDF. |
| **Final** | Full pipeline (Surveyor → Hydrologist → Semanticist → Archivist); Navigator `query`; incremental mode; 2+ codebases; full artifacts. | CODEBASE.md, onboarding_brief, trace, semantic index; final PDF; demo video. |

Work in each phase is ordered so that dependencies (e.g. models before agents) are built first.

---

## Phase 1: Interim (by Mar 12, 03:00 UTC)

### 1.1 Project setup

| # | Task | Output | Status |
|---|------|--------|--------|
| 1.1.1 | Create `pyproject.toml` with uv, project name, and dependencies (tree-sitter, tree-sitter-* grammars, sqlglot, networkx, pydantic, etc.). | pyproject.toml | ✅ |
| 1.1.2 | Lock deps with `uv lock`. | uv.lock (or equivalent) | ✅ |
| 1.1.3 | Create `src/` layout: `src/models/`, `src/analyzers/`, `src/agents/`, `src/graph/`. Add `src/__init__.py` etc. as needed. | Directory structure | ✅ |

### 1.2 Data model (knowledge graph schema)

| # | Task | Output | Status |
|---|------|--------|--------|
| 1.2.1 | Implement Pydantic models in `src/models/`: **ModuleNode**, **DatasetNode**, **FunctionNode**, **TransformationNode** (see [specs/data-model.md](../specs/data-model.md)). | src/models/*.py | ✅ |
| 1.2.2 | Implement edge types / graph types (IMPORTS, PRODUCES, CONSUMES, CALLS, CONFIGURES) as needed for serialization and graph APIs. | src/models/*.py | ✅ |

### 1.3 Analyzers

| # | Task | Output | Status |
|---|------|--------|--------|
| 1.3.1 | **tree_sitter_analyzer:** LanguageRouter (file extension → grammar); grammars for Python, SQL, YAML, JS/TS ([specs/analyzers.md](../specs/analyzers.md)). | src/analyzers/tree_sitter_analyzer.py | ✅ |
| 1.3.2 | **tree_sitter_analyzer:** AST parsing — extract imports, public functions, classes; optional complexity. Output shapes that feed ModuleNode / FunctionNode / IMPORTS. | Same file | ✅ |
| 1.3.3 | **sql_lineage:** sqlglot-based extraction of table dependencies from .sql / dbt; dialects Postgres, BigQuery, Snowflake, DuckDB. | src/analyzers/sql_lineage.py | ✅ |
| 1.3.4 | **dag_config_parser:** Parse Airflow DAG (Python) and/or dbt schema.yml for pipeline topology and config→pipeline. | src/analyzers/dag_config_parser.py | ✅ |

### 1.4 Knowledge graph layer

| # | Task | Output | Status |
|---|------|--------|--------|
| 1.4.1 | **knowledge_graph.py:** NetworkX wrapper — add module nodes/edges, lineage nodes/edges; serialize to JSON (module_graph, lineage_graph). | src/graph/knowledge_graph.py | ✅ |

### 1.5 Surveyor agent

| # | Task | Output | Status |
|---|------|--------|--------|
| 1.5.1 | **surveyor.py:** `analyze_module(path)` using tree_sitter_analyzer → ModuleNode, FunctionNode, IMPORTS ([specs/agents/surveyor.md](../specs/agents/surveyor.md)). | src/agents/surveyor.py | ✅ |
| 1.5.2 | **surveyor.py:** `extract_git_velocity(path, days=30)` — git log --follow, change frequency per file. | Same | ✅ |
| 1.5.3 | **surveyor.py:** Build module import graph (NetworkX DiGraph); PageRank; strongly connected components (circular deps). | Same | ✅ |
| 1.5.4 | **surveyor.py:** Dead-code candidates (exported symbols with no references). | Same | ✅ |

### 1.6 Hydrologist agent

| # | Task | Output | Status |
|---|------|--------|--------|
| 1.6.1 | **hydrologist.py:** Python data-flow (tree_sitter): pandas read/write, SQLAlchemy, PySpark; extract dataset names; log dynamic refs ([specs/agents/hydrologist.md](../specs/agents/hydrologist.md)). | src/agents/hydrologist.py | ✅ |
| 1.6.2 | **hydrologist.py:** Merge sql_lineage + dag_config_parser into DataLineageGraph (DatasetNode, TransformationNode, PRODUCES, CONSUMES). | Same | ✅ |
| 1.6.3 | **hydrologist.py:** `blast_radius(node)`, `find_sources()`, `find_sinks()`. | Same | ✅ |

### 1.7 Orchestrator and CLI (interim scope)

| # | Task | Output | Status |
|---|------|--------|--------|
| 1.7.1 | **orchestrator.py:** Wire Surveyor → Hydrologist; accept repo path; build and populate knowledge graph; write .cartography/module_graph.json and .cartography/lineage_graph.json. | src/orchestrator.py | ✅ |
| 1.7.2 | **cli.py:** Entry point; `analyze` subcommand (repo path: local or GitHub URL); call orchestrator; create .cartography/ under repo. | src/cli.py | ✅ |

### 1.8 Documentation and artifacts (interim)

| # | Task | Output | Status |
|---|------|--------|--------|
| 1.8.1 | **README.md:** Install (uv), run `analyze` against local path or GitHub URL; list required artifacts. | README.md | ✅ |
| 1.8.2 | Run analysis on **at least 1 target codebase** (e.g. dbt jaffle_shop or Airflow examples); produce .cartography/module_graph.json and .cartography/lineage_graph.json (lineage partial OK; min SQL via sqlglot). | Cartography artifacts | ✅ |

### 1.9 Interim PDF report

| # | Task | Output | Status |
|---|------|--------|--------|
| 1.9.1 | Write single PDF containing: (1) RECONNAISSANCE.md content, (2) architecture diagram of four-agent pipeline + data flow, (3) progress summary, (4) early accuracy observations, (5) known gaps and plan for final. | PDF report | ⬜ |

---

## Phase 2: Final (by Mar 15, 03:00 UTC)

### 2.1 Semanticist agent

| # | Task | Output | Status |
|---|------|--------|--------|
| 2.1.1 | **semanticist.py:** ContextWindowBudget — token estimation, cumulative spend, tiered model (e.g. cheap for bulk, expensive for synthesis) ([specs/agents/semanticist.md](../specs/agents/semanticist.md)). | src/agents/semanticist.py | ✅ |
| 2.1.2 | **semanticist.py:** `generate_purpose_statement(module_node)` from code (not docstring); flag documentation drift. | Same | ✅ |
| 2.1.3 | **semanticist.py:** `cluster_into_domains()` — embed purpose statements, k-means (k=5–8), label clusters. | Same | ✅ |
| 2.1.4 | **semanticist.py:** `answer_day_one_questions()` — synthesis prompt with Surveyor + Hydrologist output; five answers with evidence citations. | Same | ✅ |

### 2.2 Archivist agent

| # | Task | Output | Status |
|---|------|--------|--------|
| 2.2.1 | **archivist.py:** `generate_CODEBASE_md()` — Architecture Overview, Critical Path, Data Sources & Sinks, Known Debt, Recent Change Velocity, Module Purpose Index ([specs/agents/archivist.md](../specs/agents/archivist.md)). | src/agents/archivist.py | ✅ |
| 2.2.2 | **archivist.py:** onboarding_brief.md from Day-One answers; lineage_graph.json; semantic_index/ (vector store persistence); cartography_trace.jsonl. | Same | ✅ |
| 2.2.3 | **archivist.py:** Incremental update mode — git diff since last run; re-analyze only changed files; merge into graph. | Same | 🟦 |

### 2.3 Navigator agent

| # | Task | Output | Status |
|---|------|--------|--------|
| 2.3.1 | **navigator.py:** LangGraph agent with four tools: find_implementation, trace_lineage, blast_radius, explain_module ([specs/agents/navigator.md](../specs/agents/navigator.md)). | src/agents/navigator.py | ✅ |
| 2.3.2 | **navigator.py:** Every answer cites evidence (file, line, analysis method: static vs LLM). | Same | ✅ |

### 2.4 Orchestrator and CLI (final scope)

| # | Task | Output | Status |
|---|------|--------|--------|
| 2.4.1 | **orchestrator.py:** Full pipeline Surveyor → Hydrologist → Semanticist → Archivist; produce all .cartography/ artifacts. | src/orchestrator.py | ✅ |
| 2.4.2 | **cli.py:** Subcommand `query` — load graph/artifacts, start Navigator interactive mode. | src/cli.py | ✅ |
| 2.4.3 | **README.md:** Document running against any GitHub URL; both `analyze` and `query` modes. | README.md | ✅ |

### 2.5 Cartography artifacts and report (final)

| # | Task | Output | Status |
|---|------|--------|--------|
| 2.5.1 | Run on **2+ target codebases**; each with CODEBASE.md, onboarding_brief.md, module_graph.json, lineage_graph.json, cartography_trace.jsonl. | Cartography artifacts | ⬜ |
| 2.5.2 | Final PDF: (1) RECON vs system output, (2) pipeline diagram, (3) accuracy analysis, (4) limitations, (5) FDE applicability, (6) self-audit (Week 1 repo). | PDF report | ⬜ |

### 2.6 Demo video

| # | Task | Output | Status |
|---|------|--------|--------|
| 2.6.1 | Record video (max 6 min): Cold start, lineage query, blast radius (required); Day-One brief verification, living context injection, self-audit (mastery). See [specs/targets-and-validation.md](../specs/targets-and-validation.md). | Video | ⬜ |

---

## Dependency summary

```
Phase 1 (Interim):
  pyproject + layout → models → analyzers → knowledge_graph
       → surveyor → hydrologist → orchestrator (Surveyor+Hydrologist only) → cli analyze
       → 1 target codebase + README + interim PDF

Phase 2 (Final):
  semanticist (needs surveyor+hydrologist output) → archivist (needs all agents)
       → navigator (needs graph + lineage) → orchestrator (full pipeline) → cli query
       → incremental mode → 2+ codebases + final PDF + video
```

---

## Quick reference

| Doc | Purpose |
|-----|---------|
| [deliverables-and-rubric.md](deliverables-and-rubric.md) | Interim/final file lists, dates, rubric. |
| [specs/README.md](../specs/README.md) | Spec index and “read when…” |
| [specs_creation_plan.md](specs_creation_plan.md) | Spec creation status. |
| [cartographer_challenge_spec.md](cartographer_challenge_spec.md) | Full challenge requirements. |

**Status legend:** ⬜ Not started | 🟦 In progress | ✅ Done — update this plan as you complete tasks.
