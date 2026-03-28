
import pytest
import yaml

from mendify.config import AgentConfig, MendifyConfig, SandboxConfig, load_config


def test_default_config():
    config = MendifyConfig()
    assert config.agent.model == "claude-sonnet-4-6-20250514"
    assert config.agent.max_iterations == 3
    assert config.sandbox.timeout_seconds == 300
    assert "**/*.py" in config.allowed_paths


def test_load_config_no_file(tmp_path):
    config = load_config(tmp_path)
    assert isinstance(config, MendifyConfig)
    assert config.agent.max_iterations == 3


def test_load_config_valid_yaml(tmp_path):
    data = {
        "agent": {"max_iterations": 5, "temperature": 0.5},
        "sandbox": {"timeout_seconds": 600, "build_command": "pytest"},
        "allowed_paths": ["src/**/*.py"],
    }
    (tmp_path / ".mendify.yml").write_text(yaml.dump(data))
    config = load_config(tmp_path)
    assert config.agent.max_iterations == 5
    assert config.agent.temperature == 0.5
    assert config.sandbox.timeout_seconds == 600
    assert config.sandbox.build_command == "pytest"
    assert config.allowed_paths == ["src/**/*.py"]


def test_load_config_partial_yaml(tmp_path):
    data = {"agent": {"max_iterations": 2}}
    (tmp_path / ".mendify.yml").write_text(yaml.dump(data))
    config = load_config(tmp_path)
    assert config.agent.max_iterations == 2
    # defaults preserved for everything else
    assert config.sandbox.timeout_seconds == 300


def test_load_config_empty_yaml(tmp_path):
    (tmp_path / ".mendify.yml").write_text("")
    config = load_config(tmp_path)
    assert isinstance(config, MendifyConfig)


def test_sandbox_config_validation():
    with pytest.raises(Exception):
        SandboxConfig(timeout_seconds=5)  # below minimum of 30

    with pytest.raises(Exception):
        SandboxConfig(timeout_seconds=9999)  # above maximum of 1800


def test_agent_config_validation():
    with pytest.raises(Exception):
        AgentConfig(max_iterations=0)

    with pytest.raises(Exception):
        AgentConfig(max_iterations=11)
