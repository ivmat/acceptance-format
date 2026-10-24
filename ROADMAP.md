# Roadmap

*Planned, not final. The next steps below state direction, not a commitment to exact scope
or dates.*

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

The 0.4.0 release removed these outer concerns: commercial role wording, conditions framed
as debts (the verdict stays; conditions are now due-dated items), the work-contract and
transaction notes, `legal_ref`, the `legal` domain, money examples, and `pay` among effects.
Authority, delegation and effect gating remain in this release and are planned to move to
optional companion layers.

Two kinds of mention are **not** outer concerns, and they stay:
- **Requirements about the artefact itself**, such as the licence it must carry, are ordinary
  specification content.
- **This repository's own terms**: its licence files and contributor notes, and the copyright of
  the standards a conformance profile checks against. These concern the repository and its inputs,
  not the protocol.

## 0.4.0 — this release

- Removed the outer concerns listed above.
- Renamed the first acceptance document from contract to specification.
- Introduced `acceptance-protocol/1`. The
  [migration tool](protocol_acceptance/tools/acceptance_migrate.py) updates specifications
  and packages. Decisions are never rewritten; the consumer re-issues them. The current
  checker refuses 0.3 protocol documents; use tag v0.3.2 to check those unchanged.
- Added checked stacking for workspace libraries. A package declares its dependencies from
  `Cargo.lock`, and the checker verifies that the declaration matches. A chain requirement
  can require dependencies to be disclosed (C0) or accepted by a named acceptor (C2).
  The consumer configures a directory of trusted decisions. Checks recurse through child
  acceptances and check them again when a decision is used to authorize an effect.
- Added the [paint-stack example](protocol_acceptance/examples/paint-stack/README.md).
  Its stack label covers runtime libraries. Toolchain and platform relations are trusted as
  the base and are not checked. Acceptance adds no combined assurance across the stack;
  if any dependency in the closure comes from crates.io or git, the whole stack check is
  undecided (indeterminate), never accepted.

## Next (planned, not final)

### Any artefact, not only code (0.5, in development)

The core rules will be separated from the mechanisms a binding supplies to identify, inspect and
traverse a delivered subject. Those mechanisms cover identity, a check of the presented content,
members and inputs, inventories, freshness, changes of state and chain locations. Every 0.4.0 rule
is being classified as already stated, a proposed extension or not yet supported by the current
tool. An unchanged 0.4.0 tool already accepts a non-code artefact end to end when it is identified
by a content digest.

### The pure acceptance core

- **The verdict without conditions.** Mandatory requirements decide the verdict: rejected if
  any fails at its floor, open if any remains unresolved, accepted otherwise. A failure at
  the floor overrides a conflicting success. Optional requirements never block acceptance.
  To accept with a mandatory requirement outstanding, the consumer must explicitly relax or
  drop it in a new specification version.
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
- **Closed grammars.** Every key is declared by the class or a typed extension registry;
  undeclared keys are rejected consistently.
- **Role-bound identity.** Each document names its author as producer or consumer, so
  independence checks can use that identity.
- **Information-protocol encoding.** Each message declares what it binds and what it needs.
  The encoding is checked before any conformance claim.
- **Trust numbers out of the class.** Calibrated `alpha`/`beta`/`lr` move to an optional trust
  extension. The class already refuses them without a calibration.
- **The "profile" split.** Sibling meanings (verification, conformance, …) and narrowing
  bindings (generic → code → one language) get separate names and rules.

### More languages

The code binding today is Rust. Planned next: bindings for **C**, **Python** and **Go**. Each comes with
its own rules for evidence (the tools and test kinds of that language) and a lockfile reader, so that
stacking works in that ecosystem the way it does for Cargo workspaces today.

### Consumer source policy

**Consumer source policy.** A consumer will be able to declare, per specification, which verification
tools and which reviewer identities it accepts. Evidence produced by a tool or reviewer the
consumer has not listed will not count toward that consumer's acceptance decision, even when the
evidence is otherwise well-formed. A single requirement will be able to narrow that list further,
never widen it.

### Stacking for published packages

- crates.io and git dependencies with delivered identities, including the `.crate` digest;
- imported decisions with a consumer-approved claim mapping;
- package integrity;
- configuration receipts from the actual build, including features and target platform;
- output on standard carriers: in-toto, CycloneDX and cargo-vet;
- companion assessment of a library's own acceptance file.

### Function-level tracing

Extends stacking from whole-dependency acceptance to tracing which specific accepted claims back a
particular function call across a chain of libraries, so a consumer can check not just "is this
dependency accepted" but "is the exact code path I call accepted."

### Signing

Signing for exchanges across organisations.

### Authority, delegation and effect gating

These mechanisms move to optional companion layers that cite the core without altering it.

## Open to other kinds of artefact

The format and the protocol are not specific to code. A specification, its evidence and a decision can
be about any artefact, and the format already includes skeleton binding documents for documents, tools
and built artifacts. Further kinds would be new bindings. The core permits them, although today's
dependency and freshness checks still assume source code identified by a git commit. Examples:

- built artifacts and verification tools: accepting the exact bytes shipped (archives, binaries, images),
  or a specific tool version for a stated use;
- documents and specifications: a standard or design document accepted against requirements, clause by
  clause;
- datasets, machine-learning models and configuration: evaluation claims and policy checks, each with a
  control showing the check can fail.

The artefact-neutral core is planned for 0.5; see Next. The specific bindings listed above — built
artefacts and tools, documents, and datasets, models and configuration — remain unplanned and will
be developed if people who need them take the format up.

## Also planned

See [KNOWN-LIMITS.md](KNOWN-LIMITS.md) for the complete, current list of deferred mechanisms.
