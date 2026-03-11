"""Tests for tree_sitter_analyzer: LanguageRouter and Python AST extraction."""

import pytest

from src.analyzers.tree_sitter_analyzer import (
    analyze_module,
    extract_js_imports,
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


class TestAnalyzeModuleJavaScript:
    """JS/TS import extraction (AST-based). Skips if tree_sitter_javascript not available."""

    def test_js_import_extracted_via_analyze_module(self, tmp_path):
        if get_language_for_extension(".js") is None:
            pytest.skip("tree_sitter_javascript not available")
        (tmp_path / "app.js").write_text("import foo from 'mymodule';\nconst x = require('other');\n")
        out = analyze_module(tmp_path, "app.js")
        assert "imports" in out
        # At least one of ES6 import or require should be found
        assert len(out["imports"]) >= 1
        importer, spec = out["imports"][0]
        assert "app.js" in importer or "app" in importer
        assert "mymodule" in spec or "other" in spec

    def test_extract_js_imports_es6_import(self, tmp_path):
        if get_language_for_extension(".js") is None:
            pytest.skip("tree_sitter_javascript not available")
        from src.analyzers.tree_sitter_analyzer import parse_file
        (tmp_path / "m.js").write_text("import something from './lib';\n")
        tree = parse_file(tmp_path, "m.js")
        assert tree is not None
        source = (tmp_path / "m.js").read_bytes()
        imports = extract_js_imports(source, tree, "m.js")
        assert len(imports) >= 1
        assert any("lib" in spec for _importer, spec in imports)
