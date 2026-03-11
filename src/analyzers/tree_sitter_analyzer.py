"""Multi-language AST parsing with tree-sitter: loads grammars for Python, YAML, JavaScript/TypeScript; routes by file extension; extracts imports, function defs, class defs from AST (no regex). Used by Surveyor and Hydrologist. Per specs/analyzers.md."""
import logging
from pathlib import Path
from typing import Any, Optional

import tree_sitter_python
from tree_sitter import Language, Node, Parser, Tree

logger = logging.getLogger(__name__)

def _load_lang(loader: Any) -> Any:
    """Call .language() if callable (py-tree-sitter 0.25+); wrap capsule in Language if needed."""
    raw = loader() if callable(loader) else loader
    # py-tree-sitter 0.25 returns a PyCapsule; Parser expects tree_sitter.Language
    if isinstance(raw, Language):
        return raw
    return Language(raw)


# Supported extensions -> tree-sitter Language.
_EXTENSION_TO_LANGUAGE: dict[str, Any] = {}
try:
    _EXTENSION_TO_LANGUAGE[".py"] = _load_lang(tree_sitter_python.language)
except Exception as e:
    logger.warning("tree_sitter_python not available: %s", e)
try:
    import tree_sitter_yaml
    _EXTENSION_TO_LANGUAGE[".yml"] = _load_lang(tree_sitter_yaml.language)
    _EXTENSION_TO_LANGUAGE[".yaml"] = _load_lang(tree_sitter_yaml.language)
except Exception as e:
    logger.debug("tree_sitter_yaml not available: %s", e)
try:
    import tree_sitter_javascript
    _EXTENSION_TO_LANGUAGE[".js"] = _load_lang(tree_sitter_javascript.language)
    _EXTENSION_TO_LANGUAGE[".ts"] = _load_lang(tree_sitter_javascript.language)
    _EXTENSION_TO_LANGUAGE[".tsx"] = _load_lang(tree_sitter_javascript.language)
except Exception as e:
    logger.debug("tree_sitter_javascript not available: %s", e)


def get_language_for_path(file_path: str | Path) -> Optional[Any]:
    """Return the tree-sitter Language for the file, or None if unsupported (LanguageRouter)."""
    path = Path(file_path)
    ext = path.suffix.lower()
    return _EXTENSION_TO_LANGUAGE.get(ext)


def get_language_for_extension(ext: str) -> Optional[Any]:
    """Return the tree-sitter Language for the given extension (e.g. '.py')."""
    if not ext.startswith("."):
        ext = "." + ext
    return _EXTENSION_TO_LANGUAGE.get(ext.lower())


def parse_file(
    repo_root: str | Path,
    file_path: str | Path,
    source_bytes: Optional[bytes] = None,
) -> Optional[Tree]:
    """Parse a file and return the tree, or None if unsupported / parse error."""
    path = Path(file_path)
    lang = get_language_for_path(path)
    if lang is None:
        logger.debug("No grammar for extension: %s", path.suffix)
        return None
    if source_bytes is None:
        full_path = Path(repo_root) / path
        try:
            source_bytes = full_path.read_bytes()
        except OSError as e:
            logger.warning("Could not read %s: %s", full_path, e)
            return None
    parser = Parser(lang)
    try:
        tree = parser.parse(source_bytes)
    except Exception as e:
        logger.warning("Parse error for %s: %s", file_path, e)
        return None
    return tree


def _get_text(source: bytes, node: Node) -> str:
    """Extract substring for node from source (UTF-8)."""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def extract_python_imports(source: bytes, tree: Tree, file_path: str) -> list[tuple[str, str]]:
    """Extract (importer_path, imported_path) for Python. importer_path = file_path normalized."""
    results: list[tuple[str, str]] = []
    root = tree.root_node
    if root is None:
        return results
    importer = file_path.replace("\\", "/")

    def walk(n: Node) -> None:
        if n.type == "import_statement":
            # import foo.bar -> (importer, foo.bar)
            for child in n.children:
                if child.type == "dotted_name":
                    name = _get_text(source, child).strip()
                    if name:
                        results.append((importer, name))
            return
        if n.type == "import_from_statement":
            # from foo.bar import ... -> (importer, foo.bar)
            module_name: Optional[str] = None
            for child in n.children:
                if child.type == "dotted_name":
                    module_name = _get_text(source, child).strip()
                    break
            if module_name:
                results.append((importer, module_name))
            return
        for child in n.children:
            walk(child)

    walk(root)
    return results


def _is_public_name(name: str) -> bool:
    """True if name is considered public (no leading underscore)."""
    return bool(name) and not name.lstrip("_").startswith("_") and not name.startswith("_")


def extract_python_functions_and_classes(
    source: bytes, tree: Tree, file_path: str
) -> list[dict[str, Any]]:
    """Extract public functions and classes: name, signature (optional), line_range. For ModuleNode/FunctionNode."""
    results: list[dict[str, Any]] = []
    root = tree.root_node
    if root is None:
        return results
    parent_module = file_path.replace("\\", "/")

    def walk(n: Node) -> None:
        if n.type == "function_definition":
            name_node = n.child_by_field_name("name")
            if name_node:
                name = _get_text(source, name_node)
                if _is_public_name(name):
                    params = n.child_by_field_name("parameters")
                    sig = _get_text(source, params) if params else None
                    results.append({
                        "name": name,
                        "signature": sig,
                        "line_range": (n.start_point[0] + 1, n.end_point[0] + 1),
                        "parent_module": parent_module,
                        "kind": "function",
                    })
            return
        if n.type == "class_definition":
            name_node = n.child_by_field_name("name")
            if name_node:
                name = _get_text(source, name_node)
                if _is_public_name(name):
                    bases = []
                    base_list = n.child_by_field_name("superclasses")
                    if base_list:
                        for c in base_list.children:
                            if c.type != ",":
                                bases.append(_get_text(source, c))
                    results.append({
                        "name": name,
                        "signature": None,
                        "line_range": (n.start_point[0] + 1, n.end_point[0] + 1),
                        "parent_module": parent_module,
                        "kind": "class",
                        "base_classes": bases,
                    })
            return
        for child in n.children:
            walk(child)

    walk(root)
    return results


def extract_js_imports(source: bytes, tree: Tree, file_path: str) -> list[tuple[str, str]]:
    """Extract (importer_path, imported_module_specifier) for JavaScript/TypeScript from AST.
    Handles ES6 import (import_statement with source) and require() call_expression.
    """
    results: list[tuple[str, str]] = []
    root = tree.root_node
    if root is None:
        return results
    importer = file_path.replace("\\", "/")

    def walk(n: Node) -> None:
        # ES6: import x from 'path' / import 'path' — node type is often "import_statement" with "source" (string)
        if n.type in ("import_statement", "import_declaration"):
            source_node = n.child_by_field_name("source")
            if source_node:
                spec = _get_text(source, source_node).strip().strip("'\"").strip()
                if spec:
                    results.append((importer, spec))
            return
        # require('path') — call_expression with function "require" and first arg string
        if n.type == "call_expression":
            fn = n.child_by_field_name("function")
            if fn and _get_text(source, fn).strip() == "require":
                args = n.child_by_field_name("arguments")
                if args and args.child_count >= 1:
                    first_arg = args.child(1)  # 0 is often "(", 1 is first argument
                    if first_arg and first_arg.type == "string":
                        spec = _get_text(source, first_arg).strip().strip("'\"").strip()
                        if spec:
                            results.append((importer, spec))
            return
        for child in n.children:
            walk(child)

    walk(root)
    return results


def analyze_module(
    repo_root: str | Path,
    file_path: str | Path,
    source_bytes: Optional[bytes] = None,
) -> dict[str, Any]:
    """Analyze a single file: imports, public functions, classes. Returns a dict suitable for building ModuleNode/FunctionNode/IMPORTS.
    On parse failure or unsupported language, returns empty/partial result and logs.
    """
    path = Path(file_path)
    lang = get_language_for_path(path)
    if lang is None:
        return {"imports": [], "functions": [], "classes": [], "complexity": None, "language": path.suffix or "unknown"}

    tree = parse_file(repo_root, path, source_bytes)
    if tree is None:
        return {"imports": [], "functions": [], "classes": [], "complexity": None, "language": path.suffix or "unknown"}

    if source_bytes is None:
        full_path = Path(repo_root) / path
        try:
            source_bytes = full_path.read_bytes()
        except OSError:
            source_bytes = b""

    file_path_str = str(path).replace("\\", "/")
    ext = path.suffix.lower()
    out: dict[str, Any] = {"imports": [], "functions": [], "classes": [], "complexity": None, "language": ext or "unknown"}

    if ext == ".py":
        out["language"] = "python"
        out["imports"] = extract_python_imports(source_bytes, tree, file_path_str)
        funcs_and_classes = extract_python_functions_and_classes(source_bytes, tree, file_path_str)
        out["functions"] = [x for x in funcs_and_classes if x.get("kind") == "function"]
        out["classes"] = [x for x in funcs_and_classes if x.get("kind") == "class"]
        out["complexity"] = {"lines": source_bytes.count(b"\n") + (1 if source_bytes else 0)}
    elif ext in (".js", ".ts", ".tsx"):
        out["imports"] = extract_js_imports(source_bytes, tree, file_path_str)
        out["language"] = "javascript" if ext == ".js" else "typescript"

    return out
