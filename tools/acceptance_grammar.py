#!/usr/bin/env python3
"""acceptance_grammar.py — the rules that must mean the SAME THING in both representations.

Pure python3 stdlib, no dependencies, no I/O. Imported by `check_acceptance.py` (manifests),
`check_ledger.py` (rendered ledgers), and `check_parity_selftest.py` (the harness that proves
they agree).

WHY THIS FILE EXISTS
--------------------
`core.md` says its rules are enforced "in both representations". For most of 2026-08-25 that
sentence was maintained by hand: the same rule was written twice, once per checker, and the two
copies were kept in step by whoever remembered. They did not stay in step. The live instance, found
by an external review the same evening:

    | `O-1` | h is deliberately not implemented | S-1 (spec-document) | gap |
      **out-of-scope** · **weighted** | nonsense |

The TOML twin of that claim was REFUSED (`scope_ref` must be a locator). The Markdown row was
granted WEIGHT, because the row checker's `out-of-scope` rule had never advanced past "the verify
cell is nonempty". One rule, two implementations, one of them a year behind the other — and the
weaker one was the representation a human actually reads.

So the cross-representation rules live here, once. A rule in this file cannot drift between
checkers, because there is only one of it. Rules that are genuinely specific to one representation
(Markdown's tier markers and recipe-reference grammar; TOML's table shapes and evidence registry)
stay in their own checker, where they belong.

**This file is not a style preference and must not be inlined back.** The duplication it replaces
is the mechanism by which "enforced in both representations" became false while every gate stayed
green.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# The closed grade vocabulary (core.md §1). Nine tokens, closed by the B1b ruling.
# ---------------------------------------------------------------------------

GRADES = {
    "contract",
    "probe",
    "test-only",
    "mechanical",
    "not-covered",
    "out-of-scope",
    "inspection-argued",
    "unspecified",
    "ungraded",
}

# Grades with no deciding machinery — never weight-eligible (§1).
UNWEIGHTABLE_GRADES = {"inspection-argued", "unspecified", "ungraded"}

# Grades that assert a check was, or was not, performed — every one requires a deciding recipe
# (§3 rule 1) and a watched-fail witness to carry weight (§4.1 / W2.5).
GRADES_REQUIRING_RECIPE = {"contract", "probe", "test-only", "mechanical", "not-covered"}

# Grades that assert a check SUCCEEDED. The subset §7.1's one-sentence rule is stated in.
GRADES_ASSERTING_A_CHECK = {"contract", "probe", "test-only", "mechanical"}

# Grades that must declare boundedness (§5).
GRADES_REQUIRING_BOUNDS = {"contract", "probe"}

# W2.3 / coverage-ledger.md §6: where the claim's clause text came from. The last two are
# RESERVED to mean unweightable by design.
CLAUSE_SOURCES = {"spec-document", "external-standard", "doc-comment", "test-name", "none"}

# The two RESERVED to mean unweightable by design: the clause was read off its own evidence, or
# off nothing. Neither can be falsified, so neither can carry weight (W2.3).
#
# Defined here as a SET rather than tested for by hand in each checker. When it was tested for by
# hand, the two checkers disagreed on both members at once: `check_ledger.py` had a bespoke
# regex for `test-name` that required the token to be backtick/asterisk/underscore delimited (so
# `S-1 (test-name)` slipped through) and no test for `none` at all, while `check_acceptance.py`
# refused both unconditionally. Found by the generated clause_source parity cases, 2026-08-25.
CLAUSE_SOURCES_UNWEIGHTABLE = {"test-name", "none"}

# ---------------------------------------------------------------------------
# status × grade coherence (core.md §7.1)
# ---------------------------------------------------------------------------

# The closed status vocabulary (core.md §7.1/§7.3). Shared because a status the Markdown side
# could not recognise was silently skipping the coherence check there while the manifest validator
# refused it outright — `status = nonsense` passed WEIGHTED in a rendering (review, round 5).
STATUSES = {"evidenced", "partial", "gap", "parked", "blocked"}

# Statuses that assert NO check succeeded: no evidence records, and no grade that says one did.
STATUSES_NO_CHECK = {"gap", "parked", "blocked"}

STATUS_COHERENT_GRADES = {
    "evidenced": {"contract", "probe", "test-only", "mechanical", "inspection-argued", "ungraded"},
    "partial": {"contract", "probe", "test-only", "mechanical", "inspection-argued", "ungraded"},
    # `out-of-scope` declares the item NOT CLAIMED, which is not a check result. It was absent
    # from the §7.1 table as first written — an omission, not a decision.
    "gap": {"not-covered", "out-of-scope", "unspecified", "ungraded"},
    "parked": {"not-covered", "out-of-scope", "unspecified", "ungraded"},
    "blocked": {"not-covered", "out-of-scope", "unspecified", "ungraded"},
}


def status_grade_incoherence(status: str | None, grade: str | None) -> str | None:
    """core.md §7.1. Returns an incoherence message, or None. The two pairs the spec's
    one-sentence summary names are reported with their own sharper wording; every other pair the
    table forbids falls through to the general message."""
    if status is None or grade is None:
        return None
    coherent = STATUS_COHERENT_GRADES.get(status)
    if coherent is None or grade in coherent:
        return None
    if status in STATUSES_NO_CHECK and grade in GRADES_ASSERTING_A_CHECK:
        return (
            f"status {status!r} says no check succeeded, but grade {grade!r} asserts one did — "
            f"a claim cannot be a gap and a proof at the same time (spec §7.1)"
        )
    if status == "evidenced" and grade == "not-covered":
        return (
            "status 'evidenced' says admissible evidence exists, but grade 'not-covered' says "
            "nothing checks the item (spec §7.1)"
        )
    return (
        f"status {status!r} does not cohere with grade {grade!r} — the §7.1 table allows "
        f"{sorted(coherent)} at this status"
    )


# ---------------------------------------------------------------------------
# `scope_ref` — the locator grammar (core.md §1/§7.1)
# ---------------------------------------------------------------------------

# `out-of-scope` is the one grade whose weight attaches to a DECLARATION rather than to any
# property of the code — "the producer declared this, HERE" — so the *here* must be somewhere a
# reader can go. Free prose records nothing and cannot be told from an undeclared scope.
SCOPE_REF_LOCATOR_RE = re.compile(
    r"§\s*[0-9]"                                        # §4, §7.1
    r"|#[A-Za-z0-9][A-Za-z0-9._-]*"                     # README.md#scope
    r"|\[spec\]\.axis"                                  # the declared axis itself
    r"|\b[\w./-]+\.(?:md|rs|toml|txt|adoc|html|tex)\b"  # a document path
    r"|\bsection\s+[0-9]"
)
# NOT case-insensitive (2026-08-28, common-subset ruling): `re.IGNORECASE` here compiled to the
# schema as an inline `(?i)` group, which is Python-only syntax — invalid in the ECMA-262 dialect
# every JS-based JSON Schema validator (and VS Code) requires. Dropped, not replaced with an
# explicit case class, because the corpus and every fixture that reaches this pattern are
# uniformly lowercase: `[spec].axis` is always written lowercase (grep across spec/, docs/,
# maintainers/), every shipped document-path extension is lowercase, and no fixture or shipped
# manifest uses the literal word "section" at all (the `§` form is what the corpus actually uses).
# See tools/emit_schema.py's SCOPE_REF_PATTERN, which no longer needs to re-apply `(?i)` either.

SCOPE_REF_EXPECTATION = (
    "a section marker (§4), an anchor (README.md#scope), a document path, or [spec].axis"
)


def is_scope_locator(value: str | None) -> bool:
    """Shape only, deliberately. That the cited section actually says the item is out of scope
    is not checkable and is reviewer work — see §7.1."""
    return bool(value) and bool(SCOPE_REF_LOCATOR_RE.search(value))


# ---------------------------------------------------------------------------
# Witness floors (core.md §4.1)
# ---------------------------------------------------------------------------

# ONE date pattern; both forms are built from it. Written twice, the two could disagree about
# what a date is — the same duplication that produced every parity break this file exists to stop.
_ISO_DATE_CORE = r"\d{4}-\d{2}-\d{2}"
# A whole field (TOML `watched_fail.date`).
ISO_DATE_RE = re.compile(r"^" + _ISO_DATE_CORE + r"$")
# The same date appearing anywhere inside a Markdown witness body, where the witness is one prose
# cell rather than four named fields.
ISO_DATE_INLINE_RE = re.compile(r"(?<!\d)" + _ISO_DATE_CORE + r"(?!\d)")

# ---------------------------------------------------------------------------
# Separators. ONE definition, because every hand-written separator class in this codebase has
# turned out to be missing a variant somebody writes: `observed: <date>` and `observed — <date>`
# both defeated the metadata strip below when it accepted only a bare space (review, round 6).
# Covers comma, semicolon, colon, equals, parens, brackets, ASCII hyphen, the Unicode dash
# block (U+2010..U+2015), the minus sign, and whitespace.
# ---------------------------------------------------------------------------

SEPARATOR_CHARS = r",;:=()\[\]\-\u2010-\u2015\u2212\s"
# The same separators as a LITERAL set for str.strip(). It must be built independently: passing
# the regex class to strip() puts `\`, `s`, `u` and digits into the set, which silently ate the
# final letter of every word it touched (`harness fails` -> `harness fail`). Caught by the
# round-6 fixtures on the very next run.
SEPARATOR_STRIP_CHARS = ",;:=()[]-\u2010\u2011\u2012\u2013\u2014\u2015\u2212 \t\n.\u00b7"
SEPARATOR_RE = re.compile("[" + SEPARATOR_CHARS + "]")
# A separator run between a keyword and its value: `foo: bar`, `foo — bar`, `foo (bar`, `foo bar`.
SEP_RUN = "[" + SEPARATOR_CHARS + "]*"
# One or more. A DECLARATION requires a real separator: with `*`, `blocked_by` ran straight into
# `product` and `unblocked_byproduct` satisfied §7.3 (review, round 7).
SEP_REQUIRED = "[" + SEPARATOR_CHARS + "]+"

# The separator characters that are NOT whitespace. A declaration needs one of these, because
# whitespace alone is what running prose puts between any two words: `over lunch` is a sentence
# and `over: <list>` is a declaration, and only punctuation tells them apart. This is the
# difference between §7.2 being a rule and being a word search — `reviewed over lunch` named the
# sub-list a predicate ranges over until it existed (review, round 7).
SEPARATOR_PUNCT_CHARS = r",;:=()\[\]\-\u2010-\u2015\u2212"

# The separators a DECLARATION may use, and exactly the five §4.1 names: colon, dash, equals,
# comma, semicolon. Parens and brackets are GROUPING, not separators -- `watched-fail(K x)(body`
# and `over: [` parsed as declarations while §4.1 listed neither (review, round 8). Keeping the
# implemented set wider than the documented set is the spec overclaiming by omission.
DECLARATION_SEPARATOR_CHARS = r":=,;\-\u2010-\u2015\u2212"
SEP_DECLARATIVE = (r"\s*[" + DECLARATION_SEPARATOR_CHARS + r"]\s*")

# What a declared VALUE has to be: optional opening markup or quoting, then at least one
# alphanumeric. `over: "` and `blocked-by: "` satisfied a value pattern of one character that
# accepted the quote itself, so an empty quoted string declared a sub-list (review, round 8).
DECLARED_VALUE = r"[`'\"*_\s]*[A-Za-z0-9]"

# Not-a-word-character, on either side of a keyword. `\b` is wrong here because the keywords
# contain hyphens and underscores: `\bblocked-by\b` still matches inside `unblocked-byproduct`
# at the hyphen. These assert "no identifier character adjacent", which is what a declaration
# means.
NOT_WORD_BEFORE = r"(?<![A-Za-z0-9_])"
NOT_WORD_AFTER = r"(?![A-Za-z0-9_])"


def declaration_re(keyword: str, value: str = DECLARED_VALUE,
                   separator: str = SEP_DECLARATIVE) -> re.Pattern:
    """Build a matcher for a DECLARATIVE field in a rendered ledger.

    THE RULE THIS ENCODES (core.md §7.2, generalised to every structured field 2026-08-25,
    seventh round): **a structured obligation on a weighted row may be satisfied only by
    declarative syntax — a word-bounded keyword, a required separator, and a value — never by
    scanning free prose.**

    The instances that forced it were all the same shape: `over` matched *"reviewed over lunch"*,
    so a lunch named a sub-list; `blocked-by` matched inside `unblocked_byproduct`; the predicate
    declaration matched `item_kindpredicate` with no separator at all. A rendering is prose, and
    prose is evidence of nothing (§4.1) — the Markdown parser had been reading obligations out of
    it anyway.

    Diagnostic-only patterns are exempt and stay loose ON PURPOSE: their job is to notice that a
    producer *meant* something and say so, and a missed variant there costs a hint, not a verdict.
    Only weight-bearing reads must be declarative."""
    return re.compile(NOT_WORD_BEFORE + keyword + NOT_WORD_AFTER + separator + value,
                      re.IGNORECASE)

# The words a producer puts in front of a witness date.
# WORD-BOUNDED. Without the boundaries the short keywords matched inside ordinary words -- `on`
# inside `mutation` -- so `harness mutation, observed 2026-08-25` was stripped to `harness mutati`
# and an honest witness could be cut below the phrase floor by its own vocabulary (review, round 7).
_ANNOTATION_KEYWORD = (
    NOT_WORD_BEFORE
    + r"(?:re-?)?(?:observed|seen|watched|checked|verified|confirmed|noted|dated|recorded|on|at)"
    + NOT_WORD_AFTER
)

# Trailing WITNESS METADATA: the date annotation and the words that introduce it. Stripped before
# the phrase floor is applied, because the annotation's own tokens satisfied the floor: Markdown
# `... -> y, observed 2026-08-25` passed while the TOML twin `observed = "y"` was refused. The
# floor is meant to measure the DESCRIPTION, not the bookkeeping attached to it.
#
# ANCHORED AT THE END, and that anchor is the fix for the opposite error (review, round 6): an
# unanchored version discarded everything after the first date, so
# `failure on 2026-08-25 after harness mutation` -- a real description with a date in the middle
# -- was cut to `failure` and refused as a single token. Wrong direction, and the more dangerous
# one, because it refuses honest witnesses. Only a date at the END is bookkeeping; a date in the
# middle is part of what the producer is describing, and stays measured.
WITNESS_METADATA_TAIL_RE = re.compile(
    r"(?:" + SEP_RUN + r"(?:and\s+)?" + _ANNOTATION_KEYWORD + r")*"
    + SEP_RUN + _ISO_DATE_CORE + r"[" + SEPARATOR_CHARS + r".]*$",
    re.IGNORECASE,
)


# A "word token": an identifier, a path, a harness name, a plain English word.
PHRASE_WORD_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_'/.-]+")


def is_iso_date(value: str | None) -> bool:
    return bool(value) and bool(ISO_DATE_RE.match(value.strip()))


def is_phrase(value: str | None) -> bool:
    """core.md §4.1: a witness field must be a STATEMENT — at least two word tokens of two or
    more characters. `"x"` is not a description of what was perturbed, and neither is `"bug"`.

    A SHAPE FLOOR AND NOTHING MORE. It cannot tell a true account of a watched failure from a
    plausible invented one, and §4.1 says so out loud. Raising the cost of the lie is the whole
    of what it does."""
    return bool(value) and len(PHRASE_WORD_RE.findall(value)) >= 2


def strip_witness_metadata(text: str | None) -> str:
    """Remove a TRAILING date annotation from a witness clause, leaving the description."""
    if not text:
        return ""
    return WITNESS_METADATA_TAIL_RE.sub("", text).strip(SEPARATOR_STRIP_CHARS)


# ---------------------------------------------------------------------------
# `bounds` (core.md §5)
# ---------------------------------------------------------------------------

# Longest first, so the alternation cannot match `bounded` inside `unbounded` and read every
# unbounded declaration as a bounded one — the underclaiming direction §5 warns about.
BOUNDS_TOKENS = ("unbounded", "bounded")

# The token must END at a word boundary. A PREFIX test (`v.startswith("bounded")`) accepted
# `bounds = "boundedness:unwind=8"` as a bounded declaration, while the Markdown side located
# its token with `\b(?:un)?bounded\b` and refused the twin — a parity break INSIDE the shared
# module, which is the one place this design assumed could not have one. Found by review, round 5.
#
# EXACT LOWERCASE (ruled 2026-08-28): no longer `re.IGNORECASE`. `re.IGNORECASE` compiled to the
# emitted schema as an inline `(?i:...)` group, Python-only syntax invalid in ECMA-262. Tightened
# rather than rewritten as an explicit case class because every shipped `bounds` value is already
# exact lowercase (2 "bounded", 3 "unbounded" across examples/) — a case variant is now refused,
# by this function AND by the emitted schema pattern, in step.
BOUNDS_TOKEN_RE = re.compile(r"^(" + "|".join(BOUNDS_TOKENS) + r")\b")


def bounds_token(value: str | None) -> str | None:
    """The leading `bounded`/`unbounded` token, or None. Exact token, not prefix."""
    if not isinstance(value, str):
        return None
    m = BOUNDS_TOKEN_RE.match(value.strip())
    return m.group(1).lower() if m else None


def bounds_tail(value: str | None) -> str:
    """Whatever follows the leading token, stripped of the separators a producer writes."""
    tok = bounds_token(value)
    if tok is None:
        return ""
    return value.strip()[len(tok):].strip(SEPARATOR_STRIP_CHARS)


def has_bounds_tail(value: str | None) -> bool:
    """core.md §5: the token alone is not a boundedness declaration. §5 requires "plus free
    text stating the actual limit", and the whole `decode_length is canonical FOR INPUTS UP TO
    16 BYTES` argument rests on that text existing. `bounds = "bounded"` says which of two words
    applies and nothing about what the check ranged over.

    The floor is deliberately LOWER than `is_phrase`, and not by accident: a real limit is very
    often a single token — `unwind=8`, `[u8;12]`, `T=i32` — and a rule that demanded two English
    words there would reject the most precise declarations in the corpus while accepting
    `bounded: quite small`. So: at least one word token of two or more characters after the
    leading `bounded`/`unbounded`.

    Shape only. Whether the tail names the REAL limit is not checkable — a producer can write
    `bounded: some inputs` and satisfy this — and §5 says so out loud."""
    return bool(PHRASE_WORD_RE.search(bounds_tail(value)))
