# ADR-009: no `[[note]]` construct; the unweighted claim carries commentary

**Status:** Accepted (ruled 2026-08-28)

## Context

Work against this format produced an ask: a place to write something *about* the manifest that is
explicitly not a certified property — a producer/verifier independence disclosure, a caveat about
how a subject was sampled, an editorial aside a reader ought to see. The shape it suggested is a
new top-level element, `[[note]]`, admitted and never weighted.

The ask arrived concretely while writing the format's own self-manifest: one task brief called for
an unweighted `[[note]]` stating the producer/verifier relationship plainly. No such table exists
in the schema, and the question of whether to add one had never been ruled. One brief is the whole
record of it — this is ruled now because the answer decides a data-model boundary, not because the
request recurred.

The pull is real. A note *looks* cheaper than a claim: no `item`, no `statement` discipline, no
`status`, nothing a validator could complain about. That appearance is the thing this decision
examines, because a new admitted element is not cheap — every element is a place a producer can put
a fact, and a reader has to learn to look.

## Decision

**The format adds no `[[note]]` construct.** The **unweighted claim** is the canonical carrier for
commentary, disclosure, and any statement offered without asking the format to stand behind it.

Three reasons, in the order they bind:

1. **The unweighted claim already does exactly this, and says so verbatim.** `core.md`'s W3 puts no
   obligations on an unweighted claim — no grade, no recipe, no bounds, no axis — and W1 makes
   weight explicit and absent by default. The tier carries its meaning in its own words: *admitted
   as an assertion; the format promises nothing about this claim — same evidentiary level as "it
   was reviewed"*. A note would be a second element with that same semantics and no way to say it
   better.
2. **A parallel carrier violates the normalization the rest of the format is built on.** One fact
   lives in one place: `tools/acceptance_grammar.py` exists so a rule cannot have two
   implementations to drift between (`maintainers/OBLIGATIONS.md` — *"a rule cannot drift between
   checkers, because there is only one of it"*), and ADR-001 refuses the rendered ledger the status
   of a second source. Two admitted carriers for one kind of statement is the same defect one layer
   up: a fact recordable in two places will be recorded in two places, and the copies will disagree.
3. **It would widen the schema surface without adding trust semantics.** A `[[note]]` decides
   nothing, gates nothing, and is read by no validator function — so it buys a new table, new
   emitter and renderer cases, and a new thing a consumer must be told to read, in exchange for
   nothing the weight architecture does not already express. Design rule 7 refuses to name machinery
   that does not exist; this refuses to name a *slot* whose only content is what an existing slot
   already holds.

**Demonstrated, not asserted.** `acceptance.toml` carries the very disclosure that
raised the ask, as claim `SELF-NOTE`: an unweighted, `inspection-argued` claim stating that this
repo's manifest is produced and validated by tooling living in the repo it certifies. It validates
as part of the gate suite (step 9, under `--strict --strict-weight`), it omits `weight` and is
therefore unweighted by W1, and it reads as a disclosure to a human. This repo renders no ledger of
its own manifest, so W4 is not yet exercised on it: the claim *would* render visibly unweighted,
since W4 governs the rendered row and W1 already fixes the tier that row must state. Nothing about
it wanted a different element.

## Consequences

A task brief, template, or downstream tool that suggests `[[note]]` maps to an **unweighted
`[[claim]]`**: `weight` omitted (W1's default), a `statement` carrying the note's text, and
`grade = "inspection-argued"` or `grade = "ungraded"` — the labels for *there is nothing to
run that decides this sentence* and *the producer declines to grade*. Nothing is lost in the
translation, because W3 asks nothing of the result.

The rendering rule (W4) then covers notes for free: a note-as-claim is marked unweighted on its own
row, so a consumer can never mistake it for a format-backed statement — which is the guarantee a
separate `[[note]]` element would have had to re-establish for itself, in every rendering, forever.

Reopening this needs a note-shaped statement that an unweighted claim provably cannot express.
Convenience is not that; neither is the claim schema feeling heavy, which is an emitter's problem
and not the data model's.
