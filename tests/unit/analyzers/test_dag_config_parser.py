"""Tests for dag_config_parser: dbt schema.yml and Airflow DAG parsing."""

import pytest

from src.analyzers.dag_config_parser import (
    analyze_dag_config,
    parse_dbt_schema_yml,
    parse_airflow_dag_python,
)


class TestParseDbtSchemaYml:
    def test_models_list(self):
        yml = """
models:
  - name: my_model
    columns:
      - name: id
  - name: other_model
"""
        out = parse_dbt_schema_yml(yml)
        assert out["config_file"] == ""
        assert "my_model" in out["models"]
        assert "other_model" in out["models"]

    def test_empty_returns_empty(self):
        out = parse_dbt_schema_yml("")
        assert out["topology"] == []
        assert out["models"] == []

    def test_invalid_yaml_returns_empty(self):
        out = parse_dbt_schema_yml("not: valid: yaml: [")
        assert out["topology"] == []
        assert "models" in out


class TestParseAirflowDagPython:
    def test_task_id_and_shift(self):
        code = '''
task_a = BashOperator(task_id="task_a", bash_command="echo a")
task_b = BashOperator(task_id="task_b", bash_command="echo b")
task_a >> task_b
'''
        out = parse_airflow_dag_python(code)
        assert "task_a" in out["task_ids"]
        assert "task_b" in out["task_ids"]
        assert ("task_a", "task_b") in out["topology"]

    def test_no_dag_returns_empty_topology(self):
        out = parse_airflow_dag_python("x = 1")
        assert out["topology"] == []
        assert out["task_ids"] == []


class TestAnalyzeDagConfig:
    def test_yml_dispatches_to_dbt(self, tmp_path):
        (tmp_path / "schema.yml").write_text("models:\n  - name: m1\n")
        out = analyze_dag_config(tmp_path, "schema.yml")
        assert "m1" in out["models"]
        assert out["config_file"].endswith("schema.yml")

    def test_py_with_dag_dispatches_to_airflow(self, tmp_path):
        (tmp_path / "dag.py").write_text('task_id="t1"\nt1 >> t2')
        out = analyze_dag_config(tmp_path, "dag.py")
        assert "t1" in out["task_ids"]
        assert ("t1", "t2") in out["topology"]

    def test_unknown_extension_returns_empty(self, tmp_path):
        (tmp_path / "f.txt").write_text("x")
        out = analyze_dag_config(tmp_path, "f.txt")
        assert out["topology"] == []
        assert out["models"] == []
        assert out["task_ids"] == []
