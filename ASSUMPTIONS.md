# Assumptions and limits

*Role: risks and known limits — indexed from README §11.*

This document is for readers deciding how much to trust an envelope or ledger.

---

## Two tiers; the format vouches for one

Every admitted claim has one of two tiers:

| tier | what it means | who is vouching |
|---|---|---|
| **weighted** | the claim's class is **fully expressible and decidable** in this format: it has one meaning, and it carries the obligations its own `grade` defines (spec/core.md §1, §8). For `contract`/`probe`, that is a self-verify recipe (the deciding command), `bounds` (the covered scope), and a watched-fail witness. For `test-only`/`mechanical`, it is the recipe and a watched-fail witness, with no `bounds`. For `not-covered`, it is the recipe and a `positive_control`, which **is** its watched-fail witness (§4.1). For the declaration grade `out-of-scope`, weight attaches only to *the producer having declared the exclusion*, never to the code, and the sole obligation is a verifiable `scope_ref` locator — no recipe, no bounds. A recipe that has not been observed failing is not deciding, where a recipe is required. | the format |
| **unweighted** | admitted, but remains **an assertion**, usually *"a human asserted this, and a reviewer checked the assertion"*. Nothing about it has been mechanically decided. | nobody but the person who wrote the row |

A producer may write any claim, including one no tool can decide. Admissibility is constant; the
format's support for the row varies. An unweighted row labels an assertion as such, and a mostly
unweighted ledger may accurately represent the work.

A document must distinguish weighted from unweighted rows at a glance, the format's only
presentation requirement.

## Check the self-verify recipes

Every row beyond "admitted" carries a `self_verify` recipe, the command used to check the row. A row
without a runnable recipe is an assertion regardless of its strength label.

In the worked sample, a grep expected zero hits but returned fourteen, and a harness name claimed
more than it proved. Running the recipes found both. Grades are judgments and can drift; readers
should run a sample and check that the results support the rows.

## Validator behavior

`tools/check_acceptance.py` and `tools/check_ledger.py` retain weak, unproven, or unsupported claims
but refuse **weighted** status when the required machinery is absent.

An `ERROR` concerns the **document**. A verified library with a malformed envelope can produce
errors; a barely tested one can produce none if it claims no unsupported weight. The validator
assesses what backs each claim, not software quality.

## Grades attach to an (item, evidence) pair

The same evidence can be strong for one claim and weak for another. A symbolic panic-freedom proof
decides *"this function never panics"* but provides weak, unweighted-grade evidence for *"this
function implements the specified encoding rule"*. Grading the technology (*"it's a Kani proof, so
it's strong"*) rather than its relation to the item caused most grading errors in the drafts. Check
each row rather than transferring a grade between rows that cite the same evidence.

## What this format assumes about you, the reader

- Run some self-verify recipes instead of relying on the strength column.
- Treat "unweighted" as a common state, not a synonym for "bad" or immaturity.
- Do not combine weighted and unweighted rows into a score. The format has no numeric coverage
  score; adding one loses the distinction between the tiers.
- "The validator passed" means the **document** is well-formed and its weighted claims qualify for
  their weight. It does not establish that the software is correct, safe, or free of bugs outside
  the ledger's axis.

## What this format does not promise

- **No trust arithmetic.** There is no computed probability, confidence score, or combined rating.
  Bands are floors on evidence species rather than measurements.
- **No claim that an axis is complete.** An *axis* is the set of items a ledger claims to
  enumerate, for example, "every encoding rule in the standard" versus "every function in the
  crate"; the same artifact can look very different along different axes. A ledger declares its
  axis; nothing here checks that it covers the real spec. A real gap can hide behind an undeclared
  or narrow axis, and the format cannot correct the axis.
- **No guarantee about the reviewer.** Evidence from human or model review is admissible and capped
  at the lowest band because it has no mechanical oracle. A row backed only by review cannot qualify
  as a proof.
- **No signing, no multi-party trust model, in this draft.** This is v0. If you need cryptographic
  provenance across organizations, this format does not yet provide it.
- **No promise that this spec is stable.** See [`README.md`](README.md). Rules have been tightened,
  loosened, and split mid-draft and may change until the `0.1.0` freeze.
