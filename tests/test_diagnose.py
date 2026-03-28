import json
from unittest.mock import MagicMock, patch

import pytest

from mendify.nodes.diagnose import _parse_llm_response, diagnose


def test_parse_plain_json():
    raw = json.dumps({"diagnosis": "d", "patch": {}, "confidence": 0.9, "explanation": "e"})
    result = _parse_llm_response(raw)
    assert result["diagnosis"] == "d"
    assert result["confidence"] == 0.9


def test_parse_fenced_json():
    raw = "```json\n" + json.dumps({"diagnosis": "d", "patch": {}, "confidence": 0.8, "explanation": "e"}) + "\n```"
    result = _parse_llm_response(raw)
    assert result["diagnosis"] == "d"


def test_parse_invalid_raises():
    with pytest.raises(json.JSONDecodeError):
        _parse_llm_response("not json at all")


def test_diagnose_node(monkeypatch):
    expected = {
        "diagnosis": "missing import",
        "patch": {"src/app.py": "import os\n"},
        "confidence": 0.95,
        "explanation": "Added missing import",
    }
    mock_response = MagicMock()
    mock_response.content = json.dumps(expected)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response

    with patch("mendify.nodes.diagnose.ChatAnthropic", return_value=mock_llm):
        result = diagnose({
            "build_logs": "ModuleNotFoundError: No module named 'os'",
            "iteration": 0,
            "error_history": [],
        })

    assert result["diagnosis"] == "missing import"
    assert result["patch"] == {"src/app.py": "import os\n"}
    assert result["confidence"] == 0.95


def test_diagnose_includes_error_history(monkeypatch):
    expected = {
        "diagnosis": "different fix",
        "patch": {},
        "confidence": 0.7,
        "explanation": "new approach",
    }
    mock_response = MagicMock()
    mock_response.content = json.dumps(expected)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response

    with patch("mendify.nodes.diagnose.ChatAnthropic", return_value=mock_llm):
        diagnose({
            "build_logs": "error log",
            "iteration": 1,
            "error_history": ["previous patch failed: tests still broken"],
        })

    # The human message passed to invoke should contain the error history
    call_args = mock_llm.invoke.call_args[0][0]
    human_msg = call_args[-1]
    assert "previous patch failed" in human_msg.content
