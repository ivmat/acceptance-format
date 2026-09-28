---
type: reference
digest: Leaf acceptance/verification/code/rust — the Rust binding of the verification meaning, projected onto the generic acceptance protocol. Moved here 2026-09-24; the language-neutral rows of its former §2/§3 lifted to ../PROFILE.md (R5).
---

# Leaf: `acceptance/verification/code/rust` (formerly "rust-code.md", DRAFT since 2026-09-16)

meaning id: `acceptance/verification` (the bare meaning; NOT what a package under this binding
declares — see the full leaf id below and §1's `[format].profile` row) ·
protocol projection name: **rust-code** · leaf id: `acceptance/verification/code/rust` · meaning:
`../PROFILE.md` · binding: `../../bindings/code/rust.md` (skeleton; the binding half below is not
yet lifted there — see the note at the end of §1).

**Moved 2026-09-24.** This document was `protocol_acceptance/spec/profiles/rust-code.md`; the
shipped protocol specification now points here. Nothing here was renamed a second time:
`profile_id`, section content and every rule are carried over unchanged except the R5 lift below.

**R5 lift (same pass).** The former §2's language-neutral evidence tokens (`unit-test`,
`property-test`, `fuzz`, `lean-theorem`, `human-review`, `llm-review`, `dep-audit`) and the former
§3's profile-floor MECHANISM (the grade/band/families "iff" rule — generic to any binding of this
meaning, not Rust-specific) now live in `../PROFILE.md`, as that document's own text. This leaf
keeps only what is specific to the Rust binding: the Rust-only evidence tokens (`kani-harness`,
`miri`, `flux-refinement`, `lint`, `semver-check`), the requirement patterns, the mutation-control
discipline, and everything in §1.

This document is the first projection of the generic core (`protocol_acceptance/spec/protocol.md`,
§6.6). It supplies vocabulary and bindings only; it adds no document, state, verdict, disposition
or rule. Every field named here is either a field the format already defines for the verification
meaning or a binding of a core slot to Rust tooling.

## 1. What this profile binds

| core slot (§6.6) | this profile's binding |
|---|---|
| `[subject].kind` | `rust-crate` \| `rust-workspace` |
| subject identity | `[subject].commit` (40-hex git sha); `dirty` must be false for a package a decision may accept |
| `captured_at_revision` alias | `captured_at_commit` on evidence records (already used by the format's examples) |
| package profile | `[format].profile = "acceptance/verification/code/rust"` (the full leaf id; REQUIRED at 0.3.0, no compatibility default — B12) |
| `method`/`kind` ⇒ `epistemic_tier` CEILING | `../PROFILE.md`'s generic default table for the seven language-neutral tokens; §2 below for this binding's five additional Rust-only tokens |
| profile floor table | `[requirement.evidence.profile."acceptance/verification/code/rust"]` — the tool matches this key against the package's own declared `[format].profile` string EXACTLY (`acceptance_protocol.py`'s floor check refuses a floor declared under any other spelling, fail-closed), so a contract's floor table for this binding MUST use the identical leaf-id spelling, never the bare `acceptance/verification` meaning id; the floor MECHANISM itself is `../PROFILE.md`'s (R5 lift) — this binding contributes no floor rows of its own |
| cross-cutting `demands.fields` | `bounds` (leading token `bounded` \| `unbounded`); `semantics` (exact string) |
| recipe carriers | `cargo test …`, `cargo clippy -- -D warnings`, `cargo doc --no-deps`, `cargo kani --harness …`, `cargo miri test`, `grep -rn … src/` with a `positive_control` — any command whose `expect` string is checkable on the named stream |
| change-impact declared input set (§8) | `src/**`, `tests/**`, `benches/**`, `Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml`, `build.rs`, plus the record's `tool` and `semantics` strings; a `kani-harness` record also declares the harness source file |
| `constraints` typing | free strings; RECOMMENDED forms: `license: <SPDX expr>`, `msrv: <version>`, `no_std: true`, `deps: none|allowlist <file>`, `unsafe: forbid` |
| typed toolchain/build-input identity (core.md B20/B21) | §1a below |

This §1 table is still the binding half written inside the meaning's leaf, as it always has been
(`../../bindings/code/rust.md` is a skeleton — the lift into it is a later move, not this pass's;
see that document's own TODOs). Only the R5-lifted rows above changed pointer.

## 1a. Typed identity for code/rust evidence (core.md B20/B21)

core.md B20 lets an evidence record carry a typed `toolchain` list and a typed `build_inputs`
list; B21 lets it carry `coverage` and `tool_qualification`. All four are class-generic shapes
(B20/B21 name no language or tool); this section states what code/rust evidence SHOULD carry, and
at which `baseline` assurance-class level (`protocol_acceptance/spec/assurance-classes.toml`,
read-only here — this leaf states no new floor, only which of the class's own floors a code/rust
producer will hit first).

- **`toolchain`** SHOULD name the prover or test runner that produced the record: one entry per
  tool component actually named in the record's free-text `tool` string (e.g. `kani`, `rustc`,
  `lean4`, `aeneas`, `cargo-mutants`), each with `name` and at least one of `commit`/`digest`.
  Trap 5a.4 below still applies: when a tool reports only a semantic version and no build commit,
  write the typed entry with a `digest` instead — a deterministic content digest over the
  installed tool's own bytes (a bundle-manifest digest, or the launcher binary's own bytes) is
  usually obtainable even when a commit is not, and the adoption guide's template records exactly
  this for `kani-bundle`/`cargo-kani-launcher`. Only when NEITHER a commit NOR an honestly
  computable digest is obtainable does the typed entry go unwritten, with identity staying
  disclosed in the free-text `tool` string alone — B20 never requires a `tool`-string component to
  have a typed counterpart, and this leaf never invents a commit or a digest to manufacture one.
- **`build_inputs`** SHOULD carry `Cargo.lock` and `rust-toolchain.toml` — already declared
  `required_build_inputs` by `../../bindings/code/rust.md`'s machine-readable block, and enforced
  by `bindings/code_rust.py` under B20's opt-in-complete guard: once a **weighted** claim's
  evidence declares any `build_inputs` entry at all, the union of declared paths on that claim
  MUST include both files. An unweighted claim, or a weighted claim declaring no `build_inputs` at
  all, is unaffected.
- **`coverage`** SHOULD carry a B21 registry metric where the tool reports one: `statement` /
  `branch` / `decision` for a `cargo llvm-cov` or `grcov` run backing a `unit-test`/`property-test`
  record, `mcdc` where the toolchain reports it, `proof-obligation` for a `kani-harness` or
  `lean-theorem` record reporting a discharged-obligation count. A tool that reports nothing
  countable (a bare pass/fail, e.g. `lint`, `semver-check`, `dep-audit`) carries no `coverage`
  field — B21 never asks a record to fabricate a number the tool did not produce.
- **`tool_qualification`** SHOULD carry a `basis` (and `level`, where one exists) for a record
  relied on by a `firm` requirement approaching the class table's top levels — see below.

**When the class table makes one of these MANDATORY, not merely SHOULD** (`baseline` scheme,
`protocol_acceptance/spec/assurance-classes.toml`, read-only):

| class field | becomes required at | code/rust reading |
|---|---|---|
| `build_inputs_required` | `baseline/4` only (levels 0–3: `false`) | a `firm` requirement's relied-on weighted evidence must carry `build_inputs` naming at least `Cargo.lock` and `rust-toolchain.toml` — exactly the pair this binding already names |
| `tool_qualification_required` | `baseline/4` only | the prover/test runner's `tool_qualification.basis` must be declared on the relied-on evidence — for `kani-harness`/`lean-theorem` this is the honest place to disclose (or admit the absence of) a qualification argument for Kani/Lean+Aeneas |
| `coverage_min` | `baseline/3` (`{metric = "decision", value = 0.8}`) and `baseline/4` (`{metric = "mcdc", value = 1.0}`); absent below level 3 | a `unit-test`/`property-test` record relied on at level 3+ needs a real `decision`-or-stronger coverage number, not an invented one — a suite that cannot show it is a declared gap against the class floor, not a silently-omitted field |

`toolchain` itself has no dedicated `*_required` field in the class table at 0.3 (the table gates
`tool_qualification_required`, not toolchain identity, at level 4); this leaf's SHOULD above is a
recommendation from B20's own WHY (identity checkable at the same granularity B1 already asks of
the certified subject), not a class-table MUST — stated here so a producer aiming at level 4 does
not discover the tool_qualification expectation without also seeing its natural companion.

## 2. `method`/`kind` ⇒ `epistemic_tier` ceiling — this binding's Rust-only tokens

**R5 lift:** the seven language-neutral tokens this profile
admits (`unit-test`, `property-test`, `fuzz`, `lean-theorem`, `human-review`, `llm-review`,
`dep-audit`) and the `T1`..`T5` tier definitions themselves moved to `../PROFILE.md`'s own default
table — nothing about them was Rust-specific, so nothing about them stayed here. This binding adds
five tokens no other binding of this meaning has reason to admit:

| `epistemic_tier` (`../PROFILE.md` ladder) | this binding's additional tokens |
|---|---|
| `T2` | `kani-harness`, `flux-refinement` |
| `T3` | `miri` |
| `T4` | `lint`, `semver-check` |

Every ceiling here is unchanged from before the lift — only its citation moved: `T2` = "mechanically
sound semantic decision over the record's declared model and domain," `T3` = "empirical-sampled,"
`T4` = "mechanical-syntactic," all defined once, in `../PROFILE.md`. A record that declares
`epistemic_tier` is held to this ceiling (a stronger declared tier is an error, a weaker one is
honest). A record that declares neither `epistemic_tier` nor a token in this table or
`../PROFILE.md`'s is indeterminate and meets no floor.

## 3. The profile floor — lifted to `../PROFILE.md`

**R5 lift:** the floor mechanism (`[requirement.evidence.profile."acceptance/verification"]`,
`min_grade`/`min_band`/`families`/`kinds`, the "iff" rule, and why the grade ordering lives at the
profile rather than the format) is generic to every binding of this meaning and now lives at
`../PROFILE.md` §"The profile floor," unchanged in substance. This binding contributes no floor
row of its own; §4 below shows the mechanism populated with this binding's own families
(`dynamic`, `bmc`, `kernel`, `mechanical`, `judgment` — the same five tokens every binding of this
meaning reads off the shared family registry) for Rust requirement patterns.

## 4. Requirement patterns for a Rust delivery (with their floors)

| pattern | domain | typical core floor | typical profile floor | satisfied by |
|---|---|---|---|---|
| a functional rule ("rejects X", "computes Y per standard Z") | correctness | T3, weighted, control, recipe, delivered-revision | test-only / A1 / dynamic | `unit-test` + `property-test` records with a mutation control (`cargo test` on a mutant goes red) |
| a bounded proof of a rule | correctness | T2, weighted, control, recipe | probe or contract / A3 / bmc | `kani-harness` with declared `bounds`, mutation control |
| an unbounded proof | correctness | T1 | contract / A4 / kernel | `lean-theorem` (Aeneas extraction), theorem-mutation control |
| never panics / no UB on any input | safety | T2 or T3, recipe | probe / A1 / bmc or dynamic | `kani-harness` panic-freedom (A1 needs no control for freedom claims), `miri`, fuzz loop |
| no `unsafe` | security | T4, weighted, control, recipe | mechanical / A1 / mechanical | `lint` record for `#![forbid(unsafe_code)]` + clippy; watched_fail = add an `unsafe {}` block, observe red |
| API compatibility with the previous release | compatibility | T4 | mechanical / A1 / mechanical | `semver-check` with `baseline` |
| no known advisories at delivery | security | T4 | mechanical / A0 / mechanical | `dep-audit` with `db_version` (decays; the contract's `stale_after` should be short) |
| docs build clean | documentation | T4, recipe | mechanical / A0 / mechanical | `lint`-kind record for `cargo doc` |
| "all verification is unbounded" (cross-cutting) | correctness | `demands.fields.bounds = "unbounded"` over the proof requirements | — | every covering claim's `bounds` leading token; a bounded suite makes this `partial` → deviation → waiver + condition |

## 5. Mutation controls in Rust (the observed-red witness the core floor asks for)

`control_required = true` is met by a `[claim.evidence.control]` block with `kind = "mutation"`,
`expectation = "red"`, `observed = "red"`, `of_claim = <this claim>` on a record whose `family`
is the carrier the band gate accepts (`dynamic` for A1, `bmc` for A3, `kernel` for A4 —
`assurance-bands.md` rule 6), or by `self_verify.watched_fail` (`of_command` = the recipe
verbatim, `perturbed`, `observed`, `date`). The cheapest honest Rust form: apply a source patch
to the implementation (change a modulus, drop a check), re-run the same `cargo test --test …`,
require red, restore the file byte-exactly (hash before and after), record the transcript. A
falsifier that fails to compile is **not** observed red (the oracle never ran against it).

### 5a. Four traps the worked instance hit (name them, do not rediscover them)

1. **Decouple the harness bound from the real capacity.** When the strongest tool cannot reach the
   crate's real bound in a human-scale time-box, give the harness its own `KANI_BOUND` (here 20
   bytes against a real 34), declare it in `bounds`, and let the cross-cutting "unbounded"
   requirement compute `partial` with a `[[deviation]]` — that is the honest row, not a failure.
2. **The weight witness is not the band control.** A freedom claim (panic/UB) reaches A1 with no
   control, yet a weighted claim still needs a watched-fail witness (`0.1-DRAFT.md` §4.1). The
   witness may be a *different, fast* command that goes red against the same claim (a buffer-shrink
   mutant under `cargo test`), recorded as an observed-red control on one of the claim's own
   records; a second seven-minute Kani run buys no proof strength.
3. **`grep` absence checks collide with the mechanism proving the absence.** `grep -rn unsafe src/`
   matches `#![forbid(unsafe_code)]` itself. For "no unsafe" use a `lint` record for the `forbid`
   attribute plus clippy, and a watched_fail that inserts a real `unsafe {}` block and observes the
   compile error.
4. **Tool identity at commit granularity may be unobtainable.** A plain `cargo-kani` install
   reports a version only; write `kani@<version> (commit unknown — <why>)` rather than inventing a
   sha, and treat it as a weak identity when setting floors.

## 6. Consumer re-execution (`verification.mode = re-execute-all`)

The consumer runs each basis claim's `self_verify.command` in its own checkout at the package's
`[subject].commit`, with the toolchain the record's `tool` names, and records the real output
tail. For a Rust delivery this is a clean clone + `rustup` pin + the commands above; independence
`author-not-producer` is met by evidence whose `author` is a lab or a second lineage (the
cross-version test discipline: lineage-B tests against lineage-A code).

## 7. Worked instance

`protocol_acceptance/examples/rust-delivery/` — a real crate (`iban-check`), a consumer contract with six
requirements (five mandatory, one cross-cutting and waivable), a generated package whose evidence
transcripts come from actually running `cargo test`, `cargo clippy`, `cargo doc`, `cargo kani` and
five mutation controls, a consumer decision that re-executes the recipes and lands
`accepted-with-conditions` (the unbounded requirement waived with a dated condition), and a
change-impact run that turns an edit to the checksum module into re-verification obligations.

## 8. Second instance (prose): verify-rust-std bounties

An external Rust verification exchange maps the same projection onto challenge success criteria =
contract (`[[requirement]]` rows per
function, `kind = "cross-cutting"` rows for "unbounded" and "generic T"), a generated package
from the submission = package, two committee approvals = decision
with `authority = "committee, 2 of N"`. (An earlier, retired example package for this mapping is
not part of this export; the projection above is illustrative, not a shipped fixture.)

## 9. Phases in a Rust delivery (protocol.md §3.5)

| phase | typical floor | what the producer ships | what the consumer does |
|---|---|---|---|
| `exploratory` | `min_tier = "T5"`, unweighted, no recipe — "it builds, it runs the demo, I looked at it" | a crate that compiles, a demo binary, `human-review`/`llm-review` records, `inspection-argued` claims | tries it; records `[[requirement_feedback]]` (what was ambiguous, wrong, missing); supersedes the contract |
| `crystallizing` | `T3` tests with recipes for `firm` requirements; `T5` still allowed on `draft` ones | `unit-test`/`property-test` records, recipes, first controls | re-runs the firm rows; tightens floors; marks rows firm |
| `final` | `T3`+controls for functional rows, `T2` (kani) for safety rows, `T4` lint/semver/doc, cross-cutting `bounds` demands | the full package, mutation controls, declared inputs | full re-execution; definitive decision; conditions → obligations |

The example in `examples/rust-delivery/` is a `final`-phase contract; an exploratory predecessor
would carry the same six ids with judgment-tier floors and `phase = "exploratory"`, and
`check-contract --previous` would prove the chain only tightened.
