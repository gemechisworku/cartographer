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

**Options:** `-o DIR` (output dir), `--days N` (git velocity window), `--sql-dialect` (postgres|bigquery|snowflake|duckdb), `--no-semanticist` (skip LLM/purpose/Day-One).

**Artifacts:** `.cartography/CODEBASE.md`, `.cartography/onboarding_brief.md`, `module_graph.json`, `lineage_graph.json`, `semantic_index/purpose_index.json`, `cartography_trace.jsonl`, `day_one_answers.json`, `documentation_drift.json`. Without an API key, Semanticist still runs with placeholders (see [docs/TESTING.md](docs/TESTING.md)).

## Query mode (Navigator)

After running `analyze`, query the codebase interactively with the Navigator:

```bash
uv run cartographer query <repo-path>           # uses <repo>/.cartography
uv run cartographer query -o .cartography      # use a specific .cartography dir
```

**Commands in the REPL:** `/find <concept>`, `/trace <dataset> upstream|downstream`, `/blast <module_path>`, `/explain <path>`. You can also ask in natural language (e.g. “Where is the revenue logic?”, “What breaks if I change src/foo.py?”). Every answer cites evidence (file, line, static vs LLM).

## Run tests

```bash
uv run pytest
```

See [docs/TESTING.md](docs/TESTING.md) for the testing guide.

## Specs and plan

- **Specs:** [specs/README.md](specs/README.md)
- **Implementation plan:** [docs/implementation_plan.md](docs/implementation_plan.md)
- **Deliverables:** [docs/deliverables-and-rubric.md](docs/deliverables-and-rubric.md)
