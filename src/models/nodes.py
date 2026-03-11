"""Pydantic node types for the knowledge graph (ModuleNode, DatasetNode, FunctionNode, TransformationNode).

Used by the storage layer in src/graph/knowledge_graph.py. Per specs/data-model.md.
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ModuleNode(BaseModel):
    """A file or module in the codebase (structural unit)."""

    path: str = Field(..., description="File path relative to repo root")
    language: str = Field(..., description="e.g. python, sql, yaml, javascript")
    purpose_statement: Optional[str] = Field(None, description="What this module does (from code)")
    domain_cluster: Optional[str] = Field(
        None, description="Inferred domain e.g. ingestion, transformation, serving"
    )
    complexity_score: Optional[dict[str, Any] | float] = Field(
        None, description="e.g. cyclomatic complexity, LOC, comment ratio"
    )
    change_velocity_30d: Optional[float] = Field(
        None, description="Change frequency from git log --follow (e.g. commits per day)"
    )
    is_dead_code_candidate: bool = Field(
        False, description="True if exported symbols have no import references"
    )
    last_modified: Optional[datetime | str] = Field(
        None, description="Last modification time from git or filesystem"
    )


class DatasetNode(BaseModel):
    """A dataset, table, file, stream, or API-backed data asset."""

    name: str = Field(..., description="Table name, path, stream name, etc.")
    storage_type: Literal["table", "file", "stream", "api"] = Field(
        ..., description="table | file | stream | api"
    )
    schema_snapshot: Optional[str | dict[str, Any]] = Field(
        None, description="Optional schema or column summary"
    )
    freshness_sla: Optional[str] = Field(None, description="Freshness / SLA description")
    owner: Optional[str] = Field(None, description="Owner or team")
    is_source_of_truth: bool = Field(
        False, description="Whether this is a source-of-truth asset"
    )


class FunctionNode(BaseModel):
    """A function or callable within a module."""

    qualified_name: str = Field(..., description="e.g. module.path.function_name")
    parent_module: str = Field(..., description="Path of the containing module")
    signature: Optional[str] = Field(None, description="Function signature (args, return type)")
    purpose_statement: Optional[str] = Field(None, description="What the function does")
    call_count_within_repo: int = Field(
        0, description="Number of call sites found within the repo"
    )
    is_public_api: bool = Field(
        True, description="True if public API (e.g. no leading underscore)"
    )


class TransformationNode(BaseModel):
    """A transformation step in the data pipeline (connects datasets)."""

    source_datasets: list[str] = Field(
        default_factory=list, description="Upstream dataset identifiers"
    )
    target_datasets: list[str] = Field(
        default_factory=list, description="Downstream dataset identifiers"
    )
    transformation_type: str = Field(
        ..., description="e.g. sql, python, dbt, airflow_task"
    )
    source_file: str = Field(..., description="File where the transformation is defined")
    line_range: tuple[int, int] = Field(
        ..., description="(start_line, end_line) in source_file"
    )
    sql_query_if_applicable: Optional[str] = Field(
        None, description="Optional SQL text for SQL-based transformations"
    )
