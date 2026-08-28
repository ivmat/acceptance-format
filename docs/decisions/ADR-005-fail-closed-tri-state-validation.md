# ADR-005: fail-closed tri-state validation; illustrative vs certificate contexts

**Status:** Accepted (2026-08)

## Context

A validator that only ever says pass or fail cannot distinguish "this manifest is wrong" from "this
manifest names something the validator does not yet understand" (an unprofiled method, an
unresolved bundle reference). Silently treating the second case as a pass reproduces the exact
"looks fine because we could not check it" failure the format exists to prevent. Separately, a
teaching example and a real certificate need different strictness, but a reader must never confuse
one for the other.

## Decision

The validator returns one of three mutually exclusive states, each its own exit code: `valid` (0),
`invalid` (1, a structural obligation is violated), and `indeterminate` (2, the validator cannot
decide). `indeterminate` is non-accepting and its exit is always nonzero — a gate may never treat it
as passable. Separately, a manifest declares `illustrative = true` or is a certificate; there is no
third state, and any rendering of an illustrative manifest must visibly label it as such.

## Consequences

A caller can script on the exit code alone and never mistake "cannot verify" for "verified clean."
An illustrative manifest can teach the format's shape without ever being read as certifying a real
subject. Both rules are validator-enforced, not left to a rendering's prose.
