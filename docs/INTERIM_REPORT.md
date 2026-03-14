# Brownfield Cartographer — Interim Submission Report

**Date:** March 12, 2025  

This report contains the five required sections: (1) Reconnaissance / Manual Day-One Analysis, (2) Architecture Diagram of the Four-Agent Pipeline, (3) Progress Summary, (4) Early Accuracy Observations, and (5) Completion Plan for Final Submission.

---

## 1. Reconnaissance: Manual Day-One Analysis

### Target codebase

**Chosen target:** **Meltano** (https://github.com/meltano/meltano).

**Qualification:** Meltano meets the stated requirements for a qualifying target:

- **50+ files:** The repository contains hundreds of source files across `src/`, tests, and config.
- **Multiple languages including SQL and Python:** Core is Python (`src/meltano/`); YAML for config and CI; SQL appears in data-warehouse and dbt-related contexts; JavaScript/TypeScript in docs and tooling.
- **Real production system:** Meltano is a production dataops orchestration platform (ELT, Singer taps/targets, dbt integration). It is widely used and actively maintained.

Manual exploration was performed by reading the repository structure, key modules, and documentation to answer the Five FDE Day-One Questions below. All answers reference specific files, directories, or structural patterns discovered during that exploration.

---

### (1) What is the primary data ingestion path?

Meltano’s primary ingestion path is based on the **Singer Spec**. It follows an **ELT (Extract-Load-Transform)** pattern.

- **The path:** Data is pulled from a **Tap** (extractor), streamed as JSON-formatted messages (RECORD, STATE, SCHEMA) via `stdout`, and piped into a **Target** (loader) via `stdin`.
- **Core logic:** This is managed by the **`ELTService`** and **`Runner`** classes in the Python source. Meltano orchestrates configuration, state, and handoff between these two subprocesses.
- **Structural evidence:** The core behavior lives under `src/meltano/core/`; the Singer tap interface is central in modules such as `src/meltano/core/plugin/singer/tap.py`.

---

### (2) What are the 3–5 most critical output datasets/endpoints?

Because Meltano is a platform rather than a single pipeline, its “outputs” are the systems it manages:

1. **System database (SQLite/PostgreSQL):** Job history, state, and configuration. Loss here removes Meltano’s “memory” of what has been synced.
2. **`meltano.yml` project file:** Primary user-facing output; defines the entire project as code.
3. **Data warehouse (Target):** Final destination (e.g. Snowflake, BigQuery, Postgres) where loaders push data.
4. **Transformation layer (dbt):** Meltano generates dbt-compatible models and manifest files so data is usable after loading.
5. **State artifacts:** Incremental replication depends on JSON state messages to avoid re-fetching old data.

These are the critical dependencies for any Meltano project to function.

---

### (3) What is the blast radius if the most critical module fails?

The most critical conceptual module is **Meltano Core / orchestration engine**.

- **Blast radius:** **Total pipeline paralysis.** If the core fails, no taps run, no targets receive data, and scheduled jobs (e.g. via Airflow or Cron) error. Because Meltano manages **state**, a core failure can cause data duplication or gaps (lost sync cursor). It does not typically corrupt source data, as Meltano uses read-only access to sources.
- **Structural evidence:** Core runner and state logic are concentrated in `src/meltano/core/`; state persistence is handled in modules such as `src/meltano/core/state_store/filesystem.py`. A single tap failure has limited radius; a core/state-store failure stops the entire dataops lifecycle.

---

### (4) Where is the business logic concentrated vs. distributed?

- **Concentrated (Meltano Core):** Environment management, configuration layering, and plugin lifecycle are concentrated in the core Python library. This is where “how” the pipeline runs is decided.
- **Distributed (plugins / dbt):** The “what” (actual data logic) is distributed. Mapping/filtering often lives in taps or Meltano “stream maps.” Heavy transformation is delegated to **dbt** models in the warehouse, not in Meltano’s process.
- Meltano is intentionally “logic-light” on data itself and delegates data logic to plugins.

---

### (5) What has changed most frequently in the last 90 days (git velocity)?

Summary of frequently changed areas:

- **Dependency & environment (high velocity):** `uv.lock`, `pyproject.toml` — frequent dependency and tooling updates.
- **CI/CD (high velocity):** `.github/workflows/test.yml`, `benchmark.yml`, `version_bump.yml` — test and release automation.
- **Core logic (moderate):** `src/meltano/core/plugin/singer/tap.py` (Singer extractors), `src/meltano/core/state_store/filesystem.py` (sync state).
- **Docs & tooling (moderate):** `docs/package.json`, `.pre-commit-config.yaml`.

---

### Difficulty analysis: What was hardest to figure out manually? Where did you get lost?

The hardest part was **Question 4 (business logic distribution)**. Meltano is an orchestrator, not a data processor. In a typical app you look for the “engine” that does the work; here the “engine” is a thin management layer that delegates to many external plugins. Tracing where data logic actually lives is easy to get wrong: the repo emphasizes environment and state management, while real transformation logic lives outside the codebase in dbt and taps.

**Blast radius (Question 3)** was also deceptive because impact is binary: a single tap failure is localized, but a **State Store** or **Core Runner** failure leads to full system failure and risk of duplication or lost sync progress. The high velocity in infrastructure (e.g. `uv.lock`, workflows) underlines that the architecture prioritizes **reliability and portability** of the “manager” layer as external tools change.

---

## 2. Architecture Diagram: Four-Agent Pipeline

The Cartographer is designed as a four-agent pipeline with a central knowledge graph. The diagram below shows all four agents, the shared data store, data flow, and system inputs/outputs.

```mermaid
flowchart LR
    subgraph inputs [System inputs]
        REPO[Target codebase\n(local path or GitHub URL)]
    end

    subgraph pipeline [Four-agent pipeline]
        S[Surveyor\nStatic structure\nModule graph, PageRank\nGit velocity, dead code]
        H[Hydrologist\nData lineage\nSQL + DAG config\nblast_radius, sources/sinks]
        SEM[Semanticist\nLLM purpose\nDoc drift, domains\nDay-One answers]
        A[Archivist\nCODEBASE.md\nOnboarding brief\nTrace, incremental]
    end

    subgraph store [Central data store]
        KG[(Knowledge graph\nModule graph\nLineage graph\nSemantic index)]
    end

    subgraph outputs [System outputs]
        MG[module_graph.json]
        LG[lineage_graph.json]
        CB[CODEBASE.md]
        OB[onboarding_brief.md]
        TR[cartography_trace.jsonl]
    end

    REPO --> S
    S --> KG
    KG --> H
    H --> KG
    KG --> SEM
    SEM --> KG
    KG --> A
    A --> MG
    A --> LG
    A --> CB
    A --> OB
    A --> TR
```

**Diagram summary:**

- **Input:** Target codebase (local directory or GitHub URL).
- **Four agents:** **Surveyor** (static analysis, module graph, PageRank, git velocity, dead-code candidates) → **Hydrologist** (data lineage from SQL and DAG config; blast_radius, find_sources, find_sinks) → **Semanticist** (LLM purpose statements, doc drift, domain clustering, Day-One answers) → **Archivist** (artifact generation and trace).
- **Central store:** Knowledge graph holding module graph, lineage graph, and (when implemented) semantic index. All agents read from and write to this store.
- **Outputs:** `module_graph.json`, `lineage_graph.json`, `CODEBASE.md`, `onboarding_brief.md`, `cartography_trace.jsonl` (and optional semantic index).

**Interim state:** Surveyor and Hydrologist are implemented and wired; they populate the knowledge graph and produce `module_graph.json` and `lineage_graph.json`. Semanticist and Archivist are not yet implemented; the diagram represents the target final architecture.

---

## 3. Progress Summary: Component Status

Status is given at the level of agents, analyzers, and specific capabilities. Claims are concrete and falsifiable.

### Working (implemented and used in the interim pipeline)

| Component | Specific capability | Evidence |
|-----------|--------------------|----------|
| **Surveyor** | Builds module import graph (NetworkX DiGraph) from tree-sitter import extraction | `src/agents/surveyor.py`: `run_surveyor()` discovers files, calls `analyze_module()`, adds nodes/edges to `kg.module_graph`. |
| **Surveyor** | PageRank on module subgraph | `nx.pagerank(subg, weight="weight")` in `run_surveyor()`; result stored in node attribute `pagerank`. |
| **Surveyor** | Git velocity (change frequency per file) | `extract_git_velocity(repo_root, days)` using `git log --follow --name-only --since=...`; attached to module nodes as `change_velocity_30d`. |
| **Surveyor** | Dead-code candidates | Heuristic in `run_surveyor()`: modules never imported and with out_degree 0 get `is_dead_code_candidate=True`. |
| **Hydrologist** | Merge SQL lineage + DAG config into one lineage graph | `run_hydrologist()` uses `extract_lineage_from_file()` (sql_lineage) and `analyze_dag_config()` (dag_config_parser); all results merged into `kg.lineage_graph`. |
| **Hydrologist** | blast_radius, find_sources, find_sinks | Implemented in `src/agents/hydrologist.py`; operate on `kg.lineage_graph`. |
| **tree_sitter_analyzer** | Multi-language routing by extension; Python imports/functions/classes from AST | `get_language_for_path()`; `extract_python_imports()`, `extract_python_functions_and_classes()`; no regex for structure. |
| **tree_sitter_analyzer** | JS/TS import extraction from AST | `extract_js_imports()` for ES6 import and `require()`; used in `analyze_module()` for `.js`/`.ts`/`.tsx`. |
| **sql_lineage** | sqlglot parse; table deps from SELECT/FROM/JOIN/WITH(CTE); INSERT/MERGE/CREATE/UPDATE | `extract_table_dependencies()`; `_tables_from_expression()` (exp.Table, exp.CTE, exp.With); `_write_target()`; DIALECT_MAP (postgres, bigquery, snowflake, duckdb). |
| **dag_config_parser** | dbt schema.yml and Airflow DAG Python topology | `parse_dbt_schema_yml()`, Airflow DAG parsing; `analyze_dag_config()` dispatches by extension. |
| **knowledge_graph** | NetworkX wrapper; add typed nodes/edges; serialize/deserialize to JSON (including from file) | `src/graph/knowledge_graph.py`: add_* methods, serialize_*, write_*_json, load_*_from_dict, load_*_json(path). |
| **Models** | Pydantic node and edge types | `src/models/nodes.py` (ModuleNode, DatasetNode, FunctionNode, TransformationNode); `src/models/edges.py` (EdgeType, EdgePayload). |
| **Orchestrator** | Sequence Surveyor → Hydrologist; write artifacts | `run_analysis()` in `src/orchestrator.py` calls `run_surveyor()` then `run_hydrologist()`, then `write_module_graph_json()` and `write_lineage_graph_json()`. |
| **CLI** | `analyze` subcommand; repo path (local or GitHub URL); output to .cartography/ or -o | `src/cli.py`: `analyze` parser with `target`, `-o`, `--days`, `--sql-dialect`; calls `resolve_repo_path()` and `run_analysis()`. |

### In progress

None for the interim deliverable. All interim-scope components above are implemented and exercised by the current pipeline.

### Not started (planned for final submission)

| Component | Planned capability |
|-----------|--------------------|
| **Semanticist** | ContextWindowBudget; purpose statements from code (not docstring); doc drift; domain clustering; Day-One answers synthesis. |
| **Archivist** | CODEBASE.md; onboarding_brief.md; cartography_trace.jsonl; incremental update (git diff, re-analyze changed files). |
| **Navigator** | LangGraph agent with find_implementation, trace_lineage, blast_radius, explain_module; evidence citations. |
| **Orchestrator (final)** | Full pipeline Surveyor → Hydrologist → Semanticist → Archivist; all .cartography/ artifacts. |
| **CLI (final)** | `query` subcommand for Navigator interactive mode. |

---

## 4. Early Accuracy Observations

Generated outputs were compared to the **actual structure of a target codebase**. For the interim run, the target used was **this Cartographer repository itself** (self-analysis). The following compares the produced `module_graph.json` and `lineage_graph.json` to the repo.

### Target and method

- **Target:** Cartographer repo (local path). Contains Python in `src/` and `tests/`, YAML in tests and config, no production `.sql` files (only test/fixture usage).
- **Run:** `uv run cartographer analyze .` (output under `.cartography/`).

### Correct detections

- **Module graph**
  - **Modules:** All relevant Python modules appear as nodes with `path` and `id` (e.g. `src/cli.py`, `src/orchestrator.py`, `src/agents/surveyor.py`, `src/agents/hydrologist.py`, `src/analyzers/tree_sitter_analyzer.py`, `src/analyzers/sql_lineage.py`, `src/analyzers/dag_config_parser.py`, `src/graph/knowledge_graph.py`).
  - **Imports:** IMPORTS edges exist from these modules to both stdlib (e.g. `argparse`, `logging`, `pathlib`) and internal modules (e.g. `src.orchestrator`, `src.graph.knowledge_graph`). This matches the real import structure.
  - **Functions/classes:** Public functions and classes appear as nodes with `qualified_name` and `parent_module` (e.g. `src/cli.py::main`, `src/orchestrator.py::run_analysis`).
  - **PageRank:** Module nodes carry a `pagerank` attribute; values are non-uniform and consistent with a small graph.
- **Lineage graph**
  - **DAG config:** The only SQL in the repo is in tests; the only lineage-relevant content comes from **dag_config_parser** on test YAML and DAG Python. The graph correctly contains CONFIGURES edges from `src/analyzers/dag_config_parser.py` and test files (e.g. `tests/unit/analyzers/test_dag_config_parser.py`) to task/table-like nodes (e.g. `task_a`, `task_b`, `t1`, `t2`, `operator`) derived from those test fixtures. So the pipeline correctly identified config-driven topology where present.

### Inaccuracies and missed elements

- **Module graph**
  - **Import targets:** Import edges point to **module names** (e.g. `argparse`, `src.orchestrator`) rather than resolved file paths. The graph therefore mixes file-path nodes (e.g. `src/cli.py`) with non-path identifiers. This is by design in the current implementation but limits “which file imports which file” queries without a name→path mapping.
  - **Change velocity:** Many module nodes have `change_velocity_30d: null`. This can occur if the run environment did not have git history, or if there were no commits in the last 30 days for those files. So git velocity is correct when git is available and active; otherwise it is absent as expected.
- **Lineage graph**
  - **No SQL lineage in this repo:** There are no production `.sql` files, so sqlglot-based lineage correctly contributes nothing. The only lineage comes from DAG/config parsing of test fixtures, which matches the actual content of the repo.
  - **Python data-flow not wired:** The Hydrologist design includes Python data-flow (e.g. pandas read/write, SQLAlchemy) in the spec; the current implementation merges only SQL lineage and DAG config. So for this repo, any Python-based read/write is not yet reflected in the lineage graph (and this repo has little such code in `src/`).

### Summary

For the Cartographer self-analysis run, the **module graph** correctly reflects Python modules, imports, and public API surface, with PageRank and optional git velocity. The **lineage graph** correctly reflects the only available lineage sources (DAG config from test YAML/Python). The main limitations observed are: (1) import targets as module names rather than paths, and (2) lineage currently limited to SQL + DAG config (no Python data-flow in the graph yet). These are implementation choices and spec gaps rather than incorrect parsing of what was analyzed.

---

## 5. Completion Plan for Final Submission

Concrete, prioritized, and sequenced plan to complete the system by the final deadline (Sunday March 15, 03:00 UTC), with dependencies and risks called out.

### Work items (specific and named)

1. **Semanticist agent** (`src/agents/semanticist.py`)
   - ContextWindowBudget (token estimation, tiered model use).
   - `generate_purpose_statement(module_node)` from code (not docstring); flag documentation drift.
   - `cluster_into_domains()` (e.g. embed purpose statements, k-means, label clusters).
   - `answer_day_one_questions()`: synthesize Surveyor + Hydrologist output; produce five answers with evidence citations.

2. **Archivist agent** (`src/agents/archivist.py`)
   - `generate_CODEBASE_md()`: Architecture Overview, Critical Path, Data Sources & Sinks, Known Debt, Recent Change Velocity, Module Purpose Index.
   - Generate `onboarding_brief.md` from Day-One answers; write `lineage_graph.json`; maintain `cartography_trace.jsonl`; persist semantic index if used.
   - Incremental update: git diff since last run; re-analyze only changed files; merge into graph.

3. **Navigator agent** (`src/agents/navigator.py`)
   - LangGraph agent with four tools: find_implementation, trace_lineage, blast_radius, explain_module.
   - Every answer cites evidence (file, line, method: static vs LLM).

4. **Orchestrator and CLI (final)**
   - Orchestrator: full pipeline Surveyor → Hydrologist → Semanticist → Archivist; produce all .cartography/ artifacts.
   - CLI: add `query` subcommand to load graph/artifacts and start Navigator interactive mode.
   - README: document both `analyze` and `query`, and running against any GitHub URL.

5. **Artifacts and report**
   - Run on **2+ target codebases**; each with CODEBASE.md, onboarding_brief.md, module_graph.json, lineage_graph.json, cartography_trace.jsonl.
   - Final PDF: RECON vs system output; pipeline diagram; accuracy analysis; limitations; FDE applicability; self-audit (e.g. Week 1 repo).

6. **Demo video** (if required)
   - Cold start, lineage query, blast radius; optionally Day-One verification, context injection, self-audit (per spec).

### Sequencing and dependencies

- **Semanticist before Archivist:** Archivist needs Day-One answers and purpose-related content for CODEBASE.md and onboarding_brief. Semanticist must be able to run after Surveyor + Hydrologist and write into the knowledge graph (or a shared structure Archivist can read).
- **Archivist before Navigator:** Navigator’s tools (e.g. trace_lineage, blast_radius) rely on the graph and artifacts; Archivist produces the full artifact set. So: Surveyor → Hydrologist → Semanticist → Archivist; then Navigator can run in `query` mode.
- **Incremental mode:** Can be developed in parallel with Archivist (same agent owns “re-analyze changed files” and merge). It is not a blocker for the rest of the pipeline but improves usability for large repos.

### Technical risks and uncertainties

- **LLM cost and latency (Semanticist):** Bulk purpose statements and Day-One synthesis may require careful model choice (e.g. cheap model for bulk, expensive for synthesis) and batching. Context window limits may require chunking or summarization for very large codebases.
- **Scope in three days:** Four agents (two net-new), full pipeline, CLI `query`, 2+ codebases, and final report is tight. Prioritization: get Semanticist + Archivist + full pipeline + `query` working on one codebase first; then second codebase and incremental if time allows.
- **Navigator tool implementation:** trace_lineage and blast_radius can call existing Hydrologist/Surveyor logic; find_implementation and explain_module may need clear contracts with the graph and (optionally) semantic index. Defining these contracts early will reduce integration risk.

### Prioritization for the remaining time

| Priority | Item | Rationale |
|----------|------|-----------|
| 1 | Semanticist (minimal viable: purpose statements + Day-One answers) | Unblocks Archivist and delivers FDE-relevant output. |
| 2 | Archivist (CODEBASE.md, onboarding_brief.md, trace) | Core deliverables for final rubric and report. |
| 3 | Full pipeline + CLI `query` + Navigator (four tools) | Completes the system and demo flow. |
| 4 | Second codebase + full artifact set | Meets “2+ codebases” and strengthens accuracy discussion. |
| 5 | Incremental mode | Improves usability; can be trimmed if time is short. |

---

**End of interim report.** This document can be exported to PDF for submission.
