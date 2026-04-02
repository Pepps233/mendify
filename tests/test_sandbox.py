from unittest.mock import MagicMock, patch

import docker.errors
import pytest

from mendify.config import SandboxConfig
from mendify.sandbox import Sandbox, SandboxResult


@pytest.fixture
def config():
    return SandboxConfig(image="test-image:latest", build_command="make test")


@pytest.fixture
def repo_path(tmp_path):
    return tmp_path


@pytest.fixture
def mock_docker():
    with patch("mendify.sandbox.docker") as mock:
        mock_client = MagicMock()
        mock.from_env.return_value = mock_client
        mock.errors.NotFound = Exception
        yield mock, mock_client


def test_sandbox_result_success():
    result = SandboxResult(exit_code=0, stdout="ok", stderr="")
    assert result.success is True


def test_sandbox_result_failure():
    result = SandboxResult(exit_code=1, stdout="", stderr="error")
    assert result.success is False


def test_sandbox_start(config, repo_path, mock_docker):
    mock, mock_client = mock_docker
    mock_container = MagicMock()
    mock_client.containers.run.return_value = mock_container

    sandbox = Sandbox(config, repo_path)
    sandbox.start()

    mock_client.containers.run.assert_called_once()
    call_kwargs = mock_client.containers.run.call_args
    assert call_kwargs[0][0] == "test-image:latest"
    assert call_kwargs[1]["detach"] is True
    assert call_kwargs[1]["working_dir"] == "/workspace"


def test_sandbox_run_command(config, repo_path, mock_docker):
    mock, mock_client = mock_docker
    mock_container = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_container.exec_run.return_value = (0, (b"output", b""))

    sandbox = Sandbox(config, repo_path)
    sandbox.start()
    result = sandbox.run_command("echo hello")

    assert result.exit_code == 0
    assert result.stdout == "output"
    assert result.success is True


def test_sandbox_run_command_failure(config, repo_path, mock_docker):
    mock, mock_client = mock_docker
    mock_container = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_container.exec_run.return_value = (1, (b"", b"build failed"))

    sandbox = Sandbox(config, repo_path)
    sandbox.start()
    result = sandbox.run_command("make test")

    assert result.exit_code == 1
    assert result.stderr == "build failed"
    assert result.success is False


def test_sandbox_run_command_before_start(config, repo_path):
    sandbox = Sandbox(config, repo_path)
    with pytest.raises(RuntimeError, match="not started"):
        sandbox.run_command("echo hello")


def test_sandbox_context_manager(config, repo_path, mock_docker):
    mock, mock_client = mock_docker
    mock_container = MagicMock()
    mock_client.containers.run.return_value = mock_container

    with Sandbox(config, repo_path) as sb:
        assert sb._container is mock_container

    mock_container.stop.assert_called_once()


def test_sandbox_cleanup_idempotent(config, repo_path, mock_docker):
    mock, mock_client = mock_docker
    mock_container = MagicMock()
    mock_client.containers.run.return_value = mock_container

    sandbox = Sandbox(config, repo_path)
    sandbox.start()
    sandbox.cleanup()
    sandbox.cleanup()  # should not raise


def test_sandbox_cleanup_container_not_found(config, repo_path, mock_docker):
    mock, mock_client = mock_docker
    mock_container = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_container.stop.side_effect = docker.errors.NotFound("gone")

    sandbox = Sandbox(config, repo_path)
    sandbox.start()
    sandbox.cleanup()  # should swallow NotFound silently

    assert sandbox._container is None


def test_sandbox_cleanup_stop_generic_error(config, repo_path, mock_docker):
    mock, mock_client = mock_docker
    mock_container = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_container.stop.side_effect = RuntimeError("unexpected")

    sandbox = Sandbox(config, repo_path)
    sandbox.start()
    sandbox.cleanup()  # should log warning but not raise

    assert sandbox._container is None
