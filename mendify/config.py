from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class SandboxConfig(BaseModel):
    image: str = "mendify-sandbox:latest"
    timeout_seconds: int = Field(default=300, ge=30, le=1800)
    memory_limit: str = "512m"
    build_command: str = "make test"


class AgentConfig(BaseModel):
    model: str = "claude-sonnet-4-6-20250514"
    max_iterations: int = Field(default=3, ge=1, le=10)
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)


class MendifyConfig(BaseModel):
    agent: AgentConfig = Field(default_factory=AgentConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    allowed_paths: list[str] = Field(default_factory=lambda: ["**/*.py", "**/*.toml", "**/*.yml"])
    exclude_paths: list[str] = Field(default_factory=lambda: [".git/**", ".venv/**"])


def load_config(repo_root: Path) -> MendifyConfig:
    """Load .mendify.yml from repo root, falling back to defaults."""
    config_path = repo_root / ".mendify.yml"
    if not config_path.exists():
        return MendifyConfig()

    with config_path.open() as f:
        raw = yaml.safe_load(f) or {}

    return MendifyConfig.model_validate(raw)
