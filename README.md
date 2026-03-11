# Brownfield Cartographer

Multi-agent codebase intelligence system for data-engineering repos. Produces a knowledge graph, data lineage, semantic index, CODEBASE.md, and Day-One onboarding brief.

## Install

```bash
uv sync
```

## Run analysis

Analyze a local directory or a GitHub repo URL (cloned to a temp dir). Writes `.cartography/` under the repo (or `-o` path).

```bash
uv run cartographer analyze <path-or-github-url>
uv run cartographer analyze .                    # current directory
uv run cartographer analyze https://github.com/dbt-labs/jaffle_shop
```

**Options:** `-o DIR` (output dir), `--days N` (git velocity window), `--sql-dialect` (postgres|bigquery|snowflake|duckdb).

**Artifacts (interim):** `.cartography/module_graph.json`, `.cartography/lineage_graph.json`.

## Run tests

```bash
uv run pytest
```

See [docs/TESTING.md](docs/TESTING.md) for the testing guide.

## Specs and plan

- **Specs:** [specs/README.md](specs/README.md)
- **Implementation plan:** [docs/implementation_plan.md](docs/implementation_plan.md)
- **Deliverables:** [docs/deliverables-and-rubric.md](docs/deliverables-and-rubric.md)
