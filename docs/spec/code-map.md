# Code map

_Role: describe how the HERMES code is organised (packages, modules, declarations, imports, and the specs that cite
them) from a single source, and check that specs only describe code that exists. Files covered:
`tools/make_code_map.py`, `.github/workflows/checks.yml`, `.github/workflows/pages.yml`, `CLAUDE.md` (§ Code map).
Tests: `tools/test_make_code_map.py`._

Status: implemented on 2026-11-25. Ported from the Kairos code map (Kotlin, regular expressions) and rewritten for
Python with `ast`. Ticket: none.

## 1. Business need

### Problem and goal

- **Claude Code** must locate a feature without reading dozens of files. It needs a short, always-correct summary: for
  each module, what it declares, what it imports, and which spec describes it.
- **Contributors** want to see how the repository is organised at a glance, without cloning it, on a public page that
  stays up to date.
- **Bijectivity** between specs and code must not rely on memory alone. A machine catches the direction it can: a spec
  that cites a file, a function or a test that does not exist.

### Users and roles

Claude Code and contributors read the index and the page. CI runs the check. Nobody needs a permission.

### Requirements

- **R1.** When `python3 tools/make_code_map.py --index [filter]` runs, HERMES writes Markdown to standard output, one
  section per package. Each module line gives its path, line count, public top-level declarations, project imports,
  and the specs that cite it, or "no spec". The filter keeps the modules whose dotted name or path contains it.
- **R2.** A spec cites a source file with a backticked token ending in `.py`: a full path, a path tail, or a bare file
  name. A path abbreviated with "..." or "…" is read from after the last ellipsis. A `::name` suffix points to a
  top-level function or class, or to a `Class.method`. A glob such as `test_*.py` or the bare extension `.py` is not a citation. A module is
  linked to every spec that cites it.
- **R3.** When `--check` runs, HERMES exits with status 1 if an implemented spec cites a `.py` file that matches no file
  in the repository, or a `::name` that the matched files do not declare. It lists each error. A spec whose status line
  starts with "Status:" and says "not implemented" is skipped. Production modules that no spec cites are listed as
  warnings and do not fail the run.
- **R4.** When `--html FILE` runs, HERMES writes one self-contained page. It shows a graph with one column per package,
  one box per module and one curve per import. Selecting a module highlights what it imports and what imports it. Below
  the graph, a searchable list shows each module's file (linked to GitHub), declarations, imports and specs. With
  `--stamp`, the page shows the commit. The page text is in English.
- **R5.** For the same code, the output is identical byte for byte, apart from the stamp.
- **R6.** On every push to `main` that touches code, specs or the generator, the page is published at
  `https://skohscripts.github.io/hermes/code/`.

### Business rules and data

- Source directories: `app` and `tools` by default (`--src`), relative to `--root` (the repository by default). Missing
  directories are skipped, so the map works before the application code is migrated.
- Production module: any `.py` file in a source directory. Excluded: files named conftest.py, test_*.py or *_test.py, anything
  under a `tests` directory, and the directories `.git`, `.venv`, `venv`, `__pycache__`, `node_modules`, `build`,
  `dist`, `_site`.
- Public declaration: a top-level `class`, `def` or `async def` whose name does not start with `_`.
- Project import: an `import` or `from … import` anywhere in the module, including inside functions, that resolves to
  another project module. Relative imports are resolved against the module's package. `from pkg import name` points to
  the module `pkg.name` if it exists, otherwise to `pkg`.
- A package's __init__.py without declarations only re-exports, so it never raises the "no spec" warning.

### Errors and edge cases

- An empty source tree gives an empty index, an empty page and a passing check.
- A file that does not parse makes the script fail with Python's `SyntaxError`. The CI must not publish a map of
  broken code.

### Non-functional requirements

- Standard library only, Python ≥ 3.11. The whole current HERMES (44 modules) is mapped in about 0.2 s.
- The page loads nothing from a third party: no script, stylesheet or font from another origin. It follows the system
  light or dark theme and stays readable at 360 px (the graph scrolls horizontally, the list does not).

### Success criteria

- R1: modules, declarations, filter and "no spec" (`tools/test_make_code_map.py::CodeMapTest.test_reads_modules_and_public_declarations`,
  `tools/test_make_code_map.py::CodeMapTest.test_index_filter_and_unlinked_modules`).
- R1: relative, absolute and function-level imports resolve, and external ones are ignored
  (`tools/test_make_code_map.py::CodeMapTest.test_relative_absolute_and_nested_imports_resolve`).
- R2: full path, abbreviated path and bare name link files to specs
  (`tools/test_make_code_map.py::CodeMapTest.test_links_files_to_specs`).
- R3: a consistent tree passes, dead references are reported, unimplemented specs are skipped, and the exit code
  follows (`tools/test_make_code_map.py::CodeMapTest.test_check_passes_on_a_consistent_tree`,
  `tools/test_make_code_map.py::CodeMapTest.test_check_reports_code_the_spec_describes_but_does_not_exist`,
  `tools/test_make_code_map.py::CodeMapTest.test_check_skips_specs_not_implemented_yet`,
  `tools/test_make_code_map.py::CodeMapTest.test_main_check_exit_code`).
- R4: no third-party resource, and edges and spec links present
  (`tools/test_make_code_map.py::CodeMapTest.test_page_is_self_contained`).
- R5: same input, same page (`tools/test_make_code_map.py::CodeMapTest.test_output_is_deterministic`).
- R6: the "Pages" workflow is green on `main` (checked on GitHub, not by a unit test).

### Out of scope / deferred

- A call graph between functions: unstable from one commit to the next and hard to read. Modules are enough.
- Jinja templates, static assets and scripts outside the source directories.
- An index file committed to the repository. It would go stale between commits; generating it on demand is always
  correct.
- Failing on modules without a spec. Deferred until the code migrated from dotfiles is fully specified (see
  § Decisions).

## 2. Technical solution

### Design

`tools/make_code_map.py` works in four passes:

1. `read_sources` walks the source directories (`py_files`, `is_test`) and parses each file with `ast`.
   `declarations` keeps the public top-level declarations. `raw_imports` collects `(name, fallback)` pairs, which
   `read_sources` resolves to the longest known module that prefixes them.
2. `read_specs` reads `docs/spec/*.md`: the title (the first `# ` line), the tokens (`spec_tokens`, regular expression
   `SPEC_TOKEN_RE`), and whether the spec is implemented (`NOT_IMPLEMENTED_RE`).
3. `link_specs` links modules to specs with `matches`. That function also serves `check`, so the index and the check
   agree on what a citation is.
4. Outputs: `index` (Markdown), `check` (errors and warnings, using `top_level_names` for `::name`), `data` (JSON
   model), and `page` (HTML: `svg` lays out the graph in Python, `module_list` writes the list).

### Interfaces

| Option | Effect |
|--------|--------|
| `--root DIR` | Repository root (default: the parent of `tools/`). |
| `--src DIR…` | Source directories relative to the root (default `app tools`). |
| `--index [FILTER]` | Markdown index on standard output. |
| `--check` | Bijectivity check: errors and warnings on standard error, exit 1 on error. |
| `--html FILE` | Writes the page and creates missing directories. |
| `--json FILE` | Writes the model (sorted keys). |
| `--stamp TEXT` | Commit shown on the page (CI passes `$GITHUB_SHA`). |

Publication is described in `continuous-integration.md`.

### Traceability

| Req. | Code | Tests |
|------|------|-------|
| R1 | `tools/make_code_map.py::read_sources`, `tools/make_code_map.py::raw_imports`, `tools/make_code_map.py::index` | `tools/test_make_code_map.py::CodeMapTest.test_index_filter_and_unlinked_modules` |
| R2 | `tools/make_code_map.py::spec_tokens`, `tools/make_code_map.py::matches`, `tools/make_code_map.py::link_specs` | `tools/test_make_code_map.py::CodeMapTest.test_links_files_to_specs` |
| R3 | `tools/make_code_map.py::check`, `tools/make_code_map.py::main` | `tools/test_make_code_map.py::CodeMapTest.test_main_check_exit_code` |
| R4 | `tools/make_code_map.py::page`, `tools/make_code_map.py::svg`, `tools/make_code_map.py::module_list` | `tools/test_make_code_map.py::CodeMapTest.test_page_is_self_contained` |
| R5 | `tools/make_code_map.py::build` (everything sorted) | `tools/test_make_code_map.py::CodeMapTest.test_output_is_deterministic` |
| R6 | `.github/workflows/pages.yml` | the workflow run |

### Decisions and pitfalls

- **In-house generator rather than a plugin** (decided for Kairos on 2026-11-15, kept here). A page that updates itself
  must be produced by CI, without Claude. The same script also gives Claude its index, so there is one source.
- **`ast` rather than regular expressions** (2026-11-25). Kairos reads Kotlin with regular expressions because there is
  no parser in the standard library. Python ships one, so declarations and imports are exact: decorators, multi-line
  signatures and function-level imports are all handled.
- **Modules, not packages, as graph nodes** (2026-11-25). Kairos groups hundreds of files into packages. HERMES is a
  flat `app` package with about 40 modules, so a package-level graph would show two boxes.
- **`from pkg import name` resolution**. Without the `(name, fallback)` pair, `from . import redmine` would count both
  `app.clients` and `app.clients.redmine` as dependencies.
- **"No spec" is a warning, not an error** (2026-11-25). The code migrated from dotfiles had 30 modules out of 44 cited
  by no spec. Failing on them would block the migration. Switch them to errors once the migrated code is fully
  specified (the `shortcut:` comment in `main`).
- **Only `.py` citations are checked**. Workflow, template and configuration files are cited too, but stay unchecked
  until a spec cites one by mistake.
- **The page embeds only the links between modules as JSON**. Files, declarations and specs are already in the HTML.
- **Edges between modules of the same package** are arcs on the right of the column, bounded by the gap between two
  columns so they never cross the next one.
