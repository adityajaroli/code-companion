# code-companion

Automatically check the cyclomatic complexity of the code you change in every push and pull request, using the [PMAT](https://github.com/paiml/paiml-mcp-agent-toolkit) complexity analyzer.

## Features

- **Automated Complexity Analysis**: Measures cyclomatic complexity for the files changed in a push or pull request
- **Pull Request Integration**: Posts the report as a single sticky comment that is updated on every push, and writes it to the job summary
- **Configurable Threshold**: Set the complexity limit that fits your project with `max-cyclomatic`
- **Zero Setup**: Installs a pinned, checksum-verified PMAT release for you; no tools or dependencies to install
- **Multi-language Support**: Works with the languages PMAT can analyze; file types it can't analyze are skipped
- **Machine-readable Output**: Writes a JSON report and exposes the results as step outputs

## Quick Start

Add this workflow to your repository at `.github/workflows/complexity-check.yml`:

```yaml
name: Code Complexity Check

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
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0   # required so the action can diff against the base commit

      - name: Run complexity analysis
        uses: <owner>/code-companion@v1
        with:
          max-cyclomatic: 20
```

The step fails when a function in the changed files exceeds `max-cyclomatic`, and the report is always posted first so the failure comes with its explanation.

## Configuration

### Inputs

| Input | Description | Default | Required |
|-------|-------------|---------|----------|
| `max-cyclomatic` | Maximum allowed cyclomatic complexity per function. Functions **above** this value are reported and fail the step. Must be an integer >= 1. | `20` | No |
| `pmat-version` | PMAT release to install (without the leading `v`) | `3.42.0` | No |
| `github-token` | Token used to post the PR comment. Needs `pull-requests: write` on `pull_request` events. | `${{ github.token }}` | No |

### Outputs

| Output | Description |
|--------|-------------|
| `report-path` | Path to the generated Markdown report file |
| `json-report-path` | Path to the JSON report file (changed files only) |
| `violations-count` | Number of changed functions with cyclomatic complexity over `max-cyclomatic` |
| `pmat-json` | The same JSON report as a compact string. If it would exceed GitHub's 1 MB output limit, the per-file details are dropped (with a warning) but `violations` is kept; the file at `json-report-path` is always complete. |

Both report files are written to `$RUNNER_TEMP` (`code-companion-report.md` and `code-companion-report.json`).

### Example Configurations

**Strict complexity checking:**
```yaml
- uses: <owner>/code-companion@v1
  with:
    max-cyclomatic: 10
```

**Relaxed checking:**
```yaml
- uses: <owner>/code-companion@v1
  with:
    max-cyclomatic: 30
```

**Pin a specific PMAT version:**
```yaml
- uses: <owner>/code-companion@v1
  with:
    pmat-version: "3.42.0"
```

## What You'll See

When complexity violations are found, the action will:

1. **Fail the check**
2. **Post a report** in your PR (and in the job summary) with:
   - The threshold and how many functions in how many changed files are over it
   - A table of the offending functions: file, function, line and cyclomatic complexity, worst first (up to 50 rows)
   - A footer with the PMAT version and commit

When nothing exceeds the limit, the check passes and the report says so. If no analyzable files changed, the report says **"No analyzable files changed."**

### Sample PR Comment

```markdown
## PMAT Cyclomatic Complexity

> This check fails when a changed function's cyclomatic complexity exceeds 20.

- **Threshold:** cyclomatic complexity > 20
- **Over threshold:** 2 function(s) in 2 changed file(s)

| File | Function | Line | Cyclomatic |
| --- | --- | ---: | ---: |
| `src/server/watcher.rs` | `watch` | 12 | **27** |
| `src/utils/parser.js` | `parseData` | 45 | **23** |

<sub>PMAT 3.42.0 - commit `abc1234`</sub>
```

The comment is identified by a hidden marker (`<!-- code-companion-report -->`): an existing comment is updated in place, otherwise one is created. It is truncated below GitHub's 65,536-character limit with a pointer to the job summary. On `push` events there is no comment, only the job summary and the report files.

## Why Use This Action?

- **Maintain Code Quality**: Catch overly complex code before it reaches production
- **Review Only What Changed**: Existing violations in files you didn't touch never fail a PR
- **Team Consistency**: Enforce one complexity standard across your whole team
- **Early Detection**: Surface maintenance problems during code review, with the report right in the PR

## Advanced Usage

### Custom Workflow Triggers

```yaml
on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
    paths:
      - 'src/**'
      - 'lib/**'
```

### Matrix Builds

```yaml
strategy:
  matrix:
    max-complexity: [10, 15, 20]
steps:
  - uses: <owner>/code-companion@v1
    with:
      max-cyclomatic: ${{ matrix.max-complexity }}
```

There is one sticky comment per pull request, so matrix legs overwrite each other's comment. Use a matrix when you rely on the job summary or the outputs rather than the PR comment.

### Using the Outputs and Reports

The step fails when there are violations, so later steps are skipped unless they use `if: always()`. Use it whenever you read outputs or upload the reports:

```yaml
- id: complexity
  uses: <owner>/code-companion@v1
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: complexity-reports
    path: |
      ${{ steps.complexity.outputs.report-path }}
      ${{ steps.complexity.outputs.json-report-path }}
```

The JSON report is limited to the changed files. Its keys are `pmat_version`, `max_cyclomatic`, `violations_count`, `violations` (each offender as `file`, `name`, `line`, `end_line` and `cyclomatic`) and `files` (PMAT's own per-file data for the changed files it lists, with repo-relative paths). Because the action runs PMAT with `--max-cyclomatic`, PMAT lists only files that have a function over the limit, so `files` does too.

If the analysis itself fails (PMAT crashes or prints no report), only `report-path` is set; `json-report-path`, `violations-count` and `pmat-json` are empty.

## Understanding Complexity Metrics

- **Cyclomatic Complexity**: Measures the number of linearly independent paths through a function
- **Recommended Thresholds**:
  - Low complexity: 1-10
  - Moderate complexity: 11-20
  - High complexity: 21+ (consider refactoring)

PMAT also reports cognitive complexity, but this action only checks cyclomatic complexity and ignores PMAT's own violation list.

## What Gets Analyzed

| Event | Files analyzed |
| --- | --- |
| `pull_request` | Files added/modified/renamed between `base.sha` and `head.sha` |
| `push` | Files added/modified/renamed between `before` and the pushed commit |
| Anything else (e.g. `workflow_dispatch`) | The whole repo |

If the diff base can't be resolved (new branch, force push, shallow clone), the action falls back to `HEAD~1..HEAD`, and then to the whole repo with a warning. Deleted files are ignored. File types PMAT has no complexity analyzer for (e.g. `.json`, `.md`) are skipped by PMAT itself.


## Contributing

Found a bug or have a feature request? Please [open an issue](../../issues) or submit a pull request.

### Tests

```
pip install pytest
pytest                      # all tests
pytest tests/test_main.py   # one flow end to end
pytest -k violation -s      # one test, with the action's log output shown
pytest --pdb                # drop into the debugger on failure
```

Tests need `git` on `PATH` (they build a real temporary repo) but never call PMAT or GitHub: `conftest.py` provides a fake `pmat` and the GitHub API is replaced in-process.


## License

This action is distributed under the MIT License. See `LICENSE` for more information.
