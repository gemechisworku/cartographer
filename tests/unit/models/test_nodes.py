"""Tests for knowledge graph node models (specs/data-model.md)."""

import pytest
from pydantic import ValidationError

from src.models.nodes import (
    DatasetNode,
    FunctionNode,
    ModuleNode,
    TransformationNode,
)


class TestModuleNode:
    """ModuleNode: path, language, optional fields."""

    def test_minimal_valid(self):
        node = ModuleNode(path="src/foo.py", language="python")
        assert node.path == "src/foo.py"
        assert node.language == "python"
        assert node.purpose_statement is None
        assert node.is_dead_code_candidate is False

    def test_full_valid(self):
        node = ModuleNode(
            path="src/ingestion/kafka_consumer.py",
            language="python",
            purpose_statement="Consumes events from Kafka.",
            domain_cluster="ingestion",
            complexity_score={"loc": 120, "cyclomatic": 5},
            change_velocity_30d=2.5,
            is_dead_code_candidate=False,
            last_modified="2024-01-15T10:00:00",
        )
        assert node.domain_cluster == "ingestion"
        assert node.complexity_score["loc"] == 120

    def test_path_required(self):
        with pytest.raises(ValidationError):
            ModuleNode(language="python")

    def test_language_required(self):
        with pytest.raises(ValidationError):
            ModuleNode(path="src/foo.py")


class TestDatasetNode:
    """DatasetNode: name, storage_type (table|file|stream|api), optional fields."""

    def test_minimal_valid(self):
        node = DatasetNode(name="users", storage_type="table")
        assert node.name == "users"
        assert node.storage_type == "table"
        assert node.is_source_of_truth is False

    def test_storage_types(self):
        for st in ("table", "file", "stream", "api"):
            node = DatasetNode(name="x", storage_type=st)
            assert node.storage_type == st

    def test_invalid_storage_type(self):
        with pytest.raises(ValidationError):
            DatasetNode(name="x", storage_type="unknown")

    def test_full_valid(self):
        node = DatasetNode(
            name="daily_active_users",
            storage_type="table",
            schema_snapshot="id, date, count",
            freshness_sla="T+1",
            owner="analytics",
            is_source_of_truth=True,
        )
        assert node.is_source_of_truth is True


class TestFunctionNode:
    """FunctionNode: qualified_name, parent_module, optional signature, etc."""

    def test_minimal_valid(self):
        node = FunctionNode(
            qualified_name="src.foo.bar",
            parent_module="src/foo.py",
        )
        assert node.qualified_name == "src.foo.bar"
        assert node.call_count_within_repo == 0
        assert node.is_public_api is True

    def test_with_signature_and_purpose(self):
        node = FunctionNode(
            qualified_name="src.transforms.revenue.calculate",
            parent_module="src/transforms/revenue.py",
            signature="(amount: float, tax: float) -> float",
            purpose_statement="Computes revenue after tax.",
            call_count_within_repo=3,
            is_public_api=True,
        )
        assert node.signature == "(amount: float, tax: float) -> float"
        assert node.call_count_within_repo == 3


class TestTransformationNode:
    """TransformationNode: source/target datasets, type, source_file, line_range."""

    def test_minimal_valid(self):
        node = TransformationNode(
            source_datasets=["raw_events"],
            target_datasets=["events_daily"],
            transformation_type="sql",
            source_file="models/events_daily.sql",
            line_range=(1, 42),
        )
        assert node.source_datasets == ["raw_events"]
        assert node.target_datasets == ["events_daily"]
        assert node.line_range == (1, 42)
        assert node.sql_query_if_applicable is None

    def test_empty_datasets_allowed(self):
        node = TransformationNode(
            source_datasets=[],
            target_datasets=[],
            transformation_type="airflow_task",
            source_file="dags/pipe.py",
            line_range=(10, 15),
        )
        assert node.source_datasets == []
        assert node.transformation_type == "airflow_task"

    def test_sql_query_optional(self):
        node = TransformationNode(
            source_datasets=["a"],
            target_datasets=["b"],
            transformation_type="dbt",
            source_file="models/b.sql",
            line_range=(1, 20),
            sql_query_if_applicable="SELECT * FROM {{ ref('a') }}",
        )
        assert "ref('a')" in (node.sql_query_if_applicable or "")
