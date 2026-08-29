#!/usr/bin/env python3
"""emit_schema.py — emits the acceptance/0 manifest's JSON Schema (draft 2020-12), and checks a
TOML manifest's parsed data against it.

Pure stdlib, no dependencies (repo constraint: no third-party `jsonschema` package).

WHY THIS FILE EXISTS
--------------------
`tools/acceptance_grammar.py` exists so a rule cannot drift between the two checkers, because
there is only one of it. The schema artifact extends the same discipline one step further: it is
GENERATED from `acceptance_grammar.py` and `check_acceptance.py`'s live registries — imported, not
copied — so the shipped schema file and the validator's actual closed vocabularies cannot drift
apart either. Nothing in this module hand-writes a grade token, a band name, an evidence kind, or
a hash pattern; every closed-vocabulary value below is read out of the modules that already own it.

SHAPE vs SEMANTICS
------------------
This schema is SHAPE-normative only: table/field presence, field types, and closed-vocabulary
membership. It deliberately does NOT attempt any constraint that depends on more than one field
(status/grade coherence, band reachability, a control's carrier-family compatibility, the F4
observed-red/result contradiction guard, hash recomputation and subject/evidence binding equality,
weight-conditioned requiredness, phrase floors, cross-file uniqueness, filesystem existence). Those
are SEMANTIC rules, enforced by `tools/check_acceptance.py`, never by this schema — each is instead
named in the schema's own `x-semantic-only-rules` array and, where it attaches to one field, in
that field's `description`. See spec/format.md "The schema artifact" and spec/core.md's layered-
validation note.

Two keyword-budget choices, made deliberately (see `_INTERPRETER_KEYWORDS`, below):
  - The schema uses exactly: type, enum, minLength, minimum, pattern, properties, required,
    additionalProperties, items. No `allOf`/`if`/`then`/`const`/`oneOf`/`anyOf`/`not` — every
    conditional, cross-field, or per-`kind` obligation is semantic-only by the paragraph above, so
    there is nothing here for a conditional schema keyword to express.
  - `additionalProperties: false` is used ONLY on `[claim.self_verify]` and
    `[claim.self_verify.watched_fail]`, because those two tables are the only ones
    `check_acceptance.py` itself holds to a closed key set (unknown-key errors); every other table
    in the format is open in the live validator, and the schema says so by leaving
    `additionalProperties` unset there (defaulting to permissive, matching the validator exactly).

Usage:
    emit_schema.py                         emit the schema to stdout (deterministic bytes)
    emit_schema.py --check FILE [FILE...]  validate parsed TOML against the schema (structural
                                            subset only — see `_iter_errors`)
    emit_schema.py --selftest              embedded TOML fixtures (good + deliberately broken),
                                            the common-subset assertion's own positive-control
                                            cases, and a determinism (emit-twice) check

Exit codes: 0 = all checked files/fixtures pass; 1 = at least one fails.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m11  # noqa: E402
import acceptance_grammar as grammar  # noqa: E402
import check_acceptance as ca  # noqa: E402

SCHEMA_VERSION = "0.1.0-draft"
SCHEMA_FILENAME = f"acceptance-{SCHEMA_VERSION}.schema.json"

# ---------------------------------------------------------------------------
# Patterns derived LIVE from the modules that own them — never hand-copied.
# ---------------------------------------------------------------------------

_HEX_LEN = hashlib.sha512().digest_size * 2  # 128 — inherent to SHA-512, not a magic number
# `re.escape` backslash-escapes the hyphen in "sha-512" (`sha\-512`) even though a hyphen is not a
# regex metacharacter outside a character class — a needless-but-valid escape that is nonetheless
# noise in an artifact meant to be read by a human or a third-party validator. Stripped here,
# cosmetic only: `.replace(r"\-", "-")` undoes exactly that one over-escape and nothing else,
# because ALGORITHM ("sha-512") has no other character `re.escape` would touch.
_ALGO_PATTERN = re.escape(m11.ALGORITHM).replace(r"\-", "-")
M11_HASH_PATTERN = f"^{_ALGO_PATTERN}:[0-9a-f]{{{_HEX_LEN}}}$"

# BOUNDS_TOKENS is ORDER-SENSITIVE ("unbounded" before "bounded" — see acceptance_grammar.py's own
# comment on why: alternation order, not sorting, is what keeps "bounded" from matching the first
# few letters of "unbounded"). Do not sort this one.
#
# EXACT LOWERCASE, no inline flag (ruled 2026-08-28): `(?i:...)` is a Python-only inline-flag
# GROUP — invalid in the ECMA-262 dialect JSON Schema requires (and what VS Code and every
# JS-based validator compiles against). `acceptance_grammar.BOUNDS_TOKEN_RE`, the validator's own
# check, was tightened to match: case variants are now refused on both sides, not just here.
BOUNDS_TOKEN_PATTERN = (
    "^(?:" + "|".join(re.escape(t) for t in grammar.BOUNDS_TOKENS) + r")\b"
)

# `acceptance_grammar.SCOPE_REF_LOCATOR_RE` is no longer compiled with `re.IGNORECASE` (ruled
# 2026-08-28 — see that module) so `.pattern` needs no flag re-applied here; re-applying `(?i)` as
# an inline group was itself one of the three Python-only constructs this generator now refuses to
# emit (see `_assert_ecma_compatible`, below).
SCOPE_REF_PATTERN = grammar.SCOPE_REF_LOCATOR_RE.pattern
ISO_DATE_PATTERN = grammar.ISO_DATE_RE.pattern
# `check_acceptance.COVERED_FRACTION_RE` is likewise no longer compiled with `re.IGNORECASE`; its
# case-insensitivity on the "of" word is now baked into the pattern itself as explicit `[oO][fF]`
# character classes, which are common-subset and need no flag re-application here either.
COVERED_FRACTION_PATTERN = ca.COVERED_FRACTION_RE.pattern
COMMIT_PATTERN = ca.COMMIT_RE.pattern
# P3 (evidence-types.md "Control block"): the same git-object-name floor the `[format]`
# self-location shas use (7-40 lowercase hex, full or abbreviated) — shared with
# `captured_at_commit`, which is optional and abbreviation-tolerant, unlike [subject].commit above
# (COMMIT_PATTERN), which is the strict full 40-hex form.
SELF_LOCATION_SHA_PATTERN = ca.SELF_LOCATION_SHA_RE.pattern

# ---------------------------------------------------------------------------
# Common-subset law (ruled 2026-08-28): every regex pattern reaching the emitted schema must be
# written in the Python ∩ ECMA-262 common subset, because the schema is consumed by ECMA-262
# engines (VS Code, every JS-based JSON Schema validator) that reject Python-only regex syntax
# outright. This generator refuses to emit a pattern containing one of the constructs below;
# `--selftest` proves the assertion actually fires (see `_ECMA_ASSERTION_CASES`, below).
# ---------------------------------------------------------------------------

_NON_ECMA_CONSTRUCTS = (
    (r"(?i", "Python inline-flag group '(?i...)' — no ECMA-262 equivalent; rewrite the pattern "
              "in explicit character classes or drop the flag if the data is uniformly one case"),
    (r"(?a", "Python inline-flag group '(?a...)' — no ECMA-262 equivalent"),
    (r"(?L", "Python inline-flag group '(?L...)' — no ECMA-262 equivalent"),
    (r"(?m", "Python inline-flag group '(?m...)' — no ECMA-262 equivalent"),
    (r"(?s", "Python inline-flag group '(?s...)' — no ECMA-262 equivalent"),
    (r"(?u", "Python inline-flag group '(?u...)' — no ECMA-262 equivalent"),
    (r"(?x", "Python inline-flag group '(?x...)' — no ECMA-262 equivalent"),
    (r"(?P<", "Python named-group syntax '(?P<name>...)' — ECMA-262 uses '(?<name>...)'"),
    (r"(?P=", "Python named-backreference syntax '(?P=name)' — no ECMA-262 equivalent"),
    (r"\A", r"Python-only anchor '\A' — ECMA-262 has no start-of-string-only anchor; use '^'"),
    (r"\Z", r"Python-only anchor '\Z' — ECMA-262 has no end-of-string-only anchor; use '$'"),
    (r"(?>", "possessive/atomic group '(?>...)' — no ECMA-262 equivalent"),
)


def _assert_ecma_compatible(pattern: str, name: str) -> None:
    """Fail generation outright if `pattern` contains a construct ECMA-262 cannot parse. A
    `(?<letter>` INLINE-FLAG group (Python's `(?i:...)`-style scoped flag) is covered by the
    `(?i`/`(?a`/etc rows above; a NAMED CAPTURE `(?<name>...)` is valid ECMA-262 and deliberately
    NOT flagged here — only `(?P<` (Python's spelling of the same idea) is Python-only."""
    for needle, why in _NON_ECMA_CONSTRUCTS:
        if needle in pattern:
            raise AssertionError(
                f"emit_schema: pattern {name!r} contains a non-ECMA-262 construct {needle!r} "
                f"({why}) — pattern was {pattern!r}. Fix the SOURCE registry the pattern is "
                f"derived from (acceptance_grammar.py / check_acceptance.py), never this "
                f"generated pattern in isolation."
            )


def _assert_all_patterns_ecma_compatible() -> None:
    for name, pattern in (
        ("M11_HASH_PATTERN", M11_HASH_PATTERN),
        ("BOUNDS_TOKEN_PATTERN", BOUNDS_TOKEN_PATTERN),
        ("SCOPE_REF_PATTERN", SCOPE_REF_PATTERN),
        ("ISO_DATE_PATTERN", ISO_DATE_PATTERN),
        ("COVERED_FRACTION_PATTERN", COVERED_FRACTION_PATTERN),
        ("COMMIT_PATTERN", COMMIT_PATTERN),
    ):
        _assert_ecma_compatible(pattern, name)


_assert_all_patterns_ecma_compatible()

WATCHED_FAIL_FIELDS = {"of_command", "perturbed", "observed", "date"}

# The union of every KIND_REGISTRY "extra" field, merged across kinds. Per-kind requiredness and
# per-kind type (str-any vs str-nonempty differ by kind for the same field name, e.g. `semantics`)
# are semantic-only (see x-semantic-only-rules "per-kind-extra-fields") — this schema documents the
# loosest common shape so it never rejects a value the live registry would accept.
_EXTRA_FIELD_TAGS: dict[str, set[str]] = {}
for _kind, _reg in ca.KIND_REGISTRY.items():
    for _field, _tag in _reg["extra"].items():
        _EXTRA_FIELD_TAGS.setdefault(_field, set()).add(_tag)


# ---------------------------------------------------------------------------
# Small builders — deterministic, self-documenting node shapes.
# ---------------------------------------------------------------------------

def _s(desc: str) -> dict:
    return {"type": "string", "description": desc}


def _any(desc: str) -> dict:
    """A genuinely UNCONSTRAINED node: an annotation and no assertion keyword, which JSON Schema
    reads as the true schema (everything validates). Used only where the live validator places no
    type requirement on a field at all.

    Written as its own builder rather than reached for ad hoc, because the defect it fixes was
    exactly a description that SAID unconstrained beside a node that said `"type": "string"`
    (RESERVED trust fields, found by a cold review 2026-08-28): the validator accepted the
    calibrated numeric values the schema rejected, so the two layers disagreed about the same
    field while the prose claimed they did not."""
    return {"description": desc}


def _s1(desc: str) -> dict:
    return {"type": "string", "minLength": 1, "description": desc}


def _pat(pattern: str, desc: str) -> dict:
    return {"type": "string", "pattern": pattern, "description": desc}


def _enum(values, desc: str) -> dict:
    return {"type": "string", "enum": sorted(values), "description": desc}


def _bool(desc: str) -> dict:
    return {"type": "boolean", "description": desc}


def _int(desc: str, minimum: int | None = None) -> dict:
    node = {"type": "integer", "description": desc}
    if minimum is not None:
        node["minimum"] = minimum
    return node


def _arr(items: dict, desc: str) -> dict:
    return {"type": "array", "items": items, "description": desc}


def _obj(properties: dict, required: list[str], desc: str, closed: bool = False) -> dict:
    node = {
        "type": "object",
        "properties": properties,
        "required": sorted(required),
        "description": desc,
    }
    if closed:
        node["additionalProperties"] = False
    return node


def _extra_field_schema(field: str) -> dict:
    tags = _EXTRA_FIELD_TAGS[field]
    if tags == {"list"}:
        node = {"type": "array"}
    elif tags <= {"str-nonempty", "str-any"}:
        node = {"type": "string"}
    elif tags == {"int-pos"}:
        node = {"type": "integer", "minimum": 1}
    elif tags == {"bounds-token"}:
        node = {"type": "string", "pattern": BOUNDS_TOKEN_PATTERN}
    else:  # pragma: no cover — a new tag combination would need a new branch here
        node = {"type": "string"}
    node["description"] = (
        f"KIND_REGISTRY 'extra' field for kind(s) using it. Per-kind requiredness and exact tag "
        f"({sorted(tags)}) are semantic-only, conditioned on this record's own `kind` — see "
        f"x-semantic-only-rules 'per-kind-extra-fields' and spec/evidence-types.md."
    )
    return node


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_format() -> dict:
    props = {
        "id": {
            "type": "string",
            "enum": ["acceptance/0"],
            "description": "The format id. Exact string; a breaking change bumps the integer "
                           "(spec/format.md 'Stability').",
        },
        "shape": _enum(
            ca.SHAPE_VALUES,
            "single-file vs bundle (spec/format.md '`shape`'). SEMANTIC: 'bundle' makes the "
            "WHOLE manifest `indeterminate`, not just this field, until bundle validation ships — "
            "not expressible as a shape constraint (x-semantic-only-rules 'shape-bundle-"
            "indeterminate').",
        ),
        "spec_id": _s1("Which contract this manifest is written against (core.md §0.6)."),
        "spec_sha": _s1("The spec commit/tag this manifest targets."),
        "validator_sha": _s1("The validator commit that checked this manifest."),
        "generated_by": _s1("Generator id + version, or the literal 'hand-authored'."),
        "generated_at": _s1("ISO 8601 timestamp; shape only, not parsed as a date by the "
                            "validator."),
        "illustrative": _bool(
            "Defaults to false. true = a teaching example, not a certificate (core.md §0.6, "
            "CS-21/22) — several semantic rules below are not enforced against an illustrative "
            "manifest."
        ),
    }
    required = ["id", "shape", "spec_id", "spec_sha", "validator_sha", "generated_by",
                "generated_at"]
    return _obj(props, required, "[format] — self-location (format.md '`[format]` self-location').")


def _build_subject() -> dict:
    props = {
        "name": _s1("The artifact this manifest certifies."),
        "kind": _enum(
            ca.SUBJECT_KINDS,
            "The artifact-class registry (format.md '`[subject].kind`'). SEMANTIC NUANCE: this "
            "registry is fail-CLOSED-TO-INDETERMINATE in the live validator — a token outside it "
            "is `indeterminate`, not a hard `invalid` — which is SOFTER than a strict JSON Schema "
            "`enum` (which rejects any other value outright). A third-party schema-only consumer "
            "will therefore reject some manifests the validator itself would only flag "
            "indeterminate; see x-semantic-only-rules 'subject-kind-registry-fail-closed'.",
        ),
        "commit": _pat(
            COMMIT_PATTERN,
            "40 lowercase hex chars — git-domain identity (SHA-1 over the repository tree). "
            "NEVER compared against an M11 hash (design rule 4a).",
        ),
        "dirty": _bool("true = uncommitted changes were present at `commit`."),
        "subject_hash": _pat(
            M11_HASH_PATTERN,
            "OPTIONAL. The M11 content-hash of the subject artifact, `subject:` domain (design "
            "rule 4a). SEMANTIC: when present, every [[claim.evidence]] record naming its own "
            "`subject_hash` must equal this value exactly — an equality binding, not a shape "
            "constraint.",
        ),
        "record_root": _s1(
            "OPTIONAL. The base path every `record` pointer on this manifest resolves against, "
            "instead of the manifest file's own directory (audit F-3)."
        ),
        "repo": _s1(
            "OPTIONAL. An identifier for the subject's own repository; not validator-interpreted."
        ),
    }
    required = ["name", "kind", "commit", "dirty"]
    return _obj(props, required, "[subject] — the artifact this manifest certifies.")


def _build_spec() -> dict:
    props = {
        "path": _s1("The governing spec document."),
        "version": _s1("The spec version the [[claim]] `clause` ids refer to."),
        "axis": _s1(
            "OPTIONAL structurally. SEMANTIC: REQUIRED once ANY claim in the file claims weight "
            "(core.md §6/W2) — not enforced here because that requirement is conditioned on a "
            "sibling table's contents, not on [spec] alone. See x-semantic-only-rules "
            "'axis-required-once-any-claim-weighted'."
        ),
        "external": _arr(_s1("A normative reference not in the tree."),
                          "OPTIONAL list of normative references not held in the tree."),
    }
    required = ["path", "version"]
    return _obj(props, required, "[spec] — the governing document [[claim]] clauses cite.")


def _build_coverage() -> dict:
    props = {
        "clauses_total": _int(
            "Total clause count in spec@version. SEMANTIC floor: must be >= 1 (enforced by the "
            "validator; not encoded as `minimum` here to keep this schema's own numeric floors "
            "confined to fields the validator checks unconditionally — see "
            "x-semantic-only-rules).",
        ),
        "claims_total": _int(
            "SEMANTIC: must equal the number of [[claim]] entries actually present — a cross-"
            "field count, not a type constraint (x-semantic-only-rules "
            "'claims-total-must-match-claim-count')."
        ),
        "denominator": _enum(
            ca.DENOMINATOR_VALUES,
            "OPTIONAL, EXPERIMENTAL (CLAIM-CLASSES-AWAITING-WEIGHT.md C1): complete | slice. "
            "Validated for shape only even by the live validator.",
        ),
        "slice_note": _s1(
            "SEMANTIC: REQUIRED, nonempty, when denominator == 'slice' — a conditional "
            "requirement, not encoded structurally here."
        ),
    }
    required = ["clauses_total", "claims_total"]
    return _obj(props, required, "[coverage] — the omission-detection block.")


def _build_watched_fail() -> dict:
    props = {
        "of_command": _s1(
            "SEMANTIC: must equal this claim's own self_verify.command, whitespace-normalized — "
            "an equality binding across sibling tables, not a shape constraint (core.md §4.1)."
        ),
        "perturbed": _s1(
            "SEMANTIC: must be a PHRASE (>=2 word tokens after stripping a trailing date "
            "annotation) — a single token is not a statement (core.md §4.1)."
        ),
        "observed": _s1("SEMANTIC: same phrase floor as `perturbed`."),
        "date": _pat(ISO_DATE_PATTERN, "ISO date (YYYY-MM-DD)."),
    }
    return _obj(
        props, sorted(WATCHED_FAIL_FIELDS),
        "[claim.self_verify.watched_fail] — a structured witness that the recipe CAN report the "
        "claim false (core.md §4.1). CLOSED key set: check_acceptance.py errors on any key "
        "outside {of_command, perturbed, observed, date} — this table is one of exactly two in "
        "the whole format where `additionalProperties: false` reflects genuine, unconditional "
        "validator behaviour.",
        closed=True,
    )


def _build_self_verify() -> dict:
    props = {
        "command": _s(
            "The consumer-side recipe. SEMANTIC: REQUIRED (nonempty) whenever this claim's "
            f"`grade` is one of {sorted(ca.GRADES_REQUIRING_SELF_VERIFY)} (core.md §1/§3)."
        ),
        "expect": _s(
            "SEMANTIC: REQUIRED (nonempty) whenever `command` is present — 'what green means' "
            "has to be written (core.md §3 rule 2)."
        ),
        "precondition": _s("OPTIONAL freshness/environment guard."),
        "positive_control": _s(
            "SEMANTIC: REQUIRED (nonempty, phrase floor) when grade == 'not-covered' (core.md "
            "§4) — a grep zero is a claim about the pattern, not the code."
        ),
        "watched_fail": _build_watched_fail(),
        "expect_stream": _enum(
            ca.EXPECT_STREAM_VALUES,
            "OPTIONAL, defaults to 'stdout' (core.md §8.2): which stream `--execute` matches "
            "`expect` against.",
        ),
    }
    return _obj(
        props, [], "[claim.self_verify] — the consumer-side recipe (core.md §3), distinct from "
        "evidence. CLOSED key set: check_acceptance.py errors on any key outside "
        f"{sorted(ca.SELF_VERIFY_FIELDS)} (no legacy producers to tolerate typos from) — the "
        "other of exactly two tables in the format where `additionalProperties: false` is "
        "genuine validator behaviour, not a schema-author's guess.",
        closed=True,
    )


def _build_control() -> dict:
    props = {
        "kind": _enum(
            ca.CONTROL_KIND_VALUES,
            "mutation | ablation | planted-twin (assurance-bands.md rule 6). SEMANTIC: which "
            "kinds actually band-lift, and at which band, is a per-band whitelist — not "
            "expressible here (x-semantic-only-rules 'band-control-gate').",
        ),
        "expectation": _enum(ca.CONTROL_EXPECTATION_VALUES, "What this control was PREDICTED "
                              "to show, declared before the run."),
        "observed": _enum(ca.CONTROL_EXPECTATION_VALUES, "What the run actually showed."),
        "of_claim": _s1(
            "SEMANTIC: must equal the `id` of the [[claim]] this evidence record is nested "
            "under (assurance-bands.md rule 6) — an equality binding, not a shape constraint. A "
            "value naming no claim anywhere in the file is a separate, additional error "
            "(check_dangling_of_claim)."
        ),
    }
    required = ["kind", "expectation", "observed", "of_claim"]
    return _obj(
        props, required,
        "[claim.evidence.control] — OPTIONAL, family-agnostic (assurance-bands.md rule 6 / "
        "evidence-types.md 'Control block'). Open key set: the live validator does not reject "
        "extra keys here.",
    )


def _build_evidence_item() -> dict:
    props = {
        "kind": _enum(
            ca.KIND_REGISTRY.keys(),
            "The evidence-kind registry (evidence-types.md). Unlike [subject].kind, an unknown "
            "token here is a hard `invalid`, not `indeterminate` — this enum is genuinely closed "
            "in the live validator.",
        ),
        "family": _enum(
            {reg["family"] for reg in ca.KIND_REGISTRY.values()},
            "bmc | kernel | smt-refinement | dynamic | mechanical | judgment. SEMANTIC: must "
            "equal the `family` KIND_REGISTRY[kind] pins — a cross-field consistency rule, not "
            "independently enforceable from `family`'s own enum membership alone "
            "(x-semantic-only-rules 'kind-family-consistency').",
        ),
        "ref": _s1("The harness/theorem/test id — the checkable name."),
        "result": _enum(ca.RESULTS, "pass | fail | unsupported (design rule 5: recorded as-is, "
                        "never adjudicated)."),
        "tool": _s1("Tool identity AT BUILD GRANULARITY (commit, not version)."),
        "record": _s1(
            "Pointer to the raw run record. SEMANTIC: must resolve to an existing file under "
            "`--strict` (or [subject].record_root, if set) — a filesystem check, not a shape "
            "constraint."
        ),
        "record_hash": _pat(
            M11_HASH_PATTERN,
            "The evidence-record-domain M11 hash of the `record` file. SEMANTIC: REQUIRED on a "
            "WEIGHTED claim's evidence when not illustrative (evidence-types.md P9); when "
            "present, the validator recomputes it from `record`'s actual bytes and a mismatch is "
            "always an error — recomputation and the weighted-requiredness are both semantic, "
            "not shape.",
        ),
        "subject_hash": _pat(
            M11_HASH_PATTERN,
            "OPTIONAL. SEMANTIC: when present, must equal [subject].subject_hash exactly (design "
            "rule 4a) — an equality binding, not a shape constraint.",
        ),
        "captured_at_commit": _pat(
            SELF_LOCATION_SHA_PATTERN,
            "OPTIONAL (P3, evidence-types.md 'Control block'). 7-40 lowercase hex — a git object "
            "name, full or abbreviated, naming the commit at which this record's transcript was "
            "captured. DISCLOSURE ONLY: it is never a second validity key and this schema and the "
            "live validator both check it for shape alone — content identity is decided "
            "exclusively by `subject_hash`, above.",
        ),
        "method": _s1("OPTIONAL, profile-defined technique name (evidence-types.md CS-1/CS-2)."),
        "epistemic_tier": _enum(
            ca.EPISTEMIC_TIERS,
            "OPTIONAL, closed core vocabulary T1..T5. SEMANTIC: where `method` names a token the "
            "shipped FV profile knows, the profile-pinned tier is a CEILING on `epistemic_tier` "
            "— a STRONGER declared tier is an error, a weaker-or-equal one is accepted "
            "(evidence-types.md CS-3, ADR-002) — a cross-field coherence rule, not independently "
            "checkable from this field's own enum membership.",
        ),
        "mutants_total": _int("OPTIONAL. SEMANTIC floor: >= 1.", ),
        "mutants_caught": _int(
            "OPTIONAL. SEMANTIC: >= 0, and additionally >= 1 whenever this record's own "
            "`result` == 'pass' (assurance-bands.md rule 6) — a cross-field floor, not "
            "independently expressible as this field's own `minimum`."
        ),
        "control": _build_control(),
        "calibration": _s1(
            "OPTIONAL. SEMANTIC: REQUIRED (nonempty) whenever any of alpha/beta/lr is present "
            "(format.md design rule 3) — trust numbers without calibration are banned."
        ),
        "alpha": _any(
            "RESERVED trust field (format.md design rule 3). Type is intentionally "
            "UNCONSTRAINED here — this node states no type at all: the live validator places no "
            "type requirement on this field, only the `calibration` companion above. It emitted "
            "`\"type\": \"string\"` until 2026-08-28, which REJECTED the calibrated numeric "
            "values the validator accepts; the description and the node now agree."
        ),
        "beta": _any("RESERVED trust field — see `alpha`."),
        "lr": _any("RESERVED trust field — see `alpha`."),
    }
    for field in sorted(_EXTRA_FIELD_TAGS):
        props[field] = _extra_field_schema(field)
    required = sorted(set(ca.UNIVERSAL_EVIDENCE_FIELDS) | {"result"})
    return _obj(
        props, required,
        "[[claim.evidence]] — an admissible evidence record (evidence-types.md). >=1 required "
        "when the enclosing claim's status is evidenced/partial; forbidden when gap/parked/"
        "blocked (design rule 1 / core.md §7.3) — a cross-field cardinality rule on the "
        "enclosing claim's `evidence` array, not expressible on this item schema alone.",
    )


def _build_claim() -> dict:
    props = {
        "id": _s1("Stable, unique within the file, never reused (format.md design rule 6). "
                 "SEMANTIC: file-wide uniqueness is a cross-claim rule, not a per-field pattern."),
        "clause": _s1("The spec clause id this claim is about."),
        "item": _s1("The code item the claim attaches to."),
        "statement": _s1("What is being claimed, in prose."),
        "band": _enum(
            ca.BANDS,
            "The asserted evidence-species floor, A0..A4 (assurance-bands.md). 'A3.5' is a "
            "reserved band the validator warns on (tool not adopted). SEMANTIC: whether the band "
            "is actually REACHABLE by this claim's own passing evidence, and whether an "
            "oracle-bearing band's control-gate is satisfied, are both cross-field rules — see "
            "x-semantic-only-rules 'band-reachability' / 'band-control-gate'.",
        ),
        "status": _enum(
            ca.STATUSES,
            "evidenced | partial | gap | parked | blocked. SEMANTIC: must COHERE with `grade` "
            "(core.md §7.1) and gates the `evidence` array's required cardinality (design rule "
            "1 / §7.3) — neither is expressible from `status`'s own enum membership alone.",
        ),
        "weight": _enum(
            ca.WEIGHT_VALUES,
            "OPTIONAL, defaults to unweighted (core.md W1). 'weighted' switches on the whole "
            "anti-overclaim machinery this schema marks SEMANTIC throughout this claim's fields.",
        ),
        "grade": _enum(
            ca.CLAIM_GRADE_VALUES,
            "OPTIONAL structurally. SEMANTIC: REQUIRED when weight == 'weighted' (core.md W2); "
            f"{sorted(ca.UNWEIGHTABLE_GRADES)} can never carry weight even when present "
            "(x-semantic-only-rules 'grade-required-on-weighted').",
        ),
        "clause_source": _enum(
            ca.CLAUSE_SOURCE_VALUES,
            "OPTIONAL in general. SEMANTIC: REQUIRED when weight == 'weighted' (core.md W2.3, "
            f"transitional per §8.1); {sorted(grammar.CLAUSE_SOURCES_UNWEIGHTABLE)} are RESERVED "
            "to mean unweightable by design and refuse weight outright when present "
            "(x-semantic-only-rules 'clause-source-reserved-tokens-unweightable')."
        ),
        "bounds": _pat(
            BOUNDS_TOKEN_PATTERN,
            "This pattern checks only the leading 'bounded'/'unbounded' TOKEN. SEMANTIC: "
            f"REQUIRED when grade is one of {sorted(ca.GRADES_REQUIRING_BOUNDS)} (core.md §5), "
            "AND the token alone does not satisfy §5 — a free-text tail naming the actual limit "
            "is also required and is not pattern-checkable (x-semantic-only-rules "
            "'bounds-free-text-tail-required')."
        ),
        "doc_ref": _s1(
            "OPTIONAL. SEMANTIC (warning, not error): SHOULD be present when grade == "
            "'inspection-argued' — never weight-eligible either way."
        ),
        "scope_ref": _pat(
            SCOPE_REF_PATTERN,
            "A locator: a section marker, an anchor, a document path, or `[spec].axis`. "
            "SEMANTIC: REQUIRED when grade == 'out-of-scope' (core.md §1/§7.1); this pattern "
            "checks locator SHAPE only — that the cited location really says out-of-scope is "
            "reviewer work.",
        ),
        "item_kind": _enum(
            ca.ITEM_KIND_VALUES,
            "OPTIONAL, defaults to 'item' (core.md §7.2). SEMANTIC: 'predicate' additionally "
            "requires `over` and a valid `covered` fraction with numerator <= denominator — a "
            "cross-field requirement, not expressible on this field alone.",
        ),
        "over": _s1("SEMANTIC: REQUIRED when item_kind == 'predicate' — what the predicate "
                    "ranges over."),
        "covered": _pat(
            COVERED_FRACTION_PATTERN,
            "N/M or 'N of M'. SEMANTIC: REQUIRED when item_kind == 'predicate'; N <= M is a "
            "cross-value check this pattern alone cannot express."
        ),
        "parked_reason": _s1("SEMANTIC: REQUIRED when status == 'parked'."),
        "blocked_by": _s1(
            "SEMANTIC: REQUIRED when status == 'blocked' (core.md §7.3, P4) — names what blocks "
            "the item; without it an escalation reads as a backlog entry."
        ),
        "self_verify": _build_self_verify(),
        "evidence": _arr(
            _build_evidence_item(),
            ">=1 required when status is evidenced/partial; forbidden (must be empty/absent) "
            "when status is gap/parked/blocked (design rule 1 / core.md §7.3) — a cardinality "
            "rule conditioned on the sibling `status` field, semantic-only.",
        ),
    }
    required = ["id", "clause", "item", "statement", "band", "status"]
    return _obj(
        props, required,
        "[[claim]] — (spec clause, code item, evidence, assumptions). Open key set: fields not "
        "listed here (e.g. [[claim.assumes]], and the Reserved-hooks slots H1-H8 named in "
        "spec/format.md) are neither validated nor rejected by check_acceptance.py in this "
        "revision, so this schema asserts nothing about their shape either — see "
        "x-semantic-only-rules 'claim-open-extension-fields'.",
    )


# ---------------------------------------------------------------------------
# The rules this schema deliberately does NOT attempt — generated where the values are live,
# static prose (citing spec sections) otherwise. Every entry names the enforcing validator
# function/rule so a reader can find the live check.
# ---------------------------------------------------------------------------

def _build_semantic_rules() -> list[dict]:
    rules = [
        ("status-grade-coherence",
         "status × grade must cohere (core.md §7.1) — a gap/parked/blocked status may not carry "
         "a grade asserting a check succeeded, and evidenced/partial may not carry not-covered "
         "or out-of-scope. Error on a weighted claim, warning otherwise.",
         "check_acceptance.status_grade_incoherence / acceptance_grammar.status_grade_incoherence"),
        ("band-reachability",
         "A claim's asserted `band` must be reachable by at least one of its own PASSING "
         "evidence records' kind/family (assurance-bands.md rule 2).",
         "check_acceptance._band_reachable / check_band_reachability"),
        ("band-control-gate",
         "Oracle-bearing bands (A2/A3/A4, and functional A1) require >=1 observed-red control "
         "whose kind is on that band's whitelist and whose carrier record's family is species-"
         "compatible with the band (assurance-bands.md rule 6); a 'planted-twin' control never "
         "satisfies this gate at any band.",
         "check_acceptance._check_control_gate / _control_lifts_band"),
        ("control-of-claim-binding",
         "control.of_claim must equal the id of the [[claim]] the evidence record is nested "
         "under; a value naming no claim anywhere in the file is a separate additional error "
         "(assurance-bands.md rule 6).",
         "check_acceptance.check_control_of_claim_mismatch / check_dangling_of_claim"),
        ("control-result-contradiction",
         "F4: a record may not simultaneously have control.kind == 'mutation', "
         "control.observed == 'red', and its own `result` == 'pass' — an observed-red mutation "
         "control describes the mutant run, not the baseline run `result` describes.",
         "check_acceptance.check_evidence_record (F4 contradiction guard)"),
        ("contract-requires-symbolic-domain",
         f"grade == 'contract' requires >=1 PASSING evidence record whose family is in "
         f"{sorted(ca.SYMBOLIC_DOMAIN_FAMILIES)} (core.md §0.5) — evidence that only enumerates "
         "values witnesses points, not sets, and a test is never `contract`.",
         "check_acceptance.check_claims (§0.5/§1 contract-requires-symbolic-domain guard)"),
        ("epistemic-tier-grade-coherence",
         "grade == 'contract' additionally requires >=1 PASSING evidence record with "
         "epistemic_tier in {T1, T2} (core.md §2, CS-4); transitional, refused into "
         "`weight-pending` rather than an unconditional hard error.",
         "check_acceptance.check_claims (CS-4 guard)"),
        ("method-epistemic-tier-pinning",
         "Where `method` names a token the shipped FV profile knows, the profile-pinned tier is "
         "a CEILING on `epistemic_tier`: a STRONGER declared tier is an error, a weaker-or-equal "
         "one is accepted (evidence-types.md CS-3, ADR-002). An unprofiled `method` makes the "
         "record's epistemic_tier `indeterminate`, not a hard error.",
         "check_acceptance.check_evidence_record (CS-3 guard); METHOD_EPISTEMIC_TIER"),
        ("watched-fail-witness-required",
         f"A weighted claim whose grade is one of {sorted(ca.GRADES_REQUIRING_SELF_VERIFY)} "
         "requires a watched-fail witness: a well-formed [claim.self_verify.watched_fail] "
         "table, OR an observed-red control naming this claim, OR (grade == 'not-covered' only) "
         "a nonempty positive_control (core.md §4.1, W2.5).",
         "check_acceptance._has_watched_fail_witness / _watched_fail_block_is_valid"),
        ("watched-fail-of-command-binding",
         "watched_fail.of_command must equal this claim's own self_verify.command, whitespace-"
         "normalized (core.md §4.1) — a control over a different check witnesses nothing about "
         "this one.",
         "check_acceptance.check_watched_fail_block"),
        ("positive-control-phrase-floor",
         "self_verify.positive_control must be a PHRASE (>=2 word tokens), not a single token "
         "(core.md §4) — the same shape floor as watched_fail.perturbed/observed.",
         "check_acceptance.check_self_verify"),
        ("bounds-free-text-tail-required",
         f"The claim-level `bounds` field, required on grades {sorted(ca.GRADES_REQUIRING_BOUNDS)}, "
         "must carry a free-text tail naming the actual limit after the bounded/unbounded token "
         "— the token alone is refused (core.md §5).",
         "check_acceptance.check_grade_companions / acceptance_grammar.has_bounds_tail"),
        ("scope-ref-locator-is-shape-only",
         "is_scope_locator checks that scope_ref LOOKS like a locator; that the cited location "
         "actually says the item is out of scope is reviewer work, not checkable (core.md §7.1).",
         "acceptance_grammar.is_scope_locator"),
        ("clause-source-required-on-weighted",
         "clause_source is REQUIRED on a weighted claim (core.md W2.3); absent, it is refused "
         "into `weight-pending` (an error only under --strict-weight), per the §8.1 transition "
         "ratchet, not an unconditional hard error.",
         "check_acceptance.check_claims (W2.3 guard)"),
        ("clause-source-reserved-tokens-unweightable",
         f"clause_source in {sorted(grammar.CLAUSE_SOURCES_UNWEIGHTABLE)} is reserved to mean "
         "unweightable by design — a clause read off its own evidence, or off nothing, cannot "
         "be falsified (core.md W2).",
         "check_acceptance.check_claims"),
        ("grade-required-on-weighted",
         "A weighted claim requires `grade`; an unweighted claim may omit it entirely (core.md "
         "W2). A grade with no deciding machinery is never weight-eligible even when present.",
         "check_acceptance.check_claims"),
        ("status-evidence-count-coupling",
         "status in {evidenced, partial} requires >=1 [[claim.evidence]] entry; status in "
         "{gap, parked, blocked} requires exactly zero (design rule 1 / core.md §7.3).",
         "check_acceptance.check_claims"),
        ("parked-requires-parked-reason",
         "status == 'parked' requires a nonempty parked_reason.",
         "check_acceptance.check_claims"),
        ("blocked-requires-blocked-by",
         "status == 'blocked' requires a nonempty blocked_by (core.md §7.3, P4) — an escalation "
         "is only greppable if it names what blocks it.",
         "check_acceptance.check_claims"),
        ("predicate-item-requires-over-and-covered",
         "item_kind == 'predicate' requires nonempty `over` and a `covered` fraction N/M with "
         "N <= M (core.md §7.2, P3); a weighted predicate row missing either is refused weight "
         "outright, an unweighted one only warned.",
         "check_acceptance.check_claims"),
        ("claims-total-must-match-claim-count",
         "[coverage].claims_total must equal the number of [[claim]] entries actually present.",
         "check_acceptance.check_coverage"),
        ("claim-id-uniqueness",
         "[[claim]].id must be unique within the file (format.md design rule 6).",
         "check_acceptance.check_claims"),
        ("denominator-slice-requires-slice-note",
         "[coverage].denominator == 'slice' requires a nonempty slice_note "
         "(CLAIM-CLASSES-AWAITING-WEIGHT.md C1).",
         "check_acceptance.check_coverage"),
        ("record-pointer-must-exist",
         "[[claim.evidence]].record must resolve to an existing file (under [subject]."
         "record_root, when set) — enforced as an error only under --strict; a warning "
         "otherwise. A filesystem check, never expressible in a schema.",
         "check_acceptance.check_evidence_record"),
        ("record-hash-recompute-and-required-on-weighted",
         "record_hash is REQUIRED on a weighted, non-illustrative claim's evidence "
         "(evidence-types.md P9); when present, the validator recomputes the M11 hash of the "
         "`record` file's actual bytes and a mismatch is always an error.",
         "check_acceptance.check_evidence_record; tools/m11.py"),
        ("subject-hash-binding-equality",
         "An evidence record's subject_hash, where present, must equal [subject].subject_hash "
         "exactly (design rule 4a) — a present-but-unequal pair is a hard error, unconditionally.",
         "check_acceptance.check_evidence_record (design rule 4a guard)"),
        ("kind-family-consistency",
         "An evidence record's `family` must equal KIND_REGISTRY[kind]['family'] — the "
         "registry's own kind-to-family pinning, not independently derivable from `family`'s "
         "enum membership alone.",
         "check_acceptance.check_evidence_record; KIND_REGISTRY"),
        ("per-kind-extra-fields",
         "Each evidence `kind` in KIND_REGISTRY additionally REQUIRES its own 'extra' fields, at "
         "their own per-kind type tag (e.g. kani-harness requires `bounds`+`semantics`; "
         "lean-theorem requires `axioms`+`semantics`, `semantics` there being str-nonempty where "
         "kani-harness's is str-any). This schema documents the UNION of possible extra fields "
         "at their loosest common shape (see each field's own description); the per-kind "
         "conditional requiredness and exact tag are not expressed structurally.",
         "check_acceptance._check_field; KIND_REGISTRY"),
        ("mutants-caught-floor-on-pass",
         "mutants_caught >= 1 is additionally required whenever the SAME record's `result` == "
         "'pass' (assurance-bands.md rule 6) — a cross-field floor beyond mutants_caught's own "
         ">= 0 type constraint.",
         "check_acceptance.check_evidence_record"),
        ("reserved-trust-fields-require-calibration",
         f"Any of {ca.RESERVED_TRUST_FIELDS} present on an evidence record requires a nonempty "
         "`calibration` companion (format.md design rule 3) — trust numbers without calibration "
         "are banned.",
         "check_acceptance.check_evidence_record"),
        ("axis-required-once-any-claim-weighted",
         "[spec].axis is REQUIRED (nonempty) once ANY [[claim]] in the file claims weight "
         "(core.md §6/W2.4); optional in a wholly unweighted manifest.",
         "check_acceptance.check_spec"),
        ("subject-kind-registry-fail-closed",
         "[subject].kind outside the shipped registry is `indeterminate`, never a hard "
         "`invalid` (format.md '[subject].kind') — SOFTER than this schema's own `enum`, which a "
         "strict third-party JSON Schema validator would reject outright. Known, accepted "
         "divergence: this schema documents the registry as closed for readability; only "
         "check_acceptance.py implements the fail-open-to-indeterminate behaviour.",
         "check_acceptance.check_subject"),
        ("shape-bundle-indeterminate",
         "[format].shape == 'bundle' makes the validator return `indeterminate` for the WHOLE "
         "file, unconditionally, until bundle validation ships (format.md '`shape`') — not a "
         "constraint on the `shape` field's own value space.",
         "check_acceptance.check_format"),
        ("claim-open-extension-fields",
         "[[claim.assumes]] and the Reserved-hooks slots (H1-H8; spec/format.md 'Reserved "
         "hooks') are parseable TOML but are read by NO validator function in this revision — "
         "neither validated nor rejected. This schema asserts nothing about their shape, on "
         "purpose: doing so would not be generated from live registry data, it would be "
         "hand-copied prose, exactly the drift risk this whole artifact exists to avoid.",
         "spec/format.md 'Reserved hooks'; design rule 7"),
        ("label-binding-not-mechanical",
         "A claim's id/statement SHOULD name the same thing a reader would derive from its "
         "evidence's `ref` (format.md design rule 4b) — explicitly NOT mechanically checkable, "
         "reviewer work only.",
         "spec/format.md design rule 4b"),
    ]
    return [
        {"id": rid, "description": desc, "enforced_by": enforcer}
        for rid, desc, enforcer in sorted(rules, key=lambda r: r[0])
    ]


# ---------------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------------

def build_schema() -> dict:
    header = (
        f"acceptance/0 manifest — JSON Schema (draft 2020-12), version {SCHEMA_VERSION}. "
        "GENERATED FILE: produced by `tools/emit_schema.py`; do not hand-edit — regenerate it "
        "instead (a hand-edit will fail the drift gate on the next `gates/run_all.sh` run). "
        "NAMING: this file ships as "
        f"'schema/{SCHEMA_FILENAME}' while spec/core.md is UNSTABLE-UNTIL-FROZEN "
        "(spec/format.md 'Stability: acceptance/0 is UNSTABLE-UNTIL-FROZEN'); at freeze it is "
        "renamed 'acceptance-0.1.0.schema.json' (the '-draft' suffix dropped, no other change) "
        "and a new '-draft' cycle, if any, starts under the next minor version. "
        "SHAPE vs SEMANTICS: this schema is shape-normative only — table/field presence, field "
        "types, and closed-vocabulary membership. It is NOT semantics-normative: every "
        "constraint spanning more than one field (coherence rules, binding equalities, band "
        "reachability, hash recomputation, weight-conditioned requiredness, phrase floors, "
        "filesystem checks) is deliberately absent from the structural keywords below and is "
        "instead named in `x-semantic-only-rules`, and in the affected field's own "
        "`description`. On any disagreement between this schema and spec/core.md or "
        "spec/format.md, the spec prose and tools/check_acceptance.py win; this schema has a "
        "bug — regenerate it after fixing tools/emit_schema.py, never hand-edit the JSON. "
        "Generated from tools/acceptance_grammar.py and tools/check_acceptance.py's live "
        "registries — every closed vocabulary below is imported, never copied, so this file "
        "cannot drift from the validator that actually enforces it. See spec/format.md 'The "
        "schema artifact' for the normative statement of this split."
    )
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://acceptance-format.example/schema/{SCHEMA_FILENAME}",
        "title": f"acceptance/0 manifest {SCHEMA_VERSION}",
        "description": header,
        "type": "object",
        "required": ["format", "subject", "spec", "coverage"],
        "properties": {
            "format": _build_format(),
            "subject": _build_subject(),
            "spec": _build_spec(),
            "coverage": _build_coverage(),
            "claim": _arr(
                _build_claim(),
                "[[claim]] entries. OPTIONAL as a key (a manifest may declare zero claims); when "
                "present, must be an array of tables ([[claim]] is a TOML array-of-tables).",
            ),
        },
        "x-semantic-only-rules": _build_semantic_rules(),
    }
    return schema


def emit_bytes() -> bytes:
    schema = build_schema()
    text = json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=True)
    return (text + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# --check mode: a minimal, dependency-free JSON Schema structural interpreter.
#
# Deliberately small: it understands exactly the keywords this project's own emitted schema
# uses — type, enum, minLength, minimum, pattern, properties, required, additionalProperties,
# items — and nothing that would require a conditional (allOf/if/then/oneOf/anyOf/not/const),
# because the schema this file emits never uses one (every conditional obligation is
# semantic-only; see build_schema's module docstring). Extend the keyword set here ONLY in
# lockstep with something the emitted schema actually needs, so the two never drift apart — the
# same discipline a sibling project's own minimal dependency-free JSON Schema interpreter
# documents for its own, larger keyword set (read as precedent for shape only).
# ---------------------------------------------------------------------------

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}


def _iter_errors(instance, schema: dict, path: str = "$") -> list[str]:
    errors: list[str] = []

    if "type" in schema:
        if not _TYPE_CHECKS[schema["type"]](instance):
            return [f"{path}: expected type {schema['type']!r}, got "
                    f"{type(instance).__name__} ({instance!r})"]

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']!r}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: length {len(instance)} < minLength {schema['minLength']}")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: {instance!r} does not match pattern {schema['pattern']!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance!r} < minimum {schema['minimum']!r}")

    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in instance:
                errors.extend(_iter_errors(instance[key], subschema, f"{path}.{key}"))
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required property {req!r}")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(instance) - set(properties))
            if extra:
                errors.append(f"{path}: additional properties not allowed: {extra}")

    if isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema is not None:
            for i, item in enumerate(instance):
                errors.extend(_iter_errors(item, item_schema, f"{path}[{i}]"))

    return errors


def check_document(doc: dict, schema: dict) -> list[str]:
    """Structural errors for `doc` (already-parsed TOML/JSON data) against `schema`. Empty list
    means the document satisfies every SHAPE constraint the schema states — it says nothing
    about the semantic-only rules in schema['x-semantic-only-rules']."""
    return _iter_errors(doc, schema)


def check_file(path: Path, schema: dict) -> list[str]:
    with open(path, "rb") as f:
        doc = tomllib.load(f)
    return check_document(doc, schema)


# ---------------------------------------------------------------------------
# --selftest
# ---------------------------------------------------------------------------

_GOOD_MINIMAL = """
[format]
id            = "acceptance/0"
shape         = "single-file"
spec_id       = "acceptance-format"
spec_sha      = "0000000000000000000000000000000000000000"
validator_sha = "0000000000000000000000000000000000000000"
generated_by  = "hand-authored"
generated_at  = "2026-08-27T00:00:00Z"
illustrative  = true

[subject]
name   = "example-lib"
kind   = "rust-crate"
commit = "0000000000000000000000000000000000000000"
dirty  = false

[spec]
path    = "SPEC.md"
version = "v1"

[coverage]
clauses_total = 1
claims_total  = 1

[[claim]]
id        = "A-001"
clause    = "S-1"
item      = "src/lib.rs::add"
statement = "add never panics"
band      = "A1"
status    = "gap"
"""

# RESERVED trust fields (format.md design rule 3), both spellings. The schema described these as
# "intentionally UNCONSTRAINED" while emitting `"type": "string"` for them, so a manifest carrying
# the calibrated NUMERIC value the live validator accepts was rejected by the schema generated
# from that same validator (cold review, 2026-08-28). A calibrated number and a tagged string must
# both validate structurally, because the validator asserts nothing about this field's type.
_RESERVED_TRUST_FIELD_CLAIM = """
[[claim.evidence]]
kind        = "unit-test"
family      = "dynamic"
ref         = "t"
result      = "pass"
tool        = "cargo@1.x"
record      = "evidence/t.log"
cases       = 1
calibration = "measured on the 2026-08 held-out set, see evidence/calibration.md"
alpha       = %s
"""

_GOOD_TRUST_NUMERIC = (
    _GOOD_MINIMAL.replace('status    = "gap"', 'status    = "evidenced"')
    + (_RESERVED_TRUST_FIELD_CLAIM % "0.05")
)
_GOOD_TRUST_STRING = (
    _GOOD_MINIMAL.replace('status    = "gap"', 'status    = "evidenced"')
    + (_RESERVED_TRUST_FIELD_CLAIM % '"0.05"')
)

_BROKEN_BAD_ENUM = _GOOD_MINIMAL.replace('band      = "A1"', 'band      = "Z9"')
_BROKEN_MISSING_REQUIRED = _GOOD_MINIMAL.replace('commit = "0000000000000000000000000000000000000000"\n', '')
_BROKEN_WRONG_TYPE = _GOOD_MINIMAL.replace("dirty  = false", "dirty  = \"false\"")
_BROKEN_BAD_PATTERN = _GOOD_MINIMAL.replace(
    'commit = "0000000000000000000000000000000000000000"', 'commit = "not-a-sha"'
)


# Positive-control for the common-subset assertion (rule A, ruled 2026-08-28): plant Python-only
# constructs and confirm `_assert_ecma_compatible` actually refuses each one, then confirm a clean
# common-subset pattern is accepted. Proves the assertion is not a silent no-op — the failure mode
# a schema-drift gate with no fixture of its own would have.
_ECMA_ASSERTION_CASES: list[tuple[str, str, bool]] = [
    ("planted '(?i:...)' inline-flag group", r"^(?i:bounded|unbounded)\b", False),
    (r"planted '\A' anchor", r"^\Afoo$", False),
    ("planted '(?P<...>' named group", r"(?P<x>foo)", False),
    ("clean common-subset pattern", r"^(?:bounded|unbounded)\b", True),
]


def _ecma_assertion_selftest() -> list[str]:
    failures: list[str] = []
    for name, pattern, expect_ok in _ECMA_ASSERTION_CASES:
        try:
            _assert_ecma_compatible(pattern, name)
            accepted = True
        except AssertionError:
            accepted = False
        if accepted != expect_ok:
            verb = "accept" if expect_ok else "REJECT"
            failures.append(
                f"ECMA-ASSERTION MISMATCH ({name}): expected to {verb} but did not "
                f"({'raised' if not accepted else 'did not raise'}), pattern={pattern!r}"
            )
    return failures


def _run_toml_case(name: str, toml_text: str, schema: dict, expect_ok: bool) -> str | None:
    doc = tomllib.loads(toml_text)
    errors = check_document(doc, schema)
    ok = not errors
    if ok == expect_ok:
        return None
    verb = "PASS" if expect_ok else "FAIL"
    return f"FIXTURE MISMATCH ({name}): expected structural {verb}, errors={errors!r}"


def selftest() -> int:
    schema = build_schema()
    failures: list[str] = []

    b1 = emit_bytes()
    b2 = emit_bytes()
    if b1 != b2:
        failures.append("DETERMINISM: two emissions in the same process produced different bytes")

    failures.extend(_ecma_assertion_selftest())

    cases = [
        ("good minimal manifest", _GOOD_MINIMAL, True),
        ("bad band enum value", _BROKEN_BAD_ENUM, False),
        ("missing required [subject].commit", _BROKEN_MISSING_REQUIRED, False),
        ("wrong type for [subject].dirty", _BROKEN_WRONG_TYPE, False),
        ("commit fails the 40-hex pattern", _BROKEN_BAD_PATTERN, False),
        ("RESERVED trust field carrying a calibrated NUMBER", _GOOD_TRUST_NUMERIC, True),
        ("RESERVED trust field carrying a string", _GOOD_TRUST_STRING, True),
    ]
    for name, text, expect_ok in cases:
        r = _run_toml_case(name, text, schema, expect_ok)
        if r:
            failures.append(r)

    # ...and the node itself, directly: "intentionally UNCONSTRAINED" must mean the emitted node
    # states no assertion keyword at all, not a type the description contradicts. Asserted on the
    # emitted schema rather than only through a document fixture, so a future builder that adds a
    # constraint is caught even if no fixture happens to exercise the shape it forbids.
    _ev_props = (
        schema["properties"]["claim"]["items"]["properties"]["evidence"]["items"]["properties"]
    )
    for _tf in ("alpha", "beta", "lr"):
        _node = _ev_props[_tf]
        _keywords = sorted(set(_node) - {"description"})
        if _keywords:
            failures.append(
                f"RESERVED trust field {_tf!r} is described as UNCONSTRAINED but its emitted "
                f"node carries assertion keyword(s) {_keywords} — the schema and its own "
                f"description disagree about the same field"
            )

    for example in ("minimal.acceptance.toml", "rs-verified-der/acceptance.toml"):
        path = Path(__file__).resolve().parent.parent / "examples" / example
        errors = check_file(path, schema)
        if errors:
            failures.append(f"shipped example {example} FAILED structural check: {errors!r}")

    for f in failures:
        print(f"FAIL: {f}")
    if failures:
        print(f"SELFTEST FAIL: {len(failures)} failure(s)")
        return 1
    print(f"SELFTEST PASS: {len(cases)} embedded fixtures, {len(_ECMA_ASSERTION_CASES)} "
          f"common-subset assertion cases, 2 shipped examples, determinism ok")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if not argv:
        sys.stdout.buffer.write(emit_bytes())
        return 0
    if argv[0] == "--selftest":
        return selftest()
    if argv[0] == "--check":
        files = argv[1:]
        if not files:
            print("usage: emit_schema.py --check FILE [FILE...]", file=sys.stderr)
            return 2
        schema = build_schema()
        any_fail = False
        for f in files:
            path = Path(f)
            try:
                errors = check_file(path, schema)
            except tomllib.TOMLDecodeError as e:
                print(f"FAIL {f}: TOML parse error: {e}")
                any_fail = True
                continue
            if errors:
                any_fail = True
                print(f"FAIL {f}:")
                for e in errors:
                    print(f"  {e}")
            else:
                print(f"PASS {f}")
        return 1 if any_fail else 0
    print(f"usage: emit_schema.py [--check FILE...] [--selftest]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
