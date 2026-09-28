#!/usr/bin/env python3
"""Class validator for acceptance/0: mechanisms, composition and dispatch.

The verification compatibility CLI is check_acceptance.py. Meanings declare
ladders/families/kinds and return additive Finding values from check(doc, ctx).
Exit codes: 0 passing (possibly scoped/prospective), 1 failure, 2 indeterminate.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
import tomllib
import acceptance_grammar as grammar
from pathlib import Path

# The rules that must mean the same thing in BOTH representations live in one module, imported
# by this checker and by check_ledger.py. An earlier round-3 probe found the reason: `out-of-scope`
# had drifted to two different rules, and the Markdown copy granted weight where this one
# refused it. See tools/acceptance_grammar.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from acceptance_grammar import (  # noqa: E402
    CLAUSE_SOURCES as _G_CLAUSE_SOURCES,
    CLAUSE_SOURCES_UNWEIGHTABLE,
    GRADES as _G_GRADES,
    STATUSES as _G_STATUSES,
    STATUSES_NO_CHECK,
    UNWEIGHTABLE_GRADES as _G_UNWEIGHTABLE_GRADES,
    is_iso_date,
    is_phrase as _is_phrase,
    strip_witness_metadata,
    status_grade_incoherence,
)

# --------------------------------------------------------------------------
# Registries (spec/evidence-types.md, spec/assurance-bands.md)
# --------------------------------------------------------------------------

# B12: `[format].profile`
# is REQUIRED at 0.3.0. The compatibility default that used to live here (`acceptance/verification`,
# a public 0.2 fallback) is REMOVED — a manifest omitting the field is a class ERROR naming it
# (`parse_profile` below), not a silently-assumed meaning. There is no `DEFAULT_PROFILE` constant
# any more; every manifest under `/0` states its own profile explicitly.

# F1 (2026-09-17): OPEN base registry, not a closed enum. `prospective-
# feature` is the base token added for "a proposed feature OF an existing tool/artifact, not
# itself built yet" (RFC-0015/export-json). [format].kind_registry (validated in check_format)
# is the declared extension mechanism — a manifest may name additional kinds there.
SUBJECT_KINDS = grammar.SUBJECT_KINDS
# F3 (2026-09-17): `commit` keeps its one original meaning (retrospective certified content,
# design rule 4); `mode` says which subject shape this manifest is, and REQUIRES the distinct
# `read_at_commit` field instead of overloading `commit` for a subject that has no certified
# content yet. Absent `mode` == "retrospective", exactly the pre-existing behavior.
SUBJECT_MODES = grammar.SUBJECT_MODES
# F2 (2026-09-17): [spec].version is free-form when the governing document is in-tree (the
# pre-existing, unconstrained behavior); "external" requires a self-describing digest naming the
# CLASS-level `normative-reference:` hash domain, kept independent of the protocol's own M11
# module (`protocol/tools/m11.py`) so the core format does not depend on the protocol layer.
SPEC_PROVENANCE_VALUES = {"in-tree", "external"}
# 0.1-DRAFT §7.3 (P4, ADOPTED 2026-08-25): `blocked` — the tool cannot reach the item at all,
# which demands a different action from a reader than "nobody has done it yet". This list was
# stale for a day: the spec adopted the status and the validator rejected every manifest that
# used it, so the TOML representation could not express what the Markdown one could.
STATUSES = _G_STATUSES

# 0.1-DRAFT §7.2 (P3, ADOPTED): an item that ranges over a second list. DECLARATIVE — a claim is
# a predicate row because it says `item_kind = "predicate"`, never because a checker read its
# prose and guessed.
ITEM_KIND_VALUES = {"item", "predicate"}
COVERED_FRACTION_RE = re.compile(r"^\s*(\d+)\s*(?:/|\s+of\s+)\s*(\d+)\s*$", re.IGNORECASE)
RESULTS = {"pass", "fail", "unsupported"}
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

# B21: the coverage-metric registry an evidence record's `coverage.metric` MUST be drawn from.
# Roughly DO-178C-inspired, weakest to strongest structural criterion, plus a fifth token for a
# fully deductive proof obligation. Declared open for a
# future addition (a new token is additive, never a breaking change to an existing record).
COVERAGE_METRICS = {"statement", "branch", "decision", "mcdc", "proof-obligation"}

UNIVERSAL_EVIDENCE_FIELDS = ["kind", "family", "ref", "result", "tool", "record"]
RESERVED_TRUST_FIELDS = ("alpha", "beta", "lr")

# The `control` block (assurance-bands.md rule 6 / evidence-types.md "Control block") is
# FAMILY-AGNOSTIC (corrected 2026-08-22): it is an optional sub-table any evidence record may
# carry — `family` on the record already says what was perturbed (kernel = mutated Lean theorem,
# bmc = mutated Kani harness, dynamic = cargo-mutants/stryker, mechanical = seeded-bad gate
# fixture) (illustrative; profile vocabulary); the control block itself carries
# {kind, expectation, observed, of_claim} and is orthogonal to family. Mirrors the engine's
# receipt 2.1.0 control block 1:1.
CONTROL_EXPECTATION_VALUES = {"red", "green", "sat"}

# 0.1-DRAFT.md §1: `grade` is a REQUIRED claim field (tightened 2026-08-25 from the pre-freeze
# OPTIONAL M6 tag) — the closed nine-token vocabulary. A missing or out-of-vocabulary grade is an
# error naming 0.1-DRAFT §1.
WEIGHT_VALUES = {"weighted", "unweighted"}
# 0.1-DRAFT §1: grades with no deciding machinery can never carry weight.
UNWEIGHTABLE_GRADES = _G_UNWEIGHTABLE_GRADES


def _is_weighted(claim: dict) -> bool:
    """0.1-DRAFT W1: weight is explicit and DEFAULTS TO ABSENT. A claim that does
    not claim weight is unweighted, and the format promises nothing about it --
    the format never vouches by silence."""
    return claim.get("weight") == "weighted"
CLAIM_GRADE_VALUES = _G_GRADES

# coverage-ledger.md §6: where the claim's clause text came from. "test-name" is self-referential
# (the clause and its evidence are the same artifact) — recorded, not forbidden, but warned on.
CLAUSE_SOURCE_VALUES = _G_CLAUSE_SOURCES

# coverage-ledger.md §3: the [claim.self_verify] sub-table's allowed keys — strict (new table, no
# legacy producers to tolerate unknown keys from).
# 0.1-DRAFT §4.1 (P2, adopted 2026-08-25): `watched_fail` names what was perturbed, what was
# observed, and when -- the witness that the recipe CAN report the claim false.
SELF_VERIFY_FIELDS = {"command", "expect", "precondition", "positive_control", "watched_fail",
                      "expect_stream"}
# 0.1-DRAFT §8.2: which stream `--execute` matches `expect` against. stdout by default.
EXPECT_STREAM_VALUES = {"stdout", "stderr", "combined"}

# coverage-ledger.md §5: [coverage].denominator — whether the item list is the complete clause set
# or a declared, honestly-scoped slice.
DENOMINATOR_VALUES = {"complete", "slice"}


class Reporter:
    """Collects ERROR/WARN lines for one file."""

    def __init__(self, path: str, strict_weight: bool = False):
        self.path = path
        self.errors: list[str] = []
        self.warnings: list[str] = []
        # 0.1-DRAFT §8.1: transitional weight refusals, keyed by claim context. A refused claim
        # is NOT counted weighted; the reasons are counted and itemised so the remediation
        # backlog stays visible instead of vanishing into a tier that promises nothing.
        self.strict_weight = strict_weight
        self.pending: dict[str, list[str]] = {}
        # Structured accessors mirror the
        # WEIGHT REFUSED / [spec].axis facts already reported above as prose, so a consumer (e.g.
        # `acceptance_protocol.claim_weight_grants`) can read the refusal directly instead of
        # pattern-matching this Reporter's error strings — a message-format drift here would
        # otherwise silently turn a refused/pending claim into a granted one downstream. Populated
        # alongside the existing rep.error()/rep.warn() calls; changes no existing message, no
        # existing attribute, and no control flow.
        self.weight_refused: set[str] = set()
        self.axis_blocked: bool = False

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def weight_pending(self, ctx: str, reason: str) -> None:
        self.pending.setdefault(ctx, []).append(reason)
        msg = f"{ctx}: WEIGHT REFUSED (transitional): {reason} (0.1-DRAFT §8.1)"
        if self.strict_weight:
            self.errors.append(msg)
        else:
            self.warnings.append(msg)

    def ok(self) -> bool:
        return not self.errors and not getattr(self, "unknowns", ())

    def lines(self) -> list[str]:
        out = [f"ERROR {self.path}: {m}" for m in self.errors]
        out += [f"WARN {self.path}: {m}" for m in self.warnings]
        return out


def _is_nonempty_str(v) -> bool:
    return isinstance(v, str) and len(v) > 0


def _check_field(rep: Reporter, ctx: str, container: dict, field: str, tag: str) -> None:
    if field not in container:
        rep.error(f"{ctx}: missing required field '{field}'")
        return
    v = container[field]
    if tag == "str-nonempty":
        if not _is_nonempty_str(v):
            rep.error(f"{ctx}: field '{field}' must be a nonempty string")
    elif tag == "str-any":
        if not isinstance(v, str):
            rep.error(f"{ctx}: field '{field}' must be a string")
    elif tag == "list":
        if not isinstance(v, list):
            rep.error(f"{ctx}: field '{field}' must be a list")
    elif tag == "int-pos":
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            rep.error(f"{ctx}: field '{field}' must be an integer >= 1")
    elif tag == "int-nonneg":
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            rep.error(f"{ctx}: field '{field}' must be an integer >= 0")
    else:  # pragma: no cover — internal registry bug
        rep.error(f"{ctx}: internal validator bug — unknown tag '{tag}' for '{field}'")


# --------------------------------------------------------------------------
# Section checks
# --------------------------------------------------------------------------

def check_format(rep: Reporter, doc: dict) -> None:
    fmt = doc.get("format")
    if not isinstance(fmt, dict):
        rep.error("[format] section missing")
        return
    if fmt.get("id") != "acceptance/0":
        rep.error(f"[format].id must be \"acceptance/0\", got {fmt.get('id')!r}")
    # F1 (2026-09-17): the declared kind-registry extension. OPTIONAL; absence changes nothing.
    if "kind_registry" in fmt:
        registry = fmt.get("kind_registry")
        if not isinstance(registry, list) or not all(_is_nonempty_str(x) for x in registry):
            rep.error("[format].kind_registry must be a list of nonempty strings")


def _kind_registry(doc: dict) -> set[str]:
    fmt = doc.get("format")
    registry = fmt.get("kind_registry") if isinstance(fmt, dict) else None
    if isinstance(registry, list) and all(_is_nonempty_str(x) for x in registry):
        return set(registry)
    return set()


def _binding_admitted_kinds(doc: dict) -> set[str]:
    """B14: kinds admitted by whichever binding [format].profile names, read doc-only (no
    module import) from that binding's `admits = [...]` TOML block. Generic mechanism: it
    consults whatever binding path a manifest declares, if any, and names no binding itself —
    a binding-specific token (e.g. a language's kind name) becomes recognizable at the Class
    layer only because ITS OWN binding doc says so, never because core lists it."""
    fmt = doc.get("format")
    profile = fmt.get("profile") if isinstance(fmt, dict) else None
    if not isinstance(profile, str):
        return set()
    pieces = profile.split("/")
    if len(pieces) < 3 or pieces[0] != "acceptance":
        return set()
    binding_parts = pieces[2:]
    admitted: set[str] = set()
    for i in range(1, len(binding_parts) + 1):
        docpath = BINDING_DOC_ROOT / Path(*binding_parts[:i]).with_suffix(".md")
        try:
            text = docpath.read_text()
        except OSError:
            continue
        for block in re.findall(r"```toml\s*\n(.*?)```", text, re.S):
            try:
                data = tomllib.loads(block)
            except (tomllib.TOMLDecodeError, ValueError):
                continue
            admits = data.get("admits")
            if isinstance(admits, list):
                admitted.update(x for x in admits if isinstance(x, str))
    return admitted


def check_subject(rep: Reporter, doc: dict) -> None:
    subj = doc.get("subject")
    if not isinstance(subj, dict):
        rep.error("[subject] section missing")
        return
    if not _is_nonempty_str(subj.get("name")):
        rep.error("[subject].name must be a nonempty string")
    kind = subj.get("kind")
    allowed_kinds = SUBJECT_KINDS | _kind_registry(doc) | _binding_admitted_kinds(doc)
    if kind not in allowed_kinds:
        rep.error(
            f"[subject].kind must be one of {sorted(SUBJECT_KINDS)} (base registry) or a kind "
            f"declared in [format].kind_registry {sorted(_kind_registry(doc))}, or a kind the "
            f"declared binding admits (B14), got {kind!r} (F1, 2026-09-17)"
        )
    check_subject_locator(rep, subj)


def is_transitional_conformance(rep):
    """Only the explicitly declared conformance 0.1.0-draft transition is advisory."""
    fmt = getattr(rep, "doc", {}).get("format", {})
    return (getattr(rep, "meaning_name", None) == "conformance"
            and fmt.get("profile_version", fmt.get("version")) == "0.1.0-draft")


def check_spec(rep: Reporter, doc: dict, any_weighted: bool = False) -> None:
    spec = doc.get("spec")
    if not isinstance(spec, dict):
        rep.error("[spec] section missing")
        return
    if not _is_nonempty_str(spec.get("path")):
        rep.error("[spec].path must be a nonempty string")
    if not _is_nonempty_str(spec.get("version")):
        rep.error("[spec].version must be a nonempty string")

    # F2 (2026-09-17): the CLASS-level `normative-reference:` hash domain.
    # OPTIONAL, DEFAULTS TO "in-tree" — full backward compatibility with every manifest that
    # predates this field. "external" (the spec/format.md is not part of the subject's own
    # certified tree — an RFC, a not-yet-built subject's own design doc) requires `version` to
    # be a real digest, not a bare tag naming nothing checkable.
    provenance = spec.get("provenance", "in-tree")
    if provenance not in SPEC_PROVENANCE_VALUES:
        rep.error(
            f"[spec].provenance must be one of {sorted(SPEC_PROVENANCE_VALUES)}, "
            f"got {provenance!r} (F2)"
        )
    elif provenance == "external":
        version = spec.get("version")
        if not _wire(version, "normative-reference:"):
            rep.error(
                "[spec].version must be a "
                "'normative-reference:sha-512:<128-hex>' digest when [spec].provenance = "
                f"\"external\" (F2, 2026-09-17), got {version!r}"
            )

    if _is_nonempty_str(spec.get("path")) and hasattr(rep, "context"):
        legacy = is_transitional_conformance(rep)
        _read_document(rep, spec["path"], "spec.path", legacy=legacy,
                       domain="normative-reference:" if provenance == "external" else None,
                       expected=spec.get("version"))

    # 0.1-DRAFT.md §6: [spec].axis is REQUIRED — a prose statement of what the item list
    # enumerates (tightened 2026-08-25 from the pre-freeze OPTIONAL field). [spec].external
    # (normative references not in the tree) stays optional.
    # 0.1-DRAFT W2.4: axis is required only to EARN WEIGHT. A manifest with no
    # weighted claims may omit it -- nothing is being vouched for.
    if any_weighted and not _is_nonempty_str(spec.get("axis")):
        rep.error(
            "WEIGHT REFUSED: [spec].axis must be a nonempty string when any claim "
            "claims weight (0.1-DRAFT §6/W2)"
        )
        rep.axis_blocked = True
    if "external" in spec:
        external = spec.get("external")
        if not isinstance(external, list) or not all(_is_nonempty_str(x) for x in external):
            rep.error("[spec].external must be a list of nonempty strings")


def check_coverage(rep: Reporter, doc: dict, claims: list) -> None:
    cov = doc.get("coverage")
    if not isinstance(cov, dict):
        rep.error("[coverage] section missing")
        return
    ct = cov.get("clauses_total")
    if isinstance(ct, bool) or not isinstance(ct, int) or ct < 1:
        rep.error(f"[coverage].clauses_total must be an integer >= 1, got {ct!r}")
    claims_total = cov.get("claims_total")
    if isinstance(claims_total, bool) or not isinstance(claims_total, int):
        rep.error(f"[coverage].claims_total must be an integer, got {claims_total!r}")
    elif claims_total != len(claims):
        rep.error(
            f"[coverage].claims_total ({claims_total}) does not match actual number "
            f"of [[claim]] entries ({len(claims)})"
        )

    clause_ids = {str(c.get("clause")) for c in claims if isinstance(c, dict) and c.get("clause") is not None}
    if isinstance(ct, int) and ct > len(clause_ids) and cov.get("denominator", "complete") != "slice":
        legacy = is_transitional_conformance(rep)
        (rep.warn if legacy else rep.error)("B11: " + ("legacy " if legacy else "") + "zero-claim clauses require denominator = slice")

    # CLAIM-CLASSES-AWAITING-WEIGHT.md C1: OPTIONAL denominator — parseable and shape-checked, but its meaning
    # ("what makes a slice boundary legitimate") is NOT frozen, so its presence is EXPERIMENTAL,
    # not silently accepted. "slice" requires a nonempty slice_note so the omission-detection
    # guarantee stays honest about what it's scoped to — that shape rule IS enforced even though
    # the semantics aren't.
    denominator = cov.get("denominator")
    if denominator is not None:
        if denominator not in DENOMINATOR_VALUES:
            rep.error(
                f"[coverage].denominator must be one of {sorted(DENOMINATOR_VALUES)}, "
                f"got {denominator!r}"
            )
        else:
            rep.warn(
                f"[coverage].denominator = {denominator!r} is EXPERIMENTAL "
                f"(CLAIM-CLASSES-AWAITING-WEIGHT.md C1) — denominator/slice semantics are not yet frozen; "
                f"validated for shape only"
            )
            if denominator == "slice" and not _is_nonempty_str(cov.get("slice_note")):
                rep.error(
                    "[coverage].denominator = 'slice' requires a nonempty 'slice_note' "
                    "(CLAIM-CLASSES-AWAITING-WEIGHT.md C1)"
                )


def check_evidence_record(rep: Reporter, ctx: str, ev: dict, base_dir: Path, strict: bool) -> None:
    # universal fields (result is an enum, checked separately below)
    for f in ("kind", "family", "ref", "tool", "record"):
        if not _is_nonempty_str(ev.get(f)):
            rep.error(f"{ctx}: universal field '{f}' must be a nonempty string")

    result = ev.get("result")
    if result not in RESULTS:
        rep.error(f"{ctx}: result must be one of {sorted(RESULTS)}, got {result!r}")

    kind = ev.get("kind")
    reg = CLASS_KINDS.get(kind, getattr(rep, "kinds", {}).get(kind))
    if reg is None and not getattr(rep, "declarations_unknown", False):
        rep.error(f"{ctx}: unknown evidence kind {kind!r} (not in the registry — evidence-types.md)")
    elif reg is not None:
        expected_family = reg["family"]
        if ev.get("family") != expected_family:
            rep.error(
                f"{ctx}: kind/family mismatch — kind {kind!r} requires family "
                f"{expected_family!r}, got {ev.get('family')!r}"
            )
        if reg.get("warn_reserved"):
            rep.warn(f"{ctx}: reserved kind — tool not adopted ({kind})")
        for field, tag in reg.get("extra", {f: "str-nonempty" for f in reg.get("extra_required", [])}).items():
            _check_field(rep, ctx, ev, field, tag)

    # the `control` block (assurance-bands.md rule 6 / evidence-types.md "Control block") is
    # family-agnostic — ANY evidence record MAY carry one, regardless of its own kind/family
    # (kernel = mutated Lean theorem, bmc = mutated Kani harness, dynamic = cargo-mutants/stryker,
    # mechanical = seeded-bad gate fixture) (illustrative; profile vocabulary); the family lives
    # on the record, not the control.
    control = ev.get("control")
    if control is not None:
        if not isinstance(control, dict):
            rep.error(f"{ctx}: 'control' must be a table (kind/expectation/observed/of_claim)")
        else:
            cexp = control.get("expectation")
            if cexp not in CONTROL_EXPECTATION_VALUES:
                rep.error(
                    f"{ctx}: control.expectation must be one of "
                    f"{sorted(CONTROL_EXPECTATION_VALUES)}, got {cexp!r}"
                )
            if not _is_nonempty_str(control.get("observed")):
                rep.error(f"{ctx}: control.observed must be a nonempty string")
            if not _is_nonempty_str(control.get("of_claim")):
                rep.error(f"{ctx}: control.of_claim must be a nonempty string")

    # optional mutation-testing data fields (evidence-types.md "Control block"): DATA and GAPS,
    # never a score, and not tied to any particular kind — a dynamic mutation-testing record
    # (cargo-mutants/stryker) (illustrative; profile vocabulary) is the usual carrier, but
    # nothing enforces that narrowly here.
    for field, tag in (("mutants_total", "int-pos"), ("mutants_caught", "int-nonneg")):
        if field in ev:
            _check_field(rep, ctx, ev, field, tag)

    check_code_identity_shape(rep, ctx, ev)
    check_evidence_assurance_shape(rep, ctx, ev)

    if "mutants_caught" in ev and result == "pass":
        caught = ev.get("mutants_caught")
        if isinstance(caught, int) and not isinstance(caught, bool) and caught < 1:
            rep.error(
                f"{ctx}: result='pass' but mutants_caught={caught} — a mutation-testing "
                f"record that passes must show >=1 observed-red mutant (assurance-bands.md "
                f"rule 6)"
            )

    # reserved trust fields (format.md rule 3)
    for tf in RESERVED_TRUST_FIELDS:
        if tf in ev:
            cal = ev.get("calibration")
            if not _is_nonempty_str(cal):
                rep.error(
                    f"{ctx}: trust field '{tf}' present without a nonempty 'calibration' "
                    f"field — trust numbers without calibration are banned (format.md rule 3)"
                )


def check_code_identity_shape(rep: Reporter, ctx: str, ev: dict) -> None:
    """B20: typed toolchain identity, build-input identity and captured_at_commit shape.
    Digest recomputation for build_inputs is a separate concern (check_build_input_hashes) —
    this function is shape-only, generic words only, and names no binding or ecosystem."""
    toolchain = ev.get("toolchain")
    if toolchain is not None:
        if not isinstance(toolchain, list) or not toolchain:
            rep.error(f"{ctx}: toolchain must be a nonempty list of tables when present (B20)")
        else:
            for i, entry in enumerate(toolchain):
                tctx = f"{ctx}.toolchain[{i}]"
                if not isinstance(entry, dict):
                    rep.error(f"{tctx}: must be a table (B20)")
                    continue
                if not _is_nonempty_str(entry.get("name")):
                    rep.error(f"{tctx}: name must be a nonempty string (B20)")
                if "version" in entry and not _is_nonempty_str(entry.get("version")):
                    rep.error(f"{tctx}: version must be a nonempty string when present (B20)")
                if "commit" in entry:
                    commit = entry.get("commit")
                    if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
                        rep.error(f"{tctx}: commit must be 40 lowercase hex characters when present (B20)")
                if "digest" in entry and not _wire(entry.get("digest"), "artifact:"):
                    rep.error(f"{tctx}: digest must be an 'artifact:sha-512:<128-hex>' wire digest when present (B20)")
                if "commit" not in entry and "digest" not in entry:
                    rep.error(f"{tctx}: at least one of commit or digest is required (B20)")

    build_inputs = ev.get("build_inputs")
    if build_inputs is not None:
        if not isinstance(build_inputs, list) or not build_inputs:
            rep.error(f"{ctx}: build_inputs must be a nonempty list of tables when present (B20)")
        else:
            for i, entry in enumerate(build_inputs):
                bctx = f"{ctx}.build_inputs[{i}]"
                if not isinstance(entry, dict):
                    rep.error(f"{bctx}: must be a table (B20)")
                    continue
                if not _is_nonempty_str(entry.get("path")):
                    rep.error(f"{bctx}: path must be a nonempty string (B20)")
                if not _wire(entry.get("digest"), "artifact:"):
                    rep.error(f"{bctx}: digest must be an 'artifact:sha-512:<128-hex>' wire digest (B20)")

    captured = ev.get("captured_at_commit")
    if captured is not None and (not isinstance(captured, str) or not COMMIT_RE.fullmatch(captured)):
        rep.error(f"{ctx}: captured_at_commit must be 40 lowercase hex characters when present (B20)")


def check_evidence_assurance_shape(rep: Reporter, ctx: str, ev: dict) -> None:
    """B21: evidence-only assurance metadata -- a structural/proof-coverage metric and a declared
    tool-qualification note. DECLARED ONLY: 0.3 checks shape and registry membership, never the
    truth of the number or the qualification argument (class design rule, core.md §2 rule "nothing
    about truth"). Generic, profile-blind, names no binding or ecosystem."""
    coverage = ev.get("coverage")
    if coverage is not None:
        if not isinstance(coverage, dict):
            rep.error(f"{ctx}: coverage must be a table when present (B21)")
        else:
            metric = coverage.get("metric")
            if metric not in COVERAGE_METRICS:
                rep.error(f"{ctx}: coverage.metric must be one of {sorted(COVERAGE_METRICS)}, got {metric!r} (B21)")
            value = coverage.get("value")
            # bool is a subclass of int in Python; exclude it explicitly (the same guard B4/B20
            # use for int fields elsewhere in this module).
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not (0 <= value <= 1):
                rep.error(f"{ctx}: coverage.value must be a number in [0, 1] (a fraction, never a percent — core.md B7), got {value!r} (B21)")
            if "of" in coverage and not _is_nonempty_str(coverage.get("of")):
                rep.error(f"{ctx}: coverage.of, if present, must be a nonempty string (B21)")
            extra = set(coverage) - {"metric", "value", "of"}
            if extra:
                rep.error(f"{ctx}: coverage carries unknown field(s) {sorted(extra)} (B21)")

    tool_qualification = ev.get("tool_qualification")
    if tool_qualification is not None:
        if not isinstance(tool_qualification, dict):
            rep.error(f"{ctx}: tool_qualification must be a table when present (B21)")
        else:
            if not _is_nonempty_str(tool_qualification.get("basis")):
                rep.error(f"{ctx}: tool_qualification.basis must be a nonempty string (B21)")
            if "level" in tool_qualification and not _is_nonempty_str(tool_qualification.get("level")):
                rep.error(f"{ctx}: tool_qualification.level, if present, must be a nonempty string (B21)")
            extra = set(tool_qualification) - {"level", "basis"}
            if extra:
                rep.error(f"{ctx}: tool_qualification carries unknown field(s) {sorted(extra)} (B21)")


def check_build_input_hashes(rep: Reporter, doc: dict) -> None:
    """B20: recompute every resolvable build_inputs[].digest over the pointed file's bytes, on
    every validation path — the same B6/B16 unresolved-native-pointer treatment as
    check_record_hashes (WARNING, error under --strict); a mismatch is a FAIL."""
    for claim in doc.get("claim", []) if isinstance(doc.get("claim"), list) else []:
        if not isinstance(claim, dict): continue
        for idx, ev in enumerate(claim.get("evidence", []) if isinstance(claim.get("evidence", []), list) else []):
            if not isinstance(ev, dict): continue
            build_inputs = ev.get("build_inputs")
            if not isinstance(build_inputs, list): continue
            for bidx, entry in enumerate(build_inputs):
                if not isinstance(entry, dict): continue
                label = f"claim {claim.get('id')!r} evidence[{idx}] build_inputs[{bidx}]"
                path, digest = entry.get("path"), entry.get("digest")
                if not _is_nonempty_str(path) or not _wire(digest, "artifact:"):
                    continue  # shape already reported by check_code_identity_shape
                target = _resolve_pointer(rep, path, label)
                if target is None: continue
                try:
                    raw = target.read_bytes()
                except OSError:
                    message = f"{label}: build-input pointer does not exist: {path} (or is unreadable)"
                    (rep.error if rep.context.strict else rep.warn)(message)
                    continue
                if hashdomains.digest("artifact:", raw) != digest:
                    rep.error(f"B20: {label}: build-input digest differs from declared artifact:sha-512 hash")


def check_control_of_claim_mismatch(
    rep: Reporter, ctx: str, claim: dict, evidence: list[dict]
) -> None:
    """assurance-bands.md rule 6: a control attests only the claim its of_claim names. Runs for
    EVERY claim regardless of status (evidenced/partial/gap/parked) — matching
    check_dangling_of_claim's all-status coverage (F4, tightened 2026-08-22: this used to run
    only for status=="evidenced", inside _check_control_gate, so a mis-pointed control on a
    `partial` claim went unnoticed)."""
    cid = claim.get("id")
    for e in evidence:
        if not isinstance(e, dict):
            # already reported at the per-entry "must be a table" check (check_claims); a
            # non-table evidence entry has no .get() to call — matches check_dangling_of_claim's
            # identical guard so a malformed entry is skipped here, not a crash.
            continue
        control = e.get("control")
        if isinstance(control, dict):
            of_claim = control.get("of_claim")
            if _is_nonempty_str(of_claim) and of_claim != cid:
                rep.error(
                    f"{ctx}: control block (kind {control.get('kind')!r}) has of_claim "
                    f"{of_claim!r}, which does not name this claim ({cid!r}) — a control "
                    f"attests only the claim its of_claim names (assurance-bands.md rule 6)"
                )








def check_watched_fail_block(rep: Reporter, ctx: str, sv: dict) -> None:
    """0.1-DRAFT §4.1, structured (round 2, finding 2). `watched_fail` was any nonempty
    string, so `watched_fail = "x"` satisfied W2.5 and the claim counted weighted — the exact
    "no weighted-tier obligation may be satisfied by a phrase match" rule the Markdown side had
    already been brought to. The TOML form is a table, matching the `[claim.evidence.control]`
    precedent, and it BINDS to this claim's own recipe through `of_command`."""
    wf = sv.get("watched_fail")
    if wf is None:
        return
    if isinstance(wf, str):
        rep.error(
            f"{ctx}: self_verify.watched_fail must be a [claim.self_verify.watched_fail] TABLE "
            f"with of_command / perturbed / observed / date, not a free-text string — a phrase "
            f"is not a witness (0.1-DRAFT §4.1). Got {wf!r}"
        )
        return
    if not isinstance(wf, dict):
        rep.error(f"{ctx}: [claim.self_verify.watched_fail] must be a table")
        return
    allowed = {"of_command", "perturbed", "observed", "date"}
    for k in wf:
        if k not in allowed:
            rep.error(
                f"{ctx}: watched_fail has unknown field {k!r} (allowed: {sorted(allowed)})"
            )
    for k in sorted(allowed):
        if k not in wf:
            rep.error(
                f"{ctx}: [claim.self_verify.watched_fail] requires {k!r} (0.1-DRAFT §4.1)"
            )
        elif not isinstance(wf[k], str):
            rep.error(f"{ctx}: watched_fail.{k} must be a string")

    for k in ("perturbed", "observed"):
        # Stripped for the same reason as the Markdown side: the date annotation's own tokens
        # must not be what satisfies the floor. `date` is a separate field here, so this only
        # matters when a producer writes the annotation into the description as well -- but the
        # two representations must apply the floor to the same text, or the parity is nominal.
        if isinstance(wf.get(k), str) and not _is_phrase(strip_witness_metadata(wf[k])):
            rep.error(
                f"{ctx}: watched_fail.{k} must state what was {k} — a single token is not a "
                f"statement (0.1-DRAFT §4.1), got {wf[k]!r}"
            )
    date = wf.get("date")
    if isinstance(date, str) and not is_iso_date(date):
        rep.error(
            f"{ctx}: watched_fail.date must be an ISO date (YYYY-MM-DD) — 'when' is part of the "
            f"witness because a recipe watched to fail last year may not discriminate today "
            f"(0.1-DRAFT §4.1), got {date!r}"
        )
    # The binding. In a Markdown rendering the witness names the recipe it falsifies; here the
    # equivalent is that the perturbation was watched against THIS row's command, not a
    # neighbouring one it was copied from.
    of_cmd = wf.get("of_command")
    cmd = sv.get("command")
    if isinstance(of_cmd, str) and isinstance(cmd, str):
        # Whitespace-normalized so a re-wrapped copy still binds. NOTHING ELSE is normalized:
        # quoting stays literal, because `--harness a` and `--harness "a"` can be different
        # commands and a comparison that shrugged at the difference would not be a binding.
        if " ".join(of_cmd.split()) != " ".join(cmd.split()):
            rep.error(
                f"{ctx}: watched_fail.of_command does not equal this claim's own "
                f"self_verify.command — a control over a different check witnesses nothing "
                f"about this one (0.1-DRAFT §4.1; the of_claim rule). of_command={of_cmd!r}, "
                f"command={cmd!r}"
            )
    elif isinstance(of_cmd, str) and cmd is None:
        rep.error(
            f"{ctx}: watched_fail.of_command names a command, but this claim's self_verify "
            f"declares none to bind it to (0.1-DRAFT §4.1)"
        )


def _watched_fail_block_is_valid(sv: dict) -> bool:
    """True only for a fully-formed witness table. Used by the W2.5 gate so that a MALFORMED
    witness does not satisfy the requirement it fails to meet."""
    wf = sv.get("watched_fail")
    if not isinstance(wf, dict):
        return False
    if set(wf) != {"of_command", "perturbed", "observed", "date"}:
        return False
    if not all(isinstance(wf[k], str) for k in wf):
        return False
    if not (_is_phrase(strip_witness_metadata(wf["perturbed"]))
            and _is_phrase(strip_witness_metadata(wf["observed"]))):
        return False
    if not is_iso_date(wf["date"]):
        return False
    cmd = sv.get("command")
    if not isinstance(cmd, str):
        return False
    return " ".join(wf["of_command"].split()) == " ".join(cmd.split())




def check_self_verify(rep: Reporter, ctx: str, claim: dict) -> None:
    """Validate recipe and watched-fail shape; grade requirements belong to the meaning."""
    sv = claim.get("self_verify")

    if sv is None:
        return
    if not isinstance(sv, dict):
        rep.error(f"{ctx}: [claim.self_verify] must be a table")
        return

    # this table is new (no legacy producers to tolerate typos from) — strict on unknown keys.
    for k in sv:
        if k not in SELF_VERIFY_FIELDS:
            rep.error(f"{ctx}: self_verify has unknown field {k!r} (allowed: {sorted(SELF_VERIFY_FIELDS)})")

    # Every self_verify field is a string EXCEPT `watched_fail`, which is a table (§4.1,
    # structured 2026-08-25) and is validated by check_watched_fail_block below.
    for k in SELF_VERIFY_FIELDS - {"watched_fail"}:
        if k in sv and not isinstance(sv[k], str):
            rep.error(f"{ctx}: self_verify.{k} must be a string")

    stream = sv.get("expect_stream")
    if stream is not None and stream not in EXPECT_STREAM_VALUES:
        rep.error(
            f"{ctx}: self_verify.expect_stream must be one of "
            f"{sorted(EXPECT_STREAM_VALUES)} (or omitted, meaning 'stdout'), got {stream!r} "
            f"(0.1-DRAFT §8.2)"
        )

    check_watched_fail_block(rep, ctx, sv)

    # 0.1-DRAFT.md §3 rule 2: `command` present => `expect` is required (a harness name alone is
    # not a recipe; "what green means" has to be written).
    if _is_nonempty_str(sv.get("command")) and not _is_nonempty_str(sv.get("expect")):
        rep.error(
            f"{ctx}: self_verify.command is present, so self_verify.expect is required and "
            f"must be nonempty (0.1-DRAFT §3)"
        )







def check_claims(rep: Reporter, doc: dict, base_dir: Path, strict: bool) -> list[dict]:
    raw_claims = doc.get("claim")
    if raw_claims is None:
        claims = []
    elif isinstance(raw_claims, list):
        claims = raw_claims
    else:
        rep.error("[[claim]] entries must form an array of tables")
        claims = []

    seen_ids: set[str] = set()
    for idx, claim in enumerate(claims):
        ctx0 = f"claim[{idx}]"
        if not isinstance(claim, dict):
            rep.error(f"{ctx0}: must be a table")
            continue
        cid = claim.get("id")
        ctx = f"claim {cid!r}" if _is_nonempty_str(cid) else ctx0

        # 0.1-DRAFT §8.1 membership invariant. `weight-pending` is
        # defined as "claims weight, satisfies every rule that PREDATES the adoption, and lacks
        # only the newly-required machinery". A claim that ALSO breaks a pre-adoption rule is
        # refused outright, not pending — putting it on the backlog would file a broken row on a
        # work list whose whole meaning is "these were fine until the rules changed". The
        # Markdown checker has held this since 2026-08-25; the TOML one reported `FAIL 2 errors`
        # and `pending: 1` for the same row. So the pending decision is deferred to the END of
        # this claim's checks, and taken only if the claim raised no error of its own.
        errors_before = len(rep.errors)
        pending_reasons: list[str] = []

        for f in ("id", "clause", "item", "statement"):
            if not _is_nonempty_str(claim.get(f)):
                rep.error(f"{ctx}: field '{f}' must be a nonempty string")

        if _is_nonempty_str(cid):
            if cid in seen_ids:
                rep.error(f"{ctx}: duplicate claim id {cid!r} — ids must be unique within the file")
            seen_ids.add(cid)

        band = claim.get("band")
        check_band_mechanism(rep, claim)
        check_applicability(rep, claim)
        check_gaps(rep, claim)
        # 0.1-DRAFT.md §1/§2: `grade` is a REQUIRED claim field (tightened 2026-08-25 from the
        # pre-freeze OPTIONAL M6 tag) — the single largest break from the pre-freeze schema.
        grade = claim.get("grade")
        weight = claim.get("weight")
        if weight is not None and weight not in WEIGHT_VALUES:
            rep.error(
                f"{ctx}: weight must be one of {sorted(WEIGHT_VALUES)} (or omitted, "
                f"meaning unweighted), got {weight!r} (0.1-DRAFT W1)"
            )
        if _is_weighted(claim):
            if grade is None:
                rep.error(
                    f"{ctx}: WEIGHT REFUSED: a weighted claim requires 'grade' (0.1-DRAFT W2)"
                )
            elif grade in UNWEIGHTABLE_GRADES:
                rep.error(
                    f"{ctx}: WEIGHT REFUSED: grade {grade!r} has no deciding machinery and is "
                    f"never weight-eligible (0.1-DRAFT §1/W2)"
                )
            cs = claim.get("clause_source")
            if cs is None:
                # 0.1-DRAFT W2.3 (P1, ADOPTED 2026-08-25): a weighted claim must record where
                # its clause text came from. Absence is indistinguishable from the two values
                # reserved to mean unweightable, and W1's rule is that the format never vouches
                # by silence. Transitional per §8.1: refused into weight-pending, an ERROR under
                # --strict-weight. Held until the end of this claim (see errors_before).
                pending_reasons.append("clause_source not recorded (W2.3, P1)")
            # 0.1-DRAFT §4.1 / W2.5 (P2, ADOPTED 2026-08-25): a weighted recipe must carry a
            # witness that it CAN report the claim false. Applies to every grade that asserts a
            # check was performed; `out-of-scope` has no recipe and so has nothing to fail.
            if cs in CLAUSE_SOURCES_UNWEIGHTABLE:
                rep.error(
                    f"{ctx}: WEIGHT REFUSED: clause_source {cs!r} is reserved to mean unweightable "
                    f"by design -- a clause read off its own evidence cannot be falsified "
                    f"(0.1-DRAFT W2)"
                )
        if grade is not None and grade not in CLAIM_GRADE_VALUES:
            rep.error(
                f"{ctx}: grade must be one of {sorted(CLAIM_GRADE_VALUES)}, got {grade!r} "
                f"(0.1-DRAFT §1)"
            )

        # coverage-ledger.md §6: OPTIONAL clause_source — where the clause text came from.
        # "test-name" is self-referential (clause and evidence are the same artifact): recorded,
        # not forbidden, but MUST NOT pass silently — warned.
        clause_source = claim.get("clause_source")
        if clause_source is not None:
            if clause_source not in CLAUSE_SOURCE_VALUES:
                rep.error(
                    f"{ctx}: clause_source must be one of {sorted(CLAUSE_SOURCE_VALUES)} "
                    f"(or omitted), got {clause_source!r}"
                )
            elif clause_source == "test-name":
                rep.warn(
                    f"{ctx}: clause_source = 'test-name' is EXPERIMENTAL (CLAIM-CLASSES-AWAITING-WEIGHT.md "
                    f"C5) — the clause and its evidence are the same artifact, so the test can "
                    f"never fail the requirement"
                )

        if _is_weighted(claim):
            check_self_verify(rep, ctx, claim)
        else:
            shape = Reporter(rep.path)
            check_self_verify(shape, ctx, claim)
            for message in shape.errors:
                if is_transitional_conformance(rep): rep.warn("B13: legacy unweighted recipe shape: " + message)
                else: rep.error(message)
            rep.n_unweighted = getattr(rep, "n_unweighted", 0) + 1

        status = claim.get("status")
        if status not in STATUSES:
            rep.error(f"{ctx}: status must be one of {sorted(STATUSES)}, got {status!r}")

        if status == "parked" and not _is_nonempty_str(claim.get("parked_reason")):
            rep.error(f"{ctx}: status = 'parked' requires a nonempty 'parked_reason'")

        # 0.1-DRAFT §7.3 (P4, ADOPTED): `blocked` is an escalation, and the escalation is only
        # greppable if it names what blocks it.
        if status == "blocked" and not _is_nonempty_str(claim.get("blocked_by")):
            rep.error(
                f"{ctx}: status = 'blocked' requires a nonempty 'blocked_by' naming what blocks "
                f"it — without it an escalation reads as a backlog entry (0.1-DRAFT §7.3)"
            )

        # 0.1-DRAFT §7.1: status x grade coherence. ERROR on a claim that claims weight -- a
        # `gap`-status row carrying a weighted `contract` is the format vouching for a proof of
        # something the next field says is unproven. WARNING otherwise, because an unweighted
        # scoreboard legitimately records the grade a not-yet-started item WILL carry, which is
        # proposal P5 and is DEFERRED (§7.4). This rule must not adopt P5 sideways.
        if grade in CLAIM_GRADE_VALUES:
            msg = status_grade_incoherence(status, grade)
            if msg:
                if _is_weighted(claim):
                    rep.error(f"{ctx}: WEIGHT REFUSED: INCOHERENT: {msg}")
                else:
                    rep.warn(f"{ctx}: §7.1: {msg}")

        # 0.1-DRAFT §7.2 (P3, ADOPTED): a predicate item ranges over a second list, and its
        # honest status is a fraction. Declared, never inferred.
        item_kind = claim.get("item_kind")
        if item_kind is not None and item_kind not in ITEM_KIND_VALUES:
            rep.error(
                f"{ctx}: item_kind must be one of {sorted(ITEM_KIND_VALUES)} (or omitted, "
                f"meaning 'item'), got {item_kind!r} (0.1-DRAFT §7.2)"
            )
        elif item_kind == "predicate":
            over = claim.get("over")
            covered = claim.get("covered")
            problems: list[str] = []
            if not _is_nonempty_str(over):
                problems.append("'over' (what the predicate ranges over) is missing or empty")
            if not _is_nonempty_str(covered):
                problems.append("'covered' (numerator/denominator) is missing or empty")
            elif not COVERED_FRACTION_RE.match(covered):
                problems.append(f"'covered' must be a fraction, N/M or 'N of M', got {covered!r}")
            else:
                m = COVERED_FRACTION_RE.match(covered)
                n, d = int(m.group(1)), int(m.group(2))
                if d == 0:
                    problems.append("'covered' denominator is 0 — a predicate over nothing")
                elif n > d:
                    problems.append(f"'covered' numerator exceeds its denominator ({covered!r})")
            for p in problems:
                if _is_weighted(claim):
                    # §7.2: "A weighted predicate row that states no fraction is refused weight.
                    # *Some* is not a status."
                    rep.error(f"{ctx}: WEIGHT REFUSED: item_kind = 'predicate' — {p} "
                              f"(0.1-DRAFT §7.2)")
                else:
                    rep.warn(f"{ctx}: §7.2: item_kind = 'predicate' — {p}")
        elif claim.get("over") is not None or claim.get("covered") is not None:
            rep.warn(
                f"{ctx}: 'over'/'covered' are §7.2 predicate fields but item_kind is not "
                f"'predicate' — the fraction will be read by nothing"
            )

        evidence = claim.get("evidence")
        if evidence is None:
            evidence = []
        elif not isinstance(evidence, list):
            rep.error(f"{ctx}: [[claim.evidence]] must be an array of tables")
            evidence = []

        if status in STATUSES_NO_CHECK:
            if evidence:
                rep.error(f"{ctx}: status {status!r} must have NO evidence entries")
        elif status in ("evidenced", "partial"):
            if not evidence:
                rep.error(f"{ctx}: status {status!r} requires at least one evidence entry")

        for eidx, ev in enumerate(evidence):
            ectx = f"{ctx} evidence[{eidx}]"
            if not isinstance(ev, dict):
                rep.error(f"{ectx}: must be a table")
                continue
            check_evidence_record(rep, ectx, ev, base_dir, strict)
            check_family_mechanism(rep, ev, ectx)

        check_record_hashes(rep, {"claim": [claim]})
        check_build_input_hashes(rep, {"claim": [claim]})

        # a non-table [[claim.evidence]] entry is already reported above ("must be a table") --
        # every downstream consumer (control-mismatch, band-reachability) assumes each evidence
        # item is a dict and calls .get() on it without guarding, so it must see a filtered,
        # dict-only list, never the raw one (bug found via selftest coverage work, 2026-08-25:
        # an evidence array containing a bare string crashed validate() with AttributeError
        # instead of reporting a clean error).
        valid_evidence = [ev for ev in evidence if isinstance(ev, dict)]

        # F4 (tightened 2026-08-22): runs for EVERY status, not just "evidenced" — a `partial`
        # claim's mis-pointed control is just as much a band-overstatement-by-proxy risk as an
        # evidenced one's, and this check used to be reachable only via check_band_reachability,
        # which never ran for partial/gap/parked claims.
        check_control_of_claim_mismatch(rep, ctx, claim, valid_evidence)


        rep.claim_evaluations[claim.get("id", str(idx))] = "error" if len(rep.errors) > errors_before else "ok"
        if _is_weighted(claim):
            rep.weight_checks[ctx] = (claim, pending_reasons, len(rep.errors) > errors_before)

    # two-pass: `of_claim` pointers can only be judged against the FULL id set once every claim
    # has been walked once (assurance-bands.md rule 6 — a control pointing at a phantom claim).
    check_dangling_of_claim(rep, claims, seen_ids)

    return claims


def check_dangling_of_claim(rep: Reporter, claims: list[dict], all_ids: set[str]) -> None:
    """A `control.of_claim` that names a claim id absent from this manifest entirely is an
    error — distinct from (and in addition to) the "does not name THIS claim" mismatch already
    caught per-claim: that one fires when of_claim names a claim id that DOES exist elsewhere in
    the file; this one fires when of_claim names nothing at all (a phantom claim)."""
    for idx, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        cid = claim.get("id")
        ctx = f"claim {cid!r}" if _is_nonempty_str(cid) else f"claim[{idx}]"
        evidence = claim.get("evidence")
        if not isinstance(evidence, list):
            continue
        for eidx, ev in enumerate(evidence):
            if not isinstance(ev, dict):
                continue
            control = ev.get("control")
            if not isinstance(control, dict):
                continue
            of_claim = control.get("of_claim")
            if _is_nonempty_str(of_claim) and of_claim not in all_ids:
                rep.error(
                    f"{ctx} evidence[{eidx}]: control.of_claim {of_claim!r} does not match "
                    f"any claim id in this manifest — a control pointing at a phantom claim "
                    f"(assurance-bands.md rule 6)"
                )


# Profile-neutral mechanisms.
import copy
import importlib.util
import json
from dataclasses import dataclass
from types import SimpleNamespace
import hashdomains

CLASS_KINDS = {
    "human-review": {"family": "judgment", "extra": {"reviewer": "str-nonempty"}},
    "llm-review": {"family": "judgment", "extra": {"reviewer": "str-nonempty"}},
    "acceptance-claim": {"family": "reference", "extra": {"manifest": "str-nonempty", "manifest_hash": "str-nonempty", "claim": "str-nonempty", "records": "list"}},
}
MODULE_ROOT = Path(__file__).resolve().parent
BINDING_DOC_ROOT = MODULE_ROOT.parent / "profiles" / "bindings"


@dataclass(frozen=True)
class Finding:
    severity: str
    message: str
    claim_id: str | None = None


@dataclass(frozen=True)
class Context:
    path: Path
    root: Path | None
    strict: bool = False
    strict_weight: bool = False
    meaning_only: bool = False
    binding_only: bool = False
    stack: tuple[str, ...] = ()


def _wire(value, domain):
    try:
        return hashdomains.parse(value)[0] == domain
    except ValueError:
        return False


def check_subject_locator(rep, subj):
    mode = subj.get("mode", "retrospective")
    if mode not in SUBJECT_MODES:
        rep.error(f"[subject].mode must be one of {sorted(SUBJECT_MODES)}, got {mode!r} (F3)")
    if mode == "prospective":
        reads = [k for k in ("read_at_commit", "read_at_digest") if k in subj]
        if len(reads) != 1:
            rep.error("B1: [subject].read_at_commit is REQUIRED or read_at_digest (exactly one read-locator) when prospective")
    else:
        ids = [k for k in ("commit", "digest") if k in subj or k == "digest" and "components" in subj]
        if len(ids) != 1:
            rep.error("B1: retrospective subject requires exactly one certified identity; [subject].commit must be 40 lowercase hex chars or supply one typed locator")
        if "commit" in subj:
            if not isinstance(subj["commit"], str) or not COMMIT_RE.fullmatch(subj["commit"]):
                rep.error(f"[subject].commit must be 40 lowercase hex chars, got {subj['commit']!r}")
            if not isinstance(subj.get("dirty"), bool):
                rep.error(f"[subject].dirty must be a bool, got {subj.get('dirty')!r}")
        if "digest" in subj and not _wire(subj["digest"].rsplit(":", 1)[0] + ":" + subj["digest"].rsplit(":", 1)[-1].lower() if "components" in subj and isinstance(subj["digest"], str) else subj["digest"], "subject:"):
            rep.error("B1: subject digest must use subject:sha-512:<128-hex>")
        if "digest" in subj and "components" not in subj:
            rep.warn("B1: subject digest not recomputed")
        if "components" in subj:
            components = subj["components"]
            if not isinstance(components, list) or not components:
                rep.error("B1: components must be a nonempty array")
            else:
                names = set()
                for component in components:
                    if not isinstance(component, dict) or not isinstance(component.get("name"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", component["name"]):
                        rep.error("B1: component needs a name matching [a-z0-9][a-z0-9._-]* and typed locator")
                        continue
                    if component["name"] in names:
                        rep.error("B1: duplicate component name")
                    names.add(component["name"])
                    if "components" in component or component.get("mode", "retrospective") != "retrospective":
                        rep.error("B1: components require a git-revision or content-digest locator")
                    else:
                        check_subject_locator(rep, component)
                if all(isinstance(c, dict) and isinstance(c.get("name"), str) and ("commit" in c or "digest" in c) for c in components):
                    lines = [c["name"] + "=" + ("git-revision:" + str(c["commit"]) if "commit" in c else "content-digest:" + str(c["digest"])) for c in sorted(components, key=lambda c: c["name"].encode("utf-8"))]
                    rep.subject_digest = hashdomains.digest("subject:", ("\n".join(lines) + "\n").encode("utf-8"))
                    if "digest" not in subj:
                        rep.error("B1: components require the aggregate subject.digest")
                    elif not isinstance(subj["digest"], str) or subj["digest"].lower() != rep.subject_digest:
                        rep.error("B1: components digest differs from canonical serialization")

    for key in ("read_at_commit", "read_at_digest"):
        if key not in subj:
            continue
        value = subj[key]
        valid = value == "unpinned" or (isinstance(value, str) and bool(COMMIT_RE.fullmatch(value)) if key == "read_at_commit" else _wire(value, "subject:"))
        if not valid:
            rep.error(f"B1: [subject].{key} must be 40 lowercase hex chars or 'unpinned'" if key == "read_at_commit" else "B1: read_at_digest must use subject:sha-512 or 'unpinned'")


def _rank(tier):
    # T1 is strongest. Numeric order is the opposite of epistemic strength.
    return grammar.TIERS.index(tier) if tier in grammar.TIERS else None


def check_family_mechanism(rep, ev, ctx):
    family = ev.get("family")
    if getattr(rep, "declarations_unknown", False): return
    if family == "reference":
        return  # ceiling is derived after source admission (B8)
    families = getattr(rep, "families", {})
    if family not in families:
        rep.error(f"B3: {ctx}: undeclared evidence family {family!r}")
        return
    if "epistemic_tier" in ev:
        tier, ceiling = _rank(ev["epistemic_tier"]), _rank(families[family])
        if tier is None or ceiling is None or tier < ceiling:
            rep.error(f"B3: {ctx}: epistemic_tier above family ceiling {families[family]}")


def control_free_ceiling(rep, claim):
    ladder = rep.ladder
    if not ladder:
        return None
    tokens, ceilings = ladder["tokens"], ladder.get("control_free_ceiling", {})
    values = [ceilings.get("default", tokens[0])]
    for e in claim.get("evidence", []) if isinstance(claim.get("evidence", []), list) else []:
        if isinstance(e, dict) and e.get("result") == "pass":
            values.append(ceilings.get(e.get("kind"), ceilings.get(e.get("family"), tokens[0])))
    return max((tokens.index(v) for v in values if v in tokens), default=0)


def check_band_mechanism(rep, claim):
    if getattr(rep, "declarations_unknown", False): return
    ladder = getattr(rep, "ladder", None)
    band = claim.get("band")
    if not ladder:
        if "band" in claim:
            rep.error("B2: band forbidden under a meaning with no ladder")
        return
    tokens = ladder["tokens"]
    if band not in tokens:
        if band is None:
            if claim.get("status") == "not-applicable": return
            if not re.search(rf"\b{re.escape(tokens[0])}\b", str(claim.get("statement", ""))):
                rep.error(f"B2: band-less claim is treated at ladder floor {tokens[0]}; statement must disclose {tokens[0]}")
            return
        rep.error(f"B2: claim {claim.get('id')!r}: band must be one of {sorted(tokens)}, got {band!r}")
        return
    if tokens.index(band) > control_free_ceiling(rep, claim):
        evs = claim.get("evidence", [])
        controlled = any(isinstance(e, dict) and e.get("family") != "judgment" and isinstance(e.get("control"), dict) and e["control"].get("of_claim") == claim.get("id") and e["control"].get("observed") == "red" and e["control"].get("expectation") == "red" for e in evs) if isinstance(evs, list) else False
        passing_families = {e.get("family") for e in evs if isinstance(e, dict) and e.get("result") == "pass"} if isinstance(evs, list) else set()
        controlled = controlled and passing_families != {"judgment"}
        if not controlled:
            rep.error("B2: band above control-free ceiling requires >=1 observed-red control whose of_claim names this claim")


def check_applicability(rep, claim):
    errors, warnings = grammar.check_applicability_fields(claim, "0.1.0-draft" if is_transitional_conformance(rep) else "")
    for m in errors: rep.error(m)
    for m in warnings: rep.warn(m)


def check_gaps(rep, claim):
    errors, warnings = grammar.check_gaps_field(claim)
    for m in errors: rep.error(m)
    for m in warnings: rep.warn(m)


def check_slice_boundary(rep, doc):
    for message in grammar.slice_boundary_warnings(doc.get("coverage", {})):
        rep.warn(message)


INVENTORY_ITEM_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
INVENTORY_FIRMNESS_VALUES = {"draft", "firm"}


def check_inventory(rep: Reporter, doc: dict, claims: list) -> None:
    """B19: generic Class-rung spec inventory. A no-op unless `[spec].inventory` is present
    (0.3 contracts require it later; existing manifests need no change)."""
    spec = doc.get("spec")
    if not isinstance(spec, dict) or "inventory" not in spec:
        return
    if not _is_nonempty_str(spec.get("inventory")):
        rep.error("B19: [spec].inventory must be a nonempty string")
        return
    digest_value = spec.get("inventory_digest")
    if not _wire(digest_value, "inventory:"):
        rep.error("B19: [spec].inventory_digest must be inventory:sha-512:<128-hex>")
    if not hasattr(rep, "context"):
        return
    target = _resolve_pointer(rep, spec["inventory"], "spec.inventory")
    if target is None:
        return
    try:
        raw = target.read_bytes()
    except OSError as exc:
        rep.unknowns.append(f"B6: spec.inventory: unreadable document: {exc}")
        return
    if _wire(digest_value, "inventory:") and digest_value != hashdomains.digest("inventory:", raw):
        rep.error("B19: spec inventory digest mismatch in [spec].inventory_digest")
    try:
        inventory = tomllib.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        rep.unknowns.append(f"B19: spec.inventory: unparsable document: {exc}")
        return
    check_no_aggregates(rep, inventory, "spec.inventory", getattr(rep, "aggregate_extensions", ()))

    header = inventory.get("inventory")
    if not isinstance(header, dict) or not all(
        _is_nonempty_str(header.get(field)) for field in ("id", "title", "source")
    ):
        rep.error("B19: [inventory] must have nonempty id, title and source")

    items = inventory.get("item")
    if not isinstance(items, list) or not items:
        rep.error("B19: spec inventory must declare at least one [[item]]")
        return
    ids: list[str] = []
    for index, row in enumerate(items):
        if not isinstance(row, dict):
            rep.error(f"B19: item[{index}] must be a table")
            continue
        item_id = row.get("id")
        if not isinstance(item_id, str) or not INVENTORY_ITEM_ID_RE.fullmatch(item_id):
            rep.error(
                f"B19: item[{index}].id must match [A-Za-z0-9][A-Za-z0-9._-]*, got {item_id!r}"
            )
            continue
        if not _is_nonempty_str(row.get("title")):
            rep.error(f"B19: item {item_id!r} must have a nonempty title")
        firmness = row.get("firmness", "firm")
        if firmness not in INVENTORY_FIRMNESS_VALUES:
            rep.error(
                f"B19: item {item_id!r} firmness must be one of "
                f"{sorted(INVENTORY_FIRMNESS_VALUES)}, got {firmness!r}"
            )
        for optional in ("ref", "parent"):
            if optional in row and not _is_nonempty_str(row.get(optional)):
                rep.error(f"B19: item {item_id!r} field {optional!r} must be a nonempty string")
        ids.append(item_id)
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item_id in ids:
        (duplicates if item_id in seen else seen).add(item_id)
    if duplicates:
        rep.error(f"B19: duplicate inventory item id(s): {sorted(duplicates)}")
    item_ids = set(ids)

    cited: set[str] = set()
    additions: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        clause = claim.get("clause")
        if not isinstance(clause, str):
            continue
        label = claim.get("id", clause)
        is_addition = claim.get("addition") is True
        if clause in item_ids:
            if is_addition:
                rep.error(
                    f"B19: claim {label!r}: addition must not cite a declared inventory "
                    f"item id ({clause!r})"
                )
            else:
                cited.add(clause)
        elif is_addition:
            additions.append(label)
        else:
            rep.error(
                f"B19: claim {label!r} cites id absent from spec inventory: {clause!r} "
                f"(use addition = true for a delivered item beyond the spec)"
            )

    missing = sorted(item_ids - cited)
    if missing:
        rep.error(f"B19: spec inventory item(s) missing a claim: {missing}")
    rep.n_inventory_additions = len(additions)
    if additions:
        rep.notes.append(
            f"B19: {len(additions)} addition claim(s) beyond the spec inventory: {sorted(additions)}"
        )


def check_no_aggregates(rep, value, label="manifest", extra=(), location=()):
    blocked = grammar.AGGREGATES | set(extra)
    if isinstance(value, dict):
        if "calibration" in value:
            check_calibration(rep, value["calibration"], label)
        for key, item in value.items():
            if key in blocked:
                rep.error(f"B7: aggregate key {label}.{key} is forbidden")
            if key in RESERVED_TRUST_FIELDS and not ((len(location) == 4 and location[0] == "claim" and type(location[1]) is int and location[2] == "evidence" and type(location[3]) is int and label.startswith("manifest.")) and _is_nonempty_str(value.get("calibration"))):
                rep.error(f"B7: {label}.{key} without calibration reference on an evidence entry")
            check_no_aggregates(rep, item, label + "." + key, extra, location + (key,))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            check_no_aggregates(rep, item, f"{label}[{i}]", extra, location + (i,))


def _repository_root(path, override=None):
    nearest = next((p for p in (path.parent, *path.parents) if (p / ".git").exists()), None)
    if override is None:
        return nearest
    root = Path(override).resolve()
    if nearest is not None and not root.is_relative_to(nearest):
        return None  # --root cannot widen a known repository
    return root if path.resolve().is_relative_to(root) else None


def _resolve_pointer(rep, value, label, *, legacy=False):
    if not isinstance(value, str) or not value:
        rep.error(f"B6: {label} must be a nonempty relative path")
        return None
    path = Path(value)
    if path.is_absolute():
        rep.error(f"B6: {label}: absolute path forbidden")
        return None
    root = rep.context.root
    if root is None:
        if legacy:
            rep.warn(f"B6: legacy {label}: repository root unresolvable; pointer remains unevaluated")
        if not legacy:
            rep.unknowns.append(f"B6: {label}: repository root unresolvable (no .git ancestor; pass --root DIR)")
        return None
    try:
        target = (rep.context.path.parent / path).resolve()
        if not target.is_relative_to(root):
            rep.error(f"B6: {label}: path escapes repository root")
            return None
        nested = next((p for p in (target.parent, *target.parents) if (p / '.git').exists()), None)
        if nested is not None and nested != next((p for p in (root, *root.parents) if (p / '.git').exists()), None):
            rep.error(f"B6: {label}: path crosses repository boundary")
            return None
        return target
    except (OSError, ValueError, RuntimeError) as exc:
        rep.unknowns.append(f"B6: {label}: cannot resolve pointer: {exc}")
        return None


def _read_document(rep, value, label, *, legacy=False, domain=None, expected=None):
    target = _resolve_pointer(rep, value, label, legacy=legacy)
    if target is None:
        return None
    try:
        raw = target.read_bytes()
    except OSError as exc:
        message = f"B6: {label}: unreadable document: {exc}"
        if legacy: rep.warn(message.replace("B6:", "B6: legacy"))
        else: rep.unknowns.append(message)
        return None
    if domain and expected != hashdomains.digest(domain, raw):
        rep.error(f"B6: {label}: digest differs from declared {domain} hash")
        return None
    try:
        if target.suffix == ".toml":
            doc = tomllib.loads(raw.decode())
        elif target.suffix == ".json":
            doc = json.loads(raw)
        else:
            # Structured TOML assertions in Markdown, plus declared table keys.
            text = raw.decode()
            doc = grammar.markdown_assertion_surface(text)
        check_no_aggregates(rep, doc, label, getattr(rep, "aggregate_extensions", ()))
    except (ValueError, UnicodeError) as exc:
        rep.unknowns.append(f"B6: {label}: unparsable document: {exc}")
        return None
    return raw


def check_documents(rep, doc):
    for claim in doc.get("claim", []) if isinstance(doc.get("claim"), list) else []:
        if not isinstance(claim, dict): continue
        for key in ("doc_ref", "scope_ref"):
            value = claim.get(key)
            if isinstance(value, str) and not re.match(r"^[a-z]+:", value):
                _resolve_pointer(rep, value.split("#")[0], key, legacy=True)
    conf = doc.get("conformance", {})
    if isinstance(conf, dict) and conf.get("applicability_record"):
        _read_document(rep, conf["applicability_record"], "conformance.applicability_record", domain="applicability-record:" if conf.get("applicability_hash") else None, expected=conf.get("applicability_hash"))


def _module(path, namespace):
    if not path.is_file(): return None
    name = f"_acceptance_{namespace}_{path.stem}_{abs(hash(str(path.resolve())))}"
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def parse_profile(rep, doc):
    fmt = doc.get("format", {})
    value = fmt.get("profile") if isinstance(fmt, dict) else None
    if value is None:
        rep.error("B12: [format].profile is REQUIRED at 0.3.0 (no compatibility default); "
                   "the field is missing")
        return None, []
    if not isinstance(value, str) or not re.fullmatch(r"acceptance/[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)*", value) or value.split('/')[1] == "core":
        rep.error("B12: invalid or reserved profile id")
        return None, []
    pieces = value.split('/')[1:]
    return pieces[0], pieces[1:]


def load_bindings(rep, paths):
    loaded = []
    for i in range(1, len(paths) + 1):
        parts = paths[:i]
        path = MODULE_ROOT / "bindings" / ("_".join(parts) + ".py")
        if not path.exists(): path = MODULE_ROOT / "bindings" / Path(*parts).with_suffix('.py')
        try:
            module = _module(path, "binding")
        except Exception as exc:
            rep.unknowns.append(f"B13: binding import failed {'/'.join(parts)}: {type(exc).__name__}: {exc}")
            continue
        if module is None or not callable(getattr(module, "check", None)):
            if rep.context.meaning_only and known_leaf(paths):
                rep.scope_meaning = True
                rep.notes = []
            if not getattr(rep, "scope_meaning", False):
                rep.unknowns.append(f"B13: missing binding half {'/'.join(parts)}")
            continue
        declarations = {}
        docpath = BINDING_DOC_ROOT / Path(*parts).with_suffix('.md')
        try:
            text = docpath.read_text()
            for block in re.findall(r"```toml\s*\n(.*?)```", text, re.S):
                data = tomllib.loads(block)
                for key in ("admits", "identity"):
                    if key in data: declarations[key] = data[key]
        except (OSError, ValueError) as exc:
            rep.unknowns.append(f"B14: binding declarations unavailable: {docpath}: {exc}")
        loaded.append((module, declarations))
    return loaded


def _identity_set(declaration):
    value = declaration.get("identity", [])
    if isinstance(value, dict): value = value.get("kinds", value.get("locators", []))
    return set(value) if isinstance(value, list) and all(isinstance(v, str) for v in value) else set()


def subject_identity_kind(subject) -> str | None:
    """B1: classify a subject dict's certified identity kind — 'components' | 'git-revision' |
    'content-digest' — or None when it carries none (e.g. a prospective subject, or an
    already-invalid one `check_subject_locator` separately flags). Shared classification:
    `check_binding_chain` (B17 narrowing) below, and any caller OUTSIDE this module (the
    protocol core, `protocol_acceptance/tools/acceptance_protocol.py`) that needs the same answer
    without re-deriving it (core.md B1/B17, S6 §4.1 item 1)."""
    if not isinstance(subject, dict):
        return None
    if "components" in subject:
        return "components"
    if "commit" in subject:
        return "git-revision"
    if "digest" in subject:
        return "content-digest"
    return None


def subject_identity_value(subject):
    """B1: `(kind, value)` — `subject_identity_kind`'s classification, plus that kind's
    comparable wire value: the git-revision `commit` hex, or the `subject:` digest for
    content-digest AND components alike (B1: the aggregate `subject:` digest over the component
    table IS the components identity, not a second one — so both kinds compare on the same
    `digest` field). `(None, None)` when the subject carries no certified identity."""
    kind = subject_identity_kind(subject)
    if kind is None:
        return None, None
    if kind == "git-revision":
        return kind, subject.get("commit")
    return kind, subject.get("digest")


def check_binding_chain(rep, bindings, doc):
    parent_admits = parent_identity = None
    subject = doc.get("subject", {})
    if not isinstance(subject, dict): return
    # Any subject reaching here has already had check_subject_locator's exactly-one-identity rule
    # applied; when neither components nor commit is present, digest is assumed by construction
    # (unchanged behavior — subject_identity_kind's own explicit digest check is the general form,
    # used verbatim by every caller outside this narrow, already-validated context).
    identity = subject_identity_kind(subject) or "content-digest"
    for module, declaration in bindings:
        admits = declaration.get("admits")
        kinds = _identity_set(declaration)
        if not isinstance(admits, list) or not all(isinstance(x, str) for x in admits) or not kinds:
            rep.unknowns.append("B14: binding requires machine-readable admits and identity declarations")
            continue
        admitted = set(admits)
        if parent_admits is not None and not admitted <= parent_admits:
            rep.error("B17: admits(child) must be a subset of admits(parent)")
        if parent_identity is not None and not kinds <= parent_identity:
            rep.error("B17: identity kinds must narrow the parent")
        parent_admits, parent_identity = admitted, kinds
        check_binding_admission(rep, subject, admitted, kinds)


def check_binding_admission(rep, subject, admitted, kinds):
    if subject.get("kind") not in admitted:
        rep.error(f"B14: binding does not admit subject kind {subject.get('kind')!r}")
    identity = "components" if "components" in subject else "git-revision" if "commit" in subject else "content-digest"
    if subject.get("mode", "retrospective") == "retrospective" and identity not in kinds:
        rep.error(f"B1: binding does not admit identity {identity}")


def known_leaf(paths):
    # Registered /0 skeleton leaves (no module yet); an implemented binding identifies itself by
    # its own module file below, so a leaf with a module needs no entry here — a binding-specific
    # name never has to be listed in class code.
    declared = {"generic", "code", "document", "tool", "estate-element"}
    return "/".join(paths) in declared or (MODULE_ROOT / "bindings" / ("_".join(paths) + ".py")).is_file() or (MODULE_ROOT / "bindings" / Path(*paths).with_suffix(".py")).is_file()


def dispatch(rep, doc):
    meaning, paths = parse_profile(rep, doc)
    # Validate the declared identifier before compatibility selects its meaning.
    known = not paths or known_leaf(paths)
    if not known:
        profile_value = doc.get("format", {}).get("profile") if isinstance(doc.get("format"), dict) else None
        rep.unknowns.append(f"B12: unknown suffix regardless of scoping flags ([format].profile = {profile_value!r})")
    if meaning is not None and not (MODULE_ROOT / "profiles" / f"{meaning}.py").is_file():
        rep.unknowns.append(f"B12: unknown meaning prefix {meaning}")
    # A caller-forced `bound_meaning` (check_acceptance.py's "verification meaning explicitly
    # bound" compatibility entry; protocol_acceptance/tools/profiles.py's conformance/
    # troubleshooting package_validator partials) exists to pick WHICH meaning module evaluates
    # the package, not to discard an otherwise-valid declared binding suffix. When the declared
    # meaning already EQUALS the bound one (the only case every live PROFILES[...]-mediated caller
    # ever reaches, since each is keyed by — and forces bound_meaning to — the SAME meaning its own
    # package declares), `paths` must survive so `load_bindings` still dispatches to the declared
    # binding leaf (a `<meaning>/<binding path>` profile id's own binding chain) — discarding it
    # unconditionally silently skipped every binding-specific check (B20 build_inputs, B9's
    # cover-only guard) on that leaf's documented validator path (0.3.1 defect fix). When the
    # declared meaning DIFFERS from a caller-forced bound one — reachable only by invoking a
    # bound-meaning entry point directly on a manifest declaring a different meaning, never through
    # any PROFILES[...]-mediated protocol/format call — today's override (evaluate under the
    # forced meaning, no binding) is unchanged.
    if meaning is not None and getattr(rep, "bound_meaning", None) and meaning != rep.bound_meaning:
        # A declared
        # meaning that DIFFERS from a caller-forced bound meaning must never yield a clean,
        # unqualified PASS — that silently substitutes another meaning's rules for the package's
        # own declared one (B13's required composition; §6.6's declared-profile dispatch
        # contract). The rest of dispatch still evaluates under the forced meaning below (so a
        # caller relying on the class-level diagnostics this produces still gets them), but this
        # message alone forces the overall verdict to INDETERMINATE (exit 2, `verdict()`'s
        # `if rep.unknowns: return "INDETERMINATE", 2`), naming both meanings and the correct
        # unbound entry point.
        rep.unknowns.append(
            f"B13: declared meaning {meaning!r} differs from the meaning {rep.bound_meaning!r} "
            f"this entry point forces — a forced meaning never silently substitutes for a "
            f"package's own declared one; re-run the UNBOUND `check_core.py` directly (no "
            f"bound-meaning compatibility entry) to evaluate this package under its own declared "
            f"meaning {meaning!r}"
        )
        meaning, paths = rep.bound_meaning, []
    # A scope is effective only when the known leaf's other half is missing.
    binding_missing = bool(paths) and any(not (
        (MODULE_ROOT / "bindings" / ("_".join(paths[:i]) + ".py")).is_file()
        or (MODULE_ROOT / "bindings" / Path(*paths[:i]).with_suffix(".py")).is_file()
    ) for i in range(1, len(paths) + 1))
    meaning_missing = meaning is not None and not (MODULE_ROOT / "profiles" / f"{meaning}.py").is_file()
    requested = rep.context.meaning_only or rep.context.binding_only
    rep.scope_meaning = bool(known and paths and rep.context.meaning_only and binding_missing)
    rep.scope_binding = bool(known and paths and rep.context.binding_only and meaning_missing)
    rep.notes = []
    if requested and not (rep.scope_meaning or rep.scope_binding) and known:
        if not paths:
            rep.notes.append("scoping flag ignored: the profile has no binding half; full verdict")
        else:
            rep.notes.append("scoping flag ignored: both halves present; full composed verdict" if not binding_missing and not meaning_missing else "scoping flag ignored: requested half unavailable")
    rep.meaning_name = meaning
    rep.ladder = None
    rep.families = {"judgment": "T5", "reference": None}
    rep.kinds = dict(CLASS_KINDS)
    if meaning is None: return None, []
    try:
        bindings = load_bindings(rep, paths)
    except Exception as exc:
        rep.unknowns.append(f"B13: cannot load binding evaluator: {exc}")
        bindings = []
    try:
        module = _module(MODULE_ROOT / "profiles" / f"{meaning}.py", "meaning")
    except Exception as exc:
        if not getattr(rep, "scope_binding", False):
            rep.unknowns.append(f"B13: cannot load meaning evaluator: {exc}")
        rep.declarations_unknown = True
        return None, bindings
    if module is None:
        rep.declarations_unknown = True
        message = f"B12: unknown meaning prefix {meaning}"
        if message not in rep.unknowns:
            rep.unknowns.append(message)
        return None, bindings
    declarations = module
    declared = getattr(declarations, "LADDER", None)
    if declared:
        ladder_id = declared.get("ladder_id") if isinstance(declared, dict) else declared
        registry = _module(Path(__file__).resolve().parent / "profiles" / "__init__.py", "registry")
        if ladder_id not in registry.LADDERS:
            rep.error(f"B2: ladder_id {ladder_id!r} is not registered")
        else:
            rep.ladder = {"ladder_id": ladder_id, "tokens": list(registry.LADDERS[ladder_id]), "control_free_ceiling": declared.get("control_free_ceiling", {}) if isinstance(declared, dict) else {}}
    rep.families = {**getattr(declarations, "FAMILIES", {}), "judgment": "T5", "reference": None}
    rep.kinds = {**getattr(declarations, "KINDS", {}), **CLASS_KINDS}
    rep.aggregate_extensions = getattr(module, "AGGREGATES", ())
    rep.profile_version = doc.get("format", {}).get("profile_version", doc.get("format", {}).get("version", "0.1.0-draft")) if meaning == "conformance" else ""
    return module, bindings


def _add_findings(rep, findings):
    for finding in findings:
        if not isinstance(finding, Finding) and not (hasattr(finding, "severity") and hasattr(finding, "message")):
            rep.unknowns.append("B13: evaluator returned an invalid finding")
            continue
        if finding.severity == "error":
            rep.profile_errors.append(finding.message)
            cid = getattr(finding, "claim_id", None)
            if cid is not None:
                rep.profile_refused.add(f"claim {cid!r}")
                if rep.claim_evaluations.get(cid) != "indeterminate":
                    rep.claim_evaluations[cid] = "error"
        elif finding.severity == "pending":
            rep.profile_pending.setdefault(f"claim {finding.claim_id!r}", []).append(finding.message)
        elif finding.severity == "warning": rep.warn(finding.message)
        elif finding.severity in ("unknown", "indeterminate"): rep.unknowns.append(finding.message)
        else: rep.unknowns.append("B13: evaluator returned an invalid severity")


def check_profiles(rep, doc, meaning, bindings):
    modules = ([meaning] if meaning is not None and not rep.scope_binding else [])
    if not getattr(rep, "scope_meaning", False): modules += [m for m, _ in bindings]
    for module in modules:
        try:
            if hasattr(module, "check"):
                _add_findings(rep, module.check(copy.deepcopy(doc), rep.context))
            else:
                rep.unknowns.append("B13: evaluator has no check(doc, ctx)")
        except Exception as exc:
            rep.unknowns.append(f"B13: evaluator unavailable: {type(exc).__name__}: {exc}")


def check_reference_evidence(rep, claim, ev):
    for field in ("manifest", "manifest_hash", "claim", "record_hash"):
        if not _is_nonempty_str(ev.get(field)):
            rep.error(f"B8: reference row requires nonempty {field}")
    for field, expected in (("ref", f"{ev.get('manifest')}#{ev.get('claim')}"),
                            ("result", "pass"), ("record", ev.get("manifest")),
                            ("record_hash", ev.get("manifest_hash"))):
        if ev.get(field) != expected:
            rep.error(f"B8: reference row {field} must equal {expected!r}")
    evidence = claim.get("evidence", [])
    if _is_weighted(claim) and evidence and all(isinstance(e, dict) and e.get("kind") == "acceptance-claim" for e in evidence):
        rep.error("B8: reference-only claim is never weight-bearing")
    ctx = rep.context
    if not isinstance(ev.get("records"), list) or not ev["records"] or not all(isinstance(x, str) and x for x in ev["records"]):
        rep.error("B8: records is required and must be a nonempty list of record hashes")
        return
    if any(not _wire(h, "record:") for h in ev["records"]):
        rep.error("B8: cited records must all use record: domain")
        # Preserve this error while admitting the source far enough to diagnose
        # an explicitly cited reference row as non-native as well.
    if any(isinstance(e, dict) and "control" in e for e in claim.get("evidence", [])) or "control" in claim:
        rep.error("B8: referencing claim cannot carry a control; controls do not transfer")
    wire = ev.get("manifest_hash")
    if not _wire(wire, "manifest:"):
        rep.error("B8: manifest_hash must use manifest:sha-512")
        return
    target = _resolve_pointer(rep, ev.get("manifest"), "reference manifest")
    if target is None: return
    try:
        raw = target.read_bytes()
    except OSError as exc:
        rep.unknowns.append(f"B8: unreadable source manifest: {exc}")
        return
    if hashdomains.digest("manifest:", raw) != wire:
        rep.error("B8: source manifest hash mismatch (hash-before-parse)")
        return
    if wire in ctx.stack:
        rep.unknowns.append("B8: cycle in manifest_hash traversal")
        return
    if len(ctx.stack) + 1 > 5:
        rep.unknowns.append("B8: reference depth exceeds 4 edges (maximum five manifests including root)")
        return
    source = validate(target, False, ctx.strict_weight, root=ctx.root, _stack=ctx.stack + (wire,))
    label, _ = verdict(source)
    if label == "FAIL":
        rep.error("B8: source manifest fails validation")
        return
    if label == "INDETERMINATE":
        rep.unknowns.append("B8: source manifest is INDETERMINATE")
        return
    candidates = [c for c in source.doc.get("claim", []) if isinstance(c, dict) and c.get("id") == ev.get("claim")]
    if len(candidates) != 1 or candidates[0].get("status") not in ("evidenced", "partial"):
        rep.error("B8: source claim must exist and be evidenced or partial")
        return
    source_claim = candidates[0]
    records = []
    for requested in ev["records"]:
        matches = [e for e in source_claim.get("evidence", []) if isinstance(e, dict) and e.get("record_hash") == requested]
        if not matches or any("control" in e or e.get("result") != "pass" for e in matches):
            rep.error("B8: cited record must be a passing non-control entry of the named source claim")
            return
        if any(e.get("kind") == "acceptance-claim" for e in matches):
            rep.error("B8: cited record must be NATIVE, not a transitive acceptance-claim")
            return
        for entry in matches:
            target_record = _resolve_pointer(source, entry.get("record"), "cited record")
            try:
                if target_record is None: raise OSError("unresolvable cited record")
                target_record.read_bytes()
            except OSError:
                rep.unknowns.append("B8: cited record is unresolvable")
                return
        records.extend(matches)
    tiers = [e.get("epistemic_tier", source.families.get(e.get("family"))) for e in records]
    if any(_rank(t) is None for t in tiers):
        rep.unknowns.append("B8: source record tier is unavailable")
        return
    tier = max(tiers, key=_rank)  # minimum epistemic strength, not smallest T numeral
    if "epistemic_tier" in ev and ev["epistemic_tier"] != tier:
        rep.error("B3/B8: reference tier must equal derived minimum of source records")
    ev["epistemic_tier"] = tier
    same = 'band' in source_claim and rep.ladder and source.ladder and rep.ladder['ladder_id'] == source.ladder['ladder_id']
    if not same:
        if "band" in claim: rep.error("B8: cross-ladder or band-less source requires a band-less referencing claim")
    elif claim.get("band") in rep.ladder["tokens"]:
        ceiling = min(source.ladder["tokens"].index(source_claim.get("band", source.ladder["tokens"][0])), control_free_ceiling(rep, claim))
        if rep.ladder["tokens"].index(claim["band"]) > ceiling:
            rep.error("B8: reference band exceeds source minimum or control-free ceiling")


def verdict(rep):
    if getattr(rep, "input_failure", False): return "INDETERMINATE", 2
    if getattr(rep, "class_errors", rep.errors): return "FAIL", 1
    if "indeterminate" in getattr(rep, "claim_evaluations", {}).values(): return "INDETERMINATE", 2
    if rep.unknowns: return "INDETERMINATE", 2
    if rep.profile_errors: return "FAIL", 1
    if getattr(rep, "nothing_applicable", False): return "INDETERMINATE", 2
    if getattr(rep, "is_prospective", False): return "PASS-PROSPECTIVE", 0
    if rep.scope_meaning: return "PASS-MEANING-ONLY", 0
    if rep.scope_binding: return "PASS-BINDING-ONLY", 0
    return "PASS", 0


def _verdict_label(rep):
    return verdict(rep)[0]


def validate(path: Path, strict: bool, strict_weight: bool = False, *, root=None, meaning_only=False, binding_only=False, _stack=(), bound_meaning=None):
    path = Path(path).resolve()
    rep = Reporter(str(path), strict_weight=strict_weight)
    rep.unknowns, rep.profile_errors = [], []
    rep.claim_evaluations, rep.weight_checks, rep.profile_pending = {}, {}, {}
    rep.profile_refused = set()
    rep.context = Context(path, _repository_root(path, root), strict, strict_weight, meaning_only, binding_only, _stack)
    rep.doc = {}
    rep.bound_meaning = bound_meaning
    try:
        raw = path.read_bytes()
        doc = tomllib.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        # The old API's .errors/ok() contract remains for input failures; CLI is indeterminate.
        msg = f"cannot read file: {exc}" if isinstance(exc, OSError) else f"not valid UTF-8: {exc}" if isinstance(exc, UnicodeDecodeError) else f"TOML parse error: {exc}"
        rep.error(msg)
        rep.input_failure = True
        return rep
    rep.doc = doc
    if not _stack:
        rep.context = Context(path, rep.context.root, strict, strict_weight, meaning_only, binding_only, (hashdomains.digest("manifest:", raw),))
    if root is not None and rep.context.root is None:
        rep.unknowns.append("B6: --root cannot widen to a second repository or exclude the manifest")
    meaning, bindings = dispatch(rep, doc)
    check_format(rep, doc)
    check_subject(rep, doc)
    raw_claims = doc.get("claim", [])
    any_weighted = isinstance(raw_claims, list) and any(isinstance(c, dict) and _is_weighted(c) for c in raw_claims)
    check_spec(rep, doc, any_weighted)
    claims = check_claims(rep, doc, path.parent, strict)
    check_coverage(rep, doc, claims)
    if not claims: rep.error("B11: zero [[claim]] entries")
    check_inventory(rep, doc, claims)
    check_slice_boundary(rep, doc)
    check_no_aggregates(rep, doc, extra=getattr(rep, "aggregate_extensions", ()))
    check_documents(rep, doc)
    if meaning is not None:
        for field in getattr(meaning, "ASSERTION_SURFACES", ()):
            value = doc
            for part in field.split('.'):
                value = value.get(part) if isinstance(value, dict) else None
            if value is not None: _read_document(rep, value, field)
    check_binding_chain(rep, bindings, doc)
    for c in claims:
        if not isinstance(c, dict): continue
        for e in c.get("evidence", []) if isinstance(c.get("evidence", []), list) else []:
            if isinstance(e, dict) and e.get("kind") == "acceptance-claim":
                errors_before, unknowns_before = len(rep.errors), len(rep.unknowns)
                check_reference_evidence(rep, c, e)
                if len(rep.errors) > errors_before: rep.claim_evaluations[c.get("id")] = "error"
                elif len(rep.unknowns) > unknowns_before: rep.claim_evaluations[c.get("id")] = "indeterminate"
    rep.class_errors = tuple(rep.errors)
    check_profiles(rep, doc, meaning, bindings)
    rep.n_claims_total = len(claims)
    rep.n_not_applicable = sum(isinstance(c, dict) and grammar.effective_status(c) == 'not-applicable' for c in claims)
    rep.n_excluded = sum(isinstance(c, dict) and c.get('applicability') == 'excluded' for c in claims)
    rep.n_gaps = sum(isinstance(c, dict) and grammar.effective_status(c) == 'gap' and c.get('applicability') != 'excluded' for c in claims)
    rep.nothing_applicable = bool(claims) and rep.n_not_applicable == len(claims) and doc.get('subject', {}).get('mode', 'retrospective') != 'prospective'
    rep.is_prospective = bool(claims) and (not any(isinstance(c, dict) and c.get('status') in ('evidenced', 'partial') for c in claims) or doc.get('subject', {}).get('mode') == 'prospective')
    # Keep compatibility API errors visible without letting profile code modify class findings.
    rep.errors.extend(rep.profile_errors)
    previous = len(rep.errors)
    finalize_weight(rep)
    rep.class_errors += tuple(rep.errors[previous:])
    return rep


def selftest():
    from fixtures import legacy, core_cases, r3_cases
    from contextlib import redirect_stdout
    from io import StringIO
    with redirect_stdout(StringIO()) as output:
        result = legacy.selftest()
    if result: print(output.getvalue(), end="")
    count, failures = core_cases.run()
    for failure in failures: print(f"SELFTEST FAIL: {failure}", file=sys.stderr)
    if result or failures: return 1
    print(f"SELFTEST PASS: {165 + count} fixtures")
    return 0


def main(argv, *, bound_meaning=None):
    import argparse
    parser = argparse.ArgumentParser(prog=Path(argv[0]).name)
    parser.add_argument('--strict', action='store_true')
    parser.add_argument('--strict-weight', action='store_true')
    parser.add_argument('--root', type=Path)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--meaning-only', action='store_true')
    scope.add_argument('--binding-only', action='store_true')
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('files', nargs='*')
    args = parser.parse_args(argv[1:])
    if args.selftest: return selftest()
    if not args.files: parser.error('no FILE arguments given')
    exits = []
    for f in args.files:
        rep = validate(Path(f), args.strict, args.strict_weight, root=args.root, meaning_only=args.meaning_only, binding_only=args.binding_only, bound_meaning=bound_meaning)
        label, code = ("INDETERMINATE", 2) if getattr(rep, 'input_failure', False) else verdict(rep)
        for line in rep.lines(): print(line)
        for note in getattr(rep, "notes", []): print(f"NOTE {f}: {note}")
        for message in rep.unknowns: print(f"INDETERMINATE {f}: {message}")
        nw, nu, npd = (getattr(rep, k, 0) for k in ('n_weighted', 'n_unweighted', 'n_pending'))
        pend = f", weight-pending: {npd}" if npd else ''
        n = len(rep.errors) if code == 1 else len(rep.warnings)
        suffix = f" ({n} error{'s' if n != 1 else ''})" if code == 1 else f" ({n} warning{'s' if n != 1 else ''})" if n else ''
        print(f"{label} {f}{suffix} [weighted: {nw}, unweighted: {nu}{pend}]")
        if getattr(rep, "n_not_applicable", 0) or getattr(rep, "n_excluded", 0):
            print(f"COVERAGE {f} [not-applicable: {rep.n_not_applicable}, excluded: {rep.n_excluded}, gap: {rep.n_gaps}]")
        if (args.meaning_only or args.binding_only) and label == 'PASS-PROSPECTIVE': print(f"NOTE {f}: scoped {'meaning-only' if args.meaning_only else 'binding-only'}")
        exits.append(code)
    return 1 if 1 in exits else 2 if 2 in exits else 0




def finalize_weight(rep):
    for ctx, (claim, pending_reasons, class_error) in rep.weight_checks.items():
        pending_reasons += rep.profile_pending.get(ctx, [])
        if _is_weighted(claim):
            raised_own_error = class_error or ctx in rep.profile_refused or rep.claim_evaluations.get(claim.get("id")) == "error"
            if raised_own_error:
                # Finding 7/G5: refused outright (not weight-pending) — record structurally so a
                # downstream weight-grant reader never has to re-derive this from error strings.
                rep.weight_refused.add(ctx)
            if pending_reasons and not raised_own_error:
                for reason in pending_reasons:
                    rep.weight_pending(ctx, reason)
                rep.n_pending = getattr(rep, "n_pending", 0) + 1
            elif not raised_own_error:
                rep.n_weighted = getattr(rep, "n_weighted", 0) + 1
            elif pending_reasons:
                # Say why the backlog does NOT grow here, or a producer fixing the errors is
                # surprised by two more refusals appearing afterwards.
                rep.warn(
                    f"{ctx}: WEIGHT REFUSED outright (not `weight-pending`): this claim also "
                    f"breaks a rule that predates the 2026-08-25 adoption, so it is not on the "
                    f"§8.1 remediation backlog. It additionally lacks: "
                    f"{'; '.join(pending_reasons)}"
                )



def check_calibration(rep, value, label):
    target = _resolve_pointer(rep, value, label + ".calibration")
    if target is None: return
    try:
        raw = target.read_bytes()
        if target.suffix == ".toml": tomllib.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        rep.error(f"B7: calibration missing, unreadable or unparsable: {value!r}: {exc}")


def check_record_hashes(rep, doc):
    """Class-owned payload integrity, independent of execution and profile/scoping."""
    for claim in doc.get("claim", []) if isinstance(doc.get("claim"), list) else []:
        if not isinstance(claim, dict): continue
        for idx, ev in enumerate(claim.get("evidence", []) if isinstance(claim.get("evidence", []), list) else []):
            if not isinstance(ev, dict): continue
            label = f"claim {claim.get('id')!r} evidence[{idx}]"
            ref = ev.get("record")
            if not _is_nonempty_str(ref): continue  # universal shape check already reports it
            expected = ev.get("record_hash")
            domain = "manifest:" if ev.get("kind") == "acceptance-claim" else "record:"
            untyped = isinstance(expected, str) and bool(re.fullmatch(r"sha-512:[0-9a-f]{128}", expected)) and domain == "record:"
            if expected is not None and not _wire(expected, domain) and not untyped:
                rep.error(f"B16: {label}: record_hash must use {domain}sha-512:<128-hex>")
            target = _resolve_pointer(rep, ref, "evidence.record")
            if target is None: continue
            try:
                raw = target.read_bytes()
            except OSError:
                message = f"{label}: record pointer does not exist: {ref} (or is unreadable)"
                (rep.error if rep.context.strict else rep.warn)(message)
                continue
            if untyped:
                legacy_wire = next((name for name, prefix in (("bare", b""), ("evidence-record", b"evidence-record:"))
                                    if hashlib.sha512(prefix + raw).hexdigest() == expected.split(":", 1)[1]), None)
                if legacy_wire is None:
                    rep.error(f"B16: {label}: untyped record_hash mismatch: no legacy wire matches")
                else:
                    rep.warn(f"B16: untyped record_hash (legacy wire: {legacy_wire}); use record:sha-512")
            if expected is not None and _wire(expected, domain) and hashdomains.digest(domain, raw) != expected:
                rep.error(f"B16: {label}: record digest differs from declared {domain} hash")


def check_record_hash(claim_id: str, idx: int, ev: dict,
                      subject_root: Path) -> tuple[bool, str] | None:
    """P9 second half -- RECORD BINDING. An evidence record points at a file; nothing today ties
    that pointer to the bytes the run actually produced, so a record can be regenerated, edited or
    truncated and every checker stays green.

    Returns (is_error, message), or None when there is nothing to say.

    `record_sha256`, when present, is checked, and a MISMATCH is an error that exits nonzero: a
    present-but-wrong hash is a detected falsehood, not an absence, and reporting it at exit 0 was
    the same "vouching by silence" the format forbids everywhere else. When the hash is ABSENT it
    is reported and NOT failed: making it mandatory changes what a conforming manifest is, which is
    a spec decision and an owner call (proposed, not adopted -- see PROPOSALS-2026-08-25.md P9b)."""
    ref = ev.get("record")
    if not isinstance(ref, str) or not ref:
        return None
    declared = ev.get("record_sha256")
    p = (subject_root / ref) if not os.path.isabs(ref) else Path(ref)
    if declared is None:
        return (False,
                f"claim {claim_id!r} evidence[{idx}]: record {ref!r} declares no 'record_sha256' — "
                f"nothing binds this row to the bytes its run produced (P9b, proposed)")
    if not p.is_file():
        return (True,
                f"claim {claim_id!r} evidence[{idx}]: record {ref!r} declares a sha256 but the "
                f"file does not exist")
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    if actual != declared:
        return (True,
                f"claim {claim_id!r} evidence[{idx}]: record {ref!r} sha256 MISMATCH — declared "
                f"{declared[:16]}…, actual {actual[:16]}… (the record changed after it was cited)")
    return None

if __name__ == '__main__':
    # Profile callbacks must import this very module, including its Finding type.
    sys.modules['check_core'] = sys.modules[__name__]
    sys.exit(main(sys.argv))
