"""Extract table-level dependencies from SQL using sqlglot.

Per specs/analyzers.md. Feeds DatasetNode, TransformationNode, CONSUMES, PRODUCES.
"""
import logging
from typing import Any, Literal, Optional

import sqlglot
from sqlglot import exp
from sqlglot.dialects import BigQuery, DuckDB, Postgres, Snowflake

logger = logging.getLogger(__name__)

DialectHint = Literal["postgres", "bigquery", "snowflake", "duckdb"]
DIALECT_MAP = {
    "postgres": Postgres,
    "bigquery": BigQuery,
    "snowflake": Snowflake,
    "duckdb": DuckDB,
}


def _tables_from_expression(expression: exp.Expression, dialect: Any = None) -> list[str]:
    """Collect table names from FROM/JOIN/table in an expression."""
    tables: list[str] = []
    d = dialect or "ansi"
    for table in expression.find_all(exp.Table):
        name = table.sql(dialect=d)
        if name:
            tables.append(name)
    return tables


def _write_target(expression: exp.Expression, dialect: Any = "ansi") -> Optional[str]:
    """Return the write target table for INSERT/UPDATE/MERGE/CREATE TABLE AS."""
    if isinstance(expression, exp.Insert):
        t = expression.this
        if isinstance(t, exp.Table):
            return t.sql(dialect=dialect)
    if isinstance(expression, exp.Merge):
        t = expression.this
        if isinstance(t, exp.Table):
            return t.sql(dialect=dialect)
    if isinstance(expression, exp.Create):
        if expression.expression and isinstance(expression.this, exp.Schema):
            # CREATE TABLE x AS SELECT ...
            return expression.this.this if hasattr(expression.this, "this") else None
        if isinstance(expression.this, exp.Table):
            return expression.this.sql(dialect=dialect)
    if isinstance(expression, exp.Update):
        t = expression.this
        if isinstance(t, exp.Table):
            return t.sql(dialect=dialect)
    return None


def extract_table_dependencies(
    source_sql: str,
    file_path: str = "",
    dialect: Optional[DialectHint] = None,
) -> list[dict[str, Any]]:
    """Extract table dependencies from SQL string.
    Returns list of dicts: source_tables, target_tables, source_file, line_range, sql_snippet.
    For SELECT-only (no write), target_tables may be empty; source_tables are FROM/JOIN/WITH.
    """
    results: list[dict[str, Any]] = []
    sql_dialect = DIALECT_MAP.get(dialect or "postgres", Postgres)
    try:
        parsed = sqlglot.parse(source_sql, dialect=sql_dialect)
    except Exception as e:
        logger.warning("SQL parse error in %s: %s", file_path or "<string>", e)
        return results

    if not parsed:
        return results

    for i, statement in enumerate(parsed):
        try:
            source_tables = _tables_from_expression(statement, sql_dialect)
            target = _write_target(statement, sql_dialect)
            target_tables = [target] if target else []
            # For SELECT-only (e.g. dbt model that refs others), we still have source_tables; target can be inferred from context (e.g. filename) by caller
            start_line = getattr(statement, "start_line", None) or 1
            end_line = getattr(statement, "end_line", None) or start_line
            results.append({
                "source_tables": list(dict.fromkeys(source_tables)),
                "target_tables": target_tables,
                "source_file": file_path,
                "line_range": (start_line, end_line),
                "sql_snippet": statement.sql(dialect=sql_dialect)[:2000] if statement else None,
            })
        except Exception as e:
            logger.warning("Error extracting deps from statement %s in %s: %s", i, file_path, e)
    return results


def extract_lineage_from_file(
    repo_root: str,
    file_path: str,
    source_text: Optional[str] = None,
    dialect: Optional[DialectHint] = None,
) -> list[dict[str, Any]]:
    """Read SQL from file (or use source_text) and return dependency list. Log and return [] on error."""
    from pathlib import Path
    path = Path(repo_root) / file_path
    if source_text is None:
        try:
            source_text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("Could not read %s: %s", path, e)
            return []
    return extract_table_dependencies(source_text, file_path=str(file_path), dialect=dialect)
