"""Pydantic edge types for the knowledge graph (EdgeType, EdgePayload).

Used by the storage layer in src/graph/knowledge_graph.py. Per specs/data-model.md.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EdgeType(str, Enum):
    """Directed edge types in the knowledge graph."""

    IMPORTS = "IMPORTS"  # source_module → target_module
    PRODUCES = "PRODUCES"  # transformation → dataset
    CONSUMES = "CONSUMES"  # transformation → dataset
    CALLS = "CALLS"  # function → function
    CONFIGURES = "CONFIGURES"  # config_file → module/pipeline


class EdgePayload(BaseModel):
    """Optional metadata for graph edges (e.g. for serialization and graph APIs)."""

    weight: Optional[float] = Field(None, description="e.g. import_count for IMPORTS")
    extra: Optional[dict[str, Any]] = Field(None, description="Additional edge attributes")
