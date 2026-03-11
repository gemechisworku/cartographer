# Brownfield Cartographer

Multi-agent codebase intelligence system for data-engineering repos. Produces a knowledge graph, data lineage, semantic index, CODEBASE.md, and Day-One onboarding brief.

## Install

```bash
uv sync
```

## Run analysis

*(Interim: `analyze` subcommand; see implementation plan.)*

```bash
uv run python -m cli analyze <repo-path-or-github-url>
```

## Run tests

```bash
uv run pytest
```

See [docs/TESTING.md](docs/TESTING.md) for the testing guide.

## Specs and plan

- **Specs:** [specs/README.md](specs/README.md)
- **Implementation plan:** [docs/implementation_plan.md](docs/implementation_plan.md)
- **Deliverables:** [docs/deliverables-and-rubric.md](docs/deliverables-and-rubric.md)
