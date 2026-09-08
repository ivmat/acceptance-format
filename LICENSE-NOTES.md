# License notes — by material type

This repository is dual-licensed under [LICENSE-APACHE](LICENSE-APACHE) / [LICENSE-MIT](LICENSE-MIT)
as a whole (see [README.md](README.md) "Author & license"). This note records the license
*rationale per material type*, so a consumer of one part of the tree does not have to infer it from
the two license files alone. It does not change either license file, and it grants nothing beyond
what those files already grant — it is a map, not a new grant.

| material | license | why |
|---|---|---|
| code — `tools/*.py`, `gates/*.py` | Apache-2.0 / MIT, dual (current) | standard for a validator/tooling repo; matches the repo-wide license already in force |
| schemas — `schema/*.schema.json` | Apache-2.0 / MIT, dual (current) | generated from the same code (`tools/emit_schema.py`); same rationale as code, one license family for the whole generation pipeline |
| prose spec — `spec/*.md`, `profiles/*/PROFILE.md`, `README.md`, `WHY.md`, `QUICKSTART.md`, `ASSUMPTIONS.md`, `docs/*.md` | Apache-2.0 / MIT, dual (default) | kept in the same license family as the code it specifies, rather than splitting the repo across a code license and a separate prose license (e.g. CC-BY-4.0); this is the *default* the owner named, not a claim that CC-BY-4.0 was considered and rejected on the merits — see "Open items," below |
| examples — `examples/*`, `profiles/*/examples/*` | per the subject repo each example certifies | an example manifest names a real or illustrative subject; where the subject is a real, separately-licensed artifact (e.g. the `verify-rust-std` PR examples), the example's own license follows that subject's license, stated per example directory (`examples/verify-rust-std-pr618/`, `examples/verify-rust-std-pr664/`); illustrative/synthetic examples with no real external subject (e.g. `examples/minimal.acceptance.toml`, `profiles/verification/examples/`) fall under the repo-wide dual license like any other prose/tooling file, having no external subject to inherit a license from |

## Contributor provenance

Single author today (Ivo Matijasevic, [@ivmat](https://github.com/ivmat)). No CLA/DCO is in force;
that choice is open, not silently decided by this note.

## Private / excluded material

Nothing under this boundary is present in this repository; the boundary is stated here so its
absence reads as a design decision rather than an oversight. The following categories are
EXCLUDED from this repo, by construction, and were never included in any commit:

- a `_calibration/` directory of any kind (calibration objects tying a measured number to its
  validity scope, `spec/format.md` H5) — this format's own `alpha`/`beta`/`lr` reservation
  (design rule 3) means a calibration corpus, if one ever existed, would be exactly the kind of
  material that stays private while the fields that reference it stay public;
- any evidence corpus belonging to a private subject (a manifest MAY certify a private artifact
  without its evidence records ever leaving that artifact's own private repository — `record_root`,
  `spec/format.md`, is the mechanism that lets a manifest cite evidence it does not itself carry).

## Open items (T1: not decided here)

- Prose spec license: dual (current default, per owner word 2026-09-08) vs. CC-BY-4.0 — open,
  not ruled on the merits.
- Contributor provenance: CLA/DCO — open.
