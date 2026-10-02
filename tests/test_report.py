from code_companion.constants import CLEAN_MESSAGE, COMMENT_MARKER, COMMENT_TRUNCATED_NOTE, NO_FILES_MESSAGE
from code_companion.pmat_runner import AnalysisResult, FunctionResult
from code_companion.report import build_report, error_report, truncate_for_comment


def make_result(functions=(), ran=True, max_cyclomatic=20) -> AnalysisResult:
    return AnalysisResult(
        pmat_version="3.42.0",
        max_cyclomatic=max_cyclomatic,
        files=[],
        functions=list(functions),
        truncated=False,
        ran=ran,
    )


def test_report_lists_offenders_worst_first(make_config):
    result = make_result(
        [
            FunctionResult("src/a.py", "low", 1, 5, 21),
            FunctionResult("src/b.py", "high", 3, 9, 30),
            FunctionResult("src/c.py", "fine", 1, 2, 4),
        ]
    )

    report = build_report(make_config(), result)

    assert report.startswith(COMMENT_MARKER)
    assert "exceeds 20" in report
    assert "2 function(s) in 2 changed file(s)" in report
    assert report.index("| `src/b.py` | `high` | 3 | **30** |") < report.index("| `src/a.py` | `low` | 1 | **21** |")
    assert "fine" not in report
    assert "PMAT 3.42.0 - commit `abcdef1`" in report


def test_report_without_offenders_says_clean(make_config):
    report = build_report(make_config(), make_result([FunctionResult("src/a.py", "ok", 1, 3, 5)]))

    assert CLEAN_MESSAGE in report


def test_report_uses_the_configured_limit(make_config):
    result = make_result([FunctionResult("src/a.py", "mid", 1, 5, 8)], max_cyclomatic=5)

    report = build_report(make_config(max_cyclomatic=5), result)

    assert "exceeds 5" in report
    assert "| `src/a.py` | `mid` | 1 | **8** |" in report


def test_report_when_nothing_changed(make_config):
    report = build_report(make_config(), make_result(ran=False))

    assert NO_FILES_MESSAGE in report


def test_error_report_includes_message(make_config):
    report = error_report(make_config(), "pmat exploded")

    assert COMMENT_MARKER in report
    assert "pmat exploded" in report


def test_truncate_for_comment_keeps_short_reports_and_trims_long_ones():
    assert truncate_for_comment("short", limit=100) == "short"

    long_report = "\n".join(f"line {i}" for i in range(500))
    trimmed = truncate_for_comment(long_report, limit=200)

    assert len(trimmed) <= 200
    assert trimmed.endswith(COMMENT_TRUNCATED_NOTE)
