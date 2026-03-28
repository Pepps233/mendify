from __future__ import annotations

from pathlib import Path

from loguru import logger

from mendify.config import load_config
from mendify.sandbox import Sandbox
from mendify.state import AgentState


def validate(state: AgentState) -> dict:
    """Run the build command in a Docker sandbox and record the result."""
    repo_path = Path(state.get("repo_path", ".")).resolve()
    config = load_config(repo_path)
    error_history: list[str] = list(state.get("error_history", []))
    iteration: int = state.get("iteration", 0)

    logger.info("Validating build iteration={}", iteration)

    with Sandbox(config.sandbox, repo_path) as sb:
        result = sb.run_command(config.sandbox.build_command)

    output = result.stdout + ("\n" + result.stderr if result.stderr else "")

    if result.success:
        logger.success("Validation passed on iteration={}", iteration)
        return {
            "validation_result": "pass",
            "validation_output": output,
        }
    else:
        logger.warning("Validation failed on iteration={}", iteration)
        error_history.append(output.strip())
        return {
            "validation_result": "fail",
            "validation_output": output,
            "error_history": error_history,
            "iteration": iteration + 1,
        }
