# Known limits — 0.3.x

Acceptance 0.3.2 — locked, not ratified. A validator PASS is not ratification,
a signature, or proof that the evidence is true.

Deferred to 0.4 (see [ROADMAP.md](ROADMAP.md) for what 0.4 is planned, not final, to add):

- B8 claim-discharge mode (a claim discharged through a reference to another claim — distinct
  from the shipped `[[condition]].discharged_by` decision-level field, protocol.md §5.3).
- Digest/components freshness; freshness remains commit-only.
- Multiple governing `[spec]` documents.
- `gap_reason` and `spec_drift` claim fields.
- Registration of additional `when_kind` kinds (currently usable through `kind_registry`).
- The fault-resolution protocol and package-integrity profile.
- Signing and DSSE.
- Retirement of the conformance 0.1 legacy-field compatibility shim.
- Retirement of untyped legacy record hashes. They produce warnings throughout 0.3.x;
  writers must emit typed `record:sha-512:` hashes.
- The `external_pilot` readiness level.

The obligation, grant and effect-gate formats that a condition's discharge (protocol.md §5.3),
change-impact re-verification (§8) and stack composition (§9) refer to are not part of this
release; only the reference points the protocol declares are shipped, not those formats
themselves. In 0.3.x a condition is a `[[condition]]` row on an `accepted-with-conditions`
decision; it is discharged only by a new, superseding decision that presents the discharging
package (§5.3), never by an in-place edit.

The supplied `rust-delivery` records are regenerated with typed `record:sha-512:` hashes.
IB-001/IB-002 band-wording warnings are accepted known limits if emitted; untyped legacy
record-hash wire warnings remain only for the conformance profile's fixtures (retirement of the
untyped wire is deferred to 0.4, per the list above). Rechecking records does not rerun cargo or
Kani.

The weighted toy retains its historical evidence and commit identity. Its public
0.3 package declares the verification profile and binds the supplied teaching
contract; its test recipe is rerun by the gate. It carries a typed `record:sha-512:`
hash and validates without a legacy-hash warning.

The minimal example is fictional and validated as a producer-only record shape;
its evidence pointers are placeholders, so it is not a strict evidence certificate.

The `rs-verified-der` example is omitted pending migration. The historical
comparison document discusses it as a case study, not as a current validated example.

The public closure gate uses export provenance and exercises the unchanged closure
exporter and standalone verifier. The protocol and adoption selftests also require
git for temporary test repositories. A policy blocking git writes prevents those
tests from completing; the suite reports that failure.
