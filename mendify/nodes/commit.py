from __future__ import annotations

from loguru import logger

from mendify.github_client import GitHubClient
from mendify.state import AgentState


def commit(state: AgentState) -> dict:
    """Commit and push the validated patch to the remote branch."""
    branch = state.get("head_branch", "main")
    diagnosis = state.get("diagnosis", "automated fix")
    patch: dict[str, str] = state.get("patch", {})
    patched_files = ", ".join(patch.keys()) if patch else "unknown"

    message = (
        f"fix(ci): automated patch by Mendify\n\n"
        f"Diagnosis: {diagnosis}\n"
        f"Files patched: {patched_files}\n"
        f"Applied by: Mendify autonomous agent"
    )

    logger.info("Committing fix to branch={} files={}", branch, patched_files)

    with GitHubClient() as gh:
        gh.create_commit_and_push(branch, message)

    logger.success("Corrective commit pushed to branch={}", branch)
    return {}
