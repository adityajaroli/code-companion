# code-companion

A reusable GitHub Action that installs the [PMAT](https://github.com/paiml/paiml-mcp-agent-toolkit) CLI, measures **cyclomatic complexity** for the files changed in a push or pull request, and publishes the result as Markdown:

- to the **job summary**,
- to a **report file** (path exposed as an output), and
- on pull requests, to a single **sticky PR comment** that is updated on every push.

The step **fails when any function in the changed files has cyclomatic complexity above `max-cyclomatic`** (default 20; it also fails on genuine errors: PMAT can't be installed, crashes, or produces unparseable output). The report and PR comment are always published first, so the failure comes with its explanation.

## Quick start

```yaml
name: Complexity
on:
  push:
  pull_request:

permissions:
  contents: read
  pull-requests: write   # needed for the PR comment

jobs:
  complexity:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # required so the action can diff against the base commit
      - uses: <owner>/code-companion@v1
        with:
          max-cyclomatic: "20"   # optional; default is 20
```

## Inputs

| Name | Default | Description |
| --- | --- | --- |
| `github-token` | `${{ github.token }}` | Token used to post the PR comment. Needs `pull-requests: write` on `pull_request` events. |
| `max-cyclomatic` | `20` | Maximum allowed cyclomatic complexity per function, passed to PMAT as `--max-cyclomatic`. Functions with complexity **greater than** this value are reported and fail the step. Must be an integer >= 1. |
| `pmat-version` | `3.42.0` | PMAT release to install (without the leading `v`). |

## Outputs

| Name | Description |
| --- | --- |
| `report-path` | Path to the generated Markdown report file. |
| `json-report-path` | Path to the JSON report file (changed files only). |
| `violations-count` | Number of changed functions with cyclomatic complexity over `max-cyclomatic`. |
| `pmat-json` | The same JSON report as a compact string. If it would exceed GitHub's 1 MB output limit, the per-file details are dropped (with a warning) but `violations` is kept; the file at `json-report-path` is always complete. |

Both report files are written to `$RUNNER_TEMP` (`code-companion-report.md` and `code-companion-report.json`).

Things to know about the outputs:

- **The JSON is limited to the changed files**, like `violations-count` and the Markdown report. Its keys are `pmat_version`, `max_cyclomatic`, `violations_count`, `violations` (each offender as `file`, `name`, `line`, `end_line` and `cyclomatic`) and `files` (PMAT's own per-file data for the changed files it lists, with repo-relative paths). Because the action runs PMAT with `--max-cyclomatic`, PMAT lists only files that have a function over the limit, so `files` does too.
- **The step fails when there are violations**, so later steps are skipped unless they use `if: always()`. Use it whenever you read outputs or upload the reports.
- **If the analysis itself fails** (PMAT crashes or prints no report), only `report-path` is set; `json-report-path`, `violations-count` and `pmat-json` are empty.

Example: upload both reports as an artifact, also when the check fails.

```yaml
- id: pmat
  uses: <owner>/code-companion@v1
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: pmat-reports
    path: |
      ${{ steps.pmat.outputs.report-path }}
      ${{ steps.pmat.outputs.json-report-path }}
```

## What gets analyzed

| Event | Files analyzed |
| --- | --- |
| `pull_request` | Files added/modified/renamed between `base.sha` and `head.sha` |
| `push` | Files added/modified/renamed between `before` and the pushed commit |
| Anything else (e.g. `workflow_dispatch`) | The whole repo |

If the diff base can't be resolved (new branch, force push, shallow clone), the action falls back to `HEAD~1..HEAD`, and then to the whole repo with a warning. Deleted files are ignored. If nothing relevant changed, the report says **"No analyzable files changed."**

File types PMAT has no complexity analyzer for (e.g. `.json`, `.md`) are skipped by PMAT itself.

## The report

- A short note on when the check fails.
- The threshold (cyclomatic complexity > `max-cyclomatic`) and how many functions in how many changed files are over it.
- A table of offenders sorted by complexity (file, function, line, cyclomatic complexity), capped at 50 rows.
- A footer with the PMAT version and commit SHA.

On pull requests the comment is identified by a hidden marker (`<!-- code-companion-report -->`): an existing comment is updated in place, otherwise one is created. Comments are truncated below GitHub's 65,536-character limit with a pointer to the job summary. On `push` events there is no comment.

## Permissions and limitations

- **Fork PRs:** the token is read-only, so posting the comment fails with a 403. The action logs a warning and continues; the job summary still has the full report.
- **Runners:** Linux x86_64 only (e.g. `ubuntu-latest`). PMAT is installed from its pinned GitHub release, and the download is verified against the release's SHA256.
- **Checkout depth:** use `fetch-depth: 0`. With a shallow clone the action can only fall back to the whole repo.
- **Analysis mode:** PMAT currently reports `heuristic` analysis for Python; results can differ from AST-based tools.
- **Whole-repo run:** PMAT analyzes the whole repo on every run and the action keeps only the changed files. Very large repos may approach PMAT's 300 s timeout.
- **PMAT command:** the action always runs `pmat analyze complexity --fail-on-violation --max-cyclomatic <max-cyclomatic> --format json` (plus `--top-files` so no files are cut from the listing). Only the limit is configurable.
- **Failing on violations:** `--fail-on-violation` makes PMAT exit non-zero for violations anywhere in the repo. The action does not use PMAT's exit code for the verdict; it fails only when a function in the **changed files** is over the limit, so existing violations in untouched files never fail a PR. To block merges, mark the job as a required status check. A failed PR comment (e.g. fork PRs) only warns.
- **Cyclomatic only:** PMAT also reports cognitive complexity, but this action ignores it, along with PMAT's own violation list.

## How it works

1. `scripts/install_pmat.sh` downloads the pinned PMAT release, verifies its checksum and adds it to `PATH`.
2. `git_diff.py` determines the changed files for the event.
3. `pmat_runner.py` runs `pmat analyze complexity --format json`, locates the JSON in its output, and extracts per-function cyclomatic complexity (ignoring PMAT's `<module>` pseudo-function).
4. `report.py` renders the Markdown; `github_api.py` writes the summary, outputs and sticky comment using only `urllib`.

Runtime dependencies: Python standard library only. Inputs are passed through `env:` rather than interpolated into scripts.

```
action.yml
scripts/install_pmat.sh
src/code_companion/
  __main__.py     # entry point: python -m code_companion
  constants.py    # every fixed value: default limit, PMAT command parts, env var and output names, limits, report text
  config.py       # environment variables and the event payload
  git_diff.py     # changed-file detection
  pmat_runner.py  # run PMAT, parse JSON
  report.py       # Markdown rendering
  github_api.py   # workflow commands, outputs, summary, sticky comment
```

## Tests

```
pip install pytest
pytest                      # all tests
pytest tests/test_main.py   # one flow end to end
pytest -k violation -s      # one test, with the action's log output shown
pytest --pdb                # drop into the debugger on failure
```

Tests need `git` on `PATH` (they build a real temporary repo) but never call PMAT or GitHub: `conftest.py` provides a fake `pmat` and the GitHub API is replaced in-process.

| File | Flow covered |
| --- | --- |
| `test_config.py` | Reading inputs and the event payload, `max-cyclomatic` validation |
| `test_git_diff.py` | Changed files for push, pull request, new branch and non-diff events |
| `test_pmat_runner.py` | Finding PMAT's JSON, parsing offenders, non-zero PMAT exit, changed-file filtering, JSON size fallback, no report |
| `test_report.py` | Markdown report (sorted offenders, configured limit), clean and empty reports, comment truncation |
| `test_github_api.py` | Step outputs, creating and updating the sticky comment |
| `test_main.py` | Whole action: violation fails, clean run passes, sticky comment updated, no changed files, push event, 403 on comment, PMAT crash, invalid input |

## Code style

- **Comments:** do not add comments that restate the code. If the code is readable, no comment is needed. Add a comment only where the code is genuinely hard to read, or where the reason behind it is not obvious (a workaround, an external tool's quirk, a limit that comes from somewhere else).
- **Prefer readability over commentary:** use clear names, small functions and named constants instead of explaining unclear code in a comment.
- **Constants:** fixed values (limits, command parts, environment variable and output names, user-facing text) live in `src/code_companion/constants.py`.
- **No icons:** no emojis or icons in the code, reports or documentation.

## Releasing

1. Tag a semver release, e.g. `git tag v1.0.0 && git push origin v1.0.0`.
2. Move the floating major tag so consumers on `@v1` get updates: `git tag -f v1 v1.0.0 && git push -f origin v1`.
3. For maximum supply-chain safety, consumers can pin to a full commit SHA instead of `@v1`. Consider doing the same for `actions/setup-python` in `action.yml`.
4. To adopt a newer PMAT, bump the default of `pmat-version` in `action.yml` after checking that `pmat analyze complexity --format json` still produces the schema this action expects (`files[].functions[].metrics.cyclomatic`).
