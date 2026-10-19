---
type: reference
---

# Paper: Acceptance as a Protocol for Delegated Work

*Claims, Failure Witnesses and Refusal.* Ivo Matijašević, October 2026.

**Version 1, 19 October 2026. Preprint, not peer reviewed.** The paper describes specification 0.4.0 (commit `3dbd403`),
which is locked, not ratified.

## What it is

The paper gives the theory behind this format and protocol. It is an introductory read: what the format
guarantees, stated exactly, and what it does not. It is a direct attempt to mechanize acceptance in actual systems,
so that the acceptance of real work is checked by programs wherever it can be. It covers:

- the model;
- eight results with proofs: coverage is total; floors that only tighten preserve acceptability, with the known
  exceptions stated; staleness is exact up to hash collision; recorded labels alone give no nontrivial stack bound;
  chains fail closed; duties are separated; a failure control shows exactly "not constant-pass"; the verdict fold
  of a proposed pure core is total;
- acceptance as the core of the protocols a delegated worker needs;
- behaviour specifications that do not depend on the implementation language, with one pilot experiment;
- the comparison with other formats, and the open problems.

## Why a new format

A format of our own has no external constraint: no other standard's scope, schedule or compatibility
obligations. That leaves us free to design the best format for every use case we care about, and that we think
others care about too. It does not close off interoperability. Where an existing format is adequate, we can fall
back to it, with extensions if needed, and map our records onto it. A second reason is the combination the paper
describes, which no surveyed format requires. See also [WHY.md](../../../WHY.md).

## Files

- `paper_acceptance.tex` is the LaTeX source. Build it with `latexmk -pdf paper_acceptance.tex`. It needs a standard
  TeX Live installation.
- The PDF is attached to the release `paper-acceptance-v1` of this repository. A citable archived copy is on
  Zenodo, and its DOI is listed on that release page.

## Licence

The paper text (`paper_acceptance.tex` and its PDF) is licensed under the Creative Commons Attribution 4.0
International License (CC BY 4.0). This is an exception to the repository's Apache-2.0 / MIT licence for code and
specification text; see [LICENSE-NOTES.md](../../../LICENSE-NOTES.md).
