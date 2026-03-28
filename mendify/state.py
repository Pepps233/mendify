from __future__ import annotations

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    # LangGraph message history
    messages: list

    # Workflow context (populated by fetch_logs)
    build_logs: str
    run_id: int
    head_branch: str
    head_sha: str
    workflow_name: str

    # Diagnosis output (populated by diagnose)
    diagnosis: str
    patch: dict[str, str]         # {file_path: new_content}
    confidence: float
    explanation: str

    # Retry control
    iteration: int
    max_iterations: int
    error_history: list[str]      # previous validation errors, for retry context

    # Validation outcome (populated by validate)
    validation_result: str        # "pass" | "fail"
    validation_output: str

    # Config / paths
    repo_path: str                # absolute path to repo on disk
