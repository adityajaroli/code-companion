import json

import pytest

from code_companion.config import Config
from code_companion.constants import DEFAULT_MAX_CYCLOMATIC


def test_from_env_reads_inputs_and_event(monkeypatch, tmp_path):
    event_file = tmp_path / "event.json"
    event_file.write_text(json.dumps({"pull_request": {"number": 7}}))
    monkeypatch.setenv("INPUT_GITHUB_TOKEN", "tok")
    monkeypatch.setenv("INPUT_PMAT_VERSION", "3.42.0")
    monkeypatch.setenv("INPUT_MAX_CYCLOMATIC", "15")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))

    config = Config.from_env()

    assert config.token == "tok"
    assert config.pmat_version == "3.42.0"
    assert config.max_cyclomatic == 15
    assert config.event_name == "pull_request"
    assert config.pr_number == 7
    assert config.repository == "owner/repo"
    assert config.workspace == tmp_path.resolve()


def test_max_cyclomatic_defaults_when_empty(monkeypatch):
    monkeypatch.setenv("INPUT_MAX_CYCLOMATIC", "")

    assert Config.from_env().max_cyclomatic == DEFAULT_MAX_CYCLOMATIC


@pytest.mark.parametrize("raw", ["abc", "0", "-3"])
def test_invalid_max_cyclomatic_is_rejected(monkeypatch, raw):
    monkeypatch.setenv("INPUT_MAX_CYCLOMATIC", raw)

    with pytest.raises(ValueError, match="max-cyclomatic"):
        Config.from_env()
