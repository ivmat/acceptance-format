# License notes — by material type

This repository is dual-licensed under [LICENSE-APACHE](LICENSE-APACHE) / [LICENSE-MIT](LICENSE-MIT)
as a whole (see [README.md](README.md), "Dual licensed under Apache-2.0 or MIT"). This note records
the license *rationale per material type*, so a consumer of one part of the tree does not have to
infer it from the two license files alone. It does not change either license file, and it grants
nothing beyond what those files already grant — it is a map, not a new grant.

`EXPORT-PROVENANCE.json`'s provenance covers every file this repository exports; the two license
texts themselves are repository-resident (present in every checkout, not produced by the export)
and carry no provenance entry of their own.

| material | license | why |
|---|---|---|
| code — `format_acceptance/tools/**/*.py`, `protocol_acceptance/tools/**/*.py`, `gates/*.py` | Apache-2.0 / MIT, dual | standard for a validator/tooling repo; matches the repo-wide license already in force |
| data — `*.toml` manifests, fixtures and clause inventories (e.g. `CLASS-LOCK.toml`, `protocol_acceptance/spec/*.toml`, `format_acceptance/profiles/conformance/standards/*.clauses.toml`) | Apache-2.0 / MIT, dual | generated or hand-written alongside the code and spec they support; a clause inventory carries only clause numbers and short titles in this repository's own words, never the cited standard's normative text (see `format_acceptance/profiles/conformance/standards/README.md`'s copyright rule) |
| prose spec — `format_acceptance/spec/**/*.md`, `format_acceptance/profiles/**/*.md`, `protocol_acceptance/spec/**/*.md` (including `protocol_acceptance/spec/adapters/`), `protocol_acceptance/adoption/*.md`, `README.md`, `WHY.md`, `KNOWN-LIMITS.md`, `CHANGELOG.md`, `ROADMAP.md`, `ASSUMPTIONS.md`, `docs/*.md` | Apache-2.0 / MIT, dual (default) | kept in the same license family as the code it specifies, rather than splitting the repo across a code license and a separate prose license; this is the *default*, not a claim that an alternative (e.g. CC-BY-4.0) was considered and rejected on the merits — see "Open items," below |
| examples — `examples/*`, `format_acceptance/examples/*`, `format_acceptance/profiles/*/examples/*`, `protocol_acceptance/examples/*` | Apache-2.0 / MIT, dual | every example in this release is either illustrative/synthetic (a fictional subject, invented clause standard, or placeholder evidence pointer) or a small crate written for this repository (`iban-check`, in `protocol_acceptance/examples/rust-delivery/`); none certifies a real, separately-licensed external subject, so none needs a license distinct from the repository's own |

## Contributor provenance

Single author today (Ivo Matijasevic, [@ivmat](https://github.com/ivmat)). No CLA/DCO is in force;
that choice is open, not silently decided by this note.

## Private / excluded material

Nothing under this boundary is present in this repository; the boundary is stated here so its
absence reads as a design decision rather than an oversight. The following categories are
EXCLUDED from this repo, by construction, and were never included in any commit:

- a calibration corpus of any kind (an object tying a measured `alpha`/`beta`/`lr` number to its
  validity scope, `format_acceptance/spec/core.md` design rule 3) — this format's own reservation
  of those fields to a calibration-bearing evidence entry means a calibration corpus, if one ever
  existed, would be exactly the kind of material that stays private while the fields that
  reference it stay public;
- any evidence corpus belonging to a private subject (a manifest MAY certify a private artifact
  without its evidence records ever leaving that artifact's own private repository — the class B8
  records-mode reference, `format_acceptance/spec/core.md` B8, is the mechanism that lets a
  manifest cite evidence it does not itself carry).

## Open items

- Prose spec license: dual (current default) vs. an alternative such as CC-BY-4.0 — open, not
  ruled on the merits.
- Contributor provenance: CLA/DCO — open.
