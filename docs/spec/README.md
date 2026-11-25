# Specifications

HERMES is specified before it is coded, and every spec stays **bijective** with the code. Every behaviour of the code
is described here, and nothing here describes code that does not exist. The workflow is in `CLAUDE.md`, and step by step
in the `hermes-spec` skill (`.claude/skills/hermes-spec/SKILL.md`).

## Index

One spec per functional domain. Add a row when you add a spec, and update the status when it ships.

| Spec | Scope | Status |
|------|-------|--------|
| [`code-map.md`](code-map.md) | Code map: index for Claude Code, public page, and the spec/code bijectivity check. | implemented |

## Template

Copy this skeleton into `docs/spec/<domain>.md`. Keep both parts, in this order. Delete the guidance lines in italics.

```markdown
# <Domain title>

_Role: <one sentence>. Files covered: <every source file, backticked, e.g. app/sync.py>. Tests: <test files>._

Status: <implemented in vX.Y.Z | specified on YYYY-MM-DD, not implemented>. Ticket: <#n or none>.

## 1. Business need

### Problem and goal
_Who has the problem, what it costs them today, what changes when it is solved._

### Users and roles
_Who uses it and with which permissions. Name each role._

### Requirements
_Numbered, testable, one behaviour each. IDs are never reused or renumbered; a dropped requirement stays as
"R4 (withdrawn on YYYY-MM-DD: reason)". Pattern: "When <trigger>, HERMES <observable response>."_
- **R1.** When …, HERMES …
- **R2.** …

### Business rules and data
_Rules, calculations and entities in business words, with every default and bound ("5 by default, ≥ 1")._

### Errors and edge cases
_Empty, huge, duplicated, concurrent, offline, unauthorised, malformed: what the user sees for each._

### Non-functional requirements
_Only the ones that apply, each measurable: performance budget, security and privacy, accessibility, i18n,
compatibility, observability, data retention._

### Success criteria
_Each requirement has at least one criterion, and each criterion names the test that proves it._
- R1: <criterion> (`tests/test_<domain>.py::test_<name>`)

### Out of scope / deferred
_What a reader could expect here and will not find, and why._

## 2. Technical solution

### Design
_Components, modules, data flow. Name the real files and functions._

### Data model and migrations
### Interfaces
_HTTP routes, CLI, configuration keys (name, type, default, bounds), file formats, external APIs._

### Traceability
| Req. | Code | Tests |
|------|------|-------|
| R1 | <backticked file or file::function> | <backticked test file::test> |

### Decisions and pitfalls
_One entry per decision: what was chosen, why, what was rejected, and the date (YYYY-MM-DD)._

### Open questions
_Must be empty before the status says implemented._

### Impacts on existing specs
_Only while the status says "not implemented": changes to report into other specs when this one ships._
```
