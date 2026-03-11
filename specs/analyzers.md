# Analyzers

Analyzers are the **low-level extraction layer** used by the Surveyor and Hydrologist agents. They parse source files and configs and return structured data that populates the knowledge graph (see [data-model.md](data-model.md)). Implementations live under `src/analyzers/`.

This spec defines **contracts only**: inputs, outputs, and error behavior. Agent specs describe how each analyzer is invoked and how results are merged into the graph.

---

## Conventions

- **Input:** Each analyzer receives at least a **repo root path** and **file path** (relative or absolute). Some accept **source text** or **dialect** when the caller already has content or knows the variant (e.g. SQL dialect).
- **Errors:** On parse failure or unsupported input, **log the error and skip** the file. Do not fail the whole run. Return a partial result or empty result for that file; optional fields may indicate "dynamic reference, cannot resolve" or similar.
- **Data model:** Output shapes align with [data-model.md](data-model.md). Analyzers produce data that agents map onto Node types (ModuleNode, DatasetNode, FunctionNode, TransformationNode) and Edge types (IMPORTS, PRODUCES, CONSUMES, CONFIGURES). Analyzers do not create graph nodes directly unless specified in an agent spec.
- **Idempotency:** Same file + content should yield the same extracted result. No side effects beyond reading the filesystem and (if applicable) the repo root for context (e.g. resolving relative imports).

---

## 1. tree_sitter_analyzer (LanguageRouter + AST)

**Responsibility:** Language-agnostic AST parsing for structural extraction. Used by the Surveyor for the module graph and by the Hydrologist’s Python data-flow step.

**Implementation:** `src/analyzers/tree_sitter_analyzer.py`.

### LanguageRouter

- **Input:** File path (or file extension).
- **Output:** The tree-sitter grammar/language to use for that file.
- **Supported languages (minimum):** Python, SQL, YAML, JavaScript/TypeScript (per challenge spec). Select grammar by file extension (e.g. `.py` → Python, `.sql` → SQL, `.yml`/`.yaml` → YAML, `.js`/`.ts`/`.tsx` → JavaScript/TypeScript).
- **Unknown extension:** Return a sentinel or None; caller skips or treats as opaque.

### AST parsing contract

- **Input:** Repo root path, file path, optional raw source bytes (if not provided, read from repo root + file path).
- **Output:** A structured result per file. Exact shape is implementation-defined; the following must be derivable for supported languages (at least Python):

| Output | Description | Feeds data-model |
|--------|-------------|------------------|
| **Imports** | List of (source_module, target_module) or (importer_path, imported_path). For Python: import/from statements with relative path resolution relative to repo root. | IMPORTS edge; ModuleNode identity |
| **Public functions** | Name, signature (optional), line range. "Public" = no leading underscore (or project convention). | FunctionNode; parent_module = file path |
| **Classes** | Name, base classes (inheritance), line range. | FunctionNode or structural metadata for ModuleNode |
| **Complexity signals** | Optional: lines of code, comment ratio, cyclomatic complexity. | ModuleNode.complexity_score |

- **Method:** Use tree-sitter S-expression queries to extract the above from the AST. Do not rely on regex for structure.
- **Errors:** If parsing fails (syntax error, unsupported construct), log and return an empty or partial result for that file.

### Use by agents

- **Surveyor:** Calls this to build the module graph (imports → IMPORTS, files → ModuleNode) and to get public functions/classes for dead-code and API surface analysis.
- **Hydrologist (Python data flow):** Uses the same AST (or a dedicated query) to find pandas `read_*`/`to_*`, SQLAlchemy `execute()`, PySpark `read`/`write` calls and extract dataset names/paths as strings. F-strings and variable references: log as "dynamic reference, cannot resolve" and do not emit a concrete dataset edge.

---

## 2. sql_lineage (sqlglot)

**Responsibility:** Extract table-level dependencies from SQL (raw `.sql` and dbt model files) for the data lineage graph.

**Implementation:** `src/analyzers/sql_lineage.py`.

### Contract

- **Input:**
  - File path (relative to repo root).
  - Source text (SQL string).
  - Optional **dialect** hint: one of PostgreSQL, BigQuery, Snowflake, DuckDB (minimum supported set).
- **Output:**
  - **Table dependency graph:** List of (source_table, target_table) or equivalent. For a single statement: tables in FROM/JOIN/WITH (CTE) are upstream; the write target (INSERT/UPDATE/MERGE/CREATE TABLE AS) is downstream. For dbt, model name is typically the downstream table; ref() and source() resolve to upstream.
  - **Metadata (optional):** source_file, line_range, dialect, raw query snippet for TransformationNode.sql_query_if_applicable.
- **Parsing:** Use **sqlglot** to parse and walk the AST. Extract dependencies from SELECT/FROM/JOIN/WITH (CTE) chains. Handle dbt `ref()` and `source()` where possible (project-specific).
- **Dialects:** Support at minimum: PostgreSQL, BigQuery, Snowflake, DuckDB. Dialect affects reserved words and function names; use sqlglot’s dialect support.
- **Errors:** On parse error, log and return empty dependency list for that file.

### Feeds data-model

- **DatasetNode** for each distinct table name (name, storage_type=table).
- **TransformationNode** for each file/statement: source_datasets = upstream tables, target_datasets = downstream tables, transformation_type = e.g. `sql` or `dbt`, source_file, line_range, sql_query_if_applicable.
- **Edges:** CONSUMES (transformation → upstream dataset), PRODUCES (transformation → downstream dataset).

---

## 3. dag_config_parser (Airflow / dbt YAML)

**Responsibility:** Extract pipeline topology and config-driven dependencies from YAML (and optionally Python DAG definitions) so that task/DAG relationships and config→pipeline links are represented in the lineage and config graph.

**Implementation:** `src/analyzers/dag_config_parser.py`.

### Contract

- **Input:**
  - Repo root path.
  - File path and (for YAML) file content or path to read.
  - **Supported sources:** Airflow DAG definitions (Python files under examples/ or typical DAG paths), dbt `schema.yml` (and similar), Prefect flow definitions if in scope.
- **Output:**
  - **Pipeline topology:** List of (upstream_identifier, downstream_identifier) or (task_id, task_id) / (model_name, model_name). For Airflow: task dependencies from `set_downstream`/`set_upstream` or `>>`/`<<`; for dbt: model dependencies from schema.yml or dbt project.
  - **Config → pipeline:** Which config file or YAML block configures which module/DAG/model (for CONFIGURES edge).
- **Airflow:** Parse Python DAG files for `DAG(…)`, `BaseOperator` subclasses, and task dependency declarations. Extract task IDs and dependency edges. Optionally extract data source references from operator params (e.g. table names in BigQueryOperator).
- **dbt:** Parse `schema.yml` / `sources.yml` for model names, sources, and dependencies. Can be combined with sql_lineage (dbt models) for full dbt DAG.
- **Errors:** On parse or recognition failure, log and return empty topology for that file.

### Feeds data-model

- **CONFIGURES** edges: config_file → module or pipeline (e.g. schema.yml → dbt model set).
- **TransformationNode / lineage:** Task or model as transformation; upstream/downstream tasks or models as dataset-like nodes or transformation nodes, depending on how the Hydrologist merges with the rest of the lineage graph.
- **DatasetNode (optional):** If config explicitly names tables/sources, those can be added as datasets for lineage consistency.

---

## Summary

| Analyzer | Primary consumer | Key output | Data-model entities |
|----------|------------------|------------|----------------------|
| tree_sitter_analyzer | Surveyor, Hydrologist (Python) | Imports, functions, classes; Python data-flow call sites | ModuleNode, FunctionNode, IMPORTS; dataset refs for lineage |
| sql_lineage | Hydrologist | Table dependency list per file | DatasetNode, TransformationNode, CONSUMES, PRODUCES |
| dag_config_parser | Hydrologist | Pipeline topology, config→pipeline | CONFIGURES; TransformationNode / task dependencies |

Agents are responsible for **merging** analyzer outputs (e.g. deduplicating dataset names, resolving refs across files) and writing the canonical graph; see [agents/surveyor.md](agents/surveyor.md) and [agents/hydrologist.md](agents/hydrologist.md).
