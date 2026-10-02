from code_companion.constants import ZERO_SHA
from code_companion.git_diff import changed_files


def test_push_lists_files_changed_since_before(git_repo, make_config):
    config = make_config(
        event_name="push",
        event={"before": git_repo.first},
        sha=git_repo.second,
        workspace=git_repo.path,
    )

    assert sorted(changed_files(config)) == ["a.py", "b.py"]


def test_pull_request_lists_files_between_base_and_head(git_repo, make_config):
    event = {"pull_request": {"base": {"sha": git_repo.first}, "head": {"sha": git_repo.second}}}
    config = make_config(event_name="pull_request", event=event, workspace=git_repo.path)

    assert sorted(changed_files(config)) == ["a.py", "b.py"]


def test_new_branch_push_falls_back_to_previous_commit(git_repo, make_config):
    config = make_config(
        event_name="push",
        event={"before": ZERO_SHA},
        sha=git_repo.second,
        workspace=git_repo.path,
    )

    assert sorted(changed_files(config)) == ["a.py", "b.py"]


def test_event_without_diff_base_analyzes_whole_repo(make_config):
    config = make_config(event_name="workflow_dispatch")

    assert changed_files(config) is None
