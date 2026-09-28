---
type: reference
digest: Evidence-type registry + admissibility rules (v0) (frontmatter added 2026-09-22 for the protocol gate)
---

# Evidence-type registry + admissibility rules (v0)

Open taxonomy: any gate species can be evidence, **if** its record carries the fields that make it
attributable and reproducible. A record missing a required field is an assertion, not evidence —
the validator errors. Adding a kind = adding a row here + a registry entry in the validator, in
the same commit.

Universal required fields (every kind): `kind`, `family`, `ref`, `result`, `tool`, `record`.
`bounds` and `semantics` are required where marked below — absence there is not "unbounded/default",
it is inadmissible, because unstated scope is how a bounded check gets read as a proof.

| kind | family | extra required | what it can evidence | notes |
|---|---|---|---|---|
| `kani-harness` | bmc | `bounds`, `semantics` | A1–A3, bounded | tool at commit granularity; `unsupported` result ⇒ claim should be `parked`, not `gap` |
| `lean-theorem` | kernel | `axioms` (list; `[]` is the strong claim), `semantics` = lean/mathlib pins | A4, unbounded | kernel-checked; axioms declared, never implied |
| `flux-refinement` | smt-refinement | `bounds` = "unbounded-smt", `semantics` | A2–A3.5 invariants | CANDIDATE — tool not adopted (parked note in reserved methods); kind reserved |
| `unit-test` | dynamic | `cases` (count) | point claims; rejection/acceptance behavior at named inputs | a test's non-vacuity witness is that it RUNS the item — `record` must show execution |
| `property-test` | dynamic | `cases`, `generator` | sampled set claims | shrunk counterexamples land in `record` on fail |
| `fuzz` | dynamic | `corpus_size`, `duration` | absence-of-crash on sampled inputs | coverage data in `record` when available |
| `miri` | dynamic | `semantics` (flags) | UB-freedom on executed paths | executed-paths-only is the boundedness; say so in `bounds` |
| `lint` | mechanical | — | mechanical hygiene claims (no-unsafe, clippy class) | small, cheap, still admissible |
| `semver-check` | mechanical | `baseline` (prior version) | API-compatibility claims | cargo-semver-checks or equivalent |
| `dep-audit` | mechanical | `db_version` | advisory-freedom at a date | claim decays with time; date lives in `record` |
| `human-review` | judgment | `reviewer` | anything, weakly | **declared-null likelihood by convention** — gates flow, adds no computed trust; never the sole evidence for band ≥ A1 |
| `llm-review` | judgment | `reviewer` (model id) | anything, weakly | same convention as human-review |

There is no dedicated CONTROL *kind* — see "Control block" below: any of the kinds above may carry
one as an optional sub-table.

## Family semantics (why `family` is required)

`family` is the correlation key for the future trust-ledger layer: same-family evidence shares
blind spots and must not be double-counted; cross-family evidence (bmc × kernel × dynamic) is
where real assurance accumulates. v0 records the key and computes nothing (format.md rule 3) —
but recording it now is what makes the records upgradeable without re-running anything.

Proofs quantify over sets; tests over points. Both declare their scope the same way — `bounds`
for proofs (unwind limits / "unbounded"), `cases`/`corpus_size` for dynamic kinds. A manifest
reader must always be able to answer: *checked over what input space?*

## The `judgment` family rule

Judgment verdicts (human or LLM) are admissible — most deliveries will carry them — but
they are permanently declared-null for trust until a measured calibration exists (the failed
provable-trust-method calibration attempts are the precedent for not pretending). The validator
enforces: a claim whose only evidence is `judgment`-family cannot assert band above A0.

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
  mirrors the engine's receipt 2.1.0 control block `{kind, expectation, observed, of_claim}` (plus
  the receipt's own `checker.kind`/`toolchain` supplying the family), so the format and the engine
  share one control definition and an emitter is a 1:1 map, not a re-derivation.
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
- **Per-band `control.kind` whitelist** (tightened 2026-08-22, mirrors the engine's audit —
  `kind == "mutation"` for its own controls-check): A3/A4 and functional A1 require
  `kind == "mutation"`; A2 accepts `kind ∈ {"mutation", "ablation"}`. **`kind == "planted-twin"`
  never satisfies a band-lift, at any band** — it proves the pipeline can reject at all (a
  satisfiability/pipeline signal, the engine's separate acknowledgment-witness role), not that THIS
  claim's own oracle catches a mutation of THIS impl/theorem. A planted-twin record may still be
  present in a manifest as disclosure/satisfiability evidence — it just never counts toward the
  gate (assurance-bands.md rule 6).
- **`of_claim` must resolve.** A `control.of_claim` naming a claim id that does not exist anywhere
  in the manifest is an error — a control pointing at a phantom claim (assurance-bands.md rule 8).
