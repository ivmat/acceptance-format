---
type: proposal
digest: Binding: code — SKELETON (empty; bindings deferred) (frontmatter added 2026-09-22 for the protocol gate)
---

# Binding: `code` — SKELETON (empty; bindings deferred)

binding path: `code` · parent: `generic` (the core) · children: `code/rust` · status: **candidate;
no leaf uses this node directly** (every code subject today is `code/rust`)

<!-- TODO(producer): structurally complete, semantically empty. Fill each slot from the first
     non-Rust code subject, or from lifting the language-neutral rows of ../verification/code/rust.md
     §1 (renamed from ../rust-code.md 2026-09-24, open question 2). -->

## What this binding is

Any source-controlled software artifact, independent of language and build system. It supplies the
identity, carriers and input-set rules every language instance inherits, so that `code/rust`,
and any later `code/<language>`, only narrow.

## Subject kinds

```toml
admits = ["rust-crate", "rust-workspace", "prospective-feature"]
identity = ["git-revision"]
```

<!-- TODO(producer): the `[subject].kind` tokens this node admits, declared via
     `[format].kind_registry` or as base tokens. Expected: a language-neutral `code-package` /
     `code-workspace` pair that `code/rust` narrows to `rust-crate` / `rust-workspace`; and
     `prospective-feature` (F1) when the subject is a proposed feature of a code artifact. -->

## Subject identity

<!-- TODO(producer): a VCS revision (`[subject].commit`, 40-hex git SHA today) plus `dirty`;
     `mode = "prospective"` with `read_at_commit` for a subject not yet built (F3). Whether the
     git shape is this node's narrowing of a class-level content locator or is class-level itself
     is open question B2. -->

## Recipe carriers

<!-- TODO(producer): the shape of a `self_verify.command` this node admits — a build/test/lint
     invocation whose `expect` string is checkable on a named stream (`expect_stream`); the
     positive-control rule for absence checks (grep-shaped recipes) by reference to
     `spec/format.md` (`self_verify`) and `spec/0.1-DRAFT.md` §4.
     Language-specific commands belong to the child. -->

## Declared input sets (change impact, protocol.md §8)

<!-- TODO(producer): the language-neutral default: the source tree, the test tree, the build
     manifest and lockfile, the toolchain pin, any build script. Children name the concrete
     files. -->

## `constraints` typing

<!-- TODO(producer): free strings with RECOMMENDED forms; the language-neutral ones
     (`license: <SPDX expr>`, `deps: none|allowlist <file>`) belong here, the rest to children. -->

## Admissibility check (item 8b, this node's contribution)

The module reads the declarations above and checks B14 admission and B1 git-revision identity. A retrospective subject must declare `dirty = false`; prospective read-locators retain the class rules. Recipe carriers, declared inputs and constraint additivity remain documented obligations, not mechanical checks (B17 residual). Language-neutral `code-package` / `code-workspace` tokens remain OPEN.

## Leaves that exist on this node

None directly. `code/rust` carries `acceptance/verification/code/rust` (`../verification/code/rust.md`).

## What this binding does not define

- No claim meaning, no evidence kind, no tier, no band — those are the meaning profile's.
- No language: a build system or a package format names a child node, never this one.

## Open questions

- open question B2 (identity shape) and open question B3 (kind registry as the declaration mechanism) — see README.
- Whether `prospective-feature` belongs to this node or to `generic` (it names a shape of subject,
  not a language — `spec/format.md` F1 says generic; it is listed here because every prospective
  subject so far is code).
