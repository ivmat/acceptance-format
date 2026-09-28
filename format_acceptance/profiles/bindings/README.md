# Artifact-type bindings — the second axis (skeletons, 2026-09-20)

**Status: SCAFFOLDING.** Most node documents here are still empty skeletons; `code/rust.md` is the
one node with real content, in use through a leaf. A binding is not a
profile. It is MOSTLY the meaning-independent half of what protocol.md §6.6 says a profile
supplies — the parts that depend on what kind of thing the artifact IS rather than on what
"accepted" means — but items 6 and 8 are SPLIT across both axes, not owned by this axis alone:

| §6.6 item | belongs to |
|---|---|
| 1. `method`/`kind` ⇒ `epistemic_tier` ceiling table | the LEAF (meaning × binding): the tools are the binding's, the tiers they earn are the meaning's — DERIVED, bounded by the meaning's evidence-family ceiling (amendment A2): `tier(token) ≤ ceiling(family(token))` |
| 2. floor-schema and floor rule | the meaning profile |
| 3. claim fields `demands.fields` may name | the meaning profile |
| 4. `captured_at_revision` alias and the subject identity | **the binding**, strictly (amendment A3 — a meaning may not override identity; a meaning needing a different identity is naming a different binding node) |
| 5. recipe carriers and declared input sets | **the binding** |
| 6a. narrowing of `[subject].kind` | **the binding** |
| 6b. `constraints` typing | **the binding** fixes the form; **the meaning** may require that a particular constraint be present |
| 6c. package-level constraints | **both axes contribute**; a leaf may add a cross-product constraint neither axis states alone |
| 7. floor comparator | the meaning profile |
| 8a. package validator: entry point, orchestration, class-tagged checks | **the core** (once extracted); until then verification-only |
| 8b. admissibility checks the core CALLS | **the meaning** supplies its own check, **the binding** supplies its own check; composed at the leaf. A leaf is evaluable iff both checks are available, else it fails closed to `indeterminate` |

So a binding document answers: which `[subject].kind` tokens, how the subject is identified
(commit, content digest, version + build), what a recipe may run, what inputs change-impact
watches, how `constraints` are typed, and (item 8b) its own contribution to the admissibility
check the core calls. It never says what a claim means or how strong evidence must be.

## The chain

```
generic                 the core: [subject].kind is an OPEN registry (spec/format.md §Schema, F1;
│                       public 0.2 adds ml-model · dataset · spec · design · agent-output)
├── code                any source-controlled software artifact              code.md
│   └── code/rust       a Cargo crate or workspace                            code/rust.md
│       └── (a crate)   a specific subject; never a document, only a manifest
├── document            a written artifact: doc · spec · design               document.md
├── tool                a released tool or toolchain, used rather than built  tool.md
├── estate-element      a subsystem / repo / service of this estate           estate-element.md
├── built-artifact      the delivered package itself, not its source tree     built-artifact.md
│                       (skeleton; empty until package-integrity has a subject, design §6.1)
└── data · model · agent-output   named by the public kind registry; no node document yet
```

Each node **inherits** the node above and only refines it: narrows the kind set, fixes the identity
shape, adds carriers. Nothing lower may weaken a rule set higher. A consumer that understands
`code` can read a `code/rust` subject at the code level.

## Naming

A binding's path is its position in the chain (`code`, `code/rust`, `document`). It appears only
as the suffix of a leaf profile id — `acceptance/<meaning>/<binding path>` — never on its own in
`[format].profile`.

## The one existing binding, unlifted

`../verification/code/rust.md` §1 (subject kinds `rust-crate | rust-workspace`; identity `commit`
40-hex with `dirty = false` for an acceptable package; `captured_at_commit` alias; the Cargo
recipe carriers; the `src/** tests/** … Cargo.lock rust-toolchain.toml build.rs` input set;
`constraints` forms `license:` `msrv:` `no_std:` `deps:` `unsafe:`) IS the `code/rust` binding,
written inside the verification leaf because there was only one meaning (renamed from
`../rust-code.md`, open question 2; a later lift moved that leaf's language-neutral §2/§3 rows up
to `../verification/PROFILE.md` in the same pass, but did not touch this §1 binding half).
`code/rust.md` here is the skeleton it lifts into; the lift is a future move, not done by this
scaffolding.

## Open questions

- open question B1 — is `tool` a sibling of `code` (a released binary is identified by version + build, not by
  a source tree) or a child of it (a tool is built from code)? Sibling is taken here.
- open question B2 — subject identity at the generic level: keep `commit` git-shaped or generalize to a
  content locator that `code` narrows to a git SHA and `document` to an M11 digest? The bindings
  below assume the generalization; the class has not ruled.
- open question B3 — does the kind registry (`[format].kind_registry`, F1) become the mechanism by which a
  binding declares its kinds, so that a leaf's kind set is computable from its binding path?
