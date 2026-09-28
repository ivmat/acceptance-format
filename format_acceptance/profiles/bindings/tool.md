---
type: proposal
digest: Binding: tool — SKELETON (empty; bindings deferred) (frontmatter added 2026-09-22 for the protocol gate)
---

# Binding: `tool` — SKELETON (empty; bindings deferred)

binding path: `tool` · parent: `generic` (the core) · status: **candidate; wanted by an early
compositional-assumptions design** (a `kani-toolchain/acceptance.toml`; design history, not
published)

<!-- TODO(producer): structurally complete, semantically empty. Fill from the first toolchain
     record: Kani at a pinned release, honestly `probe` / T5. -->

## What this binding is

A released tool or toolchain as it is USED, not as it is built: a binary or installable at a
version, possibly with a build commit, possibly without one. The subject of the record is "this
tool at this pin," and the claims are about its behaviour (soundness for the properties it
decides, fidelity of its output) — under the verification meaning — or about its package
(under package-integrity). Taken as a sibling of `code` (open question B1): the identity is version + build,
and the source tree is usually not the producer's.

## Subject kinds

<!-- TODO(producer): base registry token `tool`; decide whether `toolchain` (a pinned set of tools:
     kani + cbmc + cadical + rustc) is a separate token or a `tool` with a components list. -->

## Subject identity

<!-- TODO(producer): `tool@<version>` plus build commit where obtainable (e.g. `kani@<40-hex sha>
     == 0.67.0`, naming a real pin); the weak-identity form `kani@<version> (commit unknown —
     <why>)` from `../verification/code/rust.md` trap 5a.4 (renamed from rust-code.md, open question 2);
     a components table for a toolchain. The class-level `commit` REQUIRED is wrong for a tool
     whose build commit is unknown — the same core/profile split concern as elsewhere. -->

## Recipe carriers

<!-- TODO(producer): the tool's own test suite invocation; a smoke run over a known fixture with a
     known outcome; a version probe (`kani --version`) as a precondition. -->

## Declared input sets (change impact)

<!-- TODO(producer): the pin itself — a version bump is the whole input set. -->

## `constraints` typing

<!-- TODO(producer): e.g. `platform: x86_64-unknown-linux-gnu`, `components: cbmc=6.8.0,…`. -->

## Admissibility check (item 8b, this node's contribution)

<!-- TODO(producer): the binding-side admissibility check the core CALLS (protocol.md §6.6 item 8,
     D1 amendment A1). Slots this node owns: identity shape (`tool@<version>` plus build commit
     where obtainable, or the weak-identity form `tool@<version> (commit unknown — <why>)` — never
     an invented sha); admitted `[subject].kind` set (`tool`, and whether `toolchain` is a
     separate token or a components list); the package-level constraints declared above
     (`platform:`, `components:`). There is no `dirty` slot on this node — a released tool has no
     working tree to be dirty; a components-table mismatch is this node's nearest analogue. The
     core supplies the entry point and orchestration (item 8a); the meaning supplies its own check
     (item 8b, meaning half); a leaf is evaluable only when both checks are available, else
     `indeterminate`. -->

## Leaves that exist on this node

None. The first wanted: `acceptance/verification/tool` carrying the claim "Kani@<pin> is a sound
BMC decision procedure over the domains this project's harnesses declare," graded `probe`, tier T5,
evidence = the tool's own suite and published soundness notes as `doc_ref` — the honest first cut
(design history, not published). That record is what a future discharge-reference mechanism
would point at.

## What this binding does not define

- No trust in the tool: a record on this node discloses what is known about the tool; it does not
  make the tool sound.
- No build provenance of the tool — that is `package-integrity` on this node.

## Open questions

- open question B1 — sibling of `code` or child of it.
- Whether the toolchain record is one manifest with a components table or one manifest per tool
  (Kani, CBMC, CaDiCaL, rustc, Lean, Aeneas — six candidate tools).
