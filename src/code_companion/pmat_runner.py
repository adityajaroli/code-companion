from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import github_api as gh
from .config import Config
from .constants import (
    ERROR_TAIL_CHARS,
    GROUP_RUN_PMAT,
    MAX_OUTPUT_JSON_CHARS,
    MODULE_PSEUDO_FUNCTION_PREFIX,
    NO_COLOR_ENV,
    OUTPUT_TOO_LARGE_WARNING,
    PMAT_ANALYSIS_TIMEOUT_SECONDS,
    PMAT_ANALYZE_PREFIX,
    PMAT_ANALYZE_SUFFIX,
    PMAT_EXECUTABLE,
    PMAT_MAX_CYCLOMATIC_FLAG,
    PMAT_NOT_FOUND_MESSAGE,
    PMAT_VERSION_COMMAND,
    PMAT_VERSION_TIMEOUT_SECONDS,
)


class PmatError(Exception):
    pass


@dataclass(frozen=True)
class FunctionResult:
    file: str
    name: str
    line: int
    end_line: int
    cyclomatic: int


@dataclass(frozen=True)
class AnalysisResult:
    pmat_version: str
    max_cyclomatic: int
    files: list[dict] = field(repr=False)
    functions: list[FunctionResult]
    truncated: bool  # PMAT omitted files from its listing
    ran: bool = True  # False when there was nothing to analyze and PMAT was not run

    @property
    def offenders(self) -> list[FunctionResult]:
        over = (f for f in self.functions if f.cyclomatic > self.max_cyclomatic)
        return sorted(over, key=lambda f: (-f.cyclomatic, f.file, f.line))


def empty_result(config: Config) -> AnalysisResult:
    return AnalysisResult(
        pmat_version=_pmat_version(config.pmat_version),
        max_cyclomatic=config.max_cyclomatic,
        files=[],
        functions=[],
        truncated=False,
        ran=False,
    )


def analyze_command(max_cyclomatic: int) -> list[str]:
    return [*PMAT_ANALYZE_PREFIX, PMAT_MAX_CYCLOMATIC_FLAG, str(max_cyclomatic), *PMAT_ANALYZE_SUFFIX]


def run_pmat(config: Config, only: set[str] | None) -> AnalysisResult:
    version = _pmat_version(config.pmat_version)
    command = analyze_command(config.max_cyclomatic)

    gh.group(GROUP_RUN_PMAT)
    print("$ " + " ".join(command))
    try:
        proc = subprocess.run(
            command,
            cwd=config.workspace,
            capture_output=True,
            text=True,
            timeout=PMAT_ANALYSIS_TIMEOUT_SECONDS,
            env={**os.environ, **NO_COLOR_ENV},
        )
    except FileNotFoundError:
        raise PmatError(PMAT_NOT_FOUND_MESSAGE) from None
    except subprocess.TimeoutExpired:
        raise PmatError(f"PMAT did not finish within {PMAT_ANALYSIS_TIMEOUT_SECONDS}s") from None

    data, banner = _split_output(proc.stdout)
    if banner.strip():
        print(banner.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip())
    print(f"pmat exit code: {proc.returncode}")
    gh.endgroup()

    if data is None or "files" not in data:
        tail = (proc.stderr.strip() or banner.strip())[-ERROR_TAIL_CHARS:]
        raise PmatError(f"No PMAT JSON report found (exit code {proc.returncode}): {tail}")

    return _parse(data, version, config, only)


def _pmat_version(fallback: str) -> str:
    try:
        proc = subprocess.run(
            PMAT_VERSION_COMMAND, capture_output=True, text=True, timeout=PMAT_VERSION_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.SubprocessError):
        return fallback
    lines = proc.stdout.strip().splitlines()
    return lines[0].removeprefix(PMAT_EXECUTABLE).strip() if lines else fallback


def _split_output(text: str) -> tuple[dict | None, str]:
    """Find the JSON report in `text`. Returns (report or None, remaining non-JSON text)."""
    decoder = json.JSONDecoder()
    index = 0
    while (index := text.find("{", index)) != -1:
        if index == 0 or text[index - 1] == "\n":
            try:
                obj, end = decoder.raw_decode(text, index)
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, dict):
                return obj, text[:index] + text[end:]
        index += 1
    return None, text


def _normalize(path: str, workspace: Path) -> str:
    """Make a PMAT-reported path repo-relative with forward slashes (PMAT emits './src/x.py')."""
    p = Path(path)
    if p.is_absolute():
        try:
            p = p.relative_to(workspace)
        except ValueError:
            pass
    return p.as_posix().removeprefix("./")


def _parse(data: dict, version: str, config: Config, only: set[str] | None) -> AnalysisResult:
    files: list[dict] = []
    functions: list[FunctionResult] = []
    for entry in data.get("files", []):
        path = _normalize(entry.get("path", ""), config.workspace)
        if not path or (only is not None and path not in only):
            continue
        files.append({**entry, "path": path})
        for fn in entry.get("functions", []):
            name = fn.get("name", "")
            cyclomatic = (fn.get("metrics") or {}).get("cyclomatic")
            if name.startswith(MODULE_PSEUDO_FUNCTION_PREFIX) or not isinstance(cyclomatic, int):
                continue
            line = int(fn.get("line_start") or 0)
            functions.append(FunctionResult(path, name, line, int(fn.get("line_end") or line), cyclomatic))
    return AnalysisResult(
        pmat_version=version,
        max_cyclomatic=config.max_cyclomatic,
        files=files,
        functions=functions,
        truncated=bool(data.get("files_truncated")),
    )


def report_data(result: AnalysisResult) -> dict:
    return {
        "pmat_version": result.pmat_version,
        "max_cyclomatic": result.max_cyclomatic,
        "violations_count": len(result.offenders),
        "violations": [asdict(f) for f in result.offenders],
        "files": result.files,
    }


def output_json(result: AnalysisResult) -> str:
    text = json.dumps(report_data(result), separators=(",", ":"))
    if len(text) <= MAX_OUTPUT_JSON_CHARS:
        return text
    gh.warning(OUTPUT_TOO_LARGE_WARNING)
    without_files = {**report_data(result), "files": [], "truncated": True}
    return json.dumps(without_files, separators=(",", ":"))
