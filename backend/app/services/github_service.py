"""
GitHub service: clone a repository and enumerate its source files.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterator, Tuple
from urllib.parse import urlparse

import structlog
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from app.core.config import settings
from app.parser.ast_chunker import EXT_TO_LANG

log = structlog.get_logger(__name__)

# Files / directories to skip during traversal
SKIP_DIRS = {
    ".git", ".github", "node_modules", "__pycache__", ".venv", "venv",
    ".env", "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    ".mypy_cache", ".tox", "eggs", "wheels",
}
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".lock", ".sum", ".png", ".jpg", ".jpeg", ".gif",
    ".svg", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".exe", ".bin", ".so", ".dll",
    ".class", ".jar", ".war", ".pdf", ".doc", ".docx",
}
MAX_FILE_SIZE_BYTES = 500_000  # 500 KB – skip very large files


def _repo_id_from_url(url: str) -> str:
    """Derive a deterministic repo identifier from the GitHub URL."""
    parsed = urlparse(url)
    # e.g. "/tiangolo/fastapi" → "tiangolo__fastapi"
    path = parsed.path.strip("/").replace("/", "__").replace(".git", "")
    return path


def clone_repository(repo_url: str, branch: str) -> Tuple[str, str]:
    """
    Shallow-clone *repo_url* at *branch* into a temp directory.
    Returns (local_path, repo_id).
    Raises RuntimeError on failure.
    """
    repo_id = _repo_id_from_url(repo_url)
    clone_root = Path(settings.REPO_CLONE_DIR)
    clone_root.mkdir(parents=True, exist_ok=True)
    clone_path = clone_root / repo_id

    # Remove stale clone
    if clone_path.exists():
        shutil.rmtree(clone_path)

    log.info("github.cloning", repo_url=repo_url, branch=branch, path=str(clone_path))

    clone_kwargs: dict = {
        "url": repo_url,
        "to_path": str(clone_path),
        "branch": branch,
        "depth": settings.GITHUB_CLONE_DEPTH,
        "single_branch": True,
    }

    # Inject PAT if provided
    if settings.GITHUB_TOKEN:
        parsed = urlparse(repo_url)
        auth_url = parsed._replace(
            netloc=f"{settings.GITHUB_TOKEN}@{parsed.netloc}"
        ).geturl()
        clone_kwargs["url"] = auth_url

    try:
        Repo.clone_from(**clone_kwargs)
    except GitCommandError as exc:
        raise RuntimeError(f"Failed to clone {repo_url}: {exc}") from exc

    log.info("github.cloned", repo_id=repo_id)
    return str(clone_path), repo_id


def iter_source_files(
    local_path: str,
) -> Iterator[Tuple[str, str, str]]:
    """
    Walk *local_path* and yield (relative_file_path, raw_content, language)
    for every supported source file.
    """
    root = Path(local_path)

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip directories in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            ext = filepath.suffix.lower()

            if ext in SKIP_EXTENSIONS:
                continue

            # Size guard
            try:
                if filepath.stat().st_size > MAX_FILE_SIZE_BYTES:
                    log.debug("github.skip_large", file=str(filepath))
                    continue
            except OSError:
                continue

            # Read content
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                log.warning("github.read_error", file=str(filepath), error=str(exc))
                continue

            relative = str(filepath.relative_to(root)).replace("\\", "/")
            language = EXT_TO_LANG.get(ext, ext.lstrip(".") or "text")
            yield relative, content, language


def cleanup_clone(local_path: str) -> None:
    """Remove the cloned repository directory."""
    try:
        shutil.rmtree(local_path, ignore_errors=True)
        log.debug("github.cleanup", path=local_path)
    except Exception as exc:  # noqa: BLE001
        log.warning("github.cleanup_failed", path=local_path, error=str(exc))
