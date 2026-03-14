# Testing Guide

How to run tests for the Brownfield Cartographer and how to add tests for new code. Follow the agent rule: **write code with tests** — add or extend tests for each meaningful unit of behavior.

---

## Quick start

From the repo root:

```bash
uv sync
uv run pytest
```

- **All tests:** `uv run pytest`
- **Verbose:** `uv run pytest -v`
- **One directory:** `uv run pytest tests/unit/models/`
- **One file:** `uv run pytest tests/unit/models/test_nodes.py`
- **One test:** `uv run pytest tests/unit/models/test_nodes.py::TestModuleNode::test_minimal_valid`

---

## Layout

```
tests/
  conftest.py          # Pytest config; project installed as package "src"
  unit/
    models/            # Tests for src/models (nodes, edges)
      test_nodes.py
      test_edges.py
  integration/         # (Later) CLI, orchestrator, fixtures
```

- **Unit tests:** Fast, no I/O or external services. Use the `src` package (installed by `uv sync`).
- **Imports:** Tests use `from src.models.nodes import ModuleNode` etc., because the project is installed with the top-level package name `src`.

---

## Running tests

### Prerequisites

- **uv** installed ([uv.pypa.io](https://uv.pypa.io)).
- From repo root: `uv sync` installs the project and dev deps (pytest, pytest-cov, ruff).

### Commands

| Goal | Command |
|------|--------|
| Run all tests | `uv run pytest` |
| Verbose + short traceback | `uv run pytest -v --tb=short` (default in pyproject) |
| Run with coverage | `uv run pytest --cov=src --cov-report=term-missing` |
| Run only unit model tests | `uv run pytest tests/unit/models/` |
| Run a single test class | `uv run pytest tests/unit/models/test_nodes.py::TestModuleNode` |
| Run last failed | `uv run pytest --lf` |

### CI / script

```bash
cd /path/to/cartographer
uv sync
uv run pytest -v
```

---

## What’s tested

- **Node models** (`tests/unit/models/test_nodes.py`):  
  `ModuleNode`, `DatasetNode`, `FunctionNode`, `TransformationNode` — minimal and full valid payloads, required fields, validation (e.g. `DatasetNode.storage_type` must be one of table/file/stream/api).
- **Edge types** (`tests/unit/models/test_edges.py`):  
  `EdgeType` enum (IMPORTS, PRODUCES, CONSUMES, CALLS, CONFIGURES), `EdgePayload` (weight, extra), serialization roundtrip.
- **Analyzers** (`tests/unit/analyzers/`):  
  **tree_sitter_analyzer** — LanguageRouter (Python, YAML, unknown), parse_file, analyze_module (imports, public functions/classes, private excluded).  
  **sql_lineage** — extract_table_dependencies (SELECT, JOIN, INSERT, CREATE TABLE AS, dialects), extract_lineage_from_file.  
  **dag_config_parser** — parse_dbt_schema_yml (models), parse_airflow_dag_python (task_id, >>), analyze_dag_config dispatch.
- **Knowledge graph** (`tests/unit/graph/test_knowledge_graph.py`):  
  add_module_node, add_import_edge, add_function_node, add_calls_edge; add_dataset_node, add_transformation_node, add_produces/consumes; serialize, write_module_graph_json, write_lineage_graph_json, load roundtrip.
- **Agents** (`tests/unit/agents/`):  
  **Surveyor** — analyze_module, extract_git_velocity, run_surveyor (module graph populated).  
  **Hydrologist** — run_hydrologist (Python AST + SQL + dbt YAML/DAG), blast_radius, find_sources, find_sinks; Python+SQL+config merged; edges carry transformation_type, source_file, line_range.  
  **Semanticist** — ContextWindowBudget, generate_purpose_statement, cluster_into_domains, answer_day_one_questions, run_semanticist (mock LLM, skip flags, purpose/drift).

---

## Testing Semanticist features

The Semanticist runs as part of `cartographer analyze` unless you pass `--no-semanticist`. It adds **purpose statements**, **domain clustering**, and **Day-One answers**; without an LLM API key it still runs and writes placeholder text (graceful degradation).

### 1. Unit tests (no API key)

Fast, deterministic tests with mock LLM and embeddings:

```bash
uv run pytest tests/unit/agents/test_semanticist.py -v
```

Covers: budget tracking, purpose generation from code, doc-drift heuristic, domain clustering (k-means), Day-One answer parsing, and `run_semanticist` with skip flags.

### 2. Run analysis without an API key (placeholders)

Without `OPENAI_API_KEY` or `OPENROUTER_API_KEY`, the Semanticist uses placeholders and fallback embeddings so the pipeline still completes:

```bash
# From repo root
uv run cartographer analyze .
```

**Check outputs:**

- **`.cartography/module_graph.json`** — Module nodes may have `purpose_statement` and `domain_cluster` (if any purpose was generated; without key, placeholders may appear).
- **`.cartography/day_one_answers.json`** — Five questions with `answer` and `citations`; without key you’ll see placeholder text like `[Purpose/synthesis skipped: no OPENAI_API_KEY or OPENROUTER_API_KEY set]`.
- **`.cartography/documentation_drift.json`** — List of `{ "module_path", "docstring_excerpt" }` where code vs docstring were flagged as contradicting.

### 3. Run analysis with an API key (real LLM)

For real purpose statements, domain labels, and Day-One answers, set an API key. The CLI **loads a `.env` file** from the current working directory, so you can put `OPENAI_API_KEY=sk-...` in a `.env` file in the project root (do not commit; `.env` is in `.gitignore`) and run `uv run cartographer analyze .` from that directory—no need to set the variable in the shell.

```bash
# OpenAI (cmd)
set OPENAI_API_KEY=sk-...
uv run cartographer analyze .

# PowerShell
$env:OPENAI_API_KEY = "sk-..."
uv run cartographer analyze .

# Or OpenRouter (e.g. other models)
set OPENROUTER_API_KEY=sk-...
set OPENAI_BASE_URL=https://openrouter.ai/api/v1
uv run cartographer analyze .
```

Then inspect the same files; `day_one_answers.json` should have concrete answers and file/line citations.

### 4. Skip Semanticist (faster runs)

To run only Surveyor + Hydrologist (no LLM, no purpose/domain/Day-One):

```bash
uv run cartographer analyze . --no-semanticist
```

Only `module_graph.json` and `lineage_graph.json` are written; no `day_one_answers.json` or `documentation_drift.json`.

### 5. Quick verification checklist

| What to check | Where |
|---------------|--------|
| Purpose on modules | `module_graph.json` → `nodes` → node with `path` → `purpose_statement` |
| Domain clusters | Same node → `domain_cluster` (e.g. `cluster_0` or LLM label) |
| Five Day-One answers | `day_one_answers.json` → array of `{ "question", "answer", "citations" }` |
| Doc drift | `documentation_drift.json` → list of `module_path` + `docstring_excerpt` |

---

## Lineage queries: blast_radius, find_sources, find_sinks (multi-language)

The Hydrologist builds a **single lineage graph** from Python (pandas/PySpark/SQLAlchemy), SQL, and config (dbt YAML, Airflow DAG). All edges carry **transformation_type**, **source_file**, and **line_range** where available.

### Example: blast_radius (what breaks if this node changes?)

- **SQL table:** `blast_radius(kg, "raw_events")` — returns downstream transformations and datasets that depend on `raw_events` (e.g. SQL models, Python reads), each with `(node_id, source_file, line_range)`.
- **Python module / file:** Navigator’s `blast_radius(kg, "src/ingest.py")` combines lineage impact (transformations in that file) plus **module graph** importers (who imports this module).

### Example: find_sources / find_sinks (entry and exit points)

- **find_sources(kg):** nodes with in-degree 0 — e.g. SQL tables that are only read, CSV paths from `pd.read_csv`, or config-defined sources.
- **find_sinks(kg):** nodes with out-degree 0 — e.g. tables written by INSERT/CTAS, paths from `df.to_parquet`, or final DAG tasks.

### Running queries (Navigator)

After `cartographer analyze .` and `cartographer query .`:

- `/trace my_table upstream` — static analysis (lineage graph); returns chain with source_file and line_range.
- `/blast src/transforms/revenue.py` — static analysis (lineage + module graph); returns affected node_ids with file and line.
- Responses always label evidence as **static analysis** (Surveyor/Hydrologist, graph) vs **LLM** (Semanticist, purpose/explain).

---

## Adding tests

1. **Where:** Mirror `src/`: e.g. for `src/analyzers/sql_lineage.py` add `tests/unit/analyzers/test_sql_lineage.py`.
2. **Imports:** Always use the `src` package: `from src.models.nodes import ModuleNode`, `from src.analyzers.sql_lineage import ...`.
3. **Fixtures:** Put shared fixtures in `tests/conftest.py` or a `conftest.py` in the same directory as the tests.
4. **Naming:** Prefer descriptive names: `test_sql_lineage_extracts_from_select_join`, `test_blast_radius_returns_downstream_only`.
5. **Isolation:** Prefer small, deterministic fixtures (e.g. temp dirs, in-memory SQL strings). Avoid large repos or network unless required for integration tests.

---

## Coverage (optional)

```bash
uv run pytest --cov=src --cov-report=term-missing
```

Coverage is not required for the interim deliverable but helps find untested code. Add `--cov-report=html` to generate `htmlcov/`.

---

## Linting

```bash
uv run ruff check src tests
uv run ruff format src tests
```

Fix lint issues in code you touch (per agent rule).
