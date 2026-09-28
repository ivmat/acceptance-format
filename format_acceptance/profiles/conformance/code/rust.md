---
type: proposal
digest: Leaf: acceptance/conformance/code/rust (frontmatter added 2026-09-22 for the protocol gate)
---

# Leaf: `acceptance/conformance/code/rust`

meaning: `../PROFILE.md` (`acceptance/conformance`) · binding: `../../bindings/code/rust.md`
(`code/rust`) · status: **first subject IN PROGRESS** — worked examples not published.

This document names nothing the two axes it projects don't already own: the meaning half (grade,
applicability, evidence families, bands, constraints) is `../PROFILE.md`'s; the binding half
(subject identity, recipe carriers, `constraints` typing) is `../../bindings/code/rust.md`'s
— today still expressed through `../../verification/code/rust.md` §1 (renamed from
`../../rust-code.md` 2026-09-24, open question 2), since the Step-5 lift into `bindings/code/rust.md` has not
run (deferred). This
leaf adds only what is specific to BOTH axes at once: the full token⇒tier table (D1 amendment A2,
the C8/E-6 cover-only rule in this binding's own terms, and how the two 8b checks
compose here.

## `method`/token ⇒ `epistemic_tier` table (A2)

Every token this binding's tooling admits, copied from `../../verification/PROFILE.md` §2 (the
seven language-neutral tokens) and `../../verification/code/rust.md` §2 (the five Rust-only
tokens — both renamed/lifted from `../../rust-code.md` §2, 2026-09-24, open question 2/R5) — none raised past
`../PROFILE.md`'s family⇒TIER table (a token's tier must equal that table's row for its family; the
comparison is TIER-to-TIER, never TIER-to-BAND). "Used by first subject" marks what the first
subject's `acceptance.toml` actually carries today: `kani-harness` and
`lean-theorem` records only.

| token | family | `epistemic_tier` (`../../verification/PROFILE.md` §2 or `../../verification/code/rust.md` §2) | used by first subject? |
|---|---|---|---|
| `lean-theorem` | `kernel` | T1 | yes — the source subject's Lean rows |
| `kani-harness` | `bmc` | T2 | yes — the bulk of the source subject's records |
| `flux-refinement` | `smt-refinement` | T2 — RESERVED, tool not adopted | no — not adopted in this project |
| `unit-test` | `dynamic` | T3 | not yet — no `unit-test` row in the source subject |
| `property-test` | `dynamic` | T3 | not yet |
| `fuzz` | `dynamic` | T3 | not yet |
| `miri` | `dynamic` | T3 | not yet |
| `lint` | `mechanical` | T4 | not yet |
| `semver-check` | `mechanical` | T4 | not yet |
| `dep-audit` | `mechanical` | T4 | not yet |
| `human-review` | `judgment` | T5 | not yet |
| `llm-review` | `judgment` | T5 | not yet |

Every row's tier equals `../PROFILE.md`'s family⇒TIER row for the same family (kernel→T1, bmc→T2,
smt-refinement→T2 reserved, dynamic→T3, mechanical→T4, judgment→T5) — none raised. This table
carries no band values; a token's reachable band ceiling is looked up separately, by family, in
`../PROFILE.md`'s "Band ceilings" table — the two tables are never merged into one row.

## C8 (cover-only) in Kani terms, this leaf

`../PROFILE.md` Constraints C8: a WEIGHTED claim whose **every cited `kani-harness`
evidence** explicitly declares `cover_only = true` FAILS C8 UNCONDITIONALLY. Harness names (e.g. a
`ref` ending `_witnessed`) are never interpreted — only the record metadata decides. The legacy
`[conformance].cover_only` ref list is read-only, with a deprecation WARNING, ONLY under an
explicitly declared `profile_version = "0.1.0-draft"`; at every other version, including 0.2.0, its
mere presence is a hard error (`bindings/code_rust.py`). Weighted all-cover-only claims FAIL;
unweighted ones are permitted. The checker does not automatically downgrade weight — the producer
declares `unweighted` and says why in the statement. No manifest-side `cover_tally` field exists or
is accepted (open question C4), independent of weight. Concretely, on
Kani's own output: an unsatisfied `kani::cover` still reports `VERIFICATION:- SUCCESSFUL` — the
verdict cannot say no, only the `N of M cover properties satisfied` line can
(finding E-6, design history, not published; already reproduced in this crate's own
cover-only-suffixed harnesses). Until the evidence-RECORD
projection itself carries a tally (open question C4), a generated conformance claim at this leaf that would
cite either of those two harnesses as its sole `kani-harness` evidence, weighted, is a hard FAIL —
never a PASS by exit code on a check that structurally cannot fail.

## How the two 8b checks compose here (CLOSED — updated 2026-09-24)

- **Meaning half** (`../PROFILE.md` Admissibility check): `tools/profiles/conformance.py` — native
  `check(doc, ctx)`; profile_version 0.2.0 (`source_claim` /
  `source_claims_other` / `[conformance].source_manifest{,_hash}` retired, lowered to class B8
  `acceptance-claim` reference evidence; C6/C7/C9's digest and containment sub-checks
  de-duplicated against `check_core`).
- **Binding half** (`../../bindings/code/rust.md` Admissibility check, item 8b): EXISTS —
  `tools/bindings/code_rust.py` (`bindings/{code,code_rust}.py`). It checks B14/B17
  admission and identity narrowing, A2 token/family tier ceilings, B9/C8's cover-only guard, and
  B20's required-build-inputs guard.
- **Composition, therefore: a full leaf id (`acceptance/conformance/code`,
  `acceptance/conformance/code/rust`) composes to a REAL verdict** (PASS, or FAIL with the rule
  named) — this leaf is CLOSED, not the `INDETERMINATE`-by-default state this section described
  before the binding check landed. The nine companion subjects (x690, rfc5280, keyformats × 7)
  produced a real plain-leaf PASS without `--meaning-only` when last exercised; that run is an
  unpublished historical result, not a record shipped in this repository.
  `tools/profiles/conformance.py --meaning-only` still exists, but for a leaf whose binding half
  IS available (this one), the flag is now ignored and the full composed verdict is reported
  (`check_core.py`'s scoping-flag dispatch: "scoping flag ignored: both halves present; full
  composed verdict") — the flag only still narrows evaluation for a known leaf whose binding half
  is genuinely missing.

## First subjects

The X.690 and RFC 5280 conformance subjects (plus the key-format RFCs) — both being
built under the same effort, generated from a verification subject's
projected Kani/Lean records via a `mapping.toml` (clause → row id → harness ref),
not hand-written (design history, not published). Every generated claim there borrows evidence
under `../PROFILE.md`'s
"Evidence borrowed from a verification manifest" rule (R-12): unweighted, control-free, at the
control-free band ceiling.
