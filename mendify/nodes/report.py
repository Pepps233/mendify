from __future__ import annotations

from loguru import logger

from mendify.state import AgentState


def report_failure(state: AgentState) -> dict:
    """Log the failure after max retries are exhausted."""
    run_id = state.get("run_id")
    workflow_name = state.get("workflow_name", "unknown")
    iteration = state.get("iteration", 0)
    error_history: list[str] = state.get("error_history", [])
    diagnosis = state.get("diagnosis", "no diagnosis")

    logger.error(
        "Mendify failed to heal workflow={} run_id={} after {} attempts",
        workflow_name,
        run_id,
        iteration,
    )
    logger.error("Final diagnosis: {}", diagnosis)

    for i, err in enumerate(error_history):
        logger.debug("Attempt {} error:\n{}", i + 1, err)

    return {}
