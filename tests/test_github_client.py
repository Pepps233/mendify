import io
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from mendify.github_client import GitHubClient, WorkflowFailure


def make_zip_with_log(content: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("1_job/0_step.txt", content)
    return buf.getvalue()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    with patch("mendify.github_client.httpx.Client") as mock_cls:
        mock_http = MagicMock()
        mock_cls.return_value = mock_http
        yield GitHubClient(), mock_http


def test_get_failed_workflow_run(client):
    gh, mock_http = client

    run_resp = MagicMock()
    run_resp.status_code = 200
    run_resp.json.return_value = {
        "name": "CI",
        "head_sha": "abc123",
        "head_branch": "fix/thing",
        "conclusion": "failure",
    }

    log_resp = MagicMock()
    log_resp.status_code = 200
    log_resp.content = make_zip_with_log("Build failed: SyntaxError")

    mock_http.get.side_effect = [run_resp, log_resp]

    result = gh.get_failed_workflow_run(42)

    assert isinstance(result, WorkflowFailure)
    assert result.run_id == 42
    assert result.workflow_name == "CI"
    assert result.head_sha == "abc123"
    assert "Build failed" in result.logs


def test_post_pr_comment(client):
    gh, mock_http = client

    comment_resp = MagicMock()
    comment_resp.status_code = 201
    comment_resp.json.return_value = {"id": 99}
    mock_http.post.return_value = comment_resp

    gh.post_pr_comment(7, "Mendify fixed it!")

    mock_http.post.assert_called_once()
    call_kwargs = mock_http.post.call_args[1]
    assert call_kwargs["json"]["body"] == "Mendify fixed it!"


def test_retry_on_rate_limit(client):
    gh, mock_http = client

    rate_limit_resp = MagicMock()
    rate_limit_resp.status_code = 429

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.json.return_value = {
        "name": "CI",
        "head_sha": "abc",
        "head_branch": "main",
        "conclusion": "failure",
    }

    log_resp = MagicMock()
    log_resp.status_code = 200
    log_resp.content = make_zip_with_log("error")

    mock_http.get.side_effect = [rate_limit_resp, ok_resp, log_resp]

    with patch("mendify.github_client.time.sleep"):
        result = gh.get_failed_workflow_run(1)

    assert result.workflow_name == "CI"


def test_post_retry_on_server_error(client):
    gh, mock_http = client

    err_resp = MagicMock()
    err_resp.status_code = 500

    ok_resp = MagicMock()
    ok_resp.status_code = 201
    ok_resp.json.return_value = {"id": 1}

    mock_http.post.side_effect = [err_resp, ok_resp]

    with patch("mendify.github_client.time.sleep"):
        gh.post_pr_comment(1, "retry test")

    assert mock_http.post.call_count == 2


def test_create_commit_and_push(client, monkeypatch):
    gh, _ = client

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

    monkeypatch.setattr("mendify.github_client.subprocess.run", fake_run)

    gh.create_commit_and_push("main", "fix: something")

    assert calls[0] == ["git", "add", "-A"]
    assert calls[1] == ["git", "commit", "-m", "fix: something"]
    assert calls[2][0:2] == ["git", "push"]


def test_context_manager(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")

    with patch("mendify.github_client.httpx.Client") as mock_cls:
        mock_http = MagicMock()
        mock_cls.return_value = mock_http

        with GitHubClient() as gh:
            assert gh is not None

        mock_http.close.assert_called_once()
