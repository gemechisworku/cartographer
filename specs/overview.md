# Cartographer Overview

## Goals and business problem

The Brownfield Cartographer is a **Codebase Intelligence System** for rapid FDE (Forward-Deployed Engineering) onboarding in production data-engineering environments.

**The Day-One problem:** An FDE is embedded at a client with ~72 hours to become useful. The codebase is large and polyglot (e.g. Python, Java, Spark SQL); original engineers are unavailable; documentation is stale; pipelines run but their design is unclear. The Cartographer’s job is to produce a **living, queryable map** of the system so the FDE can build a working mental model quickly.

**Cognitive bottlenecks addressed:**

- **Navigation blindness** — Which files matter? Where is the critical path? What is dead code?
- **Contextual amnesia** — No persistent architectural model for the LLM; context must be re-explained constantly.
- **Dependency opacity** — What produces/consumes this dataset? What breaks if this table changes? (Mixed SQL/Python/YAML.)
- **Silent debt** — Code and documentation drift apart; the system must surface discrepancies.

**Philosophy:** The FDE does not memorize codebases. The FDE builds instruments that make codebases legible. The Cartographer ingests a GitHub repo or local path and produces a knowledge graph of architecture, data flows, and semantic structure—scoped to data science and data engineering (pipelines, DAGs, lineage, polyglot stacks).

---

## The Cartographer’s outputs

| Output | Description |
|--------|-------------|
| **System map** | Architectural overview: modules, entry points, critical path, dead-code detection. |
| **Data lineage graph** | DAG of data flow from sources to outputs across Python, SQL, and config. |
| **Semantic index** | Vector-indexed, searchable purpose-descriptions grounded in code (not docstrings). |
| **Onboarding brief** | Auto-generated Day-One brief answering the five FDE questions with evidence. |
| **Living context (CODEBASE.md)** | Persistent, injectable context file for AI coding agents (architectural awareness). |

---

## Four agents (one sentence each)

1. **Surveyor** — Performs static structure analysis (tree-sitter AST, import graph, git velocity, dead-code candidates) and builds the module graph.
2. **Hydrologist** — Builds the data lineage DAG from Python/SQL/YAML/notebooks and provides blast radius, sources, and sinks.
3. **Semanticist** — Uses LLMs to generate purpose statements from code (not docstrings), detect doc drift, cluster domains, and answer the Five Day-One questions.
4. **Archivist** — Produces and maintains living artifacts: CODEBASE.md, onboarding brief, lineage JSON, semantic index, and cartography trace; supports incremental updates.

**Query interface:** The **Navigator** is a LangGraph agent with four tools (find_implementation, trace_lineage, blast_radius, explain_module) that query the knowledge graph and cite evidence.

---

## The Five FDE Day-One questions (verbatim)

These must be answered in the first 72 hours and are the basis of the Onboarding Brief:

1. What is the primary data ingestion path?
2. What are the 3–5 most critical output datasets/endpoints?
3. What is the blast radius if the most critical module fails?
4. Where is the business logic concentrated vs. distributed?
5. What has changed most frequently in the last 90 days (git velocity map)?

---

## High-level data flow

```
Repository (GitHub URL or local path)
         │
         ▼
   ┌─────────────┐
   │  Surveyor   │  →  Module graph, git velocity, dead-code candidates
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │ Hydrologist │  →  Data lineage DAG, sources/sinks, blast radius
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │ Semanticist │  →  Purpose statements, domain clusters, Day-One answers
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │  Archivist  │  →  CODEBASE.md, onboarding_brief, lineage JSON, semantic index, trace
   └──────┬──────┘
          │
          ▼
   Knowledge graph (NetworkX + vector store) + .cartography/ artifacts
          │
          ▼
   Navigator (query interface: find_implementation, trace_lineage, blast_radius, explain_module)
```

All agents read from and write into the shared **knowledge graph** (see [data-model.md](data-model.md)). The Archivist serializes subsets to disk (e.g. `lineage_graph.json`, `semantic_index/`). The Navigator queries the in-memory graph and artifacts to answer user questions with evidence citations.
