from __future__ import annotations

from .config import Config
from .constants import (
    ANALYSIS_FAILED_MESSAGE,
    CLEAN_MESSAGE,
    COMMENT_MARKER,
    COMMENT_TRUNCATED_NOTE,
    ERROR_TAIL_CHARS,
    FAIL_NOTE_TEMPLATE,
    LISTING_TRUNCATED_WARNING,
    MAX_COMMENT_CHARS,
    MAX_OFFENDER_ROWS,
    NO_FILES_MESSAGE,
    OFFENDER_TABLE_HEADER,
    REPORT_TITLE,
    SHA_DISPLAY_LENGTH,
)
from .pmat_runner import AnalysisResult, FunctionResult


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _header() -> list[str]:
    return [COMMENT_MARKER, f"## {REPORT_TITLE}", ""]


def _offender_row(f: FunctionResult) -> str:
    return f"| `{_cell(f.file)}` | `{_cell(f.name)}` | {f.line} | **{f.cyclomatic}** |"


def _offender_table(offenders: list[FunctionResult]) -> list[str]:
    lines = [*OFFENDER_TABLE_HEADER, *(_offender_row(f) for f in offenders[:MAX_OFFENDER_ROWS])]
    hidden = len(offenders) - MAX_OFFENDER_ROWS
    if hidden > 0:
        lines += ["", f"_...and {hidden} more._"]
    return lines


def build_report(config: Config, result: AnalysisResult) -> str:
    lines = [*_header(), FAIL_NOTE_TEMPLATE.format(limit=result.max_cyclomatic), ""]
    if not result.ran:
        lines.append(NO_FILES_MESSAGE)
    else:
        offenders = result.offenders
        files_with_offenders = len({f.file for f in offenders})
        lines += [
            f"- **Threshold:** cyclomatic complexity > {result.max_cyclomatic}",
            f"- **Over threshold:** {len(offenders)} function(s) in {files_with_offenders} changed file(s)",
            "",
        ]
        if result.truncated:
            lines += [LISTING_TRUNCATED_WARNING, ""]
        lines += _offender_table(offenders) if offenders else [CLEAN_MESSAGE]

    lines += ["", f"<sub>PMAT {result.pmat_version} - commit `{config.sha[:SHA_DISPLAY_LENGTH]}`</sub>"]
    return "\n".join(lines)


def error_report(config: Config, message: str) -> str:
    return "\n".join(
        [
            *_header(),
            ANALYSIS_FAILED_MESSAGE,
            "",
            "```text",
            message[-ERROR_TAIL_CHARS:],
            "```",
            "",
            f"<sub>commit `{config.sha[:SHA_DISPLAY_LENGTH]}`</sub>",
        ]
    )


def truncate_for_comment(report: str, limit: int = MAX_COMMENT_CHARS) -> str:
    if len(report) <= limit:
        return report
    cut = report[: limit - len(COMMENT_TRUNCATED_NOTE)].rsplit("\n", 1)[0]
    return cut + COMMENT_TRUNCATED_NOTE
