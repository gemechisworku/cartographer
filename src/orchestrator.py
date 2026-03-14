"""Pipeline: sequences Surveyor, Hydrologist, Semanticist, and Archivist; writes all .cartography/ artifacts via Archivist. Supports incremental update (--incremental)."""
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from src.agents.archivist import get_changed_files, run_archivist
from src.agents.hydrologist import run_hydrologist
from src.agents.semanticist import DAY_ONE_QUESTIONS, run_semanticist
from src.agents.surveyor import run_surveyor
from src.graph.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)

LAST_RUN_COMMIT_FILE = "last_run_commit"


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


def _get_head_commit(repo_path: Path) -> str | None:
    """Return current HEAD commit hash or None if not a git repo or error."""
    if not (repo_path / ".git").is_dir():
        return None
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


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


def _write_last_run_commit(repo_path: Path, out: Path) -> None:
    """Record current HEAD so next incremental run knows since when to diff."""
    head = _get_head_commit(repo_path)
    if head:
        (out / LAST_RUN_COMMIT_FILE).write_text(head, encoding="utf-8")
        logger.debug("Wrote %s", out / LAST_RUN_COMMIT_FILE)


def run_analysis(
    repo_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    days_velocity: int = 30,
    sql_dialect: str = "postgres",
    run_semanticist_agent: bool = True,
    incremental: bool = False,
) -> KnowledgeGraph:
    """Run full or incremental analysis. When incremental=True and .cartography exists with last_run_commit,
    re-analyze only changed files and merge into existing graph.
    """
    repo_path = Path(repo_path)
    if not repo_path.is_dir():
        raise NotADirectoryError(str(repo_path))
    out = Path(output_dir) if output_dir else repo_path / ".cartography"
    out.mkdir(parents=True, exist_ok=True)

    # Try incremental path
    if incremental:
        mod_json = out / "module_graph.json"
        lin_json = out / "lineage_graph.json"
        last_run = out / LAST_RUN_COMMIT_FILE
        if mod_json.exists() and lin_json.exists() and last_run.exists():
            last_commit = last_run.read_text(encoding="utf-8").strip()
            head = _get_head_commit(repo_path)
            if head and last_commit == head:
                logger.info("Incremental: no new commits since last run. Exiting.")
                kg = KnowledgeGraph()
                kg.load_module_graph_json(mod_json)
                kg.load_lineage_graph_json(lin_json)
                return kg
            changed = get_changed_files(repo_path, last_commit)
            if not changed:
                logger.info("Incremental: no changed files since %s. Updating last_run_commit and exiting.", last_commit[:7])
                _write_last_run_commit(repo_path, out)
                kg = KnowledgeGraph()
                kg.load_module_graph_json(mod_json)
                kg.load_lineage_graph_json(lin_json)
                return kg
            logger.info("Incremental: %d changed files since %s. Re-analyzing and merging.", len(changed), last_commit[:7])
            kg = KnowledgeGraph()
            kg.load_module_graph_json(mod_json)
            kg.load_lineage_graph_json(lin_json)
            changed_set = {p.replace("\\", "/") for p in changed}
            kg.remove_modules(changed_set)
            kg.remove_lineage_transformations_by_source_files(changed_set)

            logger.info("Phase 1/4 (incremental): Surveyor - re-analyzing %d files...", len(changed))
            run_surveyor(repo_path, kg, days_velocity=days_velocity, file_list=changed)
            module_count = sum(1 for n in kg.module_graph.nodes() if kg.module_graph.nodes[n].get("path") == n)
            logger.info("Surveyor done. Module graph: %d modules.", module_count)

            logger.info("Phase 2/4 (incremental): Hydrologist - re-analyzing lineage for changed files...")
            run_hydrologist(repo_path, kg, sql_dialect=sql_dialect, file_list=changed)
            logger.info("Hydrologist done. Lineage graph: %d nodes.", kg.lineage_graph.number_of_nodes())

            if run_semanticist_agent:
                logger.info("Phase 3/4 (incremental): Semanticist - purpose for changed modules, then full cluster + Day-One...")
                day_one_answers, documentation_drift = run_semanticist(repo_path, kg, module_paths_filter=changed_set)
                logger.info("Semanticist done. Day-One answers: 5; documentation drift flagged: %d modules.", len(documentation_drift))
            else:
                day_one_answers = [{"question": q, "answer": "(Semanticist skipped)", "citations": []} for q in DAY_ONE_QUESTIONS]
                documentation_drift = []

            logger.info("Phase 4/4: Archivist - writing artifacts...")
            run_archivist(repo_path, kg, out, day_one_answers, documentation_drift)
            _write_last_run_commit(repo_path, out)
            logger.info("Incremental run done.")
            return kg
        logger.info("Incremental requested but no prior run found (missing %s or graphs). Doing full analysis.", LAST_RUN_COMMIT_FILE)

    # Full run
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
    _write_last_run_commit(repo_path, out)
    logger.info("Done. Outputs: CODEBASE.md, onboarding_brief.md, module_graph.json, lineage_graph.json, semantic_index/, cartography_trace.jsonl, day_one_answers.json, documentation_drift.json.")
    return kg
