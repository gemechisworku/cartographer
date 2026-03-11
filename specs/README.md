# Cartographer Specs — Index

The **Brownfield Cartographer** is a multi-agent codebase intelligence system for data-engineering repos. It ingests a GitHub repo or local path and produces a living, queryable knowledge graph plus artifacts (CODEBASE.md, onboarding brief, lineage graph, semantic index). This folder contains the **project specs** — the agent-oriented breakdown of what to build. Use this index to find the right spec for the task at hand.

**Canonical challenge (full requirements):** [docs/cartographer_challenge_spec.md](../docs/cartographer_challenge_spec.md)  
**Deliverables and rubric (evaluation, dates, file lists):** [docs/deliverables-and-rubric.md](../docs/deliverables-and-rubric.md)

---

## Specs — read when…

| Spec | Path | Read when you're… |
|------|------|-------------------|
| **Overview** | [overview.md](overview.md) | Onboarding; need goals, Day-One questions, or high-level pipeline. |
| **Data model** | [data-model.md](data-model.md) | Defining or using graph nodes/edges (ModuleNode, DatasetNode, TransformationNode, IMPORTS, PRODUCES, etc.). |
| **Analyzers** | [analyzers.md](analyzers.md) | Implementing or calling tree_sitter_analyzer, sql_lineage, or dag_config_parser. |
| **Surveyor** | [agents/surveyor.md](agents/surveyor.md) | Building static structure: module graph, PageRank, git velocity, dead code. |
| **Hydrologist** | [agents/hydrologist.md](agents/hydrologist.md) | Building data lineage, blast_radius, find_sources/find_sinks. |
| **Semanticist** | [agents/semanticist.md](agents/semanticist.md) | Adding LLM purpose statements, doc drift, domain clustering, Day-One answers. |
| **Navigator** | [agents/navigator.md](agents/navigator.md) | Implementing the query interface (find_implementation, trace_lineage, blast_radius, explain_module). |
| **Archivist** | [agents/archivist.md](agents/archivist.md) | Writing CODEBASE.md, onboarding_brief, lineage JSON, semantic index, trace; incremental update. |
| **Pipeline and CLI** | [pipeline-and-cli.md](pipeline-and-cli.md) | Wiring the orchestrator, defining CLI subcommands (analyze, query), or .cartography/ layout. |
| **Targets and validation** | [targets-and-validation.md](targets-and-validation.md) | Choosing target codebases, demo protocol, or using RECONNAISSANCE.md. |

---

## Dependency order

Specs were created in dependency order (see [docs/specs_creation_plan.md](../docs/specs_creation_plan.md)):

1. overview → 2. data-model → 3. analyzers → 4–8. agents (surveyor, hydrologist, semanticist, navigator, archivist) → 9. pipeline-and-cli → 10. targets-and-validation.  
Deliverables and rubric live in **docs/** (challenge evaluation, not a project spec).

---

## Quick links

- **Challenge spec:** [docs/cartographer_challenge_spec.md](../docs/cartographer_challenge_spec.md)  
- **Deliverables & rubric:** [docs/deliverables-and-rubric.md](../docs/deliverables-and-rubric.md)  
- **Specs creation plan:** [docs/specs_creation_plan.md](../docs/specs_creation_plan.md)
