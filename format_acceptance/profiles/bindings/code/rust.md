---
type: proposal
digest: Binding: code/rust — SKELETON (the lift target for ../../verification/code/rust.md §1) (frontmatter added 2026-09-22 for the protocol gate)
---

# Binding: `code/rust` — SKELETON (the lift target for `../../verification/code/rust.md` §1)

binding path: `code/rust` · parent: `code` · status: **in use through one leaf**
(`acceptance/verification/code/rust` = `../../verification/code/rust.md`), **not yet lifted**

<!-- TODO(producer): this skeleton exists so the binding half of verification/code/rust.md has a home when the
     Step 5 extraction lifts it. Nothing is copied here now; every slot points at the row it will
     hold. Do the lift as one move, with verification/code/rust.md keeping only its meaning half. -->

## What this binding is

A Cargo crate or workspace: Rust source under Cargo, identified by a git commit, exercised by Cargo
subcommands and the Rust verification toolchain. It narrows `code`; it adds nothing a non-Rust code
subject would need.

## Subject kinds

```toml
admits = ["rust-crate", "rust-workspace"]
identity = ["git-revision"]
required_build_inputs = ["Cargo.lock", "rust-toolchain.toml"]
```

<!-- TODO(producer): lift verification/code/rust.md §1 row "[subject].kind": `rust-crate` | `rust-workspace`. -->

`required_build_inputs` is core.md B20's generic declaration mechanism (same machine-readable
block as `admits`/`identity`): once a weighted claim under this binding declares any
`build_inputs` entry at all, the union of its declared paths MUST also include `Cargo.lock`
and `rust-toolchain.toml` — the pinned dependency graph and the pinned toolchain a build
actually used. A weighted claim declaring no `build_inputs` is unaffected (B20's nonempty
guard). Checked by `bindings/code_rust.py`, not by core, which names no file itself.

## Subject identity

<!-- TODO(producer): lift verification/code/rust.md §1 rows "subject identity" (`[subject].commit` 40-hex git
     sha; `dirty` must be false for a package a decision may accept) and "captured_at_revision
     alias" (`captured_at_commit` on evidence records). -->

## Recipe carriers

<!-- TODO(producer): lift verification/code/rust.md §1 row "recipe carriers": `cargo test …`, `cargo clippy --
     -D warnings`, `cargo doc --no-deps`, `cargo kani --harness …`, `cargo miri test`, `grep -rn …
     src/` with a `positive_control`. Note trap 5a.3 (grep collides with `#![forbid(unsafe_code)]`)
     travels with the carrier, not with the meaning. -->

## Declared input sets (change impact)

<!-- TODO(producer): lift verification/code/rust.md §1 row "change-impact declared input set": `src/**`,
     `tests/**`, `benches/**`, `Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml`, `build.rs`, plus
     the record's `tool` and `semantics` strings; a `kani-harness` record also declares the harness
     source file — the last clause is meaning-specific and may stay in the leaf. -->

## `constraints` typing

<!-- TODO(producer): lift verification/code/rust.md §1 row "constraints typing": `license:`, `msrv:`, `no_std:`,
     `deps:`, `unsafe:` recommended forms. -->

## Tool identity

<!-- TODO(producer): lift trap 5a.4 — `kani@<version> (commit unknown — <why>)` when commit
     granularity is unobtainable; a weak identity, never an invented sha. -->

core.md B20's `toolchain` list gives this trap a checked shape instead of prose-only advice: one
entry per component named in the free-text `tool` string, each with `name`, optional `version`,
and at least one of `commit`/`digest` — never an invented sha. For a component where BOTH
remain unobtainable (the trap's actual case), that component simply carries no typed entry and
stays disclosed only in the free-text `tool` string with the trap's own sentinel prose; B20 does
not require every `tool`-string component to have a typed counterpart, only that any entry
present names a real commit or digest.

## Admissibility check (item 8b, this node's contribution)

The child evaluates `code.check` and its own delta. B17 asserts at import that admission and identity narrow the parent. A2 bounds each declared record tier by both the selected meaning’s `FAMILIES` and the Rust kind table: Kani T2, Lean T1, reserved Flux T2, unit/property/fuzz/miri T3, lint/semver/dep-audit T4, human/LLM review T5 (T1 is strongest). B9/C8 rejects a weighted claim with at least one Kani record when every Kani record declares `cover_only = true`. Zero Kani records do not trigger C8. At conformance 0.1 the legacy `cover_only` ref list is read with a deprecation warning; it is rejected at 0.2. Harness names are never interpreted. Recipe carriers, inputs and constraint additivity remain the B17 documented residual.

## Leaves on this node

| leaf id | document | status |
|---|---|---|
| `acceptance/verification/code/rust` | `../../verification/code/rust.md` | in use (protocol example `rust-delivery/`) |
| `acceptance/documentation/code/rust` | — | candidate (a verified DER-parsing crate's rustdoc is the nearest subject) |
| `acceptance/package-integrity/code/rust` | — | candidate |
| `acceptance/deliverable/code/rust` | — | candidate (a crate whose acceptance is discharged by referenced acceptance records) |
| `acceptance/conformance/code/rust` | `../../conformance/code/rust.md` | in use — real plain-leaf PASS (DER against X.690/RFC 5280/keyformats; the 0.2 lowering pass, profile_version 0.2.0) |

## What this binding does not define

The generic `method` ⇒ `epistemic_tier` default ceiling and the profile-floor mechanism are the
verification MEANING's own text, at `../../verification/PROFILE.md` §§2–3 (lifted off the leaf
because neither named Rust). What DOES stay leaf-side, still the meaning on
this binding, not this binding's own: the leaf's own Rust-only evidence tokens
(`../../verification/code/rust.md` §2), the requirement patterns (§4), the mutation-control
discipline (§5), consumer re-execution (§6) and the phases (§9).

## Open questions

- Whether `cargo doc --no-deps` is a carrier of this binding (any meaning may run it) or of the
  verification leaf only (verification/code/rust.md §4 places "docs build clean" there). Binding, in this
  skeleton's reading; the leaf decides what the result may evidence.
