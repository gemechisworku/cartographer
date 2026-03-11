# Pipeline and CLI

This spec defines the **orchestrator order**, **CLI entry point and subcommands**, and the **.cartography/** output layout. The orchestrator wires the four analysis agents in sequence and (optionally) the Navigator for query mode.

**Depends on:** [data-model.md](data-model.md), all agents ([surveyor](agents/surveyor.md), [hydrologist](agents/hydrologist.md), [semanticist](agents/semanticist.md), [archivist](agents/archivist.md)).

---

## Entry point

- **src/cli.py** — Single entry point. Accepts repo path (local directory or GitHub URL). Dispatches to subcommands (e.g. `analyze`, `query`). Uses **uv** and **pyproject.toml** for dependencies; see [docs/deliverables-and-rubric.md](../docs/deliverables-and-rubric.md) for required structure.

---

## Orchestrator order

The analysis pipeline runs in this order. Each agent reads from and writes to the shared **knowledge graph** (NetworkX + vector store). The orchestrator is responsible for passing the graph and any file lists between agents.

1. **Surveyor** — Builds module graph, ModuleNode, FunctionNode, IMPORTS; git velocity; dead-code candidates. Writes module graph (in-memory; serialization may be deferred to Archivist).
2. **Hydrologist** — Builds DataLineageGraph (DatasetNode, TransformationNode, PRODUCES, CONSUMES, CONFIGURES); blast_radius, find_sources, find_sinks. Consumes file list / repo layout (from Surveyor or orchestrator).
3. **Semanticist** — Fills purpose_statement, domain_cluster; doc drift; Day-One answers; feeds vector store. Consumes Surveyor + Hydrologist output.
4. **Archivist** — Writes all artifacts to .cartography/ (CODEBASE.md, onboarding_brief.md, lineage_graph.json, semantic_index/, cartography_trace.jsonl). Optionally runs incremental update (only changed files).

**Implementation:** `src/orchestrator.py` — Wires Surveyor → Hydrologist → Semanticist → Archivist in sequence; loads/saves knowledge graph as needed.

---

## CLI subcommands

| Subcommand | Purpose | Behavior |
|------------|---------|----------|
| **analyze** | Full (or incremental) analysis | Takes repo path (local or GitHub URL). Clones or uses local path. Runs Surveyor → Hydrologist → Semanticist → Archivist. Writes to `.cartography/` under repo root (or configured output path). |
| **query** | Navigator interactive mode | Takes repo path (and optionally path to existing .cartography/). Loads knowledge graph and artifacts. Starts LangGraph Navigator agent with four tools; user can ask questions (find_implementation, trace_lineage, blast_radius, explain_module). |

**Interim deliverable (Mar 12):** At least `analyze` is required; orchestrator may run only Surveyor + Hydrologist and serialize module_graph.json + lineage_graph.json.  
**Final deliverable (Mar 15):** Both `analyze` (full pipeline) and `query` (Navigator) required. README must document how to run against any GitHub URL for both modes.

---

## .cartography/ layout

All artifacts are written under a single output directory, by default **.cartography/** at the repo root (or the path being analyzed). Per-target codebase: one .cartography/ per repo (e.g. one per clone).

| Path | Producer | Description |
|------|----------|-------------|
| `.cartography/module_graph.json` | Surveyor / Archivist | Serialized module import graph (NetworkX JSON or equivalent). |
| `.cartography/lineage_graph.json` | Hydrologist / Archivist | Serialized DataLineageGraph for downstream tooling. |
| `.cartography/CODEBASE.md` | Archivist | Living context file for AI agent injection. |
| `.cartography/onboarding_brief.md` | Archivist | Day-One Brief (five questions + evidence). |
| `.cartography/semantic_index/` | Archivist | Vector store persistence (purpose statements). |
| `.cartography/cartography_trace.jsonl` | Archivist | Audit log of analysis actions. |

The orchestrator (or Archivist) is responsible for creating the output directory and writing these files. See [archivist.md](agents/archivist.md) for artifact contents.

---

## Knowledge graph lifecycle

- **Build:** Orchestrator instantiates the graph (e.g. via `src/graph/knowledge_graph.py`). Surveyor and Hydrologist add nodes and edges; Semanticist updates node attributes and populates the vector store.
- **Serialize:** Archivist (or orchestrator) writes module_graph.json and lineage_graph.json from the in-memory graph; semantic_index/ from the vector store.
- **Query mode:** For `query` subcommand, load graph and index from .cartography/ (or keep in memory if analyze was run in same process). Navigator uses the graph and vector store to answer user questions.

---

## References

- **Data model:** [data-model.md](data-model.md).
- **Agents:** [surveyor](agents/surveyor.md), [hydrologist](agents/hydrologist.md), [semanticist](agents/semanticist.md), [archivist](agents/archivist.md).
- **Deliverables:** [docs/deliverables-and-rubric.md](../docs/deliverables-and-rubric.md) for required files and dates.
