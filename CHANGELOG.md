# Changelog

## Unreleased

- The README opens with a plain-language introduction and a tiny worked example.
- The publication leak gates no longer ship in this repository. They must list the vocabulary
  they search for, so shipping them published that list. They now run before each export
  instead.
- The gate suite and the README quickstart now also run in a copy without git metadata
  (a source archive or "Download ZIP"): the protocol tool takes `--root`, like the format
  validator already did.

## 0.3.x — locked, not ratified

### 0.3.2 — 2026-09-27

Published: 2026-09-28

No normative change to the locked Class text. Repairs dangling internal cross-references in the
locked specification text and extends this release's own documentation (license notes, roadmap).

**Tools and examples.** Everything below is a tool- or example-level change, not a Class-text
change:

- A record declaring conflicting `method` and `kind` tokens is now refused, rather than silently
  read off whichever field happened to be checked first.
- `check-package`/`check-decision` now return exit 2 (INDETERMINATE) whenever the underlying
  format validator itself is indeterminate, instead of masking it behind a plain pass/fail.
- An inferred (undeclared) `epistemic_tier` is now capped by its evidence family's ceiling, the
  same B3 cap an explicitly declared tier was already held to.
- The public leak gate is repaired (several categories were silently inert due to a word-boundary
  construction bug) and extended with new categories.
- A new regression gate checks the shipped rust-delivery decision's UTC expiry arithmetic
  independently of the CLI's own `--effect` reasoning.
- The rust-delivery worked example is regenerated: its evidence transcripts are normalized
  (machine-local paths scrubbed) and its record hashes use the typed `record:sha-512:` wire form,
  never the untyped legacy wire.

### 0.3.1 — 2026-09-26

Errata release. Profile ids now match as exact strings, never by prefix. The assurance-class
table's monotonicity check covers the `required_meaning` field, fails closed on a malformed shape,
and checks the union of a profile's declared scopes. A final-phase contract's requirements must
all be firm; a draft requirement in a final contract is now an error. A contract's own assurance
class changes only through a successor contract, never a change-proposal amendment. The untyped
legacy record-hash wire is documented as a read-only warning throughout 0.3.x; its retirement
remains deferred to 0.4. A package whose caller-forced binding meaning differs from its own
declared meaning is now indeterminate, never silently accepted. The Rust binding's required
build-input check now matches by exact path within the manifest's own directory, never by
filename alone. Amending a contract now re-validates the rendered successor and preserves every
field the checker reads.

### 0.3.0 — 2026-09-24

Initial 0.3 release. Replaces the 0.2.0-draft format-only tree with the acceptance protocol and
format: contracts, packages, decisions, assurance classes, verification, conformance and
troubleshooting profiles, and a Kani adoption kit. The source version and file
hashes are recorded in `EXPORT-PROVENANCE.json`.

The tools and specifications now live under `format_acceptance/` and
`protocol_acceptance/`. The old generated schema and self-certificate are removed;
the validators and this tree's own gate suite are the executable checks.

Adds the Rust delivery chain and retains minimal and weighted toy examples.
The Rust records are copied as supplied; legacy-wire warnings remain a known limit. `rs-verified-der` is
omitted pending migration.

Retires the verify-rust-std challenge examples from the public tree.
