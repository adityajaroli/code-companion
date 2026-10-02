from __future__ import annotations

from enum import StrEnum
from typing import Final

EXIT_OK: Final = 0
EXIT_FAILURE: Final = 1

DEFAULT_MAX_CYCLOMATIC: Final = 20
MIN_MAX_CYCLOMATIC: Final = 1
TOP_FILES_LIMIT: Final = 100_000
PMAT_EXECUTABLE: Final = "pmat"
PMAT_ANALYZE_PREFIX: Final = (PMAT_EXECUTABLE, "analyze", "complexity", "--fail-on-violation")
PMAT_MAX_CYCLOMATIC_FLAG: Final = "--max-cyclomatic"
PMAT_ANALYZE_SUFFIX: Final = ("--format", "json", "--top-files", str(TOP_FILES_LIMIT))
PMAT_VERSION_COMMAND: Final = (PMAT_EXECUTABLE, "--version")
PMAT_ANALYSIS_TIMEOUT_SECONDS: Final = 330  # PMAT's own limit is 300s
PMAT_VERSION_TIMEOUT_SECONDS: Final = 30
MODULE_PSEUDO_FUNCTION_PREFIX: Final = "<"  # PMAT reports module-level code as `<module>`
NO_COLOR_ENV: Final = {"NO_COLOR": "1"}

GIT_DIFF_COMMAND: Final = ("git", "diff", "--name-only", "-z", "--diff-filter=ACMR")  # added/copied/modified/renamed
GIT_TIMEOUT_SECONDS: Final = 60
ZERO_SHA: Final = "0" * 40  # `before` on a push that creates a branch
FALLBACK_REVISION_RANGE: Final = "HEAD~1..HEAD"
PATH_SEPARATOR_NUL: Final = "\0"


class EventName(StrEnum):
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    PULL_REQUEST_TARGET = "pull_request_target"


PULL_REQUEST_EVENTS: Final = frozenset({EventName.PULL_REQUEST, EventName.PULL_REQUEST_TARGET})


class EnvVar(StrEnum):
    INPUT_GITHUB_TOKEN = "INPUT_GITHUB_TOKEN"
    INPUT_PMAT_VERSION = "INPUT_PMAT_VERSION"
    INPUT_MAX_CYCLOMATIC = "INPUT_MAX_CYCLOMATIC"
    GITHUB_EVENT_NAME = "GITHUB_EVENT_NAME"
    GITHUB_EVENT_PATH = "GITHUB_EVENT_PATH"
    GITHUB_SHA = "GITHUB_SHA"
    GITHUB_REPOSITORY = "GITHUB_REPOSITORY"
    GITHUB_WORKSPACE = "GITHUB_WORKSPACE"
    GITHUB_API_URL = "GITHUB_API_URL"
    GITHUB_OUTPUT = "GITHUB_OUTPUT"
    GITHUB_STEP_SUMMARY = "GITHUB_STEP_SUMMARY"
    RUNNER_TEMP = "RUNNER_TEMP"


class OutputName(StrEnum):
    PMAT_JSON = "pmat-json"
    REPORT_PATH = "report-path"
    JSON_REPORT_PATH = "json-report-path"
    VIOLATIONS_COUNT = "violations-count"


DEFAULT_WORKSPACE: Final = "."
DEFAULT_RUNNER_TEMP: Final = "/tmp"
REPORT_FILENAME: Final = "code-companion-report.md"
JSON_REPORT_FILENAME: Final = "code-companion-report.json"
MAX_OUTPUT_JSON_CHARS: Final = 900_000  # step outputs are limited to 1 MB
ENCODING: Final = "utf-8"

DEFAULT_API_URL: Final = "https://api.github.com"
API_VERSION: Final = "2022-11-28"
USER_AGENT: Final = "code-companion"
API_TIMEOUT_SECONDS: Final = 30
COMMENTS_PAGE_SIZE: Final = 100
HTTP_FORBIDDEN: Final = 403
NETWORK_ERROR_STATUS: Final = 0
API_ERROR_DETAIL_CHARS: Final = 200
COMMENT_MARKER: Final = "<!-- code-companion-report -->"


class CommentAction(StrEnum):
    CREATED = "created"
    UPDATED = "updated"


REPORT_TITLE: Final = "PMAT Cyclomatic Complexity"
MAX_COMMENT_CHARS: Final = 60_000  # GitHub's comment limit is 65,536
MAX_OFFENDER_ROWS: Final = 50
ERROR_TAIL_CHARS: Final = 1500
SHA_DISPLAY_LENGTH: Final = 7
OFFENDER_TABLE_HEADER: Final = (
    "| File | Function | Line | Cyclomatic |",
    "| --- | --- | ---: | ---: |",
)

FAIL_NOTE_TEMPLATE: Final = "> This check fails when a changed function's cyclomatic complexity exceeds {limit}."
INVALID_MAX_CYCLOMATIC_MESSAGE: Final = f"max-cyclomatic must be an integer >= {MIN_MAX_CYCLOMATIC}"
NO_FILES_MESSAGE: Final = "No analyzable files changed."
CLEAN_MESSAGE: Final = "No function in the changed files exceeds the threshold."
LISTING_TRUNCATED_WARNING: Final = "Note: PMAT omitted some files from its listing, so this report may be incomplete."
ANALYSIS_FAILED_MESSAGE: Final = "The complexity analysis could not be completed."
COMMENT_TRUNCATED_NOTE: Final = "\n\n_...report truncated; see the job summary for the full report._"

GROUP_DETECT_FILES: Final = "Detect changed files"
GROUP_RUN_PMAT: Final = "Run PMAT"
SHALLOW_HISTORY_WARNING: Final = (
    "Could not determine changed files (shallow history?); analyzing the whole repo. "
    "Use actions/checkout with fetch-depth: 0."
)
NO_TOKEN_WARNING: Final = "No github-token provided; skipping the PR comment"
COMMENT_FORBIDDEN_WARNING: Final = (
    "Could not post the PR comment (403): the token is read-only (e.g. a forked PR) or lacks "
    "`pull-requests: write`. The job summary still has the report."
)
OUTPUT_TOO_LARGE_WARNING: Final = "The JSON report exceeds the step-output size limit; `pmat-json` omits the per-file details"
PMAT_NOT_FOUND_MESSAGE: Final = "`pmat` was not found on PATH; the install step must have failed"
