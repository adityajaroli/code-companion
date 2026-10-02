"""Entry point: `python -m code_companion`.

Exits non-zero when a function in the changed files exceeds the cyclomatic limit (mirroring
PMAT's `--fail-on-violation`, but scoped to the changed files) and on genuine errors (install
failure, crash, unparseable output). A failed PR comment only warns.
"""

from __future__ import annotations

import json
import os
import sys

from . import github_api as gh
from .config import Config
from .constants import (
    COMMENT_FORBIDDEN_WARNING,
    ENCODING,
    EXIT_FAILURE,
    EXIT_OK,
    HTTP_FORBIDDEN,
    JSON_REPORT_FILENAME,
    NO_TOKEN_WARNING,
    REPORT_FILENAME,
    EnvVar,
    OutputName,
)
from .git_diff import changed_files
from .pmat_runner import AnalysisResult, PmatError, empty_result, output_json, report_data, run_pmat
from .report import build_report, error_report, truncate_for_comment


def _post_comment(config: Config, report: str) -> None:
    if config.pr_number is None:
        return
    if not config.token:
        gh.warning(NO_TOKEN_WARNING)
        return
    try:
        action = gh.upsert_pr_comment(
            config.token, config.repository, config.pr_number, truncate_for_comment(report)
        )
        print(f"PR comment {action}")
    except gh.ApiError as exc:
        gh.warning(COMMENT_FORBIDDEN_WARNING if exc.status == HTTP_FORBIDDEN else f"Could not post the PR comment: {exc}")


def _write_report(config: Config, report: str) -> None:
    path = config.runner_temp / REPORT_FILENAME
    path.write_text(report + "\n", encoding=ENCODING)
    gh.write_summary(report)
    gh.set_output(OutputName.REPORT_PATH, str(path))


def _write_json_report(config: Config, result: AnalysisResult) -> None:
    path = config.runner_temp / JSON_REPORT_FILENAME
    path.write_text(json.dumps(report_data(result), indent=2) + "\n", encoding=ENCODING)
    gh.set_output(OutputName.JSON_REPORT_PATH, str(path))


def _analyze(config: Config) -> AnalysisResult:
    files = changed_files(config)
    if files is not None and not files:
        return empty_result(config)
    return run_pmat(config, set(files) if files is not None else None)


def main() -> int:
    gh.mask(os.environ.get(EnvVar.INPUT_GITHUB_TOKEN, ""))
    try:
        config = Config.from_env()
    except ValueError as exc:
        gh.error(f"Invalid configuration: {exc}")
        return EXIT_FAILURE

    try:
        result = _analyze(config)
    except PmatError as exc:
        gh.error(str(exc))
        report = error_report(config, str(exc))
        _write_report(config, report)
        _post_comment(config, report)
        return EXIT_FAILURE

    report = build_report(config, result)
    _write_report(config, report)
    _write_json_report(config, result)
    gh.set_output(OutputName.VIOLATIONS_COUNT, str(len(result.offenders)))
    gh.set_output(OutputName.PMAT_JSON, output_json(result))
    _post_comment(config, report)

    if result.offenders:
        gh.error(
            f"{len(result.offenders)} function(s) in the changed files exceed cyclomatic complexity "
            f"{config.max_cyclomatic}"
        )
        return EXIT_FAILURE
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
