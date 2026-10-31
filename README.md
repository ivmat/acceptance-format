# Acceptance protocol + format

**Acceptance 0.4.0 — locked, not ratified.** Record what an artefact must do,
which claims have evidence, what remains unchecked, and a consumer's acceptance
decision. Validation checks those records; it does not prove the software correct
or ratify the specification.

<a id="why-a-green-check-is-not-enough-the-check-must-be-able-to-fail"></a>

The **format** stores claims, evidence, bounds and gaps in `acceptance.toml`.
A weighted claim needs an honest grade, a rerunnable check and a
[recorded witness that the check can fail](OVERVIEW.md#3-every-weighted-claim-shows-that-its-check-can-fail).
The **protocol** connects three documents by content hashes: the
consumer's specification, the producer's package and the consumer's decision.

Start with the [overview](OVERVIEW.md) for a walkthrough, or the
[documentation index](docs/README.md) for a specific task.

## Quickstart

Python 3.11+ is required. From the repository root, check the small Python example:

```sh
python3 format_acceptance/tools/check_acceptance.py --root . --strict --strict-weight examples/weighted-toy/acceptance.toml
python3 examples/weighted-toy/test_slug.py
```

The first command checks the recorded evidence; the second runs its five test
cases. See [weighted-toy](examples/weighted-toy/README.md) for the fields and
recorded failure control. For all public gates, run `bash gates/run_all.sh`.

The [Rust delivery](protocol_acceptance/examples/rust-delivery/README.md) shows
all three protocol documents. [Paint-stack](protocol_acceptance/examples/paint-stack/README.md)
shows acceptance across workspace libraries, with commands to check and render
the recorded decisions. Reproducing their evidence additionally needs Rust and
Kani; checking the records does not rerun those tools.

## Read next

| Task | Start here |
|---|---|
| Understand the workflow | [Overview](OVERVIEW.md) |
| Find a rule, profile or example | [Documentation index](docs/README.md) |
| Compare with other formats | [Why this format](WHY.md) |
| Assess current limitations | [Known limits](KNOWN-LIMITS.md), [assumptions](ASSUMPTIONS.md) |
| See changes or planned work | [Changelog](CHANGELOG.md), [roadmap](ROADMAP.md) |
| Read the theory | [Acceptance paper](docs/papers/acceptance/README.md) — preprint, not peer reviewed |

## Current limits

- The tools check record consistency, not whether the evidence is true or the
  requirements are adequate. All example parties are simulated; one author wrote them.
- Stacking checks Cargo workspace libraries. A crates.io or git dependency makes
  the whole stack check indeterminate. Each library has its own evidence floor;
  accepting a stack adds no combined assurance. Toolchain and platform relations
  in paint-stack are trusted as the base, not checked.
- The trusted directory of decisions is unsigned: write access is authority.
- When the named subject commit is unavailable, `--tree` checks recorded digests
  only. Files without digests are not covered, and the presented bytes are not
  proven to be the commit's bytes.

The 0.4.0 checker refuses 0.3 protocol documents. Use
[tag v0.3.2](https://github.com/ivmat/acceptance-format/tree/v0.3.2) for them, or
[the migration tool](protocol_acceptance/tools/acceptance_migrate.py).
Migration previews changes by default; `--write` applies them. Consumers must
re-issue decisions. [Known limits](KNOWN-LIMITS.md) is the full current list.

## Provenance and license

`EXPORT-PROVENANCE.json` records the export source commit, dirty state, family
version and SHA-256 of each exported file. Its family version is authoritative
for later editorial exports. The two repository-resident license files are not
exported and have no provenance entries.

Dual licensed under [Apache-2.0](LICENSE-APACHE) or [MIT](LICENSE-MIT). The paper
under `docs/papers/` is licensed under CC BY 4.0.
[License notes](LICENSE-NOTES.md) explain the choice for each material type.
