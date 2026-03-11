# Agent: Hydrologist (Data Flow & Lineage Analyst)

The Hydrologist builds the **data lineage DAG** for data-engineering codebases: it analyzes data sources, transformations, and sinks across Python, SQL, YAML, and notebooks, and produces a DataLineageGraph (NetworkX DiGraph) plus operations for blast radius, sources, and sinks.

**Implementation:** `src/agents/hydrologist.py`.  
**Depends on:** [data-model.md](../data-model.md), [analyzers.md](../analyzers.md) (tree_sitter_analyzer, sql_lineage, dag_config_parser).

---

## Role

- Construct the **DataLineageGraph**: nodes = datasets/tables (and optionally transformation steps); edges = data flow with transformation_type, source_file, line_range metadata.
- Support queries: “Show me all upstream dependencies of table X” and “What would break if I change the schema of table Y?”
- Expose **blast_radius**, **find_sources**, and **find_sinks**.

---

## Inputs

- **Repo root path.**
- **Knowledge graph** (or module/file list) so the Hydrologist knows which files to analyze. Typically run after the Surveyor has identified files.
- Optional: **dialect hints** for SQL files (PostgreSQL, BigQuery, Snowflake, DuckDB).

---

## Supported input patterns

| Language / format | Analyzer | What is extracted |
|-------------------|----------|--------------------|
| Python | tree_sitter_analyzer (data-flow queries) | pandas read_* / to_*, SQLAlchemy execute(), PySpark read/write; dataset names/paths as strings. Dynamic refs logged, not emitted. |
| SQL / dbt | sql_lineage | Table dependencies from SELECT/FROM/JOIN/WITH (CTE); dbt ref()/source(). |
| YAML / config | dag_config_parser | Airflow DAG definitions, dbt schema.yml, Prefect flow definitions; pipeline topology and config→pipeline. |
| Notebooks | Parsed as Python or custom .ipynb handling | Data source references and output paths (cells as code). |

---

## Outputs (written to knowledge graph)

- **DatasetNode** for each distinct dataset/table/file/stream (name, storage_type, optional schema_snapshot, etc.).
- **TransformationNode** for each transformation step: source_datasets, target_datasets, transformation_type, source_file, line_range, sql_query_if_applicable.
- **PRODUCES** edges: transformation → dataset (downstream).
- **CONSUMES** edges: transformation → dataset (upstream).
- **CONFIGURES** edges (from dag_config_parser): config_file → module/pipeline.
- **DataLineageGraph**: NetworkX DiGraph of lineage (nodes = datasets + transformations, edges = PRODUCES/CONSUMES). Serialized to `.cartography/lineage_graph.json` (see Archivist).

---

## Core operations

### Merge analyzer outputs

- Run **PythonDataFlowAnalyzer** (tree_sitter data-flow queries), **SQLLineageAnalyzer** (sql_lineage), and **DAGConfigAnalyzer** (dag_config_parser) on the relevant files.
- **Merge** results: deduplicate dataset names, resolve dbt ref()/source() to table names where possible, unify task/model identifiers. Build a single DataLineageGraph (NetworkX DiGraph) with consistent node/edge types per [data-model.md](../data-model.md).

### blast_radius(node)

- **Input:** A node identifier (e.g. module path, dataset name, or transformation).
- **Behavior:** From the lineage graph (and optionally module graph), compute the set of nodes that **depend on** this node (downstream). Use BFS/DFS from the given node along PRODUCES/CONSUMES (and IMPORTS if module-level). Return list of affected nodes with source_file and line_range where available.
- **Output:** List of (node_id, source_file, line_range) or equivalent; used by Navigator and for the Day-One question “What is the blast radius if the most critical module fails?”

### find_sources()

- **Behavior:** In the DataLineageGraph, find nodes with **in-degree = 0** (no incoming CONSUMES/PRODUCES). These are the entry points of the data system (raw sources).
- **Output:** List of DatasetNode (or ids) that are sources.

### find_sinks()

- **Behavior:** In the DataLineageGraph, find nodes with **out-degree = 0** (no outgoing PRODUCES). These are the exit points (final datasets or outputs).
- **Output:** List of DatasetNode (or ids) that are sinks.

---

## References

- **Data model:** [data-model.md](../data-model.md) — DatasetNode, TransformationNode, PRODUCES, CONSUMES, CONFIGURES.
- **Analyzers:** [analyzers.md](../analyzers.md) — tree_sitter_analyzer (Python data flow), sql_lineage, dag_config_parser.
