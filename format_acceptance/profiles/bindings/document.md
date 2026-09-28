---
type: proposal
digest: Binding: document — SKELETON (empty; bindings deferred) (frontmatter added 2026-09-22 for the protocol gate)
---

# Binding: `document` — SKELETON (empty; bindings deferred)

binding path: `document` · parent: `generic` (the core) · status: **candidate; no leaf uses it**

<!-- TODO(producer): structurally complete, semantically empty. Fill from the first document
     subject — a spec, a design record, a report — held to any meaning. -->

## What this binding is

A written artifact: a specification, a design document, a report, a manual. It may live in a git
tree or outside one (an RFC on a review branch, a standard fetched by URL), so its identity is a
content digest first and a commit second. It is the binding under which a document is the SUBJECT;
a document that is the SPEC of some other subject is `[spec]`, not this.

## Subject kinds

<!-- TODO(producer): decide which of the base tokens `doc`, `spec` and `design` this binding admits; base recognition alone does not admit them to this binding.
     Decide whether `report` / `manual` need extensions or use `doc`. -->

## Subject identity

<!-- TODO(producer): the M11 `subject:` digest over the document's bytes as PRIMARY identity;
     `commit` + `dirty` when the document is in a git tree; the class-level
     `normative-reference:sha-512:` form (F2) when it is not. This is the node that makes the
     core/profile split concrete: a document subject may have no git commit at all, so a
     class-level `commit` REQUIRED is wrong for it. -->

## Recipe carriers

<!-- TODO(producer): what a `self_verify.command` over a document may be — a link checker, a
     structure/lint pass (heading rules, id uniqueness), a build (`mdbook build`), a grep with a
     positive control, a diff against a prior version. -->

## Declared input sets (change impact)

<!-- TODO(producer): the document's own files; its includes/assets; the tool that renders it. -->

## `constraints` typing

<!-- TODO(producer): e.g. `language: en`, `style: <profile>`, `format: markdown|pdf`. -->

## Admissibility check (item 8b, this node's contribution)

<!-- TODO(producer): the binding-side admissibility check the core CALLS (protocol.md §6.6 item 8,
     D1 amendment A1). Slots this node owns: identity shape (an M11 content digest as PRIMARY, a
     VCS commit plus `dirty` as a secondary form when the document lives in a git tree, or the
     class-level `normative-reference:sha-512:` form (F2) when it does not — open question B2 decides how
     much of this is class-level versus this node's narrowing); admitted `[subject].kind` set
     (which of `doc`, `spec`, `design`, or an extension token); the package-level constraints
     declared above. The core supplies the entry point and orchestration (item 8a); the meaning
     supplies its own check (item 8b, meaning half); a leaf is evaluable only when both checks are
     available, else `indeterminate`. -->

## Leaves that exist on this node

None. Candidates: `acceptance/conformance/document` (a spec against a house style or a standard's
profile), `acceptance/documentation/document` (a manual against the tool it documents — note the
subject/spec inversion), `acceptance/deliverable/document` (a report whose acceptance is discharged by referenced acceptance records).

## What this binding does not define

- No meaning: whether the document is true, complete, conformant or delivered is the profile's.
- No relation to a code artifact — that is the `documentation` meaning, not this binding.

## Open questions

- open question B2 (identity generalization) is decided BY this node in practice: if `document` needs a
  digest-first identity, the class must allow it.
- Whether a `document` subject that is also someone else's `[spec]` gets one record (as subject)
  or two.
