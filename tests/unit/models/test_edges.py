"""Tests for knowledge graph edge types (specs/data-model.md)."""

import pytest

from src.models.edges import EdgeType, EdgePayload


class TestEdgeType:
    """EdgeType enum: IMPORTS, PRODUCES, CONSUMES, CALLS, CONFIGURES."""

    def test_all_types_defined(self):
        assert EdgeType.IMPORTS.value == "IMPORTS"
        assert EdgeType.PRODUCES.value == "PRODUCES"
        assert EdgeType.CONSUMES.value == "CONSUMES"
        assert EdgeType.CALLS.value == "CALLS"
        assert EdgeType.CONFIGURES.value == "CONFIGURES"

    def test_from_string(self):
        assert EdgeType("IMPORTS") is EdgeType.IMPORTS
        assert EdgeType("PRODUCES") is EdgeType.PRODUCES


class TestEdgePayload:
    """EdgePayload: optional weight and extra attributes."""

    def test_empty_valid(self):
        payload = EdgePayload()
        assert payload.weight is None
        assert payload.extra is None

    def test_with_weight(self):
        payload = EdgePayload(weight=3.0)
        assert payload.weight == 3.0

    def test_with_extra(self):
        payload = EdgePayload(extra={"source_file": "src/foo.py", "line": 10})
        assert payload.extra["source_file"] == "src/foo.py"
        assert payload.extra["line"] == 10

    def test_serialization_roundtrip(self):
        payload = EdgePayload(weight=2, extra={"key": "value"})
        data = payload.model_dump()
        restored = EdgePayload.model_validate(data)
        assert restored.weight == payload.weight
        assert restored.extra == payload.extra
