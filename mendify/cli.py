from __future__ import annotations

import sys
from pathlib import Path

import click
from loguru import logger


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def cli(verbose: bool) -> None:
    """Mendify — autonomous DevOps framework."""
    level = "DEBUG" if verbose else "INFO"
    logger.remove()
    logger.add(sys.stderr, level=level, colorize=True)


@cli.command()
@click.option("--run-id", required=True, type=int, help="GitHub Actions workflow run ID")
@click.option(
    "--repo-path",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False),
    help="Path to the repository root",
)
@click.option(
    "--max-iterations",
    default=3,
    show_default=True,
    type=int,
    help="Maximum number of fix attempts",
)
def heal(run_id: int, repo_path: str, max_iterations: int) -> None:
    """Run the full healing loop for a failed workflow run."""
    from mendify.agent import graph  # lazy import

    initial_state = {
        "run_id": run_id,
        "repo_path": str(Path(repo_path).resolve()),
        "iteration": 0,
        "max_iterations": max_iterations,
        "error_history": [],
    }

    logger.info("Starting Mendify heal run_id={} max_iterations={}", run_id, max_iterations)
    final_state = graph.invoke(initial_state)

    if final_state.get("validation_result") == "pass":
        logger.success("Mendify successfully healed the build")
        sys.exit(0)
    else:
        logger.error("Mendify could not heal the build after {} attempts", max_iterations)
        sys.exit(1)


@cli.command()
@click.option("--run-id", required=True, type=int, help="GitHub Actions workflow run ID")
@click.option(
    "--repo-path",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False),
)
def diagnose(run_id: int, repo_path: str) -> None:
    """Fetch logs and diagnose root cause without applying a patch."""
    from mendify.github_client import GitHubClient  # lazy import
    from mendify.nodes.diagnose import diagnose as diagnose_node  # lazy import

    with GitHubClient() as gh:
        failure = gh.get_failed_workflow_run(run_id)

    result = diagnose_node({
        "build_logs": failure.logs,
        "iteration": 0,
        "error_history": [],
    })

    click.echo(f"Diagnosis: {result['diagnosis']}")
    click.echo(f"Confidence: {result['confidence']:.0%}")
    click.echo(f"Explanation: {result['explanation']}")
    click.echo(f"Files to patch: {list(result['patch'].keys())}")


@cli.command()
@click.option(
    "--repo-path",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False),
)
def validate(repo_path: str) -> None:
    """Run sandbox validation on the current repo state (for local testing)."""
    from mendify.config import load_config  # lazy import
    from mendify.sandbox import Sandbox  # lazy import

    path = Path(repo_path).resolve()
    config = load_config(path)

    with Sandbox(config.sandbox, path) as sb:
        result = sb.run_command(config.sandbox.build_command)

    if result.stdout:
        click.echo(result.stdout)
    if result.stderr:
        click.echo(result.stderr, err=True)

    sys.exit(0 if result.success else 1)
