# Continuous integration

_Role: run the checks that keep HERMES releasable and its specs bijective, and publish the code map. Files covered:
`.github/workflows/checks.yml`, `.github/workflows/pages.yml`, `.github/pull_request_template.md`. Tests: the
workflow runs themselves._

Status: implemented on 2026-11-25. Ported from the Kairos workflows ("Kairos checks", "Pages") and from the HERMES CI
in dotfiles. Ticket: none.

## 1. Business need

### Problem and goal

A change must not reach `main` with failing tests, or with a spec that describes code that does not exist. Checking
this by hand is forgotten, so GitHub runs it on every PR and every push.

### Requirements

- **R1.** On every PR and every push to `main`, with no path filter, the "HERMES checks" workflow runs the unit tests
  of `tools/` and the code map check (`code-map.md` R3). A failure turns the PR red.
- **R2.** In the same workflow, the application's test suite (`pytest`) runs when `pyproject.toml` exists. Before the
  application code is migrated, the job succeeds without doing anything.
- **R3.** A new commit on a PR cancels the PR's previous run. Runs on `main` and manual runs are never cancelled.
- **R4.** On a push to `main` that touches `app/`, `tools/`, `docs/spec/`, the logo or the workflow, the "Pages"
  workflow publishes the code map at `/code/`. The site root redirects to it.
- **R5.** The PR template asks for the spec, bijectivity, code and commit checks of `CLAUDE.md`, in English.

### Success criteria

- R1 to R3: "HERMES checks" is green on the first commit of `main`, and its two jobs run in parallel.
- R4: `https://skohscripts.github.io/hermes/code/` shows the map of the latest commit of `main`.

### Out of scope / deferred

- Release workflow (desktop executable on a `vX.Y.Z` tag, ported from dotfiles `release.yml`): it comes with the
  application code.
- Linting and formatting: no tool is chosen yet.

## 2. Technical solution

### Design

- `checks.yml`, job `tools`: Python 3.11 (the minimum HERMES supports),
  `python3 -m unittest discover -s tools -p 'test_*.py'`, then `python3 tools/make_code_map.py --check`.
- `checks.yml`, job `app`: every step carries `if: hashFiles('pyproject.toml') != ''`. The system libraries of
  WeasyPrint (Pango, Cairo, GDK-Pixbuf) are installed before `pip install -e ".[dev]"` and `pytest`.
- `pages.yml`: `make_code_map.py --html "$RUNNER_TEMP/site/code/index.html" --stamp "$GITHUB_SHA"`, copy of
  `assets/logo.svg` to the site root (the page loads `../logo.svg`), a redirecting `index.html`, then
  `actions/upload-pages-artifact` and `actions/deploy-pages`.

### Decisions and pitfalls

- **`hashFiles()` in step conditions, not in the job condition** (2026-11-25). GitHub does not offer `hashFiles()` in
  `jobs.<id>.if`. Without a guard, `pytest` exits with status 5 ("no tests collected") and the job would be red from
  day one.
- **Concurrency group per PR branch, unique per run otherwise**, copied from Kairos. A superseded PR run is useless,
  but a run on `main` must finish.
- **Checks without a path filter** (as in Kairos): they take seconds, and a filter is the usual way a check gets
  skipped by mistake.
- **Pages from GitHub Actions**, not from a `gh-pages` branch. Generated files never enter the history.
