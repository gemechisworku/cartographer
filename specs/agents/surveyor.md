# Agent: Surveyor (Static Structure Analyst)

The Surveyor performs **deep static analysis** of the codebase and builds the **structural skeleton**: module graph, public API surface, complexity signals, change velocity, and dead-code candidates. It is the first agent in the pipeline and populates the knowledge graph with ModuleNode, FunctionNode, and IMPORTS (and optionally CALLS).

**Implementation:** `src/agents/surveyor.py`.  
**Depends on:** [data-model.md](../data-model.md), [analyzers.md](../analyzers.md) (tree_sitter_analyzer).

---

## Role

- Build the **module import graph**: which files import which (Python imports + relative path resolution).
- Expose the **public API surface**: exported/public functions and classes with signatures (leading-underscore convention).
- Attach **complexity signals**: cyclomatic complexity, lines of code, comment ratio.
- Compute **change velocity**: `git log --follow` per file (e.g. last 30 days); identify high-velocity core (e.g. 20% of files with 80% of changes).
- Identify **dead-code candidates**: exported symbols with no internal or external import references.

---

## Inputs

- **Repo root path** (local directory or cloned GitHub repo).
- Optional: **file allowlist/blocklist** or globs to restrict analysis (e.g. exclude `vendor/`, `node_modules/`).
- Optional: **days** for change velocity (default 30).

---

## Outputs (written to knowledge graph)

- **ModuleNode** per analyzed file: path, language, complexity_score, change_velocity_30d, is_dead_code_candidate, last_modified. Fields purpose_statement and domain_cluster are left for the Semanticist.
- **FunctionNode** per public function/class: qualified_name, parent_module, signature, is_public_api; call_count_within_repo if call graph is built.
- **IMPORTS** edges: source_module → target_module; weight = import count (optional).
- **CALLS** edges (optional): function → function for call graph analysis.
- **Module import graph** as a NetworkX DiGraph (in-memory and/or serialized). Used for PageRank and strongly connected components.

---

## Core operations

### analyze_module(path)

- **Input:** File path (relative to repo root).
- **Behavior:** Use [tree_sitter_analyzer](../analyzers.md#1-tree_sitter_analyzer-languagerouter--ast) to parse the file. Map result to ModuleNode: extract imports (→ IMPORTS), public functions and classes (→ FunctionNode), complexity signals (→ ModuleNode.complexity_score). Resolve relative imports to repo-root paths.
- **Output:** ModuleNode (and list of FunctionNodes, list of IMPORTS). On parse failure, log and skip (per analyzer conventions).

### extract_git_velocity(path, days=30)

- **Input:** Repo root path; optional `days` window.
- **Behavior:** Run `git log --follow` (or equivalent) per file; count commits per file in the window. Compute change frequency (e.g. commits per day or raw count). Identify the high-velocity subset (e.g. top 20% of files by change count).
- **Output:** Map file path → change_velocity_30d (and optionally last_modified). Attach to ModuleNode when building/updating nodes.

### Module graph construction

- Build a **NetworkX DiGraph** where nodes are module paths (or ModuleNode ids) and edges are IMPORTS (source → target). Optionally add weight = number of import statements from source to target.
- **PageRank:** Run on the import graph to identify the most “imported” modules (architectural hubs / critical path).
- **Strongly connected components (SCCs):** Detect circular dependencies; report as “Known Debt” (see Archivist).

### Dead-code detection

- For each exported symbol (public function/class): check whether it is imported or called anywhere in the repo (via IMPORTS and CALLS). If no references, set ModuleNode.is_dead_code_candidate or mark the corresponding FunctionNode.

---

## Serialization

- The Surveyor (or orchestrator) writes the **module graph** to `.cartography/module_graph.json` using NetworkX’s JSON serializer (or a schema that preserves nodes/edges). Exact timing may be in the pipeline spec; the Surveyor produces the graph structure that the Archivist can persist.

---

## References

- **Data model:** [data-model.md](../data-model.md) — ModuleNode, FunctionNode, IMPORTS, CALLS.
- **Analyzers:** [analyzers.md](../analyzers.md) — tree_sitter_analyzer (LanguageRouter, AST, imports, functions, classes).
