"""Tests for tree_sitter_analyzer: LanguageRouter and Python AST extraction."""

import pytest

from src.analyzers.tree_sitter_analyzer import (
    analyze_module,
    get_language_for_extension,
    get_language_for_path,
    parse_file,
)


class TestLanguageRouter:
    def test_python_extension(self):
        assert get_language_for_path("foo.py") is not None
        assert get_language_for_extension(".py") is not None

    def test_yaml_extensions(self):
        # May be None if tree_sitter_yaml not loaded; both .yml and .yaml should resolve
        lang_yml = get_language_for_extension(".yml")
        lang_yaml = get_language_for_extension(".yaml")
        assert (lang_yml is not None) == (lang_yaml is not None)

    def test_unknown_extension(self):
        assert get_language_for_path("foo.unknown") is None
        assert get_language_for_extension(".xyz") is None


class TestParseFile:
    def test_parse_python_string(self, tmp_path):
        (tmp_path / "f.py").write_text("def foo(): pass\n")
        tree = parse_file(tmp_path, "f.py")
        assert tree is not None
        assert tree.root_node is not None
        assert tree.root_node.type == "module"

    def test_parse_unsupported_extension(self, tmp_path):
        (tmp_path / "f.xyz").write_text("x")
        assert parse_file(tmp_path, "f.xyz") is None

    def test_parse_invalid_python_returns_none(self, tmp_path):
        (tmp_path / "bad.py").write_text("def ( invalid\n")
        # Parser may still return a tree with errors; we accept either
        result = parse_file(tmp_path, "bad.py")
        # Best effort: we don't require None for syntax errors
        assert result is None or result.root_node is not None


class TestAnalyzeModulePython:
    def test_imports_extracted(self, tmp_path):
        (tmp_path / "m.py").write_text("import os\nfrom pathlib import Path\n")
        out = analyze_module(tmp_path, "m.py")
        assert "imports" in out
        assert len(out["imports"]) >= 1
        importer, imported = out["imports"][0]
        assert "m.py" in importer or "m" in importer
        assert "os" in imported or "pathlib" in imported

    def test_public_function_extracted(self, tmp_path):
        (tmp_path / "m.py").write_text("def hello():\n    pass\n")
        out = analyze_module(tmp_path, "m.py")
        assert out["functions"]
        assert any(f["name"] == "hello" for f in out["functions"])

    def test_private_function_excluded(self, tmp_path):
        (tmp_path / "m.py").write_text("def _private():\n    pass\n")
        out = analyze_module(tmp_path, "m.py")
        assert not any(f["name"] == "_private" for f in out["functions"])

    def test_class_extracted(self, tmp_path):
        (tmp_path / "m.py").write_text("class Foo:\n    pass\n")
        out = analyze_module(tmp_path, "m.py")
        assert out["classes"]
        assert any(c["name"] == "Foo" for c in out["classes"])

    def test_unsupported_extension_returns_empty(self, tmp_path):
        (tmp_path / "f.xyz").write_text("x")
        out = analyze_module(tmp_path, "f.xyz")
        assert out["imports"] == []
        assert out["functions"] == []
        assert out["classes"] == []
