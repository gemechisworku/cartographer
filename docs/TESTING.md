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
