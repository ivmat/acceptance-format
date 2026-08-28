# ADR-002: `epistemic_tier` (closed core) vs `method` (profile-open) split

**Status:** Accepted (2026-08)

## Context

An evidence record needs to say two different things: how strong its evidence species is in
general (a kernel-checked proof outranks a fixture test), and which concrete technique actually
produced it (`kani-harness`, `lean-theorem`, a future profile's own tool names). A single open field
cannot carry both without letting a profile invent artificial strength by naming a new technique.

## Decision

Split the two axes. `epistemic_tier` is a closed, core, artifact-agnostic set of five tokens (`T1`
deductive/kernel-checked through `T5` human-judgment); only the format itself may add a tier value.
`method` is an open, profile-defined token naming the concrete technique. Every profile that
declares a `method` token must publish a `method → epistemic_tier` mapping for it, and a record's
declared `epistemic_tier` may never exceed what the profile's table assigns to its `method`.

## Consequences

A profile can add new techniques without a format revision, but cannot manufacture epistemic
strength the format did not certify. The pre-existing `kind` field is demoted to a profile-open
hint, never authoritative for grading. `family` (bmc/kernel/smt-refinement/dynamic/mechanical/
judgment) is unchanged for this revision and keeps governing the band control-gate; its eventual
retirement into `method` vocabulary is a separate, future change.
