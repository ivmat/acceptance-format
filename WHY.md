# Why this format exists

*Role: motivation/context — indexed from README §1 and §3.*

This page distinguishes this format from related formats.

## The problem

Verification claims often appear as prose or badges: "formally verified", "proofs cover the parser",
or a green check. Deciding whether a specific rule was verified requires the input domain, oracle,
and deciding mechanism. This format records those details and uncovered rules per row. A claim
carries weight only when it names a command whose failure would falsify it; otherwise, the validator
refuses weight. Without these fields, readers must distinguish supported and unconsidered rules
themselves.

## vs SARIF

**SARIF carries tool findings. An envelope carries claims and can cite SARIF output as evidence.**

SARIF is a results-interchange format. A run contains results that point to rules and locations;
`result.level` separates error, warning, and note; `result.kind` supports `pass` and `fail`; results
map to taxonomies such as CWE; and the run can record its invocation.

SARIF's unit is a tool finding. This format's unit is a claim about a specification rule, including
one no tool examined. Absence of a SARIF result does not express that row. SARIF also lacks a
required evidence-strength axis, per-claim self-verify recipe, and tier for unsupported claims.
Property bags can carry these fields, but SARIF's core semantics neither require nor grade them.
A local property-bag convention therefore lacks the same enforcement. Severity and evidence
strength are separate: a symbolic proof and fixture test can have the same `level`. The formats
compose: a `mechanical`-grade row can run a linter with `self_verify` and name its required SARIF
output with `expect`.

## vs code coverage

**Coverage records where tests executed, not what they checked.**

Line, branch, and MC/DC coverage measure executed code. They do not assess the oracle or whether a
wrong answer would be detected. Assertion-free tests can reach one hundred percent coverage.

A ledger instead declares an axis for **coverage of what**, and a grade and recipe for **decided by
what**. The axis may enumerate every encoding rule in the standard rather than every module in the
crate. A `test-only` row records concrete points, while a `probe` records bounded, monomorphic, or
fixture-shaped evidence that does not decide the item. The declared axis and denominator are not
checked against the real specification; see [`ASSUMPTIONS.md`](ASSUMPTIONS.md).

## vs test badges and a green CI pipeline

**A green pipeline summarizes a script. This format requires a checkable recipe per claim.**

A pipeline provides one bit for a repository. Its meaning depends on the current script, and it
cannot show which concerns it covers. In the case study, the subject's `check.sh` printed `PASS`
whether the proof stage ran or exited 0 because its toolchain was absent.

Per-claim recipes also separate document validity from software quality. A validator `ERROR` means
the **document** claimed unsupported weight. A well-verified library with a malformed envelope can
produce errors; a barely tested one can produce none. The result is not a quality score.

## vs proof certificates and formal-verification reports

**A proof decides a theorem. This ledger maps proofs to surface claims and records the remaining
assertions.**

A model-checker summary, SPARK report, or kernel-checked development establishes specific theorems
and is stronger evidence than this format produces. This format maps those theorems to the
consumer's claim surface and states the denominator. Proof totals do not identify unaddressed
consumer-facing rules.

The DER decoder in [`CASE-STUDY.md`](docs/CASE-STUDY.md) had 203 green proof harnesses, unbounded Lean
proofs over several core functions, and a green full-gate receipt. Its ledger still found two harnesses
proving a duplicated implementation that never entered shipped code, and three panic-freedom proofs
whose buffers were too small to contain a well-formed object. Both appeared under the same green
check as the strongest rows, and neither result was false. The pipeline omitted evidence shape,
which consumers need.

The refusal mechanism has an ancestor in a narrower domain: SV-COMP counts a verifier's answer as
correct only after an independent validator validates its witness. An unconfirmed answer remains in
the results table but receives no credit.

## vs assurance cases: CAE, GSN, SACM, Assurance 2.0

**Assurance cases are a closely related family. They check argument structure and evidence presence; this
format checks evidence-producing machinery and withholds weight when it is absent.**

An assurance case is a structured argument from evidence to a top-level claim. ISO/IEC 15026-2 sets
the minimum structure, GSN is the dominant notation, OMG's SACM is the interchange metamodel, and
Assurance 2.0 (Bloomfield and Rushby) is the modern rigorous treatment. Per-claim epistemic tiers
predate this work: SACM's `AssertionDeclaration` values (`asserted`, `needsSupport`, `assumed`,
`axiomatic`, `defeated`, `asCited`) closely match `weight`. We intend to declare the mapping.

Assurance 2.0 grades the (item, evidence) *pair* by separating an *evidentially measured* claim ("the
tests achieve MC/DC coverage") from the *evidentially useful* claim above it ("there is no
unreachable code"). We reached the same rule independently through review of a mis-graded row;
Assurance 2.0 has priority.

Automated assurance-case checking operates on logical structure and treats evidence presence, not
merit, as validity. Quantified confidence propagates subjective probability compositionally, which
this format refuses. Assurance cases do not withhold claim status for lack of a runnable recipe,
declared bounds, or a control showing that the check can fail. They also provide capabilities this
format lacks: defeaters and eliminative argumentation for recording *reasons to doubt*, argument
structure rather than a flat row list, and decades of certification experience. Assurance cases
model arguments; this format enumerates claims, including uncovered claims.

## vs CycloneDX Attestations (CDXA / ECMA-424)

**CycloneDX Attestations are similar in document shape. They use asserted confidence where this
format uses refused weight.**

CycloneDX 1.6, standardized as ECMA-424, has a `declarations` object with assessors and attestations.
Attestations map a `requirement` to `claims[]` and `counterClaims[]` with `conformance.score` and
`confidence.score` in 0–1. Claims carry `target`, `predicate`, `reasoning`, `evidence[]`, and
`counterEvidence[]`. This resembles this format's table within the SBOM ecosystem, with per-object
signatures and links to versioned standards that this format lacks.

An evidence description is prose about the evidence and its creation, not a command with expected
output. There is no positive control, bounds, clause-source discipline, declared axis, or obligation
to record uncovered rows. Within `declarations`, only a signature and an
external-reference/organization pair are required. A free-text `predicate` therefore validates, and
an assessor may assign `confidence: 0.95`. This format refuses weight instead of using 0–1 trust
arithmetic.

CDXA's `counterEvidence` addresses a gap in this format: no field records a reason to doubt a row,
which assurance cases represent with defeaters. Adoption remains a growth proposal against the spec
and has not occurred.

## vs VEX (OpenVEX, CSAF)

**VEX provides machine-readable status and a closed set of reasons but does not check them.**

VEX states whether a product is `not_affected`, `affected`, `fixed`, or `under_investigation` by a
known vulnerability. For `not_affected`, its closed vocabulary is `component_not_present`,
`vulnerable_code_not_present`, `vulnerable_code_not_in_execute_path`,
`vulnerable_code_cannot_be_controlled_by_adversary`, and `inline_mitigations_already_exist`. It does
that job at scale; this format does not replace it.

VEX does not require machine verification of a justification, and the status guidance says some are
difficult to prove conclusively. Reachability analysis and human judgment produce statements of the
same form. A bare VEX justification is unweighted unless it is paired with a deciding recipe, because
it names no command that could show it false. A closed vocabulary is useful but does not supply
evidence machinery. Unweighted status does not call the justification wrong; this format cannot
decide it.

## vs supply-chain attestation: SBOM, SLSA, SCITT, in-toto

**Supply-chain attestation establishes provenance and signer. This format records what would falsify
a claim. The layers can be combined.**

An SBOM enumerates components. Build provenance and signed attestations establish that an artifact
came from given sources and a given build without intermediate tampering. In SCITT (RFC 9943), an
issuer signs an artifact statement, a transparency service applies a registration policy and adds
it to an append-only log, and a receipt travels with it. in-toto's signed statement-and-predicate
envelope has the same role. None checks artifact behavior.

The SCITT RFC separates registration from endorsement: issuers can make false statements, and
registration proves only which issuer produced one. The standard therefore provides admission
without vouching. Refusal concerns syntax and identity, including signatures, required headers, and
issuer trust anchors, rather than whether claim content is checkable.

The records differ: attestation identifies the artifact and signer; the envelope identifies the
commit, tree state, toolchain, gate receipt, and freshness condition; the ledger records what was
decided. Layering supplies the signing and multi-party trust model absent from this format, as noted
in [`ASSUMPTIONS.md`](ASSUMPTIONS.md), without changing row semantics.

## vs cargo-vet (and cargo-crev)

**cargo-vet provides reviewed human judgment with provenance, corresponding to the unweighted tier.
It does not require per-claim falsifiers.**

cargo-vet records audits of crate version deltas against criteria such as `safe-to-run`,
`safe-to-deploy`, and custom sets such as an undefined-behavior risk ladder. It imports third-party
audit sets non-transitively through an explicit criteria map and lists unaudited dependencies in
`exemptions`. This audited-versus-exempted split is a deployed analogue of the two tiers
in this format's target ecosystem.

An audit is reviewed human judgment with provenance, equivalent to an admitted row. cargo-vet's
criteria are ecosystem trust policies ("is this safe to deploy?"), not per-claim falsifiability.
They require no deciding recipe, bounds, observed-failure witness, or declared specification axis. A
crate enters `exemptions` because nobody audited it, not because a validator refused weight, though
an exemption resembles a not-covered row. cargo-crev is further away: its documentation permits a
review without an actual code review.

A vet audit can support an unweighted row. cargo-vet supplies cross-organization audit import with
criteria translation, and crev supplies signed distributed proofs; this format supplies neither.
The unweighted tier retains these audits without presenting human judgment as mechanically decided.

## What this format does not replace

**Its scope is the record of what was verified.**

It discharges no proof, runs no test, and judges no oracle. A harness verifying the wrong property
passes like one verifying the right property. Grades are human judgments and can drift. The format
places each judgment beside a runnable command for spot-checking. See
[`ASSUMPTIONS.md`](ASSUMPTIONS.md) before relying on a ledger.

## README prose does not enforce these rules

**A README cannot enforce these rules.**

README prose alone does not enforce the row schema. Here, each claim declares its grade
and weight. The validator **refuses weight** without a deciding recipe, bounds, a witness that the
recipe has reported the claim false, or a clause read from its own evidence. The claim remains
*admitted*.

The component ideas are established. Mutation testing, model-checking vacuity detection, and
fault-injection mandates for tool qualification require evidence that checks can fail. The
claims-and-evidence shape comes from assurance cases. This format makes
a demonstrated ability to fail a mandatory per-claim condition inside the document format rather than
an optional score.
