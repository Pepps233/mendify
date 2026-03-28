from __future__ import annotations

import io
import os
import subprocess
import time
import zipfile
from dataclasses import dataclass

import httpx
from loguru import logger


@dataclass
class WorkflowFailure:
    run_id: int
    workflow_name: str
    head_sha: str
    head_branch: str
    logs: str
    conclusion: str


class GitHubClient:
    """Thin GitHub REST API client backed by httpx."""

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        token: str | None = None,
        repository: str | None = None,
    ) -> None:
        self.token = token or os.environ["GITHUB_TOKEN"]
        self.repository = repository or os.environ["GITHUB_REPOSITORY"]
        self._http = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    # ------------------------------------------------------------------
    # Workflow helpers
    # ------------------------------------------------------------------

    def get_failed_workflow_run(self, run_id: int) -> WorkflowFailure:
        """Fetch run metadata and download its logs."""
        run = self._get_with_retry(f"/repos/{self.repository}/actions/runs/{run_id}")

        log_content = self._download_logs(run_id)

        return WorkflowFailure(
            run_id=run_id,
            workflow_name=run.get("name", "unknown"),
            head_sha=run.get("head_sha", ""),
            head_branch=run.get("head_branch", ""),
            logs=log_content,
            conclusion=run.get("conclusion", "failure"),
        )

    def _download_logs(self, run_id: int) -> str:
        """Download and extract the log zip for a workflow run."""
        resp = self._http.get(
            f"/repos/{self.repository}/actions/runs/{run_id}/logs",
            follow_redirects=True,
        )
        resp.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            parts: list[str] = []
            for name in sorted(zf.namelist()):
                if name.endswith(".txt"):
                    parts.append(f"=== {name} ===\n")
                    parts.append(zf.read(name).decode("utf-8", errors="replace"))
            return "\n".join(parts)

    # ------------------------------------------------------------------
    # Commit / PR helpers
    # ------------------------------------------------------------------

    def create_commit_and_push(self, branch: str, message: str) -> None:
        """Stage all modified files, commit, and push via subprocess git."""
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        subprocess.run(["git", "push", "origin", f"HEAD:{branch}"], check=True)
        logger.info("Pushed corrective commit to branch={}", branch)

    def post_pr_comment(self, pr_number: int, body: str) -> None:
        """Post a comment on a pull request."""
        self._post_with_retry(
            f"/repos/{self.repository}/issues/{pr_number}/comments",
            json={"body": body},
        )

    # ------------------------------------------------------------------
    # Retry helpers
    # ------------------------------------------------------------------

    def _get_with_retry(self, path: str, *, retries: int = 3) -> dict:
        delay = 1.0
        for attempt in range(retries):
            resp = self._http.get(path)
            if resp.status_code in (429, 500, 502, 503, 504):
                logger.warning("GitHub API {} attempt={} status={}", path, attempt, resp.status_code)
                time.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return {}

    def _post_with_retry(self, path: str, *, json: dict, retries: int = 3) -> dict:
        delay = 1.0
        for attempt in range(retries):
            resp = self._http.post(path, json=json)
            if resp.status_code in (429, 500, 502, 503, 504):
                logger.warning("GitHub API POST {} attempt={} status={}", path, attempt, resp.status_code)
                time.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return {}

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *_) -> None:
        self.close()
