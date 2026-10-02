import json

import pytest

from code_companion import pmat_runner
from code_companion.pmat_runner import PmatError, _split_output, analyze_command, output_json, report_data, run_pmat


def test_split_output_extracts_json_from_banner(pmat_stdout):
    data, rest = _split_output(pmat_stdout())

    assert data["files"][0]["path"] == "./a.py"
    assert "Analyzing python-uv project" in rest
    assert "{" not in rest


def test_run_pmat_parses_offenders_even_when_pmat_exits_non_zero(make_config, install_fake_pmat, pmat_stdout):
    calls = install_fake_pmat(pmat_stdout(big_cyclomatic=25), returncode=1)

    result = run_pmat(make_config(max_cyclomatic=20), only=None)

    assert result.pmat_version == "3.42.0"
    assert [f.name for f in result.offenders] == ["big_function"]
    assert result.offenders[0].file == "a.py"
    assert result.offenders[0].line == 12
    assert "<module>" not in [f.name for f in result.functions]
    assert analyze_command(20) in calls

    data = report_data(result)
    assert data["violations_count"] == 1
    assert data["violations"][0] == {"file": "a.py", "name": "big_function", "line": 12, "end_line": 58, "cyclomatic": 25}
    assert [f["path"] for f in data["files"]] == ["a.py"]


def test_run_pmat_keeps_only_requested_files(make_config, install_fake_pmat, pmat_stdout):
    install_fake_pmat(pmat_stdout())

    result = run_pmat(make_config(), only={"other.py"})

    assert result.functions == []
    assert result.offenders == []
    assert report_data(result)["files"] == []


def test_output_json_drops_file_details_only_when_too_large(make_config, install_fake_pmat, pmat_stdout, monkeypatch):
    install_fake_pmat(pmat_stdout())
    result = run_pmat(make_config(), only=None)
    assert output_json(result) == json.dumps(report_data(result), separators=(",", ":"))

    monkeypatch.setattr(pmat_runner, "MAX_OUTPUT_JSON_CHARS", 10)
    data = json.loads(output_json(result))

    assert data["truncated"] is True
    assert data["files"] == []
    assert data["violations_count"] == 1


def test_analyze_command_uses_the_configured_limit():
    command = analyze_command(35)

    assert command[:4] == ["pmat", "analyze", "complexity", "--fail-on-violation"]
    assert command[command.index("--max-cyclomatic") + 1] == "35"
    assert command[command.index("--format") + 1] == "json"


def test_run_pmat_fails_when_no_json_report(make_config, install_fake_pmat):
    install_fake_pmat("something went wrong", returncode=2)

    with pytest.raises(PmatError, match="exit code 2"):
        run_pmat(make_config(), only=None)
