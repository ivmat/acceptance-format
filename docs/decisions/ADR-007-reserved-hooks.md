# ADR-007: reserved hooks ship as names, with no machinery, until ruled

**Status:** Accepted (2026-08)

## Context

Several ideas the format wants eventually — independence-weighted corroboration, attestations,
defeaters, per-claim revisit triggers — are not yet fully designed, but the field names and slot
shapes they will need should not force a breaking format-id change once they are. Building the
engine ahead of the design, or letting a schema field imply a computation nothing performs, is the
overclaim this format exists to prevent, pointed at its own roadmap.

## Decision

Reserve the hook by name only: a field, a block, or a token that the schema makes room for, stated
explicitly as a reservation ("reserved for a later engine," never "computes" or "decides"). No
validator reads a reserved hook for a verdict; no ledger sums it; no engine propagates it. A
producer may populate one today, and it is admissible exactly like any other unweighted, free-shaped
field — recorded, not acted on. Seven hooks ship this way: independence/interest-conflict slots,
provenance-correlation keys, attestations, defeaters, calibration-with-validity-scope, per-claim
revisit triggers, and two new composition-edge types.

## Consequences

Adding real machinery for a reserved hook later needs no format-id break, because the slot already
exists. Until then, standing, attestation, or a populated-but-unengineered field can never raise a
claim's `epistemic_tier` or its weight — the document must never say a reserved hook does something
it does not yet do.
