# ADR-006: bands are control-gated, independently of epistemic tier

**Status:** Accepted (2026-08)

## Context

Evidence species alone cannot tell a watched check apart from an unwatched one: a Kani harness or
Lean proof whose oracle nobody perturbed reads identically, at the species level, to one a mutation
control proved actually catches bugs. Species sets a ceiling; it does not establish that the check
would fail on a wrong answer.

## Decision

A band's ceiling is set by evidence species (`assurance-bands.md`'s per-band table), but reaching
an oracle-bearing band (A2, A3, A4, or functional A1) additionally requires an **observed-red**
control on that claim's evidence — a mutation, or for memory safety an ablation, that was watched to
fail as predicted. A `green`/`green` control passes but does not lift a band; only a literal
observed-red result does, and it must come from a carrier record species-compatible with the band
being lifted (a `judgment` record can never band-lift a mechanical gate).

## Consequences

"The proof is green" and "the proof was shown able to catch a bug" are different claims, and only
the second raises a band. A claim whose species would reach a band but lacks the matching control
is marked `partial`, never asserted at the ungated band. This is independent of `epistemic_tier`
(ADR-002): a record can be `T1`/kernel-checked and still sit at A0 until its control is observed
red.
