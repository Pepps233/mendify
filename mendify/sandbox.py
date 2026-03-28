from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import docker.errors
from loguru import logger

import docker
from mendify.config import SandboxConfig


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0


class Sandbox:
    """Docker sandbox for running build/test commands in isolation."""

    def __init__(self, config: SandboxConfig, repo_path: Path) -> None:
        self.config = config
        self.repo_path = repo_path.resolve()
        self._client: docker.DockerClient | None = None
        self._container = None

    def start(self) -> None:
        """Start the sandbox container."""
        self._client = docker.from_env()
        logger.info("Starting sandbox container image={}", self.config.image)
        self._container = self._client.containers.run(
            self.config.image,
            command="sleep infinity",
            detach=True,
            remove=True,
            mem_limit=self.config.memory_limit,
            volumes={
                str(self.repo_path): {"bind": "/workspace", "mode": "rw"}
            },
            working_dir="/workspace",
        )
        logger.debug("Sandbox container started id={}", self._container.id[:12])

    def run_command(self, cmd: str) -> SandboxResult:
        """Execute a shell command inside the running container."""
        if self._container is None:
            raise RuntimeError("Sandbox is not started. Call start() first.")

        logger.debug("Running command in sandbox: {}", cmd)
        exit_code, (stdout_bytes, stderr_bytes) = self._container.exec_run(
            cmd=["sh", "-c", cmd],
            demux=True,
            workdir="/workspace",
        )

        stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
        stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")

        logger.debug("Command exit_code={}", exit_code)
        return SandboxResult(exit_code=exit_code, stdout=stdout, stderr=stderr)

    def cleanup(self) -> None:
        """Stop and remove the container."""
        if self._container is not None:
            try:
                self._container.stop(timeout=5)
                logger.debug("Sandbox container stopped")
            except docker.errors.NotFound:
                pass
            except Exception as exc:
                logger.warning("Error stopping sandbox container: {}", exc)
            finally:
                self._container = None

        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            finally:
                self._client = None

    def __enter__(self) -> Sandbox:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()
        return None
