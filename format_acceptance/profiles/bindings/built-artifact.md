---
type: proposal
digest: Binding: built-artifact — SKELETON (empty; bindings deferred)
---

# Binding: `built-artifact` — SKELETON (empty; bindings deferred)

binding path: `built-artifact` · parent: `generic` (the core) · status: **candidate; name and
place confirmed (design history, not published), subject to change at the lock review; no
leaf uses it yet**

<!-- TODO(producer): structurally complete, semantically empty. Fill from the first delivered
     package — a `.crate` file, a release tarball, a signed binary — held to the package-integrity
     meaning (`profiles/package-integrity/PROFILE.md` "Subject"). -->

## What this binding is

The DELIVERED PACKAGE itself — a built object such as a `.crate` file, a release tarball or a
signed binary — as distinct from the source tree it was built from. `code` and `code/rust`
identify a git tree; this binding identifies what that tree produced. A subject on this node has
no working tree and no `dirty` flag; its identity is the built object's own content and the
provenance that connects it back to the source commit and build environment that produced it.

## Subject kinds

<!-- TODO(producer): no base token exists yet. Declare via `[format].kind_registry` (F1):
     candidates `crate-package`, `release-tarball`, `signed-binary`, or one generic
     `built-artifact` token narrowed by `constraints`. Decide one against the first real
     subject. -->

## Subject identity

<!-- TODO(producer): a content digest over the built object's own bytes as PRIMARY identity
     (the object a consumer actually receives), plus a provenance link back to the source
     `git-revision` identity (commit + `dirty`) and the build environment that produced it —
     modeled on SLSA Provenance / in-toto Statement subject descriptors (design history, not
     published). This is a second, additional identity
     axis alongside source identity, not a replacement for it. -->

## Recipe carriers

<!-- TODO(producer): a reproducible-build recipe that rebuilds the object from the declared
     source and toolchain and compares digests; an SBOM generation and match check; a signature
     verification step. -->

## Declared input sets (change impact)

<!-- TODO(producer): the source commit that produced the object, the exact toolchain and
     build-input identity (B20), and the packaging manifest (`Cargo.toml`, a release spec). A
     change to any of these possibly-invalidates every acceptance record naming this object. -->

## `constraints` typing

<!-- TODO(producer): e.g. `format: crate|tarball|binary`, `signed: true|false`,
     `reproducible: true|false`. -->

## Admissibility check (item 8b, this node's contribution)

<!-- TODO(producer): the binding-side admissibility check the core CALLS (protocol.md §6.6 item 8,
     D1 amendment A1). Slots this node owns: identity shape (a content digest over the built
     object as PRIMARY, plus the provenance link to source identity); admitted
     `[subject].kind` set (declared via `[format].kind_registry`, F1 — no base token exists yet);
     the package-level constraints declared above (`format:`, `signed:`, `reproducible:`). This
     node's nearest analogue to `dirty` is "the object's digest does not match a rebuild from the
     declared source and toolchain." The core supplies the entry point and orchestration
     (item 8a); the meaning supplies its own check (item 8b, meaning half); a leaf is evaluable
     only when both checks are available, else `indeterminate`. -->

## Leaves that exist on this node

None. The first candidate is `acceptance/package-integrity/built-artifact`, re-parented from the
placeholder rows `package-integrity/PROFILE.md` currently carries under `code/rust` and `tool`
once this node has a real subject.

## What this binding does not define

- No trust in the built object beyond what its provenance and reproduction evidence show: a
  record on this node discloses what is known about the object; it does not make the object
  correct — that is verification, on the source binding.
- No packaging vocabulary (SBOM format, signature scheme, license scan) — that is the
  package-integrity meaning's own closed vocabulary, not this binding.

## Open questions

- An earlier design decision confirms the name and place (design history, not published); the
  lock review may still change it.
- Whether `built-artifact` needs its own narrower children (e.g. `built-artifact/crate`) the way
  `code` narrows to `code/rust`, once a second artifact kind is real.
- Package-integrity is a stretch item for 0.3 (design history, not published); this node may stay an
  empty skeleton past the 0.3 lock.
