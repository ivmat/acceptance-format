---
type: proposal
digest: Profile: acceptance/troubleshooting 0.1.0 on the locked 0.3.2 core. Checked by tools/profiles/troubleshooting.py.
---

# Profile: `acceptance/troubleshooting` — vocabulary (checked by a validator)

`profile_id = "acceptance/troubleshooting"` · `profile_version = "0.1.0"` · parent:
`acceptance/core` · status: **candidate; checked by `tools/profiles/troubleshooting.py`**

<!-- The vocabulary below is self-contained. Do not remove a section or fill one by copying
     normative text from the core — point at the core instead. -->

## What a profile is

A profile is a closed vocabulary plus required fields, constraints, a version id, and at least one
conformance example that validates and one that fails (`spec/format.md` "Profiles"; protocol.md
§6.6). This document is that statement for the troubleshooting meaning, with the vocabulary not yet
enumerated.

## Meaning — what "accepted" says under this profile

Accepted means: **for each declared fault class, the evidence the artifact retains or exposes at run
time is sufficient to reach the declared diagnostic outcome, under the declared privacy, retention
and sampling constraints.**

The claim unit is a fault class paired with a required diagnostic outcome. Verification says the
artifact meets its requirements; this meaning says a later failure of the artifact is diagnosable.
The two are siblings and compose through `acceptance/deliverable`.

Absence rules: the existence of logs cannot discharge a claim, and missing telemetry
never counts as evidence that no event occurred.

<!-- TODO(producer): confirm against the first real subject. -->

## Artifact-type projections

| leaf id | binding | first plausible subject |
|---|---|---|
| `acceptance/troubleshooting/tool` | `bindings/tool.md` | the acceptance validator: mutation fixtures as injected faults, diagnostics as evidence |
| `acceptance/troubleshooting/estate-element` | `bindings/estate-element.md` | a delivered artifact with a reproduce receipt |
| `acceptance/troubleshooting/code/rust` | `bindings/code/rust.md` | a crate whose failure modes carry declared diagnostic outcomes |

<!-- TODO(producer): keep only the leaves a real subject exercises. -->

## Closed vocabularies this profile fixes

- **Fault classes.** OPEN per subject. The producer declares the fault classes a subject exercises,
  in the record; a consumer's contract names which of them are required deliverables. This profile
  does not fix a base set — a fault taxonomy is subject-specific (the `fault_classes` list is an
  example, not a closed enumeration).
- **Diagnostic outcomes.** CLOSED, ordered ladder: `detect` < `isolate_fault_domain`
  < `reconstruct_causal_sequence` < `identify_root_cause`. A higher outcome implies every lower one.
  `identify_failed_dependency` is NOT a fifth outcome: a failed dependency is a fault class whose
  isolated domain is external, so it is discharged through `isolate_fault_domain`, not through a
  separate rung.
- **Claim classes (`grade`).** REUSED UNCHANGED from the core — no new
  grade token. This profile adds claim fields instead: `fault_class`, `outcome`, `scenarios` (the
  bounds — the fault scenarios exercised), `outcome_criterion` and `scenario_source` (0.1.0, rows 2
  and 14 — see Required fields below).
- **Evidence kinds and families.** CLOSED, three families: `injected-diagnosis`
  (a diagnoser blind to the injected cause reaches the declared outcome from permitted evidence
  only), `telemetry-completeness` (drops, sampling, collector health, clock quality declared and
  measured), `diagnostic-structure` (static correlation/schema checks — required
  correlation fields exist on every path). "Logging exists" alone is not a
  kind and cannot discharge a claim.
- **Evidence families + family⇒tier ceiling table (D1 amendment A2).** Mapped onto the core's
  `T1 > T2 > T3 > T4 > T5` ordinal (`spec/core.md` rule, B3) using the SAME tokens `acceptance/verification`
  already closes (`../verification/PROFILE.md` §2, verbatim from the public
  `spec/evidence-types.md` — that table moved here from `protocol_acceptance/spec/profiles/rust-code.md`
  §2 in the R5 lift, 2026-09-24, open question 2) — no new tier token:

  | family | `epistemic_tier` ceiling | verified against |
  |---|---|---|
  | `injected-diagnosis` | T3 — empirical-sampled | `../verification/PROFILE.md` §2 (`unit-test`/`property-test`/`fuzz` row: "empirical-sampled") |
  | `telemetry-completeness` | T3 — empirical-sampled | `../verification/PROFILE.md` §2, same row; the check is a measurement over a running system, not a static read |
  | `diagnostic-structure` | T4 — mechanical-syntactic | `../verification/PROFILE.md` §2 (`dep-audit` row: "mechanical-syntactic") — the closest existing token to a static correlation/schema check; a fault class discharged ONLY by `diagnostic-structure` evidence cannot outrank a lint-class claim |

  Bounds: the set of fault scenarios exercised. A class with no exercised scenario is a gap, not a
  pass (Constraints, below).
- **Assurance bands.** `spec/assurance-bands.md`'s A0–A4 apply UNCHANGED — no new band vocabulary. A
  troubleshooting claim is **oracle-bearing**: the diagnoser is checked against a sealed, committed
  truth (its own blinding record, described in Required fields below), which is exactly the "postcondition oracle" shape the
  gate sentence addresses. So `assurance-bands.md`'s gate ("an oracle-bearing claim… cannot exceed A0
  without an observed-red control whose `of_claim` names it," rule 2) applies unchanged: this
  profile's control is the two-part ablation described in Required fields below, standing in for the
  core's observed-red control. Below A0 no control is required; A0 is this profile's control-free
  ceiling, same as every other oracle-bearing claim in the format.

## Required fields over the core

- On every claim: `fault_class`, `outcome` (one token of the closed ladder), `scenarios` (the
  bounds — the fault scenarios exercised; empty is not permitted on an `evidenced` claim, see
  C-T1/C-T5), `outcome_criterion = { granularity, grading }` (row 2, independent review —
  `granularity` is free text naming what is matched (e.g. `"field"`, `"rule-group"`); `grading` is
  CLOSED to `"exact-set"` in 0.1.0 — the predicted set must equal the true one exactly, never merely
  contain it; a top-k or threshold grading is a future document edit, not a silent new string), and
  `scenario_source = { rule, population }` (row 14 — the generator RULE a claim's `scenarios` were
  drawn from, in prose, and the `population` it drew from as a count; coverage is reported as a
  count out of a stated population, not whatever the producer happened to run).
- On every `injected-diagnosis` (`blind-diagnosis` kind) evidence record:
  - a `diagnoser` table naming `kind` — CLOSED set `deterministic`, `human`, `model-seat` (every kind
    is admissible, and a deterministic diagnoser MUST always be possible, since a diagnosis process
    must never depend on an LLM being available) — the diagnoser's `id`, and (row 8)
    `digest`, a `sha256:<64hex>` hash of the diagnoser's own code or prompt, fixed before the
    scenario set is sealed;
  - for `kind = "human"` or `"model-seat"` (row 20): an `isolation` table, `{ digest, tools }` — a
    packet or working-directory digest and the list of tools the diagnoser could use. No isolation
    CHECK exists yet in this format, so a `human`/`model-seat` diagnoser is capped at the
    control-free ceiling (A0) regardless of what it attests — this is a stated floor pending that
    check, not a claim that the attestation alone proves isolation;
  - a `held_out` bool (row 8) on the evidence record itself, stating plainly whether the scenario
    set was held out from the diagnoser's own authors — the first real record declares this
    honestly (`held_out = false`), not silently omitted;
  - a `blinding` table: `truth_hash` (the sealed truth's hash), `visible_evidence` (the list of
    evidence the diagnoser was permitted to see), and (row 7) `committed_at` — the 40-hex commit
    that carried the sealed truth-hash files before the diagnosis ran.
- A `[diagnostics]` table declaring the constraints under which the evidence was collected: privacy handling, retention minimum, sampling policy. The
  contract states the required values; the record declares the values actually in force.
- On a claim asserting a band above this profile's control-free ceiling (A0, Closed vocabularies
  above): a core control block with `kind = "ablation"`, `of_claim` naming the claim, `observed =
  "red"`, `expectation = "red"` (`spec/assurance-bands.md` rule 6: ablation removes a precondition
  and the property must break). `kind = "planted-twin"` never satisfies this gate, as in the core.
  **0.1.0 redefines what backs that control (row 1, independent review):** the earlier
  "evidence-stripped run" is WITHDRAWN — it deletes exactly the lines a deterministic diagnoser
  reads, so it could never fail, which made the control meaningless. Two controls now stand behind
  every ablation claim, both required, both checked by the harness before it writes a green result:
  - **no-fault**: the diagnoser runs on the UNMUTATED, green output and MUST return nothing;
  - **wrong-scenario swap**: the diagnoser runs on ANOTHER scenario's raw output and MUST NOT name
    THIS scenario's true group/key.
  The control's own `kind` stays `"ablation"` in the manifest (the removed precondition is the
  injected fault itself, unchanged); the two-part shape lives in a harness in the upstream
  development repository, not in this export, and is not new manifest vocabulary.

## Constraints

Per §6.6 item 6c, each constraint below must be exposed as a check the core calls, composed with
the binding's own check at the leaf — a constraint stated only in this document's prose is not a
constraint. This profile binds `spec/format.md`'s design rules 1–7 by reference. Profile-specific
constraints, **C-T1..C-T7, each marked IN FORCE or NOT IN FORCE**:

- **C-T1 (gap rule) — IN FORCE.** A fault class with no exercised scenario MUST be `status =
  "gap"`. It MUST NOT read as `evidenced`, and its absence MUST NOT be read as "diagnosable".
  `scenarios` entries are type-checked (nonempty strings) before
  any set/duplicate check runs — a malformed entry is a finding, never a crash (row 18).
- **C-T2 (unknown completeness) — NOT IN FORCE; fails closed (row 11).** No
  `telemetry-completeness` mechanism exists in this pass to establish drops, sampling, collector
  health or clock quality. Rather than silently pass `telemetry-completeness-check` evidence at its
  family ceiling, a claim citing it is INDETERMINATE ("C-T2 not in force in 0.1.0") — absence of a
  check MUST NOT be read as a clean pass, applied here to this profile's own
  incompleteness.
- **C-T3 (invalidation) — NOT IN FORCE.** No schema-invalidation tracking (telemetry schema
  version, collector version, semantic-convention version) exists in this pass. Stated
  here as owed, not silently dropped; a change to the subject artifact still invalidates claims
  through the core's own change-impact rule (`protocol.md` §8), which this profile does not
  narrow.
- **C-T4 (control gate) — IN FORCE.** A claim asserting a band above the control-free ceiling (A0)
  without a matching `kind = "ablation"` control (`observed = "red"`, `expectation = "red"`,
  `of_claim` naming the claim) MUST be capped at A0, never asserted at the ungated band (mirrors
  `spec/assurance-bands.md` rule 2). `kind = "planted-twin"` never lifts. 0.1.0 redefines what
  backs a satisfying control at the harness level (Required fields, row 1) without changing this
  manifest-level shape.
- **C-T5 (anti-cherry-pick) — IN FORCE; extended (rows 4, 13).** A claim lists ALL exercised
  scenarios of its fault class in `scenarios` — the bounds are the whole exercised set, not a
  favorable subset. Each `injected-diagnosis` evidence record's `results` table names, per
  scenario, the outcome actually reached (or a token below it), and MUST cover EXACTLY the claim's
  `scenarios` — no fewer, no more. `status` is CLOSED to `gap`/`evidenced`/`partial` (row 13 — any
  other token is an ERROR); `shortfall` is permitted ONLY when `status = "partial"`. Status
  `evidenced` requires every listed scenario to reach at least the claimed outcome; otherwise
  status MUST be `partial` with `shortfall` (a list of nonempty strings, type-checked before
  `sorted()` — row 18) naming exactly the scenarios that fell short — a claim that quietly narrows
  its bounds, or a `partial` whose `shortfall` does not match its own evidence, is an ERROR, not a
  lenient read. **Row 4:** the same check ALSO opens the evidence's hash-bound `record` pointer
  (already digest-verified by the core's B16) under this profile's own declared row schema — a
  JSON object with a `rows` list, each row `{fault_class, id, outcome}` — and requires
  `claim.scenarios` to equal every record row of the claim's `fault_class`, `results` to equal what
  those rows give, and a `fault_class` to be claimed by exactly one claim per record: a producer
  can no longer drop a bad scenario from both its own inline tables and pass, since both are now
  checked against the hashed truth file itself, not only against each other.
- **C-T6 (structural ceiling) — IN FORCE; extended (row 12).** A claim discharged ONLY by
  `diagnostic-structure` evidence (T4, static correlation/schema checks) MUST NOT claim an outcome
  above `detect` (states the family/tier ceiling table's own note, Closed vocabularies above, as a
  checked constraint rather than prose only) — AND can never discharge ANY claim (`status =
  "evidenced"`) on its own, at any outcome including `detect`: a static check shows the fields
  exist, not that a diagnosis was reached. Structure-only evidence may still SUPPORT another
  family's evidence; it never stands alone as the sole reason a claim is `evidenced`.
- **C-T7 (blind-diagnosis required above 'detect') — IN FORCE; new, row 3.** A non-`gap` claim
  whose `outcome` is above `detect` MUST carry at least one `blind-diagnosis` evidence record.
  Other families (`telemetry-completeness`, `diagnostic-structure`) may accompany and support that
  record, but never discharge the claim on their own — closing the earlier gap where a claim with
  telemetry-only, structure-plus-telemetry, or even NO evidence at all could pass the meaning check
  at any outcome up to `identify_root_cause`.

## What this profile does NOT define

- Fault resolution: reports, containment, diagnosis, fix, release, closure. That is a protocol
  (`protocol_acceptance/`), not a meaning.
- Fix acceptance: an ordinary acceptance of a new subject version with original-fault evidence
  (META-023). No separate profile.
- No decision, no obligation minting, no party-boundary machinery (as for every meaning).
- Deferred to the fault-resolution protocol (post-0.3, closure 0.3 open question 14): the `regression-witness` control token for fix claims, a
  `forensic` original-fault evidence kind plus a probabilistic-fault path, the
  `field-verification-failed`/`release-failed` transitions, and `fix_package.classification` plus
  the mitigation-only close guard. None of these bind in this format-level document.
- <!-- TODO(producer): add what the first subject tempted you to add and you declined. -->

## Conformance examples

Checked example files: `examples/valid.acceptance.toml` and `examples/invalid.acceptance.toml`
(plus `examples/SPEC.md` and `examples/evidence/results.json`, both files these two manifests point
at), laid out the same way `profiles/conformance/examples/` is — self-contained, synthetic, no real
diagnosis was run.

- **Valid.** A claim for a fault class, required outcome `isolate_fault_domain`, `outcome_criterion
  = { granularity, grading = "exact-set" }`, `scenario_source = { rule, population }`, `scenarios`
  naming the two scenarios exercised. Evidence: one `injected-diagnosis` (`blind-diagnosis` kind)
  record — a `deterministic` diagnoser (`digest` fixed, `held_out = false`), its blinding record
  carrying the sealed-truth hash committed before the run (`committed_at`) and the permitted
  evidence — whose `results` table shows both scenarios reaching `isolate_fault_domain`, matching
  the hash-bound record's own rows (C-T5, row 4). No band (floor, control-free A0). `python3
  tools/check_core.py profiles/troubleshooting/examples/valid.acceptance.toml` gives `PASS`.
- **Invalid.** The same claim shape, but backed ONLY by a `diagnostic-structure-check` record
  (structural correlation-field checks — the "logging exists" case: output was produced, nothing
  diagnosed) claiming `isolate_fault_domain`. Rejected by C-T6 (structure alone cannot back an
  outcome above `detect`, and cannot discharge a claim at any outcome) AND, independently, by C-T7
  (no `blind-diagnosis` evidence record backs an outcome above `detect`). `python3
  tools/check_core.py profiles/troubleshooting/examples/invalid.acceptance.toml` gives `FAIL …`
  with both `C-T6` and `C-T7` findings. A record citing a literal unregistered kind ("logging
  exists" as a `kind` string) fails one step earlier, at the core's own evidence-kind registry
  (`tools/fixtures/troubleshooting_cases.py` case `rt-kind-unknown`) — both failure modes are
  covered by the selftest, this file exercises the more instructive one.

The first REAL record (row 19), `examples/troubleshooting/validator.acceptance.toml` (not part of
this export), points its
`[spec]` at a real, small governing document for its subject —
`examples/troubleshooting/VALIDATOR-SPEC.md` (fault classes, required outcomes, scenario sources
for the acceptance validator itself) — rather than the profile's own synthetic `examples/SPEC.md`
(an invented document for the example pair above, never meant to govern a real subject, and the one
shipped here). That
document also carries a B19 spec inventory (`VALIDATOR-SPEC.inventory.toml`, generated by
`tools/spec_inventory.py`); the record's two claims cite the inventory's two item ids
(`validator-regression`, `malformed-record`) as their `clause`, so B19's coverage check (core.md)
applies to this record for the first time in this profile.

## Admissibility check (item 8b)

Checked by `tools/profiles/troubleshooting.py` (`profile_version 0.1.0`), composed the same way
`acceptance/conformance`'s own meaning check composes (`check_core.dispatch`, `protocol.md` §6.6
item 8). It verifies every rule this document states IN FORCE above (C-T1, C-T4, C-T5, C-T6, C-T7)
and every Required field (`fault_class`/`outcome`/`outcome_criterion`/`scenario_source` on every
claim; `diagnoser.{kind,id,digest}` plus `held_out` plus `blinding.{truth_hash,visible_evidence,
committed_at}` on every `blind-diagnosis` record; `diagnoser.isolation` plus the A0 cap for
`human`/`model-seat` diagnosers; the `[diagnostics]` table). It composes with the binding's own
check at the leaf — no `tool` binding exists yet (`bindings/tool.py` is unwritten), so
`acceptance/troubleshooting/tool` is `INDETERMINATE` (`B13: missing binding half tool`) under a
full validation, and `PASS-MEANING-ONLY` only when `--meaning-only` scopes the run to the meaning
half; the plain, unsuffixed `acceptance/troubleshooting` needs no binding and gives a real
(`PASS`/`FAIL`/`INDETERMINATE`) verdict from the meaning check alone — a leaf whose meaning-check or
binding-check is unavailable is never `PASS` outright (D1 amendment A1, the same fail-closed rule
`acceptance/conformance`'s admissibility check states). C-T2 (unknown completeness) and C-T3
(invalidation) are NOT IN FORCE — a claim citing `telemetry-completeness-check` evidence is
INDETERMINATE rather than silently trusted at the family ceiling (row 11); flagged as owed, not
silently dropped.

Fixtures: `tools/fixtures/troubleshooting_cases.py` (50 cases: one valid case plus one or more red
cases, with a specific error substring, per constraint/required field above), run via `python3
tools/profiles/troubleshooting.py --selftest`, which the shipped `gates/run_all.sh` invokes for
every profile in its `profiles/conformance profiles/troubleshooting …` selftest loop. A
mutation demonstration per checked rule (disable the guard, the named case(s) go red, restore exact
bytes), and a dedicated blind-diagnosis harness, exist in the upstream development repository, not
in this export: they are enforced there, not by anything shipped here.

## Open questions and dispositions

Open questions T1 through T5 are listed below. The checked vocabulary is implemented in this 0.1.0 revision
(this document plus `tools/profiles/troubleshooting.py` and the shipped
`tools/fixtures/troubleshooting_{cases,record}.py`; the mutation and blind-diagnosis harnesses are
upstream-only, not part of this export); deferred material is noted
above in "What this profile does NOT define."
