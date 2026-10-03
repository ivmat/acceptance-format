# Roadmap

*Planned, not final. Nothing described in the 0.4.x sections below is built; this page states
direction, not a commitment to exact scope or dates.*

## Scope: what the acceptance protocol is, and what it is not

The acceptance protocol is an **artefact-acceptance protocol between two roles**:
- the **producer** delivers an artefact together with evidence;
- the **consumer** judges it against the consumer's own specification, at a verification strength
  the consumer chooses.

Its moves are:
- clarify a specification;
- expand a specification;
- select the verification strength per requirement;
- deliver;
- judge;
- relax or drop a requirement.

**Out of scope, by design:** transactions, payment, pricing, legal standing, negotiation of terms and
business contracts. The protocol has to work with no monetary incentive at all, where the only goal
is to satisfy the specification.

**Designed to fit into those layers.** A contract, payment or legal process can cite an acceptance
by stable identifiers, content hashes and verdicts. The acceptance documents carry none of that
process's fields. Such layers can be built as separate protocols composed on top of this one, and
they never change the acceptance core.

The 0.3.2 release still contains some of these outer concerns, in its specification, its tools and
its tests:
- buyer, seller, supplier, customer and vendor wording for the consumer and producer roles, in the
  protocol specification (for example "the buyer's word" for ratification), in the format
  documentation, in tool comments, and in test fixtures and examples (producers named `supplier-…`,
  a supplier-policy reference, a request-for-proposal note, vendor-assurance examples);
- conditions on an acceptance framed as debts, with the producer as debtor and the consumer as
  creditor;
- the work-contract envelope, and the transaction and compensation notes, in
  `protocol_acceptance/spec/stack.md` and in §9 of the protocol;
- the `[parties]` boundary terms, including `legal_ref`;
- a `legal` requirement domain;
- assurance classes illustrated with monetary examples (an investing application);
- effect eligibility, with payment named among the effects a gate may unlock (publish, deploy, pay,
  merge).

They are not part of the acceptance core, and the 0.4 line moves them out (next section). The worked
Rust example's consumer is a fictional payments company because the delivered crate validates bank
account numbers (IBANs). That is the example's subject matter, not a protocol concern.

Two kinds of mention are **not** outer concerns, and they stay:
- **Requirements about the artefact itself**, such as the licence it must carry, are ordinary
  specification content.
- **This repository's own terms**: its licence files and contributor notes, and the copyright of
  the standards a conformance profile checks against. These concern the repository and its inputs,
  not the protocol.

## 0.4 line: the pure acceptance protocol (target)

The 0.4 line restructures the protocol around a pure core. Target shape:

- **Two roles**, producer and consumer. Each document names who wrote it, because independence
  checks need that.
- **Three documents**: specification, package and judgment. Today's "contract" is renamed
  *specification*, so that it is not read as a business contract.
- **The moves listed above.** A clarification or expansion produces a new specification version.
- **Verification strength as several independent axes, not one ladder.** The consumer sets a floor
  on each axis per requirement. The planned axes are:
  - soundness tier;
  - evidence origin: whether the evidence comes from a checker of the same family as the producer,
    from an independent family, or from observed real-world outcomes;
  - independence: who wrote the evidence, and whether the consumer re-ran it and it passed;
  - freshness: whether the evidence is bound to the delivered revision;
  - pinned inputs: whether the evidence's declared build inputs are pinned by digest;
  - a falsification control;
  - reproducibility;
  - tool qualification;
  - coverage.
- **A verdict decided by mandatory requirements only.** It is *rejected* if any mandatory requirement
  fails at its floor; otherwise *open* if any remains unresolved; otherwise *accepted*. A failure at
  the floor overrides a conflicting success at the floor. Evidence below the floor leaves a
  requirement unresolved. Optional requirements never block acceptance. To accept with a mandatory requirement still outstanding, the
  consumer must explicitly relax or drop it, which produces a new specification version. There are no
  conditions carried as debts.
- **Everything else moves to optional companion layers** that cite the core and never alter it.
  That covers the outer concerns listed under Scope, authority and delegation, and effects such as
  merging or publishing.
- **The documents will also be specified as an information protocol.** Each message declares what
  it binds and what it needs. The existing hash binding is the backbone of that encoding, and the
  encoding will be checked before any conformance is claimed.

Changes planned for the format class in the same line:

- **Trust numbers leave the class.** Calibrated `alpha`/`beta`/`lr` on an evidence record move to an
  optional trust extension. The class already refuses them without a calibration.
- **Closed grammars.** Every key a document carries is declared, either by the class or by a typed
  extension registry. Undeclared keys will be rejected consistently, including where 0.3.2 silently
  accepts them.
- **"Profile" splits into two named operations, at 0.4.0 at the earliest and possibly later.**
  Today the word covers both a sibling *meaning* (verification, conformance, …) and a narrowing
  *binding* (generic → code → one language). Each gets its own name and rules.

The release order of this restructure relative to 0.4.0–0.4.2 below is not fixed yet. The
additions below are planned to sit on the pure core. For example, consumer source policy is the
first instance of choosing a floor on the tool-qualification and independence axes.

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
