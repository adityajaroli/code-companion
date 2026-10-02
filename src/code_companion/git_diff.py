from __future__ import annotations

import subprocess
from pathlib import Path

from . import github_api as gh
from .config import Config
from .constants import (
    FALLBACK_REVISION_RANGE,
    GIT_DIFF_COMMAND,
    GIT_TIMEOUT_SECONDS,
    GROUP_DETECT_FILES,
    PATH_SEPARATOR_NUL,
    PULL_REQUEST_EVENTS,
    SHALLOW_HISTORY_WARNING,
    ZERO_SHA,
    EventName,
)


def changed_files(config: Config) -> list[str] | None:
    """Return added/modified/renamed paths, or None for "whole repo".

    Revision ranges are tried in order until one works:
      pull_request: <base.sha>...<head.sha>
      push:         <before>..<sha>   (skipped for new branches, where `before` is all zeros)
      fallback:     HEAD~1..HEAD
    If none works (e.g. shallow history), returns None so the caller analyzes everything.
    Consumers should use `actions/checkout` with `fetch-depth: 0`.
    """
    gh.group(GROUP_DETECT_FILES)
    try:
        return _detect(config)
    finally:
        gh.endgroup()


def _candidate_ranges(config: Config) -> list[str] | None:
    """Revision ranges to try for this event, or None when the event has no diff base."""
    event = config.event
    ranges: list[str] = []
    if config.event_name in PULL_REQUEST_EVENTS:
        pr = event.get("pull_request") or {}
        base, head = (pr.get("base") or {}).get("sha"), (pr.get("head") or {}).get("sha")
        if base and head:
            ranges.append(f"{base}...{head}")
    elif config.event_name == EventName.PUSH:
        before = event.get("before")
        if before and before != ZERO_SHA and config.sha:
            ranges.append(f"{before}..{config.sha}")
    else:
        return None
    return [*ranges, FALLBACK_REVISION_RANGE]


def _detect(config: Config) -> list[str] | None:
    ranges = _candidate_ranges(config)
    if ranges is None:
        print(f"Event '{config.event_name}' has no diff base; analyzing the whole repo")
        return None

    for rev in ranges:
        files = _git_diff(rev, config.workspace)
        if files is not None:
            print(f"{rev}: {len(files)} changed file(s)")
            return files

    gh.warning(SHALLOW_HISTORY_WARNING)
    return None


def _git_diff(rev: str, cwd: Path) -> list[str] | None:
    try:
        proc = subprocess.run(
            [*GIT_DIFF_COMMAND, rev, "--"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        print(f"git diff {rev} failed: {proc.stderr.strip()[:300]}")
        return None
    return [path for path in proc.stdout.split(PATH_SEPARATOR_NUL) if path]
