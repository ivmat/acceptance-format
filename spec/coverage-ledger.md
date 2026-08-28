# The coverage-ledger facet (v0) — per-item status, strength, and a self-verify recipe

**Status: additive to `acceptance/0`, and superseded on optionality by `core.md`.** Every field
below is OPTIONAL **at the unweighted tier** — a wholly unweighted manifest that omits all of them is
exactly as valid as before, because the format promises nothing about it (W3).

**At the WEIGHTED tier these fields are mandatory, and `core.md` is normative where the two
files differ.** `[spec].axis` (§6/W2), `grade` (§1/W2), `[claim.self_verify]` with a nonempty
`command` and `expect` (§3), `bounds` on `contract`/`probe` (§5), `positive_control` on
`not-covered` (§4) and `clause_source` (W2) are all required of a claim that claims weight. This
paragraph exists because the sentence it replaces — *"every field below is OPTIONAL … nothing here
changes an existing rule"* — was written before the weight architecture and read, afterwards, as
permission to omit the entire anti-overclaim machinery.

## What this facet is for

The claim schema in `format.md` answers *"what does the producer assert, and what backs it?"*. It was
designed for a machine consumer. This facet answers a different question, for a human consumer:

> **Per item of the spec: is it covered? how strongly? and what do I run to check that myself?**

Same records, one more rendering — a table a customer reads instead of a proof. It has two uses, and
they are the same artifact at two times:

1. **Producer-side, while working** — a live scoreboard against the spec's own item list. Checkmarking
   is the work-tracking, and honesty is structural because the gaps are rows, not absences.
2. **Consumer-side, after** — the verification map: each item carries the command that re-derives it.

The worked subject shipped with this repo is `examples/rs-verified-der/ENVELOPE.md` (proof-heavy).
A second worked subject — tests and structure only, no proofs at all — exists and is referenced below
by its own clause ids (`KD-*`) but is not yet published; it is held for a later cut. Every field below
was forced by a named row in one of the two, because a field nobody's real data demanded is a field
that will be filled with fiction.

## The five added fields

### 1. `[spec].axis` — declare what the item list enumerates

```toml
[spec]
path    = "PROOF_MANIFEST.md"        # unchanged, still the nearest spec-shaped in-repo document
version = "2b9f3d55"
axis    = "X.690 (2021) DER encoding rules per type + framing; RFC 5280 profile rules"
external = ["ITU-T X.690 (2021)", "RFC 5280"]   # normative references not in the tree
```

**Forced by `DER-F-8`** (*the constructed form is illegal for primitive-only universal types*). That
rule is owned by **no module**, so a module-shaped axis cannot have a row for it — and it is the row a
consumer most needs, because it is the one thing the crate does not check. The axis a ledger is built
on is a *choice*, it changes which gaps are expressible, and an undeclared axis lets a producer pick
the one with the fewest gaps without ever saying so.

`external` exists because `path` presumes an in-repo document. der's real spec is an ITU-T standard
that is not, and cannot be, in the tree.

### 2. `grade` — the strength label, extended

`format.md`'s `grade` field gains three values. The **closed** set — nine tokens, normative in
`core.md` §1, which is where it is maintained — is:

```
weight-eligible:       contract | probe | test-only | mechanical | not-covered | out-of-scope
never weight-eligible: inspection-argued | unspecified | ungraded
```

This list is closed, and it is the same list in `format.md`, `core.md` §1,
`tools/check_acceptance.py` and `tools/check_ledger.py`. A token outside it is an error.

**Forced by `DER-X-CERT`.** `x509_certificate::parse_certificate_never_panics` is a genuine Kani proof
— strong by *species*, and its band says so. On the **rule** axis it is a `probe`: it proves
panic-freedom, which is not the encoding rule, over a 12-byte buffer against a ~170-byte real input.
Band and grade are answering different questions and neither substitutes for the other:

> **band = how good is the evidence?  ·  grade = does the evidence decide the item?**

A high band with a `probe` grade is the single most misreadable state in an acceptance manifest, and
before this field there was no way to write it down. `test-only` and `inspection-argued` were forced by
`KD-A-2` and `DER-X-BOUND` respectively.

**`grade` is not Kani's `#[kani::requires]`/`#[kani::ensures]` machinery.** `rs-verified-der` contains
zero function contracts and still has `contract`-grade rows; it is the review-lens sense — *proves the
documented rule, on the real shipped path, with an oracle not derived from the state under test*
(all three terms defined in `core.md` §0.5). Recording a Kani `proof_for_contract` harness that
proves a bounded fixture as `grade = "contract"` is exactly the overclaim this vocabulary exists to
catch.

### 3. `[claim.self_verify]` — the recipe, and it is allowed on gaps

> **Added 2026-08-25 (P2, owner-adopted): `watched_fail`.** A weighted recipe must carry a witness
> that it has been watched to fail — `self_verify.watched_fail`, an observed-red `control` on one of
> the claim's own evidence records, or (on `not-covered`) `positive_control`. In a rendered ledger
> the witness is **structured** and must name a recipe of its own row:
> `watched-fail(<recipe-ref>): <perturbed> -> <observed>`. `core.md` §4.1 is normative; a
> phrase is not a witness.

```toml
  [claim.self_verify]
  command = "cargo kani -Z stubbing --manifest-path der-verified/Cargo.toml --harness sequence::proofs::no_over_read"
  expect  = "VERIFICATION: SUCCESSFUL, and both kani::cover lines satisfied"
  precondition = "git diff 0e327b7..HEAD -- der-verified/src lean is empty"   # optional
  positive_control = "..."    # REQUIRED when grade = "not-covered" (see below)
```

**Forced by `DER-C-SEQ-2`.** The harness name alone is not a recipe: this harness reports
`VERIFICATION: SUCCESSFUL` *whether or not* its covers are satisfied, because the gate does not fail on
an unsatisfied cover. "What green means" is not derivable from "which harness"; it has to be written.

`expect` is required whenever `command` is present, for that reason.

**`self_verify` is permitted on `status = "gap"` and `status = "parked"` claims** — the one place this
facet touches an existing rule, and it is a widening, not a tightening. `format.md`'s design rule 1
makes gaps first-class but forbids them any evidence records, which left a gap row carrying nothing a
consumer could check. A recipe is not evidence: it is the command that shows the gap is *real*.

**Forced by `DER-P-5` and `KD-L-1`** — both are "specified, checked by nothing", and both are
falsifiable in one grep.

### 4. `positive_control` on `not-covered` rows

A `not-covered` row is usually verified by an **absence** — a grep that returns nothing. A zero from a
grep is a claim about your pattern, not about the code, so:

> **When `grade = "not-covered"`, `positive_control` is REQUIRED — unconditionally**: an input or
> target the same command *does* match.

*(`core.md` §4 is normative.)*

**Forced by `DER-P-5`** — `grep -rn 'basic_constraints' der-verified/src` returns empty, and would
return empty just as happily if the pattern were misspelled. Its control is the same grep against a
rule that *is* implemented.

### 5. `[coverage].denominator` — is the item list complete?

```toml
[coverage]
clauses_total = 21
claims_total  = 21
denominator   = "slice"       # complete | slice
slice_note    = "the size of this honest slice, not kani-driver's requirement count"
```

**Forced by `KD-N-3` / the kani slice's own §6.3.** `format.md` rule 1 makes silent omission detectable
*by declaring the total* — but that guarantee holds only if the total is the real one. Both worked
subjects fail that: X.690 has no enumerated clause count, and the kani slice deliberately covers 28 of
61 tests and a sampled subset of flag behaviours. Declaring `"slice"` keeps the omission-detection
guarantee honest by scoping it: **inside the ledger's own boundary, not across it.**

`"complete"` is the strong claim and stays available for a subject that can back it.

### 6. `clause_source` — where the item's text came from

```toml
[[claim]]
clause_source = "test-name"   # spec-document | external-standard | doc-comment | test-name | none
```

**Forced by `KD-A-5`.** Five of the kani slice's eleven tested rows have clauses read off the test's own
name. That is self-referential — the clause and its evidence are the same artifact, so the test can
never fail the requirement. Such a row documents existing behaviour; it does not check a requirement.

The value is recorded rather than forbidden, because forbidding it would just push producers to invent
prose (design-assessment finding B1's junk-id failure mode). A validator SHOULD warn on `"test-name"`, and MUST
NOT let it pass silently.

> **Superseded in part, 2026-08-25 (P1, owner-adopted).** `clause_source` is no longer optional on a
> claim that claims **weight**: it must be present, and `test-name`/`none` refuse weight (W2.3). It
> remains optional, and `test-name` remains merely warned, at the unweighted tier — which is the
> distinction that keeps the junk-id failure mode closed. In a rendered ledger the value is the
> **closed enum token**, not a citation and not free prose.

`"none"` is the correct state for a surface with no governing specification at all — **`unspecified` is
not the same as `not-covered`**, and the kani slice needs both (`KD-N-2` has no spec; `KD-L-1` has a
stable RFC and no test). Collapsing them hides the more actionable one.

## What the facet assumes — and the four places its first foreign subject broke the assumptions

The five fields above were forced by the two subjects this draft's author built. A third subject —
the first ledger built by **another author, against a different kind of spec** (a maintainer's review
rubric), held for a later publication — is where the facet's unstated assumptions became visible. All four are recorded
here, cited to the row that forced them, in the same discipline as the fields above — a limitation
nobody's real data hit is a limitation nobody needs to know about.

**1. Items are assumed to PARTITION the surface: one row, one item, one status.** Some of that
subject's rubric items are **predicates over every member of a second list** (a large fixed set of
production units), whose honest status is a fraction, and the facet has no cardinality
anywhere. `[coverage].denominator` cannot express it and `status = "partial"` reads the same at
1-of-N as at (N-1)-of-N. The subject worked around it with a hand-built item × unit cross-product
table and put the fraction in prose. **The
assumption was stated here as proposal P3; it was ADOPTED by owner ruling on 2026-08-25 and is now
`core.md` §7.2**, enforced by both checkers: a claim declares `item_kind = "predicate"` with a
required `over` and `covered = "N/M"`, and a weighted predicate row missing either is refused
weight. Detection is declarative — an *undeclared* predicate item is still invisible to the tools,
which §7.2 states rather than hides.

**2. A prerequisite is not an item, and has nowhere to live.** *"Does the module compile and verify
against baseline at all?"* is not one of the maintainer's asks — it is the precondition under which
any of them can be assessed, and if it is false every other row is unreadable. The declared axis has
no row for it. **This is legitimate and needs no new machinery: carry it as a row that declares
itself outside the axis** — a prerequisite row under its own heading, graded
`mechanical` because a tool decides it with no behavioural oracle. What the facet asks is that such
a row **say** it is a prerequisite, so a reader does not count it as coverage of the axis: an axis
of N asks with N+1 rows must explain the extra one.

**3. `status` and `grade` collide on unstarted work, and the informative pairing is easy to get
wrong.** They are different questions — *how far along is this* versus *does the evidence decide the
item* — and on work that has not started the answers pull apart. The pairing to write is
`status = "gap"` with the grade the evidence WOULD carry, and the pairing to avoid is a
grade that implies evidence exists. Worked example: a predicate row whose honest count was **a low
initial self-score, recorded honestly** — **`status`: gap · `grade`: `not-covered` · `weight`:
unweighted · `verify`: an absence check on the fixed-length constants, with a positive control
showing the same pattern matches known lines today.**
That row is fully honest and carries a command a reader can run *to confirm the gap is real* — which
is the whole reason §3 permits `self_verify` on gaps. Note what it does not do: it does not grade
evidence that does not exist. Several sibling rows in the same envelope do (`probe (bounded), same
shape`, at status *gap*), and that is proposal P5.

**4. A ledger has two homes, and an honest recipe is often not a publishable one.** A `self_verify`
recipe must name real commands on real paths to be worth anything, and those paths are frequently
not publishable — one subject's ledger could not be committed to its own subject repo for exactly
this reason and was left untracked. The facet does not yet distinguish the **internal ledger** from the
**redacted rendering that ships**, and a redaction that silently weakens a recipe is a rendering
that overclaims relative to its source. Named, not solved: today the only safe rule is that a
redacted rendering must say it is one.

## Rendering

The markdown ledger is a *rendering* of these records, not a second source of truth. Both worked
envelopes are hand-written today; when an emitter exists it should produce the table from the manifest,
not the reverse. Until then, an envelope must state that it is hand-built and mark which of its fields
are derived from gate-enforced sources and which are the author's judgement
(`examples/rs-verified-der/ENVELOPE.md` §8 is the reference shape).

## What this facet deliberately does not do

- **No numeric coverage score.** `18 of 21 covered` invites averaging a `contract` row with a `probe`
  row. `format.md` rule 3 (no trust numbers) applies here unchanged.
- **No automatic axis check.** Whether the declared axis actually enumerates the spec is not
  mechanically checkable — same honest limitation as `clauses_total` (design-assessment findings B1/B2).
- **No new evidence kinds.** Every recipe points at evidence that already has a registry entry.
