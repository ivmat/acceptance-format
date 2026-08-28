# ADR-008: the schema is a generated artifact, never hand-written

**Status:** Accepted (2026-08)

## Context

`tools/acceptance_grammar.py` exists because a rule written twice, once per checker, did not stay
in step — the same `out-of-scope` rule drifted for a full day between the TOML validator and the
Markdown ledger checker before the shared module closed the gap. A machine-readable schema for the
TOML data model is the same risk one layer up: hand-writing `schema/*.schema.json` alongside
`tools/check_acceptance.py`'s registries recreates exactly the two-copies-of-one-rule shape the
grammar module exists to prevent, except the second copy would be a JSON file nobody runs a test
suite against. The format's own thesis — a machine-optimized TOML source of truth — is not honored
by a schema artifact that can silently say something the validator does not.

## Decision

`tools/emit_schema.py` builds the JSON Schema (draft 2020-12) programmatically, importing every
closed-vocabulary value from `tools/acceptance_grammar.py` and `tools/check_acceptance.py` rather
than copying it — a grade token, a band name, an evidence kind, a hash pattern each has exactly one
place they are spelled out, and this module reads it, never restates it. The schema is
**shape-normative only**: table/field presence, field types, closed-vocabulary membership. Every
constraint that spans more than one field — status/grade coherence, band reachability, a control's
carrier-family compatibility, hash recomputation and binding equality, weight-conditioned
requiredness, phrase floors, cross-claim id uniqueness, filesystem existence of a `record` pointer
— is semantics-normative and is deliberately absent from the schema's structural keywords; each is
instead named, by id, in the schema's own `x-semantic-only-rules` array and in the affected field's
`description`. `gates/run_all.sh` re-emits the schema to a temporary file and byte-compares it
against the committed one on every run — a mismatch fails the gate ("schema drift: run
`tools/emit_schema.py`"), so a hand-edit or a stale commit cannot survive past the next gate run.
Because Python's standard library ships no `jsonschema` package and this repo takes no third-party
dependency, `emit_schema.py` also carries a small, dependency-free structural interpreter
(`--check`) covering exactly the keyword set the emitted schema actually uses (`type`, `enum`,
`minLength`, `minimum`, `pattern`, `properties`, `required`, `additionalProperties`, `items`) — no
conditional keyword (`allOf`/`if`/`then`/`oneOf`/`anyOf`/`not`/`const`), because every conditional
obligation in the format is one of the semantic-only rules named above, and the schema never needs
to express one.

## Consequences

A closed vocabulary cannot say one thing in the schema and another in the validator, because there
is only one definition of it and the schema reads that definition at emit time. A third party or an
editor can validate a manifest's shape against the schema without running Python, but must not
mistake a schema-clean document for a certificate — the schema's own `x-semantic-only-rules` array
says, by name, everything it did not check. The naming carries the spec version:
`schema/acceptance-0.1.0-draft.schema.json` while `core.md` is UNSTABLE-UNTIL-FROZEN (`format.md`
"Stability"); at freeze the file is renamed `acceptance-0.1.0.schema.json`, dropping the `-draft`
suffix with no other change. Extending the schema's own keyword budget (a conditional, a `const`) requires extending
`_iter_errors` in lockstep, the same discipline a sibling project's own minimal
dependency-free JSON Schema interpreter documents for its own, larger keyword set (read as
precedent for shape only, not shared code — the two interpreters live in different repos,
independently, each sized to its own schema's needs).
