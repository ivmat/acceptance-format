#!/usr/bin/env python3
"""check_ledger.py — enforce the row-level rules of spec/core.md on the
MARKDOWN coverage-ledger tables in an envelope file.

Pure python3 stdlib, no dependencies.

A "ledger row" is any markdown-table row whose FIRST cell is a backticked
identifier matching ``^[A-Z]+-[A-Z0-9-]+$`` (e.g. ``DER-F-6``, ``KD-L-1``,
``DER-C-SETOF-3``). All other tables (recipe tables, summary/usefulness
tables, legend tables) are ignored automatically because their first cell is
not a bare backticked identifier.

Checks implemented (core.md sections 1-7), each printed as
``FILE:ROW_ID: LEVEL: message``:

  1. Grade token present and closed (section 1, section 7 "one row, one claim").
  2. Deciding recipe required for contract | probe | test-only | mechanical |
     not-covered (section 3).
  3. Bounds declaration required on contract | probe (section 5).
  4. positive_control required on not-covered absence checks (section 4).
  5. out-of-scope / unspecified companion fields (section 1).

Usage:
    python3 tools/check_ledger.py <file.md> [<file2.md> ...]
    python3 tools/check_ledger.py --selftest
"""

from __future__ import annotations

import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# The rules that must mean the same thing in BOTH representations live in one module, imported
# by this checker and by check_acceptance.py. the round-3 review probe is why: `out-of-scope` had
# drifted into two different rules, and THIS copy -- the one governing the representation a human
# reads -- was the weaker, granting weight where the manifest validator refused it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from acceptance_grammar import (  # noqa: E402
    CLAUSE_SOURCES,
    CLAUSE_SOURCES_UNWEIGHTABLE,
    GRADES,
    GRADES_REQUIRING_BOUNDS as NEEDS_BOUNDS,
    GRADES_REQUIRING_RECIPE as NEEDS_RECIPE,
    ISO_DATE_INLINE_RE,
    SCOPE_REF_EXPECTATION,
    UNWEIGHTABLE_GRADES,
    bounds_token,
    has_bounds_tail,
    NOT_WORD_AFTER,
    NOT_WORD_BEFORE,
    SEP_DECLARATIVE,
    STATUSES,
    declaration_re,
    is_phrase,
    strip_witness_metadata,
    is_scope_locator,
    status_grade_incoherence,
)

# ---------------------------------------------------------------------------
# The closed grade vocabulary (spec section 1).
# ---------------------------------------------------------------------------

# Recipe-letter prefixes recognised in backticked verify-cell tokens
# (`K <H>`, `R <H>`, `T <filter>`, `N <thm>`, `G`, `A <pattern>`, `D <ref>`,
# `M`, `F`, `Y`).
#
# core.md §4.2: "`<LETTER>` is a single uppercase letter declared in the RENDERING'S OWN recipe
# table" -- not a global alphabet this checker invents. This set is the FALLBACK, used only when a
# document declares no recipe table of its own (e.g. a bare fixture, in this file's own selftest).
# Every function below that judges a recipe letter takes a `letters` parameter defaulting to this
# constant; `declared_recipe_letters`, below, is how a real document's own table overrides it.
RECIPE_LETTERS = set("KRTNGADMFYE")

# core.md §4.2 (added 2026-08-25 after the round-2 review probe): a recipe reference is
# `<LETTER>` or `<LETTER> <ARG>`, and <ARG> must be a COMMAND BODY, not a placeholder.
# Until this existed, `K ???` parsed as a recipe: it satisfied the verify-cell requirement AND
# the witness-binding requirement at once, because the same nonsense string appeared on both
# sides. `watched-fail(K ???): changed anything -> saw red` passed clean and counted WEIGHTED.
# What is checkable here is SHAPE. That a plausible-looking recipe is the RIGHT recipe for the
# row is not checkable and is not claimed -- see §4.2.
RECIPE_ARG_WORD_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:/+=-]+")
# `<H>` is the recipe TABLE's metavariable, not an instance of it. A row that cites the grammar
# instead of a value has named no command.
RECIPE_ARG_METAVAR_RE = re.compile(r"^<[^<>]*>$")
RECIPE_ARG_PLACEHOLDERS = {
    "todo", "tbd", "tba", "tbc", "xxx", "fixme", "n/a", "na", "none",
    "any", "some", "something", "etc", "...",
}

# §4.2's SECOND accepted form: a backticked LITERAL command (`cargo fmt --check`). It was
# recognised by a hardcoded whitelist of program names, which refused every honest row invoking
# anything not on the list -- `./check.sh` among them, found by the der mutation pass in real use
# across 114 Kani invocations. And `recipe_tokens` never returned a literal command at all, so no
# watched-fail witness could BIND to one: a row using the form the spec offers could satisfy §3
# and never satisfy §4.1. The rule is structural now, not a list.
#
# What makes a token a command invocation rather than a row id (`DER-F-8`) or a harness path
# (`mod::proofs::foo`): a leading `./` or `/`, a script extension, or a program name FOLLOWED BY
# ARGUMENTS. A bare single word is none of these -- which also retires the "backticked `cargo`
# alone is a recipe" limit this file carried since round 7.
COMMAND_WORD_RE = re.compile(r"^[A-Za-z0-9_][\w./+-]*$")
SCRIPT_EXT_RE = re.compile(r"\.(?:sh|bash|zsh|py|pl|rb)$", re.IGNORECASE)
ENV_PREFIX_RE = re.compile(r"^[A-Z_][A-Z0-9_]*=\S*$")

# §5 in a RENDERING. There is no `bounds` FIELD here, so the declaration has to be located in
# the row first -- but once located it is judged by `acceptance_grammar.bounds_token` and
# `has_bounds_tail`, the SAME functions the manifest validator calls.
#
# This file used to carry its own three regexes for the job (BOUNDS_RE, BOUNDS_TOKEN_RE,
# BOUNDS_LIMIT_RE). They were deleted 2026-08-25 (fourth round) after the review found that they had
# quietly become a second, WEAKER grammar while the shared helpers sat imported and never called:
#
#     | `B-1` | ... | **CONTRACT** (unwind=8) · **weighted** | ... |
#
# passed WEIGHTED -- `unwind` was one of BOUNDS_RE's accepted alternatives, so a LIMIT with no
# boundedness token satisfied a boundedness check -- while its TOML twin `bounds = "unwind=8"`
# was refused for having no leading token. That is §5's exact confusion, enforced by the checker.
# An imported-but-uncalled helper is worse than no helper: it reads as parity at the import line
# and is a duplicate implementation everywhere else.
BOUNDS_TOKEN_ANCHOR_RE = re.compile(r"\b(?:un)?bounded\b", re.IGNORECASE)
# Where a rendered bounds declaration ends: the closing bracket of its parenthetical, a cell
# boundary, a `·` separator, or the end of a sentence.
BOUNDS_DECL_END_RE = re.compile(r"[)\]|·]|\.\s|\Z")

SECTION_REF_RE = re.compile(r"§\s*\d|\bsee\s+§", re.IGNORECASE)

# A ledger row id: an uppercase prefix plus one or more hyphen-separated segments.
# The last segment MAY carry a lowercase sub-item suffix (`R-3a`, `DER-F-8b`) — sub-items
# are how a real ledger splits one review ask into the functions it names, and every one of
# them is a graded row. The pre-2026-08-25 pattern was `^[A-Z]+-[A-Z0-9-]+$`, which SILENTLY
# skipped a whole run of another subject's lowercase-suffixed sub-item rows while the file
# reported "0 errors" — an unchecked row is indistinguishable from a clean one.
# Still excluded, deliberately: harness paths (`x509_validity::parse_never_panics`), file
# names (`args/mod.rs`), and lowercase-initial identifiers, none of which are ledger rows.
ID_INNER_RE = re.compile(r"^[A-Z][A-Z0-9]*(-[A-Za-z0-9]+)+$")

# GRADE STRENGTH: does the evidence decide the subject's own rule?  Grouped from the grade token.
#
# THE WORDS HERE ARE DELIBERATELY NOT "weighted"/"admitted", and that is the whole point. This
# grouping used to report itself with those two words while the summary line directly above used
# the SAME two words for the spec's weight tier (W1-W5) — two different partitions, one
# vocabulary, on adjacent lines of one report. A cold reader took the grade split for the weight
# split within the first hour and quoted the wrong pair of numbers as a headline. The format's
# entire subject is claims that read as something stronger than they are; shipping a tool that
# invites the confusion in its own output was ours, not the reader's.
#
# The two answer different questions and can disagree per row: a `not-covered` row is
# ASSERTED-grade yet typically CARRIES WEIGHT, because its own stated claim ("nothing here decides
# this") has a deciding recipe. (The retired `CONTRACT+L4` ladder token, when it existed, also
# counted as deciding-grade "contract" -- moot now that the ladder is gone.)
DECIDING_GRADES = {"contract", "mechanical"}


def grade_strength(grade: str | None) -> str | None:
    """'deciding' / 'asserted' by grade token; None when the grade is unresolved."""
    if grade is None:
        return None
    return "deciding" if grade in DECIDING_GRADES else "asserted"


# An id-shaped first cell WITHOUT backticks. Deliberately narrow: an uppercase-initial token of
# id shape and nothing else, so an ordinary prose first cell ("Total", "Notes") is not dragged in.
# It exists only to REPORT the row as unchecked, never to check it — the ledger-row pattern still
# requires the backticks.
UNBACKTICKED_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Za-z0-9]+)+$")

BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
TIER_MARKERS = {"unweighted", "weighted"}
BACKTICK_RE = re.compile(r"`([^`]*)`")

# ---------------------------------------------------------------------------
# W4 tier markers. The marker MUST be an explicit textual token on the row --
# a `UNWEIGHTED` label, a `[U]`/`[W]` prefix, or a dedicated weight column
# (spec W4). It is NOT "the word appears somewhere in the row's prose": under
# that reading a `**CONTRACT**` row with no recipe and no bounds passed clean
# merely for containing the phrase "unlike the unweighted rows in section 4",
# which exempted it from every weighted-tier obligation while still rendering
# to a human as the format's strongest grade. That is the W4 failure the spec
# calls the most consequential error in the format, reached from the other side.
# ---------------------------------------------------------------------------

# A weight-column cell: the tier token leads the cell, optionally bolded and
# optionally preceded by a warning glyph, and may be followed by prose.
WEIGHT_CELL_RE = re.compile(r"^[^A-Za-z0-9]*(?:\*\*)?(unweighted|weighted)\b", re.IGNORECASE)
# A `[U]`/`[W]` prefix marker, standalone.
BRACKET_TIER_RE = re.compile(r"(?<![A-Za-z0-9])\[([UW])\](?![A-Za-z0-9])")
# A RESERVED clause-source token (`test-name`, `none`) as a DELIMITED token -- backticked,
# bolded or italicised -- for the fallback path where a table has no clause column. Not the bare
# phrase in a sentence, which may as easily be a denial ("not read off a test name") as an
# admission. DERIVED from the shared set, not typed: this was a hand-written pattern for ONE of
# the two reserved tokens, so `none` was never detected here at all and `S-1 (test-name)` -- the
# undelimited form a real clause cell uses -- slipped past the delimiter requirement. Both were
# refused by the manifest validator throughout.
RESERVED_CLAUSE_TOKEN_RE = re.compile(
    r"(?:`|\*|\*\*|_)(?:"
    + "|".join(re.escape(t) for t in sorted(CLAUSE_SOURCES_UNWEIGHTABLE, key=len, reverse=True))
    + r")(?:`|\*|\*\*|_)",
    re.IGNORECASE,
)

# core.md §4.1 (P2, adopted 2026-08-25): a weighted recipe must carry a witness that it has
# been WATCHED TO FAIL. In a markdown rendering the witness is named in the row -- a positive
# control, a mutation control, or an explicit watched-fail note. Deliberately NOT matched: bare
# "control" (as in "control flow"), "controlled" on its own, or a green/green control, none of
# which witnesses the oracle catching anything.
# STRUCTURED, not phrase-matched (S1, 2026-08-25). The pre-fix version matched the WORDS
# "positive control" or "mutation control" anywhere in the row, so a row satisfied P2 by
# mentioning a control over a DIFFERENT harness, or by the bare phrase with no perturbation
# and no observation at all. Both passed. A witness must now name the recipe it falsifies —
# the Markdown analogue of the TOML side's `control.of_claim` identity check.
#
#   watched-fail(<recipe-ref>): <what was perturbed> -> <what was observed>
#   mutation-control(<recipe-ref>): ...
#   positive-control(<recipe-ref>): ...        (satisfies P2 only on `not-covered`, §4.1)
#
# <recipe-ref> MUST equal a recipe token that appears in this row's own verify cell.
WITNESS_RE = re.compile(
    # The separator after the closing paren is the SHARED separator class, one or more (§4.1,
    # settled 2026-08-25 seventh round). It was a hand-written colon/dash class, so `:` and `-`
    # parsed while `=`, `,` and `;` silently did not -- and a witness the producer thought they
    # had written was simply not seen. One or more, never zero: a zero-length separator would let
    # the witness run into surrounding prose.
    r"(watched-fail|mutation-control|positive-control)\s*\(\s*([^)]+?)\s*\)"
    + SEP_DECLARATIVE + r"(.+?)"
    r"(?=(?:\s*(?:·|\||$)))",
    re.IGNORECASE | re.DOTALL,
)
# The witness body must show a transition: something was done, something was observed.
WITNESS_ARROW_RE = re.compile(r"->|→|=>|⇒")

# core.md W2.3 / coverage-ledger §6: the closed clause_source enum. In a Markdown rendering
# the clause cell must carry one of these tokens; free prose ("a stable RFC") records nothing a
# consumer can act on and cannot be told from an unstated source (S2).
WEAK_WITNESS_PHRASE_RE = re.compile(
    r"positive control|mutation[- ]control|mutation-controlled|watched to fail", re.IGNORECASE)

# §7.2 (P3): a predicate item ranges over a second list and its honest status is a fraction.
# DECLARATIVE detection (§7.2, tightened 2026-08-25): the row must carry the token, delimited
# -- backticked, bolded, or `item-kind: predicate`. Reading the bare word out of running prose
# made the checker guess which items are predicates from their wording, which is a semantic
# judgement no checker can make. The honest consequence is stated in §7.2: an UNDECLARED
# predicate item is invisible to this tool, and catching one is reviewer work.
# DECLARATIVE, and word-bounded on both sides. `item[-_ ]kind` + SEP_RUN allowed ZERO separators,
# so the identifier `item_kindpredicate` declared a predicate item and earned the row a refusal it
# had not asked for -- a FALSE POSITIVE, the same defect class pointed the other way (review,
# round 7).
# The styled branch requires MATCHED delimiters, and `_` is not one of them: underscore is an
# identifier character, so `_predicate_` is the middle of `foo_predicate_bar` and not markup. The
# old alternation accepted any opener with any closer, which is how an ordinary identifier earned
# an honest row a predicate refusal (review, round 8 -- a FALSE REFUSAL, the costlier direction).
PREDICATE_DECL_RE = re.compile(
    NOT_WORD_BEFORE + r"(?:`predicate`|\*\*predicate\*\*)" + NOT_WORD_AFTER
    + r"|" + NOT_WORD_BEFORE + r"item[-_ ]kind" + NOT_WORD_AFTER + SEP_DECLARATIVE
    + r"[`\"']?predicate" + NOT_WORD_AFTER,
    re.IGNORECASE,
)
FRACTION_RE = re.compile(r"\b\d+\s*(?:of|/)\s*\d+\b", re.IGNORECASE)
# DECLARATIVE (§7.2). The prose form matched any `over <word>`, so *"reviewed over lunch"* named
# the sub-list a predicate ranges over (review, round 7). A rendering declares it the way the
# manifest field does: `over: <what it ranges over>`.
OVER_RE = declaration_re(r"over")
# §7.3 (P4): a `blocked` status must name what blocks it.
# DECLARATIVE. No leading boundary plus a zero-length separator meant `unblocked_byproduct`
# satisfied §7.3's "name what blocks it" (review, round 7).
BLOCKED_BY_RE = declaration_re(r"blocked[-_ ]by")
# W5: the document must STATE its tier counts, and they must match the computed ones. A typed
# count that has drifted from the rows is worse than no count at all -- it is a number a reader
# will quote. Before 2026-08-25 the tool printed counts and checked nothing.
DECLARED_COUNTS_RE = re.compile(
    NOT_WORD_BEFORE + r"(\d+)\s*weighted\s*,\s*(\d+)\s*unweighted" + NOT_WORD_AFTER,
    re.IGNORECASE)
# W5 states THREE counts while any row is pending ("plus `weight-pending: P` while any exists").
# The third was parsed by nothing: a rendering could declare `weight-pending: 999` against a
# computed 1 and pass (review round-2, finding 9). Accepted forms: `N weight-pending`,
# `N rows in weight-pending`, `weight-pending: N`.
DECLARED_PENDING_RE = re.compile(
    NOT_WORD_BEFORE + r"(\d+)\s*(?:rows?\s+)?(?:in\s+)?`?weight-pending`?" + NOT_WORD_AFTER
    # The keyword-first branch is the STATED syntax, `weight-pending: P`. With a zero-length
    # separator run it also read `weight-pending7` as a declared count of 7 (review, round 8).
    + r"|" + NOT_WORD_BEFORE + r"`?weight-pending`?" + SEP_DECLARATIVE + r"(\d+)"
    + NOT_WORD_AFTER,
    re.IGNORECASE)
# `status` is a closed, five-token vocabulary in BOTH representations (core.md §7 /
# `STATUSES`, shared with the manifest validator via `acceptance_grammar.py`). The alias layer
# this used to be (mapping "done"/"not-covered"/"not started"/"in-progress"/"receipted"/
# "strengthened"/"complete"/"none" onto the canonical tokens) is DELETED: a status cell now
# names one of the five closed tokens, exactly, word-bounded -- the same law the TOML side has
# always had. A rendering using a non-canonical spelling is unrecognised, not silently mapped.
STATUS_TOKENS = [(re.compile(r"\b" + re.escape(tok) + r"\b", re.I), tok)
                  for tok in sorted(STATUSES)]

# The Markdown pattern is DERIVED from the shared closed set, not typed out beside it: a
# hand-written alternation is a second copy of the enum, and a token added to `CLAUSE_SOURCES`
# would silently be rejected here while the manifest validator accepted it. Longest-first so the
# alternation cannot match a prefix of a longer token.
CLAUSE_SOURCE_RE = re.compile(
    r"(?<![A-Za-z0-9-])("
    + "|".join(re.escape(t) for t in sorted(CLAUSE_SOURCES, key=len, reverse=True))
    + r")(?![A-Za-z0-9-])",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Markdown table extraction
# ---------------------------------------------------------------------------


def _is_separator_line(line: str) -> bool:
    s = line.strip()
    if not s.startswith("|") and "-" not in s:
        return False
    # only pipes, dashes, colons, spaces allowed, and at least one dash
    if not re.fullmatch(r"[\s|:\-]+", s):
        return False
    return "-" in s


def _split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


@dataclass
class Table:
    header: list[str]
    rows: list[tuple[int, list[str]]]  # (1-indexed line number, cells)


def extract_tables(lines: list[str]) -> list[Table]:
    tables: list[Table] = []
    n = len(lines)
    i = 0
    while i < n - 1:
        line = lines[i]
        nxt = lines[i + 1]
        if line.strip().startswith("|") and _is_separator_line(nxt):
            header = _split_row(line)
            body: list[tuple[int, list[str]]] = []
            j = i + 2
            while j < n and lines[j].strip().startswith("|") and lines[j].strip() != "":
                body.append((j + 1, _split_row(lines[j])))
                j += 1
            tables.append(Table(header=header, rows=body))
            i = j
        else:
            i += 1
    return tables


def _normalize_header(h: str) -> str:
    h2 = re.sub(r"[*`]", "", h).strip().lower()
    h2 = re.sub(r"\s+", " ", h2)
    return h2


def build_col_map(header: list[str]) -> dict[str, int]:
    col_map: dict[str, int] = {}
    for idx, h in enumerate(header):
        nh = _normalize_header(h)
        if nh == "id":
            col_map.setdefault("id", idx)
        elif "strength" in nh or nh == "grade":
            col_map["strength"] = idx
        elif "verify" in nh or "recipe" in nh:
            col_map["verify"] = idx
        elif nh == "status":
            col_map["status"] = idx
        elif nh in ("weight", "tier"):
            col_map["weight"] = idx
        elif "clause" in nh:
            col_map["clause"] = idx
        elif nh == "note":
            col_map["note"] = idx
        else:
            col_map.setdefault("desc", idx)
    return col_map


# A recipe table's own "id" column cell: a single bolded uppercase letter, optionally followed
# by its placeholder argument (`**K** \`<H>\``) -- distinct in shape from a ledger row's
# backticked id (`` `DER-F-8` ``).
RECIPE_TABLE_ID_CELL_RE = re.compile(r"^\*\*([A-Z])\*\*")


def declared_recipe_letters(lines: list[str]) -> frozenset[str] | None:
    """core.md §4.2: '<LETTER> is a single uppercase letter declared in the rendering's OWN
    recipe table' -- so THIS document's letters govern THIS document's rows, not a global
    alphabet the checker invents. Scans every table in the document for the recipe-table shape
    (an `id`-headed column whose cells are bolded single uppercase letters, e.g.
    `examples/rs-verified-der/ENVELOPE.md` §4's `| id | recipe | what green means |`) and returns
    the set of letters it declares. Returns None when no such table is found at all -- the
    caller's decision what to fall back to (RECIPE_LETTERS), not this function's, so a genuinely
    letter-less document (or a bare selftest fixture) is distinguishable from one that declared an
    empty table."""
    tables = extract_tables(lines)
    letters: set[str] = set()
    found = False
    for table in tables:
        if not table.header or _normalize_header(table.header[0]) != "id":
            continue
        # A LEDGER row table also has an "id"-headed first column -- distinguish by the ABSENCE
        # of a status/strength column (a recipe table has neither) rather than by header text
        # alone, so a real ledger table is never mistaken for a recipe table.
        col_map = build_col_map(table.header)
        if "status" in col_map or "strength" in col_map:
            continue
        for _, cells in table.rows:
            if not cells:
                continue
            m = RECIPE_TABLE_ID_CELL_RE.match(cells[0].strip())
            if m:
                letters.add(m.group(1))
                found = True
    return frozenset(letters) if found else None


def match_row_id(cell: str) -> str | None:
    c = cell.strip()
    if len(c) >= 2 and c[0] == "`" and c[-1] == "`":
        inner = c[1:-1]
        if ID_INNER_RE.match(inner):
            return inner
    return None


# ---------------------------------------------------------------------------
# Row-level checks
# ---------------------------------------------------------------------------


def _cell(cells: list[str], col_map: dict[str, int], key: str) -> str | None:
    idx = col_map.get(key)
    if idx is None or idx >= len(cells):
        return None
    return cells[idx]


def _normalize_grade_text(t: str) -> str:
    # The `+L4` ladder (CONTRACT+L4 = a bounded Kani proof PLUS an unbounded Lean lid, folded
    # into one composite grade token) is retired: the six rows that used it are now plain
    # `CONTRACT` (the Kani half is what carries the row's witness; the Lean-lid fact is disclosed
    # in the row's own prose, not folded into the grade). A stray `+L4` suffix is no longer
    # normalized away here -- it is an unrecognised grade token like any other typo.
    return t.strip().lower()


def check_grade(strength_text: str | None) -> tuple[str | None, list[str]]:
    """Check 1: grade token present and closed. Returns (grade, errors)."""
    errors: list[str] = []
    if strength_text is None:
        return None, ["no strength/grade column identified in this table — grade checks skipped"]
    text = strength_text.strip()
    if not text:
        errors.append("strength cell is empty — no grade token")
        return None, errors
    spans = BOLD_RE.findall(text)
    if not spans:
        errors.append(f"no bolded grade token found in strength cell (cell: {text!r})")
        return None, errors
    valid: list[str] = []
    invalid: list[str] = []
    for s in spans:
        norm = _normalize_grade_text(s)
        if norm in GRADES:
            valid.append(norm)
        elif norm in TIER_MARKERS:
            continue          # weight tier marker, not a grade claim (spec W4)
        else:
            invalid.append(s.strip())
    distinct_valid = sorted(set(valid))
    # A bold span that is not a grade token is only an ERROR when the cell
    # contains NO grade token at all -- then it IS the (invalid) grade claim,
    # e.g. "derived" or "test-only (controlled)". When a real token is present,
    # the other spans are prose emphasis ("**not**", "**child count**") and the
    # tool must not invent violations out of typography.
    if not distinct_valid:
        for inv in invalid:
            errors.append(
                f"grade text not in the closed vocabulary: '{inv}' (strength cell: {text!r})"
            )
    if len(distinct_valid) >= 2:
        errors.append(
            "ambiguous grade — two or more DIFFERENT tokens found in one strength cell: "
            f"{distinct_valid} (one row, one claim — spec section 7) (cell: {text!r})"
        )
        return None, errors
    if not distinct_valid:
        return None, errors
    return distinct_valid[0], errors


def _recipe_arg_is_command_body(arg: str) -> bool:
    """core.md §4.2: is `arg` a plausible command body, or a placeholder?

    Checkable, and deliberately only this: the argument must carry at least one word token of
    two or more characters (an identifier, a path, a harness name, a command name), must not be
    the recipe table's own metavariable (`<H>`), and must not be a placeholder word. It cannot
    check that the command exists or that it is the right one for the row -- `--execute`
    answers the first and a reviewer answers the second (§4.2, §8.2)."""
    a = arg.strip()
    if not a:
        return False
    if RECIPE_ARG_METAVAR_RE.match(a):
        return False
    if a.strip("`'\"").lower() in RECIPE_ARG_PLACEHOLDERS:
        return False
    return RECIPE_ARG_WORD_RE.search(a) is not None


def _is_literal_command(token: str) -> bool:
    """§4.2: is `token` a backticked LITERAL command?

    Subject to the same shape checks the letter form gets -- it must be a plausible command body,
    not a placeholder and not the recipe table's metavariable -- plus one discriminator, because a
    rendering backticks row ids and harness paths too: a command invocation either names a PATH
    (`./check.sh`, `/usr/bin/env ...`), carries a SCRIPT EXTENSION, or is a program name followed
    by arguments. `DER-F-8` and `mod::proofs::foo` are none of those, and neither is a bare
    `true`."""
    t = token.strip()
    if not t or not _recipe_arg_is_command_body(t):
        return False
    words = t.split()
    first = words[0]
    # `DER_REQUIRE_LEAN=1 ./check.sh` -- an environment prefix is part of the invocation.
    if ENV_PREFIX_RE.match(first) and len(words) > 1:
        words = words[1:]
        first = words[0]
    if first.startswith("./") or first.startswith("/"):
        return True
    if SCRIPT_EXT_RE.search(first):
        return True
    # A ONE-CHARACTER program name is not a command; it is how the LETTER form starts. Without
    # this, a letter-form token that failed its own check fell through and was re-admitted as a
    # literal: `K TODO` became "program K, argument TODO", quietly undoing §4.2's placeholder
    # rule. Caught by the round-2 placeholder fixture on the next run.
    if len(first) < 2:
        return False
    return len(words) > 1 and bool(COMMAND_WORD_RE.match(first)) and "::" not in first


def recipe_reference_kind(token: str, letters: frozenset[str] = RECIPE_LETTERS) -> str | None:
    """`"letter"`, `"literal"`, or None. The one place §4.2's two accepted forms are decided, so
    the verify-cell check, `recipe_tokens`, and the witness-ref check cannot disagree about what
    a recipe reference is. `letters` (§4.2): the letters THIS document's own recipe table
    declares -- defaults to RECIPE_LETTERS only for callers with no document to consult."""
    if _recipe_token_letter(token, letters) is not None:
        return "letter"
    return "literal" if _is_literal_command(token) else None


def _recipe_token_letter(token: str, letters: frozenset[str] = RECIPE_LETTERS) -> str | None:
    """Return the recipe letter if `token` (backtick content, already
    stripped) parses as a recipe reference: a bare letter ('G', 'R'), a
    letter + space + a COMMAND BODY ('K mod::proofs::foo', 'A grep ...'), or a
    compound recipe id such as 'A0' (letter followed only by uppercase
    letters/digits — no lowercase, no hyphen, so it can't be mistaken for a
    row-id cross-reference like `DER-F-8` or a lowercase identifier).

    The command-body requirement is §4.2, added 2026-08-25: `K ???` used to parse. `letters`
    (§4.2, extended): validated against THIS document's own declared recipe table
    (`declared_recipe_letters`), not a global alphabet -- RECIPE_LETTERS is the fallback for a
    document (or fixture) that declares none."""
    if not token:
        return None
    first = token[0]
    if first not in letters:
        return None
    if len(token) == 1:
        return first
    if token[1].isspace():
        return first if _recipe_arg_is_command_body(token[1:]) else None
    rest = token[1:]
    if re.fullmatch(r"[A-Z0-9]*", rest):
        return first
    return None


def check_recipe(verify_text: str | None, letters: frozenset[str] = RECIPE_LETTERS) -> str | None:
    """Check 2: deciding recipe required. Returns an error message, or None."""
    if verify_text is None:
        return "no verify/recipe column identified in this table"
    t = verify_text.strip()
    if not t:
        return "verify cell is empty — no deciding recipe named"
    spans = [m.strip() for m in BACKTICK_RE.findall(t)]
    for m in spans:
        if _recipe_token_letter(m, letters) is not None:
            return None
    # §4.2's literal-command form. It must be DELIMITED (backticked): prose that merely contains
    # the word "cargo" has named no command.
    for span in spans:
        if _is_literal_command(span):
            return None
    return (
        f"no recognisable recipe reference in verify cell — a recipe is `<LETTER>` or "
        f"`<LETTER> <command body>` from this document's own recipe table, or a backticked "
        f"literal command; a placeholder such as `K ???` is not one (spec §4.2) (cell: {t!r})"
    )


def extract_bounds_declaration(strength_text: str | None, row_text: str) -> str | None:
    """Find the row's bounds DECLARATION and hand it back as a string the shared grammar can
    judge. Returns None when the row states no boundedness token at all.

    This is the only Markdown-specific part of §5, and it is deliberately the only part: a
    rendering has no `bounds` field, so the declaration must be LOCATED before it can be JUDGED.
    Locating is a rendering problem; judging is the format's rule, and the judging is done by
    `acceptance_grammar.bounds_token` / `has_bounds_tail` — the same functions
    `check_acceptance.py` calls, so the two representations cannot disagree about what a bounds
    declaration is.

    The strength cell is preferred because that is where the token is rendered; the whole row is
    the fallback for ledgers that put boundedness in the verify cell."""
    for source in (strength_text, row_text):
        if not source:
            continue
        m = BOUNDS_TOKEN_ANCHOR_RE.search(source)
        if not m:
            continue
        rest = source[m.start():]
        end = BOUNDS_DECL_END_RE.search(rest)
        return rest[:end.start()].strip() if end else rest.strip()
    return None


def check_bounds(strength_text: str | None, row_text: str) -> str | None:
    """Check 3 (§5): a contract/probe row must declare boundedness — the TOKEN and the LIMIT.

    Both halves are judged by the shared grammar. Until 2026-08-25 (fourth round) this function
    used a local regex whose accepted alternatives included `unwind`, `+L4`, `≤N bytes` and
    `[u8; N]` — all of them LIMITS, none of them boundedness tokens — so `**CONTRACT** (unwind=8)`
    declared boundedness by naming a bound and never saying which kind. `**CONTRACT+L4**` was
    likewise accepted with no bounds text at all, which is the single-token strength ladder §5
    spends a subsection telling renderings not to use."""
    decl = extract_bounds_declaration(strength_text, row_text)
    if bounds_token(decl) is None:
        return (
            "contract/probe row does not declare boundedness — §5 requires the token `bounded` "
            "or `unbounded` on the row. A limit alone (`unwind=8`, `≤12 bytes`, `+L4`) names a "
            "bound without saying which kind, and a grade token alone is the single-token "
            "strength ladder §5 forbids: state the pair"
        )
    if not has_bounds_tail(decl):
        return (
            f"the boundedness token states which of 'bounded'/'unbounded' applies and nothing "
            f"about WHAT THE CHECK RANGED OVER — §5 requires the token plus text naming the "
            f"actual limit (an unwind bound, a buffer size, a monomorphic instantiation, or the "
            f"domain an 'unbounded' check is complete over) (declaration: {decl!r})"
        )
    return None


def references_a_or_grep(verify_text: str | None, letters: frozenset[str] = RECIPE_LETTERS) -> bool:
    if not verify_text:
        return False
    if "grep" in verify_text.lower():
        return True
    for m in BACKTICK_RE.findall(verify_text):
        if _recipe_token_letter(m.strip(), letters) == "A":
            return True
    return False


# §4's obligation, DECLARED. Two accepted syntaxes, both explicit:
#   positive-control(<recipe-ref>): <input tried> -> <what it matched>, observed <YYYY-MM-DD>
#   positive-control: <the input or target the same command demonstrably matches>
# The first is §4.1's structured witness (which on `not-covered` is also the P2 witness); the
# second is the plain declaration for a row that carries the control without the full witness.
POSITIVE_CONTROL_DECL_RE = declaration_re(r"positive[-_ ]control")
# ...and its VALUE, up to the end of the cell, sentence or `·` separator. §4 requires the control
# to NAME an input or target, which is a statement -- so the rendered declaration carries the same
# two-token floor the manifest validator applies to `self_verify.positive_control`. Without it
# `positive-control: x` was clean here and refused there (review, round 9).
POSITIVE_CONTROL_VALUE_RE = re.compile(
    NOT_WORD_BEFORE + r"positive[-_ ]control" + NOT_WORD_AFTER + SEP_DECLARATIVE
    + r"(.+?)(?=$|\||\.\s|·)",
    re.IGNORECASE,
)
# An ATTEMPT at the structured syntax: the keyword followed by an opening paren. Used only to
# notice that the producer meant a structured witness -- never to accept one. Accepting on the
# opener was the round-10 blocker.
POSITIVE_CONTROL_OPENER_RE = re.compile(
    NOT_WORD_BEFORE + r"positive[-_ ]control" + NOT_WORD_AFTER + r"\s*\(", re.IGNORECASE)


def check_positive_control(verify_text: str | None, row_text: str,
                           letters: frozenset[str] = RECIPE_LETTERS
                           ) -> tuple[str | None, str | None]:
    """§4: `positive_control` is REQUIRED on every `not-covered` row, unconditionally.

    DECLARED, not scanned (round 8), and the structured form is validated COMPLETELY rather than
    on its opener (round 10). Two accepted syntaxes:

        positive-control(<recipe-ref>): <input tried> -> <what it matched>, observed <date>
        positive-control: <the input or target the same command demonstrably matches>

    The first is §4.1's structured witness and is checked by `validate_structured_witness`, the
    same function `watched_fail_witness` uses -- one implementation of one rule. This function
    used to carry its own, which accepted the bare opener `positive-control(`: no closing paren,
    no recipe binding, no transition, no date. A dangling opener beside a valid witness earned the
    row weight the manifest twin refused.

    An ATTEMPTED structured form that does not parse is an error even when another, valid control
    is present. A row that states something unparseable has stated it; leaving it unreported is
    how the opener came to be accepted in the first place."""
    tokens = recipe_tokens(verify_text, letters)
    parsed = [m for m in WITNESS_RE.finditer(row_text)
              if m.group(1).lower() == "positive-control"]
    valid = []
    complaints = []
    for m in parsed:
        complaint = validate_structured_witness(
            "positive-control", m.group(2).strip().strip("`"), m.group(3).strip(),
            "not-covered", tokens, letters)
        (complaints if complaint else valid).append(complaint or m)

    # Every attempted structured form must have parsed. `len(openers) > len(parsed)` means one
    # opened and never resolved.
    openers = list(POSITIVE_CONTROL_OPENER_RE.finditer(row_text))
    if len(openers) > len(parsed):
        return (
            "the row opens a structured positive control that does not parse — the form is "
            "`positive-control(<recipe>): <input> -> <what it matched>, observed <YYYY-MM-DD>`. "
            "An unparseable declaration is not a control, and a valid one elsewhere on the row "
            "does not excuse it (spec §4/§4.1)",
            None,
        )
    if complaints:
        return f"the row's structured positive control is incomplete — {complaints[0]}", None
    if valid:
        return None, None

    m = POSITIVE_CONTROL_VALUE_RE.search(row_text)
    if m:
        if is_phrase(strip_witness_metadata(m.group(1))):
            return None, None
        return (
            f"the declared positive control names nothing: §4 requires the input or target the "
            f"same command demonstrably matches, and a single token is not one "
            f"(value: {m.group(1).strip()!r})",
            None,
        )
    hint = ""
    if SECTION_REF_RE.search(row_text):
        hint = (" The row cites a section; if the control lives there, state it on the row too — "
                "a citation does not satisfy the obligation.")
    return (
        "not-covered row declares no positive control (spec §4: 'a grep that returns nothing is a "
        "claim about your pattern'). Declare it as `positive-control(<recipe>): <input> -> <what "
        "it matched>, observed <YYYY-MM-DD>` or `positive-control: <input the command matches>`."
        + hint,
        None,
    )


def recipe_tokens(verify_text: str | None, letters: frozenset[str] = RECIPE_LETTERS) -> list[str]:
    """Every backticked token in the verify cell that parses as a recipe reference."""
    if not verify_text:
        return []
    out = []
    for m in BACKTICK_RE.findall(verify_text):
        t = m.strip()
        if recipe_reference_kind(t, letters) is not None:
            out.append(t)
    return out


def validate_structured_witness(kind: str, ref: str, body: str, grade: str,
                                tokens: list[str], letters: frozenset[str] = RECIPE_LETTERS
                                ) -> str | None:
    """core.md §4.1: validate ONE parsed structured witness. Returns a complaint, or None when
    the witness is complete.

    THE ONE IMPLEMENTATION of this rule. `check_positive_control` used to carry a second, far
    weaker one: it matched the OPENER `positive-control(` and returned success on that alone --
    no closing paren, no recipe binding, no transition, no date -- so a dangling opener beside a
    valid witness earned a rendered row weight its manifest twin refused (review, round 10). Two
    parsers for one rule is the defect this codebase keeps rediscovering; there is one now, and
    both callers go through it."""
    if kind == "positive-control" and grade != "not-covered":
        return (f"witness `positive-control({ref})` does not satisfy §4.1 for grade "
                f"'{grade}' — an absence check's control witnesses only an absence claim; "
                f"use watched-fail(...) or mutation-control(...)")
    if recipe_reference_kind(ref, letters) is None:
        return (f"witness `{kind}({ref})` does not name a recipe: '{ref}' does not parse as "
                f"`<LETTER>`, `<LETTER> <command body>`, or a literal command (spec §4.2)")
    if not tokens:
        return (f"witness `{kind}({ref})` names a recipe, but this row's verify cell has no "
                f"recipe token to bind it to")
    if ref not in tokens:
        return (f"witness `{kind}({ref})` does not name any recipe of THIS row "
                f"(row recipes: {tokens}) — a control over a different check witnesses "
                f"nothing about this one (§4.1; the of_claim rule)")
    if not WITNESS_ARROW_RE.search(body):
        return (f"witness `{kind}({ref})` states no observation — the form is "
                f"'<what was perturbed> -> <what was observed>, observed <YYYY-MM-DD>'")
    halves = WITNESS_ARROW_RE.split(body, maxsplit=1)
    thin = [n for n, v in (("perturbation", halves[0]), ("observation", halves[-1]))
            if not is_phrase(strip_witness_metadata(v))]
    if thin:
        return (f"witness `{kind}({ref})` states a {' and a '.join(thin)} of one token — "
                f"'x -> y' is a transition between two characters, not a description of what "
                f"was perturbed and what was seen (§4.1)")
    if not ISO_DATE_INLINE_RE.search(body):
        return (f"witness `{kind}({ref})` states no date — 'when' is part of the witness "
                f"because a recipe watched to fail last year may not discriminate today. Add an "
                f"ISO date (YYYY-MM-DD) to the witness body (§4.1)")
    return None


def watched_fail_witness(grade: str, verify_text: str | None, row_text: str,
                         letters: frozenset[str] = RECIPE_LETTERS) -> tuple[bool, list[str]]:
    """core.md §4.1 (P2), structured. Returns (satisfied, complaints).

    A witness must (a) use one of the three named forms, (b) name a recipe that appears in
    THIS row's verify cell -- the of_claim identity check, in Markdown -- and (c) state a
    transition (perturbation -> observation). `positive-control` satisfies P2 only on
    `not-covered`, which is the one grade where the failure is a hit rather than a miss."""
    complaints: list[str] = []
    tokens = recipe_tokens(verify_text, letters)
    found_any = False
    for m in WITNESS_RE.finditer(row_text):
        found_any = True
        complaint = validate_structured_witness(
            m.group(1).lower(), m.group(2).strip().strip("`"), m.group(3).strip(), grade, tokens,
            letters)
        if complaint:
            complaints.append(complaint)
            continue
        return True, complaints
    # §4.1 witness 3, in its PLAIN declared form. §4.1 says a `not-covered` row's positive
    # control IS the witness; only the parenthesised syntax was recognised as one, so a row
    # declaring `positive-control: <statement>` satisfied §4 and was still refused for having no
    # witness -- and its TOML twin, which has one `positive_control` field serving both, passed
    # (review, round 9).
    if grade == "not-covered":
        m = POSITIVE_CONTROL_VALUE_RE.search(row_text)
        if m and is_phrase(strip_witness_metadata(m.group(1))):
            return True, complaints
    if not found_any and WEAK_WITNESS_PHRASE_RE.search(row_text):
        complaints.append(
            "the row mentions a control in prose but states no structured witness — "
            "phrase presence is not a witness (§4.1); use "
            "`watched-fail(<recipe>): <perturbation> -> <observed>`"
        )
    return False, complaints


def clause_sources_in(clause_cell: str | None) -> list[str]:
    """EVERY clause_source token in the cell, in order. Closed enum (W2.3); free prose is not a
    declaration, it is an unstated source wearing a citation.

    All of them, not the first (review, round 5): `S-1 (spec-document; none)` and
    `S-1 (spec-document; test-name)` both passed WEIGHTED, because only the leading token was
    read and the reserved one behind the semicolon was never seen. A cell that names a reserved
    token names it, wherever in the cell it sits."""
    if clause_cell is None:
        return []
    return [m.group(1).lower() for m in CLAUSE_SOURCE_RE.finditer(clause_cell)]


def clause_source_of(clause_cell: str | None) -> str | None:
    """The single declared clause_source token, or None when the cell declares none — or more
    than one, which is not a declaration either (see `clause_sources_in`)."""
    toks = set(clause_sources_in(clause_cell))
    return next(iter(toks)) if len(toks) == 1 else None


def statuses_in(status_text: str | None) -> list[str]:
    """EVERY schema status the cell's prose maps onto, most specific first."""
    if not status_text:
        return []
    return [name for rx, name in STATUS_TOKENS if rx.search(status_text)]


def normalize_status(status_text: str | None) -> str | None:
    """Markdown status cells hold prose around the token, e.g. `BLOCKED -- not reachable`; this
    locates the one closed-vocabulary token inside that prose (STATUS_TOKENS, deleted alias layer
    -- a cell now names one of the five canonical tokens, exactly, or it names none).

    Returns None when the cell maps onto MORE THAN ONE status: `evidenced, but really a gap`
    matches both `evidenced` and `gap`, which is the same first-match-wins shape as the
    contradictory tier markers and the smuggled clause_source. Found by the round-10
    partial-syntax sweep rather than reported from outside. A cell naming two statuses has named
    none, and the caller refuses it on a weighted row exactly as it refuses an unrecognised one --
    §7.1 coherence cannot be decided either way."""
    found = statuses_in(status_text)
    return found[0] if len(set(found)) == 1 else None


def check_status_grade(status: str | None, grade: str) -> str | None:
    """core.md §7.1. Delegates to the shared grammar so the Markdown and TOML verdicts on the
    same (status, grade) pair cannot diverge -- which is exactly how `out-of-scope` drifted."""
    return status_grade_incoherence(status, grade)


# A standalone, word-bounded tier word. Recognised ONLY inside a dedicated weight column: W4
# names "a dedicated weight column" as one of the three accepted markers, and reading a bare word
# out of running prose is the W4 inversion this checker was built to stop.
STANDALONE_TIER_RE = re.compile(
    NOT_WORD_BEFORE + r"(unweighted|weighted)" + NOT_WORD_AFTER, re.IGNORECASE)


def _tier_tokens_in(text: str | None) -> set[str]:
    """Every tier token in `text` expressed in a DELIMITED syntax — bolded, or a standalone
    [U]/[W] bracket marker."""
    if not text:
        return set()
    toks = {span.strip().lower() for span in BOLD_RE.findall(text)} & TIER_MARKERS
    for b in BRACKET_TIER_RE.finditer(text):
        toks.add("unweighted" if b.group(1) == "U" else "weighted")
    return toks


def tier_tokens_of_row(cells: list[str], col_map: dict[str, int], row_text: str) -> set[str]:
    """EVERY tier token the row states, across EVERY recognised syntax and EVERY path.

    Round 6 added a contradiction scan and claimed it ran "on every path"; it did not. The
    dedicated-cell path returned as soon as it found one delimited token, and the unbolded
    leading-word form was read by a separate `.match()` that never contributed to the set at all.
    So `unweighted · **weighted**` resolved to `weighted`, and two unbolded markers resolved to
    the first (review, round 7). Now there is one set, built from every syntax, and the caller
    refuses when it holds more than one."""
    toks: set[str] = set()
    weight_cell = _cell(cells, col_map, "weight")
    if weight_cell is not None and weight_cell.strip():
        toks |= _tier_tokens_in(weight_cell)
        # The unbolded word, which W4 accepts only in this column.
        toks |= {m.group(1).lower() for m in STANDALONE_TIER_RE.finditer(weight_cell)}
    toks |= _tier_tokens_in(row_text)
    return toks


def tier_marker(cells: list[str], col_map: dict[str, int], row_text: str) -> str | None:
    """W4: the row's EXPLICIT tier marker — 'weighted', 'unweighted', 'contradictory', or None
    when the row carries no marker at all. Never infers a tier from running prose."""
    toks = tier_tokens_of_row(cells, col_map, row_text)
    if len(toks) > 1:
        return "contradictory"
    if toks:
        return next(iter(toks))
    return None


def check_out_of_scope(verify_text: str | None, row_text: str = "") -> str | None:
    """core.md §1/§7.1: `out-of-scope` is the one grade whose weight attaches to a DECLARATION
    rather than to any property of the code — *"the producer declared this, HERE"* — so the
    *here* must be a locator a reader can follow.

    This check tested NONEMPTINESS ONLY until 2026-08-25 (third review round), while the manifest
    validator had required a locator since the second. That is the parity break the review probe found,
    and it was the worse half of it: the row below was granted WEIGHT by this checker and refused
    by its TOML twin.

        | `O-1` | h is deliberately not implemented | S-1 (spec-document) | gap |
          **out-of-scope** · **weighted** | nonsense |

    The locator grammar now comes from `acceptance_grammar.is_scope_locator`, which is the SAME
    function the TOML side calls — a rule with one implementation cannot drift. The reference may
    live in the verify cell or anywhere else on the row, because a rendering has no dedicated
    `scope_ref` column."""
    if verify_text is None or not verify_text.strip():
        return "out-of-scope row does not cite a source (verify cell is empty)"
    if is_scope_locator(verify_text) or is_scope_locator(row_text):
        return None
    return (
        f"out-of-scope row cites no LOCATOR — expected {SCOPE_REF_EXPECTATION} — and free prose "
        f"records nothing a consumer can act on. `out-of-scope` weight attaches to 'the producer "
        f"declared this, here', so a reader must be able to go there (spec §1/§7.1) "
        f"(cell: {verify_text.strip()!r})"
    )


def check_unspecified(row_text: str) -> str | None:
    low = row_text.lower()
    if "unspecified" in low or "no spec" in low or "clause source" in low:
        return None
    return (
        "unspecified row does not say so anywhere in the row "
        "(expected 'unspecified', 'no spec', or 'clause source')"
    )


# ---------------------------------------------------------------------------
# Row processing
# ---------------------------------------------------------------------------


@dataclass
class RowResult:
    row_id: str
    line_no: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # The normalized grade token, kept so the strength-tier split below can be DERIVED from the
    # rows rather than typed beside them.
    grade: str | None = None
    # W1: weight is explicit and DEFAULTS TO ABSENT. This field defaulted to True, which is the
    # W1 inversion sitting in the data model rather than in a rule -- and it was reachable: the
    # early return taken when a row's grade cannot be resolved (missing, ambiguous, or outside
    # the closed vocabulary) never assigns it, so those rows carried errors AND counted weighted
    # in the W5 totals. Found by the round-8 weight invariant, one layer under the case the review sent.
    weighted: bool = False
    # False for a row this tool could not check at all — it must not silently enter the
    # W5 tier totals as if it had been graded.
    counted: bool = True
    # core.md §8.1: the row CLAIMS weight and meets every pre-adoption rule, but lacks the
    # machinery W2.3/W2.5 began requiring on 2026-08-25. Not weighted, not unweighted: named
    # and counted, so the remediation backlog stays visible instead of vanishing into a tier
    # that promises nothing.
    pending: bool = False
    pending_reasons: list[str] = field(default_factory=list)
    # W1/W4: the tier the row DECLARES ("weighted" | "unweighted" | None for silence).
    declared_tier: str | None = None
    # W4: weight-eligible grade, no stated tier -- unweighted by W1, defective as a rendering.
    tier_unstated: bool = False
    # The row CLAIMED weight and was refused by an error. Counted in neither tier (§8.1).
    refused: bool = False
    # Did the row EXPLICITLY claim weight, per the production tier parser? Recorded so the
    # structural proof can use the same answer the rules use, rather than re-deriving it from
    # bold spans and thereby leaving [U]/[W] and the unbolded weight column outside the proof
    # (review, round 10).
    claimed_weight: bool = False


def _finalize(result: RowResult, claimed_weight: bool) -> RowResult:
    """§8.1's membership rule, applied at EVERY exit of `process_row`.

    A row that EXPLICITLY claimed weight and drew any weight-refusal error is `refused`: not
    weighted (the errors say so) and not unweighted (it asked for weight and was told no). It is
    counted in neither tier.

    ALL FOUR of `process_row`'s exits return through this function, and that is the architecture
    rather than a description of it: the point of a single finalisation point is that a future
    edit cannot reintroduce the leak by adding a return.

    Round 9 keyed the rule to the end of the function, which left the unweighted-early exit
    uncovered -- `**inspection-argued** · **weighted**` is refused by W2.1, leaves through it, and
    lands in the UNWEIGHTED count. Round 10 found that two DIRECT exits still remained (the
    no-strength-column and unresolved-grade returns) while the docstring claimed otherwise. Their
    behaviour happened to be safe; the claim was not true, and an architecture claim that is only
    incidentally true is the thing this file exists to stop shipping."""
    if claimed_weight and result.errors:
        result.weighted = False
        result.refused = True
    return result


def process_row(row_id: str, line_no: int, cells: list[str], col_map: dict[str, int],
                letters: frozenset[str] = RECIPE_LETTERS) -> RowResult:
    result = RowResult(row_id=row_id, line_no=line_no)
    strength_text = _cell(cells, col_map, "strength")
    verify_text = _cell(cells, col_map, "verify")
    row_text = " ".join(c for c in cells if c)
    # Computed FIRST, so every exit below can be finalised against it. §8.1's membership question
    # is "did this row claim weight", and that is answerable before any rule has run.
    claimed_weight = "weighted" in tier_tokens_of_row(cells, col_map, row_text)
    result.claimed_weight = claimed_weight

    if "strength" not in col_map:
        # This table has no identifiable strength/grade column at all (e.g.
        # a "surfaces not reached" table with only id|surface|status|note).
        # That is a tool-coverage limitation for this table shape, not a
        # rule violation in the row, so it is a warning, not an error.
        result.warnings.append(
            "no strength/grade column identified in this table — grade checks skipped, and "
            "the row is NOT counted in the tier totals"
        )
        # Same principle as an unnameable row: a row whose grade was never read must not be
        # counted as weighted. Before 2026-08-25 these defaulted into the weighted total, so
        # three of the kani-driver slice's rows were reported weighted without ever being graded.
        result.counted = False
        return _finalize(result, claimed_weight)

    grade, grade_errors = check_grade(strength_text)
    result.grade = grade
    result.errors.extend(grade_errors)

    if grade is None:
        # Grade unresolved (missing / ambiguous / invalid) — downstream checks need a known
        # grade, so stop here. The row is refused, not weighted and not unweighted: it claimed
        # a grade the vocabulary does not contain, so no tier statement about it is meaningful.
        return _finalize(result, claimed_weight)

    # --- WEIGHT (spec section 0, W1-W5) -------------------------------------
    # The format admits ANY claim. What it refuses is WEIGHT. A row is
    # unweighted when its grade has no deciding machinery, when its clause is
    # read off its own evidence, or when it says so explicitly.
    # --- W1: SILENCE IS UNWEIGHTED -----------------------------------------
    # The declared tier, or None when the row states nothing. Before 2026-08-25 this tool
    # computed `weighted = not (unweightable or marked_unweighted)`, so a row that stated NO
    # tier defaulted INTO the weighted tier -- the exact inversion of W1 ("omitted means
    # unweighted; the format never vouches by silence"), and the reason 88 rows were reported
    # weighted across four envelopes when not one of them had declared weight.
    marker = tier_marker(cells, col_map, row_text)
    # Did the row EXPLICITLY claim weight? This is the question §8.1 turns on, and it is not the
    # same as `result.weighted`, which is the claim AFTER the rules have had their say. Keying the
    # refusal invariant off the surviving flag meant a row whose claim was knocked down by an
    # earlier rule -- `**inspection-argued** · **weighted**`, or two contradictory markers -- drew
    # its error and then landed in the UNWEIGHTED count, which reports a refused row as a row that
    # never asked for anything (review, round 9).
    if marker == "contradictory":
        result.errors.append(
            "the row states BOTH tier markers — a rendering that declares two tiers has "
            "declared none, and W1 makes it unweighted (spec W4)"
        )
        marker = None
    marked_unweighted = marker == "unweighted"
    # W2.3: a clause read off its own evidence, or off nothing, cannot carry weight -- neither
    # can be falsified. When the table HAS a clause column, the token is read out of that cell
    # with the same derived enum pattern the rest of this file uses, and membership is tested
    # against the SHARED reserved set. When it does not, fall back to a delimited token in the
    # row text, which keeps prose safe ("not read off a test name" is a denial, not a claim).
    clause_cell = _cell(cells, col_map, "clause")
    if clause_cell is not None:
        clause_toks = clause_sources_in(clause_cell)
        clause_is_reserved = any(t in CLAUSE_SOURCES_UNWEIGHTABLE for t in clause_toks)
        if len(set(clause_toks)) > 1:
            result.errors.append(
                f"the clause cell declares more than one clause_source "
                f"({sorted(set(clause_toks))}) — W2.3 records ONE provenance for the item's "
                f"text, and two readers take two different claims from a cell that names two"
            )
    else:
        clause_is_reserved = bool(RESERVED_CLAUSE_TOKEN_RE.search(row_text)
                                  or "test's own name" in row_text.lower())
    unweightable = grade in UNWEIGHTABLE_GRADES or clause_is_reserved
    # Weight is claimed EXPLICITLY or not at all (W1).
    result.weighted = (marker == "weighted") and not unweightable
    result.declared_tier = marker

    # W4: a weight-eligible grade with no stated tier is the consumer-confusion case -- the
    # reader sees CONTRACT and assumes the format is behind it. The row is unweighted (W1);
    # the RENDERING is defective. Ratcheted like §8.1: reported now, error under
    # --strict-weight, because the fix is a re-render of existing envelopes.
    if marker is None and not unweightable:
        result.tier_unstated = True

    # W2.1: a row that CLAIMS weight on a grade with no deciding machinery is a refusal,
    # not a marking problem — say which rule refused it.
    if marker == "weighted" and unweightable:
        reason = ("its grade has no deciding machinery"
                  if grade in UNWEIGHTABLE_GRADES
                  else "its clause_source is one of the values reserved to mean unweightable "
                       f"({' / '.join(sorted(CLAUSE_SOURCES_UNWEIGHTABLE))}) — a clause read off "
                       "its own evidence, or off nothing, cannot be falsified")
        result.errors.append(
            f"WEIGHT REFUSED: the row is marked weighted but {reason} (spec W2)"
        )

    if grade == "unspecified":
        # An `unspecified` row asserts "no governing spec text exists for this surface". The
        # row should say so somewhere other than the grade token itself, which would otherwise
        # satisfy the check against itself. This check sat BELOW the unweighted early-return
        # until 2026-08-25 -- and `unspecified` is never weight-eligible, so it was dead code
        # that could not fire in any input. Moved above the return.
        ctx_cells = list(cells)
        sidx = col_map.get("strength")
        if sidx is not None and sidx < len(ctx_cells) and strength_text is not None:
            def _drop_grade_span(m: re.Match) -> str:
                return "" if _normalize_grade_text(m.group(1)) == grade else m.group(0)

            ctx_cells[sidx] = BOLD_RE.sub(_drop_grade_span, strength_text)
        context_text = " ".join(c for c in ctx_cells if c)
        warn = check_unspecified(context_text)
        if warn:
            result.warnings.append(warn)

    # --- §7.1: status x grade x weight coherence (S5) ------------------------
    # A `gap` claim carrying a weighted `contract` passed every check before 2026-08-25.
    # ERROR when the row claims weight; WARNING when it does not -- an unweighted prospective
    # grade is proposal P5, which the owner DEFERRED, and this rule must not adopt it sideways.
    status_cell = _cell(cells, col_map, "status")
    status_norm = normalize_status(status_cell)
    # A status this tool cannot place is not a status. Skipping the coherence check when
    # normalization fails let `status = nonsense` through clean on a WEIGHTED row, while the
    # manifest validator refused the same value against its closed vocabulary (review, round 5).
    # Only fires where a status cell actually exists and says something: a table with no status
    # column is a tool-coverage limit, not a producer error.
    # An EMPTY cell in a status column is the same undecidable case as an unrecognised one, and
    # it was passing clean while a manifest with no `status` field was refused (review, round 6).
    # A table with NO status column stays the stated tool-coverage limit: the row cannot be
    # blamed for a column its rendering does not have.
    if result.weighted and status_cell is not None and status_norm is None:
        shown = status_cell.strip()
        multi = sorted(set(statuses_in(status_cell)))
        result.errors.append(
            f"WEIGHT REFUSED: status {shown!r} names more than one status {multi} — a cell "
            f"naming two has named none, and §7.1 coherence cannot be decided (spec §7.1/§7.3)"
            if len(multi) > 1 else
            f"WEIGHT REFUSED: status {shown!r} is not one of the closed status vocabulary "
            f"{sorted(STATUSES)} (spec §7.1/§7.3), so §7.1 coherence cannot be decided for this "
            f"row — an undecidable coherence check must refuse, not skip"
            if shown else
            f"WEIGHT REFUSED: this table has a status column and the cell is EMPTY. `status` is "
            f"required on a weighted claim (spec §7.1/§7.3); without it §7.1 coherence cannot be "
            f"decided, and an undecidable coherence check must refuse, not skip"
        )
    incoherent = check_status_grade(status_norm, grade)
    if incoherent:
        if result.weighted:
            result.errors.append(f"INCOHERENT: {incoherent}")
        else:
            result.warnings.append(f"§7.1: {incoherent}")

    # §7.3 (P4): a blocked status must name what blocks it, or the escalation is prose again.
    # ERROR on a row that claims weight (P4 is ADOPTED, not a proposal: `blocked_by` is REQUIRED),
    # warning otherwise. It was a warning in both cases until 2026-08-25, so a weighted `blocked`
    # row kept its weight while naming nothing.
    if status_norm == "blocked" and not BLOCKED_BY_RE.search(row_text):
        msg = ("§7.3: status 'blocked' does not name what blocks it — add "
               "`blocked-by: <what>`; without it an escalation reads as a backlog entry")
        if result.weighted:
            result.errors.append(f"WEIGHT REFUSED: {msg}")
        else:
            result.warnings.append(msg)

    # §7.2 (P3): a predicate item must state its fraction and what it ranges over. A weighted
    # predicate row with no fraction is REFUSED WEIGHT (§7.2: "*Some* is not a status") -- it was
    # routed into `weight-pending` until 2026-08-25, which put a rule adopted the same day onto a
    # backlog whose whole meaning is "these rows were fine until the rules changed" (§8.1, S4).
    if PREDICATE_DECL_RE.search(row_text):
        if not FRACTION_RE.search(row_text):
            msg = ("§7.2: a predicate item states no fraction — 'some' is not a status; "
                   "give N of M over a named sub-list")
            if result.weighted:
                result.errors.append(f"WEIGHT REFUSED: {msg}")
            else:
                result.warnings.append(msg)
        elif not OVER_RE.search(row_text):
            msg = ("§7.2: a predicate item states a fraction but does not name the sub-list it "
                   "ranges over — a denominator with no named list is not checkable")
            if result.weighted:
                result.errors.append(f"WEIGHT REFUSED: {msg}")
            else:
                result.warnings.append(msg)

    # Unweighted rows carry NO further obligations: the format promises nothing
    # about them, so there is nothing to enforce (spec W3).
    if not result.weighted:
        return _finalize(result, claimed_weight)

    if grade in NEEDS_RECIPE:
        err = check_recipe(verify_text, letters)
        if err:
            result.errors.append(f"WEIGHT REFUSED: [grade={grade}] {err}")

    if grade in NEEDS_BOUNDS:
        err = check_bounds(strength_text, row_text)
        if err:
            result.errors.append(f"WEIGHT REFUSED: [grade={grade}] {err}")

    # core.md §4, corrected 2026-08-25: positive_control is required on EVERY not-covered row,
    # not only on the ones whose recipe looks grep-shaped. The old trigger disagreed with the §1
    # table and with check_acceptance.py, and it let a not-covered row escape the requirement by
    # naming a command the tool did not recognise as an absence check.
    if grade == "not-covered":
        err, warn = check_positive_control(verify_text, row_text, letters)
        if err:
            result.errors.append(err)
        if warn:
            result.warnings.append(warn)

    if grade == "out-of-scope":
        err = check_out_of_scope(verify_text, row_text)
        if err:
            result.errors.append(f"WEIGHT REFUSED: {err}")

    # --- W2.3 / W2.5, adopted 2026-08-25 (P1, P2) ---------------------------
    # A row that claims weight and meets every pre-adoption rule, but lacks the newly required
    # machinery, is refused weight into the transitional `weight-pending` state (core.md §8.1).
    # Checked AFTER the pre-adoption obligations above, so a row is told about those defects too.
    # P1 (W2.3) applies to EVERY weight-eligible grade, not only the recipe-bearing ones.
    # `out-of-scope` is weight-eligible and was skipped entirely, so a row could carry weight
    # with no recorded provenance at all by choosing that grade (S2).
    cs = clause_source_of(clause_cell)
    if cs is None:
        if clause_cell is None or not clause_cell.strip():
            result.pending_reasons.append("clause_source not recorded (W2.3, P1)")
        else:
            result.pending_reasons.append(
                "clause_source is free prose, not one of the closed enum "
                "(spec-document | external-standard | doc-comment | test-name | none) "
                "(W2.3, P1)"
            )

    if grade in NEEDS_RECIPE:
        # P2 (W2.5): the recipe must have been watched to fail, and the witness must bind to
        # THIS row's recipe (§4.1). Structured -- a phrase is not a witness.
        satisfied, complaints = watched_fail_witness(grade, verify_text, row_text, letters)
        for c in complaints:
            result.warnings.append(f"§4.1: {c}")
        if not satisfied:
            result.pending_reasons.append("no watched-fail witness (W2.5, P2)")

    # S4 -- the weight-pending membership invariant. §8.1 defines the state as "claims weight,
    # satisfies every rule that PREDATES the adoption, and lacks only the newly-required
    # machinery". A row that also violates a pre-adoption rule is not pending; it is refused
    # outright, and calling it pending would put a broken row on a remediation list whose whole
    # meaning is "these rows were fine until the rules changed".
    if result.pending_reasons:
        if result.errors:
            result.pending_reasons = []
            result.weighted = False
        else:
            result.pending = True
            result.weighted = False

    # THE INVARIANT (review, round 8). A row could hold weighted=True AND a WEIGHT REFUSED error at
    # the same time: weight was cleared only on the pending path, so a row refused by an ERROR
    # stayed in the weighted set -- and W5's totals are computed from exactly that flag. The
    # checker reported the row as refused and counted it as weighted in the same run, which is an
    # overclaim in the number a reader quotes.
    #
    # A refused row is counted in NEITHER tier, matching §8.1's treatment on the TOML side: it is
    # not weighted (the errors say so) and it is not unweighted (it claimed weight honestly and
    # failed). `_assert_weight_invariant` in the selftest asserts this can never come apart again.
    return _finalize(result, claimed_weight)


def declared_count_tuples(text: str) -> list[tuple[int, int]]:
    """EVERY `<N> weighted, <M> unweighted` tuple the document states, in order."""
    return [(int(m.group(1)), int(m.group(2))) for m in DECLARED_COUNTS_RE.finditer(text)]


def declared_counts(text: str) -> tuple[int, int] | None:
    """W5: the tier counts the DOCUMENT states, or None if it states none or states several.

    ALL tuples are parsed, not the first (review, round 6 — and it overruled my round-5 decision to
    leave this, correctly). I had reasoned about it as a MISREPORT risk: two envelopes legitimately
    recorded a superseded figure beside the current one, the current one came first, and erroring
    on multiplicity would have fired on honest prose. That analysis missed that the producer
    chooses the order. Put the historical tuple first and an overstated current tuple second and
    the checker validates against the historical one and exits clean — an OVERCLAIM PATH, which
    ranks above the false-positive cost every time. The two envelopes were reworded instead."""
    tuples = declared_count_tuples(text)
    return tuples[0] if len(set(tuples)) == 1 else None


def declared_pending(text: str) -> int | None:
    """W5: the `weight-pending` count the DOCUMENT states, or None if it states none."""
    m = DECLARED_PENDING_RE.search(text)
    if not m:
        return None
    return int(m.group(1) if m.group(1) is not None else m.group(2))


def check_file_text(text: str) -> list[RowResult]:
    lines = text.splitlines()
    tables = extract_tables(lines)
    # core.md §4.2: recipe letters are validated against THIS document's own declared recipe
    # table, not a global alphabet. Falls back to RECIPE_LETTERS when the document declares none.
    letters = declared_recipe_letters(lines) or RECIPE_LETTERS
    results: list[RowResult] = []
    for table in tables:
        col_map = build_col_map(table.header)
        # A markdown table is a LEDGER table only if its header carries the ledger column
        # signature -- a `status` and/or `strength`/`grade` column. Without either, this is some
        # OTHER table the document happens to render (an outcome-vocabulary table, a legend, a
        # reference table) and `match_row_id`'s backtick+ID-shape heuristic can still fire on an
        # unrelated first cell that happens to look like an id (e.g. `` `EXECUTED-PASS` `` in
        # core.md §8.2's outcome table) -- a false-positive ledger row this checker has no
        # business reporting on at all, UNCHECKED or otherwise. Skip the whole table, not just
        # the row-id match, so this can never fire per-row by accident.
        if "status" not in col_map and "strength" not in col_map:
            continue
        for line_no, cells in table.rows:
            if not cells:
                continue
            row_id = match_row_id(cells[0])
            if row_id is None:
                # Row-set integrity: a backticked first cell in a table that HAS a
                # strength/grade column is a ledger row this tool could not name. Silently
                # skipping it is the "cover-block count blind to a vanished block" failure —
                # the file would report 0 errors over a row set nobody verified. Say so.
                c = cells[0].strip()
                backticked = len(c) >= 2 and c[0] == "`" and c[-1] == "`"
                # N5 (cold reader, 2026-08-26): an UNBACKTICKED id-shaped first cell got no report
                # at all. W5's stated limit promises that rows the tool cannot name are reported
                # as UNCHECKED and excluded from both sides of the count — and that promise was
                # true only for the backticked-but-unparseable case. `| TOY-9 | ... |` in a graded
                # table vanished in silence, which is precisely the failure the backticked branch
                # exists to prevent, reached by leaving the backticks off.
                looks_like_an_id = bool(UNBACKTICKED_ID_RE.match(c))
                if (backticked or looks_like_an_id) and "strength" in col_map:
                    r = RowResult(row_id=c.strip("`"), line_no=line_no, counted=False)
                    how = ("first cell is backticked" if backticked
                           else "first cell is id-shaped but NOT backticked")
                    r.warnings.append(
                        f"{how} and this table has a grade column, but the id does not match the "
                        f"ledger-row pattern — this row was NOT checked and is NOT counted in the "
                        f"tier totals"
                    )
                    results.append(r)
                continue
            results.append(process_row(row_id, line_no, cells, col_map, letters))
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run_file(path: str, strict_weight: bool = False) -> tuple[int, int]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    results = check_file_text(text)
    n_errors = 0
    n_warnings = 0
    for r in results:
        for msg in r.errors:
            print(f"{path}:{r.row_id}: ERROR: {msg}")
            n_errors += 1
        # W4: weight-eligible grade, no stated tier. Unweighted by W1; defective as a rendering.
        # Ratcheted like §8.1.
        if r.tier_unstated:
            level = "ERROR" if strict_weight else "WARNING"
            print(f"{path}:{r.row_id}: {level}: TIER NOT STATED: the grade is weight-eligible and "
                  f"the row declares no tier — W1 makes it UNWEIGHTED, and a reader seeing the "
                  f"grade alone cannot know that (spec W4)")
            if strict_weight:
                n_errors += 1
            else:
                n_warnings += 1
        # core.md §8.1: a transitional refusal. WARNING today, ERROR under --strict-weight —
        # the ratchet that retires this state once the backlog reaches zero.
        for reason in r.pending_reasons:
            level = "ERROR" if strict_weight else "WARNING"
            print(f"{path}:{r.row_id}: {level}: WEIGHT REFUSED (transitional): {reason}")
            if strict_weight:
                n_errors += 1
            else:
                n_warnings += 1
        for msg in r.warnings:
            print(f"{path}:{r.row_id}: WARNING: {msg}")
            n_warnings += 1
    counted = [r for r in results if r.counted]
    n_p = sum(1 for r in counted if r.pending)
    n_w = sum(1 for r in counted if r.weighted)
    n_r = sum(1 for r in counted if r.refused)
    n_u = len(counted) - n_w - n_p - n_r
    n_skipped = len(results) - len(counted)
    # W5: a consumer must never have to infer the mix.
    skip_note = f", {n_skipped} UNCHECKED rows" if n_skipped else ""
    n_unstated = sum(1 for r in counted if r.tier_unstated)
    pend_note = f", {n_p} weight-pending" if n_p else ""
    if n_r:
        pend_note += f", {n_r} refused (counted in neither tier)"
    if n_unstated:
        pend_note += f", {n_unstated} tier-unstated"
    print(f"check_ledger: {len(counted)} rows checked "
          f"({n_w} weighted, {n_u} unweighted{pend_note}){skip_note}, "
          f"{n_errors} errors, {n_warnings} warnings")
    # The GRADE-STRENGTH split, derived from the grade tokens rather than typed. Reported beside
    # the weight counts and never merged into them, in words that cannot be mistaken for them.
    strengths = [grade_strength(r.grade) for r in counted]
    n_gd = strengths.count("deciding")
    n_ga = strengths.count("asserted")
    n_gx = strengths.count(None)
    unresolved = f", {n_gx} unresolved" if n_gx else ""
    print(f"check_ledger: grade strength: {n_gd} deciding-grade (contract/mechanical), "
          f"{n_ga} asserted-grade{unresolved}")
    # --- W5: declared vs computed (S6/P7) -----------------------------------
    # More than one DISTINCT stated tuple is an error in its own right, before any comparison:
    # a rendering that states two different mixes has stated none, and whichever one a checker
    # picks is the one a producer can choose to be checked against.
    all_tuples = declared_count_tuples(text)
    if len(set(all_tuples)) > 1:
        print(f"{path}: ERROR: W5: this rendering states {len(set(all_tuples))} DIFFERENT tier-count "
              f"tuples {sorted(set(all_tuples))} — W5 states the counts once. A superseded figure "
              f"must be reworded so it no longer reads as a count (spell the numbers as words, or "
              f"restructure the sentence); otherwise the checker validates against whichever tuple "
              f"comes first, which the producer chooses")
        n_errors += 1
    declared = declared_counts(text)
    if declared is None and not all_tuples:
        if results:
            level = "ERROR" if strict_weight else "WARNING"
            print(f"{path}: {level}: W5: this rendering states no tier counts — a consumer must "
                  f"never have to infer the mix (computed: {n_w} weighted, {n_u} unweighted)")
            if strict_weight:
                n_errors += 1
            else:
                n_warnings += 1
    elif declared is not None and declared != (n_w, n_u):
        print(f"{path}: ERROR: W5: declared tier counts {declared[0]} weighted, {declared[1]} "
              f"unweighted do not match the computed {n_w} weighted, {n_u} unweighted — a typed "
              f"count that has drifted from the rows is worse than none, because a reader quotes it")
        n_errors += 1
    # W5's THIRD count. `weight-pending: P` is stated "while any exists", so both directions are
    # checked: a stated count that has drifted, and rows that are pending under a rendering that
    # names no pending count at all.
    if declared is not None:
        dp = declared_pending(text)
        if dp is None and n_p:
            print(f"{path}: ERROR: W5: {n_p} row(s) are weight-pending and this rendering states "
                  f"no weight-pending count — W5 requires it while any exists (§8.1)")
            n_errors += 1
        elif dp is not None and dp != n_p:
            print(f"{path}: ERROR: W5: declared weight-pending {dp} does not match the computed "
                  f"{n_p} — the pending count IS the remediation backlog (§8.1), so a drifted one "
                  f"understates or invents work")
            n_errors += 1

    if n_p:
        # The remediation backlog, itemised. This count IS the work list; it must not be
        # absorbed into a tier that promises nothing (core.md §8.1).
        by_reason: dict[str, int] = {}
        for r in counted:
            for reason in r.pending_reasons:
                by_reason[reason] = by_reason.get(reason, 0) + 1
        detail = " · ".join(f"{k}: {v}" for k, v in sorted(by_reason.items()))
        print(f"check_ledger: remediation backlog for {path} — {detail}")
    return n_errors, n_warnings


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------


def _table(rows: list[str], header: str = "| id | rule | status | strength | verify |") -> str:
    sep = "|" + "|".join(["---"] * header.count("|") ) + "|"
    # build separator matching column count
    ncols = header.count("|") - 1
    sep = "|" + "|".join(["---"] * ncols) + "|"
    return "\n".join([header, sep] + rows)


def _run_case(name: str, md: str, expect_errors: bool, expect_warnings: bool = False,
              expect_substr: str | None = None) -> str | None:
    results = check_file_text(md)
    all_errors = [m for r in results for m in r.errors]
    # Transitional weight refusals (§8.1) are warnings in the default mode, so they are matched
    # like warnings here — a fixture asserting one is asserting the row lost weight.
    all_warnings = [m for r in results for m in r.warnings]
    all_warnings += [f"WEIGHT REFUSED (transitional): {m}"
                     for r in results for m in r.pending_reasons]
    all_warnings += ["TIER NOT STATED (spec W4)" for r in results if r.tier_unstated]
    got_errors = len(all_errors) > 0
    got_warnings = len(all_warnings) > 0
    if got_errors != expect_errors:
        return (
            f"{name}: expected errors={expect_errors}, got errors={got_errors} "
            f"({all_errors})"
        )
    if expect_warnings and not got_warnings:
        return f"{name}: expected at least one warning, got none"
    # A case that declares NO errors and NO warnings is asserting the row is CLEAN and KEPT ITS
    # WEIGHT. Until 2026-08-25 (third round) this harness only checked the error count, so a
    # tightening that started refusing weight to a "clean" fixture went unreported: the fixture
    # still had zero errors, the row was silently `weight-pending`, and the suite stayed green.
    # That is the tool's own version of the defect the format exists to catch, one level down.
    if not expect_errors and not expect_warnings:
        stray = [f"pending: {m}" for r in results for m in r.pending_reasons]
        stray += [f"warning: {m}" for r in results for m in r.warnings]
        stray += ["TIER NOT STATED" for r in results if r.tier_unstated]
        if stray:
            return (
                f"{name}: declared clean, but the row did not come through clean: {stray}"
            )
    if expect_substr is not None:
        joined = " ".join(all_errors + all_warnings)
        if expect_substr not in joined:
            return f"{name}: expected substring {expect_substr!r} in messages, got: {joined}"
    return None


def selftest() -> int:
    cases: list[tuple[str, str, bool, bool, str | None]] = []

    # 1. clean contract row passes cleanly.
    cases.append((
        "clean-contract-row",
        _table([
            "| `X-1` | some rule | S-3.2 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · **weighted** | "
            "`K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))

    # 2. free-text substitute ("derived") errors.
    cases.append((
        "free-text-substitute-derived",
        _table([
            "| `X-2` | some claim | evidenced | derived | `K mod::proofs::foo` |",
        ]),
        True, False, "no bolded grade token",
    ))

    # 3. compound cell ("mechanical, gate-enforced") errors.
    cases.append((
        "compound-cell",
        _table([
            "| `X-3` | some claim | evidenced | **mechanical, gate-enforced** | `K mod::proofs::foo` |",
        ]),
        True, False, "closed vocabulary",
    ))

    # 4. two different grade tokens in one cell -> ambiguity error.
    cases.append((
        "ambiguous-two-grades",
        _table([
            "| `X-4` | some claim | evidenced | **contract** (...) also **inspection-argued** | `K mod::proofs::foo` |",
        ]),
        True, False, "ambiguous grade",
    ))

    # 5. contract row with empty verify cell -> recipe error.
    cases.append((
        "contract-empty-verify",
        _table([
            "| `X-5` | some rule | evidenced | **CONTRACT** (bounded, unwind=8) · **weighted** |  |",
        ]),
        True, False, "no deciding recipe",
    ))

    # 6. contract row with no bounds keyword anywhere -> bounds error.
    cases.append((
        "contract-no-bounds",
        _table([
            "| `X-6` | some rule with no bounds words | evidenced | **CONTRACT** · **weighted** | `K mod::proofs::foo` |",
        ]),
        True, False, "does not declare boundedness",
    ))

    # 7. contract row WITH bounds keyword and recipe -> clean.
    cases.append((
        "contract-with-bounds",
        _table([
            "| `X-7` | some rule | X.690 6.2 (external-standard) | evidenced | "
            "**CONTRACT** (unbounded: Lean lid over all lengths) · **weighted** | "
            "`K mod::proofs::foo` · `N thm`. mutation-control(K mod::proofs::foo): flip the "
            "comparison -> the kernel rejects the mutated theorem, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))

    # 8. not-covered row referencing grep with NO control -> error.
    cases.append((
        "not-covered-grep-no-control",
        _table([
            "| `X-8` | some absence claim | gap | **not-covered** · **weighted** | "
            "`A grep -n 'foo' src/bar.rs` |",
        ]),
        True, False, "positive control",
    ))

    # 9. not-covered row referencing grep WITH control -> clean.
    cases.append((
        "not-covered-grep-with-control",
        _table([
            "| `X-9` | some absence claim | RFC 5280 4.2 (external-standard) | gap | "
            "**not-covered** · **weighted** | `A grep -n 'foo' src/bar.rs` -> empty. positive-control(A grep -n 'foo' src/bar.rs): "
            "the same pattern against src/baz.rs -> 3 matching lines, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))

    # 10. A section reference does NOT satisfy §4 (changed 2026-08-25, eighth round). It used to
    # DOWNGRADE the missing control to a warning, which made a citation admission-affecting: the
    # row kept its weight because it pointed somewhere else. The citation survives as a hint
    # attached to the error, which cannot flip it.
    cases.append((
        "not-covered-grep-section-deferral-does-not-satisfy-the-obligation",
        _table([
            "| `X-10` | some absence claim | gap | **not-covered** · **weighted** | "
            "`A grep -n 'foo' src/bar.rs` -> empty, see §6.1 |",
        ]),
        True, False, "a citation does not satisfy the obligation",
    ))

    # 11. out-of-scope row with empty verify -> error.
    cases.append((
        "out-of-scope-empty-verify",
        _table([
            "| `X-11` | some scope claim | gap | **out-of-scope** · **weighted** |  |",
        ]),
        True, False, "does not cite a source",
    ))

    # 12. out-of-scope row with non-empty verify -> clean.
    cases.append((
        "out-of-scope-with-source",
        _table([
            "| `X-12` | some scope claim | gap | **out-of-scope** | "
            "`D README.md` scope section |",
        ]),
        # W4: `out-of-scope` IS weight-eligible, so a row that states no tier is the
        # consumer-confusion case. Unweighted by W1, defective as a rendering.
        False, True, "TIER NOT STATED",
    ))

    # 13. unspecified row with no wording -> warning.
    cases.append((
        "unspecified-no-wording",
        _table([
            "| `X-13` | some claim | n/a | **unspecified** | `D some/ref.rs` |",
        ]),
        False, True, "does not say so anywhere in the row",
    ))

    # 14. unspecified row WITH wording -> clean.
    cases.append((
        "unspecified-with-wording",
        _table([
            "| `X-14` | some claim, clause source: none, unspecified | n/a | "
            "**unspecified** · **UNWEIGHTED** | `D some/ref.rs` |",
        ]),
        False, False, None,
    ))

    # 15. non-ledger rows (no backticked id in first cell) are ignored.
    cases.append((
        "non-ledger-row-ignored",
        _table([
            "| **U1** | some usefulness entry | some evidence | **strong** |",
        ], header="| # | what | evidence | strength |"),
        False, False, None,
    ))

    # 16. 6-column table (id | requirement | clause | status | strength | verify)
    # still resolves the strength/verify columns correctly, and recognises
    # the compound recipe id `A0` (letter + digits, no space).
    cases.append((
        "six-column-table",
        _table([
            "| `X-16` | some requirement | S-1 (spec-document) | gap | **not-covered** · **weighted** | "
            "`A0` -> empty. positive-control(A0): the same pattern against a known-present file "
            "-> 4 matching lines, observed 2026-08-25 |",
        ], header="| id | requirement | clause | status | strength | verify |"),
        False, False, None,
    ))

    # 17-19. The weight tier (spec section 0, W1-W5).
    cases.append((
        "unweighted-fluffy-row-is-clean",
        _table([
            "| `X-17` | we believe this is fine | n/a | **inspection-argued** · **UNWEIGHTED** | see notes |",
        ]),
        False, False, None,
    ))
    # A clause read off the test's own name is unweightable (W2.3). The signal is the
    # clause-source cell — a delimited token — not a bare phrase in running prose.
    cases.append((
        "test-name-clause-must-be-marked",
        _table([
            "| `X-18` | some behaviour | *test-name* | evidenced | **test-only** · **weighted** | `T mod::tests::x` |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "reserved to mean unweightable",
    ))
    cases.append((
        "test-name-clause-marked-unweighted-is-clean",
        _table([
            "| `X-18b` | some behaviour | *test-name* | evidenced | "
            "**test-only** · ⚠ **UNWEIGHTED** | `T mod::tests::x` |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    cases.append((
        "weighted-row-missing-recipe-is-refused",
        _table([
            "| `X-19` | a real claim | n/a | **CONTRACT** (bounded, unwind=8) · **weighted** | |",
        ]),
        True, False, "no deciding recipe named",
    ))

    # 20-22. Row-set integrity (added 2026-08-25). A sub-item id with a lowercase suffix IS a
    # ledger row and must be checked; a backticked non-id in a graded table must be reported as
    # UNCHECKED rather than skipped in silence. Positive controls, both watched to fire.
    cases.append((
        "sub-item-id-with-lowercase-suffix-is-checked",
        _table([
            "| `X-20a` | a sub-item claim | evidenced | **CONTRACT** · **weighted** | |",
        ]),
        True, False, "no deciding recipe named",
    ))
    cases.append((
        "backticked-non-id-in-graded-table-is-reported-unchecked",
        _table([
            "| `mod::proofs::foo` | a harness | evidenced | **CONTRACT** | |",
        ]),
        False, True, "was NOT checked",
    ))
    cases.append((
        "backticked-non-id-in-ungraded-table-stays-silent",
        _table([
            "| `mod::proofs::foo` | some buffer | some reason |",
        ], header="| harness | buffer | why |"),
        False, False, None,
    ))

    # 23-27. W4 tier markers must be EXPLICIT (added 2026-08-25). The prose-substring
    # reading let a strong row exempt itself from every weighted obligation.
    cases.append((
        "prose-mention-of-unweighted-does-not-exempt-a-strong-row",
        _table([
            "| `X-23` | a real claim (unlike the unweighted rows in §4) | evidenced | **CONTRACT** · **weighted** | |",
        ]),
        True, False, "no deciding recipe named",
    ))
    cases.append((
        "prose-mention-of-a-test-name-does-not-exempt-a-strong-row",
        _table([
            "| `X-24` | a real claim, not read off a test name | evidenced | **CONTRACT** · **weighted** | |",
        ]),
        True, False, "no deciding recipe named",
    ))
    cases.append((
        "bracket-U-marker-satisfies-W4",
        _table([
            "| `X-25` | [U] a documented human argument | n/a | **inspection-argued** | see notes |",
        ]),
        False, False, None,
    ))
    cases.append((
        "dedicated-weight-column-satisfies-W4",
        _table([
            "| `X-26` | a human argument | n/a | **inspection-argued** | unweighted — nothing to run | see notes |",
        ], header="| id | claim | status | grade | weight | verify |"),
        False, False, None,
    ))
    cases.append((
        "row-marked-weighted-on-an-unweightable-grade-is-refused",
        _table([
            "| `X-27` | a human argument | n/a | **inspection-argued** | **weighted** | see notes |",
        ], header="| id | claim | status | grade | weight | verify |"),
        True, False, "no deciding machinery",
    ))

    # 29. A not-covered row whose recipe is NOT grep-shaped still owes a positive control
    # (core.md §4, unconditional). Watched to fail: this passed before 2026-08-25.
    cases.append((
        "not-covered-non-grep-recipe-still-needs-a-control",
        _table([
            "| `X-29` | some absence claim | gap | **not-covered** · **weighted** | "
            "`cargo test --list` shows no such test |",
        ]),
        True, False, "positive control",
    ))

    # 30-32. W2.3 / W2.5 (P1, P2 -- adopted 2026-08-25). All three fail on the pre-adoption
    # code: it emitted no such refusal, and counted every one of these rows as weighted.
    cases.append((
        "P1-weighted-row-with-no-clause-source-is-refused",
        _table([
            "| `X-30` | some rule | evidenced | **CONTRACT** (bounded, unwind=8) · **weighted** | "
            "`K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ]),
        False, True, "clause_source not recorded",
    ))
    cases.append((
        "P2-weighted-row-with-no-watched-fail-witness-is-refused",
        _table([
            "| `X-31` | some rule | S-3.2 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · **weighted** | "
            "`K mod::proofs::foo` |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "no watched-fail witness",
    ))
    cases.append((
        "P1-P2-both-satisfied-row-keeps-its-weight",
        _table([
            "| `X-32` | some rule | S-3.2 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · **weighted** | "
            "`K mod::proofs::foo`. mutation-control(K mod::proofs::foo): flip the comparison -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))

    # 35-37. W1: SILENCE IS UNWEIGHTED (S3). All three fail on the pre-2026-08-25 code, which
    # defaulted an unmarked row INTO the weighted tier.
    cases.append((
        "S3-unmarked-weight-eligible-row-is-unweighted-not-weighted",
        _table([
            "| `X-35` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) | "
            "`K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate it -> fails |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "TIER NOT STATED",
    ))
    cases.append((
        "S3-unmarked-unweightable-grade-needs-no-marker",
        _table([
            "| `X-36` | a human argument | n/a | **inspection-argued** | see notes |",
        ]),
        False, False, None,
    ))

    # 38-42. S1/S2: structured witnesses and the closed clause_source enum. Every one of these
    # passed clean and counted WEIGHTED before 2026-08-25.
    cases.append((
        "S1-witness-naming-a-different-recipe-is-refused",
        _table([
            "| `X-38` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. mutation-control(K other::proofs::bar): "
            "flip it -> that one fails |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "does not name any recipe of THIS row",
    ))
    cases.append((
        "S1-bare-phrase-is-not-a-witness",
        _table([
            "| `X-39` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo` mutation control |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "phrase presence is not a witness",
    ))
    cases.append((
        "S1-witness-with-no-observation-is-refused",
        _table([
            "| `X-40` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): I broke it |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "states no observation",
    ))
    cases.append((
        "S1-positive-control-does-not-witness-a-contract",
        _table([
            "| `X-41` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. positive-control(K mod::proofs::foo): "
            "a matching input -> hits |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "does not satisfy §4.1 for grade 'contract'",
    ))
    cases.append((
        "S2-out-of-scope-row-owes-clause-source-too",
        _table([
            "| `X-42` | some scope claim | | gap | **out-of-scope** · **weighted** | "
            "`D README.md` scope section |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "clause_source not recorded",
    ))
    cases.append((
        "S2-free-prose-clause-source-is-not-a-declaration",
        _table([
            "| `X-43` | some rule | a stable RFC | evidenced | **test-only** · **weighted** | "
            "`T mod::tests::x`. watched-fail(T mod::tests::x): delete the impl -> test fails |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "free prose, not one of the closed enum",
    ))

    # 44-48. §7.1 coherence (S5), §7.2 predicate items (P3), §7.3 blocked (P4), §8.1
    # membership (S4). All red on the pre-2026-08-25 code.
    cases.append((
        "S5-gap-status-cannot-carry-a-weighted-contract",
        _table([
            "| `X-44` | some rule | S-1 (spec-document) | gap | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): "
            "flip it -> fails |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "cannot be a gap and a proof at the same time",
    ))
    cases.append((
        "S5-unweighted-prospective-grade-warns-but-does-not-error-P5-deferred",
        _table([
            "| `X-45` | some rule | S-1 (spec-document) | gap | **probe** (bounded, unwind=8) · "
            "**UNWEIGHTED** | none yet |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "cannot be a gap and a proof at the same time",
    ))
    cases.append((
        "P4-blocked-status-must-name-what-blocks-it",
        _table([
            "| `X-46` | some rule | S-1 (spec-document) | BLOCKED | **not-covered** · "
            "**UNWEIGHTED** | `A grep foo` -> empty |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "does not name what blocks it",
    ))
    cases.append((
        "P3-predicate-item-must-state-its-fraction",
        _table([
            "| `X-47` | `predicate`: must hold of every harness | S-1 (spec-document) | "
            "in progress | **probe** (bounded, unwind=8) · **UNWEIGHTED** | `K mod::proofs::foo` |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "'some' is not a status",
    ))
    cases.append((
        "S4-a-row-failing-a-PRE-adoption-rule-is-not-weight-pending",
        _table([
            "| `X-48` | some rule | | evidenced | **CONTRACT** · **weighted** | |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "no deciding recipe named",
    ))

    # 49-56. review round-2. Every one of these passed clean and counted WEIGHTED on the
    # 2026-08-25-morning code; each was watched red against it before the fix landed.
    #
    # Finding 1: a nonsense recipe reference. `K ???` parsed as a recipe, so it satisfied the
    # verify-cell requirement AND bound the witness to itself.
    cases.append((
        "R2-1-nonsense-recipe-ref-is-refused",
        _table([
            "| `X-49` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K ???`. watched-fail(K ???): changed anything -> saw red |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "no recognisable recipe reference",
    ))
    cases.append((
        "R2-1-recipe-table-metavariable-is-not-an-instance",
        _table([
            "| `X-50` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K <H>`. watched-fail(K <H>): negate it -> fails |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "no recognisable recipe reference",
    ))
    cases.append((
        "R2-1-placeholder-recipe-arg-is-refused",
        _table([
            "| `X-51` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K TODO`. watched-fail(K TODO): negate it -> fails |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "no recognisable recipe reference",
    ))
    cases.append((
        "R2-1-prose-mentioning-cargo-is-not-a-recipe",
        _table([
            "| `X-52` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | we ran cargo and it was fine |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "no recognisable recipe reference",
    ))
    # Positive control for finding 1: a real recipe body still parses, and a backticked literal
    # command still counts. Without these the fix could pass by refusing everything.
    cases.append((
        "R2-1-positive-control-real-recipe-still-passes",
        _table([
            "| `X-53` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    cases.append((
        "R2-1-positive-control-backticked-literal-command-still-passes",
        _table([
            "| `X-54` | some rule | S-1 (spec-document) | evidenced | **mechanical** · "
            "**weighted** | `cargo fmt --check`. watched-fail(cargo fmt --check): reformat one "
            "file -> the gate fails |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, None,
    ))
    # Finding 3: the §7.1 TABLE, not only its one-sentence summary. `partial` + `not-covered`
    # is not named by the sentence and passed weighted.
    cases.append((
        "R2-3-partial-status-cannot-carry-not-covered",
        _table([
            "| `X-55` | some rule | S-1 (spec-document) | partial | **not-covered** · "
            "**weighted** | `A grep -n 'foo' src/bar.rs` -> empty. positive-control(A grep -n "
            "'foo' src/bar.rs): the same pattern against src/baz.rs -> hits |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "does not cohere with grade 'not-covered'",
    ))
    cases.append((
        "R2-3-evidenced-status-cannot-carry-out-of-scope",
        _table([
            "| `X-56` | some scope claim | S-1 (spec-document) | evidenced | **out-of-scope** · "
            "**weighted** | `D README.md` §2 scope |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "does not cohere with grade 'out-of-scope'",
    ))
    # Finding 6: P4 blocked_by is REQUIRED, so a WEIGHTED blocked row that names nothing is
    # refused, not warned.
    cases.append((
        "R2-6-weighted-blocked-row-without-blocked-by-is-refused",
        _table([
            "| `X-57` | some rule | S-1 (spec-document) | BLOCKED | **not-covered** · "
            "**weighted** | `A grep -n 'foo' src/bar.rs` -> empty. positive-control(A grep -n "
            "'foo' src/bar.rs): src/baz.rs -> hits |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "does not name what blocks it",
    ))
    # Finding 6: predicate detection is DECLARATIVE. The bare word in prose no longer fires...
    cases.append((
        "R2-6-predicate-detection-is-declarative-not-semantic",
        _table([
            "| `X-58` | this predicate must hold of every harness | S-1 (spec-document) | "
            "in progress | **probe** (bounded, unwind=8) · **UNWEIGHTED** | `K mod::proofs::foo` |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    # ...and the declared token does, on a weighted row, as an outright refusal (§7.2).
    cases.append((
        "R2-6-declared-weighted-predicate-with-no-fraction-is-refused",
        _table([
            "| `X-59` | `predicate` over every harness | S-1 (spec-document) | partial | "
            "**probe** (bounded, unwind=8) · **weighted** | `K mod::proofs::foo`. watched-fail(K "
            "mod::proofs::foo): negate it -> fails |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "'some' is not a status",
    ))

    # 61-67. review round-3. The first is THE REVIEW'S EXACT ROW: it passed clean and counted WEIGHTED on the
    # previous commit, while its TOML twin was refused -- a live parity break, in the direction
    # that matters (the representation a human reads was the permissive one).
    cases.append((
        "R3-1-out-of-scope-with-a-locator-free-source-is-refused",
        _table([
            "| `O-1` | h is deliberately not implemented | S-1 (spec-document) | gap | "
            "**out-of-scope** · **weighted** | nonsense |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "cites no LOCATOR",
    ))
    # Positive control: the same row with a real locator keeps its weight, so the fix is not
    # "refuse every out-of-scope row".
    cases.append((
        "R3-1-positive-control-out-of-scope-with-a-locator-keeps-weight",
        _table([
            "| `O-2` | h is deliberately not implemented | S-1 (spec-document) | gap | "
            "**out-of-scope** · **weighted** | see `README.md` §2 (scope) |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    # 3d: the Markdown witness floors, brought up to the TOML ones.
    cases.append((
        "R3-3d-witness-of-single-tokens-is-not-a-witness",
        _table([
            "| `X-61` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): x -> y, "
            "observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "of one token",
    ))
    cases.append((
        "R3-3d-witness-with-no-date-is-refused",
        _table([
            "| `X-62` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> harness fails |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "states no date",
    ))
    # 3c: the §5 limit floor. A weighted row reading `(bounded)` said which of two words applied.
    cases.append((
        "R3-3c-bounds-token-with-no-limit-is-refused",
        _table([
            "| `X-63` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "nothing about WHAT THE CHECK RANGED OVER",
    ))
    cases.append((
        "R3-3c-positive-control-a-stated-limit-keeps-weight",
        _table([
            "| `X-64` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, ≤12 bytes) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    cases.append((
        "R3-3c-positive-control-an-unbounded-domain-keeps-weight",
        _table([
            "| `X-65` | some rule | S-1 (spec-document) | evidenced | "
            "**CONTRACT** (unbounded: symbolic Tag over all 4 classes) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))

    # 68-72. review round-4 plus the two breaks the review's generated cases surfaced. Each passed
    # WEIGHTED on the previous commit.
    #
    # His probe: a LIMIT with no boundedness token. `unwind` was one of the local BOUNDS_RE's
    # accepted alternatives, so naming a bound counted as saying which kind of bound it was.
    cases.append((
        "R4-1-a-limit-with-no-boundedness-token-is-refused",
        _table([
            "| `B-1` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "does not declare boundedness",
    ))
    # The single-token strength ladder §5 tells renderings not to use, which the local grammar
    # accepted as a boundedness declaration in its own right.
    cases.append((
        "R4-1-grade-token-alone-does-not-declare-boundedness",
        _table([
            "| `B-2` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "does not declare boundedness",
    ))
    # Positive control: the pair, stated. §5's actual requirement.
    cases.append((
        "R4-1-positive-control-the-pair-stated-keeps-weight",
        _table([
            "| `B-3` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** "
            "(unbounded: Lean lid over all lengths) · **weighted** | `K mod::proofs::foo`. "
            "watched-fail(K mod::proofs::foo): negate the postcondition -> harness fails, "
            "observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    # `clause_source = none` is reserved to mean unweightable and was never detected here: the
    # local pattern tested for ONE of the two reserved tokens.
    cases.append((
        "R4-2-clause-source-none-is-reserved-unweightable",
        _table([
            "| `C-1` | some rule | S-1 (none) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "reserved to mean unweightable",
    ))
    # ...and the UNDELIMITED form a real clause cell writes, which the delimiter requirement let
    # through even for the token it did test for.
    cases.append((
        "R4-2-undelimited-test-name-in-a-clause-cell-is-still-reserved",
        _table([
            "| `C-2` | some rule | S-1 (test-name) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "reserved to mean unweightable",
    ))

    # 73-78. review round-5, plus the tier-marker instance the class sweep turned up. Every one
    # passed clean and counted WEIGHTED on the previous commit.
    cases.append((
        "R5-1-boundedness-prefix-does-not-declare-boundedness",
        _table([
            "| `S-1` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (boundedness:unwind=8) "
            "· **weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "does not declare boundedness",
    ))
    cases.append((
        "R5-2-a-date-annotation-does-not-satisfy-the-phrase-floor",
        _table([
            "| `S-2` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> y, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "of one token",
    ))
    cases.append((
        "R5-3-reserved-clause-source-behind-a-separator-is-still-reserved",
        _table([
            "| `S-3` | some rule | S-1 (spec-document; none) | evidenced | **CONTRACT** (bounded, "
            "unwind=8) · **weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): "
            "negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "reserved to mean unweightable",
    ))
    cases.append((
        "R5-3b-two-clause-sources-in-one-cell-declare-nothing",
        _table([
            "| `S-4` | some rule | S-1 (spec-document; doc-comment) | evidenced | **CONTRACT** (bounded, "
            "unwind=8) · **weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): "
            "negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "declares more than one clause_source",
    ))
    cases.append((
        "R5-4-status-outside-the-closed-vocabulary-is-refused",
        _table([
            "| `S-5` | some rule | S-1 (spec-document) | nonsense | **CONTRACT** (bounded, "
            "unwind=8) · **weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): "
            "negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "is not one of the closed status vocabulary",
    ))
    # Class sweep: the same first-match-wins shape as the clause_source smuggle, in W4's marker.
    cases.append((
        "R5-7-a-row-stating-both-tier-markers-declares-neither",
        _table([
            "| `S-6` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** · **unweighted** | `K mod::proofs::foo`. watched-fail(K "
            "mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "states BOTH tier markers",
    ))

    # 79-84. review round-6 — the review's exact inputs, each passing WEIGHTED on the previous commit.
    cases.append((
        "R6-1-annotation-with-a-colon-separator-is-still-metadata",
        _table([
            "| `M-1` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> bug, observed: 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "of one token",
    ))
    cases.append((
        "R6-1-annotation-with-an-em-dash-separator-is-still-metadata",
        _table([
            "| `M-2` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> bug, observed \u2014 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "of one token",
    ))
    # The opposite error, and the more dangerous one: the strip must not discard a description
    # that happens to contain a date. This row is HONEST and must keep its weight.
    cases.append((
        "R6-1-a-date-in-the-middle-of-a-description-is-not-metadata",
        _table([
            "| `M-3` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): reverted the "
            "fix landed on 2026-08-20 -> failure on 2026-08-25 after harness mutation, observed "
            "2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    # W4: the contradiction scan on the DEDICATED weight column, which W4 recommends most.
    cases.append((
        "R6-2-dual-markers-in-a-dedicated-weight-cell-declare-nothing",
        _table([
            "| `M-4` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) | "
            "**weighted** · **unweighted** | `K mod::proofs::foo`. watched-fail(K "
            "mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | grade | weight | verify |"),
        True, False, "states BOTH tier markers",
    ))
    # §7.1: a status COLUMN with an empty cell is the same undecidable case as a bad token.
    cases.append((
        "R6-4-empty-status-cell-on-a-weighted-row-is-refused",
        _table([
            "| `M-5` | some rule | S-1 (spec-document) |  | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "the cell is EMPTY",
    ))

    # 85-93. review round-7 — the review's exact inputs. THE CLASS: a structured obligation on a weighted row
    # may be satisfied only by DECLARATIVE syntax (word-bounded keyword + separator + value),
    # never by scanning free prose. Every case below passed on the previous commit.
    cases.append((
        "R7-1-unbolded-and-bolded-tier-markers-contradict",
        _table([
            "| `T-1` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) | "
            "unweighted · **weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | grade | weight | verify |"),
        True, False, "states BOTH tier markers",
    ))
    cases.append((
        "R7-1-two-unbolded-tier-markers-contradict",
        _table([
            "| `T-2` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) | "
            "unweighted weighted | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | grade | weight | verify |"),
        True, False, "states BOTH tier markers",
    ))
    cases.append((
        "R7-2-blocked-by-inside-an-identifier-does-not-name-what-blocks",
        _table([
            "| `T-3` | some rule about unblocked_byproduct | S-1 (spec-document) | BLOCKED | "
            "**not-covered** · **weighted** | `A grep -n 'foo' src/bar.rs` -> empty. "
            "positive-control(A grep -n 'foo' src/bar.rs): src/baz.rs -> 3 matching lines, "
            "observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "does not name what blocks it",
    ))
    cases.append((
        "R7-3-reviewed-over-lunch-does-not-name-a-sub-list",
        _table([
            "| `T-4` | `predicate`: reviewed over lunch, 4 of 33 | S-1 (spec-document) | evidenced | "
            "**CONTRACT** (bounded, unwind=8) · **weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "does not name the sub-list",
    ))
    cases.append((
        "R7-3-positive-control-a-declared-over-names-the-sub-list",
        _table([
            "| `T-5` | `predicate`, over: the 33 production harnesses, 4 of 33 | "
            "S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · **weighted** | "
            "`K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    # HIS FALSE POSITIVE: an identifier that merely contains the letters must NOT declare a
    # predicate item. This row is honest and must come through clean.
    cases.append((
        "R7-4-item_kindpredicate-is-an-identifier-not-a-declaration",
        _table([
            "| `T-6` | some rule about item_kindpredicate | S-1 (spec-document) | evidenced | "
            "**CONTRACT** (bounded, unwind=8) · **weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    # HIS LETTER-EATING FIXTURE: `on` inside `mutation` was stripping the word to `mutati`.
    cases.append((
        "R7-5-the-annotation-keyword-does-not-match-inside-a-word",
        _table([
            "| `T-7` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): reverted the "
            "latch -> failure after harness mutation, observed 2026-08-25 . |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    # (6) the witness separator is the shared declarative class: every punctuation variant parses.
    for _i, _sep in enumerate((":", " - ", " = ", ", ", "; ")):
        cases.append((
            f"R7-6-witness-separator-variant-{_i}",
            _table([
                f"| `T-8{_i}` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** "
                f"(bounded, unwind=8) · **weighted** | `K mod::proofs::foo`. "
                f"watched-fail(K mod::proofs::foo){_sep}negate the postcondition -> harness "
                f"fails, observed 2026-08-25 |",
            ], header="| id | rule | clause | status | strength | verify |"),
            False, False, None,
        ))

    # 94-100. review round-8 — the review's exact inputs. Every one passed on the previous commit.
    cases.append((
        "R8-1-prose-denying-a-control-does-not-declare-one",
        _table([
            "| `P-1` | some absence claim | S-1 (spec-document) | gap | **not-covered** · "
            "**weighted** | `A grep -n 'foo' src/bar.rs` -> empty. no control exists for it |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "declares no positive control",
    ))
    cases.append((
        "R8-1-the-word-uncontrolled-does-not-declare-a-control",
        _table([
            "| `P-2` | some absence claim | S-1 (spec-document) | gap | **not-covered** · "
            "**weighted** | `A grep -n 'foo' src/bar.rs` -> empty, uncontrolled |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "declares no positive control",
    ))
    cases.append((
        "R8-1-positive-control-declared-keeps-weight",
        _table([
            "| `P-3` | some absence claim | S-1 (spec-document) | gap | **not-covered** · "
            "**weighted** | `A grep -n 'foo' src/bar.rs` -> empty. positive-control(A grep -n "
            "'foo' src/bar.rs): the same pattern against src/baz.rs -> 3 matching lines, "
            "observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    cases.append((
        "R8-2-an-empty-quoted-value-does-not-declare-a-sub-list",
        _table([
            '| `P-4` | `predicate`, over: ", 4 of 33 | S-1 (spec-document) | evidenced | '
            "**CONTRACT** (bounded, unwind=8) · **weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "does not name the sub-list",
    ))
    cases.append((
        "R8-3-a-fused-weight-pending-keyword-is-not-a-declared-count",
        _table([
            "| `P-5` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |")
        + "\n\nTier counts: 1 weighted, 0 unweighted, weight-pending7\n",
        False, False, None,
    ))
    # HIS FALSE REFUSAL: an identifier containing `_predicate_` must not declare a predicate item.
    cases.append((
        "R8-4-foo_predicate_bar-is-an-identifier-not-a-declaration",
        _table([
            "| `P-6` | some rule about foo_predicate_bar | S-1 (spec-document) | evidenced | "
            "**CONTRACT** (bounded, unwind=8) · **weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    # (2) parens and brackets are grouping, not declaration separators (§4.1's stated five).
    cases.append((
        "R8-2-a-paren-is-not-a-witness-separator",
        _table([
            "| `P-7` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo)(negate the "
            "postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "no watched-fail witness",
    ))

    # 101-107. review round-9 — the review's exact rows. Each is a refusal that was landing in a tier total.
    cases.append((
        "R9-1a-a-plain-declared-positive-control-is-witness-3",
        _table([
            "| `Q-1` | some absence claim | S-1 (spec-document) | gap | **not-covered** · "
            "**weighted** | `A grep -n 'foo' src/bar.rs` -> empty. positive-control: known "
            "fixture matches |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    cases.append((
        "R9-1b-a-single-token-positive-control-names-nothing",
        _table([
            "| `Q-2` | some absence claim | S-1 (spec-document) | gap | **not-covered** · "
            "**weighted** | `A grep -n 'foo' src/bar.rs` -> empty. positive-control: x |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "names nothing",
    ))
    cases.append((
        "R9-2a-weighted-on-an-unweightable-grade-is-refused-not-unweighted",
        _table([
            "| `Q-3` | a human argument | S-1 (spec-document) | evidenced | **inspection-argued** · "
            "**weighted** | see notes |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "no deciding machinery",
    ))
    cases.append((
        "R9-2b-contradictory-markers-are-refused-not-unweighted",
        _table([
            "| `Q-4` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
            "**weighted** · **unweighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "states BOTH tier markers",
    ))
    cases.append((
        "R9-2c-missing-bounds-and-witness-together-are-refused",
        _table([
            "| `Q-5` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** · **weighted** | "
            "`K mod::proofs::foo` |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "does not declare boundedness",
    ))

    # 108-113. review round-10 — the review's exact inputs, plus one fixture per ACCEPTED tier syntax so the
    # weight invariant is proved over all three rather than over bolded markers alone.
    cases.append((
        "R10-1-a-dangling-structured-control-opener-is-not-a-control",
        _table([
            "| `Z-1` | some absence claim | S-1 (spec-document) | gap | **not-covered** · "
            "**weighted** | `A grep -n 'foo' src/bar.rs` -> empty. positive-control( |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "does not parse",
    ))
    cases.append((
        "R10-1-a-valid-control-does-not-excuse-a-dangling-opener",
        _table([
            "| `Z-2` | some absence claim | S-1 (spec-document) | gap | **not-covered** · "
            "**weighted** | `A grep -n 'foo' src/bar.rs` -> empty. positive-control(A grep -n "
            "'foo' src/bar.rs): the same pattern against src/baz.rs -> 3 matching lines, "
            "observed 2026-08-25. positive-control( |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "does not parse",
    ))
    cases.append((
        "R10-1-an-incomplete-structured-control-is-refused",
        _table([
            "| `Z-3` | some absence claim | S-1 (spec-document) | gap | **not-covered** · "
            "**weighted** | `A grep -n 'foo' src/bar.rs` -> empty. positive-control(A grep -n "
            "'foo' src/bar.rs): x -> y |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "structured positive control is incomplete",
    ))
    # Weight claimed via the `[W]` marker, refused: the invariant must see the claim.
    cases.append((
        "R10-3-weight-claimed-via-a-bracket-marker-is-refused-into-neither-tier",
        _table([
            "| `Z-4` | [W] a human argument | S-1 (spec-document) | evidenced | **inspection-argued** | "
            "see notes |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "no deciding machinery",
    ))
    # ...and via an UNBOLDED dedicated weight column.
    cases.append((
        "R10-3-weight-claimed-via-an-unbolded-weight-column-is-refused-into-neither-tier",
        _table([
            "| `Z-5` | a human argument | S-1 (spec-document) | evidenced | **inspection-argued** | "
            "weighted | see notes |",
        ], header="| id | rule | clause | status | grade | weight | verify |"),
        True, False, "no deciding machinery",
    ))

    # 114. Round-10 SWEEP finding (mine, not reported): normalize_status was first-match-wins over
    # an ordered alias list, so a cell naming two statuses resolved to whichever alias sat first.
    cases.append((
        "R10-sweep-a-status-cell-naming-two-statuses-has-named-none",
        _table([
            "| `Z-6` | some rule | S-1 (spec-document) | evidenced, but really a gap | "
            "**CONTRACT** (bounded, unwind=8) · **weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the postcondition -> harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "names more than one status",
    ))

    # 20. grade-strength derivation (the run_file summary's second line):
    # a deciding grade, an asserted grade, and an unresolvable one
    # must classify as deciding / asserted / None respectively.
    tier_md = _table([
        "| `X-20` | rule | evidenced | **CONTRACT** (bounded) | `K mod::proofs::foo` |",
        "| `X-21` | rule | evidenced | **PROBE** (bounded) | `K mod::proofs::bar` |",
        "| `X-22` | rule | evidenced | derived | `K mod::proofs::baz` |",
    ])
    tier_want = ["weighted", "admitted", None]

    # 115-118. §4.2's literal-command form, found refusing honest rows by the der mutation pass in
    # real use (114 Kani invocations). Both of the first two were REFUSED on the previous commit:
    # `./check.sh` was not on the hardcoded program whitelist at all, and no witness could bind to
    # a literal command because `recipe_tokens` never returned one.
    cases.append((
        "R13-a-backticked-literal-command-is-a-recipe",
        _table([
            "| `L-1` | some rule | S-1 (spec-document) | evidenced | **mechanical** · **weighted** | "
            "`./check.sh`. watched-fail(./check.sh): reverted the latch -> the gate fails, "
            "observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    cases.append((
        "R13-a-witness-binds-to-a-literal-command",
        _table([
            "| `L-2` | some rule | S-1 (spec-document) | evidenced | **mechanical** · **weighted** | "
            "`cargo fmt --check`. watched-fail(cargo fmt --check): reformatted one file -> the "
            "gate fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))
    # ...and the binding is still a binding: a witness naming a DIFFERENT literal does not bind.
    cases.append((
        "R13-a-witness-naming-a-different-literal-command-does-not-bind",
        _table([
            "| `L-3` | some rule | S-1 (spec-document) | evidenced | **mechanical** · **weighted** | "
            "`./check.sh`. watched-fail(./other.sh): reverted the latch -> the gate fails, "
            "observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, True, "does not name any recipe of THIS row",
    ))
    # A bare single word is not a command invocation -- which also retires the "backticked
    # `cargo` alone is a recipe" limit this checker carried since round 7.
    cases.append((
        "R13-a-bare-single-word-is-not-a-literal-command",
        _table([
            "| `L-4` | some rule | S-1 (spec-document) | evidenced | **mechanical** · **weighted** | "
            "`true`. watched-fail(true): reverted the latch -> the gate fails, observed "
            "2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "no recognisable recipe reference",
    ))

    # N5 (cold reader, 2026-08-26) — his exact TOY-9 row. Silently skipped on the previous
    # commit: W5's UNCHECKED promise held only for BACKTICKED unparseable ids.
    cases.append((
        "N5-an-unbackticked-id-shaped-row-is-reported-unchecked",
        _table([
            "| TOY-9 | some rule | evidenced | **CONTRACT** (bounded, unwind=8) | `K mod::proofs::foo` |",
        ]),
        False, True, "NOT backticked",
    ))
    # ...and an ordinary prose first cell is still not dragged in.
    cases.append((
        "N5-a-prose-first-cell-is-not-an-unchecked-row",
        _table([
            "| Total | some rule | evidenced | **CONTRACT** (bounded, unwind=8) | `K mod::proofs::foo` |",
        ]),
        False, False, None,
    ))

    # core.md §4.2: recipe letters are validated against THIS document's OWN declared recipe
    # table (declared_recipe_letters), not the global RECIPE_LETTERS fallback. A document that
    # declares only `K` must refuse a row using `N` -- even though `N` is IN the global fallback
    # set -- exactly as a document that declares nothing falls back to the global set and accepts
    # `N` there.
    _recipe_table_declaring_only_k = "\n".join([
        "| id | recipe | what green means |",
        "|---|---|---|",
        "| **K** `<H>` | `cargo kani --harness <H>` | VERIFICATION:- SUCCESSFUL |",
    ])
    cases.append((
        "recipe-letters-scoped-to-the-documents-own-table--undeclared-letter-refused",
        _recipe_table_declaring_only_k + "\n\n" + _table([
            "| `X-50` | some rule | S-1 (spec-document) | evidenced | **mechanical** · "
            "**weighted** | `N some_theorem`. watched-fail(N some_theorem): flip it -> "
            "fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        True, False, "no recognisable recipe reference",
    ))
    cases.append((
        "recipe-letters-scoped-to-the-documents-own-table--declared-letter-accepted",
        _recipe_table_declaring_only_k + "\n\n" + _table([
            "| `X-51` | some rule | S-1 (spec-document) | evidenced | **mechanical** · "
            "**weighted** | `K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the "
            "postcondition -> the harness fails, observed 2026-08-25 |",
        ], header="| id | rule | clause | status | strength | verify |"),
        False, False, None,
    ))

    failures = []

    # STRUCTURAL INVARIANT (review, round 8): no result may be weighted AND carry a refusal error.
    # W5's totals are computed from `weighted`, so a row that is both is a row reported refused
    # and counted weighted in the same run. Asserted over every fixture in this file, not just a
    # chosen one, because the defect was in a state transition rather than in any single rule.
    # THE REAL INVARIANT (§8.1, completed round 9): a row that EXPLICITLY claimed weight and drew
    # a refusal error must be `refused` -- excluded from BOTH tier totals. Asserting only "not
    # weighted" was too weak: it passed while such rows were silently counted UNWEIGHTED, which
    # reports a refused row as one that never asked for anything.
    _inv_bad = []
    for _name, _md, _e, _w, _sub in cases:
        for _r in check_file_text(_md):
            # The PRODUCTION answer, recorded by `process_row` itself. Re-deriving it here from
            # bold spans put the `[W]` and unbolded-weight-column syntaxes outside the proof --
            # the proof was checking a different question from the one the rules answer (review,
            # round 10).
            _claimed = _r.claimed_weight
            if _r.weighted and _r.errors:
                _inv_bad.append(f"{_name}/{_r.row_id}: weighted AND refused")
            if _claimed and _r.errors and not _r.refused:
                _inv_bad.append(f"{_name}/{_r.row_id}: claimed weight, refused, but not excluded "
                                f"from the tier totals (weighted={_r.weighted})")
            if _r.refused and (_r.weighted or _r.pending):
                _inv_bad.append(f"{_name}/{_r.row_id}: refused AND in another tier")
    if _inv_bad:
        failures.append(f"weight-invariant: {_inv_bad}")
        print("SELFTEST FAIL: weight-invariant-refused-rows-are-in-neither-tier")
        for _b in _inv_bad[:5]:
            print(f"   {_b}")
    else:
        print(f"SELFTEST PASS: weight-invariant-refused-rows-are-in-neither-tier "
              f"({len(cases)} fixtures scanned)")

    # Finding 9 (W5): the DECLARED weight-pending count is compared, in both directions.
    _w5_md = _table([
        "| `X-60` | some rule | S-1 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · "
        "**weighted** | `K mod::proofs::foo` |",
    ], header="| id | rule | clause | status | strength | verify |") + \
        "\n\nTier counts: 0 weighted, 0 unweighted, weight-pending: 999\n"
    import io as _io
    import contextlib as _ctx
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "w5.md"
        _p.write_text(_w5_md, encoding="utf-8")
        _buf = _io.StringIO()
        with _ctx.redirect_stdout(_buf):
            _ne, _ = run_file(str(_p))
        if _ne < 1 or "declared weight-pending 999" not in _buf.getvalue():
            failures.append("W5-declared-pending-count-is-checked: not reported")
            print("SELFTEST FAIL: W5-declared-pending-count-is-checked")
        else:
            print("SELFTEST PASS: W5-declared-pending-count-is-checked")
        # Positive control: the same file with the RIGHT pending count is clean.
        _p2 = Path(_td) / "w5ok.md"
        _p2.write_text(_w5_md.replace("weight-pending: 999", "weight-pending: 1"),
                       encoding="utf-8")
        _buf2 = _io.StringIO()
        with _ctx.redirect_stdout(_buf2):
            _ne2, _ = run_file(str(_p2))
        if _ne2 != 0:
            failures.append(f"W5-correct-pending-count-is-clean: got {_ne2} errors")
            print("SELFTEST FAIL: W5-correct-pending-count-is-clean")
        else:
            print("SELFTEST PASS: W5-correct-pending-count-is-clean")
        # And a rendering that states tier counts while rows are pending must state the third.
        _p3 = Path(_td) / "w5none.md"
        _p3.write_text(_w5_md.replace(", weight-pending: 999", ""), encoding="utf-8")
        _buf3 = _io.StringIO()
        with _ctx.redirect_stdout(_buf3):
            _ne3, _ = run_file(str(_p3))
        if _ne3 < 1 or "states no weight-pending count" not in _buf3.getvalue():
            failures.append("W5-missing-pending-count-is-reported: not reported")
            print("SELFTEST FAIL: W5-missing-pending-count-is-reported")
        else:
            print("SELFTEST PASS: W5-missing-pending-count-is-reported")

    # Structural: the grade-strength split is DERIVED from the grade, not typed. A deciding
    # grade, an asserted-grade token and an unresolvable one must classify as deciding /
    # asserted / None respectively — counted separately from `cases` because it asserts a derivation rather
    # than matching a reported message.
    _tier_md = _table([
        "| `X-20` | rule | evidenced | **CONTRACT** (bounded) | `K mod::proofs::foo` |",
        "| `X-21` | rule | evidenced | **PROBE** (bounded) | `K mod::proofs::bar` |",
        "| `X-22` | rule | evidenced | derived | `K mod::proofs::baz` |",
    ])
    _tier_want = ["deciding", "asserted", None]
    _tier_got = [grade_strength(r.grade) for r in check_file_text(_tier_md)]
    if _tier_got == _tier_want:
        print("SELFTEST PASS: grade-strength-derivation")
    else:
        failures.append(f"grade-strength-derivation: expected {_tier_want}, got {_tier_got}")
        print(f"SELFTEST FAIL: {failures[-1]}")

    # Structural: an unmarked weight-eligible row must NOT be counted weighted (W1).
    _silent = check_file_text(_table([
        "| `X-37` | some rule | evidenced | **CONTRACT** (bounded, unwind=8) | `K mod::proofs::a`. "
        "watched-fail(K mod::proofs::a): negate the check -> harness fails, observed 2026-08-25 |",
    ]))[0]
    if _silent.weighted or _silent.declared_tier is not None:
        failures.append(f"S3-silence-is-unweighted: got weighted={_silent.weighted}")
        print("SELFTEST FAIL: S3-silence-is-unweighted")
    else:
        print("SELFTEST PASS: S3-silence-is-unweighted")


    # Structural assertions the message-matching harness cannot make: a refused row must LOSE
    # its weight, not merely be complained about, and a satisfied row must keep it (§8.1).
    _pending_md = _table([
        "| `X-33` | some rule | evidenced | **CONTRACT** (bounded, unwind=8) · **weighted** | `K mod::proofs::foo` |",
    ])
    _r = check_file_text(_pending_md)[0]
    if _r.weighted or not _r.pending:
        failures.append(
            f"weight-pending-row-is-not-weighted: expected weighted=False pending=True, "
            f"got weighted={_r.weighted} pending={_r.pending}"
        )
        print("SELFTEST FAIL: weight-pending-row-is-not-weighted")
    else:
        print("SELFTEST PASS: weight-pending-row-is-not-weighted")
    _ok_md = _table([
        "| `X-34` | some rule | S-3.2 (spec-document) | evidenced | **CONTRACT** (bounded, unwind=8) · **weighted** | "
        "`K mod::proofs::foo`. watched-fail(K mod::proofs::foo): negate the postcondition -> "
        "harness fails, observed 2026-08-25 |",
    ], header="| id | rule | clause | status | strength | verify |")
    _r2 = check_file_text(_ok_md)[0]
    if not _r2.weighted or _r2.pending:
        failures.append(
            f"compliant-row-keeps-weight: expected weighted=True pending=False, "
            f"got weighted={_r2.weighted} pending={_r2.pending}"
        )
        print("SELFTEST FAIL: compliant-row-keeps-weight")
    else:
        print("SELFTEST PASS: compliant-row-keeps-weight")

    for name, md, expect_errors, expect_warnings, expect_substr in cases:
        failure = _run_case(name, md, expect_errors, expect_warnings, expect_substr)
        if failure:
            failures.append(failure)
            print(f"SELFTEST FAIL: {failure}")
        else:
            print(f"SELFTEST PASS: {name}")

    print(f"selftest: {len(cases)} cases, {len(failures)} failed")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 1
    if argv[0] == "--selftest":
        return selftest()

    # --strict-weight: core.md §8.1's ratchet. Transitional weight refusals become errors.
    strict_weight = "--strict-weight" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        print("usage error: no FILE arguments given", file=sys.stderr)
        return 2

    total_errors = 0
    for path in paths:
        n_errors, _n_warnings = run_file(path, strict_weight=strict_weight)
        total_errors += n_errors
    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
