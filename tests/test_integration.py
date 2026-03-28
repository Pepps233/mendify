"""End-to-end graph tests with all external boundaries mocked."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from mendify.agent import build_graph
from mendify.github_client import WorkflowFailure
from mendify.sandbox import SandboxResult

FAKE_LOGS = "FAILED tests/test_app.py - AssertionError: expected 1, got 2"

FAKE_DIAGNOSIS = {
    "diagnosis": "Off-by-one error in calculation",
    "patch": {"src/app.py": "def calc(x):\n    return x + 1\n"},
    "confidence": 0.92,
    "explanation": "Fixed off-by-one in calc()",
}


def _make_llm_mock():
    mock_response = MagicMock()
    mock_response.content = json.dumps(FAKE_DIAGNOSIS)
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    return mock_llm


def _make_github_mock(logs: str = FAKE_LOGS):
    gh = MagicMock()
    gh.__enter__ = MagicMock(return_value=gh)
    gh.__exit__ = MagicMock(return_value=None)
    gh.get_failed_workflow_run.return_value = WorkflowFailure(
        run_id=99,
        workflow_name="CI",
        head_sha="abc123def",
        head_branch="fix/off-by-one",
        logs=logs,
        conclusion="failure",
    )
    gh.create_commit_and_push = MagicMock()
    return gh


def _make_sandbox_mock(success: bool = True):
    sb = MagicMock()
    sb.__enter__ = MagicMock(return_value=sb)
    sb.__exit__ = MagicMock(return_value=None)
    sb.run_command.return_value = SandboxResult(
        exit_code=0 if success else 1,
        stdout="All tests passed" if success else "FAILED",
        stderr="",
    )
    return sb


@pytest.fixture
def tmp_repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def calc(x):\n    return x\n")
    (tmp_path / ".mendify.yml").write_text(
        "sandbox:\n  build_command: 'uv run pytest'\nallowed_paths:\n  - '**/*.py'\n"
    )
    return tmp_path


def test_happy_path(tmp_repo):
    """fetch_logs -> diagnose -> apply_patch -> validate(pass) -> commit"""
    graph = build_graph()

    gh_mock = _make_github_mock()
    sandbox_mock = _make_sandbox_mock(success=True)
    llm_mock = _make_llm_mock()

    with (
        patch("mendify.nodes.fetch_logs.GitHubClient", return_value=gh_mock),
        patch("mendify.nodes.diagnose.ChatAnthropic", return_value=llm_mock),
        patch("mendify.nodes.validate.Sandbox", return_value=sandbox_mock),
        patch("mendify.nodes.commit.GitHubClient", return_value=gh_mock),
    ):
        final = graph.invoke({
            "run_id": 99,
            "repo_path": str(tmp_repo),
            "iteration": 0,
            "max_iterations": 3,
            "error_history": [],
        })

    assert final["validation_result"] == "pass"
    gh_mock.create_commit_and_push.assert_called_once()


def test_retry_then_pass(tmp_repo):
    """First validation fails, second succeeds after retry."""
    graph = build_graph()

    gh_mock = _make_github_mock()
    llm_mock = _make_llm_mock()

    fail_sb = _make_sandbox_mock(success=False)
    pass_sb = _make_sandbox_mock(success=True)
    sandbox_calls = [fail_sb, pass_sb]

    def sandbox_factory(*args, **kwargs):
        return sandbox_calls.pop(0)

    with (
        patch("mendify.nodes.fetch_logs.GitHubClient", return_value=gh_mock),
        patch("mendify.nodes.diagnose.ChatAnthropic", return_value=llm_mock),
        patch("mendify.nodes.validate.Sandbox", side_effect=sandbox_factory),
        patch("mendify.nodes.commit.GitHubClient", return_value=gh_mock),
    ):
        final = graph.invoke({
            "run_id": 99,
            "repo_path": str(tmp_repo),
            "iteration": 0,
            "max_iterations": 3,
            "error_history": [],
        })

    assert final["validation_result"] == "pass"


def test_max_retries_report_failure(tmp_repo):
    """All validations fail — report_failure is called."""
    graph = build_graph()

    gh_mock = _make_github_mock()
    llm_mock = _make_llm_mock()

    fail_sb = _make_sandbox_mock(success=False)

    with (
        patch("mendify.nodes.fetch_logs.GitHubClient", return_value=gh_mock),
        patch("mendify.nodes.diagnose.ChatAnthropic", return_value=llm_mock),
        patch("mendify.nodes.validate.Sandbox", return_value=fail_sb),
    ):
        final = graph.invoke({
            "run_id": 99,
            "repo_path": str(tmp_repo),
            "iteration": 0,
            "max_iterations": 1,
            "error_history": [],
        })

    assert final.get("validation_result") == "fail"
    gh_mock.create_commit_and_push.assert_not_called()
