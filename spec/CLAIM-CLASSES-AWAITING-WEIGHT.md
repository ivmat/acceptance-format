# Claim classes AWAITING WEIGHT CERTIFICATION

*Role: normative companion to `core.md` §0 — indexed from README §5.*

**Current truth, not a historical backlog.** This is the live index `core.md` §0 and its closing
section point at for every claim class the format cannot yet certify as weightable (C1–C9 below).
It is a different thing from `core.md` §8.1's `weight-pending` transition, which counts rows that
predate a specific rule adoption and is currently zero in this tree: this file lists claim
*classes*, by design, that the weighted tier does not yet cover at all, and it shrinks only when a
class earns weight machinery and moves into `core.md` itself. Read it as open design questions, not
as spent history.

**These are not excluded from the format.** Under the weight architecture (`core.md` §0) every
claim class below is **admissible today, as an UNWEIGHTED claim** — write it, ship it, a consumer can
read it. What each entry lacks is the machinery that would let the format *certify* it: a way to
express the claim unambiguously AND a command that decides it.

Until then each carries the unweighted semantics verbatim:

> *admitted as an assertion; the format promises nothing about this claim — same evidentiary level as
> "it was reviewed"*

**Being here is not a demotion.** Several of these are the most interesting parts of the format. It
means the class is not yet stateable in a way two people would apply identically — and certifying an
ambiguous class is worse than admitting it unweighted, because a certified ambiguity gets cited as if
it were decided.

Each entry records **what is missing before it can carry weight**. That is the promotion criterion;
when it is met, the class moves into `core.md` and becomes weightable.

---

## C1 — Denominator semantics (`[coverage].denominator`, `slice_note`)

**What it is.** `denominator = "complete" | "slice"` declares whether the item list is the subject's
real requirement total or an honest subset.

**Why it cannot carry weight yet.** The pre-freeze guarantee — *declaring the total makes omission detectable* —
holds only if the total is real, and **neither worked subject can supply one**. X.690 has no
enumerated clause count. The kani slice covers 28 of 61 tests and a sampled subset of flag behaviours.
So in practice every manifest declares `"slice"`, at which point the field says "trust me" in a
schema-shaped way.

**The unresolved question:** *what makes a slice boundary legitimate rather than convenient?* A
producer may draw the boundary around exactly the items they covered and be, technically, perfectly
honest. There is no criterion in the format that distinguishes a principled slice (a layer, a
subsystem, an RFC) from a self-serving one (whatever happened to be tested). Until there is,
`"slice"` is a disclosure, not a control — and freezing it would let it be cited as a control.

**What it needs to carry weight:** a required `slice_boundary` field naming the *rule* that decides
membership, plus a check that the boundary is stated before the rows are written rather than after.

## C2 — Generated-vs-typed row provenance (design-assessment finding B3)

**What it is.** Nothing in the format distinguishes a row emitted by a tool from one typed by a human.

**Why it cannot carry weight yet.** The obvious rule — *`bmc`/`kernel`-family evidence must be tool-emitted* —
would have made the two hand-built envelopes behind this draft inadmissible, and they are the most useful
artifacts the format has produced. The owner's reframe is explicit that producer-side hardness is
acceptable and hand-building is legitimate. So the rule cannot simply ban hand-typing.

But the risk B3 names is real and this draft's own subjects demonstrated it: **seven hand-typed rows overclaimed.**
0.1's answer is indirect — `self_verify` makes a typed row falsifiable — and that is a mitigation, not
a closure. A typed row with a *correct* command and a *wrong* grade still passes 0.1 mechanically; it
took a reviewer to catch it.

**The unresolved question:** is provenance a field (`origin = "emitted" | "typed"`, trivially lied
about), or a *process* obligation (typed rows require a second-seat review before the manifest is
citable)? The second is probably right and is not a schema change at all, which is why it does not
belong in a schema freeze.

## C3 — Comprehension-test machinery

**What it is.** The claim that a consumer can state, in minutes, from the envelope alone: what is
verified, up to which spec, with which tool, what is covered, and what is not.

**Why it cannot carry weight yet.** There is no scoring method. "In minutes" and "can state" are not measurable
as written, the answer key would be written by the same author as the envelope (marking their own
homework), and the one available reader population so far has been small and non-independent. A comprehension
criterion that cannot fail is the same defect as a proof nobody watched go red.

**What exists to build on:** the der envelope §6 ("the five things a consumer must not miss") is a
ready-made answer key of exactly the shape criterion 2 needs — five items, each with a defined right
answer. What is missing is a naive reader and a pre-registered scoring rule.

## C4 — Axis adequacy

**What it is.** Whether `[spec].axis` actually enumerates the governing spec.

**Why it cannot carry weight yet.** Not mechanically checkable against a prose standard, and probably never will
be. 0.1 requires the axis be *declared*; it cannot require it be *complete*. A producer can declare a
narrow axis truthfully and still leave the interesting gaps unexpressible.

**Partial mitigation available now:** requiring `external` normative references makes a reviewer able
to spot an axis that omits half its standard. That is review support, not a gate, and 0.1 says so.

## C5 — `clause_source = "test-name"`: warn or reject?

**What it is.** A clause read off the name of the test that checks it — self-referential, so the test
can never fail the requirement. Five of eleven tested rows in the kani-driver slice are in this state.

**Why it cannot carry weight yet.** Rejecting it drives producers to invent prose requirements to satisfy the
validator — design-assessment finding B1's junk-id failure mode, which would be a *worse* outcome: fabricated
specs that look like specs. Warning it (0.1's behaviour) risks the warning becoming wallpaper.

**The unresolved question:** the right rule is probably a **budget** ("no more than N% of rows may be
test-name-sourced before the manifest is not citable"), and neither the threshold nor the unit is
defensible yet with two subjects of evidence.

> **Partly settled 2026-08-25 (P1, owner-adopted), and the remainder is narrower than it looks.**
> The warn-or-reject question is answered *by tier*: at the **weighted** tier `test-name` (and
> `none`, and absence) **refuse weight** — W2.3, enforced in both checkers. At the **unweighted**
> tier it is still merely warned, which is what keeps B1's junk-id failure mode closed: a producer
> who cannot cite a real clause records `test-name` honestly and loses only weight, instead of
> inventing prose to satisfy a validator. What remains open is only the **budget** question — how
> many test-name-sourced rows make a whole manifest uncitable — and that still wants more subjects.

## C6 — How controls interact with grade

**What it is.** The control gate (observed-red mutation) lifts a *band*. It says nothing about
`grade`.

**Why it cannot carry weight yet.** Arguably a red mutation control is *also* evidence that a row's oracle decides
the item — which is exactly what `grade` asserts — so the two axes may not be as independent as 0.1
states them. But the counterexample is easy: a mutation control on a panic-freedom harness proves the
harness catches a planted panic, and says nothing about whether the encoding rule is decided. So a
control lifts the band and leaves the grade alone *in that case*, and possibly not in others.

Freezing a coupling I can produce a counterexample to would be exactly the ambiguity 0.1 exists to
prevent. Band-lifting stays as pre-freeze; grade stays independent; the interaction is 0.2.

## C7 — Cross-subject aggregation

One subject, one manifest, unchanged from pre-freeze. A workspace-level roll-up
immediately re-invites the averaging problem 0.1 refuses (`contract` and `probe` rows summing to a
number). Named, not designed.

## C8 — Rendering conformance

Both worked envelopes are markdown tables; `tools/check_ledger.py` enforces 0.1's row rules on that
rendering. But the markdown is currently the **source**, not a projection of a manifest. The intended
end state is the reverse: emit the table from `acceptance.toml`.

**Why it is not clean:** writing the emitter now would force the TOML to carry every nuance the prose
rows carry (the "what this does NOT say" columns), and that modelling problem is unsolved. Until it
is, the two representations are checked against the same rules but are not derived from one another —
a real duplication, named here rather than pretended away (design-assessment finding B4).

## C9 — Documentation-change claims ("the documentation now states X")

**Placed here by an owner ruling, 2026-08-25:** the closed grade set is complete and
was **not** opened, so this is a claim class awaiting weight certification, not a tenth token.

**What it is.** A reviewer asked for a caveat to be written down, and it was. A couple of rows in a
second worked subject, held for a later publication, are both this shape.

**Why it cannot carry weight yet.** It is two claims wearing one token, and neither existing token
fits the pair: the **presence** of the text is trivially decidable by a grep, while whether the
**wording conveys the caveat** is decidable by nobody. `mechanical` overclaims — it implies the
reviewer's ask is satisfied when only the text is present. `inspection-argued` underclaims, and
hides that a regression here (someone deleting the sentence) is cheaply detectable.

**The resolution to try first, and it needs no new machinery:** §7's *one row, one claim*, applied
again — a `mechanical` row for *"this exact sentence is present"*, with a pinned-text grep as its
recipe and a seeded-deletion as its `watched_fail` witness (§4.1), plus an `inspection-argued` row,
unweighted, for *"the wording is adequate"*. The proposal that raised the class reached this
conclusion itself.

**What it needs to be promoted:** the split tried on a real review-shaped subject. If producers
collapse it back into one row, or the envelope becomes unreadable at two rows per documentation ask,
that is kill criterion 2 of the B1b ruling and the class comes back for a different answer.
