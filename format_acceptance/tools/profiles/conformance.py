#!/usr/bin/env python3
"""Conformance 0.1 meaning delta and composed core CLI; C11 lineage stays at 0.1.

Counts retain the historical display for existing consumers. The gap count includes
not-applicable rows as it did before B5; applicability columns disambiguate them.
Core coverage uses effective statuses and excludes them from evidence gaps.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import tempfile
import tomllib
from contextlib import nullcontext, redirect_stdout
from dataclasses import dataclass, field
from datetime import date
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import acceptance_grammar as grammar
import hashdomains
from profiles import verification
from profiles.verification import check_recipe_requirements, check_grade_companions

# Sibling reuse by reference, not a second family or ladder registry.
FAMILIES = verification.FAMILIES
LADDER = verification.LADDER
KINDS = {k: v for k, v in verification.KINDS.items() if k != "flux-refinement"}
OPTIONAL_RECORD_FIELDS = verification.OPTIONAL_RECORD_FIELDS
from acceptance_grammar import (
    GRADES,
    NORMATIVE_REFERENCE_PREFIX,
    STATUSES,
)

MEANING = "acceptance/conformance"
SUFFIXES = {"", "/code", "/code/rust"}
APPLICABILITY = ("applicable", "not-applicable", "excluded")
AGGREGATES = {"score", "percent", "percentage", "conformance_level"}
GAP = "gap"
OUT_OF_SCOPE = "out-of-scope"
UNWEIGHTED = "unweighted"
WEIGHT_VALUES = {"weighted", UNWEIGHTED}
assert GAP in STATUSES and OUT_OF_SCOPE in GRADES
assert WEIGHT_VALUES == getattr(grammar, "WEIGHT_VALUES", WEIGHT_VALUES)
# The grammar currently exports no band ordering. The round-3 fallback is
# A0 < A1 < A2 < A3 < A4; reserved A3.5 has no rank in this borrowed-evidence lane.
BAND_ORDER = getattr(grammar, "BAND_ORDER", ("A0", "A1", "A2", "A3", "A4"))
BAND_RANK = getattr(grammar, "BAND_RANK", {band: rank for rank, band in enumerate(BAND_ORDER)})

RFC3339_RE = re.compile(
    r"([0-9]{4})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    r"[Tt](?:[01][0-9]|2[0-3]):[0-5][0-9]:(?:[0-5][0-9]|60)"
    r"(?:\.[0-9]+)?(?:[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)


def normative_digest(raw: bytes) -> str:
    return hashdomains.digest("normative-reference:", raw)


def applicability_digest(raw: bytes) -> str:
    return hashdomains.digest("applicability-record:", raw)


def source_manifest_digest(raw: bytes) -> str:
    return hashdomains.digest("manifest:", raw)


def _nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


@dataclass
class Report:
    path: Path
    failures: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    meaning_only: bool = False
    composed_verdict: str | None = None
    warnings: list[str] = field(default_factory=list)
    counts: dict[str, int | str] = field(default_factory=lambda: {
        key: "?" for key in (*APPLICABILITY, "evidenced", GAP)
    })

    def fail(self, rule: int, message: str) -> None:
        self.failures.append(f"C{rule}: {message}")

    def warn(self, rule: int, message: str) -> None:
        self.warnings.append(f"C{rule}: {message}")

    @property
    def verdict(self) -> str:
        if self.composed_verdict is not None:
            return self.composed_verdict
        if self.failures:
            return "FAIL"
        if self.unknowns:
            return "INDETERMINATE"
        return "PASS-MEANING-ONLY" if self.meaning_only else "PASS"

    @property
    def exit_code(self) -> int:
        return {"PASS": 0, "PASS-PROSPECTIVE": 0, "PASS-MEANING-ONLY": 0, "FAIL": 1, "INDETERMINATE": 2}[self.verdict]

    def render(self) -> str:
        lines = [f"FAIL {self.path}: {message}" for message in self.failures]
        lines += [f"INDETERMINATE {self.path}: {message}" for message in self.unknowns]
        lines += [f"WARN {self.path}: {message}" for message in self.warnings]
        lines += [f"NOTE {self.path}: {message}" for message in self.notes]
        c = self.counts
        lines.append(
            f"{self.verdict} {self.path} [applicable: {c['applicable']}, "
            f"not-applicable: {c['not-applicable']}, excluded: {c['excluded']}; "
            f"evidenced: {c['evidenced']}, gap: {c[GAP]}]"
        )
        return "\n".join(lines)


def _read_toml(rep: Report, path: Path, label: str) -> tuple[dict, bytes] | None:
    try:
        raw = path.read_bytes()
        return tomllib.loads(raw.decode("utf-8")), raw
    except (OSError, ValueError) as exc:
        # ValueError includes TOMLDecodeError, UnicodeDecodeError and NUL paths.
        rep.unknowns.append(f"cannot read/parse {label} {str(path)!r}: {str(exc)!r}")
        return None


def _key_paths(value, path: str, keys: set[str]):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in keys:
                yield child_path
            yield from _key_paths(child, child_path, keys)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _key_paths(child, f"{path}[{index}]", keys)


def _rfc3339(value) -> bool:
    match = RFC3339_RE.fullmatch(value) if isinstance(value, str) else None
    if match:
        try:
            date(*(int(part) for part in match.groups()))
            return True
        except ValueError:
            pass
    return False


def _repository_root(rep: Report, manifest: Path, override: Path | None) -> Path | None:
    try:
        if override is not None:
            root = override.resolve()
            if root.is_dir():
                return root
            rep.unknowns.append(f"--root is not a directory: {str(root)!r}")
        else:
            for parent in manifest.parents:
                if (parent / ".git").exists():
                    return parent
            rep.unknowns.append("no repository root found; supply --root DIR")
    except (OSError, ValueError, RuntimeError) as exc:
        rep.unknowns.append(f"cannot resolve repository root: {str(exc)!r}")
    return None


def _document_path(rep: Report, manifest: Path, root: Path, value: str,
                   label: str) -> Path | None:
    """Locate a class-covered document pointer without re-emitting B6/digest
    diagnostics: `check_core.check_spec` ([spec].path) and `check_core.check_documents`
    ([conformance].applicability_record) already report every containment and
    digest violation at 8a, unconditionally, on every validation path (design history, not
    published, removed the overlapping checks this meaning used to run itself: C9 vs B7,
    R-2 vs B6, C6 vs the recomputation core now owns). This helper only resolves the
    pointer so the meaning's own per-clause analysis can read the parsed content;
    a resolution failure here is silent (`_evaluate`'s callers already bail to
    INDETERMINATE/return-early on a None path), because the class-level check
    already produced the FAIL/INDETERMINATE that decides the composed verdict."""
    from check_core import Context, Reporter, _resolve_pointer
    shadow = Reporter(str(manifest))
    shadow.context = Context(manifest, root)
    shadow.unknowns = []
    return _resolve_pointer(shadow, value, label)


def _check_aggregates(rep: Report, doc: dict, label: str) -> None:
    for location in _key_paths(doc, label, AGGREGATES):
        rep.fail(9, f"aggregate key forbidden: {location}")


LEGACY_LINEAGE_TABLE_FIELDS = ("source_manifest", "source_manifest_hash")


def _check_legacy_lineage(rep: Report, doc: dict, conf: dict) -> None:
    """B8 (the 0.2 lowering pass, conformance 0.2): the meaning stops READING conformance 0.1.0-draft's
    pre-/0 cross-manifest lineage encoding (`source_claim`/`source_claims_other` on a
    claim, `[conformance].source_manifest{,_hash}`) — no C11-shaped validation of these
    fields runs any more, at any declared profile_version. A borrowed claim cites its
    source with a class B8 `acceptance-claim` reference evidence entry (core.md B8),
    validated entirely by `check_core.check_reference_evidence`; this meaning adds no
    B8-specific mechanism. Presence of the legacy fields is flagged, gated by
    profile_version the same way B5 (not-applicable) and B9 ([conformance].cover_only)
    already are: WARNING under an explicitly declared `0.1.0-draft` (so the nine
    pre-lowering companion subjects do not go from a real PASS to FAIL merely by carrying
    inert legacy keys pending their own regeneration), ERROR everywhere else,
    including 0.2.0 and an undeclared/omitted profile_version."""
    fmt = doc.get("format", {}) if isinstance(doc.get("format"), dict) else {}
    legacy_version = fmt.get("profile_version", fmt.get("version", "0.1.0-draft")) == "0.1.0-draft"
    report = rep.warn if legacy_version else rep.fail
    if isinstance(conf, dict):
        for key in LEGACY_LINEAGE_TABLE_FIELDS:
            if key in conf:
                report(8, f"[conformance].{key} is deprecated dead metadata (no C11 validation "
                          "runs); cite the source claim with a class B8 acceptance-claim "
                          "evidence entry instead (core.md B8)" if legacy_version else
                          f"[conformance].{key} is retired at conformance 0.2; cite the source "
                          "claim with a class B8 acceptance-claim evidence entry instead (core.md B8)")
    for claim in doc.get("claim", []) if isinstance(doc.get("claim"), list) else []:
        if not isinstance(claim, dict):
            continue
        context = f"claim {claim.get('id', claim.get('clause'))!r}"
        for key in claim:
            if isinstance(key, str) and key.startswith("source_claim"):
                report(8, f"{context}: {key!r} is deprecated dead metadata (no C11 validation "
                          "runs); cite the source claim with a class B8 acceptance-claim "
                          "evidence entry instead (core.md B8)" if legacy_version else
                          f"{context}: {key!r} is retired at conformance 0.2; cite the source "
                          "claim with a class B8 acceptance-claim evidence entry instead (core.md B8)")


def _evaluate(doc, path: Path, *, root: Path | None = None) -> Report:
    """Only the conformance meaning delta; documents are resolved against ctx."""
    rep = Report(path)
    spec = doc.get("spec")
    conf = doc.get("conformance")
    if isinstance(spec, dict) and spec.get("provenance", "in-tree") == "in-tree":
        rep.unknowns.append("in-tree conformance standards not implemented in 0.1.0-draft")
        return rep
    # C9's manifest-wide aggregate scan is not restated here: `check_core.validate`
    # already runs `check_no_aggregates` over the full manifest `doc` at 8a,
    # unconditionally, on every validation path (the 0.2 lowering pass's de-duplication; the inventory
    # and applicability-record documents below stay meaning-checked — core does not
    # see those profile-declared assertion surfaces).
    if not isinstance(spec, dict) or not _nonempty(spec.get("axis")):
        rep.fail(10, "[spec].axis must be a nonempty string")
    if not isinstance(spec, dict) or not _nonempty(spec.get("path")):
        rep.unknowns.append("missing inventory: [spec].path must name a file")
        return rep
    if not isinstance(conf, dict) or not _nonempty(conf.get("applicability_record")):
        rep.unknowns.append("missing applicability record: [conformance].applicability_record must name a file")
        return rep
    try:
        manifest = path.resolve()
    except (OSError, ValueError, RuntimeError) as exc:
        rep.unknowns.append(f"cannot resolve manifest: {str(exc)!r}")
        return rep
    repo_root = _repository_root(rep, manifest, root)
    if repo_root is None:
        return rep
    inventory_path = _document_path(rep, manifest, repo_root, spec["path"], "[spec].path")
    record_path = _document_path(rep, manifest, repo_root, conf["applicability_record"], "[conformance].applicability_record")
    _check_legacy_lineage(rep, doc, conf)
    inventory_loaded = _read_toml(rep, inventory_path, "inventory") if inventory_path is not None else None
    record_loaded = _read_toml(rep, record_path, "applicability record") if record_path is not None else None
    for loaded_doc, label in ((inventory_loaded, "inventory"), (record_loaded, "applicability record")):
        if loaded_doc is not None:
            _check_aggregates(rep, loaded_doc[0], label)
    if inventory_loaded is None or record_loaded is None:
        return rep
    inventory, inventory_raw = inventory_loaded
    record, record_raw = record_loaded
    clauses = inventory.get("clause")
    if not isinstance(clauses, list) or not clauses or not all(
        isinstance(row, dict) and _nonempty(row.get("id")) for row in clauses
    ):
        rep.unknowns.append("unusable inventory: expected nonempty [[clause]] rows with string ids")
        return rep
    ids = [row["id"] for row in clauses]
    inventory_ids = set(ids)
    if len(inventory_ids) != len(ids):
        rep.fail(1, "duplicate inventory clause id")

    claims = doc.get("claim", [])
    if not isinstance(claims, list):
        rep.fail(1, "claims must be [[claim]] rows")
        claims = []
    by_clause: dict[str, list[dict]] = {}
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict) or not _nonempty(claim.get("clause")):
            rep.fail(1, f"claim[{index}] must cite an inventory clause")
            continue
        clause = claim["clause"]
        by_clause.setdefault(clause, []).append(claim)
        if clause not in inventory_ids:
            rep.fail(1, f"claim cites clause outside inventory: {clause!r}")
    for clause in sorted(inventory_ids):
        count = len(by_clause.get(clause, []))
        if count != 1:
            rep.fail(1, f"inventory clause {clause!r} has {count} claims; expected exactly one")
    coverage = doc.get("coverage")
    for key in ("clauses_total", "claims_total"):
        value = coverage.get(key) if isinstance(coverage, dict) else None
        if type(value) is not int or value != len(clauses):
            rep.fail(1, f"[coverage].{key} must equal inventory row count {len(clauses)}, got {value!r}")

    # C6 narrows the class default (core.md check_spec allows provenance = "in-tree");
    # the wire-format and digest-recomputation checks below that are duplicate of
    # `check_core.check_spec`'s own [spec].path/[spec].version handling under
    # provenance = "external" are deliberately NOT restated here (the 0.2 lowering pass's
    # de-duplication: check_core.check_spec recomputes the normative-reference: digest for
    # provenance = 'external' under EVERY profile; conformance's C6 lifts to class).
    if spec.get("provenance") != "external":
        rep.fail(6, "[spec].provenance must be 'external'")

    # C7 narrows the class default the same way (core.md check_documents only recomputes
    # [conformance].applicability_hash's digest when the field is already present; this
    # meaning additionally REQUIRES it). The digest-recomputation-when-present duplicate
    # is not restated here (the 0.2 lowering pass's de-duplication).
    if not _nonempty(conf.get("applicability_hash")):
        rep.fail(7, "applicability_hash must be a nonempty applicability-record:sha-512:<128-hex> string")
    declared_at = record.get("declared_at")
    manifest_declared_at = conf.get("applicability_declared_at")
    if not _rfc3339(declared_at):
        rep.fail(7, "applicability record declared_at must be an RFC 3339-shaped string")
    if not _rfc3339(manifest_declared_at):
        rep.fail(7, "[conformance].applicability_declared_at must be an RFC 3339-shaped string")
    if declared_at != manifest_declared_at:
        rep.fail(7, "declaration timestamps differ: record declared_at != [conformance].applicability_declared_at")
    standard = inventory.get("standard")
    standard_id = standard.get("id") if isinstance(standard, dict) else None
    if not _nonempty(standard_id) or not (
        record.get("standard") == standard_id == conf.get("standard")
    ):
        rep.fail(7, "standard must match in applicability record, inventory [standard].id and [conformance]")

    rows = record.get("row")
    if not isinstance(rows, list):
        rep.fail(7, "applicability record must contain [[row]] entries")
        rows = []
    by_row: dict[str, list[dict]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not _nonempty(row.get("clause")):
            rep.fail(7, f"applicability row[{index}] must cite an inventory clause")
            continue
        clause = row["clause"]
        by_row.setdefault(clause, []).append(row)
        if clause not in inventory_ids:
            rep.fail(7, f"applicability row outside inventory: {clause!r}")
        if row.get("applicability") not in APPLICABILITY:
            rep.fail(7, f"applicability row {clause!r} has invalid applicability")
        if not isinstance(row.get("reason", ""), str):
            rep.fail(7, f"applicability row {clause!r} reason must be a string")
    for clause in sorted(inventory_ids):
        count = len(by_row.get(clause, []))
        if count != 1:
            rep.fail(7, f"inventory clause {clause!r} has {count} applicability rows; expected exactly one")

    for claim in claims:
        if not isinstance(claim, dict):
            continue
        clause = claim.get("clause")
        context = f"claim {claim.get('id', clause)!r}"
        if claim.get("clause_source") not in ("external-standard", "spec-document"):
            rep.fail(10, f"{context}: clause_source must be 'external-standard' or 'spec-document'")
        applicability = claim.get("applicability")
        reason = claim.get("applicability_reason", "")
        if applicability not in APPLICABILITY:
            rep.fail(2, f"{context}: invalid applicability {applicability!r}")
        if not isinstance(reason, str) or (
            applicability in ("not-applicable", "excluded") and not reason.strip()
        ):
            rep.fail(2, f"{context}: applicability_reason must be a nonempty string for not-applicable/excluded")
        matches = by_row.get(clause, []) if isinstance(clause, str) else []
        if len(matches) == 1:
            row = matches[0]
            if applicability != row.get("applicability") or reason != row.get("reason", ""):
                rep.fail(7, f"{context}: applicability/reason drift from record row {clause!r}")

        evidence = claim.get("evidence", [])
        if applicability in ("not-applicable", "excluded"):
            rule = 3 if applicability == "not-applicable" else 4
            if evidence:
                rep.fail(rule, f"{context}: {applicability} clause must carry no evidence")
            # B5 owns status pairing. Excluded retains the C4 companions.
            if applicability == "excluded" and claim.get("grade") != OUT_OF_SCOPE:
                rep.fail(rule, f"{context}: {applicability} requires grade='out-of-scope'")
            if claim.get("weight", UNWEIGHTED) != UNWEIGHTED:
                rep.fail(rule, f"{context}: {applicability} must be unweighted")
            if applicability == "excluded" and not _nonempty(claim.get("scope_ref")):
                rep.fail(rule, f"{context}: {applicability} requires nonempty scope_ref")
            if not _nonempty(reason):
                rep.fail(rule, f"{context}: {applicability} requires nonempty applicability_reason")
        if applicability == "applicable" and not evidence and claim.get("status") != GAP:
            rep.fail(5, f"{context}: applicable clause without evidence requires status='gap'")
        if applicability == "applicable" and claim.get("grade") == OUT_OF_SCOPE:
            rep.fail(5, f"{context}: applicable clause must not have grade='out-of-scope'")

    rep.counts = dict.fromkeys(rep.counts, 0)
    # Iterate the inventory, not the claims; duplicates/outside rows never inflate counts.
    for clause in inventory_ids:
        record_rows = by_row.get(clause, [])
        if len(record_rows) == 1 and record_rows[0].get("applicability") in APPLICABILITY:
            rep.counts[record_rows[0]["applicability"]] += 1
        claim_rows = by_clause.get(clause, [])
        if len(claim_rows) == 1:
            status = claim_rows[0].get("status")
            # The 0.2 lowering pass (0.2 counts migration): a not-applicable-status claim is
            # no longer pooled into gap -- the applicability<=>status pairing it adopted means
            # it is already counted, in its own column, by the applicability tally
            # above. B5: "reported in its own column, never pooled with gap."
            if status in ("evidenced", GAP):
                rep.counts[status] += 1
    return rep


def check(doc, ctx):
    from check_core import Finding, Reporter
    rep = _evaluate(doc, ctx.path, root=ctx.root)
    shared = Reporter(str(ctx.path))
    controls = []
    for claim in doc.get("claim", []) if isinstance(doc.get("claim", []), list) else []:
        if not isinstance(claim, dict):
            continue
        if claim.get("weight") == "weighted":
            label = f"claim {claim.get('id')!r}"
            check_recipe_requirements(shared, label, claim)
            check_grade_companions(shared, label, claim)
        evidence = claim.get("evidence", [])
        evs = [ev for ev in evidence if isinstance(ev, dict)] if isinstance(evidence, list) else []
        effective_band = claim.get("band", LADDER["tokens"][0])
        if claim.get("status") == "evidenced" and effective_band in verification.BANDS and evs and not any(ev.get("family") == "reference" for ev in evs):
            verification.check_band_reachability(shared, f"claim {claim.get('id')!r}",
                {**claim, "band": effective_band}, evs)
        # verification exposes its control-kind check inside check(), not as a
        # standalone helper. A control-only projection reuses that exact check
        # while species and carrier checks above consume the real claim.
        controls.append({"id": claim.get("id"), "evidence": [
            {"control": ev["control"]} for ev in evs if "control" in ev
        ]})
    def owner(message):
        return next((c.get("id") for c in doc.get("claim", []) if isinstance(c, dict)
                     and (message.startswith(f"claim {c.get('id')!r}") or f": claim {c.get('id')!r}:" in message)), None)
    return ([Finding("error", m, owner(m)) for m in rep.failures + shared.errors]
            + [Finding("warning", m) for m in rep.warnings + shared.warnings]
            + [Finding("unknown", m) for m in rep.unknowns]
            + verification.check({"claim": controls}, ctx))


def validate(path: Path, *, root: Path | None = None, meaning_only: bool = False) -> Report:
    import check_core
    # Do not use bound_meaning: that compatibility option intentionally removes
    # binding suffixes. Native dispatch must preserve the selected leaf.
    core = check_core.validate(path, False, root=root, meaning_only=meaning_only)
    rep = _evaluate(core.doc, path, root=root) if core.doc else Report(path)
    rep.failures = list(core.errors)
    rep.unknowns = list(core.unknowns)
    rep.warnings = list(core.warnings)
    rep.composed_verdict = check_core.verdict(core)[0]
    fmt = core.doc.get("format")
    profile = fmt.get("profile", "") if isinstance(fmt, dict) else ""
    if not (isinstance(profile, str) and (profile == MEANING or profile.startswith(MEANING + "/"))):
        rep.unknowns.append(f"not this check's profile: {profile!r}")
        rep.composed_verdict = "INDETERMINATE"
    rep.notes.extend(getattr(core, "notes", []))
    if getattr(core, "scope_meaning", False):
        rep.notes.append("meaning-only: binding identity and the token⇒tier table were NOT checked")
    return rep


# Selftest fixtures are deliberately independent of the checked-in examples.
# JSON string literals are TOML-compatible for these small ASCII fixtures.
def _toml_value(value) -> str:
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{json.dumps(k)} = {_toml_value(v)}" for k, v in value.items()) + " }"
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    return json.dumps(value)


def _toml_bytes(doc: dict) -> bytes:
    return ("\n".join(f"{json.dumps(k)} = {_toml_value(v)}" for k, v in doc.items()) + "\n").encode()


def _fixture_record(number: int) -> bytes:
    return (json.dumps({"synthetic": True, "clause": number}) + "\n").encode()


# The B8 source manifest this fixture's two evidenced claims reference (the 0.2 lowering pass: the
# generator's replacement for the retired source_claim/source_manifest encoding).
# Its own evidence records live under distinct numbers (101, 105) so they never
# collide on disk with the conformance manifest's own evidence/record-{1,5}.json.
SOURCE_MANIFEST_NAME = "source.acceptance.toml"
SOURCE_RECORD_NUMBERS = {"PM/wire": 101, "PM/length": 105}


def _source_fixture() -> dict:
    claims = []
    # A1 is kani-harness's control-free ceiling (verification.LADDER); no control needed.
    for claim_id, band, number in (("PM/wire", "A1", 101), ("PM/length", "A0", 105)):
        claims.append({
            "id": claim_id, "clause": "1" if claim_id == "PM/wire" else "2",
            "item": f"src/lib.rs::{claim_id.split('/')[1]}", "statement": f"{claim_id} verified",
            "status": "evidenced", "grade": "contract", "weight": UNWEIGHTED, "band": band,
            "evidence": [{
                "kind": "kani-harness", "family": "bmc", "ref": f"wire::check_{number}",
                "result": "pass", "tool": "fictional-kani@0000000", "bounds": "unwind=8",
                "semantics": "", "record": f"evidence/source-record-{number}.json",
                "record_hash": hashdomains.digest("record:", _fixture_record(number)),
            }],
        })
    return {
        "format": {"id": "acceptance/0", "profile": "acceptance/verification"},
        "subject": {"name": "example-wire-source", "kind": "doc",
                    "digest": hashdomains.digest("subject:", b"example-wire-source")},
        "spec": {"path": "SOURCE-SPEC.md", "version": "v1", "axis": "source module assertions"},
        "coverage": {"clauses_total": 2, "claims_total": 2},
        "claim": claims,
    }


def _reference_evidence(claim_id: str) -> dict:
    """A B8 `acceptance-claim` reference row citing `claim_id` in the fixture's
    source manifest (core.md B8); `record_hash`/`manifest_hash` are filled by
    `_bind_source_fixture` once the source's actual bytes are known."""
    return {
        "kind": "acceptance-claim", "family": "reference",
        "ref": f"{SOURCE_MANIFEST_NAME}#{claim_id}", "result": "pass",
        "tool": "gen_conformance_manifest.py@0.2.0",
        "record": SOURCE_MANIFEST_NAME, "record_hash": "",
        "manifest": SOURCE_MANIFEST_NAME, "manifest_hash": "",
        "claim": claim_id,
    }


def _green_fixture() -> dict:
    inventory = {"standard": {"id": "example-wire-format-1"}, "clause": [
        {"id": f"EWF-{i}"} for i in range(1, 6)
    ]}
    applicability = ["applicable", "applicable", "not-applicable", "excluded", "applicable"]
    reasons = ["", "", "Decoder only", "Deferred this revision", ""]
    record = {"standard": "example-wire-format-1", "declared_at": "2026-09-21T08:00:00Z", "row": [
        {"clause": f"EWF-{i}", "applicability": app, "reason": reason}
        for i, (app, reason) in enumerate(zip(applicability, reasons), 1)
    ]}
    doc = {
        # F1: `rust-crate` is no longer a base-registry token (B14, revision L1); this fixture predates
        # a declared binding, so it names the kind through the declared-extension mechanism
        # instead of a code/rust profile suffix.
        "format": {"id": "acceptance/0", "profile": MEANING, "profile_version": "0.2.0",
                   "kind_registry": ["rust-crate", "rust-workspace"]},
        "subject": {"name": "example-wire-crate", "kind": "rust-crate", "commit": "0" * 40, "dirty": False},
        "spec": {"path": "standard.clauses.toml", "provenance": "external", "version": "", "axis": "one claim per invented clause"},
        "coverage": {"clauses_total": 5, "claims_total": 5},
        "conformance": {"standard": "example-wire-format-1", "applicability_record": "applicability.toml", "applicability_hash": "", "applicability_declared_at": record["declared_at"]},
        "claim": [],
    }
    # claim 1 (EWF-1) borrows from PM/wire, claim 5 (EWF-5) from PM/length — the same
    # two-source shape the legacy source_claim/source_claims_other lane exercised.
    reference_source = {1: "PM/wire", 5: "PM/length"}
    for i, (app, reason) in enumerate(zip(applicability, reasons), 1):
        claim = {"id": f"CONF/EWF-{i}", "clause": f"EWF-{i}", "item": f"src/lib.rs::clause_{i}",
                 "statement": "Invented example clause", "band": "A0", "status": GAP,
                 "grade": OUT_OF_SCOPE if app in ("not-applicable", "excluded") else "ungraded",
                 "weight": UNWEIGHTED, "clause_source": "external-standard",
                 "applicability": app, "applicability_reason": reason}
        if app == "not-applicable":
            claim["status"] = "not-applicable"
            claim.pop("grade")
        if app == "excluded":
            claim["scope_ref"] = "applicability.toml"
        if i in reference_source:
            claim.update(status="evidenced", evidence=[_reference_evidence(reference_source[i])])
        doc["claim"].append(claim)
    fixture = {"manifest": doc, "inventory": inventory, "record": record, "source": _source_fixture()}
    _bind_fixture(fixture)
    return fixture


def _native_evidence(number: int) -> dict:
    """A NATIVE (non-reference) kani-harness evidence record, independent of the
    B8 lowering; record/record_hash match what `_run_case` always writes to disk
    for numbers 1 and 5 (`evidence/record-{number}.json`)."""
    return {
        "kind": "kani-harness", "family": "bmc", "ref": f"wire::check_{number}",
        "result": "pass", "tool": "fictional-kani@0000000", "bounds": "unwind=8",
        "semantics": "", "record": f"evidence/record-{number}.json",
        "record_hash": hashdomains.digest("record:", _fixture_record(number)),
    }


def _native_claim_fixture() -> dict:
    """`_green_fixture()`-shaped, but claims 1 and 5 carry NATIVE evidence instead
    of the default B8 reference rows: for binding-level tests (kind/family/tier,
    cover-only, build_inputs, controls …) that manipulate a native evidence record
    directly and have nothing to do with the B8 lowering itself. Sidesteps needing
    the source-manifest scaffolding (`_run_case`'s SOURCE-SPEC.md/source-record
    files) these callers' own minimal setups do not write."""
    fixture = copy.deepcopy(_green_fixture())
    for index, number in ((0, 1), (4, 5)):
        fixture["manifest"]["claim"][index]["evidence"] = [_native_evidence(number)]
    fixture["source"] = None
    _bind_fixture(fixture)
    return fixture


def _bind_fixture(fixture: dict) -> None:
    # Independent construction, not calls to the checker's digest helpers.
    raw = _toml_bytes(fixture["inventory"])
    fixture["manifest"]["spec"]["version"] = "normative-reference:sha-512:" + hashlib.sha512(b"normative-reference:" + raw).hexdigest()
    fixture["manifest"]["conformance"]["applicability_hash"] = "applicability-record:sha-512:" + hashlib.sha512(b"applicability-record:" + _toml_bytes(fixture["record"])).hexdigest()
    if fixture.get("source") is not None:
        _bind_source_fixture(fixture)


def _bind_source_fixture(fixture: dict) -> None:
    """Fill every B8 acceptance-claim evidence row's manifest_hash/record_hash from
    the source fixture's actual serialized bytes, and its `records` list from the
    named source claim's own (already record:-domain-typed) evidence record_hash
    values — B8 step 4's membership check is exact-string, so this MUST read the
    live source, not recompute independently."""
    source = fixture["source"]
    raw = source if isinstance(source, bytes) else _toml_bytes(source)
    wire = source_manifest_digest(raw)
    by_id = ({c["id"]: c for c in source.get("claim", []) if isinstance(c, dict)}
             if isinstance(source, dict) else {})
    for claim in fixture["manifest"]["claim"]:
        for ev in claim.get("evidence", []):
            if not (isinstance(ev, dict) and ev.get("kind") == "acceptance-claim"):
                continue
            ev.update(manifest_hash=wire, record_hash=wire)
            source_claim = by_id.get(ev.get("claim"))
            if source_claim is not None:
                ev["records"] = [e["record_hash"] for e in source_claim.get("evidence", [])
                                 if isinstance(e, dict) and "control" not in e and _nonempty(e.get("record_hash"))]


def _run_case(name: str, fixture: dict, expect_verdict: str, expect_substr: str) -> str | None:
    from unittest.mock import patch

    if not expect_substr:
        return f"{name}: fixture must specify an expected diagnostic substring"
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        base = repo / "packages" / "example"
        base.mkdir(parents=True)
        root_mode = fixture.get("root_mode", "discover")
        if root_mode in ("discover", "nearest"):
            (repo / ".git").mkdir()
        if root_mode in ("nearest", "override-nearest"):
            (base / ".git").mkdir()
        if root_mode == "worktree":
            (repo / ".git").write_text("gitdir: /synthetic/gitdir\n")
        root = repo if root_mode in ("override", "override-nearest") else None
        if root_mode == "invalid-override":
            root = repo / "missing-root"
        meaning_only = fixture.get("meaning_only", False)
        for key, filename in (("inventory", "standard.clauses.toml"), ("record", "applicability.toml"), ("source", "source.acceptance.toml")):
            value = fixture[key]
            if value is not None:
                (base / filename).write_bytes(value if isinstance(value, bytes) else _toml_bytes(value))
        if "path_case" in fixture:
            section, key, kind = fixture["path_case"]
            original = base / fixture["manifest"][section][key]
            if kind == "absolute":
                value = str(original.resolve())
            elif kind == "inside":
                shared = repo / "shared"
                shared.mkdir()
                (shared / original.name).write_bytes(original.read_bytes())
                value = "../../shared/" + original.name
            elif kind == "directory-symlink":
                outside_dir = Path(td) / "outside-directory"
                outside_dir.mkdir()
                (outside_dir / original.name).write_bytes(original.read_bytes())
                link = base / "linked-directory"
                link.symlink_to(outside_dir, target_is_directory=True)
                value = link.name + "/" + original.name
            else:
                outside = Path(td) / ("outside-" + original.name)
                outside.write_bytes(original.read_bytes())
                if kind == "escape":
                    value = "../../../" + outside.name
                else:
                    link = base / ("linked-" + original.name)
                    link.symlink_to(outside)
                    value = link.name
            fixture["manifest"][section][key] = value
        manifest = fixture["manifest"]
        if manifest is not None:
            (base / "acceptance.toml").write_bytes(manifest if isinstance(manifest, bytes) else _toml_bytes(manifest))
        (base / "evidence").mkdir()
        for number in (1, 5):
            (base / f"evidence/record-{number}.json").write_bytes(_fixture_record(number))
        for number in SOURCE_RECORD_NUMBERS.values():
            (base / f"evidence/source-record-{number}.json").write_bytes(_fixture_record(number))
        (base / "SOURCE-SPEC.md").write_text("Source governing document.\n")
        # Some sandboxes mount /tmp/.git. Hide only ambient ancestor markers for
        # the no-root fixture; exercise the real discovery and CLI code unchanged.
        exists = Path.exists

        def fixture_exists(candidate):
            if candidate.name == ".git" and not candidate.is_relative_to(repo):
                return False
            return exists(candidate)

        try:
            with patch.object(Path, "exists", fixture_exists) if root_mode == "absent" else nullcontext():
                rep = validate(base / "acceptance.toml", root=root, meaning_only=meaning_only)
                output = rep.render()
                args = [str(base / "acceptance.toml")]
                if root is not None:
                    args += ["--root", str(root)]
                if meaning_only:
                    args += ["--meaning-only"]
                cli_output = StringIO()
                with redirect_stdout(cli_output):
                    cli_exit = main(args)
        except Exception as exc:
            return f"{name}: checker raised {exc!r}"
        if rep.verdict != expect_verdict:
            return f"{name}: expected {expect_verdict}, got {rep.verdict}: {output}"
        if expect_substr not in output:
            return f"{name}: wanted substring {expect_substr!r}, got: {output}"
        expected_exit = {"PASS": 0, "PASS-PROSPECTIVE": 0, "PASS-MEANING-ONLY": 0, "FAIL": 1, "INDETERMINATE": 2}[expect_verdict]
        if cli_exit != expected_exit or rep.exit_code != expected_exit or cli_output.getvalue() != output + "\n":
            return f"{name}: CLI/library verdict, exit or output mismatch: {cli_exit}, {cli_output.getvalue()!r}"
        if expect_verdict == "PASS-MEANING-ONLY" and "binding identity and the token⇒tier table were NOT checked" not in output:
            return f"{name}: missing meaning-only scope note"
    return None


def selftest() -> int:
    green = _green_fixture()
    cases: list[tuple[str, dict, str, str]] = []

    def case(name, mutate=None, verdict="FAIL", expect_substr="", rebind=False, **options):
        fixture = copy.deepcopy(green)
        if mutate:
            mutate(fixture)
        if rebind:
            _bind_fixture(fixture)
        fixture.update(options)
        cases.append((name, fixture, verdict, expect_substr))

    def claim_set(index, **fields):
        return lambda f: f["manifest"]["claim"][index].update(fields)

    def manifest_set(section, **fields):
        return lambda f: f["manifest"][section].update(fields)

    # The 0.2 lowering pass's counts migration: gap no longer pools not-applicable-status claims (2 real
    # gaps: EWF-2 applicable-gap, EWF-4 excluded-gap; EWF-3's not-applicable status is
    # counted only in the applicability column above, never pooled -- B5).
    case("GREEN base", verdict="PASS", expect_substr="[applicable: 3, not-applicable: 1, excluded: 1; evidenced: 2, gap: 2]")
    case("C1 missing claim", lambda f: f["manifest"]["claim"].pop(), expect_substr="C1: inventory clause 'EWF-5' has 0 claims")
    case("C1 outside clause", claim_set(0, clause="EWF-99"), expect_substr="C1: claim cites clause outside inventory: 'EWF-99'")
    case("C1 duplicate claim", lambda f: f["manifest"]["claim"].append(copy.deepcopy(f["manifest"]["claim"][0])), expect_substr="C1: inventory clause 'EWF-1' has 2 claims")
    case("C1 duplicate inventory", lambda f: f["inventory"]["clause"].append({"id": "EWF-1"}), expect_substr="C1: duplicate inventory clause id", rebind=True)
    for key in ("clauses_total", "claims_total"):
        case(f"C1 wrong {key}", manifest_set("coverage", **{key: 4}), expect_substr=f"C1: [coverage].{key} must equal inventory row count 5")
        case(f"C1 boolean {key}", manifest_set("coverage", **{key: True}), expect_substr=f"C1: [coverage].{key} must equal inventory row count 5")
    case("C2 bad token", claim_set(0, applicability="optional"), expect_substr="C2: claim 'CONF/EWF-1': invalid applicability 'optional'")
    case("C2 missing applicability", lambda f: f["manifest"]["claim"][0].pop("applicability"), expect_substr="C2: claim 'CONF/EWF-1': invalid applicability None")
    for index in (2, 3):
        reason_msg = f"C2: claim 'CONF/EWF-{index + 1}': applicability_reason must be a nonempty string"
        case(f"C2 missing reason {index}", lambda f, i=index: f["manifest"]["claim"][i].pop("applicability_reason"), expect_substr=reason_msg)
        case(f"C2 whitespace reason {index}", claim_set(index, applicability_reason="  "), expect_substr=reason_msg)

    # A separate diagnostic for every sub-condition: siblings cannot mask a missing rule.
    for index, rule, token in ((2, 3, "not-applicable"), (3, 4, "excluded")):
        prefix = f"C{rule}: claim 'CONF/EWF-{index + 1}': {token} "
        for field, value, message in (
            ("evidence", [{"kind": "unit-test"}], "clause must carry no evidence"),
            ("weight", "weighted", "must be unweighted"),
            ("applicability_reason", "", "requires nonempty applicability_reason"),
        ):
            case(f"C{rule} {field}", claim_set(index, **{field: value}), expect_substr=prefix + message)
        case(f"C{rule} status", claim_set(index, status="parked"), expect_substr="B5:")
        case(f"C{rule} grade", claim_set(index, grade="ungraded"), expect_substr="B5:" if rule == 3 else prefix + "requires grade='out-of-scope'")
        case(f"C{rule} scope_ref", claim_set(index, scope_ref="  "),
             "PASS" if rule == 3 else "FAIL", "PASS " if rule == 3 else prefix + "requires nonempty scope_ref")
        case(f"C{rule} absent scope_ref", lambda f, i=index: f["manifest"]["claim"][i].pop("scope_ref", None),
             "PASS" if rule == 3 else "FAIL", "PASS " if rule == 3 else prefix + "requires nonempty scope_ref")
        case(f"C{rule} omitted weight", lambda f, i=index: f["manifest"]["claim"][i].pop("weight"), "PASS", "PASS ")
    case("C5 illegal status", claim_set(1, status="evidenced"), expect_substr="C5: claim 'CONF/EWF-2': applicable clause without evidence requires status='gap'")
    case("C5 out-of-scope applicable", claim_set(1, grade=OUT_OF_SCOPE), expect_substr="C5: claim 'CONF/EWF-2': applicable clause must not have grade='out-of-scope'")
    case("C5 extra legal gap", claim_set(0, evidence=[], status=GAP), "PASS", "evidenced: 1, gap: 3")
    # C6's digest recomputation is now core's job on every profile (check_core.check_spec
    # under provenance = "external"; the 0.2 lowering pass's de-duplication). C6 keeps only the
    # meaning-specific narrowing (provenance MUST be "external"); the mismatch itself
    # is confirmed end to end below, with the message core now owns (no more "C6:" wrap).
    case("C6 digest mismatch fails closed via core B6 (de-duplicated)", manifest_set("spec", version="normative-reference:sha-512:" + "0" * 128), expect_substr="B6: spec.path: digest differs from declared normative-reference: hash")
    case("C6 invalid provenance", manifest_set("spec", provenance="invented"), expect_substr="C6: [spec].provenance must be 'external'")
    case("R9 in-tree provenance", manifest_set("spec", provenance="in-tree", version="v1"), "INDETERMINATE", "in-tree conformance standards not implemented in 0.1.0-draft")
    case("R9 omitted provenance", lambda f: f["manifest"]["spec"].pop("provenance"), "INDETERMINATE", "in-tree conformance standards not implemented in 0.1.0-draft")
    # C7's digest recomputation is likewise core's job now (check_core.check_documents;
    # the 0.2 lowering pass's de-duplication). C7 keeps only the meaning-specific "must be present" narrowing
    # (core only recomputes when applicability_hash is already present); the mismatch
    # itself is confirmed end to end, with the message core now owns.
    case("C7 applicability_hash required", lambda f: f["manifest"]["conformance"].pop("applicability_hash"), expect_substr="C7: applicability_hash must be a nonempty applicability-record:sha-512:<128-hex> string")
    case("C7 digest mismatch fails closed via core B6 (de-duplicated)", manifest_set("conformance", applicability_hash="applicability-record:sha-512:" + "0" * 128), expect_substr="B6: conformance.applicability_record: digest differs from declared applicability-record: hash")
    case("C7 drifted applicability", lambda f: f["record"]["row"][0].update(applicability="excluded", reason="Deferred"), expect_substr="C7: claim 'CONF/EWF-1': applicability/reason drift from record row 'EWF-1'", rebind=True)
    case("C7 drifted reason", claim_set(2, applicability_reason="Different reason"), expect_substr="C7: claim 'CONF/EWF-3': applicability/reason drift from record row 'EWF-3'")
    case("C7 missing row", lambda f: f["record"]["row"].pop(), expect_substr="C7: inventory clause 'EWF-5' has 0 applicability rows", rebind=True)
    case("C7 duplicate row", lambda f: f["record"]["row"].append(copy.deepcopy(f["record"]["row"][0])), expect_substr="C7: inventory clause 'EWF-1' has 2 applicability rows", rebind=True)
    case("C7 outside row", lambda f: f["record"]["row"].append({"clause": "EWF-99", "applicability": "applicable", "reason": ""}), expect_substr="C7: applicability row outside inventory: 'EWF-99'", rebind=True)
    for location in ("record", "inventory", "manifest"):
        def change_standard(f, location=location):
            if location == "inventory":
                f[location]["standard"]["id"] = "different-standard"
            elif location == "record":
                f[location]["standard"] = "different-standard"
            else:
                f[location]["conformance"]["standard"] = "different-standard"
        case(f"C7 standard {location}", change_standard, expect_substr="C7: standard must match in applicability record, inventory [standard].id and [conformance]", rebind=True)

    for location in ("record", "manifest"):
        key = "declared_at" if location == "record" else "applicability_declared_at"
        label = "applicability record declared_at" if location == "record" else "[conformance].applicability_declared_at"
        def timestamp(f, value=None, location=location, key=key):
            target = f["record"] if location == "record" else f["manifest"]["conformance"]
            if value is None:
                target.pop(key)
            else:
                target[key] = value
        case(f"R6 missing {location} time", timestamp, expect_substr=f"C7: {label} must be an RFC 3339-shaped string", rebind=True)
        for value in ("not-a-time", "2026-09-21", "2026-09-21T08:00:00", "2026-02-30T08:00:00Z", "2026-09-21T08:00:00+25:00"):
            case(f"R6 malformed {location} time {value}", lambda f, t=value, mutate=timestamp: mutate(f, t), expect_substr=f"C7: {label} must be an RFC 3339-shaped string", rebind=True)
    case("R6 unequal times", manifest_set("conformance", applicability_declared_at="2026-09-21T09:00:00Z"), expect_substr="C7: declaration timestamps differ: record declared_at != [conformance].applicability_declared_at")
    def offset_times(f):
        value = "2026-09-21T10:00:00.123+02:00"
        f["record"]["declared_at"] = value
        f["manifest"]["conformance"]["applicability_declared_at"] = value
    case("R6 matching offset and fraction", offset_times, "PASS", "PASS ", rebind=True)

    def binding_case(name, mutate=None, *args, **kwargs):
        def change(f):
            f["manifest"]["format"]["profile"] = MEANING + "/code/rust"
            # These tests manipulate claim[0]'s evidence record directly (cover-only,
            # tally …) and have nothing to do with the B8 lowering the GREEN fixture's
            # claim[0] otherwise carries; start from a native evidence record.
            f["manifest"]["claim"][0]["evidence"] = [_native_evidence(1)]
            if mutate:
                mutate(f)
        case(name, change, *args, **kwargs)

    def weight_fixture(claim):
        claim.update(weight="weighted", grade="probe", bounds="bounded fixture inputs",
                     self_verify={"command": "cargo kani", "expect": "SUCCESS"})

    def evidence_fixture(ev):
        result = _native_evidence(1)
        result.update(ev)
        if result["kind"] == "unit-test":
            result.update(family="dynamic", cases=1)
        return result

    def standalone_cover(evidence):
        def change(f):
            claim = f["manifest"]["claim"][0]
            weight_fixture(claim)
            claim["evidence"] = [evidence_fixture(e) for e in evidence]
        return change

    def cover(f, tally=None, listed=False, extra=None, weighted=True):
        claim = f["manifest"]["claim"][0]
        if weighted:
            weight_fixture(claim)
        else:
            claim["weight"] = UNWEIGHTED
        ev = claim["evidence"][0]
        ev["ref"] = "wire::custom_cover"
        if not listed:
            ev["cover_only"] = True
        if listed:
            f["manifest"]["conformance"]["cover_only"] = [ev["ref"]]
        if tally is not None:
            ev["cover_tally"] = tally
        if extra:
            claim["evidence"].append(evidence_fixture(extra))

    cover_msg = "C8: weighted cover-only kani evidence forbidden"
    binding_case("C8 weighted cover-only", cover, expect_substr=cover_msg)
    binding_case("C8 explicit list", lambda f: cover(f, listed=True), expect_substr=cover_msg)
    binding_case("R1 former full tally escape is RED", lambda f: cover(f, tally="1 of 1"), expect_substr=cover_msg)
    binding_case("C8 partial tally", lambda f: cover(f, tally="0 of 1"), expect_substr=cover_msg)
    binding_case("C8 all tallied still RED", lambda f: cover(f, tally="1 of 1", extra={"kind": "kani-harness", "ref": "wire/other_cover", "cover_only": True, "cover_tally": "2 of 2"}), expect_substr=cover_msg)
    binding_case("C8 mixed harnesses", lambda f: cover(f, extra={"kind": "kani-harness", "ref": "wire::assertion"}), "PASS", "PASS ")
    binding_case("C8 dynamic evidence does not excuse cover-only", lambda f: cover(f, extra={"kind": "unit-test", "ref": "unit_test"}), expect_substr=cover_msg)
    binding_case("C8 unweighted allowed", lambda f: cover(f, weighted=False), "PASS", "PASS ")
    binding_case("C8 zero kani harnesses", standalone_cover([{"kind": "unit-test"}]), "PASS", "PASS ")
    binding_case("C8 parent path is not harness name", standalone_cover([{"kind": "kani-harness", "ref": "wire_witnessed/check"}]), "PASS", "PASS ")
    tally_msg = "C8: manifest-side cover_tally is not accepted (open question C4: record-level): manifest"
    binding_case("R1 top-level tally", lambda f: f["manifest"].update(cover_tally="1 of 1"), expect_substr=tally_msg + ".cover_tally")
    binding_case("R1 claim tally without evidence", claim_set(1, cover_tally="1 of 1"), expect_substr=tally_msg + ".claim[1].cover_tally")
    binding_case("R1 unweighted evidence tally", lambda f: cover(f, tally="1 of 1", weighted=False), expect_substr=tally_msg + ".claim[0].evidence[0].cover_tally")
    binding_case("R1 mixed harness tally", lambda f: cover(f, tally="1 of 1", extra={"kind": "kani-harness", "ref": "wire::assertion"}), expect_substr=tally_msg + ".claim[0].evidence[0].cover_tally")
    binding_case("R1 arbitrary table tally", manifest_set("subject", cover_tally=False), expect_substr=tally_msg + ".subject.cover_tally")
    binding_case("R1 nested array tally", manifest_set("conformance", nested=[{"details": {"cover_tally": "1 of 1"}}]), expect_substr=tally_msg + ".conformance.nested[0].details.cover_tally")
    binding_case("R1 key spelling in prose is legal", claim_set(0, statement="cover_tally is not accepted"), "PASS", "PASS ")

    # C9's manifest-wide scan is now core's job on every profile (check_core.check_no_aggregates
    # over the full manifest doc, called unconditionally by check_core.validate; the 0.2 lowering pass
    # de-duplication). Confirmed end to end, with the message core now owns (B7, not C9),
    # instead of restating a manifest-side fixture per aggregate key/location here. C9 keeps
    # only the inventory/applicability-record checks below — profile-declared assertion
    # surfaces core does not see.
    case("C9 manifest aggregate fails closed via core B7 (de-duplicated)", claim_set(0, score=1), expect_substr="B7: aggregate key manifest.claim[0].score is forbidden")
    case("C9 record percent", lambda f: f["record"].update(percent=1), expect_substr="C9: aggregate key forbidden: applicability record.percent", rebind=True)
    case("C9 record row percentage", lambda f: f["record"]["row"][0].update(percentage=1), expect_substr="C9: aggregate key forbidden: applicability record.row[0].percentage", rebind=True)
    case("C9 inventory conformance_level", lambda f: f["inventory"]["clause"][0].update(conformance_level="full"), expect_substr="C9: aggregate key forbidden: inventory.clause[0].conformance_level", rebind=True)

    case("C10 missing axis", lambda f: f["manifest"]["spec"].pop("axis"), expect_substr="C10: [spec].axis must be a nonempty string")
    case("C10 empty axis", manifest_set("spec", axis="  "), expect_substr="C10: [spec].axis must be a nonempty string")
    case("C10 non-string axis", manifest_set("spec", axis=1), expect_substr="C10: [spec].axis must be a nonempty string")
    for index in range(5):
        msg = f"C10: claim 'CONF/EWF-{index + 1}': clause_source must be 'external-standard' or 'spec-document'"
        case(f"C10 missing clause_source {index}", lambda f, i=index: f["manifest"]["claim"][i].pop("clause_source"), expect_substr=msg)
        case(f"C10 doc-comment {index}", claim_set(index, clause_source="doc-comment"), expect_substr=msg)
    case("C10 spec-document allowed", claim_set(0, clause_source="spec-document"), "PASS", "PASS ")

    # B8 lowering (the 0.2 lowering pass): the GREEN fixture itself already carries two real B8
    # acceptance-claim reference rows (claim 1 cites PM/wire, claim 5 cites
    # PM/length) — "GREEN base" above is this mechanism's own end-to-end PASS
    # fixture. These cases cover what conformance's own C8 delta adds: the
    # legacy source_claim/source_claims_other/[conformance].source_manifest{,_hash}
    # fields are no longer READ (no C11 validation of them runs at any version),
    # flagged the same way B5/B9's legacy encodings are: WARNING under an
    # explicitly declared 0.1.0-draft (so the nine pre-lowering companion subjects
    # do not break before their own regeneration), ERROR at GREEN's 0.2.0
    # default and everywhere else. Everything about the reference row itself
    # (hash membership, band ceilings, cycles, control stripping, tier
    # derivation …) is core's own mechanism (`check_core.check_reference_evidence`)
    # and is exercised by its own b8-* fixtures, not restated here.
    for key in LEGACY_LINEAGE_TABLE_FIELDS:
        case(f"C8 legacy [conformance].{key} rejected at 0.2", manifest_set("conformance", **{key: "source.acceptance.toml"}),
             expect_substr=f"C8: [conformance].{key} is retired at conformance 0.2; cite the source claim "
                           "with a class B8 acceptance-claim evidence entry instead (core.md B8)")
    case("C8 legacy claim source_claim rejected at 0.2", claim_set(2, source_claim="PM/wire"),
         expect_substr="C8: claim 'CONF/EWF-3': 'source_claim' is retired at conformance 0.2; cite the "
                       "source claim with a class B8 acceptance-claim evidence entry instead (core.md B8)")
    case("C8 legacy claim source_claims_other rejected at 0.2", claim_set(2, source_claims_other=["PM/wire"]),
         expect_substr="C8: claim 'CONF/EWF-3': 'source_claims_other' is retired at conformance 0.2; "
                       "cite the source claim with a class B8 acceptance-claim evidence entry instead (core.md B8)")

    def legacy_field_at_0_1(f):
        f["manifest"]["format"]["profile_version"] = "0.1.0-draft"
        claim_set(2, source_claim="PM/wire")(f)
    case("C8 legacy claim field is a WARNING only under declared 0.1.0-draft", legacy_field_at_0_1, "PASS",
         "C8: claim 'CONF/EWF-3': 'source_claim' is deprecated dead metadata (no C11 validation runs)")

    def legacy_table_at_0_1(f):
        f["manifest"]["format"]["profile_version"] = "0.1.0-draft"
        f["manifest"]["conformance"]["source_manifest"] = "source.acceptance.toml"
    case("C8 legacy [conformance].source_manifest is a WARNING only under declared 0.1.0-draft", legacy_table_at_0_1, "PASS",
         "C8: [conformance].source_manifest is deprecated dead metadata (no C11 validation runs)")

    def multi_reference(f):
        f["manifest"]["claim"][0]["evidence"].append(_reference_evidence("PM/length"))
    case("B8 a claim may cite more than one source claim (two reference rows)", multi_reference, "PASS", "PASS ", rebind=True)

    def missing_source(f):
        f["source"] = None
    case("B8 missing source manifest is INDETERMINATE", missing_source, "INDETERMINATE", "B8: unreadable source manifest")

    for section, key in (("spec", "path"), ("conformance", "applicability_record")):
        for kind in ("absolute", "escape", "symlink", "directory-symlink"):
            message = "absolute path forbidden" if kind == "absolute" else "path escapes repository root"
            case(f"R2 {key} {kind} fails closed via core B6 (de-duplicated)",
                 expect_substr=f"B6: {'spec.path' if section == 'spec' else 'conformance.applicability_record'}: {message}",
                 path_case=(section, key, kind))
        case(f"R2 {key} .. within root", verdict="PASS", expect_substr="PASS ", path_case=(section, key, "inside"))
    case("R2 nearest ancestor wins", expect_substr="B6: spec.path: path escapes repository root", path_case=("spec", "path", "inside"), root_mode="nearest")
    case("R2 .git file is a root marker", verdict="PASS", expect_substr="PASS ", root_mode="worktree")
    case("R2 root override without .git", verdict="PASS", expect_substr="PASS ", root_mode="override")
    case("R2 override takes precedence over nearest .git", verdict="INDETERMINATE", expect_substr="--root cannot widen", path_case=("spec", "path", "inside"), root_mode="override-nearest")
    case("R2 override still confines references", expect_substr="B6: spec.path: path escapes repository root", path_case=("spec", "path", "escape"), root_mode="override")
    case("R2 invalid override", verdict="INDETERMINATE", expect_substr="--root cannot widen", root_mode="invalid-override")
    case("R2 no root", verdict="INDETERMINATE", expect_substr="no repository root found; supply --root DIR", root_mode="absent")

    case("plain meaning with flag", verdict="PASS", expect_substr="scoping flag ignored: the profile has no binding half; full verdict", meaning_only=True)
    for suffix in ("/code", "/code/rust"):
        # Four combinations per leaf: a green/red meaning, with/without the flag.
        for flag in (False, True):
            case(f"R10 green {suffix} flag={flag}", manifest_set("format", profile=MEANING + suffix),
                 "PASS",
                 "PASS ",
                 meaning_only=flag)
            def red_leaf(f, suffix=suffix):
                f["manifest"]["format"]["profile"] = MEANING + suffix
                f["manifest"]["claim"][2]["evidence"] = [{"kind": "unit-test"}]
            case(f"R10 red {suffix} flag={flag}", red_leaf, expect_substr="C3: claim 'CONF/EWF-3': not-applicable clause must carry no evidence", meaning_only=flag)
    for suffix in ("/unknown", "/code/python", "/code/rust/unknown", "ish"):
        case(f"unknown suffix {suffix}", manifest_set("format", profile=MEANING + suffix), "INDETERMINATE", "B12: unknown")
    case("unknown suffix with flag", manifest_set("format", profile=MEANING + "/unknown"), "INDETERMINATE", "B12: unknown", meaning_only=True)
    case("other profile", manifest_set("format", profile="acceptance/verification"), "INDETERMINATE", "not this check's profile")
    case("no profile", lambda f: f["manifest"]["format"].pop("profile"), "INDETERMINATE", "not this check's profile")
    case("no format", lambda f: f["manifest"].pop("format"), "INDETERMINATE", "not this check's profile")
    for key, label in (("manifest", "manifest"), ("inventory", "inventory"), ("record", "applicability record")):
        for value, description in ((None, "missing"), (b"broken = [", "bad TOML"), (b"\xff", "bad UTF-8")):
            # Bind malformed document bytes so parse failure, not stale hash, is tested.
            def unreadable(f, k=key, v=value):
                f[k] = v
                if isinstance(v, bytes) and k != "manifest":
                    if k == "inventory":
                        f["manifest"]["spec"]["version"] = normative_digest(v)
                    else:
                        f["manifest"]["conformance"]["applicability_hash"] = applicability_digest(v)
            message = ({"missing": "cannot read file", "bad TOML": "TOML parse error", "bad UTF-8": "not valid UTF-8"}[description]
                       if key == "manifest" else f"cannot read/parse {label}")
            case(f"{description} {key}", unreadable, "INDETERMINATE", message)
    case("missing inventory pointer", lambda f: f["manifest"]["spec"].pop("path"), "FAIL", "[spec].path must be a nonempty string")
    case("missing record pointer", lambda f: f["manifest"]["conformance"].pop("applicability_record"), "INDETERMINATE", "missing applicability record")
    case("empty inventory", lambda f: f["inventory"].update(clause=[]), "INDETERMINATE", "unusable inventory", rebind=True)
    case("malformed claims", lambda f: f["manifest"].update(claim=["oops"]), expect_substr="C1: claim[0] must cite an inventory clause")
    case("malformed applicability", claim_set(0, applicability=[]), expect_substr="C2: claim 'CONF/EWF-1': invalid applicability []")
    case("malformed evidence", claim_set(0, evidence=["oops"]), "FAIL", "evidence[0]: must be a table")

    failures = []
    for name, fixture, verdict, expect_substr in cases:
        failure = _run_case(name, fixture, verdict, expect_substr)
        if failure:
            failures.append(failure)
    for failure in failures:
        print(f"SELFTEST FAIL: {failure}", file=sys.stderr)
    from fixtures.binding_cases import CASES, selftest as migration_selftest
    migration_failures = migration_selftest("conformance")
    count = len(cases) + sum(c[0] == "conformance" for c in CASES)
    print(f"selftest: {count} cases, {len(failures) + migration_failures} failures")
    return 1 if failures or migration_failures else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--selftest", action="store_true", help="run embedded able-to-fail fixtures")
    parser.add_argument("--root", type=Path, help="override repository root for document containment")
    parser.add_argument("--meaning-only", action="store_true", help="scope evaluation to the class and conformance meaning")
    parser.add_argument("manifests", metavar="MANIFEST.toml", nargs="*", type=Path)
    args = parser.parse_args(argv)
    if args.selftest:
        if args.manifests or args.root is not None or args.meaning_only:
            parser.error("--selftest cannot be combined with manifests or validation options")
        return selftest()
    if not args.manifests:
        parser.error("at least one manifest is required")
    reports = [validate(path, root=args.root, meaning_only=args.meaning_only) for path in args.manifests]
    for rep in reports:
        print(rep.render())
    return 1 if any(rep.exit_code == 1 for rep in reports) else max(rep.exit_code for rep in reports)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
