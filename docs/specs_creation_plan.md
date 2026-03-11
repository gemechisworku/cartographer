# Specs Creation Plan

This document defines the order and status of spec creation for the Brownfield Cartographer. Specs are created in **dependency order**: each spec only depends on specs that appear earlier in the list.

**Rule:** Do not create a spec until all of its dependencies are marked complete.

---

## Dependency order (creation sequence)

| # | Spec | Depends on | Status |
|---|------|------------|--------|
| 1 | [specs/overview.md](../specs/overview.md) | — | ✅ Done |
| 2 | [specs/data-model.md](../specs/data-model.md) | overview | ✅ Done |
| 3 | [specs/analyzers.md](../specs/analyzers.md) | data-model | ✅ Done |
| 4 | [specs/agents/surveyor.md](../specs/agents/surveyor.md) | data-model, analyzers | ✅ Done |
| 5 | [specs/agents/hydrologist.md](../specs/agents/hydrologist.md) | data-model, analyzers | ✅ Done |
| 6 | [specs/agents/semanticist.md](../specs/agents/semanticist.md) | data-model, overview, surveyor, hydrologist | ✅ Done |
| 7 | [specs/agents/navigator.md](../specs/agents/navigator.md) | data-model, hydrologist | ✅ Done |
| 8 | [specs/agents/archivist.md](../specs/agents/archivist.md) | data-model, all other agents | ✅ Done |
| 9 | [specs/pipeline-and-cli.md](../specs/pipeline-and-cli.md) | data-model, all agents | ✅ Done |
| 10 | [specs/targets-and-validation.md](../specs/targets-and-validation.md) | overview, deliverables | ✅ Done |
| 11 | [docs/deliverables-and-rubric.md](deliverables-and-rubric.md) | overview, pipeline (moved to docs/) | ✅ Done |
| 12 | [specs/README.md](../specs/README.md) | all above | ✅ Done |

**Status legend:** ⬜ Not started | 🟦 In progress | ✅ Done

---

## Phase summary

| Phase | Specs | Purpose |
|-------|--------|--------|
| **1 – Foundation** | 1–2 | overview, data-model |
| **2 – Analyzers** | 3 | Analyzer contracts (tree_sitter, sql_lineage, dag_config) |
| **3 – Agents** | 4–8 | Surveyor, Hydrologist, Semanticist, Navigator, Archivist |
| **4 – Pipeline & deliverables** | 9–11 | Orchestration, CLI, targets, rubric |
| **5 – Index** | 12 | specs/README.md |

---

## Per-spec checklist (update as you go)

### 1. specs/overview.md
- [x] File created
- [x] Goals and business problem
- [x] Four agents (one sentence each)
- [x] Five Day-One questions (verbatim)
- [x] High-level data flow (repo → agents → graph → artifacts)
- [x] Status set to ✅ in table above

### 2. specs/data-model.md
- [x] File created
- [x] Node types: ModuleNode, DatasetNode, FunctionNode, TransformationNode (fields)
- [x] Edge types: IMPORTS, PRODUCES, CONSUMES, CALLS, CONFIGURES
- [x] Note: NetworkX + vector store
- [x] Status set to ✅ in table above

### 3. specs/analyzers.md
- [x] File created
- [x] Conventions (input, errors, reference to data-model)
- [x] Section: tree_sitter_analyzer (LanguageRouter, AST, outputs)
- [x] Section: sql_lineage (sqlglot, dialects, table deps)
- [x] Section: dag_config_parser (Airflow/dbt YAML, topology)
- [x] Status set to ✅ in table above

### 4. specs/agents/surveyor.md
- [x] File created
- [x] Inputs/outputs, module graph, PageRank, git velocity, dead code
- [x] References: data-model, analyzers (tree_sitter)
- [x] Status set to ✅ in table above

### 5. specs/agents/hydrologist.md
- [x] File created
- [x] DataLineageGraph, blast_radius, find_sources/find_sinks
- [x] References: data-model, analyzers (all three)
- [x] Status set to ✅ in table above

### 6. specs/agents/semanticist.md
- [x] File created
- [x] Purpose statements, doc drift, domain clustering, Day-One answers, ContextWindowBudget
- [x] References: data-model, overview, surveyor, hydrologist
- [x] Status set to ✅ in table above

### 7. specs/agents/navigator.md
- [x] File created
- [x] Four tools: find_implementation, trace_lineage, blast_radius, explain_module
- [x] Evidence citations (file:line, analysis method)
- [x] References: data-model, hydrologist
- [x] Status set to ✅ in table above

### 8. specs/agents/archivist.md
- [x] File created
- [x] Artifacts: CODEBASE.md, onboarding_brief, lineage_graph.json, semantic_index/, cartography_trace.jsonl
- [x] CODEBASE.md sections, incremental update
- [x] References: data-model, all other agents
- [x] Status set to ✅ in table above

### 9. specs/pipeline-and-cli.md
- [x] File created
- [x] Orchestrator order (Surveyor → Hydrologist → Semanticist → Archivist)
- [x] CLI subcommands (e.g. analyze, query), .cartography/ layout
- [x] References: data-model, all agents
- [x] Status set to ✅ in table above

### 10. specs/targets-and-validation.md
- [x] File created
- [x] Target codebases (dbt, Airflow, etc.), demo protocol
- [x] RECONNAISSANCE.md role (manual baseline, do not edit for now)
- [x] References: overview, deliverables
- [x] Status set to ✅ in table above

### 11. docs/deliverables-and-rubric.md
- [x] File created (moved from specs/ to docs/ — challenge evaluation, not project spec)
- [x] Interim (Mar 12) file list + PDF sections
- [x] Final (Mar 15) file list + PDF sections
- [x] Rubric summary (1–5)
- [x] References: overview, pipeline
- [x] Status set to ✅ in table above

### 12. specs/README.md
- [x] File created
- [x] Purpose of Cartographer
- [x] Table: spec → path → "read when…"
- [x] Pointer to docs/cartographer_challenge_spec.md and docs/deliverables-and-rubric.md
- [x] Status set to ✅ in table above

---

## How to use this plan

1. Create specs in order 1 → 12. If a spec depends on others, ensure those are done first.
2. For each spec: create the file, fill content, tick the per-spec checklist, then set its Status to ✅ in the main table (replace ⬜ with ✅).
3. If a spec is in progress, set Status to 🟦.
4. Keep this file updated so anyone (or an agent) can see what’s done and what’s next.

**Canonical challenge:** [cartographer_challenge_spec.md](cartographer_challenge_spec.md)
