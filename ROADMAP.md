# Roadmap

Planned direction, not a commitment to scope or dates. For shipped changes, see
[CHANGELOG.md](CHANGELOG.md); for current limitations, see
[KNOWN-LIMITS.md](KNOWN-LIMITS.md). Acceptance concerns an artefact and its evidence;
transaction, payment and legal processes remain outside the core.

## Next

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
