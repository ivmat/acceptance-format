# acceptance-format

**A format for recording what verification decided, including what it did not.**

> **Status: `0.1.0-draft`, living, not yet frozen.** The spec may change before the freeze. The
> shipped samples exercise the draft and are not stable tooling targets.

This README is the entry point and index, adapted from [arc42](https://arc42.org) for a spec repo
(no deployed system, so §6/§7 read as *how validation runs*; internal module decomposition beyond
the flat `spec/`/`tools/`/`gates/` layout in §5 is skipped as not applicable).

## 1. Introduction & goals

An **envelope** or **manifest** can admit any software verification claim, including one no machine
can decide. (Three words for three layers, defined here rather than only at
[§12](#12-glossary): a **manifest** is the TOML source of truth — `acceptance.toml`; a **ledger**
is its rendered table, one row per specification rule; an **envelope** is the legacy Markdown
document that bundles a ledger with witness/identity metadata — `examples/rs-verified-der/ENVELOPE.md`
is one. §4 below splits manifest from ledger further; [`docs/GLOSSARY.md`](docs/GLOSSARY.md) has
the full entries.) Admitting a claim does not endorse it: the format grants **weight** — its own
backing — only to claim classes it can fully express and mechanically decide, and refuses weight,
never the claim, otherwise. See [`WHY.md`](WHY.md) for the motivating problem and how this differs
from SARIF, coverage, a green badge, an assurance case, and other related formats.

## 2. Constraints

- Python 3.11+, standard library only — no dependency to install before validating.
- The spec is a living draft (`0.1.0-draft`); freezing requires both a clean weighted core and
  demonstrated use in real verification work (`spec/core.md`'s freeze criterion).
- Single-producer, no cryptographic signing or multi-party trust model in this revision.
- Dual-licensed Apache-2.0 / MIT (see [Author & license](#author--license)).

## 3. Context & scope

This format records **what was verified, how strongly, and how to check it yourself** — it is not a
results-interchange format (SARIF), a coverage tool, a green CI badge, a proof certificate, an
assurance case, a supply-chain attestation, or a trust score. It does not discharge a proof, run a
test, or judge an oracle. See [`WHY.md`](WHY.md) for the full set of comparisons.

## 4. Solution strategy

A TOML manifest (`acceptance.toml`) is the source of truth (ADR-001); a rendered Markdown ledger is
a projection of it for human reading. Validation is **fail-closed**: a claim earns the format's
weight only by supplying every required obligation (a grade, a runnable recipe, a witness that the
recipe can fail), and the validator **refuses weight** rather than rejecting the document when a
claim falls short — the claim stays visible, honestly unweighted.

## 5. Building blocks

### For users

| file | purpose |
|---|---|
| `acceptance.toml` | the format's own acceptance manifest — the repo describing itself, at the format's own convention (a subject carries its manifest at its root); the first certificate-grade manifest; every claim re-runnable |
| `spec/core.md` | normative spec for the WEIGHTED tier: grade, bounds, recipes, watched-fail, weight rules — start with its Overview |
| `spec/format.md` | the TOML schema, design rules, M11 content-hashing, reserved hooks — start with its Overview |
| `spec/evidence-types.md` | evidence-record kinds, `family`, `epistemic_tier`/`method`, control blocks — start with its Overview |
| `spec/assurance-bands.md` | evidence-species floors (A0–A4), control-gated |
| `spec/coverage-ledger.md` | rendering rules for the legacy Markdown ledger form |
| `spec/CLAIM-CLASSES-AWAITING-WEIGHT.md` | claim classes not yet certified as weightable (C1–C9), live |
| `tools/check_acceptance.py` | TOML manifest validator; `--selftest`, `--strict`, `--strict-weight` |
| `tools/check_ledger.py` | Markdown ledger row-rule checker |
| `tools/check_execute.py` | recipe-execution mode; `--yes-run-untrusted-commands` (required), `--subject-root` (required), `--selftest`, `--timeout`, `--only` (a zero-match `--only` is a hard error, not a vacuous pass), `--require-run` |
| `tools/check_parity_selftest.py` | asserts the two checkers reach the same verdict |
| `tools/acceptance_grammar.py` | shared grammar both checkers import, so a rule cannot drift |
| `tools/m11.py` | the M11 content-hash implementation (SHA-512, domain-separated); CLI: `python3 tools/m11.py <domain> <file>` prints the `sha-512:<hex>` digest (`--help` lists domains, `--selftest` runs its checks) |
| `tools/emit_schema.py` | emits `schema/*.schema.json` from live grammar/validator registries; `--check` structurally validates a manifest against it |
| `schema/acceptance-0.2.0-draft.schema.json` | the CURRENT generated JSON Schema (draft 2020-12); shape-normative only, never hand-edited (`format.md` "The schema artifact") |
| `schema/acceptance-0.1.0-draft.schema.json` | the PRIOR schema, kept as a historical, no-longer-regenerated artifact (superseded 0.2 by the addition of `[format].profile`) |
| `profiles/verification/PROFILE.md` | the `acceptance/verification` profile statement (added 0.2): closed vocabularies, required fields, constraints, what it does not define |
| `gates/run_all.sh` | the gate suite (10 steps); run it directly, or install it as a pre-commit hook via `maintainers/install_hooks.sh` (§7) — there is no tracked CI configuration in this repo |
| `gates/check_content_leaks.py` | private-vocabulary leak gate, against `gates/leak_baseline.json` (kept empty; any hit fails) |
| `gates/test_check_content_leaks.py` | the leak gate's own selftest |

Also in the tree: `examples/minimal.acceptance.toml` (an illustrative manifest),
`examples/rs-verified-der/` (the worked example: an illustrative manifest paired with
`ENVELOPE.md`, the frozen legacy ledger form — see its own `README.md`),
[`examples/weighted-toy/`](examples/weighted-toy/) — **start here to write a weighted manifest**: a
genuine, non-illustrative WEIGHTED certificate for a tiny real subject, small enough to copy
whole (see its own `README.md` for a field-by-field walkthrough) — and
[`examples/verify-rust-std-pr618/`](examples/verify-rust-std-pr618/) — a real manifest for a real
submission: [`model-checking/verify-rust-std` PR #618](https://github.com/model-checking/verify-rust-std/pull/618)
(15 Kani-verified `core::intrinsics` claims plus one explicit gap claim, `kani@d4df833c8f8f`
0.67.0 / CBMC 6.8.0, whole-module `370/370`, every claim unweighted and `A0` with the grading
rationale in the manifest's own header comments — see its own `README.md`) — and
[`examples/verify-rust-std-pr664/`](examples/verify-rust-std-pr664/) — a real manifest for a real
submission: [`model-checking/verify-rust-std` PR #664](https://github.com/model-checking/verify-rust-std/pull/664)
(one bounded `A3`/probe claim on `TwoWaySearcher::next_back`'s backward-search-loop coverage plus
one explicit `A0` gap claim, `kani@d4df833c8f8f` 0.67.0 / CBMC 6.8.0, `VERIFICATION SUCCESSFUL`
on all 5 loop-arm covers, every claim unweighted, with a negative-control mutant and three
structured disclosed assumptions — see its own `README.md`). Also
[`profiles/verification/examples/`](profiles/verification/examples/) — the profile's own
conformance pair: `valid/acceptance.toml` validates cleanly, `invalid/acceptance.toml` fails for a
named PROFILE reason (not a syntax error), both wired into `gates/run_all.sh`. Also
`maintainers/hooks/pre-commit` + `maintainers/install_hooks.sh` (installs the gate suite as a
commit hook, §7), and a standard Python `.gitignore` (`__pycache__/`, `*.pyc`).

Related project: [`autoprover-core`](https://github.com/ivmat/autoprover-core) — a proving-pipeline
architecture and reference implementation whose verification receipts are designed to project into
this format (its ADR-005 states the relationship from that side).

### For maintainers

[`maintainers/`](maintainers/) — working material for repo maintainers and their agents
(obligation inventories, validator worklists); nothing in it is needed to use the format.

## 6. Runtime view

A validation run reads a manifest or ledger, checks every claim's structural obligations, and
prints one of three outcomes per file — `valid`, `invalid`, or `indeterminate` (ADR-005) — never a
score. See [`QUICKSTART.md`](QUICKSTART.md) for the first command to run and what its output means.

## 7. Deployment / usage

There is nothing to deploy; there is a command to run. [`QUICKSTART.md`](QUICKSTART.md) validates
an envelope and walks through writing a first ledger row. Run `maintainers/install_hooks.sh` once
to make the gate suite (`gates/run_all.sh`) run automatically before every commit.

## 8. Crosscutting concepts

- **Refusal, not rejection.** A claim that cannot meet a weighted obligation is admitted unweighted,
  never deleted (`spec/core.md` §0, §8).
- **`epistemic_tier` vs `method`** — closed core strength vs. open technique name (ADR-002).
- **M11 content-hashing** — SHA-512, domain-separated, self-describing values (`spec/format.md`
  §"Content-hashing (M11)"; ADR-004).
- **Closed vocabularies everywhere a token decides weight** — `grade` (`spec/core.md` §1), `status`
  (§7.1), `bounds` (§5) — never free prose where a rule must be checked.
- **The schema is generated, never hand-written** — `schema/*.schema.json` is shape-normative only
  (field presence, types, closed vocabularies); every cross-field rule stays semantics-normative in
  the spec prose, enforced only by the validator (`spec/format.md` "The schema artifact"; ADR-008).

## 9. Architecture decisions

Recorded as short ADRs, indexed at [`docs/decisions/README.md`](docs/decisions/README.md): TOML as
source of truth, the `epistemic_tier`/`method` split, grade's coherence rule, M11 hashing,
fail-closed tri-state validation, control-gated bands, reserved hooks, the schema as a
generated artifact, and the refusal of a `[[note]]` construct.

## 10. Quality

`gates/run_all.sh` runs both checkers' selftests, validates the shipped examples and envelope, runs
the cross-representation parity harness, runs the leak gate, checks the generated schema for
drift, and validates the format's own self-manifest (`acceptance.toml`) as a
certificate, and validates the profile conformance pair (`profiles/verification/examples/`) — ten steps, all must pass before a commit. Re-run that last step yourself with

```sh
python3 tools/check_acceptance.py --strict --strict-weight acceptance.toml
```

[`CASE-STUDY.md`](docs/CASE-STUDY.md) reports what building a real ledger against a formally
verified crate found, including defects the gates themselves later closed.

## 11. Risks & known limits

The validator checks structure, never truth: that a named command is the *right* one, that a
watched failure really happened, that a declared axis really enumerates the spec — none of this is
decidable and none of it is checked. Read [`ASSUMPTIONS.md`](ASSUMPTIONS.md) before relying on a
ledger or envelope.

## 12. Glossary

Every term of art — claim, grade, band, `epistemic_tier`, watched-fail, and the rest — is defined in
[`docs/GLOSSARY.md`](docs/GLOSSARY.md).

## Status and scope note

**0.2 is the verification profile of a general acceptance format (planned; extracted after two
internal domains use it).** `acceptance/0`'s manifest shape is, as of 0.2, named a **profile**
(`acceptance/verification`, `profiles/verification/PROFILE.md`) of a general core that does not
ship yet — nothing about a claim, an evidence record, or a validator verdict changes; 0.1's rules
are exactly what the profile names. The general core is extracted later, once two domains other
than verification have each independently exercised the same shared Claim/Evidence/Acceptance
semantics on their own carriers — extracting a core from one demonstrated use is a guess at what is
actually shared; extracting it from two is a generalization. Until then, this repository ships one
profile, and every manifest in it validates identically to how it always did.

## Adopters

An adopter is placed on a ladder, not given a name-drop — each rung is a stronger form of use than
the one below it (owner-controlled use < a proposed upstream PR < a merged upstream use < an
independent implementation), and every named consumer states which rung it is on, with the format
revision it targets:

| consumer | rung | format revision |
|---|---|---|
| rs-verified-der | owner-controlled use (`examples/rs-verified-der/`; repo visibility not asserted here — T1, not checked) | `0.1.0-draft` |
| [autoprover-core](https://github.com/ivmat/autoprover-core) | owner-controlled use (its ADR-005 states the projection) | `0.1.0-draft` |
| [`model-checking/verify-rust-std` PR #618](https://github.com/model-checking/verify-rust-std/pull/618) | proposed upstream — **OPEN**, not merged (checked via `gh pr view`, 2026-09-08) | `0.1.0-draft` (`examples/verify-rust-std-pr618/`) |
| [`model-checking/verify-rust-std` PR #664](https://github.com/model-checking/verify-rust-std/pull/664) | proposed upstream — **OPEN**, not merged (checked via `gh pr view`, 2026-09-08) | `0.1.0-draft` (`examples/verify-rust-std-pr664/`) |
| — | independent implementations | none |

## Similar formats

Owner rule: name similar formats at publication and say why this one exists anyway; a
requirement-by-requirement, clause-level comparison is a separate, later check (**PENDING**, not
performed here) — this table is the seed, not the discharge.

| similar format | why this format exists anyway |
|---|---|
| SARIF | a results-interchange format for tool findings, not a certificate of what a producer verified, under what assumptions, and how a reader re-checks it — out of scope by design (`WHY.md`) |
| OSCAL assessment results / POA&M | models remediation and accepted risk over an assessment; it does not refuse to weight an under-evidenced claim, and it has no per-claim watched-fail-witness or evidence-subject-binding check |
| in-toto Statement v1 | already binds a subject by digest with typed predicates — the useful part this format keeps in spirit; it has no closed epistemic-tier vocabulary, no calibration-reference gate on trust numbers, and no observed-red control block |
| CycloneDX 1.6 attestations | closest in shape (claims + evidence + conformance); whether it carries a refusal-to-weight with an able-to-fail witness, counted first-class gaps, or exact-content binding checked at validation time is the clause-level comparison marked PENDING, above |
| RATS (RFC 9334) | a real evidence-vs-attestation-results and appraisal-policy vocabulary; the same PENDING comparison applies — it is not yet checked, requirement by requirement, against this format's refusal/gap/binding machinery |
| GSN/SACM | models claim–argument–evidence graphs, well suited to HUMAN-authored, design-time assurance cases; this format targets mechanically re-checkable, per-claim weight refusal instead, which is a different job even where the vocabulary looks similar |

## Maintenance and compatibility

Single maintainer today (see "Author & license," below); no CLA/DCO process is in force. Across
0.x minor versions: only vocabulary ADDITIONS (a new evidence kind, a new closed token, a new
profile) are compatible changes; no required field is ever REMOVED from an existing profile; and
the validator's set of refusals may only GROW, never shrink — a manifest that validated under an
earlier 0.x minor version may start failing under a later one (a tightening, disclosed as such in
that version's changelog), but a manifest that validates under a later 0.x minor version was never
silently permitted to skip a check an earlier version enforced. `acceptance/0`'s own id does not
bump on a tightening (`spec/format.md` "Stability"); pin to the validator's git sha, not to the id
string, for the only real stability guarantee this format offers pre-freeze.

## Author & license

Ivo Matijasevic ([@ivmat](https://github.com/ivmat)). Dual-licensed under either of
[LICENSE-APACHE](LICENSE-APACHE) or [LICENSE-MIT](LICENSE-MIT), at your option. See
[LICENSE-NOTES.md](LICENSE-NOTES.md) for the license rationale by material type (code, schemas,
prose, examples) and the excluded-material boundary.
