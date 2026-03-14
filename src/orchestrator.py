"""Pipeline: sequences Surveyor, Hydrologist, Semanticist, and Archivist; writes all .cartography/ artifacts via Archivist. CLI accepts repo path."""
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from src.agents.archivist import run_archivist
from src.agents.hydrologist import run_hydrologist
from src.agents.semanticist import DAY_ONE_QUESTIONS, run_semanticist
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
    run_semanticist_agent: bool = True,
) -> KnowledgeGraph:
    """Run Surveyor, Hydrologist, and (optionally) Semanticist; write artifacts to output_dir (default repo_path/.cartography)."""
    repo_path = Path(repo_path)
    if not repo_path.is_dir():
        raise NotADirectoryError(str(repo_path))
    out = Path(output_dir) if output_dir else repo_path / ".cartography"
    out.mkdir(parents=True, exist_ok=True)

    kg = KnowledgeGraph()

    logger.info("Phase 1/4: Surveyor - building module graph (imports, PageRank, git velocity)...")
    run_surveyor(repo_path, kg, days_velocity=days_velocity)
    module_count = sum(1 for n in kg.module_graph.nodes() if kg.module_graph.nodes[n].get("path") == n)
    logger.info("Surveyor done. Module graph: %d modules.", module_count)

    logger.info("Phase 2/4: Hydrologist - building data lineage (SQL, DAG config)...")
    run_hydrologist(repo_path, kg, sql_dialect=sql_dialect)
    logger.info("Hydrologist done. Lineage graph: %d nodes.", kg.lineage_graph.number_of_nodes())

    if run_semanticist_agent:
        logger.info("Phase 3/4: Semanticist - purpose statements, domain clustering, Day-One answers...")
        day_one_answers, documentation_drift = run_semanticist(repo_path, kg)
        logger.info("Semanticist done. Day-One answers: 5; documentation drift flagged: %d modules.", len(documentation_drift))
    else:
        day_one_answers = [{"question": q, "answer": "(Semanticist skipped)", "citations": []} for q in DAY_ONE_QUESTIONS]
        documentation_drift = []

    logger.info("Phase 4/4: Archivist - writing all .cartography/ artifacts...")
    run_archivist(repo_path, kg, out, day_one_answers, documentation_drift)
    logger.info("Done. Outputs: CODEBASE.md, onboarding_brief.md, module_graph.json, lineage_graph.json, semantic_index/, cartography_trace.jsonl, day_one_answers.json, documentation_drift.json.")
    return kg
