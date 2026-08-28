# Witness envelopes and coverage ledgers: case study

*Role: quality evidence — indexed from README §10.*

For an overview, start with [`README.md`](../README.md).

> **Status: working draft.** This format is neither frozen nor a standard. Current subjects are a
> verified DER library, an open Rust standard-library verification challenge, and a model-checker
> patch. Freezing requires demonstrated use in verification work *without overclaiming*. The
> usefulness ledger records the criteria and supporting or opposing evidence.

## Admit any claim; require evidence for weight

An envelope can admit any software claim, including one no machine can decide. Rows for uncovered
claims distinguish them from supported claims and claims never made. Admitting a claim does not
endorse it:

| tier | what it means | typical evidence |
|---|---|---|
| **weighted** | the format vouches for it because a **deciding recipe**, a command whose failure would falsify the row, exists | a proof harness over a symbolic domain; a kernel-checked theorem; a compiler-enforced property |
| **unweighted** | admitted, but retains its evidentiary level, usually *"a human asserted this and a reviewer checked the assertion"* | an inspection argument; a fixture-shaped probe; a point test; a declared scope gap |

The validator grants weight only to claim classes it can express and decide. Wording cannot move a
claim between tiers; the tooling enforces the distinction.

In the flagship case study, **72 of 80 rows are weighted and 8 are unweighted**. Those are the tier
numbers the table above describes, and they are the ones to quote.

A second, independent split is reported beside them and must not be read as this one: **grade
strength**, which asks whether a row's grade *decides* the subject's rule rather than asserting it.
There, 35 rows carry a deciding grade (`contract`/`mechanical`) and 45 an asserted one
(`probe`/`test-only`/`not-covered`/`out-of-scope`/`inspection-argued`). The two disagree by
construction: a `not-covered` row has an asserted grade and still carries weight, because its own
claim ("nothing here decides this") has a deciding recipe.

*An earlier version of this paragraph quoted the grade numbers under the tier words, reporting the
case study as "45 of 80 admitted".* The tool's adjacent labels caused the confusion: both splits
printed themselves as "weighted/admitted" on adjacent lines. The tool now says `deciding-grade`/`asserted-grade` for the
second, and this paragraph says which is which.

`tools/check_ledger.py` derives every count above from the ledger rather than accepting typed
totals. Admitted rows are expected.

## What an envelope is

An envelope usually contains:

**A witness envelope** identifies the certified commit, tree state, toolchain down to the solver,
gate receipt, and freshness condition under which the receipt still speaks for HEAD.

**A coverage ledger** has one row per *specification rule*, not per code module. Each row has a
status, evidence strength, and runnable **self-verify recipe**. Uncovered rules also have rows.

This per-rule axis can answer *"is the constructed-form rule enforced?"* when no module owns that
rule; a module table can only answer questions such as *"does `sequence.rs` have harnesses?"* In the
DER case study, three rule-axis rows have no counterpart in any module table.

Producing an envelope requires the producer to declare and enumerate a specification axis, grade
each rule's evidence, and attach a command that fails when the row is wrong. The consumer runs one
command per row.

## Findings from the case study

The subject is a formally verified DER (X.690) decoder with 203 Kani proof harnesses, 6 Lean proofs
over unbounded input, 485 tests, and a green full-gate receipt. Building and recertifying its
envelope found the following issues:

1. **The green gate did not distinguish a skipped proof stage.** The crate's `check.sh` printed
   `PASS` whether the Lean stage ran or exited 0 because the toolchain was absent. Two clean-room
   runs had this condition. Separate evidence covered those runs, so no claim was false, but the
   receipt could not distinguish a skip from a pass. The fix added machine-readable status to every
   exit path, a fail-closed `REQUIRE_LEAN` mode, and a self-test for all three states.

2. **Two proofs verified a copy.** Their harnesses named a "no over-read" property of the shipped
   sequence walk but ran a duplicated implementation and never entered shipped code. The manifest
   gate counts harnesses, bounds, stubs, and covers; none changes when a harness verifies a copy. A
   green manifest gate therefore does not establish that a harness enters shipped code, and the
   existing gates could not catch this error.

3. **Reviews found repeated grading errors.** The first draft labelled fixture-shaped and
   monomorphic evidence as deciding; review caught seven rows. Later review caught two more in
   opposite directions. One proof was graded as deciding an item its round-trip oracle cannot
   decide: the oracle used the crate's encoder, so a decoder and encoder sharing a misreading pass
   together. One panic-freedom row was graded too weakly because its grade came from the evidence
   technology rather than the item. Overclaiming and underclaiming are both grading errors. Grades
   require review because they are judgments, while per-row recipes reduce the review cost.
   (Self-reported: the drafts are in commit history, not preserved as separate artifacts.)

4. **A self-verify recipe had never produced the claimed result.** Three "not covered" rows promised
   a grep returning nothing. One returned **14 hits**, all test fixtures in the same file. Its conclusion was correct
   but its evidence was not; a reader running the command could not reconcile the two. The error had
   existed since the first version and survived a review that read labels without running commands.

   The replacement was also wrong. It enumerated a closed set, an error enum, and inferred that a
   rule absent from it was unenforced. The enum documentation establishes only *variant ⇒ enforced
   rule*, not the converse; the crate has an enforced, proof-graded rule without its own variant.
   The replacement's *positive control* used a case-sensitive pattern and returned zero on a file
   containing fourteen matches. The row now has a scoped absence check with two controls: one shows
   that the pattern can match, and one shows that the scope produced the zero. Either control alone
   misses one of these failures. A zero-result grep tests the code, pattern, and scope.

5. **Three proofs could not witness their accept path.** Three panic-freedom harnesses used buffers
   too small to contain a well-formed object, so every input was rejected early. They prove "no
   panic on garbage" but provide no evidence that the accept path is safe. The tool reports
   `SUCCESSFUL` with `0 of 1 cover properties satisfied`, and the gate does not fail.

6. **Control tests found holes in a count guard.** The ledger's totals were wired into the subject's
   documentation gate so stale counts would fail the build. Each of nine count claims was
   deliberately staled and the gate re-run; **three did not turn red** because of case-sensitive
   phrase patterns. The guard's comments record two earlier instances of this hole class. The claims
   were reworded until the gate detected them, and the file was then diffed byte-identical to its
   pre-mutation copy. Deliberately failing the check exposed the holes.

These findings do not grade the *oracle* inside a harness. A harness verifying the wrong property
passes like one verifying the right property. The reviewed strength column asserts oracle quality;
no gate derives it, so it is marked as judgement rather than derivation.

## Samples

One envelope ships with this repo:
[`examples/rs-verified-der/ENVELOPE.md`](../examples/rs-verified-der/ENVELOPE.md). It covers a verified
DER decoder with 80 rows, both tiers in one table, and counts wired into the subject's gate.

Planned unpublished samples include a **mostly unweighted** case reflecting its underlying work and a
proof-free, pure-test-evidence case supported entirely by **mutation-controlled** tests, pending their
subjects' disclosure sequence; both will be added after publication. Until then, the repository
contains only its most mature subject and does not demonstrate the full maturity range.

## Quickstart

[`QUICKSTART.md`](../QUICKSTART.md) gives the validation command and a worked example against a small
real subject.

## Design rules

- **The subject's generated documents are authoritative.** If they disagree with an envelope, the
  generated documents win and the envelope has a bug.
- **Every row carries a runnable recipe.** A hand-asserted row naming a command is falsifiable in one
  step; a row naming only a conclusion is not.
- **Derived fields are marked and gated where possible.** Counts should come from subject generators.
  In the flagship case, a stale count fails the subject's gate.
- **Only deciding evidence upgrades a row.** Rewording does not.
- **No scores.** Averaging a kernel-checked theorem with a fixture test erases their distinction.

## Vocabulary drift

Within hours of closing the vocabulary, **two independently written envelopes against the same spec
used five undefined grade tokens**: `CONTRACT-analogue`, `doc-only`, `test-backed`, `receipt-backed`,
and `admitted`. The row checker rejects all five. Each author encountered a real claim shape, a
mutation-controlled unit test, documentation edit, or compile receipt, and added a word without
checking the closed set.

The closed set already covered **three of the five**. For `CONTRACT-analogue`, the grade is
`test-only`, while weight records what mutation control establishes. The two axes cover the case.

Two explanations remain:

- the closed set may be **incomplete**. A review thread and rubric sprint are not a verified library,
  and existing tokens may not cover a claim such as "documentation now states X". Such cases become
  **growth proposals** for a decision rather than new tokens;
- adopters may need the **checker in their loop**. Both envelopes were fixed within minutes by
  running it.

One freeze criterion requires the vocabulary to work across subjects. The second and third subjects
show that it does not yet do so; freezing on a schedule would accept a known vocabulary problem.

Each invented token tried to qualify evidence as better or worse than its grade. A single-axis
vocabulary would absorb that pressure as new tokens. Separate axes record **the evidence kind** and
**whether the format vouches for it**.

## Status, and what would change it

This working draft is not a standard, has no version guarantee, and will change as samples provide
evidence. The spec records the freeze criteria. The usefulness ledger records what building
envelopes found and will provide the case for freezing.

Scaling from one library's claim surface to an entire tool remains an unproven design goal.
