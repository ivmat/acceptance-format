# Profile: `acceptance/verification`

`profile_id = "acceptance/verification"` · `profile_version = "0.2.0-draft"`

## What a profile is

A **profile** is a closed vocabulary plus required fields, constraints, a version id, and at
least one conformance example that validates and one that fails — the shape every domain
extension of this format's general core must have (`spec/format.md` "Profiles", added 0.2). This
document is that statement for the one profile 0.2 ships.

**Everything the manifest called `acceptance/0` already did in 0.1 is what this profile names.**
No behaviour changes: every `0.1.0-draft` manifest already shipped conforms to this profile by
construction, whether or not it declares `[format].profile` (0.2 makes the field OPTIONAL,
defaulting to `acceptance/verification` — see `spec/format.md` "Profiles"). What is new in 0.2 is
the *name*, not the rule.

## Closed vocabularies this profile fixes

- **Claim classes — the `grade` vocabulary** (`spec/core.md` §1, normative, not restated here):
  nine closed tokens. Weight-eligible: `contract`, `probe`, `test-only`, `mechanical`,
  `not-covered`, `out-of-scope`. Never weight-eligible: `inspection-argued`, `unspecified`,
  `ungraded`. A token outside this set is an error on any claim, weighted or not.
- **Evidence kinds and their families** (`spec/evidence-types.md`'s registry table, normative,
  not restated here): `kani-harness` (bmc), `lean-theorem` (kernel), `flux-refinement`
  (smt-refinement, reserved), `unit-test` / `property-test` / `fuzz` / `miri` (dynamic), `lint` /
  `semver-check` / `dep-audit` (mechanical), `human-review` / `llm-review` (judgment) — each with
  its own extra-required fields (`bounds`, `semantics`, `axioms`, `cases`, `generator`,
  `corpus_size`, `duration`, `baseline`, `db_version`, `reviewer`, as that table lists per kind).
  The closed, artifact-agnostic `epistemic_tier` axis (`T1`–`T5`) and the profile's
  `method → epistemic_tier` ceiling table live in the same document and are unchanged by this
  profile — this revision's FV table is this profile's table (`spec/evidence-types.md`, "The
  profile `method → epistemic_tier` table").
- **Assurance bands** (`spec/assurance-bands.md`, normative, not restated here): `A0`–`A4`, plus
  the reserved `A3.5`, gated by evidence species and (for oracle-bearing claims) an observed-red
  `control` block, per that document's rules 1–8.

## Required fields over the core

A `[format].profile = "acceptance/verification"` manifest (or one that omits the field and so
defaults to it, per `spec/format.md` "Profiles") is held to every field this profile's normative
documents already require:

- `[format]` self-location (`spec_id`, `spec_sha`, `validator_sha`, `generated_by`,
  `generated_at`) — `spec/format.md` "`[format]` self-location".
- `[subject]` identity (`name`, `kind`, `commit`, `dirty`) — `spec/format.md`'s schema block.
- `[coverage]` totals (`clauses_total`, `claims_total`) — design rule 1, below.
- On every WEIGHTED claim: the five W2 conditions (`spec/core.md` §8 — a weight-eligible `grade`;
  every companion field that grade requires; a non-reserved `clause_source`; a declared
  `[spec].axis`; a watched-fail witness on every grade that asserts a check was performed) and,
  where `grade = "contract"`, the §2 `epistemic_tier`/grade coherence rule.
- On every `[[claim.evidence]]` record: `kind`, `family`, `ref`, `result`, `tool`, `record`
  (`spec/evidence-types.md` "Required fields"), plus `record_hash` on weighted evidence (P9).

Nothing above is a new obligation; this section names, in one place, which of the core's fields
this profile activates — the same fields `tools/check_acceptance.py` already enforces against
every manifest in this repo.

## Constraints (design rules 1–4b, by reference)

This profile binds `spec/format.md`'s design rules 1–4b as profile constraints, restated here by
reference and not copied, so the rule text lives in exactly one place:

1. **Gaps are first-class** (design rule 1) — omission is the only forbidden state.
2. **Evidence is admissible or it is nothing** (design rule 2) — a record missing its required
   provenance fields is an assertion, not evidence.
3. **No trust numbers without calibration** (design rule 3) — `alpha`/`beta`/`lr` are REJECTED
   unless they carry a `calibration` reference; see also "What this profile does not define",
   below.
4. **The certificate binds to exact content** (design rule 4) — `[subject].commit` is required; a
   dirty tree says so.
4a. **Evidence-subject binding is checked, and a mismatch is a hard error, unconditionally**
   (design rule 4a) — the `[subject].subject_hash` / `[[claim.evidence]].subject_hash` pair.
4b. **Label-binding is a SHOULD, not a validator error** (design rule 4b) — reviewer work, named
   so it is reviewed for.

Design rules 5–7 (producer-never-self-overrides; stable claim ids; no ledger/view/independence
property stated before its machinery exists) bind this profile identically and are likewise not
restated here — `spec/format.md` is the one normative text for all seven.

## What this profile does not define

- **No aggregate trust score.** Design rule 3 already forbids a number without a calibration
  reference; this profile adds no ledger that sums, discounts, or otherwise arithmetics evidence
  into a single figure. The numeric rule is stated once, precisely, at `spec/core.md` §8: (i)
  aggregate trust scores are prohibited; (ii) per-record calibrated measurements are permitted as
  fields; (iii) a calibration reference is necessary for weight, never sufficient — W2's five
  conditions still bind regardless.
- **No results-interchange format.** This profile records what verification decided and how to
  re-check it, not a portable results envelope (SARIF's role) — see `WHY.md`.
- **No signing.** Every reserved hook in `spec/format.md` ("Reserved hooks", H1–H8), including the
  `[[attestation]]` block (H3) and the `claim:` M11 domain, ships no engine in this revision; this
  profile does not change that. A future signed-verdict binding is a declared adapter, never a
  claim that this profile already signs anything.
