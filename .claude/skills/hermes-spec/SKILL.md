---
name: hermes-spec
description: Spec-first workflow of the HERMES repository. Write a complete, testable specification in docs/spec/ before any code, get it approved, then keep spec and code bijective (every behaviour described, nothing described that does not exist) and trace every micro-decision. Use before implementing anything (feature, fix, refactor), when writing or reviewing a spec, when the user describes something to build, and when checking that a spec and the code say the same thing.
---

# Spec-first workflow (HERMES)

The rule is in `CLAUDE.md`, and the spec template is in `docs/spec/README.md`. This skill makes them operational.
Follow the steps **in order**, and don't write production code before step 3.

A spec is complete when another developer could implement it without asking a question, and a tester could write every
test from it without reading the code.

## 0. Search before designing

Never re-decide what is already decided.

1. Read `docs/spec/README.md` and find the domains involved.
2. Locate the code: run `python3 tools/make_code_map.py --index <filter>`. The filter is a piece of a module name or
   path. Then `grep -rn "<keyword>" docs/spec/ app/`: code comments carry the local "why".
3. Read the "Decisions and pitfalls" and "Out of scope" sections of each domain involved. If the request contradicts
   a recorded decision, **say so** and offer to reopen it explicitly. Never work around it silently.

## 1. Frame the need with the user

Before writing anything:

- **State your assumptions**: platform, users, data volume, permissions, what "done" means. Ambiguity resolved
  silently is the most expensive kind of bug.
- **Ask the questions** whose answers change the spec, in one batch. Give each one a recommended answer, so the user
  can reply "ok". Don't ask what the code or the existing specs already answer.
- **Turn vague words into measurable criteria.** For example, "fast" becomes "the backlog of 2,000 issues renders in
  under 1 s". "Robust" becomes a list of error cases and the behaviour for each one. Then ask "are these the right
  targets?".
- **Size the change.** A small change is a few lines added to the existing domain spec. A project is a new spec,
  `docs/spec/<domain>.md`, added to the index. A spec covers one functional domain. Split one that covers two.

## 2. Write the spec

Copy the template from `docs/spec/README.md`. Fill both parts, in this order.

**Part 1, business need**: the "what" and the "why". No class or file names.

- **Requirements** are numbered `R1`, `R2`… One observable behaviour each, written as "When <trigger>, HERMES
  <response>". IDs are never renumbered or reused. A dropped requirement stays, marked "(withdrawn on YYYY-MM-DD:
  reason)".
- Cover the **unhappy paths** for each requirement: empty input, huge input, duplicates, concurrent edits, an external
  service that is down or slow, an unauthorised user, malformed data, partial failure. Each one gets a defined
  behaviour that the user can see.
- Write **every default and every bound** ("26 weeks by default, ≥ 1"), every limit, and every unit.
- Add **non-functional requirements** only when they apply, and make each one measurable: performance budget,
  security and privacy (what data leaves the machine, who can see what), accessibility, i18n, compatibility,
  observability, retention.
- **Success criteria**: every requirement has at least one, and each criterion names the test that will prove it, as
  `tests/test_<domain>.py::test_<behaviour>`. Name the test even before it exists. That is the contract.
- **Out of scope**: what a reader could expect and will not get, and why.
- Quote user-facing text in double quotes, exactly as it will appear.

**Part 2, technical solution**: the real "how".

- "Files covered" and "Traceability" cite the real paths in backticks (`app/sync.py`, `app/sync.py::run_sync`). The
  code map links modules to specs through these citations, and `--check` fails if one points at nothing.
- Data model and migrations, interfaces (routes, CLI, configuration keys with type, default and bounds), algorithms,
  error handling, security.
- **Decisions and pitfalls**: each entry gives what was chosen, why, the alternatives rejected, and the date.
- **Open questions**: allowed while drafting, and must be empty before the status says implemented.

**A spec that is not implemented yet** carries "Status: specified on YYYY-MM-DD, not implemented". It does **not**
modify existing specs. Instead, it lists "Impacts on existing specs (to report at implementation)" at the end. This
keeps the registry bijective: existing specs keep describing the code that exists. `--check` skips specs with this
status.

### Self-review before showing the spec

- [ ] Each requirement is testable and unambiguous. No "fast", "simple", "user-friendly", "etc.", "and so on",
      "if needed", "appropriately".
- [ ] Each requirement has its unhappy paths, its success criterion and a named test.
- [ ] Defaults, bounds and units are written everywhere.
- [ ] Part 1 contains no implementation, and part 2 names real files.
- [ ] No contradiction with a recorded decision, unless that decision is reopened explicitly.
- [ ] Nothing private: no customer, employer, server name, internal URL or real data (the repository is public).

## 3. Get approval

Show the user a short summary: requirements, key decisions, open questions. Then **wait for approval** before writing
production code. A small change to an existing spec can go ahead once you have stated it. A new spec cannot.

## 4. Implement

Implement the tests named in the success criteria first, then write the code that makes them pass. Each test
docstring starts with the requirement it proves (`"""sync R3: …"""`), so code → spec is greppable. Keep the local
"why" in code comments.

## 5. Trace in the spec (bijectivity)

Checklist before pushing:

- [ ] Every behaviour added or changed is described in part 1 **and** part 2.
- [ ] Nothing in the spec describes code that does not exist. Re-read each statement you touched and check the file
      name, function, default value and bound against the code.
- [ ] `python3 tools/make_code_map.py --check` reports no error. Check the warnings of the modules you touched: a
      module without a spec is a gap.
- [ ] The status is up to date ("not implemented" becomes "implemented in vX.Y.Z" or "implemented on YYYY-MM-DD"),
      and the open questions are empty.
- [ ] The "Impacts on existing specs" have been reported into those specs and then removed from the list.
- [ ] Micro-decisions made while coding (threshold, rounding, edge case, library pitfall) are in "Decisions and
      pitfalls", and the matching code comment carries the local "why".
- [ ] Every success criterion names a test that exists and passes.
- [ ] The index `docs/spec/README.md` is up to date.
- [ ] A spec/code gap noticed on the way is fixed in the same change, in the spec or in the code. For a behaviour that
      is intended and tested, the code is the reference.

## 6. README: only for a feature

- A user-facing feature gets a short usage description in `README.md`.
- A fix, a refactor or a technical decision is traced in the spec only, never in the README.

## Style of specs

- English, short sentences, no filler. Write dates as YYYY-MM-DD.
- Write defaults and bounds every time.
- A decision states what was chosen, why, and what was rejected.
- Cross-cutting references (architecture, design charter) are cited, not copied.
