"""Tests for sql_lineage: table dependency extraction via sqlglot."""

import pytest

from src.analyzers.sql_lineage import (
    extract_table_dependencies,
    extract_lineage_from_file,
)


class TestExtractTableDependencies:
    def test_select_from_single_table(self):
        deps = extract_table_dependencies("SELECT * FROM users")
        assert len(deps) == 1
        assert "users" in deps[0]["source_tables"]
        assert deps[0]["target_tables"] == []

    def test_select_join(self):
        deps = extract_table_dependencies("SELECT * FROM a JOIN b ON a.id = b.id")
        assert len(deps) == 1
        assert set(deps[0]["source_tables"]) >= {"a", "b"}

    def test_with_cte(self):
        sql = "WITH cte AS (SELECT * FROM base_table) SELECT * FROM cte"
        deps = extract_table_dependencies(sql)
        assert len(deps) >= 1
        assert "base_table" in deps[0]["source_tables"]

    def test_insert_into(self):
        deps = extract_table_dependencies("INSERT INTO dest SELECT * FROM src")
        assert len(deps) == 1
        assert "src" in deps[0]["source_tables"]
        assert "dest" in deps[0]["target_tables"]

    def test_create_table_as(self):
        sql = "CREATE TABLE new_table AS SELECT * FROM old_table"
        deps = extract_table_dependencies(sql)
        assert len(deps) >= 1
        assert any("old_table" in d["source_tables"] for d in deps)

    def test_invalid_sql_returns_empty(self):
        deps = extract_table_dependencies("NOT VALID SQL {{{")
        assert deps == []

    def test_dialect_postgres(self):
        deps = extract_table_dependencies("SELECT * FROM users", dialect="postgres")
        assert len(deps) == 1

    def test_dialect_bigquery(self):
        deps = extract_table_dependencies("SELECT * FROM `project.dataset.table`", dialect="bigquery")
        assert len(deps) >= 1


class TestExtractLineageFromFile:
    def test_reads_file(self, tmp_path):
        (tmp_path / "q.sql").write_text("SELECT * FROM t1 JOIN t2 ON t1.id = t2.id")
        deps = extract_lineage_from_file(str(tmp_path), "q.sql")
        assert len(deps) >= 1
        assert deps[0]["source_file"] == "q.sql"

    def test_missing_file_returns_empty(self, tmp_path):
        deps = extract_lineage_from_file(str(tmp_path), "nonexistent.sql")
        assert deps == []
