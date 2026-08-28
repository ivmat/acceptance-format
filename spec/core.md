# Acceptance format — core specification

**Status: `0.1.0-draft`, living, deliberately not frozen** (draft opened 2026-08-25). This file
defines the two-tier weight architecture, with the **WEIGHTED** tier as its focus — the claim
classes the format certifies as fully expressible and decidable. None of it is sealed.

## Overview — orientation only; every rule below is stated in its own section

**Normative for the two-tier weight architecture, with weighted certification as its focus:**
which claim classes the format certifies as fully expressible and mechanically decidable, and what
a claim must carry to earn that certification — plus the rules that bind the UNWEIGHTED tier and
every rendering of it: W1 (weight is explicit and absent by default, so silence is unweighted), W3
(an unweighted claim carries no further obligation), and W4/W5 (a rendering marks each row's tier
and states its tier counts, unweighted rows included). Companions: `format.md` (manifest tables and fields), `evidence-types.md` (evidence records),
`assurance-bands.md` (band floors), `coverage-ledger.md` (the rendered-ledger facet).

**Map.** §0 the two tiers · §0.5 terms used normatively · §0.6 `illustrative` · §1 the closed
`grade` vocabulary · §2 band vs grade · §3 `self_verify` · §4–§4.2 controls, the watched-fail
witness, recipe references · §5 `bounds` · §6 the axis · §7–§7.4 one row one claim and status
coherence · §8–§8.3 the weight rules W1–W5, `--execute`, `weight-pending`, the tri-state contract.

**Read first:** §0, then §0.5, then §1; a producer writing a manifest then goes to §8's W1–W5,
where weight is granted or refused.

**What "enforced" means here, said once so no sentence below has to be read generously.**
`tools/check_acceptance.py` (manifests) and `tools/check_ledger.py` (rendered ledgers) enforce the
**structural** obligations of every rule below: that the required fields are present, drawn from
the closed vocabularies, mutually coherent, and bound to the row they belong to. They enforce
**nothing about truth**. That the named command is the right one for the item, that the watched
failure really was watched, that the cited scope section says what the row claims, that the declared
axis actually enumerates the spec — none of these are decidable and none are checked. Every
"enforced" in this document means the first thing. Where a rule has a residual that only a reviewer
can close, the section says so in its own words; this paragraph is the general case, not a
substitute for those.

**Nothing is excluded from the format.** Claim classes not yet certified are listed in
`CLAIM-CLASSES-AWAITING-WEIGHT.md`; they are admissible today as **unweighted** claims, and each
records what it needs to earn weight. That boundary is living too. Read §0 first.

## The freeze criterion (owner, 2026-08-25) — conjunctive

> **0.1 freezes only when BOTH hold:**
> **(a) the format is CLEAN** — no ambiguity, no overclaim path, every strong grade carries a
> deciding recipe; **AND**
> **(b) it has DEMONSTRATED usefulness in real FV work** — it changed decisions, found defects, or
> made coverage legible in live verification practice, evidenced in the usefulness ledger below and
> including a vision-at-scale demonstration held for a later publication.
>
> **Neither alone freezes it.** A clean format nobody's verification work is better for is a
> well-specified ornament. A useful format with an overclaim path is worse than none, because its
> output gets cited.

**The criterion applies to the WEIGHTED core only** (§0). Weight certification is the thing that must
be clean: no ambiguity, no overclaim path, every weighted claim carrying a deciding recipe. The
**unweighted tier is free by construction** and gates nothing — it promises nothing, so there is
nothing to be clean about and nothing that could overclaim. Freezing therefore means *"this set of
claim classes is certified weightable, permanently"*; classes not yet certified keep arriving
unweighted in the meantime, with no pressure on the freeze.

Why this bar and not a date: the owner's ruling is that a format becomes freeze-ready by showing its
usefulness in the formal-verification area with a long-term vision of the whole, not by looking
finished. Freezing early converts today's guesses into tomorrow's citations. **Better to know the bar
now than freeze early.**

**(a) CLEAN — current state: NOT met, and as of the 2026-08-25 rigor audit the reasons are specific
rather than atmospheric.** Every weight rule below that is a **structural** rule — a required field,
a closed vocabulary, a binding, a coherence constraint — is mechanically enforced in both
representations and in both directions (a fixture that must pass and a fixture that must fail,
watched red before the fix landed).

**That claim is itself checked now, and it was false when first written.** "Enforced in both
representations" was maintained by hand — the same rule written twice, once per checker — and the
copies drifted: `out-of-scope` required a locator in a manifest and accepted any nonempty cell in a
rendered ledger, so a row a human reads was granted weight that its manifest twin was refused. Two
things changed. The cross-representation rules now live in **one module** both checkers import
(`tools/acceptance_grammar.py`), so a rule cannot have two implementations to drift between. And
`tools/check_parity_selftest.py` states a battery of claims in **both** forms and asserts the two
verdicts match, with a watched-break proof that reproduces the original divergence; it is step 6 of
`gates/run_all.sh`. Parity is a gate now, not a promise.

Three rules below are deliberately **not** mechanical and say so
where they are stated: §3 rule 5 (give the most *specific* command — a reviewer sees it at a glance),
§6 axis adequacy (not decidable), and §7.2 detection of an *undeclared* predicate item. Both worked
subjects were re-validated against the mechanical rules, with rows corrected rather than rules
softened (see the review note in the envelope shipped here; the other subjects are held for a later
publication). What the audit found anyway:

- **Fixed, in this document and the two checkers:** nine terms used normatively and never defined
  (§0.5), §2 contradicting W3 about whether `grade` is mandatory, §4 contradicting §1 about whether
  a `not-covered` row always owes a positive control, `bounds` mandatory since 0.1 with neither of
  its values defined (§5), two spec files printing a six-token subset of the nine-token closed
  vocabulary, a `**CONTRACT**` row able to exempt itself from every weighted obligation with a stray
  word in its prose, and seven graded rows of one envelope silently unchecked by the row checker.
- **P1 and P2 ADOPTED by owner ruling the same night, and enforced** (W2 conditions 3 and 5): a
  weighted claim must record `clause_source`, and a weighted recipe must carry a witness that it has
  been watched to fail (§4.1). These were the two overclaim paths that decided (a); they are closed
  as rules. **Current state, updated 2026-08-27: the `weight-pending` backlog in THIS tree is zero**
  — the one envelope shipped here (`rs-verified-der`) was remediated 2026-08-26, and `--strict-weight`
  is now the gate's default (`gates/run_all.sh`). The remediation backlog this adoption created
  against the *other* envelopes P1/P2 were originally counted against is real, but those envelopes
  are held out-of-tree (not yet published here), so it is not a backlog this repo's own gate can
  show as zero-or-not; it is tracked where those envelopes live.
- **Adopted and enforced since that list was written, in both checkers:** predicate items (P3, §7.2),
  `blocked` as a status with a required `blocked_by` (P4, §7.3), the row checker is in the gate
  suite (P6, `gates/run_all.sh` step 4), W5's counts are compared against the computed ones
  including `weight-pending` (P7, W5), and `--execute` runs each recipe (P9, §8.2). **Still open as
  proposals:** grades attached to evidence that does not exist yet (P5 — **DEFERRED** by owner
  ruling, §7.4) and `resolved_by` (P8 — approved after revision, *not implemented*).
- **Still unestablished, unchanged:** that the rules stay unambiguous on subjects unlike these, and
  that hand-grading survives scale — an open question this draft states rather than hides.

**P1 and P2 were the two that decided (a), and they are now rules.** Both were paths by which a
producer following this document literally obtained the format's vouching for a claim nothing could
falsify — the one failure the design invariant ranks above every other. **(a) is not met by adopting
them**: a rule with a backlog of rows that do not meet it is a rule on paper. (a) is met when the
`weight-pending` count reaches zero and `--strict-weight` is the default. **Updated 2026-08-27: both
now hold in this tree** — `gates/run_all.sh` runs `--strict-weight` against every shipped manifest
and envelope, and the computed `weight-pending` count against them is zero. This closes (a) for the
claim classes and subjects shipped in THIS repo; it does not, by itself, establish that the rules
hold at breadth (see the counter-ledger, below) or against envelopes held out-of-tree.

**(b) USEFUL — accumulating, see the ledger.** Four counted entries below, all against the one subject
shipped in this repo; further entries exist against subjects not yet published and will be appended
as those subjects ship.

## Usefulness ledger

The evidence for (b). Entries are appended as they occur, each with a pointer a third party can check.
An entry is included only if it names what would have happened *without* the format.

| # | what the format did | evidence | strength |
|---|---|---|---|
| **U1** | **Surfaced two X.690 rules that no module owned — and they were implemented and proven the same day.** `DER-F-8` (constructed form illegal for primitive-only UNIVERSAL types) and `DER-F-9` (the reserved EOC identifier `00 00`) existed as rows *only* because the ledger's axis is encoding rules rather than source modules. Both were disclosed in `PROOF_MANIFEST.md` §6.3 as prose about an absence; neither was a row anywhere, and neither was being worked. | `rs-verified-der` `3725018` *"identifier_form: decide the two X.690 identifier rules no layer decided"*, folded at `bffab69`, full gate green at `130de97`: **203/203** harnesses (was 191/191). The new `identifier_form.rs` ships **twelve** harnesses, **four stated over the complete input domain** (symbolic `u32` tag number × 4 classes × both forms) rather than a bounded buffer. | **Strong.** Verifiable by sha. A gap went from prose to proof in one day, and the module's own docstring adopts the ledger's framing (*"`Ok` means well-formed TLV, not valid DER"*). |
| **U1b** | **Fixed a documentation defect in a public crate.** The ledger's finding E-1 — three module docstrings (`bit_string.rs`, `utc_time.rs`, `generalized_time.rs`) asserting that tag identity and primitive form were *"enforced (and proven) upstream by `crate::tag`/`crate::tlv`"* when neither module has so much as a `Constructed` rejection. A second-model review then sharpened the finding itself: the **definite**-length half IS enforced upstream, only the **primitive** and **tag-identity** halves are not. | `rs-verified-der` docstrings at `130de97` now read *"**The identifier is not enforced upstream.** Of the tag identity and the primitive/definite form, only the **definite**-length half is enforced by `crate::tlv`… The **primitive**-form half and…"* — the corrected scoping, shipped. | **Strong.** A safety-relevant doc defect in a published crate, found by building the ledger, scoped correctly by review, fixed same-day. |
| **U2** | **Made an inverted strength gradient legible.** "191 of 191 verified" reads as uniform. On the rule axis the framing/codec layers are `contract`/unbounded while the X.509 layer — where a hostile certificate actually lands — had **no conformance `contract` row at all**, three harnesses whose covers are unsatisfied, and panic-freedom proved at ≤12 bytes against a ~170-byte certificate. | `examples/rs-verified-der/ENVELOPE.md` §5.3, §6.4, §6.5 | **Medium.** Every fact was already disclosed somewhere across ~160 KB of prose; the format made the *shape* visible in one table. No decision is yet known to have changed because of it. |
| **U3** | **Found a green-gate hole.** `check.sh` prints `PASS` after `check_lean.sh` SKIPs and exits 0 with no Lean toolchain — so `PASS` alone witnesses no unbounded row. Found only because the format forces a per-row *"what does green mean"*. | `lean/check_lean.sh:23-25`; envelope §4 warning | **Medium.** A real consumer-protection defect in the gate's reading, not in the proofs. |

Further usefulness entries exist against subjects not yet published (an ordering constraint caught
before it became a live bug; a green-and-numerous run log turned into an honest zero-of-N before it
reached a reviewer). They are held back with those subjects and will be appended here once published,
rather than cited without a checkable pointer.

**Counter-ledger (kept honestly).** (a) CLEAN is NOT met at breadth, and there is direct evidence.
Two envelopes, written independently against the same spec within hours of the vocabulary being
closed, each invented grade tokens outside the closed set: five tokens across the two, all rejected
by `tools/check_ledger.py`. This is the single most useful negative result the format has produced
about *itself*, and it cuts two ways:

- the closed set may be **genuinely incomplete** — a PR-review ask and a rubric sprint are not a
  verified crate, and "doc-only" or "receipt-backed" may be real classes the vocabulary lacks;
- or adopters need the checker **in their loop**, because a vocabulary nobody validates against is a
  suggestion.

Either way the (a) criterion is unmet until it is resolved, and no freeze can happen before then. The
drift was invisible until a second and third subject existed — which is precisely why the owner's
"useful AND clean, demonstrated, not asserted" bar is the right one.

Draft means: rules may be tightened, loosened, or withdrawn. A manifest valid today may need edits
tomorrow, and that is the point of not freezing.

---

## 0. The architecture: one format, two tiers of promise

**Owner ruling, 2026-08-25** (this supersedes the earlier core/excluded split):

> *"have full format in mind and allow ANY claim. but we do not give it 'weight' until we can be sure
> format can express it fully. so we allow even fluffy input but make it clear format does not promise
> anything on those (i.e. same level as 'it was reviewed')."*

So there is **one format with a full expressive surface**. No claim class is excluded; free-text and
fluffy claims are admissible. What varies is not admissibility but **weight** — whether the *format
itself* stands behind the claim.

| tier | what the FORMAT promises | machinery |
|---|---|---|
| **WEIGHTED** | the format certifies this claim-class as **fully expressible and decidable**: the claim means one thing, and one named command decides it | the entire anti-overclaim machinery is **mandatory** — §1–§7 below |
| **UNWEIGHTED** | **nothing.** Verbatim semantics: *admitted as an assertion; the format promises nothing about this claim — **same evidentiary level as "it was reviewed"*** | none required. Write what you like |

Three consequences, and they are the whole design:

1. **The validator's job flips.** It does not reject weak claims. It **refuses weight** to any claim
   whose class lacks certified deciding machinery. Refusal is not rejection — the claim stays in the
   document, at the tier that promises nothing.
2. **Unweighted is free by construction**, because it promises nothing. That is what lets the format
   have a full surface without acquiring an overclaim path: an assertion cannot overclaim if the
   format has publicly declined to vouch for it.
3. **Weight defaults to absent.** A claim that does not explicitly claim weight, and earn it, is
   unweighted. The format never vouches by silence.

**The rendering rule is what the tier distinction depends on** (§8): a document that displays weighted and unweighted rows so
they look alike has destroyed the distinction, and is invalid. The consumer must never be able to
mistake an assertion for a format-backed claim. This is the one place the format polices presentation,
because presentation is where the promise is actually delivered.

### Why this resolves the tension it replaces

The previous cut (freeze the clean parts, exclude the fluffy ones) forced a bad choice on anything the
format strained to express: exclude it, and the document is silent about a real part of the subject;
include it, and the format vouches for something it cannot decide. Weight dissolves it — **anything
that strains drops to unweighted rather than blocking**. The der envelope's `inspection-argued` rows
are the natural instance: *"real-size panic-freedom rests on an un-machine-checked compositional
argument"* is a true, important, unweightable claim. It belongs in the document. It must never be
read as format-backed.

---

## 0.5 Terms used normatively

Every term below appears in a MUST or a REQUIRED somewhere in this document. Each was previously
left to the reader, and a term that decides whether a row carries weight cannot be left to the
reader: the producer will read it the flattering way and nobody will read it the other way.

| term | definition |
|---|---|
| **claim** / **row** | the unit the format certifies: one *item*, one *grade*, one tier. A `[[claim]]` in a manifest and a row in a rendered ledger are the same thing in two representations (§7: one row, one claim). |
| **item** | the thing a claim is about — a behaviour, a rule, a requirement, a review ask. The **axis** (§6) is the statement of what the item list enumerates; the items are its members. |
| **clause** | the *text* the item is held to, and `clause_source` records where that text came from. Item and clause are not the same field: the item is what you checked, the clause is who says it should hold. `[coverage].clauses_total` counts the axis; `[coverage].claims_total` counts the rows. |
| **weighted core** | the set of claim classes the format certifies as fully expressible and decidable (§0). "The core is clean" is a statement about this set only; the unweighted tier promises nothing and so has nothing to be clean about. |
| **deciding recipe** | a `self_verify` block whose `command` a third party can run and whose `expect` states what the run must show for the claim to stand. A recipe that cannot distinguish the claim being true from the claim being false is not a deciding recipe, whatever it names (§3 rule 2, §4). |
| **absence check** | a `self_verify.command` whose passing condition is that it produces **no** output or **no** match — a grep with no hits, a count that must reach zero, a search returning empty. Absence checks are the case §4 governs, because their result is a claim about the pattern rather than about the code. |
| **symbolic domain** | inputs the checker reasons over as *sets* rather than enumerating as values — a symbolic variable a model checker quantifies, not a fixture, a loop over literals, or a sampled generator. `contract` requires one; tests witness points, so a test is never `contract` (§1). |
| **shipped path** | the code a user of the artifact actually executes. Evidence that drives a copy, a re-implementation, a test-only harness body, or a stubbed substitute is not evidence about the shipped path, and grading it `contract` is the overclaim §1 exists to catch. |
| **independent oracle** | the thing the evidence compares the result *against*, derived from the specification rather than from the state under test. A postcondition that re-computes its expectation using the same code it is checking is not independent: it cannot fail. This is the review-lens sense of `contract` — *decides the documented item, on the real shipped path, against an oracle not derived from the state under test* — stated here rather than by reference, so the definition travels with the spec. |
| **bounded** / **unbounded** | see §5, where the pair is defined and the case that fits neither name is worked through. |
| **`epistemic_tier`** | the WIRE KEY for the closed, core, artifact-agnostic epistemic class (`T1`–`T5`) of the METHOD that produced one evidence record (`evidence-types.md`). **This key is never spelled bare `tier`** — this document already uses "tier" for the WEIGHTED/UNWEIGHTED weight-tier (§0's table), and one key does not carry two meanings (the same "one token, one meaning" law behind §1's closed grade vocabulary). Prose MAY shorten `epistemic_tier` to "tier (T1–T5)" after first naming the wire key in a section; the schema NEVER does. |
| **method** | the profile-defined, open token naming the concrete technique an evidence record used (`kani-harness`, `lean-theorem`, …). Distinct from `kind` (the registry column, now a hint) and from `family` (unchanged, `evidence-types.md`). |
| **`[[claim.assumes]]`** | the typed upgrade of the free-text "assumptions" element (`format.md`): one record per assumption a claim's evidence depends on, with a `void_if` trigger. Governed by the **void-not-discount invariant** (`format.md`): a struck `void_if` VOIDS the claim, it never merely discounts it — stated now, enforced by no engine in this revision. |

---

## 0.6 `illustrative` — teaching example vs certificate (F2)

The usefulness ledger above and the "held for a later publication" subjects this document
mentions throughout are exactly the two validation contexts a red-team finding (F2) found
conflated: a manifest teaching the format's shape (an intentionally partial or fixture-only
example) versus one certifying a real subject.

```toml
[format]
illustrative = false   # OPTIONAL, defaults to false. true = this manifest is a teaching example,
                        # not a certificate.
```

A manifest carries `illustrative = true` or it is a certificate — there is no third state.

**Validator-obligation: the gate runs strict on non-illustrative manifests.** The enforcement gate
(`gates/run_all.sh`) runs **strict** — record existence checked; content-hash checked once M11
(`format.md`) lands — on **everything not marked `illustrative`**. An `illustrative` manifest
stays **shape-only**: closed vocabularies and required-field presence are still checked (nothing
here waives §1's grade vocabulary or §3's `self_verify` shape), but binding (`format.md` rule 4a),
watched-fail witnesses (§4.1), and tier/grade coherence (§2) are not enforced against it. Any
rendering or gate output for an `illustrative` manifest MUST label it as such in its `PASS`/`valid`
line — an unlabeled illustrative pass reads exactly like a certified one, which is the confusion F2
exists to close.

---

## The design invariant (governs the WEIGHTED tier)

> **The format's job is to make overclaim STRUCTURALLY hard.**
> A claim without a deciding recipe cannot carry weight.

Not "discouraged", not "flagged in review" — **not weightable**. If a producer cannot supply the one
command that would falsify a label, the validator refuses weight. The producer may still make the
claim; it is admitted unweighted, where it will be read as an assertion.

This is the hardest failure mode the format exists to prevent, and it is worth stating why it is
ranked above every other concern: a *missing* claim is visible (the ledger has a row for it, and
`coverage.claims_total` makes omission detectable). A *wrong* claim is invisible — it looks exactly
like a right one. Ambiguity is the same failure wearing a different coat: a label that can be read two
ways will be read the flattering way by the producer and the unflattering way by nobody.

### The design evidence (why this is mandatory and not advisory)

The author hand-built a 45-row envelope for `rs-verified-der` — a repo with unusually disciplined
documentation, having just read the PROBE-vs-CONTRACT lens, working from committed
evidence. **Seven rows were still labelled `CONTRACT` on evidence that was fixture-shaped or
monomorphic**, and three self-verify recipes could not verify what they promised. A second-model
review caught all of them in one pass, cheaply, *because every row named a command it could
run*.

Two conclusions, both written into the rules below:

1. **The labels are where a hand-built envelope goes wrong** — not the facts. Every count in that
   envelope was right. The strength cells were what drifted.
2. **The recipe is what makes the label falsifiable.** A row with a command is checkable by a
   reviewer, a customer, or a script in one step. A row without one is an opinion.

So the recipe is not a nicety attached to strong rows. **It is the thing that entitles a row to be
strong.**

---

## 1. Grade — the closed vocabulary

**A WEIGHTED claim/row MUST carry exactly one `grade` token from this closed set. An unweighted
one may carry none** — W3 imposes no obligations on the tier that promises nothing, and §2 says
the same in more words.

Where a `grade` **is** present — at either tier — exactly one token from the closed set is the rule.
Compound cells ("mechanical, gate-enforced"), two grades in one cell, and free-text substitutes
("derived") are **errors**, not style issues — each is a place where two readers take away two
different claims.

**The two representations differ here, and the difference is deliberate.** A manifest may omit
`grade` on an unweighted claim: the field is simply absent and nothing reads it. A **rendered row
sitting in a table that has a grade column** may not leave that cell empty, because a blank cell in
a graded table cannot be told from a forgotten one — the token for *"the producer declines to
grade"* is `ungraded`, and writing it is one word. `tools/check_ledger.py` enforces the second and
`tools/check_acceptance.py` the first; neither has ever required a grade on an unweighted manifest
claim.

| token | means | weight-eligible? | required to carry weight |
|---|---|---|---|
| `contract` | the documented item is decided on the **shipped** path, over a **symbolic** domain, with an oracle **not derived from the state under test** | **yes** | `self_verify` + `bounds` + `watched_fail` |
| `probe` | bounded, monomorphic, or fixture-shaped evidence. **Also applies to** a safety proof (e.g. panic-freedom) when it is offered as evidence for a *different* item that it does not decide | **yes** | `self_verify` + `bounds` + `watched_fail` |
| `test-only` | `#[test]`/doc-test at named concrete inputs. Witnesses points, not sets | **yes** | `self_verify` + `watched_fail` |
| `mechanical` | a tool decides it with no behavioural oracle (formatter, lint, advisory DB, a count-derivation gate) | **yes** | `self_verify` + `watched_fail` |
| `not-covered` | the item is **in scope** for the declared axis and nothing checks it | **yes** | `self_verify` + `positive_control` (which **is** its `watched_fail`, §4.1) |
| `out-of-scope` | the producer declares the item deliberately not implemented or not claimed | **yes**, narrowly — weight attaches to *"the producer declared this, here"*, never to any property of the code | `scope_ref` |
| `inspection-argued` | a documented human argument; there is nothing to run | **no** — no deciding machinery exists, by definition | — (unweighted). `doc_ref` is RECOMMENDED, not required: the cited argument is all a reader has, but W3 puts no obligation on an unweighted claim |
| `unspecified` | there is **no governing spec text** for this surface at all | **no** — "no document governs this" is not mechanically decidable | — (unweighted). `clause_source = "none"` RECOMMENDED, not required (W3) |
| `ungraded` | the producer declines to grade | **no** | — (unweighted) |

**`contract`'s requirement list is completed by §2.** A `contract` grade additionally requires the
§2 `epistemic_tier`/grade coherence rule to hold: at least one passing `T1`/`T2` evidence record
whose declared scope covers the claim's domain. §1 states the recipe/bounds/watched-fail
obligations; §2 states the tier/coherence obligation that decides whether `contract` specifically
(as opposed to `probe`) is earned.

**Grade attaches to the (item, evidence) pair, not to the evidence alone** (review finding P1,
folded 2026-08-25). **Prior art, and this rule is not ours**: Assurance 2.0 (Bloomfield & Rushby,
SRI) has carried the same distinction since at least 2021, as the split between a claim that is
*evidentially measured* (*"the tests achieve MC/DC coverage"*) and one that is *evidentially
useful* (*"there is no unreachable code"*) — the gap between what evidence measures and what it is
claimed to show, explicitly modelled. This draft re-derived it independently from the der
envelope's mis-graded rows; that makes it convergent, not novel, and the citation is owed wherever
the rule is stated. The same Kani harness can be `contract` for one item and `probe` for another:
a symbolic panic-freedom proof *is* a contract when the item **is** "this function does not
panic", and *is* a probe when it is offered for "this function accepts exactly the RFC 5280
structures", which it does not decide. Before this correction the vocabulary demoted every
panic-freedom proof regardless of what it was claimed for — an underclaim, which is the same
defect as an overclaim pointed the other way. `rs-verified-der`'s `DER-S-2` was mis-graded exactly
this way and is corrected.

The three non-eligible grades are not second-class citizens; they are honest labels for claims the
format cannot decide, and they appear in both worked envelopes. What they may never do is carry
weight.

**`not-covered` ≠ `out-of-scope` ≠ `unspecified`**, and 0.1 refuses to let them collapse:
*in scope and unchecked* / *deliberately excluded* / *nothing to be in scope of*. They demand
different actions from a consumer (worry / accept / go read the code), so they are different tokens.

**`grade` is not Kani's `#[kani::requires]`/`#[kani::ensures]` machinery.** `rs-verified-der` contains
**zero** function contracts and still has `contract`-grade rows. This is the review-lens sense —
*decides the documented item, on the real shipped path, with an independent oracle* — and all three
of those terms are defined in §0.5 rather than by reference to a document outside this repo. A
`proof_for_contract` harness that proves a bounded
fixture is `probe`, and calling it `contract` because of the attribute name is precisely the
overclaim this vocabulary exists to catch.

## 2. Band and grade are both mandatory on a weighted claim, and they are not the same axis

> **band = how good is the evidence?  ·  grade = does the evidence decide the item?**

**A WEIGHTED claim MUST carry both**, and neither may be inferred from the other. 0.1 tightens
`grade` from optional to **required at the weighted tier** — the single largest break from the
pre-freeze schema. An unweighted claim carries neither obligation, because W3 imposes none: it may
omit `grade` entirely, and a `grade`-less claim is admitted, unweighted, exactly as W1 says.

**Re-scope, stated explicitly: this MUST binds the MANIFEST representation** — `[[claim]]` in a
`.toml` file, checked by `tools/check_acceptance.py`, where `band` is a schema field. **The
legacy rendering — the Markdown ledger form this repo's worked envelopes use (e.g.
`examples/rs-verified-der/ENVELOPE.md`), checked by `tools/check_ledger.py` — carries no `band`
column in its row schema and is exempt from this MUST.** It is a retired-class carrier for that
reason: its row shape was fixed before this document's `band` obligation existed for it to bind,
and this is named as a reservation rather than silently tolerated as a gap `tools/check_ledger.py`
happens not to check. This exemption is for the shape that already shipped without a `band`
column, not a standing license — a rendering format that adds one is bound by this MUST exactly
as the manifest representation is.

The state this exists to make writable is **high band + `probe` grade**: a genuine, well-controlled,
A2/A3-worthy Kani proof that nevertheless does not decide the item on the axis being claimed.
`rs-verified-der`'s `x509_certificate::parse_certificate_never_panics` is exactly that — a real proof,
of panic-freedom, at ≤12 bytes, against a ~170-byte real certificate. Before this pairing existed
there was no way to write that down, and the only available renderings were both lies.

**Band never asserts item coverage on its own.** A reader may not conclude from `band = "A3"` that the
item is covered; only `grade` says that.

**The `epistemic_tier`/grade coherence rule.** `grade = "contract"` on a weighted claim REQUIRES
at least one **passing** evidence record (`result = "pass"`) whose `epistemic_tier` (`evidence-
types.md`) is `T1` or `T2`, **and** whose declared scope (`bounds`, §5) covers the claim's declared
domain. This is the mechanical half of the review-lens PROBE-vs-CONTRACT distinction, stated as a
checkable structural rule rather than left to the reviewer alone:

- the family/tier fragment (≥1 passing T1/T2 record exists) is a plain existence check over the
  claim's evidence array;
- the scope-coverage conjunct is checked against §5's bounds grammar — **abstaining, not passing,
  where the comparison cannot be made.** An evidence record with no parseable `bounds` text does
  not satisfy this conjunct, under the same "phrase presence is not a witness" law §4.1 already
  states.

**What the validator decides about scope coverage in THIS revision, stated as a tri-state**
(tightened 2026-08-28; the first cut of this section named a `check_scope` routine that never
existed, and the validator carried a comment asserting the conjunct was "already covered by the
claim's own `bounds` field" — which is false: requiring the CLAIM to declare boundedness says
nothing about what the EVIDENCE ranged over, and a weighted `contract` reading `bounds =
"unbounded: all byte strings"` against evidence bounded to one byte passed `--strict-weight`):

1. **REFUSED, decidably** — the claim's bounds token is `unbounded` and every qualifying (passing,
   T1/T2) evidence record's token is `bounded`. §5 defines those two tokens as *the entire input
   domain* and *a proper subset* of it, so containment fails on the tokens alone and no free text
   can repair it. This is a detected contradiction, not a missing field, so it is a hard error —
   not a §8.1 `weight-pending` refusal.
2. **SATISFIED, decidably** — some qualifying record's token is `unbounded`. Evidence over the
   whole domain covers every claim domain inside it.
3. **UNDECIDABLE, and said out loud** — everything else: `bounded` against `bounded` (comparing two
   free-text tails, which §5 already assigns to the reviewer: "whether the stated limit is the real
   one is reviewer work"), and qualifying records that declare no `bounds` at all (`lean-theorem`
   requires `axioms` and `semantics`, not `bounds`). These draw a **transitional warning naming the
   case as undecidable in this revision** — neither a refusal nor a confirmation. Comparable
   structured claim/evidence domains, which is the machinery that would actually decide
   containment, are a **freeze obligation** (`maintainers/VALIDATOR-TODO.md`); a checker that
   inferred containment from prose would be inventing the answer, which is worse than naming the
   gap. Case 3 is where the transitional WARN sits rather than the refusal case 1's wording would
   otherwise suggest, and that softening is recorded here rather than left to be discovered in the
   code.

`epistemic_tier` does not subsume `grade` and `grade` does not retire: a T2 harness over a
monomorphic instance of a generic item is a `probe` at `T2`; the same tool over the item's real
domain is a `contract` at `T2`. `epistemic_tier` alone cannot tell those apart — only the
scope-coverage conjunct can, which is why both halves of this rule are required, not either alone.

**This resolves the sampled-eval grade-vocabulary gap without a new grade token.** A 20k-sample
held-out ML eval is `epistemic_tier = T3` + `grade = probe` — the strength lives on
`epistemic_tier`, the adequacy call stays on `grade`, and no token needs inventing for "sampled
but substantial."

## 3. `self_verify` — mandatory wherever a row claims something is checked

```toml
[claim.self_verify]
command = "cargo kani -Z stubbing --manifest-path der-verified/Cargo.toml --harness sequence::proofs::no_over_read"
expect  = "VERIFICATION:- SUCCESSFUL, and both kani::cover lines satisfied"
precondition     = "git diff 0e327b7..HEAD -- der-verified/src lean is empty"   # optional
positive_control = "..."     # MANDATORY for grade = "not-covered"
```

Rules, all validator-enforced:

1. **`self_verify` is REQUIRED when `grade` ∈ {`contract`, `probe`, `test-only`, `mechanical`,
   `not-covered`}** — every grade that asserts a check was, or was not, performed.
2. **`expect` is REQUIRED whenever `command` is present, and must be non-empty.** "Which harness" does
   not determine "what green means": `sequence::proofs::no_over_read` reports
   `VERIFICATION:- SUCCESSFUL` whether or not its covers are satisfied, because the gate does not fail
   on an unsatisfied cover. A row that names a command but not its expected output has not told the
   consumer how to fail it.
3. **`self_verify` IS permitted on `status = "gap"`/`"parked"`.** A recipe carries no evidentiary
   weight on its own: it is the command that shows the gap is real. (This is 0.1's one widening of a pre-freeze rule, and the
   reason `not-covered` can be mandatory-recipe at all.)
4. `inspection-argued` takes `doc_ref` instead — there is deliberately nothing to run, and pretending
   otherwise would be the same overclaim in reverse. Because that grade is never weight-eligible, this
   is a **recommendation** (validator warning), not a gate: W3 imposes no obligations on the
   unweighted tier, and a rule that can never fire is worse than an honest warning.
5. Producers **SHOULD** give the most specific command that decides the claim: a single named harness
   beats a whole suite. `command = "cargo test"` on every row is technically compliant and useless —
   the recipe's value is that it decides *this* row (review finding, folded). Not mechanically enforced;
   a reviewer can see it at a glance, which is the point of the recipe being visible at all.

## 4. `positive_control` — mandatory on every absence check

> **When `grade = "not-covered"` on a WEIGHTED claim, `positive_control` is REQUIRED —
> unconditionally within that scope.**
>
> *Scoped 2026-08-26.* The sentence read "REQUIRED — unconditionally" with no tier
> qualifier, which contradicted W3 ("unweighted claims carry no obligations") and
> overstated both checkers, neither of which has ever demanded it of an unweighted row.
> The "unconditionally" still does real work and still means what §4 says below: within
> the weighted tier there is no absence-check precondition the producer gets to interpret.

*Corrected 2026-08-25.* This rule previously read *"when `grade = "not-covered"` **and the command
is an absence check**"*, which disagreed with the §1 table (which requires it of every `not-covered`
row) and with `tools/check_acceptance.py` (which has always required it unconditionally). The
qualifier also handed the producer the trigger: "absence check" was undefined until §0.5, so a
producer could decide their command was not one and owe nothing. A rule whose precondition the
obligated party gets to interpret is not a rule. The definition stays in §0.5 because it is still
the *reason* for the requirement; it is no longer the *condition* on it.

A grep that returns nothing is a claim about your **pattern**, not about the code. This is not
theoretical: in this envelope's first draft, `grep -rn 'basic_constraints' der-verified/src` and
`grep -rn 'constructed' tag.rs tlv.rs` were both offered as absence proofs and **both returned
matches** — one from comments and test fixtures, one from the parsed field itself. Neither would have
verified anything, and both looked authoritative.

The control is an input or target the *same* command demonstrably matches. If you cannot name one,
your pattern is not a measurement.

**The control must NAME an input or target — a statement, not a token.** `positive_control = "x"`
is refused in both representations: it satisfies "nonempty" and identifies nothing a reader could
try. This floor is specific to this field because §4's requirement is that you *name the input the
same command demonstrably matches*; `over` and `blocked_by` (§7.2, §7.3) carry **no** such floor,
because a list name or a tool identifier is legitimately one token (`module X`, `kani`). Stated
here so the code and this document agree field by field.

**A structured control is validated whole, not by its opening.** `positive-control(` on its own
declares nothing, and a valid control elsewhere on the row does not excuse it: a row that states
something unparseable has stated it.

**In a rendered ledger the control is DECLARED**, in one of two syntaxes:

```
positive-control(<recipe-ref>): <input tried> -> <what it matched>, observed <YYYY-MM-DD>
positive-control: <the input or target the same command demonstrably matches>
```

*Corrected 2026-08-25, eighth round.* The row checker had been scanning for the bare substring
"control" anywhere in the row, so *"no control exists for it"* — a sentence stating that the
control does **not** exist — satisfied the obligation, and so did the word "uncontrolled". **A
citation no longer substitutes either**: pointing at a section used to downgrade a missing control
to a warning, which made a reference admission-affecting rather than diagnostic. A citation may
accompany the declaration; it cannot replace it.

## 4.1 `watched_fail` — a weighted recipe must have been seen to fail

> **A recipe nobody has watched fail is not a deciding recipe.** Every weighted claim whose grade
> asserts a check was performed (`contract`, `probe`, `test-only`, `mechanical`, `not-covered`)
> MUST carry a witness that the named command *can* report the claim false.

**Owner ruling, 2026-08-25, adopting proposal P2 in its strong reading:** the format's vouching means
**demonstrated able to fail**, not *decidable in principle*. A weighted row is the format telling a
consumer "this was decided". A command that would pass with the implementation deleted decided
nothing, and the format must not stand behind it.

The format already holds this idea elsewhere; §4.1 only extends it here, consistently.
§4 says it for absence checks — *"a grep that returns nothing is a claim about your pattern"*.
`assurance-bands.md` says it for bands — *"a check nobody watched fail is untested"*, and gates
A2/A3/A4 on an observed-red control. Weight was the axis that did not say it, and P2 is the
demonstration of what that cost: a mutation that deleted a sort step **broke no test**, and a row
citing those tests would have been weighted with the rules as they stood (recorded as control `M2`
in a second subject's envelope, §4, held for a later publication).

**The witness — any ONE of three, deliberately reusing what exists rather than inventing a fourth:**

1. **`[claim.self_verify.watched_fail]`** — a **table**, naming *which command* was watched,
   *what was perturbed*, *what was observed*, and *when*. All four are REQUIRED:

   ```toml
   [claim.self_verify]
   command = "cargo test -p kani-driver --test parallel"
   expect  = "87 passed; 0 failed"

     [claim.self_verify.watched_fail]
     of_command = "cargo test -p kani-driver --test parallel"   # MUST equal `command` above
                                                                # (whitespace-normalized; quoting
                                                                #  stays literal)
     perturbed  = "reverted the AtomicBool latch to an error-channel abort"
     observed   = "4 of 6 permutation tests fail, including a_genuine_error_is_not_displaced_by_a_concurrent_abort"
     date       = "2026-08-24"
   ```

   The table is the TOML twin of the Markdown form: `of_command` is the `<recipe-ref>` binding
   (§4.1's `of_claim` rule — a control over a *different* check witnesses nothing about this one),
   `perturbed`/`observed` are the required transition, and `date` is *when*, because a recipe
   watched to fail a year ago may not discriminate today.

   **What is checked, and what is not.** Checked: the table is complete, `of_command` equals this
   claim's own `command`, `date` is an ISO date, and `perturbed`/`observed` are statements rather
   than single tokens. **Not checked, and not checkable:** that the perturbation was really made,
   that the observation really happened, or that either is described honestly. A producer who
   invents a plausible sentence defeats this field completely. Structure raises the cost of the lie
   and moves the residual to review; it does not remove it, and the field must not be read as
   though it did.

2. **An observed-red `control` block on an evidence record of this claim** — `control.expectation =
   "red"`, `control.observed = "red"`, and `control.of_claim` equal to this claim's id
   (`evidence-types.md`). A claim that already earns a control-gated band already satisfies this;
   nothing is asked twice.

3. **`self_verify.positive_control`** on a `not-covered` claim, **and on no other grade**. In a
   rendering **either declared syntax** satisfies this — the parenthesised witness form and the
   plain `positive-control: <input>` form. An absence check whose control demonstrably matches *is*
   the witness that the command can come back non-empty. §4 and §4.1 are the same requirement
   meeting at the one grade where the "failure" is a hit rather than a miss. On a `contract` row it
   witnesses nothing: showing that a command *can* match some input says nothing about whether the
   proof would notice a broken implementation.

**What does NOT satisfy it**, and each of these is a real attempt someone will make: that the
harness is green; that the tool is sound; that the code is obviously right; a control on a
*different* claim (`assurance-bands.md` rule 6 — *"one fixture does not lift a module of claims"*);
or a `planted-twin`, which shows the pipeline can reject at all and not that this oracle catches a
mutation of this item.

**A note on `mechanical`.** A formatter or count-derivation gate has no behavioural oracle to mutate,
and its witness is a **seeded-bad fixture the gate must catch** — the `planted-twin` shape, which
never lifts a *band* but is exactly the right witness for the *weight* question here, because the
claim being weighted is the gate's own claim. Record it in `watched_fail`.

### In a rendered ledger, the witness is structured — a phrase is not a witness

A Markdown row states its witness in one of three forms, and `tools/check_ledger.py` parses them:

```
watched-fail(<recipe-ref>): <what was perturbed> -> <what was observed>, observed <YYYY-MM-DD>
mutation-control(<recipe-ref>): ...
positive-control(<recipe-ref>): ...      # satisfies this rule ONLY on `not-covered`
```

**The separator after `(<recipe-ref>)` is any punctuation separator** — colon, dash, equals,
comma or semicolon, with optional whitespace around it, and **exactly those five**: parentheses and
brackets are grouping, not separators, and the implementation accepted them until 2026-08-25's
eighth round — a set wider than the documented one, which is this document overclaiming by
omission. Whitespace alone is not a separator, and
neither is nothing: both would let the witness run into the surrounding prose. The colon is the
form used throughout this document.

**The Markdown witness carries the same floors as the TOML table**: the perturbation and the
observation must each be a statement rather than a single token, and the body must carry an ISO
date. The date annotation is removed before the statement floor is applied, in both
representations — otherwise `-> y, observed 2026-08-25` passes on the strength of its own
bookkeeping.

Four rules, each closing a hole that was open until 2026-08-25 — and the fourth exists because the
first three, shipped that morning, were got round by lunchtime:

1. **`<recipe-ref>` MUST name a recipe that appears in this row's own verify cell.** This is the
   Markdown form of `control.of_claim`: a control over a *different* check witnesses nothing about
   this one.
2. **The body MUST state a transition** — a perturbation *and* an observation. `mutation control`
   as a bare phrase says a category of thing exists somewhere; it does not say anything was seen.
3. **`positive-control` is scoped to `not-covered`** (§4.1 witness 3). On a `contract` row it is
   not a witness at all: showing that a command *can* match some input says nothing about whether
   the proof would notice a broken implementation.
4. **`<recipe-ref>` must itself PARSE as a recipe** (§4.2). Rule 1 checks *identity* and not
   *shape*, and the two came apart immediately: a row whose verify cell read `` `K ???` `` and
   whose witness read `watched-fail(K ???): changed anything -> saw red` satisfied rule 1 against
   itself. The same nonsense on both sides is a binding, and it witnessed nothing.

**The general rule this is an instance of, stated once so it governs every future check:**

> **No weighted-tier obligation may be satisfied by the mere PRESENCE of a phrase.** A rendering is
> prose, and prose is evidence of nothing. Where a rendering lacks the structure to satisfy an
> obligation, the row is **refused weight** — never granted it because the tool could not tell.

Phrase matching keeps exactly one job: **diagnosis**. A row that mentions a control and states no
structured witness is told so, and is still refused.

**The general form of that rule, for renderings**: **a structured obligation on a weighted row may
be satisfied only by DECLARATIVE syntax — a word-bounded keyword, a required separator, and a
value — never by scanning free prose.** A rendering is prose; a checker that reads obligations out
of prose is guessing, and every such guess found so far has been wrong in one direction or the
other. `blocked-by` matched inside `unblocked_byproduct`; `over` matched *"reviewed over lunch"*;
the predicate declaration matched the identifier `item_kindpredicate` and refused an honest row.
Diagnostic-only patterns stay loose deliberately — their job is to notice that a producer *meant*
something and say so, and a missed variant there costs a hint rather than a verdict.

**Both representations are held to this identically**, and that is checked rather than asserted
**for the placements the battery exercises**: `tools/check_parity_selftest.py` pairs each
obligation's fixture across the two forms and fails if the verdicts differ (§0's note on what
"enforced" means).

*The limit in that clause is real and is not yet closed.* Each paired case states its obligation in
ONE placement — a particular cell, a particular order within the row. A defect that depends on
WHERE a token sits rather than on whether it is present is invisible to a battery with one
placement per obligation. Closing it needs a per-placement dimension across the battery, which is
open work, not a caveat that excuses itself.

**The exact reach of that rule, because it is easy to over-read**. What is now structural in
*both* representations: the grade token, the tier marker, `clause_source`, `bounds`' leading
token, `scope_ref`'s locator, the recipe reference (§4.2), the predicate fraction, `blocked_by`,
and the watched-fail witness with its binding, its transition and its date.

What remains **free text with a shape floor**: `positive_control`, `watched_fail`'s
`perturbed`/`observed` (each must be a statement rather than a single token — `watched_fail = "x"`
and `positive_control = "x"` are both refused), and `bounds`' explanatory tail (at least one word
token, because a real limit is often a single one: `unwind=8`, `[u8;12]`, `T=i32`). A producer who
writes a plausible sentence satisfies all of these, and the format cannot tell.

What remains **free text with NO floor at all, checked only for being nonempty**:
`self_verify.expect`. It is not an oversight to be fixed later, and the reason is worth stating:
`expect` is the one field whose content a static checker has no standing to judge. `test result:
ok` is four characters of substance and a perfect expectation; a long English sentence may be
worthless. Length and word-count measure the wrong thing. What actually decides whether `expect`
means anything is **running the command** and seeing whether the string appears — which is §8.2's
job, and §8.2 additionally refuses the degenerate case where the command spells the expectation
out itself. So the division is: statics require `expect` to exist (§3 rule 2, because "which
harness" does not determine "what green means"), and only execution can say more.

**The rule says a phrase's presence cannot satisfy an
obligation; it does not say the format can check that a phrase is true.** Nothing can, and a version
of this sentence that implied otherwise would be this document committing the defect it exists to
prevent.

### `clause_source` in a rendered ledger is the closed enum, not a citation

W2.3 requires `clause_source`, and the value is one of `spec-document` | `external-standard` |
`doc-comment` | `test-name` | `none`. **Exactly one.** A cell naming two (`spec-document; none`)
has declared no provenance, and a reserved token anywhere in the cell is read wherever it sits —
reading only the leading token let `test-name` and `none` ride behind a separator. In a Markdown
ledger the clause cell must carry that token; a citation may accompany it (`X.690 §8.3
(external-standard)`) but does not replace it. **Free prose in the clause cell is not a
declaration** — *"a stable RFC"* records nothing a consumer can act on, and cannot be told apart
from an unstated source. It is refused exactly like an empty cell.

**`watched_fail` is a statement about the recipe, like `expect` — not evidence, and it carries no
band.** It does not raise assurance, it establishes that the recipe discriminates — without which
`expect` describes an outcome that could not have been otherwise.

## 4.2 What counts as a recipe reference — the grammar, and its limit

`<recipe-ref>` was checked for *identity* (does it name a recipe of this row?) and never for
*shape*, and the two are not the same rule. A row whose verify cell read `` `K ???` `` and whose
witness read `watched-fail(K ???): changed anything -> saw red` satisfied the identity check
**against itself**: the same nonsense appeared on both sides, so the binding held, and the row
counted weighted.

> **A recipe reference is `<LETTER>` or `<LETTER> <command body>`.** `<LETTER>` is a single
> uppercase letter declared in the rendering's own recipe table (§4's `K`/`R`/`T`/`N`/`A`/`D`/`G`
> shape). `<command body>` is the argument that makes the letter into a runnable command: a
> harness path, a test filter, a grep pattern, a theorem name, a document reference. A backticked
> **literal** command (`` `cargo fmt --check` ``) is equally a recipe reference.

**What makes a token a literal command**, as opposed to a row id (`DER-F-8`) or a harness path
(`mod::proofs::foo`), both of which a rendering also backticks: a leading `./` or `/`, a script
extension, or a program name **followed by arguments**. A bare single word is none of these.

Three things are refused as command bodies, each because it names no command:

1. **Nothing runnable** — no word token of two or more characters (`???`, `--`, `.`).
2. **The recipe table's own metavariable** — `` `K <H>` `` cites the grammar rather than an
   instance of it. §4 defines `K <H>`; a row must supply the `<H>`.
3. **A placeholder word** — `TODO`, `TBD`, `XXX`, `n/a`, `none`, `some`.

The same grammar governs both sides, and **both accepted forms**: the verify cell must contain a
reference that parses, and the witness's `<recipe-ref>` must *itself* parse **and** equal one of
the row's own references — whether that reference is a letter form or a literal command.

**The limit, stated out loud, because this section is exactly where a checker invites overreading.**
This is a **shape** check. It establishes that the row named something with the form of a command.
It does **not** establish that the command exists, that it runs, that it succeeds, or that it is the
right command for this row. The first three are what `--execute` answers (§8.2) and only for the
manifest representation; the fourth is not mechanically decidable at all and is reviewer work,
permanently. A row can still satisfy §4.2 with a well-formed command that decides nothing.

## 5. `bounds` — mandatory on `contract` and `probe`

`bounds` ∈ {`"bounded"`, `"unbounded"`}, plus free text stating the actual limit. **Both halves
are required and both are checked**. A weighted `contract`/`probe` claim reading `bounds =
"bounded"`, or a row reading `**CONTRACT** (bounded)`, is refused: it states which of two words
applies and nothing about what the check ranged over.

**`bounded`/`unbounded` are TOKENS, matched exactly.** `bounds = "boundedness:unwind=8"` does not
declare boundedness: it begins with the letters and is a different word.

**A limit is not a boundedness token, and neither is a grade.** `bounds = "unwind=8"`, or a row
reading `**CONTRACT** (unwind=8)`, names a bound without saying *which kind* — and "up to 8" reads
as a ceiling to one reader and as a sample size to another, which is the ambiguity §5 exists to
remove. `**CONTRACT+L4**` with no bounds text is the single-token strength ladder this section's
last subsection tells renderings not to use. Both are refused; the row must state the pair.

*Added 2026-08-25, fourth round, and the reason is worth recording because it is the failure mode
this format is about.* The rendered-ledger checker had accepted `unwind`, `+L4`, `≤N bytes` and
`[u8; N]` as boundedness declarations in their own right — all of them limits — **while importing
the shared `bounds_token`/`has_bounds_tail` helpers and never calling them.** The import line read
as parity; the behaviour was a second, weaker grammar. So `**CONTRACT** (unwind=8)` carried weight
in a rendering and was refused in a manifest, which is §5's exact confusion enforced by the tool
meant to prevent it. The local grammar is deleted rather than demoted: a dead near-duplicate is the
hazard, not the cure. `gates/run_all.sh` step 6 now fails if either checker imports a shared rule
it does not call.

The floor on the tail is deliberately low — one word token — because a real limit is very often a
single one (`unwind=8`, `[u8;12]`, `T=i32`), and a rule demanding two English words would reject the
most precise declarations in the corpus while waving through `bounded: quite small`. That it is a
*shape* floor is the point and the limit: a producer can write `bounded: some inputs` and satisfy
it. Whether the stated limit is the real one is reviewer work.

**The two tokens, defined**:

- **`"bounded"`** — the check ranges over a **proper subset** of the item's input domain, and says
  nothing outside it. An unwind limit, a fixed-size buffer, a capped length, a monomorphic
  instantiation of a generic, a fixture: each of these makes a proof bounded, and the free text must
  name which one and at what limit.
- **`"unbounded"`** — the check ranges over the item's **entire** input domain. There is no
  "outside it" for the claim to be silent about.

Reading a bounded proof as unbounded is the classic overclaim, and it is the difference between
"`decode_length` is canonical" and "`decode_length` is canonical **for inputs up to 16 bytes**". 0.1
therefore refuses a `contract` or `probe` row that does not say which it is. `"unbounded"` is an
explicit, falsifiable claim — not a default and not an absence.

### The case that fits neither name at first reading, and does fit `"unbounded"`

A model-checking harness can be **domain-complete**: no unwind bound, no buffer, the input a fully
symbolic value of the item's own type, so every input the item accepts is covered. It has no kernel
check behind it and no unbounded *length* — the input is a scalar, so there is no length to be
unbounded over. Producers read `"unbounded"` as *"proved for inputs of any size"*, find no size to
speak of, and write `"bounded"` — which is **false**, and false in the underclaiming direction.

**It is `"unbounded"`.** The test is the definition above: is there any input to the item that the
check does not cover? If not, the check is unbounded, whatever the input's shape. The free text
carries the shape: `bounds = "unbounded: symbolic Tag over all 4 classes x both forms x all 2^32 tag
numbers; no unwind, no buffer"`.

**Underclaim is a failure of this format, not a safe default.** The whole point of §1's
`(item, evidence)` correction is that demoting a proof below what it decides is *"an underclaim,
which is the same defect as an overclaim pointed the other way"*. A crate's strongest result going
invisible in the one document written to make strength legible is that defect, and it happened: the
der crate's own `COVERAGE.md` carries two cells reading `CONTRACT (bounded)` on harnesses that are
domain-complete, one of them stating `bounded` and `domain-complete biconditional` in the same cell.

### Do not compress `grade` and `bounds` into one rung

That `COVERAGE.md` reached the wrong cell because it had invented a **single-token strength ladder**
— `CONTRACT` defined as bounded, `CONTRACT+L4` defined as unbounded-and-kernel-checked — with no
rung for *unbounded, no kernel check*. Four of that crate's harnesses fall in the missing rung, so
the vocabulary forced them down to `CONTRACT (bounded)`.

The format's answer is not a third rung. **`grade` and `bounds` are two independent fields and a
rendering must keep them two**: `grade = "contract"` + `bounds = "unbounded"` says exactly the thing
the missing rung was for, and `grade = "contract"` + `bounds = "unbounded"` + a kernel-family
evidence record says the other one. A ladder that multiplies the two axes into one token needs a rung
for every combination, will always be missing one, and each missing rung is a row forced into a
neighbouring label — in whichever direction the ladder happens to lean.

Any rendering that shows a single strength token per row MUST make it a pair, or state the bounds
beside it. A row that shows a grade and no boundedness has not said what it proved over.

## 6. Axis declaration — mandatory

`[spec].axis` is REQUIRED: a prose statement of what the item list enumerates. `[spec].external` lists
normative references not in the tree.

The axis choice determines **which gaps are expressible**. A module-shaped axis has no row for a
cross-cutting rule, so a producer who picks it never has to write the gap down — and never has to lie
either, which is what makes an undeclared axis the most comfortable place to hide. On the der subject
this is not hypothetical: two X.690 rules the crate does not enforce are owned by no module, and
became rows only once the axis was rules rather than files.

An undeclared axis is an unstated scope. 0.1 requires it stated.

## 7. One row, one claim

A row/claim asserts exactly one item at one grade. If two things are true at two strengths, they are
two rows.

Forced by a real row: der's Lean-lid claim was originally written as *"`sorry`-freedom is
gate-enforced; 'no crate-code axiom' is inspection-argued"* — one cell, two grades, and a reader takes
away whichever half they were looking for. Split, both halves are honest and neither is available to
be misread.

## 7.1 `status` × `grade` × `weight` must cohere

`status` says **how far along** the work is; `grade` says **whether the evidence decides the item**.
They are independent axes, and independent is not the same as unconstrained: some pairs assert
contradictory things about the same row, and until 2026-08-25 every one of them validated.

| status | means | grades that cohere | may it carry weight? |
|---|---|---|---|
| `evidenced` | admissible evidence exists and reaches the asserted band | `contract` · `probe` · `test-only` · `mechanical` · `inspection-argued` · `ungraded` | yes, on a weight-eligible grade meeting W2 |
| `partial` | evidence exists but does not reach the asserted band (`assurance-bands.md` rule 5) | same as `evidenced` | yes, same conditions |
| `gap` | in scope for the axis, and nothing checks it | `not-covered` · `unspecified` · `ungraded` | only via `not-covered`, which is weight-eligible for the *absence* claim |
| `parked` | the tool cannot run it (`unsupported`), so nothing was checked | same as `gap`, plus `parked_reason` | same as `gap` |
| `blocked` | the item is **not reachable with the tool at all** — an escalation, not a backlog item (§7.3) | same as `gap`, plus `blocked_by` | same as `gap` |

**`out-of-scope` was missing from this table as first written**, which is an omission and not a
decision: the grade existed and no status was said to cohere with it. It coheres with the three
statuses that assert **no check succeeded** (`gap`, `parked`, `blocked`) — the producer is declaring
the item not claimed, which is not a check result — and never with `evidenced` or `partial`, which
assert that evidence exists for an item the same row says is not claimed.

**The rule, one sentence:**

> **A status that asserts no check succeeded (`gap`, `parked`, `blocked`) may not carry a grade that
> asserts one did (`contract`, `probe`, `test-only`, `mechanical`).** And `evidenced` may not carry
> `not-covered`: evidence exists and nothing checks it cannot both be true.

**Severity is deliberately split.** On a row that **claims weight** this is an **error** — a
`gap`-status row carrying a weighted `contract` is the format vouching for a proof of something it
says in the next cell is unproven. On an **unweighted** row it is a **warning**: a scoreboard
legitimately wants to record the grade a not-yet-started item *will* carry, which is proposal P5 and
is **DEFERRED** (§7.4). This rule must not adopt P5 sideways by making prospective grades an error.

**The whole table is enforced, not only its one-sentence summary**. The sentence names two pairs;
the table forbids more than two. `status = "partial"` with `grade = "not-covered"` — *evidence
exists but does not reach the band* against *nothing checks it* — is named by neither half of the
sentence, and passed **weighted**. It is now read off the table.

**A status cell must name exactly one status.** *"done, but really a gap"* names two, and a cell
naming two has named none — §7.1 coherence cannot be decided against either, so a weighted row
carrying one is refused, exactly as an unrecognised status is.

**`scope_ref` must be a locator.** `out-of-scope` is the one grade whose weight attaches to a
declaration rather than to a property of the code — *"the producer declared this, **here**"* — so
the *here* has to be somewhere a reader can go. A `scope_ref` of free prose records nothing and
cannot be told apart from an undeclared scope, exactly as a free-prose clause cell cannot (§4.1).
The checkable rule is minimal and deliberately shape-only: **`scope_ref` must contain a section
marker (`§4`), an anchor (`README.md#scope`), a document path, or the literal `[spec].axis`.**
Whether the cited section actually says the item is out of scope is not checkable and is reviewer
work.

## 7.2 Predicate items — an item that ranges over a second list (P3, adopted)

The facet assumed items **partition** the surface: one row, one item, one status. An item can
instead be a **predicate over every member of a second list**, whose honest status is a fraction.

**Forced by a rubric item in a second worked subject** — a rubric-scored review sprint,
held for a later publication: some of its review asks are predicates over a large fixed list of
production units, each with a low initial self-score recorded honestly. `status = "partial"` reads
the same at 1-of-N as at (N-1)-of-N, and `[coverage].denominator` describes the item list, not a
sub-list inside one row.

```toml
item_kind = "predicate"                              # REQUIRED: the declaration itself
over      = "the N production units in module X"     # REQUIRED: what it ranges over
covered   = "3/40"                                    # REQUIRED: numerator/denominator, N<=M
```

In a rendered ledger the fraction goes **in the row** (e.g. `3 of 40`), never in a paragraph beside it,
and the row **declares itself** a predicate with a delimited token — `` `predicate` ``,
**predicate**, or `item-kind: predicate`.

**In a rendered ledger the predicate fields are DECLARED, not narrated**: `` `predicate` ``,
`over: <what it ranges over>`, and the fraction `N of M`. `over` needs the keyword, a punctuation
separator and a value — a bare `over <word>` is a preposition, and while the checker accepted one
*"reviewed over lunch"* named the sub-list a predicate ranges over. The same applies to
`blocked-by:` (§7.3).

**Detection is DECLARATIVE, never semantic**. A checker cannot read *"decode rejects every
non-minimal encoding"* and know whether the producer meant a predicate over a named list or a
single rule; the first version read the bare word "predicate" out of running prose, which is that
guess wearing a regex. So the tools look for the declaration and nothing else.

**The cost of that choice, stated rather than hidden: an UNDECLARED predicate item is invisible to
both checkers.** A producer who writes a predicate item as an ordinary row gets no complaint, and
`status = "partial"` will read the same at 1-of-33 as at 32-of-33 — which is the very defect P3 was
adopted to fix. Catching an undeclared one is reviewer work, permanently. The alternative (guessing
from prose) would produce false accusations on ordinary rows and still miss the careful producer, so
the declarative rule is the conservative one, not the strong one.

**A weighted predicate row that states no fraction is refused weight** — an error, not a transitional
`weight-pending`. *Some* is not a status, and §8.1's backlog means *"these rows were fine until the
rules changed"*, which a fractionless predicate row never was.

**This is not trust arithmetic** (`format.md` rule 3). `N of M` is a denominator with a numerator,
counted on a named list; nothing is averaged, scored, or combined across rows, and two predicate
rows are never summed.

## 7.3 `blocked` — the tool cannot do it, which is not the same as nobody has (P4, adopted)

`not-covered` was carrying two claims that demand opposite actions from a reader: *nobody has done
the work yet* (schedule it) and *this is not expressible with the tool at all* (escalate it).

**Forced by a rubric item in the same envelope**: a rubric item the tool could not reach at all was
recorded as blocked rather than scored — sitting beside another item that was simply
unstarted. Both were `not-covered`, and the difference survived only in prose.

**Minimal mechanism, and deliberately not a tenth grade** (the B1b ruling closed the grade set): a
**status** value, `blocked`, with a REQUIRED `blocked_by` naming what blocks it.

```toml
status     = "blocked"
blocked_by = "kani 0.67 cannot quantify over a generic T; see <issue>"
```

Grade stays `not-covered` — the item is still in scope and still unchecked. What changes is that the
escalation is greppable instead of being a sentence a reader may or may not reach.

`blocked` takes the same obligations as `gap`: **no evidence records**, and `blocked_by` is
REQUIRED. In a rendered ledger the equivalent is `blocked-by: <what>` on the row; on a row that
claims weight, its absence is a refusal, not a warning.

## 7.4 P5 (prospective grades) — DEFERRED, and why it is recorded here

A grade attached to evidence that does not exist yet (`probe (bounded)` at status *not started*)
was filed as proposal P5. **Owner ruling 2026-08-25: DEFERRED — no forcing row.** The six instances
in that same second subject's §3.2 are all unweighted, so nothing overclaims; the
practice is a scoreboard convenience with no demonstrated harm.

It is recorded in the spec rather than left in the proposals file because §7.1 is one step from
forbidding it, and a future editor tightening §7.1 to an error would adopt a deferred proposal by
accident. **Do not.** The split severity in §7.1 is that deferral, made mechanical.

---

## 8. The weight rules (validator-enforced)

**W1 — weight is explicit and defaults to absent.** `weight = "weighted" | "unweighted"`. Omitted
means unweighted. The format never vouches by silence.

**W2 — weight is REFUSED unless every condition holds:**

1. `grade` present and weight-eligible (§1);
2. every companion field that grade requires (§3–§5) present and non-empty;
3. `clause_source` present and **not** `test-name` or `none` — a clause read off its own evidence
   cannot carry weight, because nothing could falsify it (the kani slice has five such rows).
   `clause_source` records where the item's text came from: `spec-document` | `external-standard` |
   `doc-comment` | `test-name` | `none`. The last two are **reserved to mean unweightable by
   design** — the requirement was read off the test's own name, or has no source at all.
   **Absence is a refusal too** (P1, adopted 2026-08-25): a claim that omits `clause_source` has
   unstated provenance, which is indistinguishable from the two values reserved to mean
   unweightable, and W1's rule is that the format never vouches by silence;
4. `[spec].axis` declared (§6);
5. a **watched-fail witness** (§4.1), on every grade that asserts a check was performed — P2,
   adopted 2026-08-25 in the strong reading: the format's vouching means *demonstrated able to
   fail*, not *decidable in principle*.

The error reads **WEIGHT REFUSED** and names the failing condition. The claim itself is *not*
rejected — it is admitted unweighted. `WEIGHT REFUSED` on a manifest is one instance of the
validator's general `invalid` exit state — see §8.3 for the full tri-state contract.

> **Both were adopted 2026-08-25 (owner ruling), and both are enforced.** Conditions 3 and 5 were
> the two open overclaim paths this document named as deciding criterion (a). They are now rules,
> not proposals. The reasoning and the demonstrations are recorded with proposals P1 and P2.
>
> **Transition (§8.1).** Rows written before the adoption do not silently keep unearned weight and
> are not silently rejected either: they are refused weight into a named, counted state,
> `weight-pending`. See §8.1.

**W3 — unweighted claims carry no obligations.** No grade, no recipe, no bounds, no axis. A claim
whose entire content is a free-text sentence validates cleanly. It carries this semantics verbatim:

> *admitted as an assertion; the format promises nothing about this claim — same evidentiary level as
> "it was reviewed"*

**W4 — the rendering rule.** Any document rendering these claims MUST make the tier visible per row,
and MUST NOT render the two tiers alike. It is the most consequential rule in the format: an
unmarked row is the exact moment a consumer mistakes an assertion for a format-backed claim.
Enforced by `tools/check_ledger.py`.

**W4 and W1 together — what an UNMARKED row means**. W1 governs: **silence is unweighted.** A
rendered row that states no tier is unweighted, in every representation, without exception. It is
never promoted by the tool's inability to find a marker.

The two cases differ, and only one of them is a defect:

- **Grade is never weight-eligible** (`inspection-argued`, `unspecified`, `ungraded`): the grade
  token *is* the marker. A reader who sees `inspection-argued` cannot mistake it for a
  format-backed claim, so an explicit tier marker is RECOMMENDED, not required.
- **Grade is weight-eligible** (`contract`, `probe`, `test-only`, `mechanical`, `not-covered`,
  `out-of-scope`) **and the row states no tier**: this is the consumer-confusion case W4 exists for.
  The reader sees `CONTRACT` and assumes the format is behind it; W1 says it is not. **The row is
  unweighted, and the rendering is defective.** Reported as `TIER NOT STATED`, and an error under
  `--strict-weight` — the same ratchet as §8.1, for the same reason: the fix is a rendering change
  across existing envelopes, and the ratchet is flipped when they are done, not before.

**A rendering may not claim weight by convention.** "Unweighted rows are marked; everything else is
weighted by default" is exactly the inversion W1 forbids, however clearly the convention is
documented at the top of the file — a convention is not visible *on the row*, which is what W4
requires, and a reader arriving at row 40 from a link has not read it.

The marker MUST be an **explicit, non-colour-based textual token** on the row itself — a `UNWEIGHTED`
label, a `[U]`/`[W]` prefix, or a dedicated weight column. Colour, opacity, a tooltip, an icon, or a
footnote do not satisfy W4 (review finding, folded): a distinction that is technically present but
perceptually invisible is malicious compliance, and W4 exists precisely to stop the rendering from
quietly undoing what the validator enforced.

**The marker is a token, not a word in a sentence**. `tools/check_ledger.py` previously read the
tier off *any* occurrence of "unweighted" in the row's text, which inverted W4: a row graded
`**CONTRACT**` with an empty recipe cell and no boundedness declaration passed clean because its
prose said *"unlike the unweighted rows in §4"* — the substring dropped it to the unweighted tier,
W3 then imposed no obligations on it, and a human still read the strongest grade in the vocabulary
off the strength column. The tool now reads exactly the three forms this rule names: a weight/tier
column, a bolded tier token, or a standalone `[U]`/`[W]`. All three were always what W4 said; two
of them the tool had never accepted.

**W5 — every rendering states its tier counts, and they are CHECKED.** `weighted: N,
unweighted: M`, plus `weight-pending: P` while any exists (§8.1). A consumer must never have to
infer the mix.

Two obligations, and until 2026-08-25 neither was enforced — `check_ledger.py` printed the counts
and compared them to nothing:

1. **A rendering with ledger rows and no stated counts** is reported (error under
   `--strict-weight`).
2. **Stated counts that do not match the computed ones are an ERROR, unconditionally.** A typed
   count that has drifted from its rows is worse than no count, because it is the number a reader
   quotes. This fired on first use: a second subject's envelope claimed two weighted rows
   against three unweighted, where the computed figures were zero and three.
   **"Unconditionally" now means it**: the checker read only
   the FIRST stated tuple, so a rendering could state a passing figure first and an overstated one
   second and exit clean — a producer-chosen overclaim path, not a misreport. Every tuple is
   parsed, and **a rendering that states two different tuples is an error in its own right**: it
   has stated no count, and whichever one a checker picks is the one the producer selected. A
   superseded figure must therefore be reworded so it no longer reads as a count — spell the
   numbers as words, or restructure the sentence.
3. **All THREE counts are compared, `weight-pending` included**. A rendering that states tier
   counts while any row is pending must state the pending count too, and it must match.

**What W5 does NOT check**, so the rule is not read past its edge: it compares the counts a
rendering *states* against the counts this checker *computes from the rows it could parse*. Rows the
tool cannot name are reported as `UNCHECKED` and excluded from both sides — they are visible, not
counted — so a matching W5 line is a statement about the parsed row set, not a guarantee that the
row set is complete. `coverage.claims_total` is the manifest-side analogue and has the same limit.

*That promise became true on 2026-08-26.* It held only for a first cell that was BACKTICKED and
unparseable; an id-shaped cell with the backticks left off produced no report at all, so a row
could leave the count silently — the exact failure the `UNCHECKED` state exists to prevent, reached
by removing two characters. Both shapes are reported now. What remains open: a row whose first
cell looks like ordinary prose is still invisible, because nothing distinguishes it from a table
that is not a ledger.

**Never type a count you can compute.** Every count in a rendering should be produced by the
checker and pasted, or the rendering will eventually disagree with itself — which is the same
defect as `coverage.claims_total` drifting from the claim list, one representation down.

## 8.2 `--execute` — running the recipe (P9, adopted; `tools/check_execute.py`)

Every static rule in this document checks that the producer **typed** the required strings, in the
required shape. None of them checks that the strings correspond to anything that exists. A cold
reader of this format earned a weighted
`contract` row with `command = "true"`: the row named a command, declared an expected output, and
satisfied every rule above.

`--execute` runs each `self_verify.command` in the subject root and matches the real output against
the row's own `expect`. Five outcomes, and they are kept apart on purpose:

| outcome | means |
|---|---|
| `EXECUTED-PASS` | ran, exit 0, and the declared `expect` appears on the selected stream |
| `EXECUTED-FAIL` | did not run, timed out, or exited non-zero |
| `EXPECT-MISMATCH` | exit 0, but the row's own declared `expect` was **not** on the selected stream |
| `SELF-FULFILLING-SUSPECT` | the declared `expect` appears verbatim in the row's **own command text**. Refused without running |
| `NOT-RUN` | no command — never counted as a pass, and never a *failure* either unless `--require-run` is given (see the exit semantics below) |

**Which stream `expect` is matched against**: **stdout**, unless the row declares otherwise with
`self_verify.expect_stream = "stdout" | "stderr" | "combined"`. Matching a combined stream made
every warning, progress line and backtrace a place for the expected string to turn up, and a
command that printed its expectation only on stderr passed. A row that legitimately needs stderr
says so, on the row, where a reader sees it.

**Why `EXPECT-MISMATCH` is not folded into `EXECUTED-FAIL`.** `expect` is matched as a literal
substring, deliberately: anything cleverer would decide what a producer meant, and a matcher that
guesses passes things it should not. But that makes `expect` a *machine-checkable string*, which is
stronger than the prose many existing rows carry (*"VERIFICATION: SUCCESSFUL, and both kani::cover
lines satisfied"* is two facts joined by an English conjunction). A mismatch today is as likely to be
a prose `expect` as a broken recipe, and reporting the first as the second would be this format's own
failure mode pointed inward. **Exit 0 with no `expect` is a mismatch, never a pass** — §3 rule 2.

**Trust boundary, and it is not a footnote.** This mode **executes commands taken from a document**.
A manifest is producer-supplied data and `self_verify.command` is an arbitrary shell string inside
it; running one is equivalent to running a script someone sent you. So it is **off by default**,
refuses to run without an explicit acknowledgement flag, echoes every command, and imposes a
per-row timeout. There is no sandbox. A gate may enable it per repo, for manifests whose provenance
that repo knows — never for a manifest received from outside.

### What `EXECUTED-PASS` establishes, and what it cannot — stated in full

> **`EXECUTED-PASS` means: the command ran, exited 0, and produced the expectation the row
> declared. It does NOT mean the command is a genuine oracle for the claim, and no execution mode
> can make it mean that.**

This is not a caveat added for modesty; it is the mode's actual boundary, and it was found by
running it: `command = "printf 'CLAIM VERIFIED'"` with `expect = "CLAIM VERIFIED"` ran, exited 0,
printed exactly what the row declared, and earned `EXECUTED-PASS`. The producer had typed the answer
into the question.

**What is now refused.** A row whose declared `expect` appears verbatim inside its own command text
is `SELF-FULFILLING-SUSPECT` — a distinct outcome, refused **before running**, because running it
decides nothing. It is a distinct outcome for the same reason `EXPECT-MISMATCH` is distinct from
`EXECUTED-FAIL`: it is a different defect and demands a different action (rewrite the recipe, not
fix the tool or the code).

**What is NOT refused, and cannot be.** That check catches the string being echoed by the command's
own text, because that is mechanically visible. It does not catch a command that greps a fixture the
producer also wrote, a test that asserts something no implementation could violate, a harness whose
postcondition re-computes its expectation from the state under test (§0.5, *independent oracle*), or
any of the other ways a command can pass without deciding anything. **Every one of those is a
reviewer's job, permanently.** `--execute` narrows the gap between *"the producer typed the required
words"* and *"weight is earned"*; it does not close it, and a gate that treats a green `--execute`
run as closure has re-created the overclaim this whole format exists to make hard.

**What it does not do:** judge whether the command is the *right* command for the claim (that is
review), or make a green run mean the claim is true (`expect` is what green means, and `expect` is
producer-supplied). It answers exactly one question: **does the recipe, run today, do what the row
says it does?**

### Exit semantics — what makes this mode exit non-zero

- **A present-but-mismatched `record_hash` is ALWAYS an error.** It is a *detected falsehood*, not
  an absence: the manifest named a hash, and the file does not have it. Reporting that at exit 0 is
  vouching by silence, one representation down. An **absent** `record_hash` stays a note IN THIS
  MODE — `--execute` narrows to "does the recipe run," not manifest-wide field requirements;
  `record_hash` being REQUIRED on a weighted claim's evidence (P9, evidence-types.md) is enforced by
  `tools/check_acceptance.py` at manifest-validation time, not re-derived here from a bare
  evidence-record dict.
- **`NOT-RUN` is a note by default and an error under `--require-run`.** A manifest legitimately
  carries unweighted rows with no recipe, so failing on absence by default would be wrong. But a
  gate that wants a green result to speak for the *whole file* rather than for the rows that
  happened to carry a command must be able to say so, and `--require-run` is how. Without it, "0
  failures" over a file of `NOT-RUN` rows is a true sentence that means nothing.
- **`--only` that selects NO claim is an error, not a green run** (added 2026-08-28). A mistyped
  claim id used to skip every row and exit 0 — including under `--require-run`, because an empty
  outcome set has no `NOT-RUN` rows to count. A run that executed nothing decided nothing, and a
  gate wired to `--only <typo>` reported success for a claim it never looked at: the same
  vacuous-green defect as the `NOT-RUN` bullet above, one level up, at selection rather than at
  execution. The error names the id that matched nothing.

## 8.1 Transition — `weight-pending`, and why it is not just "unweighted"

W2 conditions 3 and 5 were adopted on 2026-08-25, after four envelopes had been written. Two bad
options were available and both were rejected:

- **Grandfather the existing rows.** Then the format vouches, today, for rows that do not meet the
  rule it just adopted — the exact overclaim P1 and P2 were adopted to close.
- **Demote them to `unweighted` and say nothing more.** Refusal-not-rejection is right, but plain
  demotion drops ~90 rows into the tier that *promises nothing* and makes them indistinguishable
  from rows that never claimed weight. The remediation backlog would vanish into a count, and W4's
  "an unweighted row must be visibly marked" would fire on every one of them — telling the reader
  those envelopes had committed the most consequential error in the format, which is false. They
  committed a pre-adoption omission.

**So there is a third state, and it is a state of the CHECKER's report, not a value anyone writes.**

**A refused row is counted in NEITHER tier, on every path.** It is not weighted — the errors say
so — and it is not unweighted, because it asked for weight and was told no; reporting it as
unweighted describes it as a row that never asked for anything.

> **`weight-pending`** — the row claims weight, satisfies every rule that predates the adoption, and
> lacks only the newly-required machinery (`clause_source`, a watched-fail witness, or both).

**The membership invariant is the definition read strictly, and both checkers now hold it.** A row
that *also* breaks a pre-adoption rule is **not** pending: it is refused outright and counted in
neither tier. Filing it on the backlog would put a broken row on a work list whose whole meaning
is *"these rows were fine until the rules changed"*, and would inflate the one number this section
exists to keep honest. A refused-outright row is now told, in a warning, which pending obligations
it *also* lacks — otherwise a producer who fixes the errors is ambushed by two more refusals
appearing behind them.

Rules adopted **after** 2026-08-25 do not enter this state at all. `weight-pending` names a
one-time transition with a fixed membership, not a general holding pen for any rule a row fails;
a §7.2 predicate row with no fraction is refused, not pending, because it was never compliant under
any earlier version of the rules.

Its properties, and each one matters:

1. **It is not weighted.** A pending row is excluded from the weighted count from the day of
   adoption. No unearned weight survives the transition, which is the whole point.
2. **It is not unweighted either.** It is not counted in that tier, and W4's marking rule does not
   fire on it — the row's *declared* tier is what W4 polices, and the row declared weight honestly.
3. **It is counted, named, and itemised by reason.** The checker prints
   `weight-pending: N` and a breakdown per failing condition. **The count IS the remediation
   backlog**, and it must stay visible rather than being absorbed into a tier that promises nothing.
4. **It is a warning today and an error on demand.** `--strict-weight` turns every pending row into
   `WEIGHT REFUSED`. That is the ratchet: the flag goes into the gate suite when the backlog reaches
   zero, and the state stops existing.

**`weight-pending` is transitional and is not part of the frozen format.** When the backlog is
cleared and `--strict-weight` is the default, this section is deleted and W2 has four conditions
enforced as four conditions. A permanent third tier would be a place to park rows forever, which is
how a two-tier format quietly becomes a one-tier format with a waiting room.

## 8.3 The validator's tri-state contract (`valid` | `invalid` | `indeterminate`)

Generalizes the existing binary error/pass behavior implicit above (§8's `WEIGHT REFUSED` is one
instance of `invalid`) — this document never previously named an exit-code contract explicitly;
this is new normative text, anchored to the nearest existing discussion of what a validator run
reports.

**The validator returns one of three mutually exclusive states, each its own exit code:**

| state | exit code | means |
|---|---|---|
| `valid` | `0` | every checked obligation holds; nothing indeterminate |
| `invalid` | `1` | a structural obligation is violated (a required field absent, a closed-vocabulary token out of set, a cross-field equality failed — the evidence-subject binding check, `format.md` rule 4a, lands here) |
| `indeterminate` | `2` | the validator cannot decide — an unresolved extension, an unprofiled `method`/`kind` (`evidence-types.md`, `format.md`'s kind-registry rule), or `shape = "bundle"` (`format.md`) |

**`indeterminate` is non-accepting and its exit is nonzero, unconditionally** — a warning beside
`PASS` is not permitted; a gate that treats exit `2` as passable has re-created the "cannot fully
verify ≠ looks fine" failure this contract exists to prevent. `invalid` and `indeterminate` are
**distinct** codes so a caller can tell "this manifest is wrong" from "this manifest names
something the validator does not yet understand" without parsing stderr.

`format.md`'s validator-obligation entries (the bundle-indeterminate rule, the kind-registry
fail-closed rule) resolve into this same tri-state; this section is the one place the contract as
a whole is stated, rather than repeated per obligation.

**Layered validation.** Conceptually, a shape check precedes every semantic check named above: a
document must have the required tables, fields, and closed-vocabulary tokens in place before any
cross-field rule (status/grade coherence, band reachability, a hash binding, a weight-conditioned
requirement) is even meaningful to ask about a value that might not exist or might be the wrong
type. `tools/check_acceptance.py` implements both layers in one pass rather than as two literal
phases — there is no engineering value in separating them at runtime when one validator owns both
— but the layers are conceptually and artifact-wise distinct: the shape layer is what
`schema/acceptance-0.1.0-draft.schema.json` (`format.md` "The schema artifact") documents for a
third party or an editor; the semantic layer is what this document's own sections (§0.5 onward)
and `format.md`'s design rules state, and only `tools/check_acceptance.py` enforces it. A document
that fails the shape layer cannot meaningfully be evaluated against the semantic layer at all — an
absent `grade` field has no coherence to check against `status`.

---

## What the WEIGHTED tier deliberately does not decide

Named so their absence is not read as permission. These are claim classes **awaiting weight
certification** — usable today, unweighted, with what is missing recorded in
`CLAIM-CLASSES-AWAITING-WEIGHT.md`.

- **No numeric coverage score, no trust arithmetic.** `18 of 21 covered` averages a `contract` row
  with a `probe` row. Pre-existing rule 3 stands unchanged.
- **No mechanical axis-adequacy check.** Whether the declared axis actually enumerates the spec is not
  checkable; it is declared and reviewable — so *"this axis is complete"* is an unweighted claim.
- **No generated-vs-typed provenance.** Nothing distinguishes a derived row from a hand-typed one
  (design-assessment finding B3). `self_verify` mitigates it; it does not close it.
- **No denominator semantics.** `clauses_total` and the slice/complete distinction are unweighted.
