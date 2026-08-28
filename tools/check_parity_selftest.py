#!/usr/bin/env python3
"""check_parity_selftest.py — prove the two representations reach the SAME VERDICT.

Pure python3 stdlib. Run: `python3 tools/check_parity_selftest.py` (exit 0 = parity holds).

WHY THIS EXISTS
---------------
`core.md` says its rules are enforced "in both representations, and in both directions".
That sentence was maintained by hand, and it was false. the round-3 review probe:

    | `O-1` | h is deliberately not implemented | S-1 (spec-document) | gap |
      **out-of-scope** · **weighted** | nonsense |

The manifest twin of that claim was REFUSED — `scope_ref` must be a locator. The rendered row was
granted WEIGHT. One rule, two implementations, and the permissive one governed the representation a
human actually reads. Nothing in the gate suite could have noticed, because every test in it
exercised one checker at a time.

WHAT THIS HARNESS ASSERTS, AND WHAT IT DOES NOT
-----------------------------------------------
Each case below states ONE claim twice — once as a `[[claim]]` and once as a ledger row — and
asserts the two checkers agree on the **verdict class**:

    WEIGHTED  the claim came through clean and the format vouches for it
    REFUSED   the claim did not earn weight, by error or by transitional refusal

It does NOT compare wording, message counts, warning text, or which rule fired. Those legitimately
differ: a rendering has no `scope_ref` column, a manifest has no tier marker, and the diagnostics
should speak in the vocabulary of the representation the producer is looking at. **The verdict is
the thing a consumer acts on, so the verdict is the thing that must match.**

Consequently a case passing here means the two checkers agreed — NOT that either was right. A rule
absent from both representations is in parity and still missing. This harness closes drift between
the checkers; it does not close the gap between the checkers and the spec.

THE HARNESS IS ITSELF WATCHED
-----------------------------
`--prove-break` re-runs the O-1 case with the Markdown side monkeypatched back to its pre-fix
behaviour (nonemptiness only) and asserts that this harness REPORTS THE BREAK. A parity harness
that has never been seen to fail is a parity harness nobody has tested — the same rule §4.1 puts on
every weighted recipe, applied to the tool that checks it. The main run performs that proof too, so
it cannot be skipped by forgetting a flag.
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_acceptance as CA  # noqa: E402
import check_ledger as CL  # noqa: E402

WEIGHTED = "WEIGHTED"
REFUSED = "REFUSED"

MANIFEST_HEAD = """[format]
id            = "acceptance/0"
shape         = "single-file"
spec_id       = "acceptance-format"
spec_sha      = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
validator_sha = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
generated_by  = "check_parity_selftest.py"
generated_at  = "2026-08-27T00:00:00Z"

[subject]
name   = "parity"
kind   = "rust-crate"
commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
dirty  = false

[spec]
path    = "SPEC.md"
version = "v1"
axis    = "the parity battery's own rows"

[coverage]
clauses_total = 1
claims_total  = 1

"""

MD_HEADER = "| id | rule | clause | status | strength | verify |"
MD_SEP = "|---|---|---|---|---|---|"


@dataclass
class ParityCase:
    name: str
    obligation: str      # which spec rule this case exercises
    expect: str          # WEIGHTED | REFUSED
    toml: str
    md: str


def toml_verdict(claim_toml: str) -> tuple[str, list[str]]:
    """Run the manifest validator and classify. A claim is WEIGHTED only if the file is clean AND
    the claim was counted in the weighted tier — `weight-pending` is a refusal (§8.1 property 1:
    "It is not weighted")."""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "acceptance.toml"
        path.write_text(MANIFEST_HEAD + claim_toml, encoding="utf-8")
        rep = CA.validate(path, strict=False)
    n_weighted = getattr(rep, "n_weighted", 0)
    if rep.ok() and n_weighted == 1:
        return WEIGHTED, []
    reasons = list(rep.errors) + [r for rs in rep.pending.values() for r in rs]
    return REFUSED, reasons or ["weight was not claimed (W1: silence is unweighted)"]


def md_verdict(md_row: str) -> tuple[str, list[str]]:
    """Run the row checker and classify, by the same rule."""
    text = "\n".join([MD_HEADER, MD_SEP, md_row])
    results = CL.check_file_text(text)
    if not results:
        return REFUSED, ["no ledger row was recognised at all"]
    row = results[0]
    if row.weighted and not row.errors and not row.pending_reasons:
        return WEIGHTED, []
    return REFUSED, (list(row.errors) + list(row.pending_reasons)
                     or ["weight was not claimed (W1: silence is unweighted)"])


# ---------------------------------------------------------------------------
# The battery — at least one case per weighted-tier obligation.
# ---------------------------------------------------------------------------

# A claim that satisfies every obligation, in both representations. Every REFUSED case below is
# this one with exactly ONE thing broken, so a refusal is attributable to that one thing.
_GOOD_TOML = '''[[claim]]
id        = "P-1"
clause    = "S-1"
item      = "src/lib.rs::a"
statement = "a rejects non-minimal encodings"
band      = "A0"
weight    = "weighted"
grade     = "contract"
bounds    = "bounded: unwind=8"
status    = "evidenced"
clause_source = "spec-document"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  method    = "kani-harness"
  epistemic_tier = "T2"
  ref       = "check_a"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: kani-unwind-8"
  semantics = ""
  record    = "evidence/does-not-exist-p1.json"
  record_hash = "sha-512:00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"

  [claim.self_verify]
  command = "cargo kani --harness check_a"
  expect  = "VERIFICATION:- SUCCESSFUL"

    [claim.self_verify.watched_fail]
    of_command = "cargo kani --harness check_a"
    perturbed  = "deleted the minimality check in decode"
    observed   = "check_a FAILED on the padding assertion"
    date       = "2026-08-25"
'''

_GOOD_MD = (
    "| `P-1` | a rejects non-minimal encodings | S-1 (spec-document) | evidenced | "
    "**CONTRACT** (bounded, unwind=8) · **weighted** | `K mod::proofs::check_a`. "
    "watched-fail(K mod::proofs::check_a): deleted the minimality check in decode -> "
    "check_a FAILED on the padding assertion, observed 2026-08-25 |"
)


def _t(**repl: str) -> str:
    out = _GOOD_TOML
    for old, new in repl.items():
        marker = old.replace("__", " ")
        assert marker in out, f"TOML fixture marker not found: {marker!r}"
        out = out.replace(marker, new, 1)
    return out


CASES: list[ParityCase] = [
    ParityCase(
        "baseline-fully-compliant-claim",
        "the whole weighted battery (W2.1-W2.5, §3, §4.1, §4.2, §5, §7.1)",
        WEIGHTED, _GOOD_TOML, _GOOD_MD,
    ),
    ParityCase(
        "W1-silence-is-unweighted",
        "W1 — weight is explicit and defaults to absent",
        REFUSED,
        _GOOD_TOML.replace('weight    = "weighted"\n', ""),
        _GOOD_MD.replace(" · **weighted**", ""),
    ),
    ParityCase(
        "W2.1-unweightable-grade-cannot-carry-weight",
        "W2.1 — grade present and weight-eligible",
        REFUSED,
        _GOOD_TOML.replace('grade     = "contract"', 'grade     = "inspection-argued"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**inspection-argued**"),
    ),
    ParityCase(
        "P1-clause_source-absent",
        "W2.3 (P1) — weight requires recorded provenance",
        REFUSED,
        _GOOD_TOML.replace('clause_source = "spec-document"\n', ""),
        _GOOD_MD.replace(" | S-1 (spec-document) | ", " |  | "),
    ),
    ParityCase(
        "P1-clause_source-read-off-its-own-evidence",
        "W2.3 — test-name is reserved to mean unweightable",
        REFUSED,
        _GOOD_TOML.replace('clause_source = "spec-document"',
                           'clause_source = "test-name"'),
        _GOOD_MD.replace(" | S-1 (spec-document) | ", " | `test-name` | "),
    ),
    ParityCase(
        "P2-no-watched-fail-witness",
        "W2.5 (P2) / §4.1 — a recipe nobody has watched fail",
        REFUSED,
        _GOOD_TOML[:_GOOD_TOML.index("    [claim.self_verify.watched_fail]")],
        _GOOD_MD[:_GOOD_MD.index(". watched-fail(")] + " |",
    ),
    ParityCase(
        "P2-witness-bound-to-a-different-check",
        "§4.1 — the of_claim / of_command binding",
        REFUSED,
        _GOOD_TOML.replace('of_command = "cargo kani --harness check_a"',
                           'of_command = "cargo kani --harness check_b"'),
        _GOOD_MD.replace("watched-fail(K mod::proofs::check_a):",
                         "watched-fail(K other::proofs::check_b):"),
    ),
    ParityCase(
        "P2-witness-states-no-observation-or-perturbation",
        "§4.1 — the witness must be a statement, not a token",
        REFUSED,
        _GOOD_TOML.replace('perturbed  = "deleted the minimality check in decode"',
                           'perturbed  = "x"'),
        _GOOD_MD.replace("deleted the minimality check in decode -> "
                         "check_a FAILED on the padding assertion", "x -> y"),
    ),
    ParityCase(
        "P2-witness-states-no-date",
        "§4.1 — 'when' is part of the witness",
        REFUSED,
        _GOOD_TOML.replace('    date       = "2026-08-25"\n', ""),
        _GOOD_MD.replace(", observed 2026-08-25", ""),
    ),
    ParityCase(
        "recipe-absent",
        "§3 rule 1 — a deciding recipe is required",
        REFUSED,
        _GOOD_TOML[:_GOOD_TOML.index("  [claim.self_verify]")],
        _GOOD_MD[:_GOOD_MD.index("| `K mod::proofs::check_a`")] + "|",
    ),
    ParityCase(
        "bounds-absent",
        "§5 — boundedness is mandatory on contract/probe",
        REFUSED,
        _GOOD_TOML.replace('bounds    = "bounded: unwind=8"\n', ""),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**CONTRACT**"),
    ),
    ParityCase(
        "bounds-token-with-no-stated-limit",
        "§5 — the token plus the actual limit",
        REFUSED,
        _GOOD_TOML.replace('bounds    = "bounded: unwind=8"', 'bounds    = "bounded"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**CONTRACT** (bounded)"),
    ),
    ParityCase(
        "S7.1-gap-status-with-a-grade-that-asserts-a-check",
        "§7.1 — status × grade coherence, the summary pair",
        REFUSED,
        _GOOD_TOML.replace('status    = "evidenced"', 'status    = "gap"')
                  .replace(_GOOD_TOML[_GOOD_TOML.index("  [[claim.evidence]]"):
                                      _GOOD_TOML.index("  [claim.self_verify]")], ""),
        _GOOD_MD.replace(" | evidenced | ", " | gap | "),
    ),
    ParityCase(
        "S7.1-partial-status-with-not-covered",
        "§7.1 — the pair only the TABLE forbids",
        REFUSED,
        _GOOD_TOML.replace('grade     = "contract"', 'grade     = "not-covered"')
                  .replace('bounds    = "bounded: unwind=8"\n', "")
                  .replace('status    = "evidenced"', 'status    = "partial"')
                  .replace('  expect  = "VERIFICATION:- SUCCESSFUL"',
                           '  expect  = "VERIFICATION:- SUCCESSFUL"\n'
                           '  positive_control = "the same pattern against src/b.rs matches"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**not-covered**")
                .replace(" | evidenced | ", " | partial | ")
                .replace("|$", "|")
                .replace(", observed 2026-08-25 |",
                         ", observed 2026-08-25. positive-control: 3 matching lines in "
                         "src/baz.rs |"),
    ),
    ParityCase(
        "S7.1-out-of-scope-with-a-locator-free-source",
        "§1/§7.1 — scope_ref must be a locator (THE ROUND-3 REVIEW PROBE)",
        REFUSED,
        _GOOD_TOML.replace('grade     = "contract"',
                           'grade     = "out-of-scope"\nscope_ref = "nonsense"')
                  .replace('bounds    = "bounded: unwind=8"\n', "")
                  .replace('status    = "evidenced"', 'status    = "gap"')
                  .replace(_GOOD_TOML[_GOOD_TOML.index("  [[claim.evidence]]"):], ""),
        "| `O-1` | h is deliberately not implemented | S-1 (spec-document) | gap | "
        "**out-of-scope** · **weighted** | nonsense |",
    ),
    ParityCase(
        "S7.1-out-of-scope-with-a-real-locator",
        "§1/§7.1 — the positive control for the case above",
        WEIGHTED,
        _GOOD_TOML.replace('grade     = "contract"',
                           'grade     = "out-of-scope"\nscope_ref = "README.md#scope"')
                  .replace('bounds    = "bounded: unwind=8"\n', "")
                  .replace('status    = "evidenced"', 'status    = "gap"')
                  .replace(_GOOD_TOML[_GOOD_TOML.index("  [[claim.evidence]]"):], ""),
        "| `O-2` | h is deliberately not implemented | S-1 (spec-document) | gap | "
        "**out-of-scope** · **weighted** | see `README.md` §2 (scope) |",
    ),
    ParityCase(
        "P3-predicate-with-no-fraction",
        "§7.2 — a weighted predicate row that states no fraction",
        REFUSED,
        _GOOD_TOML.replace('clause_source = "spec-document"',
                           'clause_source = "spec-document"\nitem_kind = "predicate"\n'
            'over      = "the 33 production harnesses"'),
        _GOOD_MD.replace("| a rejects non-minimal encodings |",
                         "| `predicate`, over: the 33 production harnesses |"),
    ),
    ParityCase(
        "P3-predicate-with-its-fraction",
        "§7.2 — the positive control",
        WEIGHTED,
        _GOOD_TOML.replace(
            'clause_source = "spec-document"',
            'clause_source = "spec-document"\nitem_kind = "predicate"\n'
            'over      = "the 33 production harnesses in module X"\ncovered   = "4/33"'),
        _GOOD_MD.replace(
            "| a rejects non-minimal encodings |",
            "| `predicate`, over: the 33 production harnesses, 4 of 33 |"),
    ),
    ParityCase(
        "P4-blocked-without-blocked_by",
        "§7.3 — an escalation must name what blocks it",
        REFUSED,
        _GOOD_TOML.replace('grade     = "contract"', 'grade     = "not-covered"')
                  .replace('bounds    = "bounded: unwind=8"\n', "")
                  .replace('status    = "evidenced"', 'status    = "blocked"')
                  .replace(_GOOD_TOML[_GOOD_TOML.index("  [[claim.evidence]]"):
                                      _GOOD_TOML.index("  [claim.self_verify]")], "")
                  .replace('  expect  = "VERIFICATION:- SUCCESSFUL"',
                           '  expect  = "VERIFICATION:- SUCCESSFUL"\n'
                           '  positive_control = "the same pattern against src/b.rs matches"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**not-covered**")
                .replace(" | evidenced | ", " | BLOCKED | ")
                .replace(", observed 2026-08-25 |",
                         ", observed 2026-08-25. positive-control: 3 matching lines in "
                         "src/baz.rs |"),
    ),
    ParityCase(
        "S4.2-recipe-reference-that-names-no-command",
        "§4.2 — a recipe reference must parse",
        REFUSED,
        # The manifest analogue of `K ???` is an empty command: neither names anything runnable.
        _GOOD_TOML.replace('command = "cargo kani --harness check_a"', 'command = ""'),
        _GOOD_MD.replace("`K mod::proofs::check_a`", "`K ???`"),
    ),
    # --- §5 bounds SHAPES (review round-4). The battery had one bounds case per direction and
    # --- missed the shape that actually diverged: a LIMIT with no boundedness token.
    ParityCase(
        "bounds-limit-with-no-leading-token",
        "§5 — a limit is not a boundedness token (THE ROUND-4 REVIEW PROBE)",
        REFUSED,
        _GOOD_TOML.replace('bounds    = "bounded: unwind=8"', 'bounds    = "unwind=8"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**CONTRACT** (unwind=8)"),
    ),
    ParityCase(
        "bounds-grade-token-carrying-the-boundedness-implicitly",
        "§5 — the single-token strength ladder a rendering may not use",
        REFUSED,
        _GOOD_TOML.replace('bounds    = "bounded: unwind=8"', 'bounds    = "+L4"'),
        # The `CONTRACT+L4` ladder token itself is retired (a rendering used to be able to fold
        # "bounded Kani + unbounded Lean" into one composite grade token, with no separate bounds
        # text at all -- the single-token strength ladder this case names). A bare `CONTRACT`
        # with no bounds text reproduces the same "grade token alone, no boundedness stated" shape
        # with the current (non-ladder) vocabulary.
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**CONTRACT**"),
    ),
    ParityCase(
        "bounds-generic-one-token-tail",
        "§5 — the tail must carry a word token",
        REFUSED,
        _GOOD_TOML.replace('bounds    = "bounded: unwind=8"', 'bounds    = "bounded: x"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**CONTRACT** (bounded, x)"),
    ),
    ParityCase(
        "bounds-numeric-only-tail",
        "§5 — a bare number IS a limit and is accepted, in both",
        WEIGHTED,
        _GOOD_TOML.replace('bounds    = "bounded: unwind=8"', 'bounds    = "bounded: 12"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**CONTRACT** (bounded, 12)"),
    ),
    # Both `unbounded`-claim cases also move the EVIDENCE record's own bounds to `unbounded`.
    # Without that they carry a second, unrelated defect as of 2026-08-28: core.md §2's
    # scope-coverage conjunct refuses an unbounded `contract` claim whose only qualifying T1/T2
    # evidence is `bounded`. These cases exist to witness §5's CLAIM-side bounds grammar, and a
    # case that fails for two obligations witnesses neither — which is exactly what the minimality
    # audit below says, and it said it the moment the conjunct started being checked.
    ParityCase(
        "bounds-unbounded-with-a-stated-domain",
        "§5 — `unbounded` is an explicit claim, not a default",
        WEIGHTED,
        _GOOD_TOML.replace('bounds    = "bounded: unwind=8"',
                           'bounds    = "unbounded: symbolic Tag over all 4 classes"')
                  .replace('bounds    = "bounded: kani-unwind-8"',
                           'bounds    = "unbounded: symbolic Tag, no unwind bound"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)",
                         "**CONTRACT** (unbounded: symbolic Tag over all 4 classes)"),
    ),
    ParityCase(
        "bounds-unbounded-with-no-domain-stated",
        "§5 — `unbounded` owes its domain too, not just `bounded`",
        REFUSED,
        _GOOD_TOML.replace('bounds    = "bounded: unwind=8"', 'bounds    = "unbounded"')
                  .replace('bounds    = "bounded: kani-unwind-8"',
                           'bounds    = "unbounded: symbolic Tag, no unwind bound"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**CONTRACT** (unbounded)"),
    ),
    # --- clause_source: the Markdown pattern is DERIVED from the shared set, so every token in
    # --- that set must be accepted by both. One case per token, generated below the list.
    # --- review round-5. Each of these diverged BETWEEN the representations, and the first one
    # --- diverged inside the shared module itself.
    ParityCase(
        "bounds-token-prefix-smuggling",
        "§5 — `bounded` is a token, not a prefix (THE ROUND-5 REVIEW PROBE)",
        REFUSED,
        _GOOD_TOML.replace('bounds    = "bounded: unwind=8"',
                           'bounds    = "boundedness:unwind=8"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)",
                         "**CONTRACT** (boundedness:unwind=8)"),
    ),
    ParityCase(
        "witness-observation-of-one-token-plus-a-date",
        "§4.1 — the phrase floor measures the description, not the date annotation",
        REFUSED,
        _GOOD_TOML.replace('observed   = "check_a FAILED on the padding assertion"',
                           'observed   = "y"'),
        _GOOD_MD.replace("check_a FAILED on the padding assertion, observed 2026-08-25",
                         "y, observed 2026-08-25"),
    ),
    ParityCase(
        "clause-source-reserved-token-behind-a-separator",
        "W2.3 — every token in the cell is read, not just the first",
        REFUSED,
        # TOML holds one token per field, so the manifest analogue of smuggling a second one is
        # simply declaring the reserved value.
        _GOOD_TOML.replace('clause_source = "spec-document"', 'clause_source = "none"'),
        _GOOD_MD.replace(" | S-1 (spec-document) | ", " | S-1 (none) | "),
    ),
    ParityCase(
        "status-outside-the-closed-vocabulary",
        "§7.1 — an undecidable coherence check refuses rather than skipping",
        REFUSED,
        _GOOD_TOML.replace('status    = "evidenced"', 'status    = "nonsense"'),
        _GOOD_MD.replace(" | evidenced | ", " | nonsense | "),
    ),
    # --- review round-6: the new machinery's own edges.
    ParityCase(
        "witness-metadata-with-a-colon-separator",
        "§4.1 — the annotation keyword and ANY separator are metadata (round-6 probe)",
        REFUSED,
        _GOOD_TOML.replace('observed   = "check_a FAILED on the padding assertion"',
                           'observed   = "bug, observed: 2026-08-25"'),
        _GOOD_MD.replace("check_a FAILED on the padding assertion, observed 2026-08-25",
                         "bug, observed: 2026-08-25"),
    ),
    ParityCase(
        "witness-metadata-with-a-dash-separator",
        "§4.1 — same, with an em dash",
        REFUSED,
        _GOOD_TOML.replace('observed   = "check_a FAILED on the padding assertion"',
                           'observed   = "bug, observed \u2014 2026-08-25"'),
        _GOOD_MD.replace("check_a FAILED on the padding assertion, observed 2026-08-25",
                         "bug, observed \u2014 2026-08-25"),
    ),
    ParityCase(
        "witness-with-a-date-in-the-MIDDLE-keeps-its-text",
        "§4.1 — only a TRAILING annotation is metadata; the strip must not over-reach",
        WEIGHTED,
        _GOOD_TOML.replace('observed   = "check_a FAILED on the padding assertion"',
                           'observed   = "failure on 2026-08-25 after harness mutation"'),
        _GOOD_MD.replace("check_a FAILED on the padding assertion, observed 2026-08-25",
                         "failure on 2026-08-25 after harness mutation, observed 2026-08-25"),
    ),
    ParityCase(
        "status-cell-present-but-empty",
        "§7.1 — a required status that is absent refuses in both (round-6 probe)",
        REFUSED,
        _GOOD_TOML.replace('status    = "evidenced"\n', ""),
        _GOOD_MD.replace(" | evidenced | ", " |  | "),
    ),
    # --- review round-7: the prose-scanning class. Weight-bearing Markdown reads must be
    # --- declarative; these pair each against the manifest field that has always been.
    ParityCase(
        "blocked-by-must-be-declared-not-merely-contained",
        "§7.3 — a keyword inside an identifier declares nothing (round-7 probe)",
        REFUSED,
        _GOOD_TOML.replace('grade     = "contract"', 'grade     = "not-covered"')
                  .replace('bounds    = "bounded: unwind=8"\n', "")
                  .replace('status    = "evidenced"', 'status    = "blocked"')
                  .replace(_GOOD_TOML[_GOOD_TOML.index("  [[claim.evidence]]"):
                                      _GOOD_TOML.index("  [claim.self_verify]")], "")
                  .replace('  expect  = "VERIFICATION:- SUCCESSFUL"',
                           '  expect  = "VERIFICATION:- SUCCESSFUL"\n'
                           '  positive_control = "the same pattern against src/b.rs matches"'),
        _GOOD_MD.replace("| a rejects non-minimal encodings |",
                         "| a rule about unblocked_byproduct |")
                .replace("**CONTRACT** (bounded, unwind=8)", "**not-covered**")
                .replace(" | evidenced | ", " | BLOCKED | ")
                .replace(", observed 2026-08-25 |",
                         ", observed 2026-08-25. positive-control: 3 matching lines in "
                         "src/baz.rs |"),
    ),
    ParityCase(
        "predicate-over-must-be-declared-not-narrated",
        "§7.2 — `reviewed over lunch` does not name a sub-list (round-7 probe)",
        REFUSED,
        _GOOD_TOML.replace(
            'clause_source = "spec-document"',
            'clause_source = "spec-document"\nitem_kind = "predicate"\ncovered   = "4/33"'),
        _GOOD_MD.replace("| a rejects non-minimal encodings |",
                         "| `predicate`: reviewed over lunch, 4 of 33 |"),
    ),
    ParityCase(
        "predicate-over-declared-keeps-weight",
        "§7.2 — the positive control for the case above",
        WEIGHTED,
        _GOOD_TOML.replace(
            'clause_source = "spec-document"',
            'clause_source = "spec-document"\nitem_kind = "predicate"\n'
            'over      = "the 33 production harnesses"\ncovered   = "4/33"'),
        _GOOD_MD.replace("| a rejects non-minimal encodings |",
                         "| `predicate`, over: the 33 production harnesses, 4 of 33 |"),
    ),
    ParityCase(
        "an-identifier-containing-the-keyword-is-not-a-declaration",
        "§7.2 — HIS FALSE POSITIVE: `item_kindpredicate` must pass in both",
        WEIGHTED,
        _GOOD_TOML.replace('item      = "src/lib.rs::a"',
                           'item      = "src/lib.rs::item_kindpredicate"'),
        _GOOD_MD.replace("| a rejects non-minimal encodings |",
                         "| a rule about item_kindpredicate |"),
    ),
    ParityCase(
        "annotation-keyword-inside-a-word-is-not-metadata",
        "§4.1 — `on` inside `mutation` must not strip the word (round-7 probe)",
        WEIGHTED,
        _GOOD_TOML.replace('observed   = "check_a FAILED on the padding assertion"',
                           'observed   = "failure after harness mutation"'),
        _GOOD_MD.replace("check_a FAILED on the padding assertion, observed 2026-08-25",
                         "failure after harness mutation, observed 2026-08-25 ."),
    ),
    ParityCase(
        "W4-two-tier-markers-declare-nothing",
        "W4 — a row may state at most one tier",
        REFUSED,
        # A manifest holds one `weight` value, so the analogue of stating two tiers is stating a
        # value that is neither.
        _GOOD_TOML.replace('weight    = "weighted"', 'weight    = "both"'),
        _GOOD_MD.replace(" · **weighted**", " · **weighted** · **unweighted**"),
    ),
    ParityCase(
        "grade-outside-the-closed-vocabulary",
        "§1 — grade is one token from the closed set",
        REFUSED,
        _GOOD_TOML.replace('grade     = "contract"', 'grade     = "derived"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**derived** (bounded, unwind=8)"),
    ),
    ParityCase(
        "not-covered-without-a-positive-control",
        "§4 — positive_control is required on every not-covered row",
        REFUSED,
        _GOOD_TOML.replace('grade     = "contract"', 'grade     = "not-covered"')
                  .replace('bounds    = "bounded: unwind=8"\n', "")
                  .replace('status    = "evidenced"', 'status    = "gap"')
                  .replace(_GOOD_TOML[_GOOD_TOML.index("  [[claim.evidence]]"):
                                      _GOOD_TOML.index("  [claim.self_verify]")], ""),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**not-covered**")
                .replace(" | evidenced | ", " | gap | "),
    ),
    ParityCase(
        "positive-control-does-not-witness-a-contract",
        "§4.1 witness 3 — a positive control witnesses only `not-covered`",
        REFUSED,
        # The witness table is removed; a positive_control is offered in its place on a
        # `contract` row, where §4.1 says it witnesses nothing.
        _GOOD_TOML[:_GOOD_TOML.index("    [claim.self_verify.watched_fail]")].replace(
            '  expect  = "VERIFICATION:- SUCCESSFUL"',
            '  expect  = "VERIFICATION:- SUCCESSFUL"\n'
            '  positive_control = "the same harness against a known-bad fixture"'),
        _GOOD_MD.replace(
            "watched-fail(K mod::proofs::check_a): deleted the minimality check in decode -> "
            "check_a FAILED on the padding assertion, observed 2026-08-25",
            "positive-control(K mod::proofs::check_a): a known-bad fixture -> the harness "
            "reports it, observed 2026-08-25"),
    ),
    ParityCase(
        "refused-row-is-counted-in-neither-tier",
        "§8.1 — a row that claimed weight and was refused is in neither tier",
        REFUSED,
        # An explicit weight claim on a grade that can never carry it: refused by W2.1, and the
        # question this case exists for is what the TOTALS then say.
        _GOOD_TOML.replace('grade     = "contract"', 'grade     = "inspection-argued"')
                  .replace('bounds    = "bounded: unwind=8"\n', ""),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**inspection-argued**"),
    ),
    ParityCase(
        "positive-control-plain-declaration-is-witness-3",
        "§4.1 witness 3 — the PLAIN declared form satisfies it, in both",
        WEIGHTED,
        _GOOD_TOML.replace('grade     = "contract"', 'grade     = "not-covered"')
                  .replace('bounds    = "bounded: unwind=8"\n', "")
                  .replace('status    = "evidenced"', 'status    = "gap"')
                  .replace(_GOOD_TOML[_GOOD_TOML.index("  [[claim.evidence]]"):
                                      _GOOD_TOML.index("  [claim.self_verify]")], "")
                  .replace(_GOOD_TOML[_GOOD_TOML.index("    [claim.self_verify.watched_fail]"):],
                           "")
                  .replace('  expect  = "VERIFICATION:- SUCCESSFUL"',
                           '  expect  = "VERIFICATION:- SUCCESSFUL"\n'
                           '  positive_control = "the known fixture matches 3 lines"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**not-covered**")
                .replace(" | evidenced | ", " | gap | ")
                .replace("watched-fail(K mod::proofs::check_a): deleted the minimality check in "
                         "decode -> check_a FAILED on the padding assertion, observed 2026-08-25",
                         "positive-control: the known fixture matches 3 lines"),
    ),
    ParityCase(
        "positive-control-plain-declaration-of-one-token-names-nothing",
        "§4 — the plain declaration carries the same statement floor in both",
        REFUSED,
        _GOOD_TOML.replace('grade     = "contract"', 'grade     = "not-covered"')
                  .replace('bounds    = "bounded: unwind=8"\n', "")
                  .replace('status    = "evidenced"', 'status    = "gap"')
                  .replace(_GOOD_TOML[_GOOD_TOML.index("  [[claim.evidence]]"):
                                      _GOOD_TOML.index("  [claim.self_verify]")], "")
                  .replace(_GOOD_TOML[_GOOD_TOML.index("    [claim.self_verify.watched_fail]"):],
                           "")
                  .replace('  expect  = "VERIFICATION:- SUCCESSFUL"',
                           '  expect  = "VERIFICATION:- SUCCESSFUL"\n'
                           '  positive_control = "x"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**not-covered**")
                .replace(" | evidenced | ", " | gap | ")
                .replace("watched-fail(K mod::proofs::check_a): deleted the minimality check in "
                         "decode -> check_a FAILED on the padding assertion, observed 2026-08-25",
                         "positive-control: x"),
    ),
    ParityCase(
        "malformed-structured-positive-control-is-refused",
        "§4/§4.1 — a structured control is validated whole, not on its opener (round-10 blocker)",
        REFUSED,
        # The manifest analogue of a dangling opener is a control that is present but says
        # nothing: both are declarations that do not resolve to a control.
        _GOOD_TOML.replace('grade     = "contract"', 'grade     = "not-covered"')
                  .replace('bounds    = "bounded: unwind=8"\n', "")
                  .replace('status    = "evidenced"', 'status    = "gap"')
                  .replace(_GOOD_TOML[_GOOD_TOML.index("  [[claim.evidence]]"):
                                      _GOOD_TOML.index("  [claim.self_verify]")], "")
                  .replace(_GOOD_TOML[_GOOD_TOML.index("    [claim.self_verify.watched_fail]"):],
                           "")
                  .replace('  expect  = "VERIFICATION:- SUCCESSFUL"',
                           '  expect  = "VERIFICATION:- SUCCESSFUL"\n'
                           '  positive_control = "x"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**not-covered**")
                .replace(" | evidenced | ", " | gap | ")
                .replace("watched-fail(K mod::proofs::check_a): deleted the minimality check in "
                         "decode -> check_a FAILED on the padding assertion, observed 2026-08-25",
                         "positive-control("),
    ),
    ParityCase(
        "status-cell-naming-two-statuses",
        "§7.1 — a cell naming two statuses has named none (round-10 sweep)",
        REFUSED,
        # A TOML `status` field holds one value, so the analogue is a value outside the enum.
        _GOOD_TOML.replace('status    = "evidenced"', 'status    = "done-and-gap"'),
        _GOOD_MD.replace(" | evidenced | ", " | evidenced, but really a gap | "),
    ),
    ParityCase(
        "recipe-as-a-backticked-literal-command",
        "§4.2 — a literal command is a recipe reference, and a witness binds to it",
        WEIGHTED,
        _GOOD_TOML.replace('grade     = "contract"', 'grade     = "mechanical"')
                  .replace('bounds    = "bounded: unwind=8"\n', "")
                  .replace('command = "cargo kani --harness check_a"', 'command = "./check.sh"')
                  .replace('of_command = "cargo kani --harness check_a"',
                           'of_command = "./check.sh"'),
        _GOOD_MD.replace("**CONTRACT** (bounded, unwind=8)", "**mechanical**")
                .replace("`K mod::proofs::check_a`", "`./check.sh`")
                .replace("watched-fail(K mod::proofs::check_a)", "watched-fail(./check.sh)"),
    ),
    ParityCase(
        "W5-a-clean-row-is-counted-in-the-weighted-tier",
        "W5 — the counts follow the verdicts",
        WEIGHTED, _GOOD_TOML, _GOOD_MD,
    ),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


# One paired case per member of the shared `CLAUSE_SOURCES` enum, GENERATED from the set rather
# than typed out — so a token added to the shared vocabulary automatically acquires a parity case
# and cannot be accepted by one representation and rejected by the other. `test-name` and `none`
# are the two reserved to mean unweightable, so their expected verdict is REFUSED.
from acceptance_grammar import (  # noqa: E402
    CLAUSE_SOURCES,
    CLAUSE_SOURCES_UNWEIGHTABLE,
)

for _cs in sorted(CLAUSE_SOURCES):
    CASES.append(ParityCase(
        f"clause_source-{_cs}",
        f"W2.3 — the closed clause_source enum, token {_cs!r}",
        REFUSED if _cs in CLAUSE_SOURCES_UNWEIGHTABLE else WEIGHTED,
        _GOOD_TOML.replace('clause_source = "spec-document"', f'clause_source = "{_cs}"'),
        _GOOD_MD.replace(" | S-1 (spec-document) | ", f" | S-1 ({_cs}) | "),
    ))


def _check_inventory_case(obligation: str, case: str, known: set[str]) -> list[str]:
    """One cited case: a live ParityCase name, or `selftest:<fixture>` for an obligation only one
    representation can carry (the battery asserts agreement; there the two correctly differ)."""
    if case.startswith("selftest:"):
        fixture = case[len("selftest:"):]
        here = Path(__file__).resolve().parent
        sources = ((here / "check_acceptance.py").read_text(encoding="utf-8")
                   + (here / "check_ledger.py").read_text(encoding="utf-8"))
        if fixture not in sources:
            return [f"OBLIGATIONS.md: {obligation!r} cites fixture {fixture!r}, which appears in "
                    f"neither checker's selftest"]
        return []
    if case not in known:
        return [f"OBLIGATIONS.md: {obligation!r} names parity case {case!r}, which does not exist "
                f"in this battery"]
    return []


def audit_refused_row_counting(verbose: bool = True) -> list[str]:
    """§8.1: a row that claimed weight and was refused is counted in NEITHER tier.

    The battery's verdict classes are WEIGHTED and REFUSED, so a refusal case proves the verdict
    and says nothing about the COUNTING -- and the counting is what W5 publishes. This asserts the
    tier totals directly, in both representations, for a row that explicitly claimed weight and
    drew a refusal. The inventory's "refused row counted in neither tier" obligation cites this."""
    failures: list[str] = []
    case = next((c for c in CASES if c.name == "refused-row-is-counted-in-neither-tier"), None)
    if case is None:
        return ["the refused-row counting case is missing from the battery"]

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "acceptance.toml"
        path.write_text(MANIFEST_HEAD + case.toml, encoding="utf-8")
        rep = CA.validate(path, strict=False)
    t_w = getattr(rep, "n_weighted", 0)
    t_u = getattr(rep, "n_unweighted", 0)
    if rep.ok() or t_w or t_u:
        failures.append(
            f"TOML: a refused claim must be counted in neither tier — got weighted={t_w}, "
            f"unweighted={t_u}, ok={rep.ok()}")

    rows = CL.check_file_text("\n".join([MD_HEADER, MD_SEP, case.md]))
    row = rows[0]
    if not row.refused or row.weighted or row.pending:
        failures.append(
            f"MD: a refused row must be refused and in neither tier — got refused={row.refused}, "
            f"weighted={row.weighted}, pending={row.pending}")

    for f in failures:
        if verbose:
            print(f"REFUSED-COUNTING FAIL: {f}")
    if verbose and not failures:
        print("REFUSED-COUNTING PASS: a refused row is excluded from both tier totals, "
              "both representations")
    return failures


def audit_obligations_inventory(verbose: bool = True) -> list[str]:
    """`maintainers/OBLIGATIONS.md` enumerates every obligation that gates the weighted tier, walked
    from the SPEC rather than from the code. This asserts the two stay in step.

    THE METHOD GAP THIS CLOSES (review, round 8). Seven rounds were closed by auditing mechanisms —
    the regexes, the shared-module wiring, the separator classes. Each audit was complete over the
    mechanism it enumerated, and that is exactly why it missed `positive_control`: implemented
    with a substring `in` rather than a regex, it was not in the set being audited, so no amount
    of rigour applied to regexes was ever going to reach it. Enumerating from the spec side fixes
    the frame — the obligations are defined there, in a form that does not depend on how any of
    them happens to be implemented.

    Checked here: every inventory row names a parity case that EXISTS. Not checked: that the
    inventory lists every obligation the spec states — that walk is human work, and claiming
    otherwise would be this file's own version of the defect.

    THAT CAVEAT HAS BEEN CASHED, which is the point of writing it down in advance. A cold reader
    found §0.5's "tests witness points, so a test is never `contract`" — normative from the day it
    was written, enforced nowhere, and absent from BOTH tables of OBLIGATIONS.md, so the file's own
    completeness claim was false for it. Enforced and listed as of 2026-08-26. The lesson is not
    that the inventory failed; it is that a human walk of a spec misses things, and saying so in
    advance is the difference between a limit and an excuse."""
    path = Path(__file__).resolve().parent.parent / "maintainers" / "OBLIGATIONS.md"
    if not path.is_file():
        return [f"{path.name} is missing — the obligations inventory is part of the gate"]

    known = {c.name for c in CASES}
    failures: list[str] = []
    rows = 0
    in_inventory = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## The inventory"):
            in_inventory = True
            continue
        if in_inventory and line.startswith("## "):
            break
        if not in_inventory or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5 or cells[0] in ("obligation",) or set(cells[0]) <= set("-: "):
            continue
        rows += 1
        obligation, cell = cells[0], cells[4]
        # A row may cite several cases (an obligation with more than one accepted syntax needs
        # one per syntax, or it is only half mapped -- review, round 9).
        names = [c.strip().strip("`") for c in cell.split("·") if c.strip()]
        for case in names:
            failures.extend(_check_inventory_case(obligation, case, known))
        if not names:
            failures.append(f"OBLIGATIONS.md: {obligation!r} names no parity case")
        if False:
            # An obligation only ONE representation can carry cannot have a paired case: the
            # battery asserts the two verdicts AGREE, and here they correctly differ. Such a row
            # cites a single-representation fixture instead, and the audit checks it is real.
            pass
        # An obligation must be enforced somewhere, or be an explicit n/a with a reason.
        for col, rep in ((cells[2], "manifest"), (cells[3], "rendering")):
            if not col:
                failures.append(f"OBLIGATIONS.md: {obligation!r} leaves the {rep} column blank — "
                                f"name the enforcing function or say 'n/a — <why>'")
            elif col.startswith("n/a") and "—" not in col and "--" not in col:
                failures.append(f"OBLIGATIONS.md: {obligation!r} claims n/a for the {rep} with no "
                                f"reason; a blank exemption is a silent row")
    if not rows:
        failures.append("OBLIGATIONS.md: no inventory rows parsed — the table shape changed")
    for f in failures:
        if verbose:
            print(f"INVENTORY FAIL: {f}")
    if verbose and not failures:
        print(f"INVENTORY PASS: {rows} obligations, each with an enforcement site in both "
              f"representations (or a stated n/a) and a live parity case")
    return failures


def audit_case_minimality(verbose: bool = True) -> list[str]:
    """Every REFUSED paired case must be MINIMALLY invalid — failing for exactly ONE obligation,
    on both sides.

    review, round 8: the `blocked-by` case's Markdown half failed for two reasons (no blocked-by AND
    no positive control) while its TOML half supplied the control. Delete the blocked-by rule and
    the pair still reads green, so the case was not testing what it named. A multi-invalid fixture
    is a test that cannot fail for its stated reason, which is the same defect as a recipe nobody
    watched fail — one level up, in the harness.

    What this checks is REASON COUNT, not reason identity: the two representations legitimately
    word their refusals differently, and comparing text would just re-import the wording coupling
    the battery exists to avoid. One reason each side, and the case name says which."""
    failures: list[str] = []
    for case in CASES:
        if case.expect != REFUSED:
            continue
        _, treasons = toml_verdict(case.toml)
        _, mreasons = md_verdict(case.md)
        for side, reasons in (("TOML", treasons), ("MD", mreasons)):
            if len(reasons) > 1:
                failures.append(
                    f"NOT MINIMAL {case.name} [{side}]: fails for {len(reasons)} obligations, so "
                    f"it cannot witness the one it names — {reasons}"
                )
                if verbose:
                    print(f"MINIMALITY FAIL: {case.name} [{side}]: {len(reasons)} reasons")
            elif not reasons:
                failures.append(
                    f"NO REASON {case.name} [{side}]: expected REFUSED but reported no reason")
                if verbose:
                    print(f"MINIMALITY FAIL: {case.name} [{side}]: refused with no reason")
    if verbose and not failures:
        n = sum(1 for c in CASES if c.expect == REFUSED)
        print(f"MINIMALITY PASS: all {n} refusal cases fail for exactly one obligation per side")
    return failures


def run_battery(verbose: bool = True) -> list[str]:
    failures: list[str] = []
    for case in CASES:
        tv, treasons = toml_verdict(case.toml)
        mv, mreasons = md_verdict(case.md)
        if tv != mv:
            failures.append(
                f"PARITY BREAK {case.name} [{case.obligation}]: TOML={tv} MD={mv}\n"
                f"    TOML said: {treasons or '(clean)'}\n"
                f"    MD   said: {mreasons or '(clean)'}"
            )
            if verbose:
                print(f"PARITY FAIL: {case.name}: TOML={tv} MD={mv}")
        elif tv != case.expect:
            failures.append(
                f"BOTH WRONG {case.name} [{case.obligation}]: expected {case.expect}, "
                f"both said {tv}\n    reasons: {treasons or mreasons or '(clean)'}"
            )
            if verbose:
                print(f"SELFTEST FAIL: {case.name}: expected {case.expect}, both said {tv}")
        elif verbose:
            print(f"PARITY PASS: {case.name} -> both {tv}  [{case.obligation}]")
    return failures


def prove_the_harness_can_break(verbose: bool = True) -> list[str]:
    """Watched-red, on the review's own probe. Monkeypatch the Markdown `out-of-scope` rule back to the
    behaviour it had before this round -- nonemptiness only -- and assert that the battery above
    REPORTS the break rather than passing. Without this, "parity holds" is a claim from a harness
    nobody has seen fail, which is the exact thing §4.1 refuses to accept about a recipe."""
    case = next(c for c in CASES if c.name == "S7.1-out-of-scope-with-a-locator-free-source")
    original = CL.check_out_of_scope

    def pre_fix_check_out_of_scope(verify_text, row_text=""):
        # verbatim the pre-2026-08-25 rule
        if verify_text is None or not verify_text.strip():
            return "out-of-scope row does not cite a source (verify cell is empty)"
        return None

    CL.check_out_of_scope = pre_fix_check_out_of_scope
    try:
        tv, _ = toml_verdict(case.toml)
        mv, _ = md_verdict(case.md)
    finally:
        CL.check_out_of_scope = original

    if tv == REFUSED and mv == WEIGHTED:
        if verbose:
            print("WATCHED-BREAK PASS: with the pre-fix Markdown rule restored, the review's O-1 row is "
                  f"MD={mv} against TOML={tv} — the harness sees the break it was built for")
        return []
    if verbose:
        print(f"WATCHED-BREAK FAIL: expected TOML={REFUSED} MD={WEIGHTED}, got TOML={tv} MD={mv}")
    return [
        f"the watched-break proof did not reproduce the pre-fix divergence "
        f"(got TOML={tv} MD={mv}) — this harness has not been shown able to fail, so a green "
        f"run from it witnesses nothing"
    ]


def audit_shared_imports(verbose: bool = True, root: str | Path | None = None) -> list[str]:
    """Every name a checker takes from `acceptance_grammar` must be REFERENCED somewhere else in
    that file.

    This exists because of the defect the review found in round 4: `check_ledger.py` imported
    `bounds_token` and `has_bounds_tail`, referenced neither, and kept its own weaker bounds
    grammar. The import line READ like parity. Nothing else did. An imported-but-unreferenced
    shared helper is a duplicate implementation with a single-source-of-truth alibi, and it is
    invisible to the paired battery, because both checkers can agree on every case the battery
    happens to contain while disagreeing on the shape it does not.

    WHAT IT ACTUALLY CHECKS -- stated precisely, because the first version of this docstring
    overclaimed on both counts and the review caught it in round 5:

      * It counts REFERENCES, not calls. A name that appears anywhere -- including in a bare
        alias assignment such as `LOCAL = shared_name` -- counts as used. It cannot tell a
        genuine call site from a re-export, so **alias forwarding is not detected**: a checker
        that binds a shared helper to a local name and then never calls the local name passes
        this audit. The earlier docstring said "must actually be CALLED"; it never checked that.
      * It reports a name imported MORE THAN ONCE. Harmless at runtime, which is why duplicates
        survive unnoticed and accumulate.
      * It sees `from acceptance_grammar import X` AND `import acceptance_grammar [as A]`. For
        the second form it requires at least one `A.<something>` attribute access, and counts
        `A.X` as a reference to X as well. Two rounds of regression here: an earlier version
        collected aliases but consulted them only while resolving from-imported names, and a
        later duplicate-import insertion misattached the alias branch to an `if verbose:` so it
        never ran at all. Both times the proof stayed green because it walked its own copy of the
        AST. The traversal is `_audit_source`, there is one of it, and every proof calls it.

    WHAT IT STILL CANNOT SEE, and this list is the honest one:

      * A rule that SHOULD be shared and was never routed through the module at all. Nothing here
        looks for duplicated logic; it only inspects names already taken from the shared module.
      * Alias forwarding, per above.
      * Dynamic access (`getattr(acceptance_grammar, name)`).

    So this audits WIRING and the battery audits BEHAVIOUR, and neither substitutes for the
    other."""
    failures: list[str] = []
    root = Path(root) if root is not None else Path(__file__).resolve().parent
    for name in ("check_ledger.py", "check_acceptance.py"):
        path = root / name
        if not path.is_file():
            continue
        found = _audit_source(name, path.read_text(encoding="utf-8"))
        failures.extend(found)
        if verbose:
            for f in found:
                print(f"WIRING FAIL: {f}")
            if not found:
                print(f"WIRING PASS: {name}: every shared-grammar import is referenced")
    return failures


def _audit_source(name: str, src: str) -> list[str]:
    """THE traversal. One copy, used by `audit_shared_imports` on the real checkers and by the
    watched-break proofs on planted source.

    It was duplicated: the proofs carried their own walk, so they proved a COPY behaved correctly
    and said nothing about the function that runs in the gate. That is the night's own lesson
    turned on the tool that enforces it -- and it cost exactly what it always costs. A
    duplicate-import check inserted into the real function misattached the module-alias branch to
    an `if verbose:`, so a pure unused `import acceptance_grammar as ag` reported clean, and the
    proof stayed green because it was walking its own copy (review, round 11)."""
    import ast

    tree = ast.parse(src)
    imported: dict[str, str] = {}      # local binding -> name in acceptance_grammar
    module_aliases: set[str] = set()   # `import acceptance_grammar as A` -> {"A"}
    seen_bindings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "acceptance_grammar":
            for alias in node.names:
                imported[alias.asname or alias.name] = alias.name
                seen_bindings.append(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "acceptance_grammar":
                    module_aliases.add(alias.asname or alias.name)

    refs: dict[str, int] = {k: 0 for k in imported}
    alias_refs: dict[str, int] = {a: 0 for a in module_aliases}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in refs:
            refs[node.id] += 1
        elif isinstance(node, ast.Attribute):
            base = node.value
            if isinstance(base, ast.Name) and base.id in alias_refs:
                # `ag.bounds_token` is a use of the MODULE, and of that name if it was also
                # from-imported.
                alias_refs[base.id] += 1
                if node.attr in refs:
                    refs[node.attr] += 1

    failures: list[str] = []
    # A name imported twice. Harmless at runtime, which is exactly why it survives unnoticed.
    for dup in sorted({b for b in seen_bindings if seen_bindings.count(b) > 1}):
        failures.append(f"{name}: imports {dup!r} from acceptance_grammar more than once")
    for local, origin in sorted(imported.items()):
        if refs[local] == 0:
            failures.append(
                f"{name}: takes {origin!r} from acceptance_grammar and never references it — "
                f"either use it (and delete whatever local rule stood in for it) or drop the "
                f"import; a shared helper nobody uses is a duplicate rule with an alibi"
            )
    # A module alias with no attribute access is the same defect wearing the other import form.
    # Checked independently of `imported`, because a file may carry ONLY the alias -- in which
    # case the loop above inspects nothing.
    for alias, n in sorted(alias_refs.items()):
        if n == 0:
            failures.append(
                f"{name}: imports the acceptance_grammar module as {alias!r} and never accesses "
                f"anything through it — drop the import or use it"
            )
    return failures


AUDITED_SOURCES = ("check_ledger.py", "check_acceptance.py", "acceptance_grammar.py",
                   "check_execute.py", "check_parity_selftest.py")


def find_shadowed_definitions(name: str, src: str) -> list[str]:
    """Top-level names DEFINED MORE THAN ONCE in one module. Python binds the last one, silently.

    THE CLASS, and it has now cost this repo twice in one night:

      * round 4 — `check_ledger.py` imported `bounds_token`/`has_bounds_tail` and kept its own
        weaker bounds grammar. The shared rule was shadowed by a local one.
      * round 12 — a repaired `audit_shared_imports` was added while the OLD definition stayed
        below it. Python bound the old one, so the GATE ran the broken traversal while every
        proof passed against the repaired helper it called directly. The repair existed, was
        correct, and was dead.

    Both are the same shape: two implementations of one name, and the wrong one wins. An
    imported-but-unused helper is the cross-module form; a duplicate `def` is the within-module
    form. The first has been guarded since round 4; this guards the second.

    Scope and limit: TOP-LEVEL `def`, `class`, and assignment names — plain, annotated, and
    tuple/list-unpacked, recursively. It does NOT see conditional definitions, methods, names
    rebound inside a function, or `for`/`with`/`import` bindings. A redefinition under an `if` is
    sometimes deliberate, and flagging it would make the guard something people switch off. That
    list is the honest scope: the earlier version of this sentence said "assignment names" while
    the code handled only direct `ast.Name` targets of `ast.Assign`, so two of the forms it
    claimed — an annotated rebind and a tuple-unpack rebind — evaded it (review, round 13)."""
    import ast

    def bound_names(target: ast.expr) -> list[str]:
        """Every name an assignment target binds, unpacking nested tuples and lists.

        `x, y = ...` and `[x, y] = ...` bind through a Tuple/List node whose elements may
        themselves be Tuple/List, so this recurses. Taking only direct `ast.Name` targets --
        which is what this did -- let `x: int = 5` and `x, y = 5, 6` rebind a name defined above
        without the guard noticing."""
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, (ast.Tuple, ast.List)):
            return [n for el in target.elts for n in bound_names(el)]
        if isinstance(target, ast.Starred):
            return bound_names(target.value)
        return []   # Attribute/Subscript targets bind no module-level NAME

    tree = ast.parse(src)
    seen: dict[str, int] = {}
    for node in tree.body:
        names: list[str] = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [n for t in node.targets for n in bound_names(t)]
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            # An ANNOTATED rebind is still a rebind. Skipped entirely before, so `x: int = 5`
            # after `def x(): ...` was invisible. A bare `x: int` binds nothing and is skipped.
            names = bound_names(node.target)
        for n in names:
            seen[n] = seen.get(n, 0) + 1
    return [
        f"{name}: {n!r} is defined {c} times at top level — Python binds the LAST one, so the "
        f"others are dead. A repair added beside its stale twin is a repair that does not run"
        for n, c in sorted(seen.items()) if c > 1
    ]


def audit_shadowed_definitions(verbose: bool = True) -> list[str]:
    """Run `find_shadowed_definitions` over every tool in this directory."""
    here = Path(__file__).resolve().parent
    failures: list[str] = []
    for name in AUDITED_SOURCES:
        path = here / name
        if not path.is_file():
            continue
        found = find_shadowed_definitions(name, path.read_text(encoding="utf-8"))
        failures.extend(found)
        if verbose:
            for f in found:
                print(f"SHADOW FAIL: {f}")
    if verbose and not failures:
        print(f"SHADOW PASS: no top-level name is defined twice in any of "
              f"{len(AUDITED_SOURCES)} tool sources")
    return failures


def prove_the_shadow_guard_can_fail(verbose: bool = True) -> list[str]:
    """Watched-red for the guard above, on planted source, through the same function the audit
    calls -- not a copy of it."""
    failures: list[str] = []
    dup = ("def audit_shared_imports():\n    return 1\n\n\n"
           "def audit_shared_imports():\n    return 2\n")
    found = find_shadowed_definitions("planted.py", dup)
    if not any("defined 2 times" in f for f in found):
        failures.append(f"the shadow guard does not detect a duplicated def — got {found}")
        print("SHADOW-BREAK FAIL: duplicate def not detected", file=sys.stderr)
    elif verbose:
        print("SHADOW-BREAK PASS: a top-level name defined twice is detected")

    # The stated-scope plants that evaded the first version (review, round 13).
    for label, planted in (
        ("an annotated rebind of a def", "def x():\n    return 1\n\n\nx: int = 5\n"),
        ("a tuple-unpack rebind of a def", "def x():\n    return 1\n\n\nx, y = 5, 6\n"),
        ("a list-unpack rebind of a def", "def x():\n    return 1\n\n\n[x, y] = [5, 6]\n"),
    ):
        if not any("defined 2 times" in f
                   for f in find_shadowed_definitions("planted.py", planted)):
            failures.append(f"the shadow guard does not detect {label}")
            print(f"SHADOW-BREAK FAIL: {label} not detected", file=sys.stderr)
        elif verbose:
            print(f"SHADOW-BREAK PASS: {label} is detected")

    single = "def audit_shared_imports():\n    return 1\n"
    if find_shadowed_definitions("planted.py", single):
        failures.append("the shadow guard reports a singly-defined name")
        print("SHADOW-BREAK FAIL: false positive on a single def", file=sys.stderr)
    elif verbose:
        print("SHADOW-BREAK PASS: a singly-defined name is accepted")
    # ...and a DISTINCT tuple unpack must not be reported: the guard counts rebinds, not unpacks.
    if find_shadowed_definitions("planted.py", "a, b = 1, 2\n"):
        failures.append("the shadow guard reports a plain tuple assignment")
        print("SHADOW-BREAK FAIL: false positive on a tuple assignment", file=sys.stderr)
    elif verbose:
        print("SHADOW-BREAK PASS: a plain tuple assignment is accepted")
    return failures


def prove_the_wiring_audit_can_fail(verbose: bool = True) -> list[str]:
    """Watched-red for the wiring audit, over the three defects it claims to detect and the two
    clean forms it must not report.

    Every case calls `audit_shared_imports` — the OUTER production binding, the exact name the
    gate calls — over a directory of planted checkers. Two rounds were lost to proofs that did
    not: round 11's walked their own AST, and round 12's called the inner `_audit_source`, which
    is how a stale duplicate `audit_shared_imports` shadowed the repaired one and ran in the gate
    while every proof passed. A proof that reaches past the production name proves whatever it
    reached instead."""
    failures: list[str] = []
    defects = [
        ("an imported-and-ignored helper",
         "from acceptance_grammar import bounds_token\nX = 1\n",
         "never references it"),
        ("a module alias imported and never accessed",
         "import acceptance_grammar as ag\nX = 1\n",
         "never accesses anything through it"),
        ("a name imported twice",
         "from acceptance_grammar import bounds_token\n"
         "from acceptance_grammar import bounds_token\n"
         "def f(v):\n    return bounds_token(v)\n",
         "more than once"),
    ]
    clean = [
        ("a used from-import",
         "from acceptance_grammar import bounds_token\ndef f(v):\n    return bounds_token(v)\n"),
        ("a used module alias",
         "import acceptance_grammar as ag\ndef f(v):\n    return ag.bounds_token(v)\n"),
    ]

    def audit_planted(src: str) -> list[str]:
        """Run the PRODUCTION entry point over a planted `check_ledger.py`."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "check_ledger.py").write_text(src, encoding="utf-8")
            (d / "check_acceptance.py").write_text("X = 1\n", encoding="utf-8")
            return audit_shared_imports(verbose=False, root=d)

    for label, src, expected in defects:
        found = audit_planted(src)
        if not any(expected in f for f in found):
            failures.append(
                f"the wiring audit does not detect {label} — expected a failure mentioning "
                f"{expected!r}, got {found}")
            print(f"WIRING-BREAK FAIL: {label} not detected", file=sys.stderr)
        elif verbose:
            print(f"WIRING-BREAK PASS: {label} is detected")

    # The positive controls, so the three above cannot pass by the audit failing everything.
    for label, src in clean:
        found = audit_planted(src)
        if found:
            failures.append(f"the wiring audit reports {label} as a failure: {found}")
            print(f"WIRING-BREAK FAIL: {label} wrongly reported", file=sys.stderr)
        elif verbose:
            print(f"WIRING-BREAK PASS: {label} is accepted")
    return failures


def main(argv: list[str]) -> int:
    verbose = "--quiet" not in argv
    if "--prove-break" in argv:
        return 1 if prove_the_harness_can_break(verbose) else 0
    if "--audit-imports" in argv:
        return 1 if (audit_shared_imports(verbose)
                     + prove_the_wiring_audit_can_fail(verbose)) else 0

    failures = run_battery(verbose)
    # The proof runs on every invocation, so it cannot be lost by forgetting a flag.
    failures += prove_the_harness_can_break(verbose)
    failures += audit_obligations_inventory(verbose)
    failures += audit_refused_row_counting(verbose)
    failures += audit_case_minimality(verbose)
    failures += audit_shared_imports(verbose)
    failures += audit_shadowed_definitions(verbose)
    failures += prove_the_shadow_guard_can_fail(verbose)
    failures += prove_the_wiring_audit_can_fail(verbose)

    print(f"check_parity: {len(CASES)} paired cases + 1 watched-break proof + "
          f"obligations inventory + minimality audit + shared-import wiring audit + "
          f"shadowed-definition guard (+11 watched-break proofs), {len(failures)} failed")
    for f in failures:
        print(f"  {f}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
