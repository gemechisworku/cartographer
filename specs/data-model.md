# Knowledge Graph Data Model

The central data store is a **knowledge graph** implemented as:

- **NetworkX graph** — structure, module graph, and data lineage (nodes and edges).
- **Vector store** — semantic search over purpose statements (e.g. module/function descriptions).

All nodes and edges must conform to the Pydantic schemas below. Implementations live under `src/models/` and are consumed by agents and the Navigator.

**Reference:** [Cartographer challenge spec — Knowledge Graph Schema](../docs/cartographer_challenge_spec.md).

---

## Node types

### ModuleNode

Represents a file or module in the codebase (structural unit).

| Field | Description |
|-------|-------------|
| `path` | File path (relative to repo root). |
| `language` | Language (e.g. python, sql, yaml, javascript). |
| `purpose_statement` | Short “what this module does” (from code; may be filled by Semanticist). |
| `domain_cluster` | Inferred domain label (e.g. ingestion, transformation, serving, monitoring). |
| `complexity_score` | Metric(s): e.g. cyclomatic complexity, lines of code, comment ratio. |
| `change_velocity_30d` | Change frequency (e.g. from `git log --follow` over last 30 days). |
| `is_dead_code_candidate` | True if exported symbols have no internal or external import references. |
| `last_modified` | Last modification time (e.g. from git or filesystem). |

---

### DatasetNode

Represents a dataset, table, file, stream, or API-backed data asset.

| Field | Description |
|-------|-------------|
| `name` | Identifier (table name, path, stream name, etc.). |
| `storage_type` | One of: `table`, `file`, `stream`, `api`. |
| `schema_snapshot` | Optional schema or column summary. |
| `freshness_sla` | Optional freshness / SLA description. |
| `owner` | Optional owner or team. |
| `is_source_of_truth` | Whether this is considered a source-of-truth asset. |

---

### FunctionNode

Represents a function (or callable) within a module.

| Field | Description |
|-------|-------------|
| `qualified_name` | Full name (e.g. module.path.function_name). |
| `parent_module` | Path of the containing module. |
| `signature` | Function signature (args, return type if known). |
| `purpose_statement` | What the function does (from code; may be from Semanticist). |
| `call_count_within_repo` | Number of call sites found within the repo. |
| `is_public_api` | True if considered part of the public API (e.g. no leading underscore). |

---

### TransformationNode

Represents a transformation step in the data pipeline (connects datasets).

| Field | Description |
|-------|-------------|
| `source_datasets` | List of dataset identifiers (upstream). |
| `target_datasets` | List of dataset identifiers (downstream). |
| `transformation_type` | Kind of transform (e.g. sql, python, dbt, airflow_task). |
| `source_file` | File where the transformation is defined. |
| `line_range` | Line range (start, end) in source_file. |
| `sql_query_if_applicable` | Optional SQL text for SQL-based transformations. |

---

## Edge types

Edges are directed. Weights and metadata are implementation-specific (e.g. edge attributes in NetworkX).

| Edge type | Source → Target | Description |
|-----------|-----------------|-------------|
| **IMPORTS** | source_module → target_module | Module A imports module B. Weight = import count (optional). |
| **PRODUCES** | transformation → dataset | A transformation produces a dataset (data lineage). |
| **CONSUMES** | transformation → dataset | A transformation consumes a dataset (upstream dependency). |
| **CALLS** | function → function | Call graph: function A calls function B. |
| **CONFIGURES** | config_file → module/pipeline | YAML/ENV or config file configures a module or pipeline. |

---

## Usage notes

- **Module graph (Surveyor):** Primarily ModuleNode + IMPORTS (and optionally FunctionNode + CALLS).
- **Data lineage (Hydrologist):** DatasetNode, TransformationNode, PRODUCES, CONSUMES; CONFIGURES for DAG/config-driven pipelines.
- **Semanticist:** Fills or updates `purpose_statement` and `domain_cluster` on ModuleNode (and optionally FunctionNode).
- **Navigator:** Queries the graph (e.g. lineage traversal, blast radius) and the vector store (semantic search); all answers cite evidence (file, line, analysis method).

Serialization of the graph (e.g. to `.cartography/module_graph.json`, `.cartography/lineage_graph.json`) is defined in the Archivist and pipeline specs.
