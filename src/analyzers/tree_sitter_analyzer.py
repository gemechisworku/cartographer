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


def extract_python_data_flow(
    source: bytes, tree: Tree, file_path: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Extract data flow from Python AST: pandas read_*/to_*, SQLAlchemy execute/text, PySpark read/write.
    Returns (transformations, dynamic_refs_log).
    Each transformation: {sources or targets: list[str], source_file, line_range, transformation_type, dynamic_refs}.
    Unresolved (variable/f-string) refs are logged in dynamic_refs_log and not emitted as concrete datasets.
    """
    transformations: list[dict[str, Any]] = []
    dynamic_refs_log: list[str] = []
    root = tree.root_node
    if root is None:
        return transformations, dynamic_refs_log
    path_n = file_path.replace("\\", "/")

    def get_call_name(n: Node) -> Optional[str]:
        """Return qualified name for call (e.g. 'read_csv', 'pd.read_csv', 'df.to_parquet')."""
        if n.type == "attribute":
            obj = n.child_by_field_name("object")
            attr = n.child_by_field_name("attribute")
            if obj and attr:
                sub = get_call_name(obj)
                name = _get_text(source, attr).strip()
                return f"{sub}.{name}" if sub else name
            return None
        if n.type == "identifier":
            return _get_text(source, n).strip()
        return None

    def _collect_strings_from_node(n: Node) -> list[str]:
        """Recursively collect string literal text from a node (argument_list may nest argument -> string)."""
        out: list[str] = []
        if n.type in ("string", "concatenated_string"):
            s = _get_text(source, n).strip().strip("'\"").strip()
            if s:
                out.append(s)
            return out
        for c in n.children:
            out.extend(_collect_strings_from_node(c))
        return out

    def get_string_arg(args_node: Node, idx: int = 0) -> Optional[str]:
        """First string literal argument, or None. Logs dynamic if not literal."""
        if not args_node or args_node.type != "argument_list":
            return None
        strings = _collect_strings_from_node(args_node)
        if idx < len(strings):
            return strings[idx]
        return None

    def get_first_string_or_keyword(args_node: Node, keywords: set[str]) -> Optional[str]:
        """First positional string or first matching keyword string. Handles nested argument nodes."""
        if not args_node or args_node.type != "argument_list":
            return None
        for c in args_node.children:
            if c.type == "keyword_argument":
                name = c.child_by_field_name("name")
                if name and _get_text(source, name).strip().rstrip("=") in keywords:
                    val = c.child_by_field_name("value")
                    if val:
                        strs = _collect_strings_from_node(val)
                        if strs:
                            return strs[0]
                        dynamic_refs_log.append(f"{path_n}: dynamic ref in keyword -> {_get_text(source, val).strip()[:60]}")
                    return None
        all_strings = _collect_strings_from_node(args_node)
        return all_strings[0] if all_strings else None

    READ_PATTERNS = ("read_csv", "read_parquet", "read_sql", "read_table", "read_json", "read_excel")
    WRITE_PATTERNS = ("to_csv", "to_parquet", "to_sql", "to_json", "to_excel")
    PANDAS_READ = {"pd.read_csv", "pd.read_parquet", "pandas.read_csv", "pandas.read_parquet"}
    PANDAS_WRITE = {"df.to_csv", "df.to_parquet", "dataframe.to_csv"}

    def walk(n: Node) -> None:
        # tree-sitter-python uses "call"; other grammars may use "call_expression"
        if n.type not in ("call", "call_expression"):
            for child in n.children:
                walk(child)
            return
        fn = n.child_by_field_name("function")
        args = n.child_by_field_name("arguments")
        if not fn or not args:
            for child in n.children:
                walk(child)
            return
        name = get_call_name(fn)
        if not name:
            for child in n.children:
                walk(child)
            return
        # Normalize: last part for pandas-style
        parts = name.split(".")
        last = parts[-1].lower() if parts else ""
        line_range = (n.start_point[0] + 1, n.end_point[0] + 1)

        # pandas read_* (do not return: walk children to find nested calls)
        if last in READ_PATTERNS:
            path_arg = get_first_string_or_keyword(args, {"filepath_or_buffer", "path", "path_or_buf", "name"}) or get_string_arg(args, 0)
            if path_arg:
                transformations.append({
                    "sources": [path_arg],
                    "targets": [],
                    "source_file": path_n,
                    "line_range": line_range,
                    "transformation_type": "python_pandas",
                })
        elif last in WRITE_PATTERNS:
            path_arg = get_first_string_or_keyword(args, {"path_or_buf", "path", "name"}) or get_string_arg(args, 0)
            if path_arg:
                transformations.append({
                    "sources": [],
                    "targets": [path_arg],
                    "source_file": path_n,
                    "line_range": line_range,
                    "transformation_type": "python_pandas",
                })
        elif "execute" in last or last == "text":
            s = get_string_arg(args, 0)
            if s and ("select" in s.lower() or "from" in s.lower() or "insert" in s.lower()):
                transformations.append({
                    "sources": [],
                    "targets": [f"sql:{path_n}:{line_range[0]}"],
                    "source_file": path_n,
                    "line_range": line_range,
                    "transformation_type": "python_sqlalchemy",
                })
        elif "read" in name.lower() and ("csv" in last or "parquet" in last or "json" in last):
            path_arg = get_first_string_or_keyword(args, {"path"}) or get_string_arg(args, 0)
            if path_arg:
                transformations.append({
                    "sources": [path_arg],
                    "targets": [],
                    "source_file": path_n,
                    "line_range": line_range,
                    "transformation_type": "python_pyspark",
                })
        elif "write" in name.lower() and ("parquet" in last or "csv" in last or "save" in last):
            path_arg = get_first_string_or_keyword(args, {"path"}) or get_string_arg(args, 0)
            if path_arg:
                transformations.append({
                    "sources": [],
                    "targets": [path_arg],
                    "source_file": path_n,
                    "line_range": line_range,
                    "transformation_type": "python_pyspark",
                })
        for child in n.children:
            walk(child)

    walk(root)
    return transformations, dynamic_refs_log


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
