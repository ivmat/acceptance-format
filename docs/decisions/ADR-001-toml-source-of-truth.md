# ADR-001: TOML is the source of truth; other views are generated

**Status:** Accepted (2026-08)

## Context

The format ships two representations of the same claims: a TOML manifest
(`acceptance.toml`, checked by `tools/check_acceptance.py`) and a rendered Markdown ledger
(checked by `tools/check_ledger.py`). Only one worked subject exists so far, and its Markdown
ledger predates the manifest schema — the two were written and checked independently, against the
same rules, rather than one derived from the other.

## Decision

The TOML manifest is the format's source of truth. A rendered Markdown ledger is a projection of a
manifest's claims for human reading. Where the two disagree, the manifest is authoritative and the
rendering has a bug. New subjects should author a manifest; a Markdown ledger, where one exists, is
tolerated as a legacy carrier, not a second source.

## Consequences

Cross-representation rules (grade vocabulary, watched-fail witnesses, status coherence) live in one
shared grammar module (`tools/acceptance_grammar.py`) both checkers import, so a rule cannot drift
between representations. The one shipped ledger (`examples/rs-verified-der/ENVELOPE.md`) is
grandfathered as hand-authored, not machine-projected, and is marked as such. Emitting a Markdown
view mechanically from a manifest is future work, not yet built.
