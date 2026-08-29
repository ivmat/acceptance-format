# Evidence-type registry + admissibility rules (v0)

## Overview — orientation only; every rule below is stated in its own section

**Normative for the `[[claim.evidence]]` record:** which evidence kinds are admissible and what
each must carry, the closed `epistemic_tier` axis and the open `method` token, the M11 hash fields,
and the family-agnostic `control` block the band gates in `assurance-bands.md` are built on. Read
the required-fields list first (it sits in the `epistemic_tier` section, ABOVE the registry table),
then the registry table itself; what follows those two is per-field detail, the profile
`method → epistemic_tier` obligation, the `control` sub-table's rules, and the M11
content-hashing construction.

Open taxonomy: any gate species can be evidence, **if** its record carries the fields that make it
attributable and reproducible. A record missing a field this revision requires is an assertion, not
evidence — the validator errors (the two fields required only at freeze are listed apart from
those, below). Adding a kind = adding a row here + a registry entry in the validator, in the same
commit.

## Epistemic tier — closed, core, artifact-agnostic

A `[[claim.evidence]]` record's `epistemic_tier` field is **required at freeze and TRANSITIONAL in
this revision** — a record that declares it is fully validated against the rules below, a record
that omits it is still admissible and draws a warning (see "Required fields", below). Where the
field is present its value is one token from a **closed, CORE, artifact-agnostic** set. This is a
different axis from `family` (below) and, by ruling, a different WIRE KEY from the
weight-architecture's WEIGHTED/UNWEIGHTED "tier" (core.md
§0): that axis's key stays `weight`/`grade`-adjacent vocabulary exactly as 0.1 already has it;
this axis's key is `epistemic_tier`. In prose either may be shortened to "tier (T1–T5)" once the
section has said `epistemic_tier` once; the two are never spelled the same in TOML.

**Each row below is a CEILING, not an assignment: the strongest `epistemic_tier` that the row's
right-column `method` tokens (the FV profile's `method → epistemic_tier` table) may declare** — a
record may honestly declare that tier or any weaker one; a stronger declared tier is a validator
error (spelled out in full under "The profile `method → epistemic_tier` table", below).

| `epistemic_tier` | means | this profile's code column (FV) |
|---|---|---|
| `T1` | deductive, kernel-checked derivation | `lean-theorem` |
| `T2` | mechanically sound semantic decision over the record's declared model and domain, by exhaustive exploration or sound abstraction; no claim outside that scope | `kani-harness`, `flux-refinement` |
| `T3` | empirical-sampled | `unit-test`, `property-test`, `fuzz`, `miri` |
| `T4` | mechanical-syntactic | `lint`, `semver-check`, `dep-audit` |
| `T5` | human-judgment | `human-review`, `llm-review` |

**Tier order compares warrant species only under equal claim, model, semantics, oracle,
assumptions, and scope.** T2 ≥ T3 means a sound decision dominates sampling over that same
domain; tiers do not rank records with non-comparable scopes. T1–T5 are not a general strength
order over unrelated records — the table above orders warrant *species*, and a comparison between
two records is only meaningful when both hold everything else equal.

**T1's load is scoped, not general.** A T1 (kernel-checked) record is reality-grounded only for
the derivation it actually decides — a kernel validates that a proof follows from
its axioms, never that the axioms adequately formalize the informal item. T1 classifies
derivation checking, not truth of the manifest statement or adequacy of its formalization. A
kernel-checked proof of the wrong formal statement remains T1 as a method record but does not
thereby establish the intended claim. Formalization, axiomatic, and semantic dependencies belong
in `[[claim.assumes]]`; contrary evidence belongs in H4 `[[defeater]]`.

**`epistemic_tier` is CORE and closed; adding a new tier value is the one non-profile-local
change.** A profile may not invent a T6 or redefine what T1 means — that would let a profile
manufacture epistemic strength the format did not certify. Everything else about how a profile's
concrete techniques map to these five tokens is profile-open (see the `method → epistemic_tier`
table, below).

Required fields (every kind), split by when the requirement binds:

- **Required in this revision:** `kind`, `family`, `ref`, `result`, `tool`, `record`. A record
  missing one of these is an assertion, not evidence — the validator errors.
- **Required at freeze, transitional in this revision†:** `epistemic_tier`, `method`. A record
  missing one of these is still admissible today and draws a warning, not an error.

**† `epistemic_tier` and `method` are REQUIRED AT FREEZE and TRANSITIONAL in this revision (CS-1,
CS-2).** `tools/check_acceptance.py` deliberately treats both as optional for now: where a record
declares them they are fully validated (`epistemic_tier` against the closed `T1`–`T5` set, and
against the profile-pinned tier its `method` earns AS A CEILING — see the profile table, below;
a weaker declared tier is accepted, a stronger one is an error); where a
record omits them, the record is still admissible. Stated plainly rather than softened: an omission
today draws a WARNING (ruled 2026-08-28), not an error: the record stays admissible, but a
producer is now told that a field the frozen format will require is missing. At freeze this
transition ends and both fields move into the first bullet, required of every record, with the
omission WARN becoming a hard error; the ratchet is booked in `maintainers/VALIDATOR-TODO.md`.

`bounds` and `semantics` are required where marked below — absence there is not
"unbounded/default", it is inadmissible, because unstated scope is how a bounded check gets read
as a proof. `record_hash` and `subject_hash` are documented separately, below ("Content-hashing" —
M11 content-hash fields).

| kind | family | extra required | what it can evidence | notes |
|---|---|---|---|---|
| `kani-harness` | bmc | `bounds`, `semantics` | A1–A3, bounded | tool at commit granularity; `unsupported` result ⇒ claim should be `parked`, not `gap` |
| `lean-theorem` | kernel | `axioms` (list; `[]` is the strong claim), `semantics` = lean/mathlib pins | A4, unbounded | kernel-checked; axioms declared, never implied |
| `flux-refinement` | smt-refinement | `bounds` = "unbounded-smt", `semantics` | A2–A3.5 invariants | CANDIDATE — tool not adopted; kind reserved |
| `unit-test` | dynamic | `cases` (count) | point claims; rejection/acceptance behavior at named inputs | a test's non-vacuity witness is that it RUNS the item — `record` must show execution |
| `property-test` | dynamic | `cases`, `generator` | sampled set claims | shrunk counterexamples land in `record` on fail |
| `fuzz` | dynamic | `corpus_size`, `duration` | absence-of-crash on sampled inputs | coverage data in `record` when available |
| `miri` | dynamic | `semantics` (flags) | UB-freedom on executed paths | executed-paths-only is the boundedness; say so in `bounds` |
| `lint` | mechanical | — | mechanical hygiene claims (no-unsafe, clippy class) | small, cheap, still admissible |
| `semver-check` | mechanical | `baseline` (prior version) | API-compatibility claims | cargo-semver-checks or equivalent |
| `dep-audit` | mechanical | `db_version` | advisory-freedom at a date | claim decays with time; date lives in `record` |
| `human-review` | judgment | `reviewer` | anything, weakly | **declared-null likelihood by convention** — gates flow, adds no computed trust; never the sole evidence for band ≥ A2 |
| `llm-review` | judgment | `reviewer` (model id) | anything, weakly | same convention as human-review |

There is no dedicated CONTROL *kind* — see "Control block" below: any of the kinds above may carry
one as an optional sub-table.

## `method` — open, profile-defined — and `kind`'s demotion to a hint

`method` is the second field on the transitional terms above: **required at freeze and TRANSITIONAL
in this revision** — validated where a record declares it, warned-but-admissible where a record
omits it. Where present, it is an **open, profile-defined** token naming the concrete technique
(`kani-harness`, `lean-theorem`, `robustness-proof`, `schema-validate`, …).
`method` is what a profile's `method → epistemic_tier` table (below) keys on to CAP the
`epistemic_tier` above — the table sets the strongest permitted value for that `method`, a record
may honestly declare that tier or any weaker one, and a stronger declared tier is a validator
error; it is the field that carries epistemic weight into the format.

**A `method` token MUST identify its warrant-relevant mode, not merely a tool family** — the same
underlying tool can produce warrants of different strength (a bounded harness run exhaustively
over its declared domain versus the same harness run as a sampler), and `method` names which mode
actually ran, because that mode is what `epistemic_tier` is grading. **If one run supplies
independently usable warrants at different tiers, emit separate evidence records; if the warrants
are inseparable, assign the weakest necessary tier** — a record is epistemically atomic, so a
hybrid campaign that genuinely produced two distinct warrants is two records, not one record
claiming the stronger of the two.

**`kind` (the registry column above) is retained but demoted: it is a profile-open HINT, never
authoritative for grading or tier assignment.** For the FV profile shipped with this revision,
`kind` and `method` coincide in spelling (`kind = "kani-harness"` and `method = "kani-harness"`
name the same registry entry) — this is a convenience for the one profile that exists today, not
a rule that the two fields must agree in general. A future profile may register a `method` with no
corresponding `kind` entry (an artifact class `kind` has no registry token for at all); the
validator does not require `kind` to resolve `method`, only the reverse direction never holds.

**`family` (bmc | kernel | smt-refinement | dynamic | mechanical | judgment) is UNCHANGED BY THIS
REVISION** and continues to govern `assurance-bands.md`'s control-lift carrier-family-compatibility
gate exactly as today — add-alongside-and-flag, not retire-or-rewrite, for this revision. The
eventual migration target is that `assurance-bands.md`'s band-gates come to read `epistemic_tier`
directly, and `family` itself retires into profile `method` vocabulary — **that migration is its
OWN follow-up change entry against `assurance-bands.md`, never a silent rewrite of the band rules
smuggled in here**: this revision ships `epistemic_tier`/`method` alongside the untouched `family`
field; it does not touch a single sentence of `assurance-bands.md`'s existing band-gating text.
Both `family` and `epistemic_tier`/`method` are independently checked until that follow-up entry
lands — `family` as a required field, `epistemic_tier`/`method` on the transitional terms above.
Neither axis substitutes for the other in the meantime.

**Note on `[subject].kind`.** `[subject].kind` (`format.md`, the artifact-class field) is a
**distinct field** from `[[claim.evidence]].kind` (the registry column above, now a hint). The two
fields share a name and nothing else; conflating them misapplies this demotion to a field it does
not touch — `[subject].kind` is not demoted by anything in this revision.

## The profile `method → epistemic_tier` table is mandatory wherever `method` is used

A profile that declares any `method` token MUST publish a `method → epistemic_tier` mapping
covering every token it declares. Where a record declares both fields, the tier its active
profile's table assigns to that record's `method` is a **CEILING** on its `epistemic_tier`
(above): a declared tier STRONGER than the pinned one is a validator error (a producer does not
get to self-assign a stronger `epistemic_tier` than the method earns), and a declared tier
weaker than or equal to the pinned one is accepted. **The ceiling is deliberately one-sided**
(clarified 2026-08-28; this sentence read "MUST equal" and contradicted its own parenthetical, and
`tools/check_acceptance.py` enforced the equality): conservative deflation is not an overclaim, and
a format built to refuse overclaims must not turn around and forbid a producer from recording a
WEAKER tier than the technique would allow. A `kani-harness` record marked `T3` because that
harness only samples the space is an underclaim, not a violation. `docs/decisions/ADR-002-epistemic-
tier-vs-method.md` states the ceiling directly ("may never exceed") and is the reading that governs.
Where no profile is declared for a `method` token, the record's `epistemic_tier`
is **indeterminate**, not silently `T5` (see `core.md` §8.3's tri-state validator contract for
what "indeterminate" means at validation time).

**Disclosure: profile selection has no wire mechanism in this revision — the FV profile above is
HARD-CODED** (stated 2026-08-28). This section says a record's tier is resolved against "its
active profile's table", and there is nothing on the wire that selects one: no `[format].profile`
identifier, no field carrying or pointing at a mapping table, and `tools/check_acceptance.py`
applies the single FV table above to every manifest it reads. So a second profile cannot be
expressed at all today, and a manifest produced under one would be silently graded against FV's
table. The `method` axis is profile-OPEN by design and this revision ships exactly one profile;
that is a shipped limitation, not a property of the format. Defining the selection mechanism, and
how a consumer authenticates the mapping it resolves (an unauthenticated profile table is a place
to manufacture the epistemic strength ADR-002 split these two fields to prevent), is a
freeze obligation, booked in `maintainers/VALIDATOR-TODO.md`.

## Content-hashing (M11 content-hash fields) — `record_hash` and `subject_hash`

**`record_hash` — the evidence-record content-hash (P9).** Every `[[claim.evidence]]` record MAY
carry `record_hash`, the M11 `evidence-record:`-domain content-hash (`format.md`, "Content-hashing
(M11)") of the file its `record` field points at, in the self-describing form
`"sha-512:<128-hex>"`. Compute it with `python3 tools/m11.py evidence-record <path-to-record-file>`
— that one command is the whole recipe; `tools/m11.py`'s `--help` lists the other domains this
same CLI computes. **REQUIRED on every WEIGHTED claim's evidence; OPTIONAL on unweighted**
(P9; `format.md`'s "Content-hashing (M11)" section — always-reference the record file, never inline
its bytes; inline embed is explicitly deferred). A **present-but-mismatched** `record_hash` is ALWAYS an error, on a
weighted or unweighted claim alike — it is a *detected falsehood*, not an absence: the manifest
named a hash and the file does not have it, and reporting that as clean would be vouching by
silence, one representation down. An **absent** `record_hash` on an unweighted claim's evidence
stays a note. `tools/check_acceptance.py` recomputes and compares this hash for every
non-illustrative manifest (`[format].illustrative`, `format.md` CS-21/22); illustrative manifests
stay shape-only and skip both the recomputation and the required-on-weighted obligation (their
`record` pointers are routinely fixture-only or absent).

**`subject_hash` — evidence-subject binding (`format.md` design rule 4a).** An evidence record MAY
carry its own `subject_hash`, naming which subject content (in the same self-describing M11 form)
the record's `result` was actually computed against. Where present, it MUST equal
`[subject].subject_hash` (`format.md`'s schema) exactly — a mismatch is the hard error design
rule 4a ships as a validator obligation. `[subject].subject_hash` is itself OPTIONAL in this
revision; when the manifest does not declare one, no evidence record's `subject_hash` has anything
to be checked against, and the check does not fire. Both fields are computed under the `subject:`
M11 domain (`format.md`, "`subject:` domain" — added post-ratification 2026-08-28, closing the
audit-surfaced gap where this field named a hash no domain computed): a single-file subject hashes
its own raw bytes; a multi-file subject (crate, workspace) hashes a bundle-root-style inventory
over its declared file set, a case this revision's tooling does not yet compute (see that
section).

This is a distinct field and a distinct check from `record_hash`, above: `record_hash` verifies
the evidence RECORD FILE has not been tampered with since it was cited; `subject_hash` verifies
the evidence is bound to the SUBJECT the manifest actually certifies. Neither is compared against
`[subject].commit` — a git-domain identity (SHA-1, over the repository tree, a different algorithm
over a different object) — comparing an M11 hash against a git commit sha is the category error
design rule 4a explicitly does not make.

## Family semantics (why `family` is required)

`family` is the correlation key for the future trust-ledger layer: same-family evidence shares
blind spots and must not be double-counted; cross-family evidence (bmc × kernel × dynamic) is
where real assurance accumulates. v0 records the key and computes nothing (format.md rule 3) —
but recording it now is what makes the records upgradeable without re-running anything.

Proofs quantify over sets; tests over points. Both declare their scope the same way — `bounds`
for proofs (unwind limits / "unbounded"), `cases`/`corpus_size` for dynamic kinds. A manifest
reader must always be able to answer: *checked over what input space?*

## The `judgment` family rule

Judgment verdicts (human or LLM) are admissible — most real-world deliveries will carry them — but
they are permanently declared-null for trust until a measured calibration exists (no measured
calibration of judgment verdicts exists yet; pretending otherwise is exactly what rule 3 forbids).
The validator enforces: a claim whose only evidence is `judgment`-family cannot assert band above
A1.

## Control block (`control = { kind, expectation, observed, of_claim }`) — the observed-red witness

**Corrected 2026-08-22** (the first cut of this section, which fixed a control's family to
`dynamic` via two dedicated kinds `mutation-test`/`anti-vacuity-fixture`, mislabeled der's real
controls — kernel-family mutated Lean theorems and bmc-family mutated Kani harnesses are not
"dynamic." Controls are **family-agnostic**.)

A control is **NOT a special evidence kind**. It is an optional `control` sub-table any evidence
record above MAY carry, regardless of that record's own `kind`/`family`:

```toml
[[claim]]
id = "L-length"          # the claim's own id — of_claim below must equal THIS
...

  [[claim.evidence]]
  kind      = "lean-theorem"      # the record's own kind — unchanged, still species evidence
  family    = "kernel"            # states what was PERTURBED: kernel = mutated Lean theorem here
  ref       = "decode_accepts_only_canonical (mutant: flipped comparison)"
  result    = "fail"              # the mutated theorem does not typecheck — this IS the expected outcome
  tool      = "lean4@4.x-pinned + lean-mutate@pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/mutant-length.lean"

    [claim.evidence.control]
    kind        = "mutation"      # mutation | ablation | planted-twin
    expectation = "red"           # red | green | sat
    observed    = "red"
    of_claim    = "L-length"      # MUST equal the id of the [[claim]] this record is under
```

- `family` on the record states what was perturbed and stays exactly what it would be without a
  control: `kernel` for a mutated Lean theorem, `bmc` for a mutated Kani harness (implementation
  mutated, the SAME harness re-run), `dynamic` for a cargo-mutants/stryker/mutmut run over a test
  suite, `mechanical` for a seeded-bad gate fixture (a planted-twin a gate must catch). The
  `control` block's own `kind` (mutation/ablation/planted-twin) is orthogonal to family — this
  mirrors a pre-existing internal receipt format's control block `{kind, expectation, observed,
  of_claim}`, so the format and that receipt format share one control definition and an emitter is
  a 1:1 map, not a re-derivation.
- **Binary floor, and "passes" ≠ "band-lifts"** (tightened 2026-08-22, F1): a control **passes**
  (behaved as predicted) iff `observed == expectation` — nothing else. But a control only
  **band-lifts** when it is a **literal `red`**: `expectation == "red"` AND `observed == "red"`.
  A `green`/`green` or `sat`/`sat` control also passes (it behaved as predicted) and is perfectly
  recordable, but it does NOT lift a band — it never showed the oracle catching anything wrong.
  Passing is independent of the record's own `result` field: a kernel-family control record for a
  rejected mutated theorem legitimately has `result = "fail"` (the mutated proof did not typecheck)
  while its `control.observed = "red" == control.expectation = "red"` — the control PASSES (and
  band-lifts) precisely because the underlying check failed the way it should. Do not conflate any
  of these three notions.
- **The contradiction guard (F4).** `control.kind = "mutation"` **AND** `control.observed = "red"`
  **IMPLIES** the carrier evidence record's own `result != "pass"`. A record cannot simultaneously
  claim its own check passed (`result = "pass"`) and that a mutation of the thing it checks was
  observed red *by this same record* — an observed-red mutation control means the mutant was
  rejected, which is a property of a **different** run (the mutant run) than the one `result`
  describes (the baseline run). A record stating both is self-contradictory on its face and is a
  validator error, additive to the existing control-block rules (`assurance-bands.md` rule 6) — it
  does not replace or loosen any of them.
- **Carrier-family compatibility** (tightened 2026-08-22, F2): the CARRIER record — the evidence
  record the `control` block sits on — must itself be species-compatible with the band being
  lifted: A4 needs `family = "kernel"`, A3 needs `"bmc"`, A2 needs `"bmc"` or `"dynamic"`,
  oracle-bearing A1 needs `"dynamic"`. `judgment` is compatible with none of these — a
  `human-review` record carrying a `control` block never band-lifts anything, regardless of what
  the block itself says (assurance-bands.md rule 6).
- **`of_claim` MUST equal the id of the `[[claim]]` the record is recorded under.** A control block
  whose `of_claim` names a *different* claim does not satisfy the enclosing claim's gate — a
  gate-level fixture that proves a gate fires controls that gate's own claim, not every behavioural
  claim it nominally covers (assurance-bands.md rule 6). This check runs for **every claim
  status** (evidenced/partial/gap/parked, tightened 2026-08-22, F4) — a `partial` claim's
  mis-pointed control is caught too, even though `partial` never asserts its band is reached.
- `mutants_total` / `mutants_caught` are OPTIONAL data fields on any evidence record (not tied to
  any particular kind), for dynamic mutation-testing records (cargo-mutants/stryker/mutmut) that
  want to state a tally. They are DATA and GAPS, never a score: surviving mutants are recorded, a
  human triages equivalent mutants, nothing is auto-deducted into the band (rule 3/F4 intact). If
  present alongside `result = "pass"`, `mutants_caught` must be ≥ 1 — the binary floor restated in
  the tally.
- No control is admissible to *raise* a judgment-family claim (rule 3 is unconditional — judgment
  has no mechanical oracle to mutate).
- **Per-band `control.kind` whitelist** (tightened 2026-08-22, mirrors a pre-existing internal
  system's audit — `kind == "mutation"` for its own controls-check): A3/A4 and functional A1
  require `kind == "mutation"`; A2 accepts `kind ∈ {"mutation", "ablation"}`. **`kind ==
  "planted-twin"` never satisfies a band-lift, at any band** — it proves the pipeline can reject at
  all (a satisfiability/pipeline signal, a pre-existing internal system's separate
  acknowledgment-witness role), not that THIS claim's own oracle catches a mutation of THIS
  impl/theorem. A planted-twin record may still be
  present in a manifest as disclosure/satisfiability evidence — it just never counts toward the
  gate (assurance-bands.md rule 6).
- **`of_claim` must resolve.** A `control.of_claim` naming a claim id that does not exist anywhere
  in the manifest is an error — a control pointing at a phantom claim (assurance-bands.md rule 8).
- **`captured_at_commit` — OPTIONAL per-record provenance disclosure (P3, design ruled
  2026-08-29).** Any `[[claim.evidence]]` record MAY carry `captured_at_commit`, naming the git
  commit at which THAT record's transcript was captured — a git object name, full or abbreviated
  (`tools/check_acceptance.py`'s `SELF_LOCATION_SHA_RE`: 7-40 lowercase hex, the same floor
  `[format].spec_sha`/`validator_sha` already use). It is a plain per-record field, not nested
  under `control` and not limited to control-carrying records — documented here because the
  stale-control policy below is the concern that motivated it. It formalizes, as a real field, the
  ad hoc workaround this format already tolerated: naming the actual capture commit inside the
  free-text `tool` field plus a disclosure comment on the record (`format.md`'s "Partial
  re-certification"). `captured_at_commit` ADDS the structured disclosure alongside that
  workaround — a producer supplies both, not one instead of the other. It does not alter
  `format.md`'s own partial-recertification requirements (the capture commit still MUST be named
  in the evidence `tool` field, and the exception still MUST be disclosed in a comment on the
  record) — `format.md` itself is unchanged by this field.

  **`captured_at_commit` is DISCLOSURE ONLY — it is NEVER a second validity key.** Validity binding
  stays exactly where design rule 4a already put it: a record's `subject_hash`, where present,
  MUST equal `[subject].subject_hash` (Content-hashing, above) — that comparison is what decides
  whether a record still speaks to the subject a reader holds. `captured_at_commit` answers a
  different question ("when was this run") and settles nothing about whether the record is still
  good on its own: a record naming an old commit with a matching `subject_hash` is exactly as valid
  as one naming today's commit, and a record naming today's commit with a stale `subject_hash` is
  exactly as invalid either way. The validator checks `captured_at_commit` for SHAPE ONLY — a
  malformed value is a hard error, unconditionally, the same fail-closed treatment
  `record_hash`/`subject_hash`'s own malformed-shape branches get, above: a disclosure that cannot
  be understood is worse than no disclosure.

  **The stale-control policy.** A `control` block's carrier record states an observation —
  expectation vs. observed — over the subject as it existed when the record was captured. Subject
  content moves between commits; a control's observation does not automatically travel with it. A
  control whose carrier record's subject content is UNCHANGED since capture (its `subject_hash` —
  when DECLARED on both the record and `[subject]` — still equals `[subject].subject_hash` at the
  commit a reader is checking) REMAINS VALID across commits — nothing about a mutation control's
  meaning depends on which commit happened to be current when it ran, only on whether the thing it
  perturbed is still the same bytes. Content that HAS CHANGED since capture VOIDS the control: the
  mutation was applied to code that no longer exists in this form, the control's
  `red`/`green`/`sat` observation says nothing about today's subject, and the control MUST be
  re-run before it is cited again. **When subject hashes are absent, this revision makes no
  machine-checkable content-continuity determination** — there is nothing for the validator to
  compare, so it cannot decide staleness either way; `captured_at_commit` MUST NOT be used as a
  fallback binding to fill that gap. `subject_hash` equality alone carries the content-validity
  binding. `captured_at_commit` supplies historical context only and MUST NOT be consulted to
  validate, invalidate, weight, or band-lift a record.

  **Granularity of "subject content" (ruled 2026-08-29): the design-rule-4a subject identity,
  exactly.** For a single-file subject that is the file's bytes; for a multi-file subject the
  inventory-hash construction over the declared subject tree — never any finer unit (a
  per-file identity is not a `subject_hash` and the MUST-equal rule rejects it), never the
  whole repository tree, and never the toolchain (a build input, pinned by the record's own
  provenance fields). A producer that wants finer-grained carry-over triage — e.g. treating a
  control as carried because one file's bytes are unchanged while the declared subject moved —
  may do so only as a DISCLOSED ASSUMPTION on the consuming claim (a `[[claim.assumes]]` entry
  naming the file-level identity relied on, the unproven cross-file build-input residual, and
  void-if triggers covering both a change to the harness's transitive build inputs beyond that
  file and a toolchain differing from the control's recorded pin). Such an assumption is
  void-not-discount like every other; it is never spec-blessed validity. The capture-time
  transitive-closure manifest — the principled successor to file-level triage — is booked in
  the 0.2 design stream.
