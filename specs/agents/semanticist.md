# Agent: Semanticist (LLM-Powered Purpose Analyst)

The Semanticist adds **semantic understanding** that static analysis cannot provide: purpose statements grounded in code (not docstrings), documentation drift detection, domain clustering, and answers to the Five FDE Day-One questions. It runs after the Surveyor and Hydrologist and consumes their outputs.

**Implementation:** `src/agents/semanticist.py`.  
**Depends on:** [data-model.md](../data-model.md), [overview.md](../overview.md), [surveyor.md](surveyor.md), [hydrologist.md](hydrologist.md).

---

## Role

- For each module: generate a **Purpose Statement** (what this module does, not how) based on its **code**, not its docstring.
- **Flag documentation drift:** Compare purpose inferred from code with the existing docstring; if they contradict, flag as “Documentation Drift”.
- **Domain clustering:** Cluster modules into inferred domains (e.g. ingestion, transformation, serving, monitoring) from semantic similarity of purpose statements (embed + k-means).
- **Answer the Five Day-One questions** with evidence citations (file paths and line numbers), by synthesizing Surveyor + Hydrologist output with LLM reasoning.

---

## Inputs

- **Knowledge graph** after Surveyor and Hydrologist: ModuleNode (and optionally FunctionNode), module graph, DataLineageGraph, sources/sinks, blast radius hints.
- **Source code** (or file paths to read) for modules that need purpose statements.
- **Five Day-One questions** (see [overview.md](../overview.md)).

---

## Outputs (written to knowledge graph / artifacts)

- **ModuleNode.purpose_statement** (and optionally FunctionNode.purpose_statement) updated with LLM-generated purpose.
- **ModuleNode.domain_cluster** updated with inferred domain label.
- **Documentation drift flags** (e.g. list of (module_path, docstring_vs_implementation)); consumed by Archivist for “Known Debt”.
- **Day-One answers** with evidence citations → fed to Archivist for `onboarding_brief.md`.
- **Vector store**: embeddings of purpose statements for semantic search (Navigator’s find_implementation); see Archivist for `semantic_index/`.

---

## Cost discipline

- **ContextWindowBudget:** Before each LLM call, estimate token count and track cumulative spend. Enforce a budget (configurable).
- **Tiered model selection:** Use a **fast, cheap model** (e.g. Gemini Flash, Mistral via OpenRouter) for bulk module purpose extraction. Reserve **expensive models** (e.g. Claude, GPT-4) for synthesis only: domain cluster naming and Day-One answer generation.

---

## Core operations

### generate_purpose_statement(module_node)

- **Input:** ModuleNode (path, and access to module source code).
- **Behavior:** Send the module’s **code** (not docstring) to the LLM. Ask for a 2–3 sentence purpose statement that explains **business function**, not implementation detail. Cross-reference with the existing docstring; if they contradict, mark “Documentation Drift”.
- **Output:** Updated purpose_statement; optional drift flag.

### cluster_into_domains()

- **Input:** All ModuleNode.purpose_statement (after bulk purpose generation).
- **Behavior:** Embed purpose statements (e.g. via an embedding API). Run **k-means** (k = 5–8) and assign each module to a cluster. Optionally use LLM to label each cluster with an inferred domain name (e.g. “ingestion”, “transformation”, “serving”).
- **Output:** ModuleNode.domain_cluster updated; Domain Architecture Map for reporting.

### answer_day_one_questions()

- **Input:** Full Surveyor + Hydrologist output (module graph, PageRank hubs, lineage graph, sources, sinks, blast radius), plus code context as needed.
- **Behavior:** Single **synthesis** prompt to the LLM (prefer expensive model) asking for the Five FDE Day-One answers with **specific evidence citations**: file paths and line numbers. Questions (verbatim from [overview.md](../overview.md)):
  1. What is the primary data ingestion path?
  2. What are the 3–5 most critical output datasets/endpoints?
  3. What is the blast radius if the most critical module fails?
  4. Where is the business logic concentrated vs. distributed?
  5. What has changed most frequently in the last 90 days (git velocity map)?
- **Output:** Structured answers with citations; passed to Archivist for `onboarding_brief.md`.

---

## References

- **Data model:** [data-model.md](../data-model.md) — ModuleNode.purpose_statement, domain_cluster.
- **Overview:** [overview.md](../overview.md) — Five Day-One questions.
- **Surveyor / Hydrologist:** [surveyor.md](surveyor.md), [hydrologist.md](hydrologist.md) — inputs to synthesis.
