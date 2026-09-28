# Roadmap

*Planned, not final. Nothing described in the 0.4.x sections below is built; this page states
direction, not a commitment to exact scope or dates.*

## 0.4.0 — consumer source policy and stacking

Two additions to the acceptance protocol.

**Consumer source policy.** A consumer will be able to declare, per contract, which verification
tools and which reviewer identities it accepts. Evidence produced by a tool or reviewer the
consumer has not listed will not count toward that consumer's acceptance decision, even when the
evidence is otherwise well-formed. A single requirement will be able to narrow that list further,
never widen it.

**Stacking (dependency acceptance).** This is a different sense of "stack" from
`protocol_acceptance/spec/protocol.md` §9 ("Composition with the rest of the stack"), which is
about this protocol composing with OTHER external protocol models (obligations, grants,
work-contracts) — none of which ship as part of this release (see
[KNOWN-LIMITS.md](KNOWN-LIMITS.md)); stacking here is about a producer's OWN dependency chain.

A producer will be able to declare its own dependencies
(direct and transitive, drawn from its lockfile) as part of its acceptance package. A consumer will
be able to require that some or all of those dependencies — and the tools that built them — are
themselves accepted, not merely present. Four levels are planned, of increasing strength:

- the dependency is disclosed, with its exact identity checked;
- the dependency ships its own acceptance package (self-attestation);
- the dependency has an actual acceptance decision from a named acceptor, checked against a store
  of trusted decisions the consumer configures;
- the consumer re-evaluates the dependency's own evidence directly against its own contract.

0.4.0 plans the first and third of these levels, for one ecosystem (Rust) to start. An unsigned,
consumer-configured store of trusted decisions stands in for a full trust infrastructure until
signing arrives later. Whole-stack acceptance — covering every dependency in a producer's declared
closure — is planned without walking a full dependency graph: the flattened list of transitive
dependencies is the declaration a consumer checks against. Temporal rules apply throughout: a
dependency's acceptance decision must still be valid at the time it is relied on, not merely have
been true once.

## 0.4.1 — function-level tracing

Extends stacking from whole-dependency acceptance to tracing which specific accepted claims back a
particular function call across a chain of libraries, so a consumer can check not just "is this
dependency accepted" but "is the exact code path I call accepted."

## 0.4.2 — configuration receipts

Adds tool-emitted evidence of the actual build configuration (compile-time features, target
platform, and similar) used to produce an accepted artifact, so a claim's stated configuration
assumptions can be checked against what was really built, rather than only declared.

## Also planned for 0.4

Carried over from 0.3.x's stated known limits — see [KNOWN-LIMITS.md](KNOWN-LIMITS.md) for the
complete, current list.
