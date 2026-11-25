<!--
Title: in English, short, with the ticket reference when there is one, e.g. "Collaborative priorities per release [#12]".
Fill every section in English (CLAUDE.md § Pull requests). Delete the comments and the lines that do not apply.
Never paste private data: no customer names, internal URLs, tokens or database exports.
-->

## Summary

<!-- What changes for the user, in two to four sentences. -->

Closes #

## Changes

<!-- One line per logical change, ideally one per commit. -->

-

## Decisions reopened

<!-- Decisions already traced in docs/spec/ that this PR changes, with the spec section and why. "None" if none. -->

## Spec and documentation

- [ ] Spec written or updated **before** the code (`docs/spec/`, two parts: business need, technical solution)
- [ ] Every requirement has a success criterion that names its test, and the test exists
- [ ] Spec and code are bijective: every behaviour is described, nothing describes missing code (`python3 tools/make_code_map.py --check`); index `docs/spec/README.md` updated
- [ ] Small decisions traced in "Decisions and pitfalls", and the local "why" in code comments
- [ ] User-facing feature only: `README.md` updated; bug fix, refactor or internal decision: traced in the spec only

## Verification

- [ ] `python3 -m unittest discover -s tools -p 'test_*.py'`
- [ ] `pytest` (application code)
- [ ] Screens looked at in light and dark themes, and at phone width, for any visible change

## Commits

- [ ] English conventional commits, `type(scope): description [#<ticket>]`, one logical change each (skill `commit`)

## Notes for the reviewer

<!-- What is not done or not checked, known limits, follow-ups. -->
