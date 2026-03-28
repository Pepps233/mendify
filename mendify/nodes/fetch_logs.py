from __future__ import annotations

from loguru import logger

from mendify.github_client import GitHubClient
from mendify.state import AgentState


def fetch_logs(state: AgentState) -> dict:
    """Download CI failure logs from GitHub Actions and populate state."""
    run_id = state.get("run_id")
    if run_id is None:
        raise ValueError("run_id is required in state before fetch_logs")

    logger.info("Fetching logs for workflow run_id={}", run_id)

    with GitHubClient() as gh:
        failure = gh.get_failed_workflow_run(run_id)

    logger.info(
        "Fetched logs workflow={} branch={} sha={}",
        failure.workflow_name,
        failure.head_branch,
        failure.head_sha[:8],
    )

    return {
        "build_logs": failure.logs,
        "head_sha": failure.head_sha,
        "head_branch": failure.head_branch,
        "workflow_name": failure.workflow_name,
    }
