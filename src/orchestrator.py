"""Orchestrator: wire Surveyor -> Hydrologist, build knowledge graph, write .cartography/ artifacts.

Interim: Surveyor + Hydrologist only; writes module_graph.json and lineage_graph.json.
"""
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from src.agents.hydrologist import run_hydrologist
from src.agents.surveyor import run_surveyor
from src.graph.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)


def _clone_repo(url: str, target_dir: Path) -> bool:
    """Clone url into target_dir. Return True on success."""
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(target_dir)],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error("git clone failed: %s", e)
        return False


def resolve_repo_path(path_or_url: str) -> Path | None:
    """If path_or_url is a GitHub URL, clone to temp dir and return that path. Else return Path if directory exists."""
    if path_or_url.startswith(("http://", "https://", "git@")):
        parsed = urlparse(path_or_url)
        if "github" in (parsed.netloc or ""):
            tmp = tempfile.mkdtemp(prefix="cartographer_")
            if _clone_repo(path_or_url, Path(tmp)):
                return Path(tmp)
            shutil.rmtree(tmp, ignore_errors=True)
            return None
        logger.warning("Only GitHub URLs supported for clone")
        return None
    p = Path(path_or_url).resolve()
    if p.is_dir():
        return p
    logger.error("Not a directory: %s", p)
    return None


def run_analysis(
    repo_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    days_velocity: int = 30,
    sql_dialect: str = "postgres",
) -> KnowledgeGraph:
    """Run Surveyor then Hydrologist; write module_graph.json and lineage_graph.json to output_dir (default repo_path/.cartography)."""
    repo_path = Path(repo_path)
    if not repo_path.is_dir():
        raise NotADirectoryError(str(repo_path))
    out = Path(output_dir) if output_dir else repo_path / ".cartography"
    out.mkdir(parents=True, exist_ok=True)

    kg = KnowledgeGraph()
    run_surveyor(repo_path, kg, days_velocity=days_velocity)
    run_hydrologist(repo_path, kg, sql_dialect=sql_dialect)

    kg.write_module_graph_json(out / "module_graph.json")
    kg.write_lineage_graph_json(out / "lineage_graph.json")
    return kg
