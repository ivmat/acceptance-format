---
type: proposal
digest: The class profile model — flat acceptance meanings, refine-only artifact bindings, leaf composition, profile identifiers, admission blocks and monotonicity, transcribed from the 2026-09-22 v2 design.
---

# Acceptance profiles and artifact bindings

**Class text LOCKED at 0.3.2 (2026-09-27).** This text is frozen: a change needs a new `[[lock]]` entry
(new version + reason) in `CLASS-LOCK.toml`, enforced by `gates/check_class_lock.py`. Locked is not
ratified: the status below stays CANDIDATE until the owning authority ratifies the class.

This CANDIDATE contract states the shared profile model and B12, B13, B14 and B17.
[core.md](core.md) defines the class rules; this file gives the profile model's shared form.

## The two axes and their leaves

A **profile** is an acceptance meaning: what acceptance says about the artifact.
Meanings MUST be flat siblings under the reserved class name `acceptance/core`;
they MUST NOT inherit from one another. The planned set is verification, conformance,
documentation, package-integrity and deliverable. A **binding** is the artifact-type
axis: `generic`, with `code`, `document`, `tool`, `estate-element` and `built-artifact`
siblings; any binding node MAY narrow further into its own instances (not named here —
those are binding-specific, not class vocabulary). Bindings MUST refine their parents. A
**leaf** is meaning × binding, materialised only when real work needs it — for example
`acceptance/conformance/code/rust` (illustrative; profile vocabulary) projects a meaning
onto a narrowed binding instance.

The built-artifact binding name and place are not yet confirmed: `built-artifact` directly under
`generic`. The node document is a skeleton; no leaf under it materialises until package-integrity
has a subject. `intent` is deferred. `unit-testing` and `obligation-discharge` are not
meanings.

## D1/A1 division of responsibilities

The following table is copied from [the binding-axis README](../profiles/bindings/README.md),
its D1/A1 table citing protocol §6.6 and amendments A2/A3. Its historical “once extracted;
until then verification-only” phrase records the scaffolding stage; B13 assigns 8a to
the core in the target contract below.

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

A meaning MAY use one ladder registered once by `ladder_id` in the class ladder
registry (`tools/profiles/__init__.py` `LADDERS`), whose token order is authoritative;
two meanings share a ladder iff they name the same registered id (B2). Every meaning
shares the class tier ordinal T1 > T2 > T3 > T4 > T5, strongest to weakest (B3).
The class keeps `self_verify` and `watched_fail` shapes when present and the control
binding invariant; verification owns per-grade recipe/bounds/positive-control
requirements and its control-kind vocabulary.

## Identifier grammar and prefix rule (B12)

`[format].profile` is REQUIRED at 0.3.0 and MUST be `acceptance/<meaning>[/<binding path>]`.
Omission is an ERROR naming the field — there is no compatibility default. `acceptance/core` is
reserved and MUST NOT be written into a manifest. A binding suffix MUST NOT stand alone
as a profile id.

A validator that knows the meaning but not the suffix MUST check at the known prefix
and report INDETERMINATE regardless of scoping flags, never declare the record invalid
merely for that suffix. Scoping flags MUST apply only to a KNOWN leaf id whose 8b
half is missing.
An unknown meaning prefix is likewise INDETERMINATE. The B11 ordering still makes
an already-detected class error FAIL.

Lexically: `segment := [a-z0-9][a-z0-9-]*`; the meaning MUST be exactly one segment; a binding path MUST be
one or more `/`-joined segments; empty segments, uppercase and escaping MUST be rejected.

## Binding declarations and admission (B1, B14, B17)

Every binding document MUST carry a machine-readable fenced `toml` block. The binding
module parses its `admits` list; the core loads the declarations for subset and identity
narrowing checks. The block format is:

```toml
admits = ["<admitted subject-kind token>"]
identity = ["<admitted registered locator-kind token>"]
```

The strings above are placeholders, not additional registry tokens. The base kind
registry is in [format.md](format.md). `identity` lists admitted kinds from B1's
`git-revision`, `content-digest`, and `components` registry. The block carries the
binding's admission, not a second subject-kind registry. A known base kind or declared
`[format].kind_registry` extension MUST still pass the selected binding's `admits` check.

For every parent/child pair, `admits(child) ⊆ admits(parent)` MUST hold. Admitted identity
kinds MUST narrow, never substitute. A meaning MUST NOT change subject identity (A3).
Recipe carriers, input sets and constraint forms MUST be additive; `/0` documents
this obligation but does NOT mechanically verify additivity. The core MUST check
admission subsets and identity narrowing over loaded documents with
`check_core.check_binding_chain`; `check_core.load_bindings` and `bindings/*.py`
own declaration loading and admission.

## 8a/8b composition (B13, B17)

The core MUST supply the package entry point, orchestration and class checks (8a).
`check_core.dispatch` MUST dispatch the meaning prefix to `tools/profiles/<meaning>.py`
and the binding path to its `tools/bindings/` module (8b). The binding module naming
includes `code.py` and `code_rust.py`.

A leaf MUST evaluate `check_meaning ∧ check_binding ∧ leaf delta`.
Each binding child MUST construct `check_child = check_parent ∧ delta`.
A meaning or binding check MAY only add errors: it MUST NOT remove or suppress a class error.
Class errors MUST be evaluated first. A leaf MAY add a cross-product constraint (6c),
but neither axis alone may weaken the other. A binding-declared over-claim guard (B9)
is inherited by every leaf under that binding's node.

A known leaf with a missing 8b half and no scoping flag MUST be INDETERMINATE.
Scoping flags MUST apply only to such known leaf ids; an unknown suffix MUST remain
INDETERMINATE regardless of flags. An explicit meaning-only (`--meaning-only`) or
binding-only evaluation MUST report its scope; it MUST NOT
imply the missing half ran. All available checks must pass to earn scoped PASS.
F4 still wins over a scoped PASS, printing the scope as a note.

## Ordered verdict composition (B11)

The table below is also held in [core.md](core.md) §4.

| condition | verdict | exit |
|---|---|---|
| any class (8a) error | FAIL | 1 |
| zero `[[claim]]`, or `claims_total ≠ len(claims)` | FAIL | 1 |
| root unresolvable / a dereferenced document missing, unreadable or unparsable (native evidence payloads follow B6) | INDETERMINATE | 2 |
| any claim in evaluation state `indeterminate` | INDETERMINATE | 2 |
| profile prefix unknown, or unknown suffix regardless of scoping flags | INDETERMINATE | 2 |
| known leaf id with a missing 8b half and no scoping flag | INDETERMINATE | 2 |
| any 8b error (meaning or binding) | FAIL | 1 |
| every claim `not-applicable` (retrospective) | INDETERMINATE ("nothing applicable") | 2 |
| `[subject].mode = "prospective"` (any claim counts — the subject is not certified) | PASS-PROSPECTIVE | 0 |
| zero `evidenced`/`partial` claims (F4) | PASS-PROSPECTIVE | 0 |
| scoping flag used for a known leaf id with a missing 8b half, all available checks pass | PASS-MEANING-ONLY / PASS-BINDING-ONLY | 0 |
| otherwise | PASS | 0 |

Across multiple files: FAIL > INDETERMINATE > any PASS. The prospective row is the ruled resolution of
B1's ceiling.
