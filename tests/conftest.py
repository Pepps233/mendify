import pytest


@pytest.fixture(autouse=True)
def strip_secrets(monkeypatch):
    """Remove real credentials from test environment to prevent accidental API calls."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
