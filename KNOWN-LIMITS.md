# Known limits — 0.4.0

Acceptance 0.4.0 — locked, not ratified. A validator PASS is not ratification,
a signature, or proof that the evidence is true.

Deferred mechanisms (see [ROADMAP.md](ROADMAP.md) for planned work):

- B8 claim-discharge mode (using a source verdict without named records). B8
  `acceptance-claim` reference evidence ships and requires named source records. It is also
  distinct from the shipped decision-level `[[condition]].discharged_by` field
  (protocol.md §5.3).
- Digest/components freshness; freshness remains commit-only.
- Multiple governing `[spec]` documents.
- `gap_reason` and `spec_drift` claim fields.
- Registration of additional `when_kind` kinds (currently usable through `kind_registry`).
- The fault-resolution protocol and package-integrity profile.
- Signing and DSSE.
- Retirement of conformance compatibility paths. At resolved profile version `0.1.0-draft`,
  `source_claim`, `source_claims_other` and `[conformance].source_manifest{,_hash}` are inert
  metadata accepted with warnings; at `0.2.0` they are errors. They never supply borrowing
  evidence. Legacy applicability encodings remain, and `[conformance].cover_only` is
  read-only with a warning at `0.1.0-draft` and dropped at `0.2`. Borrowing uses B8 named-record
  references, as described in the [conformance profile](format_acceptance/profiles/conformance/PROFILE.md).
- Retirement of untyped legacy record hashes. The current validator still accepts matching
  legacy wires read-only with warnings; writers must emit typed `record:sha-512:` hashes.
  This is separate from the refusal of 0.3 protocol documents.
- The `external_pilot` readiness level.

Stacking checks workspace path dependencies only. If any dependency in the closure comes from
crates.io or git, the whole stack check is undecided (indeterminate), never accepted. A consumer configures an unsigned directory store: write access is authority;
backdating and removal followed by restoration are undetected. Hash and issuer checks show
consistency, not authorship. Each commit is a separate identity, so a new commit needs a new
acceptance. With `--tree`, a checkout lacking the named commit (every clone of this repository)
is treated as a non-checkout; only the recorded digests are checked. Outside a checkout the same
limit applies: the presented bytes are not proven to be the commit's bytes. Files without recorded
digests are not covered.

The independence levels are not nested. The order `none < author-not-producer < consumer-run <
third-party` puts `consumer-run` above `author-not-producer`, but `consumer-run` demands only the
consumer's own passing re-run (protocol.md §5.2), not an author outside the producer
(§6.2 condition 8). So a successor specification may move a requirement from
`author-not-producer` to `consumer-run` without a `relaxed` record, a requirement at
`consumer-run` meets an assurance-class target of `author-not-producer`, and the shipped class
table drops the author condition between `baseline/2` and `baseline/3`. Producer-authored or
author-less evidence that the consumer re-ran then satisfies the requirement. A consumer that needs
both demands should use `third-party`, which demands both and also an author outside the
consumer. A later version will treat independence as separate,
monotone facts.

The per-requirement status list in protocol.md §6.3 is incomplete as written. A requirement whose
only claims are `not-applicable`, with no deviation, matches none of its five cases. A below-floor
`evidenced` claim together with a deviation matches two of them. The tools apply the cases in this
order, and the first that holds decides: `missing`, `satisfied`, `partial`, `deviation-declared`,
then `gap` for everything else, including the `not-applicable` case. Read §6.3 in that order. A
later version will state it in the specification text; no result changes.

There is no combined assurance for a stack. Each library is accepted under its own
specification and evidence floor. Paint-stack's label covers runtime libraries only;
toolchain and platform relations are trusted as the base and are not checked. A source
acceptance and a declared build-time-copy binding do not prove that compilation preserves
meaning.

A condition is a `[[condition]]` row on an `accepted-with-conditions` decision. It is
discharged only by a new, superseding decision presenting the discharging package
(protocol.md §5.3), never by an in-place edit. Authority, delegation and effect eligibility
remain in this release; the downstream effect gate itself is outside it.

The supplied Rust examples are regenerated at 0.4.0 with typed `record:sha-512:` hashes.
IB-001/IB-002 band-wording warnings remain known limits if emitted. Untyped legacy record-hash
warnings remain in the conformance teaching fixtures. Rechecking records does not rerun
Cargo or Kani.

The weighted toy retains its historical evidence and commit identity. Its package declares
the verification profile and binds the updated teaching specification; its test recipe is
rerun by the gate. It uses a typed `record:sha-512:` hash.

The minimal example is fictional and validated as a producer-only record shape;
its evidence pointers are placeholders, so it is not a strict evidence certificate.

The historical `rs-verified-der` example is not included in this export. The comparison
document discusses it as a case study, not as a current validated example.

The 0.4.0 checker refuses 0.3 protocol documents. Check them with
[tag v0.3.2](https://github.com/ivmat/acceptance-format/tree/v0.3.2), or use
[the migration tool](protocol_acceptance/tools/acceptance_migrate.py) and have the consumer
re-issue decisions.

The public closure gate uses export provenance and exercises the closure exporter and
standalone verifier. The protocol and adoption selftests require git for temporary test
repositories. A policy blocking git writes prevents those tests from completing; the suite
reports that failure.
