import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from code_companion import github_api  # noqa: E402
from code_companion.config import Config  # noqa: E402
from code_companion.constants import PMAT_EXECUTABLE, EnvVar  # noqa: E402

PMAT_VERSION_OUTPUT = "pmat 3.42.0\ncommit: unavailable (source archive)\n"
PMAT_BANNER = "Analyzing python-uv project complexity (all languages)...\nSuccessfully analyzed 1 file(s)\n"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in EnvVar:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def make_config(tmp_path):
    def build(**overrides) -> Config:
        values = {
            "token": "tok",
            "pmat_version": "3.42.0",
            "max_cyclomatic": 20,
            "event_name": "push",
            "event": {},
            "sha": "abcdef1234567",
            "repository": "owner/repo",
            "workspace": tmp_path,
            "runner_temp": tmp_path,
        }
        return Config(**{**values, **overrides})

    return build


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return proc.stdout.strip()


@pytest.fixture
def git_repo(tmp_path):
    """A repo with two commits: the second modifies a.py and adds b.py."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    (repo / "a.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "first")
    first = _git(repo, "rev-parse", "HEAD")

    (repo / "a.py").write_text("x = 2\n")
    (repo / "b.py").write_text("y = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "second")
    second = _git(repo, "rev-parse", "HEAD")
    return SimpleNamespace(path=repo, first=first, second=second)


@pytest.fixture
def api(monkeypatch):
    """Fake GitHub API. `existing` is returned for GETs; set `error` to make every call raise."""
    state = SimpleNamespace(calls=[], existing=[], error=None)

    def fake_request(token, method, url, body=None):
        state.calls.append((method, url, body))
        if state.error:
            raise state.error
        return list(state.existing) if method == "GET" else {}

    monkeypatch.setattr(github_api, "_request", fake_request)
    return state


@pytest.fixture
def pmat_stdout():
    """Builds PMAT's stdout: banner lines followed by the JSON report for ./a.py."""

    def build(big_cyclomatic: int = 25) -> str:
        functions = [
            {"name": "<module>", "line_start": 1, "line_end": 60, "metrics": {"cyclomatic": 3}},
            {"name": "small", "line_start": 5, "line_end": 9, "metrics": {"cyclomatic": 2}},
            {"name": "big_function", "line_start": 12, "line_end": 58, "metrics": {"cyclomatic": big_cyclomatic}},
        ]
        report = {
            "summary": {"total_files": 1},
            "violations": [],
            "files": [{"path": "./a.py", "functions": functions}],
            "files_truncated": False,
        }
        return PMAT_BANNER + json.dumps(report, indent=2) + "\n"

    return build


@pytest.fixture
def install_fake_pmat(monkeypatch):
    """Replace `pmat` with canned output; every other command (e.g. git) runs for real."""
    real_run = subprocess.run

    def install(stdout: str, returncode: int = 1) -> list[list[str]]:
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            if cmd[0] != PMAT_EXECUTABLE:
                return real_run(cmd, **kwargs)
            calls.append(list(cmd))
            if "--version" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout=PMAT_VERSION_OUTPUT, stderr="")
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        return calls

    return install
