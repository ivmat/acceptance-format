---
type: proposal
digest: Profile: acceptance/conformance — profile_version 0.2.0 (conformance lowering) (frontmatter added 2026-09-22 for the protocol gate; updated 2026-09-24 for the 0.2.0 de-duplication pass)
---

# Profile: `acceptance/conformance` — profile_version 0.2.0

`profile_id = "acceptance/conformance"` · `profile_version = "0.2.0"` · parent:
`acceptance/core` · status: **candidate — first subject: a verified DER-parsing crate vs
X.690 (2021) DER / RFC 5280 / keyformats; the nine subjects run at profile_version 0.2.0**
The profile vocabulary and its checked examples are shipped in this directory.

**Conformance 0.2.0 (2026-09-24).** `source_claim` / `source_claims_other` /
`[conformance].source_manifest{,_hash}` (0.1.0-draft's pre-`/0` cross-manifest borrowing
encoding) are retired — the meaning no longer reads them, at any declared `profile_version`, no
compatibility shim. A borrowed claim now cites its source with a class B8 `acceptance-claim`
reference evidence entry (`core.md` B8), validated entirely by
`check_core.check_reference_evidence` — this meaning adds no B8-specific mechanism of its own.
C6's inventory-digest recomputation, C7's applicability-hash recomputation and C9's manifest-wide
aggregate scan are likewise retired from this meaning: `check_core.check_spec`,
`check_core.check_documents` and `check_core.check_no_aggregates` already run those checks on
every profile, unconditionally. C6/C7/C9 keep only what is
meaning-specific: C6 requires `[spec].provenance = "external"` (core's own default is
`"in-tree"`); C7 requires `applicability_hash` to be present at all (core only recomputes its
digest when the field already exists); C9 still scans the clause inventory and the applicability
record, the two profile-declared assertion surfaces core does not see. `[conformance].cover_only`
(the `code/rust` binding's legacy cover-only ref list) is dropped at 0.2, not merely deprecated —
see Constraints C8 below.

This document's closed vocabularies, required fields, constraints and admissibility check are
filled below. The clause inventory (`conformance/standards/`), the checker
(`tools/profiles/conformance.py`), the examples pair (`conformance/examples/`) and both first-subject
manifests are separate deliverables of the same effort and are referenced, not restated, here — this
document still "point[s] at the core, don't copy it," the rule the skeleton pass set.

## What a profile is

A profile is a closed vocabulary plus required fields, constraints, a version id, and at least one
conformance example that validates and one that fails (`spec/format.md` "Profiles"; protocol.md
§6.6 lists the eight things a profile supplies). This document is that statement for the
conformance meaning, and is the public authority for it; its vocabulary is enumerated below, and
its example pair (`conformance/examples/`) and checker (`tools/profiles/conformance.py`) are
shipped alongside it.

## Meaning — what "accepted" says under this profile

Accepted means: **the artifact meets every applicable clause of a named, versioned standard, and the applicability of each clause (applies / does not apply / excluded, with the reason) was declared before the evidence was read.**
The standard may be external or in-tree relative to the certified tree; an in-tree audit checklist is a legitimate conformance standard.
The claim list is the standard's clause list, or a declared slice of it.

**The meaning above is broader than what this implementation checks, at every `profile_version`
through 0.2.0.** This meaning admits
`[spec].provenance ∈ {external, in-tree}` (open question C2). This IMPLEMENTATION admits
`provenance = "external"` ONLY: an external clause inventory, digest-pinned per F2/R-7. A manifest
declaring `provenance = "in-tree"` at this profile_version is `INDETERMINATE`
("in-tree conformance standards not implemented"), never `FAIL` — the meaning is not wrong about
in-tree checklists, this draft simply does not check them yet.

What distinguishes this from `acceptance/verification` is not the evidence (a clause may be
discharged by a proof, a test, a lint, or an inspection) but the required fields: an applicability
statement per clause, a versioned standard as the primary governing document, and coverage
counted against the standard's own clause numbering.

Conformance is a sibling of verification (open question 4, decided 2026-09-20).
The distinguishing required field is the per-clause applicability statement.

## Artifact-type projections

Applies to any binding whose subject can be held to a standard, whether external or in-tree.
Expected leaves:

| leaf id | binding | first plausible subject | status |
|---|---|---|---|
| `acceptance/conformance/code` | `bindings/code.md` | a codec crate against its wire-format standard | narrowed to `code/rust`, below, for the first subject |
| `acceptance/conformance/code/rust` | `bindings/code/rust.md` | a verified DER-parsing crate vs X.690 (2021) DER / RFC 5280 | first subject IN PROGRESS — `conformance/code/rust.md`; worked examples not published |
| `acceptance/conformance/document` | `bindings/document.md` | a spec document against a house style or a profile of a standard | not yet exercised |
| `acceptance/conformance/tool` | `bindings/tool.md` | a tool against a command-line or output-format standard | not yet exercised |

## Closed vocabularies this profile fixes

- **Claim classes (`grade`).** The core's nine-token grade vocabulary (`spec/format.md` "Schema";
  closed at `tools/acceptance_grammar.py`'s `GRADES`) is REUSED UNCHANGED. Applicability (below) is
  a separate field, not a grade — a clause declared `not-applicable` is `grade = "out-of-scope"`
  (Constraints C3), the same token verification already uses for "the producer declared this out of
  scope, here." No new grade token.
- **Applicability statement.** The closed set: `applicable` | `not-applicable` | `excluded`.
  `applicability_reason` is the required companion
  for the last two; absent-or-empty is allowed for `applicable`. This field, not the evidence, is
  what makes this profile a profile (open question C1).
- **Evidence kinds and families.** Declared here, definitions cited from `spec/evidence-types.md`
  (meanings do not inherit, D1 ruling §0) — every kind this meaning admits IS a verification-profile
  row, reused by reference: `kani-harness`/bmc, `lean-theorem`/kernel, `unit-test` ·
  `property-test` · `fuzz` · `miri`/dynamic, `lint` · `semver-check` · `dep-audit`/mechanical,
  `human-review` · `llm-review`/judgment. **Delta: none.** No new kind, no new family — a clause a
  tool cannot decide is discharged by a `human-review`/`llm-review` (judgment-family) row already in
  the registry, not by a new "inspection" kind.
- **Evidence families + family⇒TIER table (D1 amendment A2).** Declared here, verified
  against `spec/evidence-types.md` and `../verification/PROFILE.md` §2 / `../verification/code/rust.md`
  §2 (the tier ladder split R5 lifted 2026-09-24: the language-neutral default table is now at
  `../verification/PROFILE.md` §2; the Rust-only tokens stayed at `../verification/code/rust.md`
  §2, renamed from `../rust-code.md`) — none raised. **This is a family⇒TIER
  table, not a family⇒band table; a `T`-value and an `A`-value are never compared to one another —
  the band-ceiling table below is separate, and is the only place a `T` and an `A` appear on the
  same row:**

  | family | `epistemic_tier` | verified against |
  |---|---|---|
  | `kernel` | T1 | `evidence-types.md` (`lean-theorem` row); `../verification/PROFILE.md` §2 |
  | `bmc` | T2 | `evidence-types.md` (`kani-harness` row); `../verification/code/rust.md` §2 |
  | `smt-refinement` | T2 — RESERVED, tool not adopted | `evidence-types.md` (`flux-refinement` row); `../verification/code/rust.md` §2 |
  | `dynamic` | T3 | `evidence-types.md` (`unit-test`/`property-test`/`fuzz` rows: `../verification/PROFILE.md` §2; `miri` row: `../verification/code/rust.md` §2) |
  | `mechanical` | T4 | `evidence-types.md` (`dep-audit` row: `../verification/PROFILE.md` §2; `lint`/`semver-check` rows: `../verification/code/rust.md` §2) |
  | `judgment` | T5 | `evidence-types.md` (`human-review`/`llm-review` rows); `../verification/PROFILE.md` §2 |

  The per-leaf `method`/token ⇒ `epistemic_tier` table (§6.6 item 1, `conformance/code/rust.md` for
  the first subject) lists every admitted token's tier, copied from `../verification/PROFILE.md` §2
  (the seven language-neutral tokens) and `../verification/code/rust.md` §2 (the five Rust-only
  tokens), never raised past this table's row for the token's family.
- **Band ceilings (SEPARATE from the tier table above).** The species ceiling each family's evidence
  may reach, DERIVED from `spec/evidence-types.md`'s "what it can evidence" column and
  `spec/assurance-bands.md`'s species-ceiling table — none raised:

  | family | band ceiling this meaning admits | cited from |
  |---|---|---|
  | `bmc` | ≤ A3, bounded | `evidence-types.md` (`kani-harness` row) |
  | `kernel` | ≤ A4, unbounded | `evidence-types.md` (`lean-theorem` row) |
  | `smt-refinement` | ≤ A3.5 — RESERVED, tool not adopted | `evidence-types.md` (`flux-refinement` row) |
  | `dynamic` | ≤ A1, alone (a mutation control for oracle-bearing claims; A1 uncontrolled for no-oracle freedom claims) | `assurance-bands.md` rule 4 |
  | `mechanical` | ≤ A1 | `assurance-bands.md` band table, A1 row ("mechanical hygiene") |
  | `judgment` | ≤ A0, per `assurance-bands.md` rule 3, `evidence-types.md`'s judgment rule and the validator's enforcement | open question C6, CLOSED (0.3 open question 9) |
- **Assurance bands.** `spec/assurance-bands.md`'s A0–A4 apply UNCHANGED for this first subject —
  the evidence here IS verification evidence (the same `kani-harness`/`lean-theorem` records the
  rev02 manifest already carries), so nothing yet motivates a departure from the species ceilings
  written for it. This is a disposition of the skeleton's "unclear" TODO (design history, not
  published), not a ruling that bands stay class-level forever: open question 10 (resolved 2026-09-20)
  already rules bands eventually VERIFICATION-PROFILE-OWNED, not a class ordinal every profile
  inherits silently. Whether conformance needs its own table is revisited at Step 5.

## Required fields over the core

FIXED vocabulary:

- `[format].profile` names the leaf, e.g. `acceptance/conformance/code/rust`.
- `[spec].provenance` classifies the governing standard relative to the certified tree as `external` or `in-tree`, per `spec/format.md` F2.
  `external` requires the digest form of `[spec].version` (`normative-reference:sha-512:<hex>`); `in-tree` retains the F2 default and free-form version rules — **this IMPLEMENTATION (profile_version 0.1.0-draft) only checks `provenance = "external"`; `in-tree` is `INDETERMINATE` here, not a validation path this draft runs.**
- `[spec].path` names the clause-inventory file (`<standard-id>.clauses.toml`, schema owned by
  `conformance/standards/README.md` — not redefined here); `[spec].external` lists any additional
  external normative references (e.g. `["ITU-T X.690 (02/2021)"]`). **Path rule:**
  `[spec].path` and `[conformance].applicability_record` (below) MUST be relative and resolve
  inside the repo root (the nearest ancestor with `.git`, or an explicit `--root`); an absolute
  path is a FAIL, not a warning.
- `[spec].version = "normative-reference:sha-512:<128-hex>"` (F2 digest, REQUIRED with
  `provenance = "external"`) is computed over the CLAUSE-INVENTORY FILE's own bytes — the in-tree,
  normalized slice — never over the external standard's text (the COPYRIGHT RULE: no
  clause text or quote may enter this tree). **Inventory identity is bound by digest ONLY**
  : the hash binds CONTENT, nothing else — a consumer who wants to know whether this is
  THE canonical inventory for the standard compares `[spec].version` against the canonical
  inventory's own digest, out-of-band; this format does not perform that comparison. **Disclosed
  residual:** the digest proves the checked-in inventory's bytes are what they are; it does NOT
  prove the inventory faithfully represents the cited standard. That second question is
  judgment-level and nothing in this format decides it (open question C5, below).
- `[spec].axis = "one claim per clause of the declared slice of <standard id>"` — REQUIRED, checker-
  enforced, present or not (this profile does not leave it optional the way the core
  does for a wholly-unweighted manifest).
- `[coverage].clauses_total` / `.claims_total` = the inventory's `[[clause]]` row count (one claim
  per clause, applicable or not). `denominator = "slice"` MAY be used only if the core validator
  already accepts it — it is EXPERIMENTAL, not yet frozen (open question 12(b), resolved 2026-09-20);
  otherwise omit it and put the same fact in `slice_note` as free text.
- A new `[conformance]` table, this meaning's own (the core does not define it):
  ```toml
  [conformance]
  standard                  = "itu-t-x690-2021"
  applicability_record      = "applicability.toml"        # relative, resolves inside repo root (R-2)
  applicability_hash        = "applicability-record:sha-512:<128-hex>"   # wire form, R-7
  applicability_declared_at = "2026-09-21T00:00:00Z"       # RFC 3339; MUST equal applicability.toml's
                                                            # own declared_at (R-6)
  ```
- A companion file, `applicability.toml`, one `[[row]]` per clause (`clause`,
  `applicability`, `reason`), hashed by `[conformance].applicability_hash` (wire form above). This
  is the "declared before evidence was read" artifact a claim's `applicability` AND its `reason` may
  never drift from (Constraints C7) — a CONTENT binding; see C7 for what it does and does not prove.
- On every claim: `clause_source` ∈ {`external-standard`, `spec-document`}, required
  regardless of weight (R-8), and the following class B5 fields:

  | field | required shape at `0.1.0-draft` |
  |---|---|
  | `status` | `not-applicable` is the primary encoding for an inapplicable clause; no evidence, unweighted or omitted weight, and no grade (or `out-of-scope`). Excluded clauses remain `gap`, with `grade = "out-of-scope"` and nonempty `scope_ref`. |
  | `applicability` | `applicable`, `not-applicable`, or `excluded`; must match the applicability record row and the class B5 status pairing. Legacy `gap` + `out-of-scope` + `scope_ref` + `not-applicable` is read with a WARNING at `0.1.0-draft`, rejected at `0.2`. |
  | `applicability_reason` | Nonempty for not-applicable and excluded; absent or empty allowed for applicable. Must equal the record row's reason. |
  | `[conformance].cover_only` | Deprecated list of harness refs: accepted READ-ONLY with a deprecation WARNING at `0.1.0-draft`, dropped at `0.2`. Producers emit record-level `cover_only = true`; the `code/rust` binding owns C8. |

## Constraints

Per §6.6 item 6c, each constraint below must be exposed as a check the core calls, composed with
the binding's own check at the leaf — a constraint stated only in this document's prose is not a
constraint. This profile binds `spec/format.md`'s design rules 1–7 by reference, not by copy.
`tools/profiles/conformance.py` (standalone; imports `tools/acceptance_grammar.py`, never edits
`tools/check_acceptance.py`) is this meaning's 8b admissibility check — the meaning half the core
calls; the binding half is `code/rust.md`'s own (see `conformance/code/rust.md`). Profile-specific
constraints (FIXED vocabulary):

- **C1** every inventory clause (`conformance/standards/<id>.clauses.toml`, schema owned by
  `conformance/standards/README.md`) has exactly one claim; no claim cites a clause outside the
  inventory.
- **C2** `applicability` ∈ {`applicable`, `not-applicable`, `excluded`} (closed);
  `applicability_reason` nonempty for the last two, absent-or-empty allowed for `applicable`.
- **C3/C4 (class B5 is primary)** — `not-applicable` uses `status = "not-applicable"`,
  `applicability = "not-applicable"` and nonempty `applicability_reason`, no evidence,
  and unweighted or omitted weight. No grade or `scope_ref` is required. `excluded`
  remains a visible `status = "gap"` with `applicability = "excluded"`, nonempty reason,
  `grade = "out-of-scope"`, nonempty `scope_ref`, no evidence and unweighted or omitted
  weight. The legacy not-applicable gap/out-of-scope/scope_ref encoding is read with
  a WARNING only under explicitly declared conformance `0.1.0-draft`; elsewhere it
  is an ERROR.
- **C5 (the restriction runs the OTHER way)** (a) an `applicable` clause with
  no evidence is `status = "gap"` — legal, counted, visible; (b) an `applicable` claim may NOT carry
  `grade = "out-of-scope"` (that grade is reserved for the two non-applicable tokens, C3/C4). Beyond
  (a)/(b), status/grade coherence for an `applicable` claim is the core's own concern
  (`tools/acceptance_grammar.py`'s `STATUS_COHERENT_GRADES`) — not restated here.
- **C6 (narrowed at 0.2 — de-duplicated against the core's own check)** `[spec].provenance` MUST equal `"external"`
  (this meaning's own narrowing; core's own default is `"in-tree"`). The `[spec].version` wire-form
  check and its digest recomputation against the inventory file are no longer restated here: under
  `provenance = "external"`, `check_core.check_spec` already performs both, on every profile,
  unconditionally. A mismatch or malformed digest still fails closed — the message now
  reads `B6: spec.path: …`, not `C6: …`.
- **C7 (CONTENT binding, not a TIME claim; narrowed at 0.2 —
  de-duplicated against the core's own check)** `applicability_hash` MUST be present (this meaning's own narrowing; core only
  recomputes its digest when the field already exists). The digest recomputation against
  `applicability.toml`'s actual bytes is no longer restated here: `check_core.check_documents`
  already performs it, on every profile, whenever `[conformance].applicability_hash` is present.
  A mismatch still fails closed — the message now reads
  `B6: conformance.applicability_record: …`, not `C7: …`. Row equality covers BOTH `applicability`
  AND `reason` (exact string) for every clause — every manifest claim's `applicability` and its
  reason must equal `applicability.toml`'s row for that clause. `declared_at` (the
  `applicability.toml` record)
  and `[conformance].applicability_declared_at` (the manifest) must be present, EQUAL, and RFC
  3339-shaped. This is stated plainly: the hash binds CONTENT; that the declaration preceded
  evidence being read is PRODUCER-ASSERTED, not mechanically established by anything in this
  format. The timestamp-equality check proves internal CONSISTENCY between the two files, not
  temporal ORDER — no wording anywhere in this profile claims otherwise.
- **Applicability-hash wire form** — domain-separated the same way F2 is:
  `sha512(b"applicability-record:" + <applicability.toml bytes>)`, written as
  `applicability_hash = "applicability-record:sha-512:<128-hex>"`.
- **C8 (E-6, class B9, code/rust binding)** — the `code/rust` binding rejects a
  WEIGHTED claim with at least one `kani-harness` record when every cited Kani record
  explicitly declares `cover_only = true`. Non-Kani records do not excuse it; zero
  Kani records do not trigger it. Names are never interpreted. The legacy
  `[conformance].cover_only` list is read-only with a deprecation WARNING at
  `0.1.0-draft`, and rejected at `0.2`. Unweighted cover-only claims are permitted.
  A record tally never lifts weight in `/0`; manifest-side `cover_tally` is rejected
  anywhere, independently of weight. A Kani verdict on a cover-only harness cannot
  report false: an unsatisfied `kani::cover` is still `VERIFICATION:- SUCCESSFUL`
  (finding E-6, design history, not published).
- **C9 (narrowed at 0.2 — de-duplicated against the core's own check)** no aggregate score anywhere. The
  manifest-wide aggregate-key scan is no longer restated here: `check_core.check_no_aggregates`
  already covers the WHOLE manifest, on every profile, unconditionally (a `B7:`-prefixed message,
  not `C9:`). C9 keeps only what core cannot see: `applicability.toml` and the clause inventory,
  the two profile-declared assertion surfaces (design rule 3 restated for those two documents).
- **C11 — RETIRED at 0.2 (lowered to class B8).** The pre-`/0` borrowed-evidence contract
  described in this section through `profile_version 0.1.0-draft` (`source_claim`,
  `source_claims_other`, `[conformance].source_manifest{,_hash}`) is gone: the meaning no longer
  reads these fields, at any declared `profile_version` — their presence is a hard `C8:`-prefixed
  error, not a warning with a grace period ("no compatibility shim," by design). A borrowed claim now cites its source with a class B8 `acceptance-claim` reference
  evidence entry in `evidence` (`core.md` B8) — see "Evidence borrowed from a verification
  manifest," below, for what that entry looks like and which core rule owns each part of the old
  C11 contract (hash-before-parse, source-claim existence and status, non-control membership,
  band ceilings, cycle/depth guards). This meaning adds no B8-specific mechanism of its own;
  `check_core.check_reference_evidence` is the entire admissibility check.
- **Fail closed**: unknown profile suffix, missing inventory, or missing record ⇒
  `INDETERMINATE` (exit 2), never `PASS` — the D1 amendment A1 rule (item 8) restated for this
  meaning: a leaf is evaluable only when both its meaning-check (`conformance.py`) and its
  binding-check (`conformance/code/rust.md` / `bindings/code/rust.md`) are available.

## Evidence borrowed from a verification manifest (supersedes §1.5's carry rule)

The first subject's conformance claims are generated by citing a verification subject's
already-captured Kani/Lean records — BORROWED evidence, not freshly run evidence. `assurance-
bands.md` rule 6 is explicit that **a control attests only the claim its `of_claim` names**.
rev02's observed-red controls name `PM/<module>` (the rev02 module claim); re-pointing one of them
at `CONF/<clause>` (a generated conformance claim) would forge an attestation the control never
made. So: **controls do not transfer.**

A generated conformance claim built this way is governed by class B8, above (`core.md` B8, C11's
0.2 disposition): `evidence` carries one `kind = "acceptance-claim"`, `family = "reference"` row
per contributing rev02 claim — `ref = "<rev02 manifest path>#PM/<module>"`, `result = "pass"`,
`manifest`/`manifest_hash` naming and hash-pinning the rev02 manifest, `claim = "PM/<module>"`,
and `records` = that claim's own cited `record_hash` values (`record:`-domain, exact membership
against what rev02 itself declares). A clause discharged by more than one rev02 module claim (e.g.
a framing rule both `PM/tag` and `PM/length` touch) carries one reference row PER contributing
claim — B8 has no single-row multi-source shape, so this replaces the old
`source_claim`/`source_claims_other` pair naming one row with two (or more) rows naming one source
each. Stated in the same terms as the ruling that motivates it, a generated claim:

- cites the hash-pinned rev02 evidence records by their OWN `record_hash` values, never a copied
  `[claim.evidence.control]` block and never a claim-level `control` key — B8 refuses to cite an
  entry that carries a `control` table in the source, and refuses a referencing claim that carries
  one of its own (steps 4–5; the planted-twin/mutation control entries are never citable, so
  nothing about the copy can smuggle one in);
- is `weight = "unweighted"` — B8 step 6 evaluates weight eligibility with every `acceptance-claim`
  record removed; a claim with no other, native evidence is unweighted by construction;
- has `band ≤ min(band of every cited source claim, the control-free ceiling)` (B8 step 7), never
  any source claim's own, control-lifted band;
- carries a plain-text reason for the downgrade — **that reason lives in the claim's own
  `statement` field.** The nonempty-`statement` check is the CORE validator's, which already
  requires `statement` to be a nonempty string on EVERY claim, unconditionally — not a rule this
  meaning adds or duplicates. Whether the sentence actually, adequately explains THIS downgrade is
  reviewer-owned, not mechanically checked by either checker — the same honest limit as every
  other free-text field in this format;
- an evidence-less claim (a `gap`, or a `not-applicable`/`excluded` claim under C3/C4) carries no
  `acceptance-claim` row at all — it borrowed nothing.

**Weighted count in this profile is therefore ZERO, honestly** — every generated claim in the first
subject is unweighted by construction, because every one of them borrows rev02 evidence under this
rule. FINDINGS.md for the generated subjects must state the two ways up from here (open question C3, below,
is the second):

1. **A per-clause observed-red Kani campaign** — mutate the clause-enforcing line, watch THAT
   clause's own harness go red, exactly what an earlier worked example did by hand (design
   history, not published).
2. **open question C3's `discharged_by`** cross-manifest reference — if and when that mechanism is ruled, a
   conformance claim could discharge by reference to a verification claim's own, non-transferred
   control, rather than by copying evidence at all.

## What this profile does NOT define

- No aggregate conformance score or percentage (design rule 3 applies unchanged).
- No certification body, mark, or attestation of conformance — this is the producer's record and
  the consumer's re-check, not a certificate issued by a third party.
- No signing (reserved hooks H1–H8 unchanged).
- No quoting of standard text, ever (the COPYRIGHT RULE):
  inventories carry clause numbers and short titles in the producer's own words only, never
  normative text.
- No claim that the clause inventory IS the standard — it is a declared, in-tree slice written by
  hand from the standard's structure; its faithfulness to the external document is a disclosed
  residual (open question C5), not something this format checks.
- No cover-only weighting (Constraints C8 / E-6): an unsatisfied `kani::cover` on a witness harness
  is not evidence a claim decided anything, no matter how green the exit status.

## Conformance examples

`conformance/examples/valid/acceptance.toml` (passes) and `conformance/examples/invalid/` (fails
for a named C1–C9 reason, not a syntax error), built against a small self-made inventory fixture,
shipped alongside this profile and wired into the gate suite.

## Admissibility check (item 8b)

The meaning-side admissibility check for this profile is `tools/profiles/conformance.py` (standalone;
imports `tools/acceptance_grammar.py`, native `check(doc, ctx)`; `--selftest` with one able-to-fail
red fixture per Constraints rule and fail-closed — 182 cases). It
checks: per-clause applicability-statement well-formedness (every clause `applicable` /
`not-applicable` / `excluded`, the last two with a reason); that `[spec].provenance = "external"`
(C6, narrowed) — `provenance = "in-tree"` is `INDETERMINATE` at this profile_version
above), not a path this check validates; `[spec].axis` present and `clause_source` on every claim
(R-8); and Constraints C1–C10, C8 (the `code/rust` binding's own delta). What used to be C11 (the
pre-`/0` borrowed-evidence lineage) is retired at 0.2: presence of `source_claim`,
`source_claims_other` or `[conformance].source_manifest{,_hash}` is now a hard error at every
`profile_version`; a borrowed claim is validated entirely by `check_core.check_reference_evidence`
(class B8) once it carries a real `acceptance-claim` evidence row. C6/C7/C9's digest and
containment sub-checks are likewise retired from this module — `check_core.check_spec`,
`check_core.check_documents` and `check_core.check_no_aggregates` already cover them on every
profile, unconditionally (de-duplicated against the core's own checks, per Constraints C6/C7/C9 above).

The core supplies the entry point, orchestration and class checks (8a). R-10 is
closed: the `code` and `code/rust` binding checks (8b) are available, and a full leaf
composes meaning ∧ binding. Scoping flags apply only to a known leaf whose other
half is missing. When both halves exist, the flag is ignored with a NOTE and the
full composed verdict is reported.

## Open questions and dispositions

- open question C1 — CLOSED (2026-09-20): conformance is a sibling of verification, distinguished by required per-clause applicability.
- open question C2 — CLOSED (2026-09-20): an audit checklist may be the standard, including an in-tree checklist; provenance follows F2 relative to the certified tree.
- open question C3 — may a conformance claim discharge by reference to a verification claim about the same
  item (a `discharged_by`-shaped cross-manifest reference; design history, not published), and what
  profile compatibility rule governs that reference? STILL OPEN — tied to "Evidence borrowed
  from a verification manifest," above as the second of the two ways this profile's weighted count
  climbs off zero; this document does not resolve it.
- open question C4 (new, 2026-09-21) — the evidence-record projection carries no
  cover-tally field (`mutants_total`/`mutants_caught`, `spec/evidence-types.md`, are the only
  optional tally fields today, and neither is a `kani::cover` tally). A manifest-side `cover_tally`
  key is REJECTED wherever it appears, independent of weight — that reading of C8 is removed
  entirely, it is not a permitted escape at any weight. Until an evidence-RECORD tally field exists,
  a WEIGHTED claim whose every cited `kani-harness` evidence is cover-only FAILS C8 (see C8, above);
  the unweighted shape of the same claim is permitted. The fix: add an OPTIONAL
  `cover_satisfied`/`cover_total` (or similarly named) pair to the evidence-RECORD schema, so a
  cover-only harness can someday earn weight on its tally. This is a `spec/`-level schema
  extension, deferred rather than made in this document — recorded here as the fix E-6/C8 actually
  needs.
- open question C5 (new, 2026-09-21) — the F2 digest over the clause-inventory file proves the checked-in
  inventory's bytes are what they are (a CONTENT binding); it does not, and structurally
  cannot, prove the inventory FAITHFULLY represents the external standard it slices. What evidence
  (a second reviewer's sign-off against a purchased copy? a diff review recorded somewhere?) would
  ever discharge that judgment-level question is undecided; nothing in this format decides it
  today.
- open question C6 — CLOSED (2026-09-24, 0.3 open question 9, decided: A0 is correct, the stricter reading). The
  discrepancy flagged earlier ("FLAGGED, not fixed") is now fixed:
  `spec/evidence-types.md`'s "judgment family rule" prose said "cannot assert band above A1"; it
  now reads A0, matching `spec/assurance-bands.md` rule 3 and the validator's enforcement. This
  document's band-ceiling table above (`judgment` ≤ A0) already agreed with the corrected text.
