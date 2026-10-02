from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .constants import (
    DEFAULT_MAX_CYCLOMATIC,
    DEFAULT_RUNNER_TEMP,
    DEFAULT_WORKSPACE,
    ENCODING,
    INVALID_MAX_CYCLOMATIC_MESSAGE,
    MIN_MAX_CYCLOMATIC,
    EnvVar,
)


@dataclass(frozen=True)
class Config:
    token: str
    pmat_version: str
    max_cyclomatic: int
    event_name: str
    event: dict = field(repr=False)
    sha: str
    repository: str
    workspace: Path
    runner_temp: Path

    @property
    def pr_number(self) -> int | None:
        number = (self.event.get("pull_request") or {}).get("number")
        return int(number) if number is not None else None

    @classmethod
    def from_env(cls) -> Config:
        """Raises ValueError for an invalid `max-cyclomatic` or a malformed event payload."""
        env = os.environ
        return cls(
            token=env.get(EnvVar.INPUT_GITHUB_TOKEN, ""),
            pmat_version=env.get(EnvVar.INPUT_PMAT_VERSION, "").strip(),
            max_cyclomatic=_parse_max_cyclomatic(env.get(EnvVar.INPUT_MAX_CYCLOMATIC)),
            event_name=env.get(EnvVar.GITHUB_EVENT_NAME, ""),
            event=_load_event(env.get(EnvVar.GITHUB_EVENT_PATH)),
            sha=env.get(EnvVar.GITHUB_SHA, ""),
            repository=env.get(EnvVar.GITHUB_REPOSITORY, ""),
            workspace=Path(env.get(EnvVar.GITHUB_WORKSPACE, DEFAULT_WORKSPACE)).resolve(),
            runner_temp=Path(env.get(EnvVar.RUNNER_TEMP, DEFAULT_RUNNER_TEMP)),
        )


def _parse_max_cyclomatic(raw: str | None) -> int:
    if raw is None or not raw.strip():
        return DEFAULT_MAX_CYCLOMATIC
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(INVALID_MAX_CYCLOMATIC_MESSAGE) from None
    if value < MIN_MAX_CYCLOMATIC:
        raise ValueError(INVALID_MAX_CYCLOMATIC_MESSAGE)
    return value


def _load_event(path: str | None) -> dict:
    if not path or not Path(path).is_file():
        return {}
    return json.loads(Path(path).read_text(encoding=ENCODING))
