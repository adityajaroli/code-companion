from code_companion import github_api as gh
from code_companion.constants import COMMENT_MARKER, CommentAction


def test_set_output_writes_multiline_value(monkeypatch, tmp_path):
    output_file = tmp_path / "output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

    gh.set_output("report", "line one\nline two")

    text = output_file.read_text()
    assert text.startswith("report<<ghadelimiter_")
    assert "line one\nline two" in text


def test_upsert_creates_comment_when_none_exists(api):
    action = gh.upsert_pr_comment("tok", "owner/repo", 5, f"{COMMENT_MARKER} body")

    assert action == CommentAction.CREATED
    method, url, body = api.calls[-1]
    assert method == "POST"
    assert url.endswith("/repos/owner/repo/issues/5/comments")
    assert body == {"body": f"{COMMENT_MARKER} body"}


def test_upsert_updates_the_existing_marker_comment(api):
    api.existing = [{"id": 1, "body": "unrelated"}, {"id": 99, "body": f"{COMMENT_MARKER} old"}]

    action = gh.upsert_pr_comment("tok", "owner/repo", 5, f"{COMMENT_MARKER} new")

    assert action == CommentAction.UPDATED
    method, url, body = api.calls[-1]
    assert method == "PATCH"
    assert url.endswith("/repos/owner/repo/issues/comments/99")
    assert body == {"body": f"{COMMENT_MARKER} new"}
