# Acceptance protocol + format

**Acceptance 0.3.2 — locked, not ratified.** The 0.3.x release records requirements,
evidence and a consumer's acceptance decision. Validation checks the records;
it does not certify the software or ratify the specification.

The format describes claims and their evidence. The protocol connects a consumer's
contract, a producer's package and a consumer's decision. Verification, conformance
and troubleshooting profiles add domain rules. Assurance classes set evidence floors.

## Quickstart

Python 3.11+ is required. From this tree's root, validate the supplied Rust example:

```sh
python3 format_acceptance/tools/check_acceptance.py --root . --strict --strict-weight protocol_acceptance/examples/rust-delivery/acceptance.toml
python3 protocol_acceptance/tools/acceptance_protocol.py check-contract protocol_acceptance/examples/rust-delivery/acceptance-contract.toml
python3 protocol_acceptance/tools/acceptance_protocol.py check-package protocol_acceptance/examples/rust-delivery/acceptance.toml --contract protocol_acceptance/examples/rust-delivery/acceptance-contract.toml
python3 protocol_acceptance/tools/acceptance_protocol.py check-decision protocol_acceptance/examples/rust-delivery/acceptance-decision.toml --contract protocol_acceptance/examples/rust-delivery/acceptance-contract.toml --package protocol_acceptance/examples/rust-delivery/acceptance.toml
bash gates/run_all.sh
```

These commands check the supplied records. Reproducing the Rust evidence additionally
requires the Rust and Kani toolchains; see the example's README.

Read the [format](format_acceptance/spec/core.md),
[protocol](protocol_acceptance/spec/protocol.md),
[weighted-tier rules](format_acceptance/spec/0.1-DRAFT.md),
[worker-brief adapter](protocol_acceptance/spec/adapters/worker-brief.md),
[Kani adoption guide](protocol_acceptance/adoption/KANI-FV-ADOPTION.md),
[assumptions](ASSUMPTIONS.md) and [comparisons](WHY.md).

## Known limits

The Rust example ships as supplied, regenerated with typed `record:sha-512:` hashes; the
weighted toy is typed the same way. IB-001/IB-002 band-wording warnings are accepted known
limits if emitted; untyped legacy record-hash wire warnings remain only for the conformance
profile's fixtures, which are copied read-only teaching material and are not migrated. The
gate output records the warnings for this exact cut. See
[KNOWN-LIMITS.md](KNOWN-LIMITS.md) for the mechanisms deferred to 0.4, and
[ROADMAP.md](ROADMAP.md) for what 0.4 is planned (not final) to add.

`EXPORT-PROVENANCE.json` identifies the exact source commit, family version, dirty
state and SHA-256 of every exported file it lists; the two license files below are
repository-resident and are not themselves exported files, so they carry no provenance
entry. The source family version there is authoritative for later editorial 0.3.x exports.

Dual licensed under Apache-2.0 or MIT; see [LICENSE-APACHE](LICENSE-APACHE) and
[LICENSE-MIT](LICENSE-MIT). [LICENSE-NOTES.md](LICENSE-NOTES.md) records the license
rationale per material type.
