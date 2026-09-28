---
type: reference
digest: Profile: acceptance/verification — the meaning's own generic text (method/kind to epistemic_tier default ceiling, the profile-floor mechanism — both lifted from the Rust leaf, 2026-09-24) plus the provenance pointer to the shipped public document. Not a skeleton.
---

# Profile: `acceptance/verification`

`profile_id = "acceptance/verification"` · `profile_version = "0.2.0-draft"` (public)

This document is the shipped statement for the `acceptance/verification` meaning. It defines the
meaning-level vocabulary, required fields, constraints, and profile floors; the Rust leaf supplies
the binding-specific vocabulary. A manifest MUST declare its profile explicitly. A meaning id does
not implicitly select a binding: when binding-specific rules are required, the manifest declares
the applicable leaf id and the corresponding binding check is dispatched.

## 1. The leaf in use, and what its id would be

The protocol projection `code/rust.md` is this meaning projected onto the `code/rust` artifact
binding. That leaf's id is

```
acceptance/verification/code/rust
```

and a manifest that needs this binding declares
`[format].profile = "acceptance/verification/code/rust"`. A manifest declaring only
`acceptance/verification` receives the meaning-level checks; it does not acquire a Rust binding by
default. The Rust leaf is `code/rust.md` in this directory.

The binding half of `code/rust.md` (subject kinds, subject identity, recipe carriers, declared
input sets, constraints typing — its §1 rows) is what `../bindings/code/rust.md` will carry once
lifted — that lift did not run in this pass, see that document's own TODOs. The meaning half that
is SPECIFIC to the Rust binding (the requirement patterns, the mutation-control discipline, the
Rust-only evidence tokens) stays in the leaf; the part of the meaning half that was never actually
Rust-specific (the `method` ⇒ `epistemic_tier` default ceiling, the profile floor mechanism) moved
here, to §§2–3, in the same pass (R5).

## 2. `method`/`kind` ⇒ `epistemic_tier` — the meaning's default ceiling (R5 lift, 2026-09-24)

Lifted verbatim from `code/rust.md`'s former §2 (itself "verbatim from the public verification
profile," `spec/evidence-types.md`). These seven tokens are language-neutral: any binding of this
meaning admits them unchanged, with no per-binding narrowing.

| `epistemic_tier` | means | default tokens (every binding) |
|---|---|---|
| `T1` | deductive, kernel-checked derivation | `lean-theorem` |
| `T2` | mechanically sound semantic decision over the record's declared model and domain | *(none language-neutral — every T2 token today is a binding-specific prover; see the binding's own leaf, e.g. `code/rust.md` §2)* |
| `T3` | empirical-sampled | `unit-test`, `property-test`, `fuzz` |
| `T4` | mechanical-syntactic | `dep-audit` |
| `T5` | human-judgment | `human-review`, `llm-review` |

A binding leaf's own token table (e.g. `code/rust.md` §2) adds tokens under these SAME tier
definitions — never a new tier, never a raised ceiling for a token already listed here. A record
that declares `epistemic_tier` is held to whichever table's ceiling its `kind`/`method` token
falls under (a stronger declared tier is an error, a weaker one is honest); a record declaring
neither an `epistemic_tier` nor a recognised token, at this table or a binding's own, is
indeterminate and meets no floor.

## 3. The profile floor: `[requirement.evidence.profile."acceptance/verification"]` (R5 lift, 2026-09-24)

Lifted verbatim (mechanism, not values) from `code/rust.md`'s former §3. Nothing about the
mechanism below named Rust; a binding leaf shows it populated with that binding's own families
(e.g. `code/rust.md` §4's requirement-pattern table).

```toml
  [requirement.evidence.profile."acceptance/verification"]
  min_grade = "test-only"        # contract > probe > test-only > mechanical = not-covered
                                 #   > inspection-argued > (ungraded, unspecified, out-of-scope)
  min_band  = "A1"               # A0 < A1 < A2 < A3 < A3.5 < A4  (assurance-bands.md)
  families  = ["dynamic", "bmc", "kernel"]   # ≥ 1 passing record in one of these
  # kinds   = ["unit-test", "property-test"] # OPTIONAL: narrower than families
```

A claim meets the profile floor iff `rank(claim.grade) ≥ rank(min_grade)`,
`rank(claim.band) ≥ rank(min_band)`, and ≥ 1 passing evidence record has `family ∈ families` (and
`kind ∈ kinds` when given). **The grade ordering exists only here, as floors a consumer may set.**
The format deliberately does not order grades (a probe is not a weak contract; it is a different
claim) — this profile orders them for the single purpose of letting a contract say "at least this
deciding", and says so.

## 4. Test versus proof is weight, not a profile

Unit tests, property tests, fuzzing, bounded proofs and unbounded proofs are all evidence under
THIS profile. They differ in how much of the input space they cover, and the format already
carries that: `epistemic_tier` (T3 empirical-sampled for `unit-test`/`property-test`/`fuzz`, T2
for `kani-harness`, T1 for `lean-theorem`), `bounds` (bounded / unbounded), and the assurance
bands (A1 for a dynamic oracle, A3 for bmc, A4 for kernel). An exhaustive test over a finite type
covers the whole domain and earns proof-level weight by the same rule — the weight is a function
of coverage, not of the tool's name. So `unit-test` is a `method` token at a low band inside this
profile, and there is no `unit-testing` profile in the tree. The public README's `Profiles` table
must not list one.

## 5. The prospective mode is a mode of this profile

A check-manifest (a manifest whose claims are read off a spec before the implementation exists,
every claim `gap` / `A0` / unweighted — `spec/format.md` F3/F4) is this profile in
`[subject].mode = "prospective"`, not a different profile: the meaning of "accepted" is unchanged
(the implementation does what the spec says, evidenced by checks), only the subject's state is
declared. (The seeds that exercised this mode during development are private fixtures, not part
of this public repository.)

## What this document does not do

It adds no NEW vocabulary, field, constraint or example beyond what this document already
shipped, or what §§2–3 above carry over from the Rust leaf (`code/rust.md`) by a plain move (R5)
— the lifted text is unchanged in substance, only in which document states it. Any change to what
`acceptance/verification` MEANS is a change made directly to this document, its authoritative
statement.
