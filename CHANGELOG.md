# Changelog

## 0.4.0 — 2026-10-12 — locked, not ratified

- Retirement of untyped legacy record hashes is deferred again; 0.4.0 still accepts matching legacy wires read-only with warnings.

- **Breaking:** the first document is now a specification, and the protocol is
  `acceptance-protocol/1`. The current checker refuses 0.3 protocol documents; use
  [tag v0.3.2](https://github.com/ivmat/acceptance-format/tree/v0.3.2) or migrate.
- **Removed:** commercial role wording, conditions framed as debts (the verdict stays;
  conditions are now due-dated items), the work-contract and transaction notes, `legal_ref`,
  the `legal` domain, money examples, and `pay` among effects. Authority, delegation and
  effect gating remain, with a planned move to companion layers.
- **Added:** checked stacking, including B1 subtree `path` identities, B22 dependency
  declarations, C0/C2 chain requirements, a consumer-configured directory store, `--tree`
  and `--store`, recursive checks and effect-time checks. The paint-stack example checks
  runtime libraries; toolchain and platform relations are trusted as the base and are not
  checked. The label adds no combined assurance.
- **Added:** [the migration tool](protocol_acceptance/tools/acceptance_migrate.py) for
  specifications and packages. Decisions are never rewritten; the consumer re-issues them.
- **Examples:** the Rust examples are regenerated at 0.4.0. The weighted toy's bindings are
  updated while its historical evidence and subject identity are retained. The README has a
  plain-language introduction, a tiny example and the stacking walkthrough.
- **Tools:** selftests cover version routing, migration and chain validation.
- The gate suite and README quickstart work without git metadata (a source archive or
  Download ZIP); the protocol tool accepts `--root`. The exported repository now includes
  a `REPO.md` descriptor. The roadmap separates this release from planned work.

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
and checks the union of a profile's declared scopes. A final-phase specification's requirements must
all be firm; a draft requirement in a final specification is now an error. A specification's own assurance
class changes only through a successor specification, never a change-proposal amendment. The untyped
legacy record-hash wire is documented as a read-only warning throughout 0.3.x; its retirement
remains deferred to 0.4. A package whose caller-forced binding meaning differs from its own
declared meaning is now indeterminate, never silently accepted. The Rust binding's required
build-input check now matches by exact path within the manifest's own directory, never by
filename alone. Amending a specification now re-validates the rendered successor and preserves every
field the checker reads.

### 0.3.0 — 2026-09-24

Initial 0.3 release. Replaces the 0.2.0-draft format-only tree with the acceptance protocol and
format: specifications, packages, decisions, assurance classes, verification, conformance and
troubleshooting profiles, and a Kani adoption kit. The source version and file
hashes are recorded in `EXPORT-PROVENANCE.json`.

The tools and specifications now live under `format_acceptance/` and
`protocol_acceptance/`. The old generated schema and self-certificate are removed;
the validators and this tree's own gate suite are the executable checks.

Adds the Rust delivery chain and retains minimal and weighted toy examples.
The Rust records are copied as supplied; legacy-wire warnings remain a known limit. `rs-verified-der` is
omitted pending migration.

Retires the verify-rust-std challenge examples from the public tree.
