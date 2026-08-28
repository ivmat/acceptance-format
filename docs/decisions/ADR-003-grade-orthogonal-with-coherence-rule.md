# ADR-003: grade is orthogonal to band and to epistemic tier, bound by a coherence rule

**Status:** Accepted (2026-08)

## Context

`grade` (does the evidence decide the item?), `band` (how good is the evidence species?), and
`epistemic_tier` (how strong is the method that produced one record?) are three different
questions. Collapsing them into one strength ladder produced a real overclaim: a domain-complete,
unbounded proof was demoted to `CONTRACT (bounded)` because the ladder had no rung for
"unbounded, no kernel check" — an underclaim, the same defect as an overclaim pointed the other way.

## Decision

Keep the three axes independent, but add one coherence rule where independence would otherwise let
a weak record earn a strong grade: `grade = "contract"` on a weighted claim requires at least one
**passing** evidence record whose `epistemic_tier` is `T1` or `T2`, and whose declared `bounds`
cover the claim's declared domain. `epistemic_tier` alone cannot distinguish a `probe` from a
`contract` use of the same tool — only the scope-coverage half of the rule can, so both halves are
required together.

## Consequences

A high-band, high-tier proof that does not decide the claimed item stays at `probe`, honestly. No
new grade token is needed for "a strong tool applied to the wrong domain" or for "sampled but
substantial" evidence (`epistemic_tier = T3` + `grade = probe` covers it without inventing a token).
The rule is validator-enforced, not left to reviewer judgment alone.
