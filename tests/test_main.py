import json
import re
from types import SimpleNamespace

import pytest

from code_companion.__main__ import main
from code_companion.constants import (
    COMMENT_MARKER,
    EXIT_FAILURE,
    EXIT_OK,
    JSON_REPORT_FILENAME,
    NO_FILES_MESSAGE,
    REPORT_FILENAME,
)
from code_companion.github_api import ApiError


@pytest.fixture
def pr_env(monkeypatch, tmp_path, git_repo):
    """Environment of a pull_request run on a real two-commit repo."""
    runner_temp = tmp_path / "runner"
    runner_temp.mkdir()
    paths = SimpleNamespace(
        event=tmp_path / "event.json",
        output=tmp_path / "output.txt",
        summary=tmp_path / "summary.md",
        runner_temp=runner_temp,
    )
    write_event(paths, {"pull_request": {"number": 5, "base": {"sha": git_repo.first}, "head": {"sha": git_repo.second}}})

    env = {
        "INPUT_GITHUB_TOKEN": "tok",
        "INPUT_PMAT_VERSION": "3.42.0",
        "INPUT_MAX_CYCLOMATIC": "20",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_EVENT_PATH": paths.event,
        "GITHUB_SHA": git_repo.second,
        "GITHUB_REPOSITORY": "owner/repo",
        "GITHUB_WORKSPACE": git_repo.path,
        "GITHUB_OUTPUT": paths.output,
        "GITHUB_STEP_SUMMARY": paths.summary,
        "RUNNER_TEMP": runner_temp,
    }
    for name, value in env.items():
        monkeypatch.setenv(name, str(value))
    return paths


def write_event(paths, event):
    paths.event.write_text(json.dumps(event))


def output_value(paths, name):
    match = re.search(rf"{name}<<(\S+)\n(.*?)\n\1", paths.output.read_text(), re.DOTALL)
    return match.group(2)


def test_pull_request_with_violation_publishes_report_and_fails(pr_env, api, install_fake_pmat, pmat_stdout):
    install_fake_pmat(pmat_stdout(big_cyclomatic=25), returncode=1)

    exit_code = main()

    assert exit_code == EXIT_FAILURE
    report = (pr_env.runner_temp / REPORT_FILENAME).read_text()
    assert "| `a.py` | `big_function` | 12 | **25** |" in report
    assert "big_function" in pr_env.summary.read_text()
    assert output_value(pr_env, "violations-count") == "1"
    assert output_value(pr_env, "report-path") == str(pr_env.runner_temp / REPORT_FILENAME)
    json_report = pr_env.runner_temp / JSON_REPORT_FILENAME
    report_json = json.loads(json_report.read_text())
    assert report_json["violations_count"] == 1
    assert report_json["violations"][0]["name"] == "big_function"
    assert report_json["files"][0]["path"] == "a.py"
    assert output_value(pr_env, "json-report-path") == str(json_report)
    assert json.loads(output_value(pr_env, "pmat-json")) == report_json
    method, url, body = api.calls[-1]
    assert (method, url.rsplit("/repos/", 1)[1]) == ("POST", "owner/repo/issues/5/comments")
    assert COMMENT_MARKER in body["body"]


def test_pull_request_without_violation_passes(pr_env, api, install_fake_pmat, pmat_stdout):
    install_fake_pmat(pmat_stdout(big_cyclomatic=3), returncode=0)

    exit_code = main()

    assert exit_code == EXIT_OK
    assert output_value(pr_env, "violations-count") == "0"
    assert "No function in the changed files exceeds the threshold." in pr_env.summary.read_text()
    assert api.calls[-1][0] == "POST"


def test_existing_sticky_comment_is_updated(pr_env, api, install_fake_pmat, pmat_stdout):
    install_fake_pmat(pmat_stdout(big_cyclomatic=3), returncode=0)
    api.existing = [{"id": 42, "body": f"{COMMENT_MARKER} previous run"}]

    main()

    method, url, body = api.calls[-1]
    assert (method, url.rsplit("/repos/", 1)[1]) == ("PATCH", "owner/repo/issues/comments/42")
    assert COMMENT_MARKER in body["body"]


def test_no_changed_files_skips_pmat(pr_env, git_repo, api, install_fake_pmat, pmat_stdout):
    calls = install_fake_pmat(pmat_stdout())
    same = {"sha": git_repo.second}
    write_event(pr_env, {"pull_request": {"number": 5, "base": same, "head": same}})

    exit_code = main()

    assert exit_code == EXIT_OK
    assert not [call for call in calls if "analyze" in call]
    assert NO_FILES_MESSAGE in pr_env.summary.read_text()
    report_json = json.loads((pr_env.runner_temp / JSON_REPORT_FILENAME).read_text())
    assert report_json["violations_count"] == 0
    assert report_json["files"] == []


def test_push_event_publishes_report_without_comment(pr_env, git_repo, api, monkeypatch, install_fake_pmat, pmat_stdout):
    install_fake_pmat(pmat_stdout(big_cyclomatic=3), returncode=0)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    write_event(pr_env, {"before": git_repo.first})

    exit_code = main()

    assert exit_code == EXIT_OK
    assert (pr_env.runner_temp / REPORT_FILENAME).exists()
    assert output_value(pr_env, "violations-count") == "0"
    assert api.calls == []


def test_forbidden_comment_only_warns(pr_env, api, install_fake_pmat, pmat_stdout, capsys):
    install_fake_pmat(pmat_stdout(big_cyclomatic=3), returncode=0)
    api.error = ApiError(403, "Resource not accessible by integration")

    exit_code = main()

    assert exit_code == EXIT_OK
    assert "::warning::Could not post the PR comment (403)" in capsys.readouterr().out
    assert (pr_env.runner_temp / REPORT_FILENAME).exists()


def test_pmat_crash_fails_with_error_report(pr_env, api, install_fake_pmat):
    install_fake_pmat("segfault", returncode=139)

    exit_code = main()

    assert exit_code == EXIT_FAILURE
    assert "could not be completed" in (pr_env.runner_temp / REPORT_FILENAME).read_text()
    assert not (pr_env.runner_temp / JSON_REPORT_FILENAME).exists()
    assert "violations-count" not in pr_env.output.read_text()


def test_invalid_max_cyclomatic_fails_before_running_pmat(pr_env, api, monkeypatch, install_fake_pmat, pmat_stdout, capsys):
    calls = install_fake_pmat(pmat_stdout())
    monkeypatch.setenv("INPUT_MAX_CYCLOMATIC", "abc")

    exit_code = main()

    assert exit_code == EXIT_FAILURE
    assert "max-cyclomatic must be an integer" in capsys.readouterr().out
    assert calls == []
    assert api.calls == []
