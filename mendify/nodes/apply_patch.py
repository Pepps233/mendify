from __future__ import annotations

import fnmatch
from pathlib import Path

from loguru import logger

from mendify.config import load_config
from mendify.state import AgentState


def apply_patch(state: AgentState) -> dict:
    """Write patch files to disk, enforcing allowed_paths and path traversal protection."""
    patch: dict[str, str] = state.get("patch", {})
    repo_path = Path(state.get("repo_path", ".")).resolve()
    config = load_config(repo_path)

    if not patch:
        logger.warning("No patch to apply")
        return {}

    allowed = config.allowed_paths
    written: list[str] = []

    for rel_path, content in patch.items():
        # Path traversal protection
        target = (repo_path / rel_path).resolve()
        if not str(target).startswith(str(repo_path)):
            logger.error("Path traversal attempt blocked: {}", rel_path)
            raise ValueError(f"Patch path escapes repo root: {rel_path}")

        # Allowed-paths check
        if not any(fnmatch.fnmatch(rel_path, pattern) for pattern in allowed):
            logger.error("Path not in allowed_paths: {}", rel_path)
            raise ValueError(f"Patch path not in allowed_paths: {rel_path}")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(rel_path)
        logger.info("Patched file: {}", rel_path)

    logger.info("Applied {} file(s)", len(written))
    return {}
