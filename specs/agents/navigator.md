# Agent: Navigator (Query Interface)

The Navigator is a **LangGraph agent** that provides the query interface to the codebase knowledge graph. It exposes four tools for exploratory and precise structured querying; every answer must **cite evidence** (source file, line range, and analysis method: static vs. LLM inference).

**Implementation:** `src/agents/navigator.py`.  
**Depends on:** [data-model.md](../data-model.md), [hydrologist.md](hydrologist.md) (lineage concepts: blast_radius, trace_lineage).

---

## Role

- Allow **natural language** and **structured** interrogation of the knowledge graph.
- Implement four tools: find_implementation, trace_lineage, blast_radius, explain_module.
- Enforce **evidence citations** on every response: file path, line range, and whether the answer came from static analysis or LLM inference (for trust).

---

## Tools

| Tool | Query type | Description | Example |
|------|------------|-------------|---------|
| **find_implementation(concept)** | Semantic | Search the vector store (purpose statements) for where a concept is implemented. | “Where is the revenue calculation logic?” |
| **trace_lineage(dataset, direction)** | Graph | Traverse the DataLineageGraph upstream or downstream from a dataset. | “What produces the daily_active_users table?” |
| **blast_radius(module_path)** | Graph | Return all dependents of a module (what breaks if this module changes). Uses Hydrologist’s blast_radius plus module graph. | “What breaks if I change src/transforms/revenue.py?” |
| **explain_module(path)** | Generative | Produce a short explanation of what a module does, using graph context and optionally LLM. | “Explain what src/ingestion/kafka_consumer.py does.” |

---

## Contract per tool

### find_implementation(concept)

- **Input:** Natural language concept or phrase (e.g. “revenue calculation”, “Kafka consumer”).
- **Behavior:** Embed the concept; query the **vector store** (semantic_index of purpose statements). Return matching modules/functions with similarity score, file path, line range. Cite: “semantic search (LLM-derived purpose).”
- **Output:** List of (path, line_range, snippet or purpose, confidence/score).

### trace_lineage(dataset, direction)

- **Input:** Dataset name (or table/path); direction = "upstream" | "downstream".
- **Behavior:** Look up the dataset in the DataLineageGraph. Traverse CONSUMES (upstream) or PRODUCES (downstream). Return chain of datasets and transformations with source_file and line_range.
- **Output:** Ordered list of (node_id, type, source_file, line_range). Cite: “static analysis (lineage graph).”

### blast_radius(module_path)

- **Input:** Module path (e.g. `src/transforms/revenue.py`).
- **Behavior:** Call Hydrologist’s **blast_radius** for lineage impact; optionally include module graph (IMPORTS) so that modules that import this one are also listed. Return all affected nodes with file and line.
- **Output:** List of (node_id, source_file, line_range). Cite: “static analysis (lineage + module graph).”

### explain_module(path)

- **Input:** Module file path.
- **Behavior:** Load ModuleNode (purpose_statement, domain_cluster), related FunctionNodes, and optionally code snippet. If needed, call LLM to generate a short explanation. Prefer graph-derived purpose; use LLM only when enriching.
- **Output:** Short explanation plus citations: “Purpose from semantic analysis (LLM)” and/or “Structure from static analysis (tree-sitter).”

---

## Evidence citation rules

- Every tool response must include:
  - **Source file** (path relative to repo root).
  - **Line range** (start, end) when applicable.
  - **Analysis method:** “static analysis” (Surveyor/Hydrologist, graph traversal) vs. “LLM inference” (Semanticist, purpose statements, generative explain). This distinction matters for user trust.

---

## References

- **Data model:** [data-model.md](../data-model.md) — graph and vector store usage.
- **Hydrologist:** [hydrologist.md](hydrologist.md) — DataLineageGraph, blast_radius, find_sources, find_sinks.
