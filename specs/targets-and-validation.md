# Target Codebases and Validation

This spec defines the **required target codebases** for running the Cartographer, the **demo protocol** (proof of execution), and the role of **RECONNAISSANCE.md** as the manual baseline for testing and comparison.

**Depends on:** [overview.md](overview.md), [docs/deliverables-and-rubric.md](../docs/deliverables-and-rubric.md).

---

## Required target codebases

The system must produce results for **at least two** of the following. These represent real-world systems encountered in FDE deployments.

### Primary options

| Target | Description | Verification |
|--------|-------------|--------------|
| **dbt jaffle_shop (or any dbt project)** | [github.com/dbt-labs/jaffle_shop](https://github.com/dbt-labs/jaffle_shop). Mixed SQL + YAML + Python. | Lineage graph must extract the full dbt DAG; match dbt’s own lineage visualization where possible. |
| **Apache Airflow example DAGs** | [github.com/apache/airflow](https://github.com/apache/airflow) (e.g. examples/). Python + YAML. | Identify pipeline topology, task dependencies, and data sources from Airflow operator definitions. |
| **Real open-source data platform** | e.g. mitodl/ol-data-platform or similar. Meaningful Python, SQL/dbt, YAML/config. | Cartography artifacts (CODEBASE.md, lineage, brief) must be meaningful and accurate. |

### Stretch

- **Real company open-source data platform** — e.g. Airbnb Minerva, Spotify Backstage data plugins, Stripe open-source tools. Brownfield, undocumented complexity. Highest-value demo: Day-One Brief on a repo no one on the team has read before.

### Self-referential validation

- **Your own Week 1 submission** — Local path to your Week 1 code. Run the Cartographer on it. Compare generated CODEBASE.md to your ARCHITECTURE_NOTES.md (or equivalent). Discrepancies indicate either Cartographer bugs or gaps in Week 1 documentation; document in the final report.

---

## RECONNAISSANCE.md role

- **RECONNAISSANCE.md** is a **manual Day-One analysis** of a chosen target codebase, produced **without** the Cartographer (human-only reconnaissance).
- **Do not edit it** for the purpose of “fixing” the spec or the tool; it is the **baseline** to compare against.
- **Use it for testing:** After running the Cartographer on the same target, compare system-generated CODEBASE.md and onboarding_brief.md to RECONNAISSANCE.md. Report: what matched, what differed, and why (in the PDF report).
- Referenced in deliverables: Interim PDF includes “RECONNAISSANCE.md content”; Final PDF includes “RECONNAISSANCE.md: manual Day-One analysis vs. system-generated output comparison.”

---

## References

- **Overview:** [overview.md](overview.md) — Five Day-One questions, Cartographer outputs.
- **Deliverables:** [docs/deliverables-and-rubric.md](../docs/deliverables-and-rubric.md) — Interim/final file lists, PDF report sections.
