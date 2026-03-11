# Agent: Archivist (Living Context Maintainer)

The Archivist **produces and maintains** the system’s outputs as living artifacts: CODEBASE.md, onboarding brief, lineage graph JSON, semantic index, and cartography trace. It runs after the Surveyor, Hydrologist, and Semanticist, and optionally supports **incremental update** (re-analyze only changed files).

**Implementation:** `src/agents/archivist.py`.  
**Depends on:** [data-model.md](../data-model.md), all other agents ([surveyor.md](surveyor.md), [hydrologist.md](hydrologist.md), [semanticist.md](semanticist.md)).

---

## Role

- Write all **.cartography/** artifacts to disk (or configured output path).
- Structure **CODEBASE.md** for direct injection into AI coding agents.
- Produce **onboarding_brief.md** from Semanticist’s Day-One answers.
- Serialize **lineage_graph.json** and maintain **semantic_index/**.
- Emit **cartography_trace.jsonl** (audit log of every analysis action, evidence source, confidence).
- Support **incremental update**: re-analyze only files changed since last run (via git diff).

---

## Inputs

- **Knowledge graph** after Surveyor, Hydrologist, and Semanticist: ModuleNode (with purpose_statement, domain_cluster, change_velocity, is_dead_code_candidate), DataLineageGraph, sources/sinks, Day-One answers with citations, documentation drift flags.
- **Output directory:** Default `.cartography/` under repo root (or per-target path).
- **Trace buffer:** In-memory log of agent actions (or the Archivist reads from each agent’s outputs) to write cartography_trace.jsonl.

---

## Artifacts

| Artifact | Description |
|----------|-------------|
| **CODEBASE.md** | Living context file. Sections below. Used for injection into AI coding agents. |
| **onboarding_brief.md** | Day-One Brief: five FDE questions answered with evidence citations (from Semanticist). |
| **lineage_graph.json** | Serialized DataLineageGraph (NetworkX or equivalent JSON) for downstream tooling. |
| **semantic_index/** | Vector store persisted (e.g. embeddings of purpose statements) for Navigator’s find_implementation. |
| **cartography_trace.jsonl** | Audit log: every agent action, evidence source, confidence level (Week 1 agent_trace pattern). |

---

## CODEBASE.md sections

The file must be structured for immediate use when injected into an AI coding agent. Required sections:

1. **Architecture Overview** — One paragraph summary of the system (from module graph + lineage high level).
2. **Critical Path** — Top 5 modules by PageRank (from Surveyor); these are architectural hubs.
3. **Data Sources & Sinks** — From Hydrologist’s find_sources() and find_sinks(); list entry and exit points.
4. **Known Debt** — Circular dependencies (Surveyor SCCs) + documentation drift flags (Semanticist).
5. **Recent Change Velocity** — High-velocity files (e.g. top N by change_velocity_30d); likely pain points.
6. **Module Purpose Index** — Concise list: path → purpose_statement (from Semanticist) for quick lookup.

---

## cartography_trace.jsonl

- **Format:** One JSON object per line (JSONL). Each record logs an analysis action: agent name, action (e.g. “analyze_module”, “blast_radius”), input (path or node), output summary or evidence source, confidence level if applicable.
- **Purpose:** Audit trail for intelligence gathering; mirrors Week 1’s agent_trace.jsonl. Enables debugging and verification of where an answer came from.

---

## Incremental update mode

- **Trigger:** If `git log` (or equivalent) shows new commits since the last Cartographer run, optionally **re-analyze only changed files** instead of the full codebase.
- **Behavior:** Determine the set of changed files (e.g. `git diff --name-only` between last run commit and HEAD). Run Surveyor/Hydrologist/Semanticist only on those files (and any files that depend on them if needed for consistency). Merge results into the existing knowledge graph and refresh only affected artifacts. This keeps the Cartographer practical for ongoing FDE engagements.

---

## References

- **Data model:** [data-model.md](../data-model.md) — node/edge types used in serialization.
- **Other agents:** [surveyor.md](surveyor.md) (module graph, PageRank, velocity, dead code), [hydrologist.md](hydrologist.md) (lineage, sources, sinks), [semanticist.md](semanticist.md) (purpose statements, Day-One answers, drift).
