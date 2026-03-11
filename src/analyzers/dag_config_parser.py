"""Extract pipeline topology from Airflow DAG (Python) and dbt schema.yml.

Per specs/analyzers.md. Feeds CONFIGURES; upstream/downstream for lineage.
"""
import logging
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def parse_dbt_schema_yml(content: str, file_path: str = "") -> dict[str, Any]:
    """Parse dbt schema.yml (or similar) for model names and dependencies.
    Returns: topology list of (upstream, downstream), config_file, models list.
    """
    import yaml  # optional: add pyyaml to deps if not present
    try:
        data = yaml.safe_load(content)
    except Exception as e:
        logger.warning("YAML parse error in %s: %s", file_path, e)
        return {"topology": [], "config_file": file_path, "models": [], "sources": []}

    if not data:
        return {"topology": [], "config_file": file_path, "models": [], "sources": []}

    topology: list[tuple[str, str]] = []
    models: list[str] = []
    sources: list[str] = []

    # dbt schema: models can be a list of dicts with name, columns, or version + models
    if isinstance(data.get("models"), list):
        for item in data["models"]:
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    models.append(name)
                # dep refs in columns or tests
                for ref in _yaml_refs(item):
                    topology.append((ref, name or "unknown"))
    if isinstance(data.get("sources"), list):
        for item in data["sources"]:
            if isinstance(item, dict):
                n = item.get("name")
                if n:
                    sources.append(n)

    return {"topology": topology, "config_file": file_path, "models": models, "sources": sources}


def _yaml_refs(item: dict) -> list[str]:
    """Heuristic: pull ref-like names from a dbt model/source block."""
    refs: list[str] = []
    for v in item.values():
        if isinstance(v, str) and ("ref(" in v or "source(" in v):
            for m in re.findall(r"ref\s*\(\s*['\"]?([^'\")\s]+)", v):
                refs.append(m)
            for m in re.findall(r"source\s*\(\s*['\"]?([^'\")\s]+)", v):
                refs.append(m)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, dict):
                    refs.extend(_yaml_refs(x))
    return refs


def parse_airflow_dag_python(content: str, file_path: str = "") -> dict[str, Any]:
    """Parse Airflow DAG Python file for task IDs and dependencies (>> / set_downstream).
    Returns: topology list of (upstream_task, downstream_task), config_file, task_ids.
    """
    topology: list[tuple[str, str]] = []
    task_ids: list[str] = []
    # Heuristic: find task_id= or .set_downstream( or >> operator usage
    task_id_re = re.compile(r'task_id\s*=\s*["\']([^"\']+)["\']')
    for m in task_id_re.finditer(content):
        task_ids.append(m.group(1))
    # >> operator: task_a >> task_b >> task_c
    shift_re = re.compile(r"(\w+)\s*>>\s*(\w+)")
    for m in shift_re.finditer(content):
        topology.append((m.group(1), m.group(2)))
    # set_downstream / set_upstream
    set_ds = re.compile(r"\.set_downstream\s*\(\s*\[?([^\]\)]+)\]?")
    for m in set_ds.finditer(content):
        downstream = [x.strip().strip('"\'') for x in m.group(1).split(",")]
        # previous line or context might have task name; we don't have AST so skip if ambiguous
        pass
    return {"topology": topology, "config_file": file_path, "task_ids": task_ids}


def analyze_dag_config(
    repo_root: str | Path,
    file_path: str | Path,
    content: Optional[str] = None,
) -> dict[str, Any]:
    """Dispatch by extension: .yml/.yaml -> dbt schema; .py in dags/ or containing DAG( -> Airflow.
    Returns topology, config_file, and model/task identifiers. On error, returns empty and logs.
    """
    path = Path(file_path)
    if content is None:
        full = Path(repo_root) / path
        try:
            content = full.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("Could not read %s: %s", full, e)
            return {"topology": [], "config_file": str(path), "models": [], "sources": [], "task_ids": []}

    path_str = str(path).replace("\\", "/")
    if path.suffix.lower() in (".yml", ".yaml"):
        out = parse_dbt_schema_yml(content, path_str)
        out.setdefault("task_ids", [])
        return out
    if path.suffix.lower() == ".py" and ("DAG(" in content or ">>" in content):
        out = parse_airflow_dag_python(content, path_str)
        out.setdefault("models", [])
        out.setdefault("sources", [])
        return out
    return {"topology": [], "config_file": path_str, "models": [], "sources": [], "task_ids": []}
