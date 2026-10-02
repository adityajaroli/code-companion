from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid

from .constants import (
    API_ERROR_DETAIL_CHARS,
    API_TIMEOUT_SECONDS,
    API_VERSION,
    COMMENT_MARKER,
    COMMENTS_PAGE_SIZE,
    DEFAULT_API_URL,
    ENCODING,
    NETWORK_ERROR_STATUS,
    USER_AGENT,
    CommentAction,
    EnvVar,
)


class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(f"GitHub API {status}: {detail[:API_ERROR_DETAIL_CHARS]}")
        self.status = status


def _escape(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def group(title: str) -> None:
    print(f"::group::{_escape(title)}")


def endgroup() -> None:
    print("::endgroup::")


def warning(message: str) -> None:
    print(f"::warning::{_escape(message)}")


def error(message: str) -> None:
    print(f"::error::{_escape(message)}")


def mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}")


def set_output(name: str, value: str) -> None:
    """Write a step output using a random delimiter so values can't inject extra outputs."""
    path = os.environ.get(EnvVar.GITHUB_OUTPUT)
    if not path:
        print(f"{name}={value}")
        return
    delimiter = f"ghadelimiter_{uuid.uuid4().hex}"
    with open(path, "a", encoding=ENCODING) as fh:
        fh.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def write_summary(markdown: str) -> None:
    path = os.environ.get(EnvVar.GITHUB_STEP_SUMMARY)
    if path:
        with open(path, "a", encoding=ENCODING) as fh:
            fh.write(markdown + "\n")


def _request(token: str, method: str, url: str, body: dict | None = None):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT_SECONDS) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as exc:
        raise ApiError(exc.code, exc.read().decode(errors="replace")) from None
    except urllib.error.URLError as exc:
        raise ApiError(NETWORK_ERROR_STATUS, str(exc.reason)) from None
    return json.loads(payload) if payload else None


def upsert_pr_comment(token: str, repository: str, pr_number: int, body: str) -> CommentAction:
    api = os.environ.get(EnvVar.GITHUB_API_URL, DEFAULT_API_URL)
    comments_url = f"{api}/repos/{repository}/issues/{pr_number}/comments"

    page = 1
    while True:
        batch = _request(token, "GET", f"{comments_url}?per_page={COMMENTS_PAGE_SIZE}&page={page}")
        for comment in batch:
            if COMMENT_MARKER in (comment.get("body") or ""):
                comment_url = f"{api}/repos/{repository}/issues/comments/{comment['id']}"
                _request(token, "PATCH", comment_url, {"body": body})
                return CommentAction.UPDATED
        if len(batch) < COMMENTS_PAGE_SIZE:
            break
        page += 1

    _request(token, "POST", comments_url, {"body": body})
    return CommentAction.CREATED
