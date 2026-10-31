# Documentation index

Read one path for the task at hand. The linked specifications remain the rule
sources; this index adds no requirements. Acceptance 0.4.0 is locked, not ratified.

## Tasks and examples

| Task | Read |
|---|---|
| Understand specification → package → decision | [Overview](../OVERVIEW.md) |
| Write a first weighted manifest | [Weighted toy](../examples/weighted-toy/README.md) |
| Accept a delivery with unmet requirements | [Rust delivery](../protocol_acceptance/examples/rust-delivery/README.md) |
| Choose evidence floors by criticality | [Assurance classes](../protocol_acceptance/spec/assurance-classes.toml) |
| Tighten requirements or amend a specification | [Protocol](../protocol_acceptance/spec/protocol.md): §§3.5–3.6 |
| Check a dependency stack | [Paint-stack](../protocol_acceptance/examples/paint-stack/README.md) |
| Report verification and its bounds | [DER case study](CASE-STUDY.md), [verification profile](../format_acceptance/profiles/verification/PROFILE.md) |
| Check a named standard | [Conformance profile](../format_acceptance/profiles/conformance/PROFILE.md), [examples](../format_acceptance/profiles/conformance/examples/README.md) |
| Record whether faults can be diagnosed | [Troubleshooting profile](../format_acceptance/profiles/troubleshooting/PROFILE.md) |
| Brief a worker or adopt the protocol for Rust verification | [Worker adapter](../protocol_acceptance/spec/adapters/worker-brief.md), [Kani adoption guide](../protocol_acceptance/adoption/KANI-FV-ADOPTION.md) |
| Migrate older protocol documents | [Migration tool](../protocol_acceptance/tools/acceptance_migrate.py), [known limits](../KNOWN-LIMITS.md) |
| Compare approaches or inspect the theory | [Comparisons](../WHY.md), [acceptance paper](papers/acceptance/README.md) |

## Format rules

| Question | Source and section |
|---|---|
| What is a claim, and what is admissible evidence? | [Core](../format_acceptance/spec/core.md): glossary, §§1–3 (B-rules) |
| How are pass, fail and indeterminate composed? | [Core](../format_acceptance/spec/core.md): §4 verdict table |
| Which TOML fields and hash domains apply? | [Format schema](../format_acceptance/spec/format.md), [hash domains](../format_acceptance/spec/hash-domains.md) |
| What is a profile or binding? | [Profiles](../format_acceptance/spec/profiles.md), [bindings](../format_acceptance/profiles/bindings/README.md) |
| What makes a claim weighted? | [Weighted-tier rules](../format_acceptance/spec/0.1-DRAFT.md): §§1–5 grades, bounds, recipes and controls; §8 weight rules |
| How do status, grade and weight fit together? | [Weighted-tier rules](../format_acceptance/spec/0.1-DRAFT.md): §7.1; §8.1 weight-pending |
| How is the record rendered without hiding gaps? | [Coverage ledger](../format_acceptance/spec/coverage-ledger.md) |
| What do evidence records and bands mean? | [Evidence types](../format_acceptance/spec/evidence-types.md), [assurance bands](../format_acceptance/spec/assurance-bands.md) |

`0.1-DRAFT.md` is a live weighted-tier document despite its historical filename.
It is not one of the Class files frozen by `CLASS-LOCK.toml`; existing citations
still use that path.

## Protocol rules

The [protocol specification](../protocol_acceptance/spec/protocol.md) is organized
by the document or operation you need:

| Topic | Section |
|---|---|
| Roles and design rules | §§1–2 |
| Specification, evidence floors and amendments | §3 |
| Producer package | §4 |
| Consumer decision, conditions and effect eligibility | §5 |
| Computed requirement coverage and stacking | §6 |
| Content binding and hashes | §7 |
| Change impact and re-verification | §8 |
| Outer layers and rendering | §§9–10 |
| Residual limits | §11 |

For current caveats read [KNOWN-LIMITS.md](../KNOWN-LIMITS.md); for trusted inputs
read [ASSUMPTIONS.md](../ASSUMPTIONS.md). [CHANGELOG.md](../CHANGELOG.md) records
shipped changes and [ROADMAP.md](../ROADMAP.md) records future direction.
