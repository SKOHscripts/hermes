# HERMES development workflow

HERMES is an open-source steering tool for IT products, under development. Until the migration is done, the working
application lives in the `hermes/` directory of the SKOHscripts/dotfiles repository (Python, FastAPI, SQLAlchemy,
Jinja). This repository lays the foundations first: workflow, specs, code map, CI. The code moves here module by
module, each with its spec.

**Everything is in English**: code, comments, docstrings, logs, specs, README, commits, PRs, issues. This is a
deliberate break with the French of the dotfiles version. Translate what you migrate.

**Public repository**: never commit customer, employer or instance-specific data. That means no server names,
internal URLs, ticket contents, tokens or real exports. Examples use invented data.

## The four steps

Every contribution follows these steps, in this order (skill `hermes-spec`):

1. **Specify first.** Before implementing, write the spec: a few lines added to an existing domain spec for a small
   change, a new domain spec for a project. Get it approved before writing code.
2. **Implement.** Write the tests named by the spec's success criteria first, then the code.
3. **Trace in the spec.** The spec stays **exhaustive and bijective** with the code. Every behaviour of the code is
   described, and nothing in the spec describes code that does not exist. Small decisions that don't deserve a document
   but must not be re-decided go to "Decisions and pitfalls". The code comment carries the local "why"; the spec is the
   consolidated registry.
4. **Document in the README if, and only if, it is a user-facing feature.** A fix, a refactor or an internal decision
   is traced in the spec only.

## Where specs live

- `docs/spec/`: **one spec per functional domain**, with the index and the template in `docs/spec/README.md`.
- Each spec has two parts, in this order. **Part 1, business need**: problem, users, numbered requirements `R1…`,
  rules, errors, non-functional requirements, success criteria naming their tests, out of scope. **Part 2, technical
  solution**: real files and functions, interfaces, traceability table, decisions and pitfalls.
- A spec that is not implemented yet says so in its status line and does not modify the other specs; it lists its
  impacts on them instead.

## Code map

Before browsing the code to locate a feature, run `python3 tools/make_code_map.py --index <filter>`. The filter is a
piece of a module name or path, for example `sync` or `clients/`. The output lists modules, public declarations,
project imports and the specs that cite each one. The same source publishes `https://skohscripts.github.io/hermes/code/`
(`docs/spec/code-map.md`). A module marked "no spec" is a bijectivity gap.

## Traceability rules

- **Bijectivity**: every behaviour of the code has a spec trace, and every spec statement matches real code. Fix a gap
  you notice in the same change. `python3 tools/make_code_map.py --check` fails when a spec cites a file, function or
  test that does not exist.
- **Never re-decide** a recorded decision without reopening it explicitly. Search `docs/spec/` and the code comments
  before redesigning anything.
- Requirement IDs are stable. Tests start their docstring with the requirement they prove (`"""sync R3: …"""`).

## Repository skills (`.claude/skills/`)

- `hermes-spec`: the workflow above, step by step: framing questions, template, self-review, bijectivity checklist.
- `hermes-monte-carlo`: reproducible probabilistic forecasts in pure Python, and their statistical tests.
- `commit`: English conventional commits, `type(scope): description [#ticket]`, atomic, with partial staging that
  doesn't need `git add -p`.

## Checks before pushing

```bash
python3 -m unittest discover -s tools -p 'test_*.py'
python3 tools/make_code_map.py --check
pytest   # once the application code is here
```

CI runs the same commands on every PR (`docs/spec/continuous-integration.md`).

## Pull requests and commits

Titles, descriptions and review answers are in English, and fill every section of `.github/pull_request_template.md`.
Commits follow the `commit` skill.
