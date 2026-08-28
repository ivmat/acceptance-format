# Assurance bands (v1, control-gated): floors on evidence type, gated by control discipline

A band is the *minimum evidence species* backing a claim, capped by whether that claim's oracle was
ever watched to fail on purpose — SPARK-ladder-shaped, instantiated for this format's toolbox. It is
deliberately NOT a trust score: two A3 claims with different harness diversity, or different
mutation-kill counts, are not equally trustworthy, and v1 refuses to pretend otherwise (the ledger
layer, when calibrated, will compute that difference from the same records).

**Assurance = evidence species × control discipline.** A check nobody watched fail is untested — a
Kani harness or Lean proof whose oracle nobody perturbed reads identically, at the species level, to
one a mutation control proved catches bugs. Species alone cannot tell those apart, so from v1 the
higher bands require both: the evidence *species* sets the ceiling a claim could reach, and an
*observed-red control* is what actually earns the climb. (A prior, species-only version of this
table lived at this same path before 2026-08-22; this control-gated version supersedes it.)

| band | claim character | species ceiling | control REQUIRED to reach it? |
|---|---|---|---|
| A0 | ran / asserted / judgment | any admissible record, incl. judgment | no — A0 IS "uncontrolled or unwitnessed" |
| A1 | non-vacuous but not state-exhaustive | controlled dynamic (test + control); mechanical hygiene; panic/UB-freedom | **yes for oracle-bearing dynamic** (`kind == "mutation"` only); no for no-oracle hygiene/freedom (see rule 6) |
| A2 | memory safety on the unsafe surface | `kani-harness`/`miri` on unsafe + control | **yes** (`kind ∈ {mutation, ablation}` on the unsafe surface) |
| A3 | bounded functional contract | `kani-harness` proving a functional contract — via `-Z function-contracts` machinery OR assertion-style property harnesses — bounds declared, + a red mutation control | **yes** (`kind == "mutation"` — observed-red mutation of the impl) |
| A4 | foundational functional correctness (unbounded) | `lean-theorem`, axioms declared, + control | **yes** (`kind == "mutation"` — mutated theorem the kernel rejects) |
| A3.5 | refinement-shaped invariants | `flux-refinement` | RESERVED — tool not adopted; control gate not enforced while parked |

**The gate, one sentence:** an **oracle-bearing** claim (A2/A3/A4, and functional A1) cannot exceed
A0 without an observed-red control whose `of_claim` names it.

Validator-enforced rules:

1. `band` ∈ {A0, A1, A2, A3, A3.5, A4}. A3.5 is accepted by the parser but flagged (reserved — its
   tool is a parked candidate, not adopted; the control gate below does not apply to A3.5 while it
   remains unadopted).
2. A claim's band must be *reachable by species* per the table above AND, for **oracle-bearing**
   claims, carrying an **observed-red control** whose `of_claim` names the claim; else the claim is
   capped at A0 (an A4 claim with only bmc evidence, or an A3 claim with the right species but no
   matching control, is a band overstatement — the exact failure mode the format exists to prevent).
3. Judgment-family-only evidence caps the band at A0 (evidence-types.md). Judgment has no mechanical
   oracle to mutate, so it never reaches a control-gated band regardless of the "control REQUIRED"
   column — this cap is unconditional and unaffected by control discipline.
4. Dynamic-family evidence: a functional (oracle-bearing) claim resting on dynamic evidence alone is
   **A0 UNLESS** it carries a matching observed-red `control` block (evidence-types.md — a mutation
   run over the test suite, e.g. cargo-mutants/stryker), in which case it reaches **A1** — never A2+,
   because tests witness points, not sets, so a control does not lift a dynamic-only claim past A1.
   No-oracle dynamic claims (`miri` UB-freedom, `fuzz`
   absence-of-crash) reach A1 without a control (rule 6 exception — there is no postcondition oracle
   to mutate). This cap outranks the per-band table above: `miri` counts toward A2 only alongside at
   least one non-dynamic record (the table names the kinds that can reach a band; this rule bounds
   what a single family may claim alone — cross-family corroboration is where assurance accumulates,
   evidence-types.md).
5. `status = "partial"` means: admissible evidence exists but does not reach the asserted band — the
   record shows both the ambition and the shortfall honestly. A claim whose species evidence would
   reach a band but lacks the control that band now requires is exactly this case: mark it `partial`
   (or drop the band to A0), never assert the ungated band.
6. **Control discipline (binary floor), family-agnostic.** See also the F4 contradiction guard
   (`evidence-types.md`, "Control block" section): `control.kind = "mutation"` AND
   `control.observed = "red"` implies the carrier record's own `result != "pass"` — additive to
   this rule, never a replacement for it. A control is a `control = {kind,
   expectation, observed, of_claim}` block any evidence record MAY carry (evidence-types.md) — it
   is NOT a fixed-family evidence kind: the record's own `family` states what was perturbed
   (`kernel` = mutated Lean theorem, `bmc` = mutated Kani harness, `dynamic` = cargo-mutants/stryker
   over a test suite, `mechanical` = seeded-bad gate fixture); the control's `kind`
   (mutation/ablation/planted-twin) is orthogonal to that family. A control **passes** (behaved as
   predicted) iff `observed == expectation` — but passing and **band-lifting are not the same
   thing** (tightened 2026-08-22, F1): a `green`/`green` or `sat`/`sat` control also has
   `observed == expectation`, and is recordable exactly like a red one, but it does NOT lift a
   band — only a **literal `red`** (`expectation == "red"` AND `observed == "red"`) does, because
   only a red result witnesses the oracle catching a planted bug. Control validity is independent
   of the record's own `result` field (a rejected mutated Lean theorem legitimately has
   `result = "fail"`; that IS the observed-red). A mutation
   tool's tally (`mutants_total`/`mutants_caught`, evidence-types.md, optional data fields) is
   recorded as data and as GAPS: surviving mutants are recorded, never subtracted into a numeric
   band, and no `alpha`/`beta`/`lr` field rides along (format.md rule 3 / F4 intact). **A control
   attests only the claim its `of_claim` names, nothing more:** a gate-level fixture that proves a
   gate fires controls that gate's own claim, NOT every behavioural claim the gate nominally covers.
   One fixture does not lift a module of claims — a control block whose `of_claim` names a different
   claim than the one it is recorded under does not satisfy that claim's control gate (band
   overstatement by proxy, same failure mode as rule 2).

   **Per-band control-kind whitelist:**
   - A3/A4, and functional (oracle-bearing) A1: the band-lifting control's `kind` MUST be
     `"mutation"` — mutate the impl/theorem, the oracle catches it.
   - A2 (memory safety / unsafe surface): `kind` ∈ {`"mutation"`, `"ablation"`} — ablation removes
     a precondition/hypothesis and the property must break.
   - `kind == "planted-twin"` **NEVER** satisfies a band-lift gate, at any band. A planted-twin
     proves the pipeline can reject at all (a satisfiability/pipeline signal) — not that THIS
     claim's own oracle catches a mutation of THIS impl/theorem. That is a separate
     acknowledgment-witness role, not a band-lift. A planted-twin record may still be present in a
     manifest as disclosure/satisfiability evidence; it simply never counts toward this gate.

   **Carrier-family compatibility (tightened 2026-08-22, F2):** family-agnostic does not mean
   family-blind. A band-lifting control's **CARRIER record** — the evidence record the `control`
   block sits on — must itself be species-compatible with the band being lifted, or it does not
   count: A4 needs a `kernel`-family carrier, A3 needs `bmc`, A2 needs `bmc` or `dynamic`,
   oracle-bearing A1 needs `dynamic`. `judgment` is compatible with **none** of these — a
   `human-review` record carrying `control = {kind="mutation", expectation="red",
   observed="red", of_claim=...}` must NOT satisfy an A3/A4 gate; that would let a review stand
   in for a mechanical control and defeat the entire point of this gate.
7. **Coverage is not control.** `llvm-cov`/`vitest --coverage`-class evidence shows an item was
   *executed* (necessity), not that the oracle *catches a wrong answer* (sufficiency). Coverage
   corroborates an A0/A1 record; it never lifts a band and is never itself an admissible control.
8. **`of_claim` must resolve.** A `control.of_claim` naming a claim id that does not exist
   *anywhere* in the manifest is an error — a control pointing at a phantom claim. This is
   independent of, and in addition to, rule 6's "does not name THIS claim" mismatch: that one
   fires when `of_claim` names a claim id that DOES exist elsewhere in the file; this one fires
   when `of_claim` names nothing at all.

Bands say what a reader may assume WITHOUT re-running anything. The re-run path (tool pins in
every record) is the stronger option and always available — internal consumers should prefer it
wherever a wrong claim would break something downstream.

See `evidence-types.md` for the family-agnostic `control` block (`{kind, expectation, observed,
of_claim}`) this gate is built on — kernel/bmc/dynamic/mechanical alike.
