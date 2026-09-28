#!/usr/bin/env python3
"""acceptance_protocol.py — the reference tool for the acceptance PROTOCOL (`acceptance-protocol/0`).

Pure stdlib, python3.11+ (uses `tomllib`). No third-party dependencies.

Implements `protocol_acceptance/spec/protocol.md` (the generic, artifact-agnostic core, P11) and consults
`format_acceptance/profiles/verification/code/rust.md` (renamed 2026-09-24) only through `profiles.py`
(never by name in this file) (illustrative; profile vocabulary).
`protocol_acceptance/spec/states.toml` is the source of truth for the three lifecycles; `check-states` and
`transition` read it directly rather than re-encoding it here.

This tool is profile-blind (P11): it never hard-codes a grade, band, family or kind token. Every
such vocabulary lives in `profiles.py`, keyed by profile id, and is reached only through the
`PROFILES[...]` interface (`tier_ceiling`, `grade_rank`, `band_rank`, `revision_alias`,
`floor_check`, `floor_not_weaker`, `validate_floor`, `package_constraints`, `package_validator`) —
`check-package`/`check-decision` reach the package validator ONLY through
`PROFILES[id]["package_validator"]`, never by calling `check_acceptance.py` directly by name.

Verbs (see `README.md` for the worked examples):

    check-contract CONTRACT.toml [--previous OLD.toml] [--json]
    check-package  PACKAGE.toml --contract CONTRACT.toml [--previous-contract OLD.toml]
                   [--strict] [--json]
    coverage       PACKAGE.toml --contract CONTRACT.toml [--json]
    decide         PACKAGE.toml --contract CONTRACT.toml --issuer NAME --out DECISION.toml
                   [--mode re-execute-all|spot-check|package-trusted]
    check-decision DECISION.toml --contract CONTRACT.toml --package PACKAGE.toml
                   [--previous-contract OLD.toml] [--json]
                   [--effect [--now YYYY-MM-DD] [--allow-conditions]]
    check-states   [STATES.toml]
    transition     MACHINE FROM NAME [--states STATES.toml]
    impact         DECISION.toml --contract C --package P --new-commit SHA
                   (--changed PATH... | --changed-file LIST.txt) [--new-package NEW_PACKAGE.toml]
                   [--out-events EVENTS.jsonl]
    render         CONTRACT.toml PACKAGE.toml [DECISION.toml] [--out VIEW.md]
    check-amendment AMENDMENT.toml --contract BASE.toml [--json]
    apply-amendment AMENDMENT.toml --contract BASE.toml [--current CURRENT.toml] --out NEW.toml
                   [--id AC-...] (--accept-by NAME | --dry-run)
    amend          --from-decision DECISION.toml --contract CONTRACT.toml --out AMENDMENT.toml
    --selftest

Exit codes: 0 = pass/valid, 1 = validation error(s), 2 = indeterminate/usage error, 99 = selftest mismatch.
`check-decision --effect`'s exit code reflects EFFECT ELIGIBILITY (§5.0a), not mere validity.

On any disagreement between this file and `protocol_acceptance/spec/protocol.md`, the spec wins and this file
has a bug — each point the spec leaves open, and the fail-closed reading this tool picked, is recorded
inline at the function or comment that resolves it (e.g. the `record_tier`/`methods` conflict below).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent.parent / "format_acceptance" / "tools"))  # check_core, check_acceptance, acceptance_grammar

import m11  # noqa: E402


def _load_private(path: Path, name: str):
    """Load `path` under a private `sys.modules` name, never the bare module basename.

    This file's own `profiles.py` is named `profiles` — the SAME bare name as the format
    core's `format_acceptance/tools/profiles/` PACKAGE (verification.py/conformance.py/
    troubleshooting.py's home). A plain `import profiles` here registers `sys.modules['profiles']`
    as THIS module, so any later `check_core.validate(bound_meaning=...)` call that has to load a
    format meaning module — which itself does `from profiles import verification` — silently
    resolves that `profiles` to the wrong module and fails to load (confirmed: `check_core.validate`
    with `bound_meaning="conformance"` raised "cannot import name 'verification' from 'profiles'
    (protocol_acceptance/tools/profiles.py)" before this fix). Loading THIS module under a private
    name leaves the bare `profiles` name free for the format core's own package."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_profiles = _load_private(_HERE / "profiles.py", "_protocol_profiles")  # noqa: E402
import check_core  # noqa: E402 — the profile-neutral core (dispatch, subject identity, validate)
import check_acceptance as CA  # noqa: E402 — kept for the historical verification-bound default (§6.6 item 8)
from acceptance_grammar import is_iso_date  # noqa: E402

PROFILES = _profiles.PROFILES

# ---------------------------------------------------------------------------------------------
# Core vocabularies (protocol.md). Core fields ONLY — profile vocabulary (grade/band/family/kind)
# lives in profiles.py and is never named here (P11).
# ---------------------------------------------------------------------------------------------

PROTOCOL_ID = "acceptance-protocol/0"

CONTRACT_STATUSES = {"draft", "issued", "ratified", "superseded", "withdrawn"}
ISSUED_BY_VALUES = {"consumer", "producer"}
DOMAIN_VALUES = {
    "correctness", "safety", "security", "performance", "compatibility", "documentation",
    "packaging", "process", "legal", "information-flow", "availability", "other",
}
# protocol.md §3: where a REQUIREMENT's text came from (distinct from the format's own per-claim
# `clause_source` vocabulary in acceptance_grammar.py, which answers a different question).
CONTRACT_CLAUSE_SOURCES = {"consumer-statement", "external-standard", "spec-document"}
REQUIREMENT_KINDS = {"item", "cross-cutting"}

TIER_TOKENS = ["T1", "T2", "T3", "T4", "T5"]
TIER_RANK = {t: 5 - i for i, t in enumerate(TIER_TOKENS)}  # T1=5 (strongest) .. T5=1

FRESHNESS_VALUES = {"delivered-revision", "any"}
# §3.7: a 4th value, `third-party` — independent of BOTH the producer and the
# consumer (DO-178C/ISO 26262's separate-organisation independence tier). Ordered
# none < author-not-producer < consumer-run < third-party (INDEPENDENCE_RANK below).
INDEPENDENCE_VALUES = {"none", "author-not-producer", "consumer-run", "third-party"}

VERIFICATION_MODES = ["package-trusted", "spot-check", "re-execute-all"]
MODE_RANK = {m: i for i, m in enumerate(VERIFICATION_MODES)}

RUN_RESULTS = {"pass", "fail", "not-run", "error"}

DISPOSITION_STATUSES = {
    "satisfied", "satisfied-with-conditions", "unsatisfied", "waived",
    "insufficient-evidence", "not-applicable",
}
# requirement-defect (§3.5): a deviation that asks for a CONTRACT change, not a waiver.
DEVIATION_KINDS = {"unmet", "partial", "alternative", "not-applicable", "requirement-defect"}
WAIVER_CODES = {"risk-accepted", "alternative-evidence", "not-applicable", "deferred", "other"}
FILLER_ROLES = {"producer", "validator"}
CONDITION_OWNERS = {"producer", "consumer", "verifier"}
DECISION_VERDICTS = {"accepted", "accepted-with-conditions", "rejected", "evidence-requested"}
ACCEPTANCE_RULES = {"all-mandatory-satisfied"}

# §3.4a — party boundary: declared once per contract, never branched on by a core check
# except the two named in check_contract below (cross-org disclosure/integrity).
PARTY_BOUNDARIES = {"internal", "cross-org"}
BOUNDARY_TERM_FIELDS = {
    "identity_scheme", "integrity", "transport", "disclosure", "rerun_location", "legal_ref",
}

# §3.5 — iteration and tightening (P12).
PHASE_VALUES = {"exploratory", "crystallizing", "final"}
PHASE_ORDER = {"exploratory": 0, "crystallizing": 1, "final": 2}
FIRMNESS_VALUES = {"draft", "firm"}
FRESHNESS_RANK = {"any": 0, "delivered-revision": 1}
INDEPENDENCE_RANK = {"none": 0, "author-not-producer": 1, "consumer-run": 2, "third-party": 3}

# §3.7: `[requirement.evidence].coverage_min.metric` MUST be one of the SAME registry the
# format's B21 `coverage.metric` uses (core.md) — read from check_core directly, never a second,
# driftable copy of the token list (the same discipline profiles.py's _KNOWN_FAMILIES/_KNOWN_KINDS
# already follow for the format's own registries).
COVERAGE_METRICS = check_core.COVERAGE_METRICS
REQUIREMENT_FEEDBACK_KINDS = {
    "ambiguous", "wrong", "missing", "over-constrained", "under-constrained", "malicious-compliance",
}

# §3.6 — the amendment document.
AMENDMENT_STATUSES = {"proposed", "accepted", "rejected", "stale", "superseded"}
AMENDMENT_ISSUED_BY = {"consumer", "producer", "verifier"}
CHANGE_OPS = {"add", "modify", "drop", "tighten", "relax"}

ITEM_STATUSES = {"satisfied", "partial", "deviation-declared", "gap", "missing"}
CROSSCUT_STATUSES = {"satisfied", "partial", "deviation-declared"}

# §5.2 insufficient-evidence row: cov(R) in this set satisfies the disjunct on coverage alone.
INSUFFICIENT_COV = {"partial", "deviation-declared", "missing", "gap"}


# ---------------------------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------------------------

def _nonempty(v) -> bool:
    return isinstance(v, str) and len(v) > 0


# One wire form: the pre-lock m11.py wire form `sha-512:<hex>` (domain baked into the
# hash bytes, not repeated in the wire string) is retired for the protocol's OWN contract/package/
# decision hash fields (m11.py now writes `<domain>:sha-512:<hex>` for those three domains,
# matching the format core's self-describing form exactly, protocol.md §7). A document that still
# carries the bare form on one of these fields is an explicit ERROR, not merely a downstream
# mismatch — no compatibility shim with pre-lock drafts.
_BARE_M11_WIRE_RE = re.compile(r"\Asha-512:[0-9a-f]{128}\Z")


def _reject_bare_m11_wire(rep: "Reporter", value, domain: str, label: str) -> None:
    if isinstance(value, str) and _BARE_M11_WIRE_RE.match(value):
        rep.error(
            f"{label}: {value!r} uses the retired bare 'sha-512:<hex>' wire form — the protocol "
            f"now requires the self-describing '{domain}:sha-512:<hex>' form for this field "
            f"(B16, one wire form; no compatibility shim with pre-lock drafts)"
        )


def _subject_binds_field(subject: dict) -> tuple[str | None, str | None]:
    """Protocol identity = format identity: the `[binds].subject` field NAME and VALUE a
    package's certified subject identity requires — `('commit', <40-hex>)` for a git-revision
    identity, `('digest', <subject:sha-512:hex>)` for content-digest OR components (B1: the
    aggregate `subject:` digest over the component table IS the components identity, not a second
    one, so both compare on the same field). `(None, None)` when the subject carries no certified
    identity (classification and value both come from `check_core.subject_identity_value`, reused
    verbatim, never re-implemented — called on the format core directly, not through the
    verification-bound `check_acceptance` compatibility entry, since the function is profile-blind)."""
    kind, value = check_core.subject_identity_value(subject if isinstance(subject, dict) else {})
    if kind is None:
        return None, None
    return ("commit" if kind == "git-revision" else "digest"), value


def now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_utc_date() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


_ISO8601_DURATION_RE = re.compile(
    r"^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?"
    r"(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$"
)


def is_iso8601_duration(s) -> bool:
    """protocol.md §3.3: `stale_after` parses as an ISO-8601 duration (`P...`). Shape only: at
    least one component must be present (bare `P` or `PT` is not a duration)."""
    if not isinstance(s, str):
        return False
    m = _ISO8601_DURATION_RE.match(s)
    if not m:
        return False
    return any(g is not None for g in m.groups())


def is_rfc3339_datetime(s) -> bool:
    """`[document].issued_at` is documented as RFC 3339
    (protocol.md §3.2/§5.0), but nothing checked its shape before this — a nonempty-but-garbage
    value (e.g. `"sometime"`) passed `check_decision`'s VALID gate, and then made
    `check_decision_effect`'s `stale_after` ceiling silently fail OPEN (see there) instead of
    refusing the decision. Accepts a leading `Z` or a numeric offset, same as
    `datetime.fromisoformat` after the `Z`→`+00:00` substitution already used for the ceiling
    math elsewhere in this file. `fromisoformat` alone also
    accepts a bare date (`"2026-09-16"`) and an offset-less datetime (`"2026-09-20T09:00"`),
    neither of which is an RFC 3339 `date-time` — a strict-RFC-3339 vendor would reject a decision
    this tool VALIDs, the same split F8 closed. So require the full
    `date "T" time offset` shape explicitly BEFORE the calendar-validity check."""
    if not _nonempty(s):
        return False
    # RFC 3339 date-time: full-date "T" full-time, where full-time carries a Z or ±hh:mm offset.
    if not re.match(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$", s):
        return False
    try:
        datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def duration_to_timedelta(s: str) -> datetime.timedelta:
    """Approximate conversion (Y=365d, M=30d — no calendar arithmetic dependency) used only to
    derive a decision's `[validity].stale_after` DATE from a contract's ISO-8601 DURATION when
    `decide` emits a skeleton. Documented approximation — see README "ambiguities resolved"."""
    m = _ISO8601_DURATION_RE.match(s)
    if not m:
        raise ValueError(f"not an ISO-8601 duration: {s!r}")
    y, mo, w, d, h, mi, sec = (int(g) if g else 0 for g in m.groups())
    days = y * 365 + mo * 30 + w * 7 + d
    return datetime.timedelta(days=days, hours=h, minutes=mi, seconds=sec)


def _split_semicolon_line(line: str) -> list[str]:
    """One line of `key = val; key2 = val2; ...` -> one line per `key = val`, splitting only on
    `;` OUTSIDE quoted strings and before any `#` comment. Returns [line] unchanged when the line
    carries no bare semicolon (the common case), so this never touches a normal TOML line."""
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]
    segments: list[str] = []
    buf: list[str] = []
    in_str: str | None = None
    i, n = 0, len(stripped)
    saw_semicolon = False
    while i < n:
        c = stripped[i]
        if in_str:
            buf.append(c)
            if c == in_str and stripped[i - 1] != "\\":
                in_str = None
            i += 1
            continue
        if c in ('"', "'"):
            in_str = c
            buf.append(c)
            i += 1
            continue
        if c == "#":
            buf.append(stripped[i:])
            i = n
            break
        if c == ";":
            saw_semicolon = True
            segments.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        segments.append(tail)
    if not saw_semicolon:
        return [line]
    return [indent + seg for seg in segments if seg]


def _desemicolon_toml(text: str) -> str:
    """Fallback preprocessing for `states.toml`'s `key = val; key2 = val2` single-line shorthand,
    which is NOT valid TOML (bare `;` is not a statement separator) — confirmed against stdlib
    tomllib. `protocol_acceptance/spec/states.toml` is not on this tool's touch-list, so the file is not
    rewritten; this tool instead tolerates the shorthand as a fallback parse (see README "spec
    ambiguities resolved")."""
    out_lines: list[str] = []
    for ln in text.split("\n"):
        out_lines.extend(_split_semicolon_line(ln))
    return "\n".join(out_lines)


def load_toml(path: Path, allow_semicolon: bool = False) -> tuple[dict | None, str | None]:
    """Returns (doc, error). error is None on success. Tries a strict parse first; only on
    failure does it retry with the semicolon-shorthand fallback (`_desemicolon_toml`) — a
    well-formed file is never rewritten before parsing.

    The semicolon-shorthand retry is `states.toml`'s alone —
    `protocol_acceptance/spec/states.toml` is the only file this tool tolerates it for (not on this tool's
    touch-list, see `_desemicolon_toml`), and `allow_semicolon` defaults to False so every
    protocol DOCUMENT (contract/package/decision/amendment) is held to strict TOML. Applying the
    fallback to every document let an invalid-TOML document parse, hash and bind here while a
    conforming parser rejected it outright — a validity split on a hash-bound file.
    Callers pass `allow_semicolon=True` only when loading `states.toml` itself."""
    try:
        raw = path.read_bytes()
    except OSError as e:
        return None, f"cannot read file: {e}"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        return None, f"not valid UTF-8: {e}"
    try:
        return tomllib.loads(text), None
    except tomllib.TOMLDecodeError as first_err:
        if not allow_semicolon:
            return None, f"TOML parse error: {first_err}"
        try:
            return tomllib.loads(_desemicolon_toml(text)), None
        except tomllib.TOMLDecodeError:
            return None, f"TOML parse error: {first_err}"


class Reporter:
    """Collects ERROR/WARN lines for one document. Mirrors check_acceptance.Reporter's shape so
    the two tools read the same to a human and to a script."""

    def __init__(self, path: str):
        self.path = path
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.unknowns: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def ok(self) -> bool:
        return not self.errors and not self.unknowns

    def exit_code(self) -> int:
        return 1 if self.errors else 2 if self.unknowns else 0

    def lines(self) -> list[str]:
        out = [f"ERROR {self.path}: {m}" for m in self.errors]
        out += [f"WARN {self.path}: {m}" for m in self.warnings]
        out += [f"INDETERMINATE {self.path}: {m}" for m in self.unknowns]
        return out

    def merge(self, other: "Reporter", prefix: str = "") -> None:
        for m in other.errors:
            self.errors.append(f"{prefix}{m}")
        for m in other.warnings:
            self.warnings.append(f"{prefix}{m}")
        unknowns = list(getattr(other, "unknowns", ()))
        if hasattr(other, "profile_errors") and check_core.verdict(other)[1] == 2 and not unknowns:
            unknowns.append("format validation is INDETERMINATE (unresolved evaluation)")
        self.unknowns.extend(f"{prefix}{m}" for m in unknowns)


def requirement_by_id(contract: dict) -> dict[str, dict]:
    reqs = contract.get("requirement")
    if not isinstance(reqs, list):
        return {}
    out = {}
    for r in reqs:
        if isinstance(r, dict) and _nonempty(r.get("id")):
            out[r["id"]] = r
    return out


def package_profile_id(package: dict) -> str | None:
    """The package's own declared `[format].profile`, or None when the field is absent.

    NEVER substitutes a default profile id — B12
    made `[format].profile` REQUIRED with no compatibility default, and this function used to
    paper over an absent field with `acceptance/verification`, which meant every caller of it
    silently evaluated an undeclared package under an assumed meaning instead of reporting the
    missing field. Callers MUST treat `None` as "no profile declared" and report it, not resolve
    a binding for it."""
    fmt = package.get("format")
    if isinstance(fmt, dict) and _nonempty(fmt.get("profile")):
        return fmt["profile"]
    return None


def producer_identity_set(contract: dict, package: dict) -> set[str]:
    """protocol.md §4.1 rule 7 / Finding 7: the package's producer identity is
    {parties.producer.name of the contract} ∪ {every [[filler]].party with role='producer'}. P5
    and `independence` compare against this WHOLE set, never the contract's producer string
    alone — a package under `producer = "open"` MUST name at least one filler (checked in
    `check_package` rule 7); the caller decides what to do with an empty set."""
    names: set[str] = set()
    pname = ((contract.get("parties") or {}).get("producer") or {}).get("name")
    if _nonempty(pname):
        names.add(pname)
    for f in (package.get("filler") or []):
        if isinstance(f, dict) and f.get("role") == "producer" and _nonempty(f.get("party")):
            names.add(f["party"])
    return names


# B6 repository-root override, set once from the CLI's --root (the same override
# check_acceptance.py --root offers). None keeps the core's own rule: the nearest `.git` ancestor.
# A copy without git metadata (a source archive) has no such ancestor, so every record pointer is
# INDETERMINATE there unless the caller names the root explicitly.
_ROOT_OVERRIDE: Path | None = None


def _run_package_validator(validator, package_path: Path, strict: bool):
    if _ROOT_OVERRIDE is None:
        return validator(package_path, strict=strict, strict_weight=False)
    return validator(package_path, strict=strict, strict_weight=False, root=_ROOT_OVERRIDE)


def claim_weight_grants(
    package_path: Path, claims: list[dict], profile: dict | None = None,
) -> tuple[dict[str, bool], object]:
    """Finding 1 / §6.2 cond 2: "the claim's weight is granted by the format validator — a claim
    the validator reports as weight-refused or weight-pending is unweighted here whatever its
    `weight` string says". Runs the package validator (strict=False, strict_weight=False —
    coverage must see the same weight-pending/refused facts regardless of what --strict-weight a
    producer happened to pass directly) and reads GRANTED/PENDING/REFUSED back from its Reporter,
    never re-deriving the weight rule independently (that would just be a second, driftable copy
    of the same logic).

    Finding 17: reached through the profile binding (`profile["package_validator"]`) when one is
    given, never a hardcoded `check_acceptance.py` call by name. The fallback for a missing
    or unbound profile is `check_core.validate` UNBOUND (no `bound_meaning`) — the core's own
    `dispatch` reads the package's own declared `[format].profile` and resolves the right meaning
    itself, so an unrecognised caller never defaults to `acceptance/verification` specifically.

    Returns (grants, ca_reporter) where grants[claim_id] is True only when the claim declared
    `weight = "weighted"` AND the validator did not put it on the weight-pending backlog (§8.1)
    AND did not refuse it outright (a "WEIGHT REFUSED" error naming this claim, or the
    document-wide `[spec].axis` refusal that blocks every weighted claim in the file)."""
    validator = (profile or {}).get("package_validator") or check_core.validate
    ca_rep = _run_package_validator(validator, package_path, False)
    # `pending` is read via getattr with a `{}`
    # fallback, which fails OPEN for a profile-bound validator that does not expose the attribute.
    # Dormant today — the in-repo check_acceptance.Reporter always constructs `pending` — so this
    # is a documented residual, not a live hole; a future alternate `package_validator` must expose
    # `pending` (or gain the same structured-or-fallback treatment applied to refusal below).
    pending_ctxs = set(getattr(ca_rep, "pending", {}) or {})
    # Take the UNION of the validator's
    # structured accessors (`weight_refused`/`axis_blocked`, additive on check_acceptance.Reporter)
    # AND the error-string parse — not one or the other. The union is fail-closed: if a future
    # WEIGHT REFUSED emission site forgets to populate the structured set, the string parse still
    # catches it, and vice-versa if a message format drifts. Either source flagging a claim refuses
    # its weight.
    refused_ctxs: set[str] = set(getattr(ca_rep, "weight_refused", None) or set())
    for e in ca_rep.errors:
        if ": WEIGHT REFUSED" in e:
            refused_ctxs.add(e.split(": WEIGHT REFUSED", 1)[0])
    axis_blocked = bool(getattr(ca_rep, "axis_blocked", False)) or any(
        e.startswith("WEIGHT REFUSED: [spec].axis") for e in ca_rep.errors
    )
    grants: dict[str, bool] = {}
    for c in claims:
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        if not _nonempty(cid):
            continue
        ctx = f"claim {cid!r}"
        granted = (
            c.get("weight") == "weighted"
            and check_core.verdict(ca_rep)[1] == 0
            and not axis_blocked
            and ctx not in pending_ctxs
            and ctx not in refused_ctxs
        )
        grants[cid] = granted
    return grants, ca_rep


def relied_on_records(claim: dict, floor: dict) -> list[dict]:
    """§6.2 closing paragraph: "the passing evidence records that establish the tier and family
    for this claim, plus the record carrying the observed-red control when control_required is
    met by a control." Shared by cond 7 (freshness) and cond 8 (independence) — Finding 9's fix
    (a record with no author must FAIL the demand, not silently pass it) only works if both
    conditions read the same restricted set the spec actually names, not "every evidence record
    on the claim" (which is what the tool did before)."""
    out = [e for e in evidence_list(claim) if e.get("result") == "pass"]
    if floor.get("control_required"):
        cid = claim.get("id")
        for e in evidence_list(claim):
            if e in out:
                continue
            ctrl = e.get("control")
            if (isinstance(ctrl, dict) and ctrl.get("expectation") == "red"
                    and ctrl.get("observed") == "red" and ctrl.get("of_claim") == cid):
                out.append(e)
    return out


def tool_produced_relied_on_records(claim: dict, floor: dict) -> list[dict]:
    """§6.2 conds 9-10: the subset of
    `relied_on_records` that is PRODUCED BY RUNNING A TOOL, i.e. every evidence record whose
    `family` is not the format's `judgment` family (B3: the class families are `judgment`,
    ceiling T5, and `reference`; the closed evidence-kind registry's ONLY judgment-family kinds
    are `human-review` and `llm-review`, B4) — a judgment-family record names a `reviewer`, never
    a tool, and never carries `build_inputs`/`tool_qualification` in the first place, so it is
    exempt from both floors rather than a vacuous pass smuggled through "at least one"."""
    return [e for e in relied_on_records(claim, floor) if e.get("family") != "judgment"]


def revision_alias_conflict(record: dict, profile: dict | None) -> bool:
    """Finding 20 / §6.2 cond 7: "a record with... both the core name and the alias present and
    unequal, fails freshness." """
    if "captured_at_revision" not in record:
        return False
    alias = profile.get("revision_alias") if profile is not None else None
    if not alias or alias not in record:
        return False
    return record.get("captured_at_revision") != record.get(alias)


# ---------------------------------------------------------------------------------------------
# Coverage core — protocol.md §6. Profile-blind (P11): every grade/band/family/kind token is
# read only inside `profiles.py`'s `floor_check`; this module only ever compares TIER tokens
# (T1..T5) and boolean/enum core fields.
# ---------------------------------------------------------------------------------------------

def evidence_list(claim: dict) -> list[dict]:
    return [e for e in (claim.get("evidence") or []) if isinstance(e, dict)]


def claim_has_observed_red_control(claim: dict) -> bool:
    """§6.2 cond 5: an observed-red control on one of the claim's OWN evidence records."""
    cid = claim.get("id")
    for e in evidence_list(claim):
        ctrl = e.get("control")
        if not isinstance(ctrl, dict):
            continue
        if (ctrl.get("expectation") == "red" and ctrl.get("observed") == "red"
                and ctrl.get("of_claim") == cid):
            return True
    return False


def claim_has_watched_fail(claim: dict) -> bool:
    """§6.2 cond 5 (alternative witness): a `[claim.self_verify.watched_fail]` table naming
    of_command/perturbed/observed/date, all present as nonempty strings. Full field-level
    correctness (phrase floor, of_command binding) is `check_acceptance.py`'s job when the
    package is validated; here we only need presence, since the coverage function must also be
    computable over a package that has not (yet) been run through `check_acceptance.py`."""
    sv = claim.get("self_verify")
    if not isinstance(sv, dict):
        return False
    wf = sv.get("watched_fail")
    if not isinstance(wf, dict):
        return False
    return all(_nonempty(wf.get(k)) for k in ("of_command", "perturbed", "observed", "date"))


def get_revision_field(record: dict, profile: dict | None):
    """§6.2 cond 7 / §6.6.4: the core field is `captured_at_revision`; a profile may alias it
    (verification/code/rust.md §1: `captured_at_commit`) (illustrative; profile vocabulary). Either spelling
    on a record satisfies."""
    if "captured_at_revision" in record:
        return record.get("captured_at_revision")
    if profile is not None:
        alias = profile.get("revision_alias")
        if alias and alias in record:
            return record.get(alias)
    return None


def record_tier(record: dict, profile: dict | None) -> tuple[str | None, str | None]:
    """§6.1 / §6.2 cond 3. Returns (tier_token_or_None, error_or_None).

    A record's tier is its declared `epistemic_tier`, held to the profile's ceiling for the
    record's `method` (or `kind`), capped by its kind and B3 family ceiling. A STRONGER
    declared tier than the ceiling is an ERROR and the
    record is treated as INDETERMINATE for floor purposes (fail-closed: an overclaimed tier must
    not silently pass a floor). Absent `epistemic_tier`, the capped ceiling is used. A record the
    profile cannot place (unknown method/kind, no profile) is indeterminate with no error — that
    is a legitimate, expected state (verification/PROFILE.md §2 / verification/code/rust.md §2) (illustrative; profile vocabulary), not a
    defect."""
    declared = record.get("epistemic_tier")
    token = record.get("method") or record.get("kind")
    ceiling = None
    if profile is not None:
        ceiling = profile.get("tier_ceiling", {}).get(token)

    # §6.1's method/kind inference remains bounded by core.md B3. Use the
    # actual meaning's family declarations supplied by the format validator.
    if profile is not None:
        limits = [profile.get("tier_ceiling", {}).get(record.get("kind")),
                  profile.get("family_ceiling", {}).get(record.get("family"))]
        for limit in limits:
            if ceiling is not None and limit in TIER_RANK:
                ceiling = min((ceiling, limit), key=TIER_RANK.get)

    if declared is not None:
        family_ceiling = (profile or {}).get("family_ceiling", {}).get(record.get("family"))
        if declared in TIER_RANK and family_ceiling in TIER_RANK and TIER_RANK[declared] > TIER_RANK[family_ceiling]:
            return None, f"declared epistemic_tier {declared!r} exceeds family ceiling {family_ceiling!r} (core.md B3)"
        if declared not in TIER_RANK:
            return None, f"epistemic_tier {declared!r} is not one of {TIER_TOKENS}"
        if ceiling is not None and TIER_RANK[declared] > TIER_RANK[ceiling]:
            return None, (
                f"declared epistemic_tier {declared!r} exceeds the profile ceiling {ceiling!r} "
                f"for {token!r} (verification/PROFILE.md §2 / verification/code/rust.md §2, illustrative; profile vocabulary) — treated as "
                f"indeterminate"
            )
        return declared, None

    if ceiling is not None:
        return ceiling, None
    return None, None


def claim_tier(claim: dict, profile: dict | None) -> str | None:
    """§6.1: the strongest tier among the claim's PASSING evidence records."""
    best = None
    for e in evidence_list(claim):
        if e.get("result") != "pass":
            continue
        t, _err = record_tier(e, profile)
        if t is not None and (best is None or TIER_RANK[t] > TIER_RANK[best]):
            best = t
    return best


def record_kind_method_conflict(record: dict) -> str | None:
    """§6.1 reads a record's tier off its `method` (or `kind`), but neither §6.1 nor §6.2 cond 4
    says what happens when a record declares BOTH and they name DIFFERENT tokens. `method` and
    `kind` draw from the
    identical, closed vocabulary (verification/PROFILE.md §2: "`unit-test` is a `method` token…
    there is no `unit-testing` profile"; a binding leaf adds its own tokens under the SAME table,
    e.g. verification/code/rust.md §2, illustrative; profile vocabulary) — the two fields are
    two names for the SAME fact (which technique produced this
    record), never two independent axes, so a record naming two different techniques cannot be
    read as "the weaker of the two" or "prefer one field over the other": it is a
    misdeclaration. That silence is a spec gap, read fail-closed here: BOTH fields present and
    unequal is a conflicting declaration, refused wherever the record would otherwise count
    toward a `methods` floor (§6.2 cond 4) or a tier — without this, a record can name a WEAKER
    `kind` (capping `record_tier`'s escalation) while still naming a STRONGER
    `method` token literally, and a `methods` floor that names that stronger token (cond 4's raw
    `in methods` membership test) is satisfied by a record that never actually used that
    technique. This function is deliberately NOT consulted by `record_tier` itself — that
    function's existing kind/family-capping behavior for a record naming only one of
    `method`/`kind` (or naming both consistently) is unchanged; this is an additional, narrower
    refusal for the specific both-present-and-unequal shape."""
    method, kind = record.get("method"), record.get("kind")
    if _nonempty(method) and _nonempty(kind) and method != kind:
        return (
            f"record declares conflicting method {method!r} and kind {kind!r} — method and kind "
            f"are the same closed vocabulary (verification/PROFILE.md §2) and must agree; spec "
            f"gap in §6.1/§6.2 cond 4 read fail-closed"
        )
    return None


def collect_tier_errors(claims: list, profile: dict | None) -> list[str]:
    """Every over-strong declared `epistemic_tier`, across ALL claims — surfaced regardless of
    whether the record happens to matter to any particular requirement's floor (a producer
    overclaiming a tier is always wrong, not just wrong-when-it-would-have-mattered) — plus every
    conflicting method/kind declaration (`record_kind_method_conflict`), which is refused the
    same way: always surfaced, never only when it happens to matter to a particular
    requirement."""
    out: list[str] = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        for idx, e in enumerate(evidence_list(c)):
            conflict = record_kind_method_conflict(e)
            if conflict:
                out.append(f"claim {cid!r} evidence[{idx}]: {conflict}")
                continue
            _tier, error = record_tier(e, profile)
            if error:
                out.append(f"claim {cid!r} evidence[{idx}]: {error}")
    return out


def meets_item_floor(
    claim: dict, floor: dict, profile: dict | None, profile_id: str,
    subject_identity, producer_names: set[str],
    weight_grants: dict[str, bool] | None = None,
    consumer_name: str | None = None,
) -> tuple[bool, str | None]:
    """§6.2, conditions 1-12 in order (conditions 9-11 added, condition 8 extended, profile floor
    renumbered 9->12, all §3.7). Returns (meets, first_failed_reason).

    `producer_names` is the WHOLE producer identity set (Finding 7, §4.1 rule 7), never a single
    string. `weight_grants` is the per-claim effective-weight map computed by
    `claim_weight_grants` (Finding 1, §6.2 cond 2) — a claim absent from the map (or mapped
    False) is treated as unweighted regardless of its own `weight` field. `consumer_name` is
    `[parties].consumer.name` (§3.7 cond 8's `third-party` branch only — independent of BOTH
    sides, so it must be excluded too, not just the producer set)."""
    weight_grants = weight_grants or {}
    # 1
    if claim.get("status") != "evidenced":
        return False, "status is not 'evidenced' (§6.2 cond 1)"

    # 2 — Finding 1: effective weight is what the format VALIDATOR granted, not the claim's own
    # `weight` string (a claim the validator reports weight-pending/refused is unweighted here).
    weighted_required = floor.get("weighted_required", True)
    if weighted_required and not weight_grants.get(claim.get("id"), False):
        return False, (
            "weighted_required but the format validator did not GRANT weight to this claim "
            "(pending or refused — read from its Reporter, not the claim's own 'weight' field) "
            "(§6.2 cond 2)"
        )

    # 3
    min_tier = floor.get("min_tier")
    tier = claim_tier(claim, profile)
    if tier is None or TIER_RANK.get(tier, 0) < TIER_RANK.get(min_tier, 0):
        return False, f"claim tier {tier!r} does not reach min_tier {min_tier!r} (§6.2 cond 3)"

    # 4 — a record whose `method` and `kind` NAME DIFFERENT tokens is a conflicting declaration
    # (`record_kind_method_conflict`) and is refused here BEFORE its token is read for membership
    # in `methods` — otherwise a record could name a weaker `kind` (capped by `record_tier`)
    # while still naming a stronger `method` token literally, satisfying a `methods` floor it
    # never actually met.
    methods = floor.get("methods")
    if methods:
        passing = [e for e in evidence_list(claim) if e.get("result") == "pass"]
        conflicts = [c for c in (record_kind_method_conflict(e) for e in passing) if c]
        eligible = [e for e in passing if not record_kind_method_conflict(e)]
        if not any((e.get("method") or e.get("kind")) in methods for e in eligible):
            reason = f"no passing record with method/kind in {methods} (§6.2 cond 4)"
            if conflicts:
                reason += f" — refused a conflicting declaration: {conflicts[0]}"
            return False, reason

    # 5
    if floor.get("control_required"):
        if not (claim_has_observed_red_control(claim) or claim_has_watched_fail(claim)):
            return False, (
                "control_required but no observed-red control or self_verify.watched_fail "
                "(§6.2 cond 5)"
            )

    # 6
    if floor.get("recipe_required"):
        sv = claim.get("self_verify")
        if not (isinstance(sv, dict) and _nonempty(sv.get("command")) and _nonempty(sv.get("expect"))):
            return False, (
                "recipe_required but no [claim.self_verify] with nonempty command/expect "
                "(§6.2 cond 6)"
            )

    # 7 — Finding 9/20: "relied on" is the §6.2 closing-paragraph set, not every record on the
    # claim; an alias/core-name conflict fails freshness even when one of the two would have
    # matched (Finding 20).
    if floor.get("freshness") == "delivered-revision":
        for e in relied_on_records(claim, floor):
            if revision_alias_conflict(e, profile):
                return False, (
                    "freshness=delivered-revision but a relied-on record carries BOTH "
                    "captured_at_revision and the profile's alias, unequal to each other "
                    "(§6.2 cond 7, Finding 20)"
                )
            rev = get_revision_field(e, profile)
            if rev != subject_identity:
                return False, (
                    "freshness=delivered-revision but a relied-on record's captured_at_revision "
                    "(or its alias) does not equal the package's subject identity IN FULL — an "
                    "abbreviated or absent value also fails (§6.2 cond 7)"
                )

    # 8 — Finding 9: a record with NO author fails the demand (it does not pass it); compares
    # against the WHOLE producer identity set (Finding 7), never a single producer string.
    if floor.get("independence") == "author-not-producer":
        for e in relied_on_records(claim, floor):
            author = e.get("author")
            if not _nonempty(author):
                return False, (
                    "independence=author-not-producer but a relied-on record carries no "
                    "nonempty author (§6.2 cond 8, Finding 9 — absence fails the demand)"
                )
            if author in producer_names:
                return False, (
                    "independence=author-not-producer but a relied-on record's author is in "
                    "the package's producer identity set (§6.2 cond 8, §4.1 rule 7)"
                )

    # 8, third-party (§3.7): independent of BOTH sides — the same absence-fails-the-demand
    # rule as author-not-producer, plus the consumer's own name is ALSO excluded (author-not-
    # producer only excludes the producer set; a consumer's own in-house run does not qualify a
    # third-party floor).
    if floor.get("independence") == "third-party":
        for e in relied_on_records(claim, floor):
            author = e.get("author")
            if not _nonempty(author):
                return False, (
                    "independence=third-party but a relied-on record carries no nonempty "
                    "author (§6.2 cond 8, §3.7)"
                )
            if author in producer_names:
                return False, (
                    "independence=third-party but a relied-on record's author is in the "
                    "package's producer identity set (§6.2 cond 8, §3.7)"
                )
            if _nonempty(consumer_name) and author == consumer_name:
                return False, (
                    "independence=third-party but a relied-on record's author is the "
                    "contract's own consumer — third-party independence excludes both sides "
                    "(§6.2 cond 8, §3.7)"
                )

    # 9 (§3.7): build_inputs_required — B20's required-build-inputs guard is opt-in at the format
    # (it fires only once a
    # claim declares any build_inputs); this floor makes declaring them MANDATORY. The quantifier
    # is EVERY relied-on record that is PRODUCED BY RUNNING A TOOL (family != "judgment", B3) —
    # a `judgment`-family record (human-review, llm-review) names a reviewer, never a tool, and
    # is exempt (one relied-on record with none is no longer enough to pass the others through).
    # Vacuously met when no relied-on record is tool-produced.
    if floor.get("build_inputs_required"):
        offenders = [
            e for e in tool_produced_relied_on_records(claim, floor)
            if not (isinstance(e.get("build_inputs"), list) and e.get("build_inputs"))
        ]
        if offenders:
            return False, (
                "build_inputs_required but a tool-produced relied-on evidence record "
                "(family != 'judgment') carries no nonempty build_inputs list — EVERY such "
                "record must carry one, not merely one of them; a judgment-family record "
                "(human/llm review) is exempt (§6.2 cond 9, §3.7, B20)"
            )

    # 10 (§3.7): tool_qualification_required — the checking tool
    # itself must be declared qualified (shape only, B21; the class never validates the
    # qualification argument). Same quantifier and exemption as cond 9.
    if floor.get("tool_qualification_required"):
        offenders = [
            e for e in tool_produced_relied_on_records(claim, floor)
            if not (
                isinstance(e.get("tool_qualification"), dict)
                and _nonempty(e.get("tool_qualification", {}).get("basis"))
            )
        ]
        if offenders:
            return False, (
                "tool_qualification_required but a tool-produced relied-on evidence record "
                "(family != 'judgment') carries no tool_qualification table with a nonempty "
                "basis — EVERY such record must carry one, not merely one of them; a "
                "judgment-family record (human/llm review) is exempt (§6.2 cond 10, §3.7, B21)"
            )

    # 11 (§3.7): coverage_min — a structural/proof-coverage metric floor. A
    # relied-on record's own coverage.metric MUST match the demanded metric (a different metric
    # is incomparable, never a pass by coincidence) and its value must reach the floor.
    coverage_min = floor.get("coverage_min")
    if isinstance(coverage_min, dict):
        want_metric, want_value = coverage_min.get("metric"), coverage_min.get("value")
        if not any(
            isinstance(e.get("coverage"), dict)
            and e["coverage"].get("metric") == want_metric
            and isinstance(e["coverage"].get("value"), (int, float))
            and not isinstance(e["coverage"].get("value"), bool)
            and e["coverage"]["value"] >= (want_value if isinstance(want_value, (int, float)) else 2)
            for e in relied_on_records(claim, floor)
        ):
            return False, (
                f"coverage_min={coverage_min!r} but no relied-on evidence record carries a "
                f"coverage.metric={want_metric!r} record reaching value >= {want_value!r} "
                f"(§6.2 cond 11, §3.7, B21)"
            )

    # 12 — Finding 2: every profile floor the contract DECLARES for this requirement is ALWAYS
    # evaluated, never conditionally skipped because the package happens to use a different
    # profile. A floor declared under a profile id that is not the package's own, or for which no
    # binding is available, is NOT MET — fail-closed, never a silent pass and never a skip.
    prof_table = floor.get("profile")
    if isinstance(prof_table, dict):
        for pid, prof_floor in prof_table.items():
            if pid != profile_id:
                return False, (
                    f"profile floor declared for {pid!r} but the package's own profile is "
                    f"{profile_id!r} — a floor under a different profile is never met, not "
                    f"skipped (§6.2 cond 12, Finding 2, fail-closed)"
                )
            binding = PROFILES.get(pid)
            if binding is None:
                return False, (
                    f"profile floor declared for {pid!r} but the tool has no binding for it "
                    f"(§6.2 cond 12, fail-closed)"
                )
            ok, reason = binding["floor_check"](prof_floor, claim)
            if not ok:
                return False, f"profile floor not met for {pid!r}: {reason} (§6.2 cond 12)"

    return True, None


def _leading_token(value: str) -> str:
    parts = value.strip().split()
    if not parts:
        return ""
    return parts[0].rstrip(":,;")


def meets_demands(
    claim: dict, demands: dict, profile: dict | None,
    weight_grants: dict[str, bool] | None = None,
) -> tuple[bool, str | None]:
    """§6.4: the core demands (min_tier, weighted_required, control_required, as in §6.2) plus
    every `[requirement.demands.fields]` entry — a field `f = "tok"` holds iff `claim[f]` exists
    and its leading whitespace-delimited token equals `tok` — and every
    `[requirement.demands.fields_exact]` entry, which requires the WHOLE string to be equal
    (Finding 18)."""
    weight_grants = weight_grants or {}
    if "min_tier" in demands:
        want = demands["min_tier"]
        tier = claim_tier(claim, profile)
        if tier is None or TIER_RANK.get(tier, 0) < TIER_RANK.get(want, 0):
            return False, f"tier {tier!r} does not reach demanded min_tier {want!r} (§6.4)"

    if demands.get("weighted_required"):
        # Finding 1 extends to cross-cutting demands: the same effective-weight rule applies.
        if not weight_grants.get(claim.get("id"), False):
            return False, "weighted_required demanded but the format validator did not grant weight to this claim (§6.4)"

    if demands.get("control_required"):
        if not (claim_has_observed_red_control(claim) or claim_has_watched_fail(claim)):
            return False, "control_required demanded but not met (§6.4)"

    fields = demands.get("fields") or {}
    for field, tok in fields.items():
        val = claim.get(field)
        if not isinstance(val, str) or not val.strip():
            return False, f"field {field!r} is absent or empty on the claim (§6.4 demands.fields)"
        if _leading_token(val) != tok:
            return False, (
                f"field {field!r} leading token {_leading_token(val)!r} != demanded {tok!r} "
                f"(§6.4 demands.fields)"
            )

    fields_exact = demands.get("fields_exact") or {}
    for field, want in fields_exact.items():
        val = claim.get(field)
        if not isinstance(val, str) or val != want:
            return False, (
                f"field {field!r} value {val!r} != demanded exact value {want!r} "
                f"(§6.4 demands.fields_exact, Finding 18)"
            )

    return True, None


def compute_item_status(
    req: dict, claims_for_req: list[dict], floor: dict, profile: dict | None, profile_id: str,
    subject_identity, producer_names: set[str], deviation_ids: set[str],
    weight_grants: dict[str, bool] | None = None,
    consumer_name: str | None = None,
):
    """§6.3. Returns (status, basis, reasons)."""
    if not claims_for_req:
        return "missing", [], {}
    reasons: dict[str, str] = {}
    basis: list[str] = []
    for c in claims_for_req:
        ok, reason = meets_item_floor(
            c, floor, profile, profile_id, subject_identity, producer_names, weight_grants,
            consumer_name,
        )
        if ok:
            basis.append(c.get("id"))
        else:
            reasons[c.get("id")] = reason
    if basis:
        return "satisfied", basis, reasons
    if any(c.get("status") in ("evidenced", "partial") for c in claims_for_req):
        return "partial", [], reasons
    if req.get("id") in deviation_ids:
        return "deviation-declared", [], reasons
    return "gap", [], reasons


def compute_crosscutting_status(
    req: dict, all_claims: list[dict], profile: dict | None, deviation_ids: set[str],
    weight_grants: dict[str, bool] | None = None,
):
    """§6.4. Returns (status, basis, reasons). Fail-closed choice: an EMPTY candidate set (no
    evidenced claim among `over`) is never silently `satisfied` — it falls to `partial` (or
    `deviation-declared`), since vacuous truth over zero claims is not evidence of anything."""
    over = req.get("over")
    if over == "all":
        candidates = [c for c in all_claims if isinstance(c, dict) and c.get("status") == "evidenced"]
    else:
        overset = set(over or [])
        candidates = [
            c for c in all_claims
            if isinstance(c, dict) and c.get("clause") in overset and c.get("status") == "evidenced"
        ]
    demands = req.get("demands") or {}
    reasons: dict[str, str] = {}
    basis: list[str] = []
    offending: list[str] = []
    for c in candidates:
        ok, reason = meets_demands(c, demands, profile, weight_grants)
        if ok:
            basis.append(c.get("id"))
        else:
            offending.append(c.get("id"))
            reasons[c.get("id")] = reason
    if candidates and not offending:
        return "satisfied", basis, reasons
    if req.get("id") in deviation_ids:
        return "deviation-declared", basis, reasons
    if not candidates:
        reasons["_no_candidates"] = (
            "no evidenced claim found among `over` — a cross-cutting requirement is never "
            "vacuously satisfied (§6.4, fail-closed)"
        )
    return "partial", basis, reasons


def compute_coverage(contract: dict, package: dict, package_path: Path) -> dict:
    """`coverage(contract, package)` — protocol.md §6, total and deterministic.

    `package_path` is REQUIRED (Finding 1): coverage must read the format validator's own
    effective-weight verdict (`claim_weight_grants`), which means running the bound profile's
    package validator (`check_core.validate`, bound to the package's own declared meaning —
    `check_acceptance.py` only for `acceptance/verification`, its historical compatibility entry)
    over the file on disk — a claim's `weight` field alone is never trusted.

    Returns:
        {
          "requirements": {req_id: {"status", "basis", "reasons", "mandatory"}},
          "summary": {mandatory_total, mandatory_satisfied, optional_total, optional_satisfied,
                      acceptable},
          "record_errors": [...],   # over-strong declared epistemic_tier (§6.1) — always ERRORS
          "warnings": [...],        # unknown-profile-binding notices
          "profile_id": str,
          "subject_identity": ...,
          "weight_grants": {claim_id: bool},
          "ca_reporter": the package validator's Reporter (diagnostic only),
        }
    """
    reqs = contract.get("requirement")
    reqs = [r for r in reqs if isinstance(r, dict)] if isinstance(reqs, list) else []
    claims = package.get("claim")
    claims = [c for c in claims if isinstance(c, dict)] if isinstance(claims, list) else []
    deviations = package.get("deviation")
    deviations = [d for d in deviations if isinstance(d, dict)] if isinstance(deviations, list) else []
    deviation_ids = {d.get("requirement") for d in deviations if _nonempty(d.get("requirement"))}

    # The package's certified subject identity, whichever B1 kind it carries (git-revision,
    # content-digest or components — reusing check_core's classification, never re-implemented).
    # `freshness = "delivered-revision"` (§6.2 cond 7 below) compares this against a revision-
    # shaped `captured_at_revision` field, so it is only ever satisfiable for a git-revision
    # (commit) identity — unchanged scope, §6.6 item 4, protocol.md §7.
    _subj_kind, subject_identity = check_core.subject_identity_value(package.get("subject") or {})
    producer_names = producer_identity_set(contract, package)
    # §3.7 (§6.2 cond 8 third-party branch): the contract's own consumer identity.
    consumer_name = ((contract.get("parties") or {}).get("consumer") or {}).get("name")

    profile_id = package_profile_id(package)
    profile = PROFILES.get(profile_id) if profile_id is not None else None

    warnings: list[str] = []
    if profile_id is None:
        warnings.append(
            "package declares no [format].profile (B12: REQUIRED at 0.3.0, no compatibility "
            "default) — falling back to core-only tiering (every record lacking an explicit "
            "epistemic_tier is indeterminate) and no profile floor can be evaluated"
        )
    elif profile is None:
        warnings.append(
            f"package declares profile {profile_id!r}, which has no known binding in "
            f"profiles.py — falling back to core-only tiering (every record lacking an "
            f"explicit epistemic_tier is indeterminate) and no profile floor can be evaluated"
        )

    weight_grants, ca_reporter = claim_weight_grants(package_path, claims, profile)
    if profile is not None:
        profile = {**profile, "family_ceiling": getattr(ca_reporter, "families", {})}
    record_errors = collect_tier_errors(claims, profile)

    requirements: dict[str, dict] = {}
    mandatory_total = mandatory_satisfied = 0
    optional_total = optional_satisfied = 0

    # Finding 18: `over` must never name a cross-cutting requirement id (§3.1 rule 4, no
    # nesting). Coverage itself must not silently evaluate a nested reference either.
    crosscut_ids = {r.get("id") for r in reqs if r.get("kind") == "cross-cutting" and _nonempty(r.get("id"))}

    for req in sorted(reqs, key=lambda r: r.get("id", "")):
        rid = req.get("id")
        if not _nonempty(rid):
            continue
        mandatory = bool(req.get("mandatory"))
        kind = req.get("kind", "item")
        if kind == "cross-cutting":
            over = req.get("over")
            if isinstance(over, list) and (set(over) & crosscut_ids):
                status, basis, reasons = "partial", [], {
                    "_nesting": (
                        f"'over' names a cross-cutting requirement id "
                        f"({sorted(set(over) & crosscut_ids)}) — no nesting in /0 (§3.1 rule 4, "
                        f"Finding 18); this cross-cutting requirement is a contract error, never "
                        f"evaluated as satisfied"
                    )
                }
            else:
                status, basis, reasons = compute_crosscutting_status(
                    req, claims, profile, deviation_ids, weight_grants,
                )
        else:
            claims_for_req = sorted(
                (c for c in claims if c.get("clause") == rid), key=lambda c: c.get("id", "")
            )
            floor = req.get("evidence") or {}
            status, basis, reasons = compute_item_status(
                req, claims_for_req, floor, profile, profile_id, subject_identity,
                producer_names, deviation_ids, weight_grants, consumer_name,
            )
        requirements[rid] = {
            "status": status, "basis": basis, "reasons": reasons, "mandatory": mandatory,
        }
        if mandatory:
            mandatory_total += 1
            if status == "satisfied":
                mandatory_satisfied += 1
        else:
            optional_total += 1
            if status == "satisfied":
                optional_satisfied += 1

    summary = {
        "mandatory_total": mandatory_total,
        "mandatory_satisfied": mandatory_satisfied,
        "optional_total": optional_total,
        "optional_satisfied": optional_satisfied,
        "acceptable": mandatory_satisfied == mandatory_total,
    }
    return {
        "requirements": requirements,
        "summary": summary,
        "record_errors": record_errors,
        "warnings": warnings,
        "profile_id": profile_id,
        "subject_identity": subject_identity,
        "weight_grants": weight_grants,
        "ca_reporter": ca_reporter,
    }


def print_coverage_table(cov: dict, file=sys.stdout) -> None:
    print(f"coverage (profile: {cov['profile_id']!r})", file=file)
    for rid in sorted(cov["requirements"]):
        r = cov["requirements"][rid]
        tag = "mandatory" if r["mandatory"] else "optional"
        print(f"  {rid}: {r['status']} [{tag}] basis={r['basis']}", file=file)
        for cid in sorted(r["reasons"]):
            print(f"      {cid}: {r['reasons'][cid]}", file=file)
    s = cov["summary"]
    print(
        f"  summary: mandatory {s['mandatory_satisfied']}/{s['mandatory_total']}, "
        f"optional {s['optional_satisfied']}/{s['optional_total']}, "
        f"acceptable={s['acceptable']}",
        file=file,
    )
    for w in cov["warnings"]:
        print(f"  WARN: {w}", file=file)
    for e in cov["record_errors"]:
        print(f"  ERROR: {e}", file=file)


# ---------------------------------------------------------------------------------------------
# Assurance class + spec maturity — protocol.md §3.7.
#
# CLASS-RUNG mechanism: the class table (`spec/assurance-classes.toml`) is DATA the tool reads
# generically (P11) — no scheme or level is hard-coded here, only the file's shape. Adding a
# level, or a second scheme, never touches this module.
# ---------------------------------------------------------------------------------------------

_ASSURANCE_TABLE_PATH = _HERE.parent / "spec" / "assurance-classes.toml"
_ASSURANCE_TABLE_CACHE: dict | None = None

# The axes a class-table level row and a `[requirement.evidence]` floor table are BOTH shaped by
# — the same field names on both sides is the whole trick that lets one comparison function serve
# both "does this requirement meet its class target" and "does this override raise, not lower".
_CLASS_AXES = (
    "min_tier", "weighted_required", "control_required", "recipe_required", "independence",
    "freshness", "build_inputs_required", "tool_qualification_required", "coverage_min",
)


def _load_assurance_class_table() -> dict:
    """Loads and caches `spec/assurance-classes.toml`. Returns
    {"scheme": str, "levels": {int: level_row_dict}}. Raises RuntimeError on a malformed table —
    a broken CLASS-rung data file is a defect the tool must never silently tolerate."""
    global _ASSURANCE_TABLE_CACHE
    if _ASSURANCE_TABLE_CACHE is not None:
        return _ASSURANCE_TABLE_CACHE
    doc, err = load_toml(_ASSURANCE_TABLE_PATH)
    if err or not isinstance(doc, dict):
        raise RuntimeError(f"cannot load assurance class table {_ASSURANCE_TABLE_PATH}: {err}")
    scheme = ((doc.get("document") or {}).get("scheme"))
    if not _nonempty(scheme):
        raise RuntimeError(f"{_ASSURANCE_TABLE_PATH}: [document].scheme must be a nonempty string")
    levels: dict[int, dict] = {}
    for row in doc.get("level") or []:
        if not isinstance(row, dict) or not isinstance(row.get("level"), int) or isinstance(row.get("level"), bool):
            raise RuntimeError(f"{_ASSURANCE_TABLE_PATH}: every [[level]] must carry an integer 'level'")
        levels[row["level"]] = row
    if not levels:
        raise RuntimeError(f"{_ASSURANCE_TABLE_PATH}: no [[level]] rows declared")
    _ASSURANCE_TABLE_CACHE = {"scheme": scheme, "levels": levels}
    return _ASSURANCE_TABLE_CACHE


def parse_assurance_class(value) -> tuple[str, int] | None:
    """`"<scheme>/<level>"` -> (scheme, level_int), or None on any shape failure. Never raises —
    the caller reports the shape error with full context."""
    if not isinstance(value, str) or "/" not in value:
        return None
    scheme, _, level_s = value.rpartition("/")
    if not _nonempty(scheme) or not level_s.isdigit():
        return None
    return scheme, int(level_s)


def resolve_assurance_class(rep: Reporter, ctx: str, value) -> dict | None:
    """Parses and resolves an `assurance_class` field to its level row, reporting a shape/lookup
    ERROR and returning None on any failure. `value` absent is NOT an error here — the caller
    decides what absence means (contract-level: no class floors; requirement-level: no override)."""
    parsed = parse_assurance_class(value)
    if parsed is None:
        rep.error(f"{ctx}: assurance_class must be a string \"<scheme>/<level>\", got {value!r} (§3.7)")
        return None
    scheme, level = parsed
    try:
        table = _load_assurance_class_table()
    except RuntimeError as e:
        rep.error(f"{ctx}: {e}")
        return None
    if scheme != table["scheme"]:
        rep.error(
            f"{ctx}: assurance_class scheme {scheme!r} is not registered — the table at "
            f"{_ASSURANCE_TABLE_PATH} declares scheme {table['scheme']!r} (§3.7)"
        )
        return None
    row = table["levels"].get(level)
    if row is None:
        rep.error(
            f"{ctx}: assurance_class level {level} is not registered for scheme {scheme!r} — "
            f"known levels: {sorted(table['levels'])} (§3.7)"
        )
        return None
    return row


def _axis_actual_from_evidence(ev: dict) -> dict:
    """The SAME axis shape a class-table level row carries, read off a requirement's
    `[requirement.evidence]` floor table, defaults matching §3.1 rule 5 / §3.7."""
    return {
        "min_tier": ev.get("min_tier"),
        "weighted_required": ev.get("weighted_required", True),
        "control_required": ev.get("control_required", False),
        "recipe_required": ev.get("recipe_required", False),
        "independence": ev.get("independence"),
        "freshness": ev.get("freshness"),
        "build_inputs_required": ev.get("build_inputs_required", False),
        "tool_qualification_required": ev.get("tool_qualification_required", False),
        "coverage_min": ev.get("coverage_min") if isinstance(ev.get("coverage_min"), dict) else None,
    }


def _class_axis_violations(actual: dict, target: dict) -> list[str]:
    """Every axis on which `actual` is WEAKER than `target`. Shared by the maturity rule
    (actual = a requirement's evidence floor, target = its effective class's level row) and the
    per-requirement override "may only raise" check (actual = the override's level row,
    target = the contract's level row) — both sides share the SAME axis names (`_CLASS_AXES`),
    by design (§3.7)."""
    out: list[str] = []
    if TIER_RANK.get(actual.get("min_tier"), -1) < TIER_RANK.get(target.get("min_tier"), -1):
        out.append(f"min_tier {actual.get('min_tier')!r} below class target {target.get('min_tier')!r}")
    for b in (
        "weighted_required", "control_required", "recipe_required",
        "build_inputs_required", "tool_qualification_required",
    ):
        if target.get(b) and not actual.get(b):
            out.append(f"{b}={actual.get(b)!r} but class target requires true")
    if INDEPENDENCE_RANK.get(actual.get("independence"), -1) < INDEPENDENCE_RANK.get(target.get("independence"), -1):
        out.append(f"independence {actual.get('independence')!r} below class target {target.get('independence')!r}")
    if FRESHNESS_RANK.get(actual.get("freshness"), -1) < FRESHNESS_RANK.get(target.get("freshness"), -1):
        out.append(f"freshness {actual.get('freshness')!r} below class target {target.get('freshness')!r}")
    t_cov = target.get("coverage_min")
    if isinstance(t_cov, dict):
        a_cov = actual.get("coverage_min")
        if not isinstance(a_cov, dict):
            out.append(f"coverage_min absent but class target requires >= {t_cov}")
        elif a_cov.get("metric") != t_cov.get("metric"):
            out.append(
                f"coverage_min metric {a_cov.get('metric')!r} does not match class target "
                f"metric {t_cov.get('metric')!r} (incomparable)"
            )
        elif not isinstance(a_cov.get("value"), (int, float)) or isinstance(a_cov.get("value"), bool) or a_cov.get("value") < t_cov.get("value"):
            out.append(f"coverage_min value {a_cov.get('value')!r} below class target {t_cov.get('value')!r}")
    return out


# Declared metric-strength ordering for `coverage_min.metric` (this file mirrors
# assurance-classes.toml's own header comment: "statement, branch, decision, mcdc,
# proof-obligation, roughly DO-178C-inspired ordering, weakest to strongest"). Used ONLY by
# `check_assurance_table_monotonic` below, to compare two DIFFERENT class-table LEVELS that may
# legitimately choose different metrics (§6.2 cond 11's "a different metric is incomparable,
# never a pass" is a runtime rule about ONE claim's own evidence against ONE requirement's own
# floor — not a claim about which of two metrics is the stronger structural-coverage target).
_METRIC_STRENGTH = {"statement": 0, "branch": 1, "decision": 2, "mcdc": 3, "proof-obligation": 4}

# Ordinal reading of the DOCUMENTARY `bounds` axis (assurance-classes.toml's own field-meaning
# comment: "any" | "bounded" | "unbounded"), weakest to strongest. NOT read by any runtime floor
# check (§3.7: `bounds` is RESIDUAL, not mechanically compared) — used only by the monotonicity
# selftest below, since the table's header claims monotonicity on this axis too.
_BOUNDS_RANK = {"any": 0, "bounded": 1, "unbounded": 2}


def _coverage_min_level_weaker(lo: dict, hi: dict) -> str | None:
    """Whether `hi`'s `coverage_min` is a WEAKENING of `lo`'s, comparing two class-table LEVELS
    (`lo` = level N-1, `hi` = level N). Returns a violation string, or None if `hi` is at least
    as strict. A metric absent from `_METRIC_STRENGTH` fails closed (never a silent pass)."""
    lo_cov, hi_cov = lo.get("coverage_min"), hi.get("coverage_min")
    if not isinstance(lo_cov, dict):
        return None  # nothing at the lower level to weaken
    if not isinstance(hi_cov, dict):
        return "coverage_min dropped entirely at the higher level"
    lo_m, hi_m = lo_cov.get("metric"), hi_cov.get("metric")
    if lo_m not in _METRIC_STRENGTH or hi_m not in _METRIC_STRENGTH:
        return f"coverage_min metric {hi_m!r}/{lo_m!r} not in the declared strength ordering {sorted(_METRIC_STRENGTH)}"
    if _METRIC_STRENGTH[hi_m] > _METRIC_STRENGTH[lo_m]:
        return None  # a strictly stronger metric at the higher level; value is not compared
    if _METRIC_STRENGTH[hi_m] < _METRIC_STRENGTH[lo_m]:
        return f"coverage_min metric {hi_m!r} is weaker than {lo_m!r}"
    hi_v, lo_v = hi_cov.get("value"), lo_cov.get("value")
    if not isinstance(hi_v, (int, float)) or isinstance(hi_v, bool) or not isinstance(lo_v, (int, float)) or isinstance(lo_v, bool) or hi_v < lo_v:
        return f"coverage_min value {hi_v!r} below {lo_v!r} at the same metric {hi_m!r}"
    return None


def _required_meaning_entries(level_row: dict, ctx: str) -> tuple[list[tuple[str, "frozenset | None"]], list[str]]:
    """`(profile, when_kind)` pairs for one level's `required_meaning` list, `when_kind` as a
    `frozenset` of kind tokens, or `None` for an unconditional entry — an ABSENT or EMPTY
    `when_kind` are BOTH unconditional, matching the runtime check's own `not when_kind` reading
    (§3.7, `applies = not when_kind or ...`). FAIL CLOSED on a malformed shape:
    a non-list `required_meaning`, a non-dict entry, a missing/non-string `profile`, or a non-list
    `when_kind` is reported as a violation string, never silently skipped or silently accepted —
    returns `(entries, violation_strings)`."""
    entries: list[tuple[str, "frozenset | None"]] = []
    errors: list[str] = []
    rm_list = level_row.get("required_meaning")
    if rm_list is None:
        rm_list = []
    elif not isinstance(rm_list, list):
        return entries, [f"{ctx}: required_meaning must be a list, got {rm_list!r}"]
    for i, rm in enumerate(rm_list):
        if not isinstance(rm, dict):
            errors.append(f"{ctx}[{i}]: required_meaning entry must be a table, got {rm!r}")
            continue
        profile = rm.get("profile")
        if not isinstance(profile, str) or not profile:
            errors.append(f"{ctx}[{i}]: required_meaning.profile must be a nonempty string, got {profile!r}")
            continue
        wk = rm.get("when_kind")
        if wk is not None and not isinstance(wk, list):
            errors.append(f"{ctx}[{i}]: required_meaning.when_kind must be a list, got {wk!r}")
            continue
        # Every element must be a nonempty string
        # BEFORE `frozenset()` construction — `when_kind=[1]` was silently accepted, and a nested
        # list/table raised an uncaught TypeError instead of a reported violation.
        if isinstance(wk, list) and not all(isinstance(x, str) and x for x in wk):
            errors.append(
                f"{ctx}[{i}]: required_meaning.when_kind elements must all be nonempty strings, "
                f"got {wk!r}"
            )
            continue
        entries.append((profile, frozenset(wk) if wk else None))
    return entries, errors


def _required_meaning_covered(lo_when, hi_whens: list) -> bool:
    """Whether a level-N `required_meaning` entry scoped to `lo_when` (a `frozenset`, or `None`
    for unconditional) is still required, at least as broadly, at level N+1, given that profile's
    own `when_kind` values at level N+1 (`hi_whens`) — ALL of that profile's rows at level N+1,
    unioned: runtime applicability (§3.7,
    `applies = not when_kind or subject_kind in when_kind`) OR-combines every row for a profile, so
    a lower row requiring profile P for kinds `{a, b}` is genuinely covered by an EQUIVALENT SPLIT
    at the higher level — two P rows, `{a}` and `{b}` — even though neither row alone is a
    superset; requiring one individual superset rejected that legitimate refactor. An unconditional
    entry at N+1 (`None`) covers anything; a scoped entry at N+1 can never cover an unconditional
    entry at N — it does not apply to every kind the way the lower level's entry did."""
    if any(hi_when is None for hi_when in hi_whens):
        return True
    if lo_when is None:
        return False
    union: frozenset = frozenset().union(*hi_whens) if hi_whens else frozenset()
    return lo_when <= union


def _required_meaning_monotonic_violations(lo_entries: list, hi_entries: list, ctx: str) -> list[str]:
    """`required_meaning` is monotone too — every profile a level requires
    (unconditionally or for a given `when_kind` set) must still be required, at least as broadly,
    at the next level up. `required_meaning` may only GAIN reach across levels, never lose it.
    Takes already-validated `(profile, when_kind)` entry lists (see `_required_meaning_entries`),
    not the raw level rows — shape errors are reported once per level, not once per adjacent pair."""
    out: list[str] = []
    hi_by_profile: dict[object, list] = {}
    for profile, when in hi_entries:
        hi_by_profile.setdefault(profile, []).append(when)
    for profile, lo_when in lo_entries:
        if not _required_meaning_covered(lo_when, hi_by_profile.get(profile, [])):
            scope = "unconditionally" if lo_when is None else f"when_kind={sorted(lo_when)}"
            out.append(
                f"{ctx}: required_meaning profile {profile!r} (required {scope} at the lower "
                f"level) is not still required, at least as broadly, at the higher level"
            )
    return out


def _monotonic_violations(levels: dict) -> list[str]:
    """The pair-by-pair monotonicity check itself, over any `{level_int: level_row}` mapping —
    factored out from `check_assurance_table_monotonic` so the selftest can feed it a synthetic
    (deliberately non-monotone) table without touching the shipped file."""
    out: list[str] = []
    rm_by_level: dict[int, list] = {}
    for n in sorted(levels):
        entries, errors = _required_meaning_entries(levels[n], f"level {n} required_meaning")
        rm_by_level[n] = entries
        out.extend(errors)
    for n in sorted(levels):
        if n - 1 not in levels:
            continue
        lo, hi = levels[n - 1], levels[n]
        ctx = f"level {n} vs level {n - 1}"
        if TIER_RANK.get(hi.get("min_tier"), -1) < TIER_RANK.get(lo.get("min_tier"), -1):
            out.append(f"{ctx}: min_tier {hi.get('min_tier')!r} is weaker than {lo.get('min_tier')!r}")
        for b in (
            "weighted_required", "control_required", "recipe_required",
            "build_inputs_required", "tool_qualification_required",
        ):
            if lo.get(b) and not hi.get(b):
                out.append(f"{ctx}: {b} is true at level {n - 1} but false at level {n}")
        if INDEPENDENCE_RANK.get(hi.get("independence"), -1) < INDEPENDENCE_RANK.get(lo.get("independence"), -1):
            out.append(f"{ctx}: independence {hi.get('independence')!r} is weaker than {lo.get('independence')!r}")
        if FRESHNESS_RANK.get(hi.get("freshness"), -1) < FRESHNESS_RANK.get(lo.get("freshness"), -1):
            out.append(f"{ctx}: freshness {hi.get('freshness')!r} is weaker than {lo.get('freshness')!r}")
        cov_violation = _coverage_min_level_weaker(lo, hi)
        if cov_violation:
            out.append(f"{ctx}: {cov_violation}")
        lo_b, hi_b = lo.get("bounds"), hi.get("bounds")
        if lo_b not in _BOUNDS_RANK or hi_b not in _BOUNDS_RANK:
            out.append(
                f"{ctx}: bounds {hi_b!r}/{lo_b!r} not in the documented any/bounded/unbounded "
                f"ordering (documentary axis)"
            )
        elif _BOUNDS_RANK[hi_b] < _BOUNDS_RANK[lo_b]:
            out.append(f"{ctx}: bounds {hi_b!r} is weaker than {lo_b!r} (documentary axis, Finding F4)")
        out.extend(_required_meaning_monotonic_violations(rm_by_level[n - 1], rm_by_level[n], ctx))
    return out


def check_assurance_table_monotonic() -> list[str]:
    """Checks monotonicity of every assurance-class axis.
    `spec/assurance-classes.toml`'s own header claims "every axis is at least as strict at level
    N+1 as at level N" — for the mechanically-compared axes (`_CLASS_AXES`, the same axes
    `_class_axis_violations` compares a requirement's floor against its class target), the
    documentary `bounds` axis (§3.7), and `required_meaning` (a profile a level requires,
    unconditionally or scoped by `when_kind`, must still be required at least as broadly one level
    up). Returns one violation string per broken axis (or `required_meaning` entry) per adjacent
    level pair; an empty list means the table holds monotonic end to end."""
    table = _load_assurance_class_table()
    return _monotonic_violations(table["levels"])


def check_contract_assurance_class(rep: Reporter, contract: dict) -> None:
    """protocol.md §3.7 — the maturity rule (0.3 closure §4d). Runs as part of `check_contract`.

    1. Shape/lookup of `[acceptance].assurance_class` and every `[[requirement]].assurance_class`
       (already partly shape-checked in `_check_requirement_fields`; this function does the FULL
       resolution and the cross-checks that need the whole contract).
    2. Per-requirement override may only RAISE (§3.5-style tightening, applied WITHIN one
       contract version, not across a `supersedes` chain).
    3. Maturity rule: a `firm` requirement of a `final`-phase contract MUST meet its effective
       class's floors (ERROR naming requirement, floor, class); any requirement while the
       contract's phase is not `final` gets a NOTE (INFO — §5.2's existing "decisions there are
       already provisional" logic, never an error) listing the same gap. A `draft` requirement in
       a `final`-phase contract is its OWN hard ERROR (§3.5,
       `_check_requirement_fields`) — that combination never reaches this function's NOTE branch,
       so this rule never double-reports it.
    4. `required_meaning`: contract-level (not per-requirement) — every meaning the contract's
       OWN assurance_class demands must appear in `[acceptance].profiles_required`, scoped by
       `when_kind` against `[subject].kind` when given.
    5. The spec-clarity summary line: firm vs draft requirement counts (always emitted).
    """
    acceptance = contract.get("acceptance") if isinstance(contract.get("acceptance"), dict) else {}
    phase = acceptance.get("phase") or "final"
    if phase not in PHASE_VALUES:
        phase = "final"  # already reported as a shape error elsewhere; do not cascade here

    contract_class_value = acceptance.get("assurance_class")
    contract_row = None
    if contract_class_value is not None:
        contract_row = resolve_assurance_class(rep, "[acceptance].assurance_class", contract_class_value)

    raw_reqs = contract.get("requirement")
    raw_reqs = raw_reqs if isinstance(raw_reqs, list) else []

    firm_count = draft_count = 0
    for req in raw_reqs:
        if not isinstance(req, dict):
            continue
        rid = req.get("id") or "?"
        firmness = req.get("firmness") or "firm"
        if firmness == "draft":
            draft_count += 1
        else:
            firm_count += 1

        if req.get("kind", "item") != "item":
            continue  # class floors compare [requirement.evidence]; cross-cutting has none (§3.1 rule 4)

        req_class_value = req.get("assurance_class")
        req_row = None
        if req_class_value is not None:
            req_row = resolve_assurance_class(rep, f"requirement {rid!r} assurance_class", req_class_value)
            if req_row is not None and contract_row is not None:
                raise_violations = _class_axis_violations(req_row, contract_row)
                if raise_violations:
                    rep.error(
                        f"requirement {rid!r}: assurance_class override {req_class_value!r} is "
                        f"WEAKER than the contract's assurance_class {contract_class_value!r} on: "
                        f"{'; '.join(raise_violations)} — a per-requirement override may only "
                        f"RAISE the class, never lower it (§3.7)"
                    )

        effective_row = req_row if req_row is not None else contract_row
        effective_ref = req_class_value if req_row is not None else contract_class_value
        if effective_row is None:
            continue  # no class declared anywhere for this requirement — today's behavior (§3.7 item 2)

        evidence = req.get("evidence") if isinstance(req.get("evidence"), dict) else {}
        actual = _axis_actual_from_evidence(evidence)
        gap = _class_axis_violations(actual, effective_row)
        if not gap:
            continue
        if phase == "final" and firmness == "firm":
            rep.error(
                f"requirement {rid!r}: below its assurance class {effective_ref!r} target on: "
                f"{'; '.join(gap)} (§3.7, the maturity rule)"
            )
        elif phase != "final":
            rep.warn(
                f"NOTE (spec-clarity gap, not an error — requirement {rid!r} is "
                f"{'draft' if firmness == 'draft' else f'in phase {phase!r}'}): below its "
                f"assurance class {effective_ref!r} target on: {'; '.join(gap)} (§3.7)"
            )
        # else: phase == "final" and firmness == "draft" — §3.5 already makes
        # this combination its OWN hard ERROR in `_check_requirement_fields`; no separate NOTE
        # here, so the same defect is never reported twice.

    if contract_row is not None:
        profiles_required = set(acceptance.get("profiles_required") or [])
        subject_kind = (contract.get("subject") or {}).get("kind") if isinstance(contract.get("subject"), dict) else None
        for rm in contract_row.get("required_meaning") or []:
            if not isinstance(rm, dict):
                continue
            profile = rm.get("profile")
            when_kind = rm.get("when_kind")
            applies = not when_kind or subject_kind in (when_kind or [])
            if not applies or profile in profiles_required:
                continue
            msg = (
                f"assurance class {contract_class_value!r} requires profile {profile!r} in "
                f"[acceptance].profiles_required"
            )
            if when_kind:
                msg += f" (subject kind {subject_kind!r} matches {when_kind})"
            msg += " (§3.7)"
            if phase == "final":
                rep.error(msg)
            else:
                rep.warn(f"NOTE (spec-clarity gap, not an error): {msg}")

    rep.warn(f"NOTE (spec-clarity): {firm_count} firm / {draft_count} draft requirement(s)")


def check_contract(doc: dict) -> Reporter:
    rep = Reporter("contract")

    document = doc.get("document")
    if not isinstance(document, dict):
        rep.error("[document] section missing")
        document = {}
    else:
        if document.get("protocol") != PROTOCOL_ID:
            rep.error(f"[document].protocol must be {PROTOCOL_ID!r}, got {document.get('protocol')!r}")
        if not isinstance(document.get("minor"), int) or isinstance(document.get("minor"), bool):
            rep.error("[document].minor must be an integer")
        if document.get("kind") != "contract":
            rep.error(f"[document].kind must be 'contract', got {document.get('kind')!r}")
        if not _nonempty(document.get("id")):
            rep.error("[document].id must be a nonempty string")
        if not isinstance(document.get("version"), int) or isinstance(document.get("version"), bool):
            rep.error("[document].version must be an integer")
        if not _nonempty(document.get("issued_at")):
            rep.error("[document].issued_at must be a nonempty string")
        issued_by = document.get("issued_by")
        if issued_by not in ISSUED_BY_VALUES:
            rep.error(f"[document].issued_by must be one of {sorted(ISSUED_BY_VALUES)}, got {issued_by!r}")
        status = document.get("status")
        if status not in CONTRACT_STATUSES:
            rep.error(f"[document].status must be one of {sorted(CONTRACT_STATUSES)}, got {status!r}")

    parties = doc.get("parties")
    consumer_name = None
    producer_name = None
    if not isinstance(parties, dict):
        rep.error("[parties] section missing")
    else:
        consumer = parties.get("consumer")
        if not isinstance(consumer, dict) or not _nonempty(consumer.get("name")):
            rep.error("[parties].consumer.name must be a nonempty string (§3.3: consumer named)")
        else:
            consumer_name = consumer["name"]
        producer = parties.get("producer")
        if not isinstance(producer, dict) or not _nonempty(producer.get("name")):
            rep.error("[parties].producer.name must be a nonempty string")
        else:
            producer_name = producer["name"]

        # §3.4a — party boundary: OPTIONAL, absent means "internal". The core never branches on
        # it except here: cross-org REQUIRES disclosure and integrity to be stated (ERROR if
        # missing). [parties.boundary_terms] carries the rest (free strings, closed key set).
        boundary = parties.get("boundary")
        if boundary is None:
            boundary = "internal"
        elif boundary not in PARTY_BOUNDARIES:
            rep.error(
                f"[parties].boundary must be one of {sorted(PARTY_BOUNDARIES)}, got {boundary!r} (§3.4a)"
            )
            boundary = "internal"
        terms = parties.get("boundary_terms")
        if terms is not None:
            if not isinstance(terms, dict):
                rep.error("[parties.boundary_terms] must be a table (§3.4a)")
                terms = {}
            else:
                for k, v in terms.items():
                    if k not in BOUNDARY_TERM_FIELDS:
                        rep.error(
                            f"[parties.boundary_terms].{k} is not a declared parameter "
                            f"({sorted(BOUNDARY_TERM_FIELDS)}) (§3.4a)"
                        )
                    elif not _nonempty(v):
                        rep.error(f"[parties.boundary_terms].{k}, if present, must be a nonempty string (§3.4a)")
        if boundary == "cross-org":
            terms = terms or {}
            if not _nonempty(terms.get("disclosure")):
                rep.error(
                    "[parties.boundary_terms].disclosure must be a nonempty string when "
                    "[parties].boundary = 'cross-org' (§3.4a)"
                )
            if not _nonempty(terms.get("integrity")):
                rep.error(
                    "[parties.boundary_terms].integrity must be a nonempty string when "
                    "[parties].boundary = 'cross-org' (§3.4a)"
                )
            # The ratification requirement (§3.3, §3.4: [ratification] REQUIRED iff issued_by =
            # 'producer' and status = 'ratified') is ALREADY unconditional on boundary — a
            # producer-drafted cross-org contract binds only once ratified, exactly like an
            # internal one; no second, boundary-specific rule is added here (verified below,
            # reused as-is).

    # ratification: REQUIRED iff issued_by == producer and status == ratified.
    issued_by = document.get("issued_by")
    status = document.get("status")
    ratification = doc.get("ratification")
    needs_ratification = issued_by == "producer" and status == "ratified"
    if needs_ratification:
        if not isinstance(ratification, dict):
            rep.error("[ratification] is REQUIRED when issued_by='producer' and status='ratified'")
        else:
            if consumer_name is not None and ratification.get("by") != consumer_name:
                rep.error(
                    f"[ratification].by must equal [parties].consumer.name "
                    f"({consumer_name!r}), got {ratification.get('by')!r}"
                )
            if not _nonempty(ratification.get("at")):
                rep.error("[ratification].at must be a nonempty string")
    elif isinstance(ratification, dict):
        rep.warn(
            "[ratification] is present but issued_by/status do not require it "
            "(§3.3 — harmless, but check status/issued_by are what was intended)"
        )

    # subject
    subject = doc.get("subject")
    profiles_required = None
    if not isinstance(subject, dict):
        rep.error("[subject] section missing")
    else:
        if not _nonempty(subject.get("kind")):
            rep.error("[subject].kind must be a nonempty string")
        if not _nonempty(subject.get("name")):
            rep.error("[subject].name must be a nonempty string")
        if not _nonempty(subject.get("profile")):
            rep.error("[subject].profile must be a nonempty string (§3.1 rule 7)")

    # Policy (OPTIONAL, §3): `.hash`, when present,
    # is M11 over the policy bytes under the `normative-reference:` domain (the same domain the
    # format core uses for a governing-document digest); the retired bare `sha-512:<hex>` form is
    # an explicit ERROR here too, same as contract/package/decision (§7, one wire form).
    policy = doc.get("policy")
    if isinstance(policy, dict):
        _reject_bare_m11_wire(rep, policy.get("hash"), "normative-reference", "[policy].hash")

    # acceptance
    acceptance = doc.get("acceptance")
    if not isinstance(acceptance, dict):
        rep.error("[acceptance] section missing")
    else:
        rule = acceptance.get("rule")
        if rule not in ACCEPTANCE_RULES:
            rep.error(f"[acceptance].rule must be one of {sorted(ACCEPTANCE_RULES)}, got {rule!r}")
        mode = acceptance.get("consumer_verification")
        if mode not in MODE_RANK:
            rep.error(
                f"[acceptance].consumer_verification must be one of {VERIFICATION_MODES}, "
                f"got {mode!r}"
            )
        if not _nonempty(acceptance.get("authority")):
            rep.error("[acceptance].authority must be a nonempty string")
        profiles_required = acceptance.get("profiles_required")
        if not isinstance(profiles_required, list) or not all(_nonempty(p) for p in profiles_required):
            rep.error("[acceptance].profiles_required must be a list of nonempty strings")
            profiles_required = []
        stale_after = acceptance.get("stale_after")
        if stale_after is not None and not is_iso8601_duration(stale_after):
            rep.error(
                f"[acceptance].stale_after must be an ISO-8601 duration (P...), got {stale_after!r}"
            )
        verifiers = acceptance.get("verifiers")
        if verifiers is not None and not (isinstance(verifiers, list) and all(_nonempty(v) for v in verifiers)):
            rep.error("[acceptance].verifiers, if present, must be a list of nonempty strings")
        threshold = acceptance.get("decision_threshold")
        if threshold is not None and (isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 1):
            rep.error("[acceptance].decision_threshold, if present, must be an integer >= 1")

        # §3.1 rule 7: subject.profile must appear in profiles_required.
        if isinstance(subject, dict) and _nonempty(subject.get("profile")) and profiles_required:
            if subject["profile"] not in profiles_required:
                rep.error(
                    f"[subject].profile {subject['profile']!r} does not appear in "
                    f"[acceptance].profiles_required {profiles_required!r} (§3.1 rule 7)"
                )

    # ext
    ext = doc.get("ext")
    if ext is not None:
        if not isinstance(ext, dict):
            rep.error("[ext] must be a table")
        else:
            for k, v in ext.items():
                if not isinstance(v, dict) or "critical" not in v or not isinstance(v.get("critical"), bool):
                    rep.error(f"[ext].{k} must be a table carrying a boolean 'critical' field")
                elif v.get("critical") is True:
                    rep.error(
                        f"[ext].{k} is marked critical=true and unknown to this tool — "
                        f"unknown critical extensions are rejected (protocol.md §9 'version negotiation')"
                    )

    # phase (§3.5): optional, defaults to 'final'.
    phase = "final"
    if isinstance(acceptance, dict) and "phase" in acceptance:
        phase = acceptance.get("phase")
        if phase not in PHASE_VALUES:
            rep.error(f"[acceptance].phase must be one of {sorted(PHASE_VALUES)}, got {phase!r}")
            phase = "final"

    # [document].dropped / .reopened / .amendments (§3.5, §3.6) — shape only here; the
    # cross-version semantics (dropped ids actually absent, reopened only when phase regresses)
    # are checked by check_contract_tightening (--previous), which has both versions to compare.
    dropped = document.get("dropped")
    if dropped is not None:
        if not isinstance(dropped, list) or not all(
            isinstance(d, dict) and _nonempty(d.get("id")) and _nonempty(d.get("reason")) for d in dropped
        ):
            rep.error("[document].dropped, if present, must be a list of {id, reason} tables with nonempty strings")
    reopened = document.get("reopened")
    if reopened is not None:
        if not isinstance(reopened, dict) or not all(_nonempty(reopened.get(k)) for k in ("reason", "by")):
            rep.error("[document].reopened, if present, must be a table {reason, by} of nonempty strings")
    amendments = document.get("amendments")
    if amendments is not None and not (isinstance(amendments, list) and all(_nonempty(a) for a in amendments)):
        rep.error("[document].amendments, if present, must be a list of nonempty strings")

    # requirements
    raw_reqs = doc.get("requirement")
    if raw_reqs is None:
        raw_reqs = []
    elif not isinstance(raw_reqs, list):
        rep.error("[[requirement]] must be an array of tables")
        raw_reqs = []

    seen_ids: set[str] = set()
    all_ids: set[str] = set()
    for r in raw_reqs:
        if isinstance(r, dict) and _nonempty(r.get("id")):
            all_ids.add(r["id"])
    crosscut_ids = frozenset(
        r["id"] for r in raw_reqs
        if isinstance(r, dict) and _nonempty(r.get("id")) and r.get("kind") == "cross-cutting"
    )

    # Finding 13 (§3.1 rule 1): retired_ids shape, and self-check — a requirement id may never
    # be one this SAME document already declares retired.
    retired_ids = document.get("retired_ids")
    retired_id_set: set[str] = set()
    if retired_ids is not None:
        if not isinstance(retired_ids, list) or not all(_nonempty(x) for x in retired_ids):
            rep.error("[document].retired_ids, if present, must be a list of nonempty strings")
        else:
            retired_id_set = set(retired_ids)

    mandatory_count = 0
    for idx, req in enumerate(raw_reqs):
        ctx0 = f"requirement[{idx}]"
        if not isinstance(req, dict):
            rep.error(f"{ctx0}: must be a table")
            continue
        rid = req.get("id")
        ctx = f"requirement {rid!r}" if _nonempty(rid) else ctx0
        if not _nonempty(rid):
            rep.error(f"{ctx0}: field 'id' must be a nonempty string")
        else:
            if rid in seen_ids:
                rep.error(f"{ctx}: duplicate requirement id")
            seen_ids.add(rid)
            if rid in retired_id_set:
                rep.error(f"{ctx}: id {rid!r} is in [document].retired_ids — retired ids are never reused (§3.1 rule 1, Finding 13)")
        if req.get("mandatory") is True:
            mandatory_count += 1
        _check_requirement_fields(rep, ctx, req, all_ids, phase, crosscut_ids)

    if mandatory_count < 1:
        rep.error("contract must carry at least one mandatory requirement (§3.3)")

    # §3.7: assurance class + spec maturity — the whole-contract cross-checks that need
    # every requirement at once (override raise-only, the maturity rule, required_meaning,
    # the spec-clarity summary). Always runs; absent [acceptance].assurance_class everywhere
    # means no class floors apply and only the spec-clarity NOTE is emitted (§3.7 item 2).
    check_contract_assurance_class(rep, doc)

    return rep


def _check_requirement_fields(
    rep: Reporter, ctx: str, req: dict, all_ids: set[str], phase: str,
    crosscut_ids: frozenset = frozenset(),
) -> None:
    """The common per-requirement body of `check-contract`, factored out so `check-amendment` can
    validate a `[change.proposed]` full requirement table (add/modify ops) with the SAME rule.

    `crosscut_ids` (Finding 18) is the set of requirement ids whose `kind = "cross-cutting"` in
    the CONTAINING contract — used to reject nesting in `over`. Empty by default for callers (the
    amendment's per-op `[change.proposed]` check) that only see one requirement at a time."""
    if not _nonempty(req.get("statement")):
        rep.error(f"{ctx}: field 'statement' must be a nonempty string")
    if not isinstance(req.get("mandatory"), bool):
        rep.error(f"{ctx}: field 'mandatory' must be a bool")
    if not isinstance(req.get("waivable"), bool):
        rep.error(f"{ctx}: field 'waivable' must be a bool")
    domain = req.get("domain")
    if domain not in DOMAIN_VALUES:
        rep.error(f"{ctx}: domain must be one of {sorted(DOMAIN_VALUES)}, got {domain!r}")
    cs = req.get("clause_source")
    if cs not in CONTRACT_CLAUSE_SOURCES:
        rep.error(f"{ctx}: clause_source must be one of {sorted(CONTRACT_CLAUSE_SOURCES)}, got {cs!r}")
    if "external_ref" in req and not _nonempty(req.get("external_ref")):
        rep.error(f"{ctx}: external_ref, if present, must be a nonempty string")
    if "parent" in req and not _nonempty(req.get("parent")):
        rep.error(f"{ctx}: parent, if present, must be a nonempty string")
    # Finding 13 (§3.1 rule 1): `replaces` names the OLD id a NEW id semantically replaces.
    if "replaces" in req and not _nonempty(req.get("replaces")):
        rep.error(f"{ctx}: replaces, if present, must be a nonempty string")

    # firmness (§3.5): optional, default 'firm'; REQUIRED (any value) when phase='crystallizing'.
    firmness = req.get("firmness")
    if firmness is not None and firmness not in FIRMNESS_VALUES:
        rep.error(f"{ctx}: firmness must be one of {sorted(FIRMNESS_VALUES)}, got {firmness!r}")
    if phase == "crystallizing" and firmness is None:
        rep.error(f"{ctx}: firmness is REQUIRED when [acceptance].phase = 'crystallizing' (§3.5)")
    # A `final`-phase contract may carry ONLY `firm` requirements (§3.5/§3.7) —
    # an absent firmness defaults to firm (above), so only an EXPLICIT 'draft' trips this. Distinct
    # from the maturity rule (§3.7, `check_contract_assurance_class`): this is unconditional, not
    # scoped to a resolved assurance class, and fires even with no class declared anywhere.
    if phase == "final" and firmness == "draft":
        rep.error(
            f"{ctx}: firmness must not be 'draft' in a 'final'-phase contract — a final contract "
            f"requires every requirement to be firm (§3.5)"
        )

    relaxed = req.get("relaxed")
    if relaxed is not None:
        if not isinstance(relaxed, dict) or not all(_nonempty(relaxed.get(k)) for k in ("reason", "by")):
            rep.error(f"{ctx}: [requirement.relaxed], if present, must be a table {{reason, by}} of nonempty strings")

    kind = req.get("kind", "item")
    if kind not in REQUIREMENT_KINDS:
        rep.error(f"{ctx}: kind must be one of {sorted(REQUIREMENT_KINDS)}, got {kind!r}")
        return

    has_evidence = isinstance(req.get("evidence"), dict)
    has_demands = isinstance(req.get("demands"), dict)
    has_over = "over" in req

    if kind == "cross-cutting":
        if has_evidence:
            rep.error(f"{ctx}: kind='cross-cutting' must not carry [requirement.evidence] (§3.1 rule 4)")
        if not has_over:
            rep.error(f"{ctx}: kind='cross-cutting' requires 'over'")
        else:
            over = req.get("over")
            if over == "all":
                pass
            elif isinstance(over, list) and all(_nonempty(o) for o in over):
                unresolved = [o for o in over if o not in all_ids]
                if unresolved:
                    rep.error(f"{ctx}: 'over' names unresolved requirement id(s): {unresolved}")
                # Finding 18 (§3.1 rule 4, no nesting in /0): `over` may name item requirements
                # only — a cross-cutting requirement inside another's `over` is a contract error.
                nested = [o for o in over if o in crosscut_ids]
                if nested:
                    rep.error(
                        f"{ctx}: 'over' names cross-cutting requirement id(s) {nested} — "
                        f"'over' may name item requirements only, no nesting in /0 "
                        f"(§3.1 rule 4, Finding 18)"
                    )
            else:
                rep.error(f"{ctx}: 'over' must be the string 'all' or a list of nonempty strings")
        if not has_demands:
            rep.error(f"{ctx}: kind='cross-cutting' requires [requirement.demands]")
        else:
            _check_demands(rep, ctx, req["demands"])
    else:  # item
        if has_demands or has_over:
            rep.error(f"{ctx}: kind='item' must not carry 'over'/[requirement.demands] (§3.1 rule 4)")
        if not has_evidence:
            rep.error(f"{ctx}: kind='item' requires [requirement.evidence]")
        else:
            _check_evidence_floor(rep, ctx, req["evidence"])


def _check_demands(rep: Reporter, ctx: str, demands: dict) -> None:
    if "min_tier" in demands and demands["min_tier"] not in TIER_RANK:
        rep.error(f"{ctx}: demands.min_tier must be one of {TIER_TOKENS}")
    if "weighted_required" in demands and not isinstance(demands["weighted_required"], bool):
        rep.error(f"{ctx}: demands.weighted_required must be a bool")
    if "control_required" in demands and not isinstance(demands["control_required"], bool):
        rep.error(f"{ctx}: demands.control_required must be a bool")
    fields = demands.get("fields")
    if fields is not None:
        if not isinstance(fields, dict) or not all(
            _nonempty(k) and _nonempty(v) for k, v in fields.items()
        ):
            rep.error(f"{ctx}: demands.fields must be a table of nonempty string -> nonempty string")
    # Finding 18 (§6.4): `fields_exact` — same shape as `fields`, but the claim's field must equal
    # the WHOLE string, not just its leading token.
    fields_exact = demands.get("fields_exact")
    if fields_exact is not None:
        if not isinstance(fields_exact, dict) or not all(
            _nonempty(k) and isinstance(v, str) for k, v in fields_exact.items()
        ):
            rep.error(f"{ctx}: demands.fields_exact must be a table of nonempty string -> string")


def _check_evidence_floor(rep: Reporter, ctx: str, ev: dict) -> None:
    min_tier = ev.get("min_tier")
    if min_tier not in TIER_RANK:
        rep.error(f"{ctx}: evidence.min_tier must be one of {TIER_TOKENS}, got {min_tier!r}")
    if "weighted_required" in ev and not isinstance(ev["weighted_required"], bool):
        rep.error(f"{ctx}: evidence.weighted_required, if present, must be a bool")
    if not isinstance(ev.get("control_required"), bool):
        rep.error(f"{ctx}: evidence.control_required must be a bool")
    if not isinstance(ev.get("recipe_required"), bool):
        rep.error(f"{ctx}: evidence.recipe_required must be a bool")
    freshness = ev.get("freshness")
    if freshness not in FRESHNESS_VALUES:
        rep.error(f"{ctx}: evidence.freshness must be one of {sorted(FRESHNESS_VALUES)}, got {freshness!r}")
    independence = ev.get("independence")
    if independence not in INDEPENDENCE_VALUES:
        rep.error(f"{ctx}: evidence.independence must be one of {sorted(INDEPENDENCE_VALUES)}, got {independence!r}")
    methods = ev.get("methods")
    if methods is not None and not (isinstance(methods, list) and all(_nonempty(m) for m in methods)):
        rep.error(f"{ctx}: evidence.methods, if present, must be a list of nonempty strings")
    # §3.7: three core floor fields; B20's required-build-inputs guard is opt-in at the format.
    # All three default to False when absent — the same "undocumented default is the defect"
    # discipline as weighted_required/control_required/recipe_required (§3.1 rule 5).
    if "build_inputs_required" in ev and not isinstance(ev["build_inputs_required"], bool):
        rep.error(f"{ctx}: evidence.build_inputs_required, if present, must be a bool (§3.7)")
    if "tool_qualification_required" in ev and not isinstance(ev["tool_qualification_required"], bool):
        rep.error(f"{ctx}: evidence.tool_qualification_required, if present, must be a bool (§3.7)")
    coverage_min = ev.get("coverage_min")
    if coverage_min is not None:
        if not isinstance(coverage_min, dict):
            rep.error(f"{ctx}: evidence.coverage_min, if present, must be a table {{metric, value}} (§3.7)")
        else:
            metric = coverage_min.get("metric")
            if metric not in COVERAGE_METRICS:
                rep.error(
                    f"{ctx}: evidence.coverage_min.metric must be one of {sorted(COVERAGE_METRICS)} "
                    f"(the format's B21 registry), got {metric!r} (§3.7)"
                )
            value = coverage_min.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not (0 <= value <= 1):
                rep.error(
                    f"{ctx}: evidence.coverage_min.value must be a number in [0, 1], got {value!r} (§3.7)"
                )
            extra = set(coverage_min) - {"metric", "value"}
            if extra:
                rep.error(f"{ctx}: evidence.coverage_min carries unknown field(s) {sorted(extra)} (§3.7)")
    # Finding 14 (§3.1 rule 1, §3.5): `[requirement.evidence.recipe]` — the consumer NAMES the
    # check it will re-run; part of the floor set (§3.5), so it is validated here like every
    # other floor field.
    recipe = ev.get("recipe")
    if recipe is not None:
        if not isinstance(recipe, dict) or not _nonempty(recipe.get("command")) or not _nonempty(recipe.get("expect")):
            rep.error(
                f"{ctx}: evidence.recipe, if present, must be a table with nonempty 'command' "
                f"and 'expect' strings (Finding 14)"
            )
        elif "control_patch" in recipe and not _nonempty(recipe.get("control_patch")):
            rep.error(f"{ctx}: evidence.recipe.control_patch, if present, must be a nonempty string (Finding 14)")
    prof = ev.get("profile")
    if prof is not None:
        # P11: the core validates SHAPE only; CONTENT is delegated to the profile's own
        # floor-schema validator (Finding 10, §6.6 item 2, §3.3) — a profile id with no binding
        # available is an ERROR, never a silently-ignored floor.
        if not isinstance(prof, dict) or not all(isinstance(v, dict) for v in prof.values()):
            rep.error(
                f"{ctx}: evidence.profile must be a table of profile-id -> table "
                f"(content validated by the profile binding, not the core — §3.1 rule 5)"
            )
        else:
            for pid, floor_table in prof.items():
                binding = PROFILES.get(pid)
                if binding is None or "validate_floor" not in binding:
                    rep.error(
                        f"{ctx}: profile floor declared for {pid!r} but the tool has no "
                        f"floor-schema validator binding for it — an unavailable binding is an "
                        f"error, never a silently-ignored floor (§3.3, §6.6 item 2, Finding 10)"
                    )
                    continue
                for err in binding["validate_floor"](floor_table):
                    rep.error(f"{ctx}: profile {pid!r} floor: {err} (Finding 10)")


def check_contract_tightening(new_contract: dict, old_contract: dict) -> Reporter:
    """protocol.md §3.5, checked by `check-contract --previous OLD.toml`. For every requirement id
    present in both versions: no floor may weaken unless the successor's requirement carries a
    full [requirement.relaxed] (WARNed, never silently accepted); every dropped id must be listed
    in [document].dropped; phase may not move backwards without [document].reopened."""
    rep = Reporter("tightening")

    old_doc = old_contract.get("document") or {}
    new_doc = new_contract.get("document") or {}
    if new_doc.get("supersedes") != old_doc.get("id"):
        rep.error(
            f"--previous: the new contract's [document].supersedes ({new_doc.get('supersedes')!r}) "
            f"must equal the previous contract's [document].id ({old_doc.get('id')!r})"
        )

    # Q1 (BLOCKER, §3.5 "Projection pinning"): [subject].profile is INVARIANT across a
    # supersedes chain — a differing successor is a hard error, excusable by nothing (relaxed is
    # per-requirement, reopened is phase only; neither touches the projection). A different
    # projection is a NEW contract (new id, no supersedes), never a tightening step.
    old_subject = old_contract.get("subject") or {}
    new_subject = new_contract.get("subject") or {}
    old_profile = old_subject.get("profile")
    new_profile = new_subject.get("profile")
    if old_profile != new_profile:
        rep.error(
            f"--previous: [subject].profile changed across the supersedes chain "
            f"({old_profile!r} -> {new_profile!r}) — the projection is INVARIANT across a chain; "
            f"a different projection is a NEW contract (new id, no supersedes), never a "
            f"tightening step (§3.5 Projection pinning)"
        )

    # Q1: [acceptance].profiles_required may only GAIN entries across the chain, never lose them.
    old_profiles_required = set((old_contract.get("acceptance") or {}).get("profiles_required") or [])
    new_profiles_required = set((new_contract.get("acceptance") or {}).get("profiles_required") or [])
    removed_profiles = old_profiles_required - new_profiles_required
    if removed_profiles:
        rep.error(
            f"--previous: [acceptance].profiles_required dropped {sorted(removed_profiles)} — "
            f"profiles_required may only GAIN entries across a supersedes chain, a removed entry "
            f"is a hard error (§3.5 Projection pinning)"
        )

    old_phase = (old_contract.get("acceptance") or {}).get("phase") or "final"
    new_phase = (new_contract.get("acceptance") or {}).get("phase") or "final"
    if PHASE_ORDER.get(new_phase, 2) < PHASE_ORDER.get(old_phase, 2):
        reopened = new_doc.get("reopened")
        if not (isinstance(reopened, dict) and all(_nonempty(reopened.get(k)) for k in ("reason", "by"))):
            rep.error(
                f"--previous: phase moved backwards ({old_phase!r} -> {new_phase!r}) without a "
                f"full [document].reopened {{reason, by}} (§3.5)"
            )

    # Finding 12 (§3.5, P5, "one authority identity"): `relaxed.by` is compared against the
    # contract's [acceptance].authority — the SAME identity that accepts amendments and issues
    # decisions — never `parties.consumer.name` as a separate rule (that mismatch made an
    # authorized relax fail whenever the authority and the consumer party name differ).
    authority_name = (new_contract.get("acceptance") or {}).get("authority")

    old_by_id = requirement_by_id(old_contract)
    new_by_id = requirement_by_id(new_contract)

    dropped_ids = {
        d.get("id") for d in (new_doc.get("dropped") or []) if isinstance(d, dict) and _nonempty(d.get("id"))
    }
    for rid in sorted(set(old_by_id) - set(new_by_id)):
        if rid not in dropped_ids:
            rep.error(
                f"requirement {rid!r} is absent from the successor and not listed in "
                f"[document].dropped (§3.5)"
            )

    # Finding 13 — §3.1 rule 1: retired_ids = predecessor's retired_ids UNION this version's
    # dropped ids; ids may never be reused across the WHOLE supersedes chain, not merely against
    # the immediate predecessor.
    old_retired = set(old_doc.get("retired_ids") or [])
    new_retired = set(new_doc.get("retired_ids") or [])
    expected_retired = old_retired | dropped_ids
    if new_retired != expected_retired:
        rep.error(
            f"[document].retired_ids ({sorted(new_retired)}) must equal the predecessor's "
            f"retired_ids UNION this version's dropped ids ({sorted(expected_retired)}) "
            f"(§3.1 rule 1, Finding 13)"
        )
    reused = set(new_by_id) & old_retired
    if reused:
        rep.error(
            f"requirement id(s) {sorted(reused)} were retired by a predecessor and must never "
            f"be reused across the supersedes chain (§3.1 rule 1, Finding 13)"
        )

    # Finding 13: a NEW requirement carrying `replaces = <old id>` requires that old id to be
    # among THIS version's dropped ids (the semantic-replacement linkage); `replaces` on a
    # requirement that ALSO existed under the same id in the predecessor is a misuse — replaces
    # is only for a genuinely new id.
    for rid, req in new_by_id.items():
        replaces = req.get("replaces")
        if _nonempty(replaces):
            if rid in old_by_id:
                rep.error(
                    f"requirement {rid!r} carries 'replaces' but that id already existed in the "
                    f"predecessor — 'replaces' names the OLD id from a NEW id, it does not "
                    f"belong on a carried-over requirement (§3.1 rule 1, Finding 13)"
                )
            elif replaces not in dropped_ids:
                rep.error(
                    f"requirement {rid!r} carries replaces={replaces!r} but {replaces!r} is not "
                    f"listed in this version's [document].dropped (§3.1 rule 1, Finding 13)"
                )

    for rid in sorted(set(old_by_id) & set(new_by_id)):
        old_req, new_req = old_by_id[rid], new_by_id[rid]
        relaxed = new_req.get("relaxed")
        has_relaxed = (
            isinstance(relaxed, dict) and all(_nonempty(relaxed.get(k)) for k in ("reason", "by"))
            and (authority_name is None or relaxed.get("by") == authority_name)
        )

        # Finding 13 / §3.1 rule 1: a SEMANTIC replacement (statement/kind/domain changed) under
        # the SAME id is a rule-1 violation regardless of `relaxed` — relaxed only excuses a
        # floor weakening, never an identity violation. `over` is covered by the shrink check
        # below (part of the floor set, §3.5), not here.
        for f in ("statement", "kind", "domain"):
            old_v = old_req.get(f, "item" if f == "kind" else None)
            new_v = new_req.get(f, "item" if f == "kind" else None)
            if old_v != new_v:
                rep.error(
                    f"requirement {rid!r}: {f!r} changed under the SAME id ({old_v!r} -> "
                    f"{new_v!r}) — a semantic replacement requires a NEW id carrying "
                    f"replaces={rid!r}, with {rid!r} listed in [document].dropped (§3.1 rule 1, "
                    f"Finding 13)"
                )

        # Finding 16 (§3.1 rule 1): an `over` that DROPS an id is itself a semantic replacement
        # — it requires a NEW id carrying `replaces`, exactly like statement/kind/domain above.
        # It is NOT a floor weakening `relaxed` can excuse under the SAME id (growing `over` is a
        # floor-only tightening, allowed freely; shrinking it under the same id is an identity
        # violation, not a relaxable weakening).
        old_over_ident = old_req.get("over")
        new_over_ident = new_req.get("over")
        if old_over_ident is not None and new_over_ident is not None:
            if old_over_ident == "all" and new_over_ident != "all":
                rep.error(
                    f"requirement {rid!r}: 'over' dropped id(s) under the SAME id (was 'all', "
                    f"now {new_over_ident!r}) — a semantic replacement requires a NEW id carrying "
                    f"replaces={rid!r}, with {rid!r} listed in [document].dropped (§3.1 rule 1, "
                    f"Finding 16)"
                )
            elif isinstance(old_over_ident, list) and new_over_ident != "all":
                new_over_set = set(new_over_ident) if isinstance(new_over_ident, list) else set()
                dropped_over_ids = set(old_over_ident) - new_over_set
                if dropped_over_ids:
                    rep.error(
                        f"requirement {rid!r}: 'over' dropped id(s) {sorted(dropped_over_ids)} "
                        f"under the SAME id — a semantic replacement requires a NEW id carrying "
                        f"replaces={rid!r}, with {rid!r} listed in [document].dropped (§3.1 rule "
                        f"1, Finding 16)"
                    )

        violations: list[str] = []
        if old_req.get("mandatory") is True and new_req.get("mandatory") is not True:
            violations.append("mandatory went true -> false")
        # Finding 5: waivable false -> true is also a weakening (a non-waivable floor becoming
        # waivable lets the consumer accept below it later).
        if old_req.get("waivable") is False and new_req.get("waivable") is True:
            violations.append("waivable went false -> true")

        old_ev = old_req.get("evidence") if isinstance(old_req.get("evidence"), dict) else None
        new_ev = new_req.get("evidence") if isinstance(new_req.get("evidence"), dict) else None
        if old_ev is not None and new_ev is not None:
            old_tier, new_tier = old_ev.get("min_tier"), new_ev.get("min_tier")
            if TIER_RANK.get(new_tier, -1) < TIER_RANK.get(old_tier, -1):
                violations.append(f"min_tier weakened ({old_tier!r} -> {new_tier!r})")
            for f in (
                "weighted_required", "control_required", "recipe_required",
                # §3.7: the two new boolean floors join the same weakening check.
                "build_inputs_required", "tool_qualification_required",
            ):
                old_v = old_ev.get(f, True) if f == "weighted_required" else old_ev.get(f)
                new_v = new_ev.get(f, True) if f == "weighted_required" else new_ev.get(f)
                if old_v is True and new_v is not True:
                    violations.append(f"{f} went true -> false")
            old_fresh, new_fresh = old_ev.get("freshness"), new_ev.get("freshness")
            if FRESHNESS_RANK.get(new_fresh, -1) < FRESHNESS_RANK.get(old_fresh, -1):
                violations.append(f"freshness weakened ({old_fresh!r} -> {new_fresh!r})")
            old_indep, new_indep = old_ev.get("independence"), new_ev.get("independence")
            if INDEPENDENCE_RANK.get(new_indep, -1) < INDEPENDENCE_RANK.get(old_indep, -1):
                violations.append(f"independence weakened ({old_indep!r} -> {new_indep!r})")

            # §3.7: `coverage_min` joins the floor set — REMOVING it, lowering its
            # `value`, or changing its `metric` (incomparable, so treated as a weakening — the
            # same "incomparable is an error" stance the profile-floor comparator takes, §3.5
            # item 7) are all weakenings unless relaxed.
            old_cov_min = old_ev.get("coverage_min") if isinstance(old_ev.get("coverage_min"), dict) else None
            new_cov_min = new_ev.get("coverage_min") if isinstance(new_ev.get("coverage_min"), dict) else None
            if old_cov_min is not None:
                if new_cov_min is None:
                    violations.append("evidence.coverage_min REMOVED")
                elif new_cov_min.get("metric") != old_cov_min.get("metric"):
                    violations.append(
                        f"evidence.coverage_min.metric changed "
                        f"({old_cov_min.get('metric')!r} -> {new_cov_min.get('metric')!r}, incomparable)"
                    )
                elif not isinstance(new_cov_min.get("value"), (int, float)) or new_cov_min.get("value") < old_cov_min.get("value"):
                    violations.append(
                        f"evidence.coverage_min.value weakened "
                        f"({old_cov_min.get('value')!r} -> {new_cov_min.get('value')!r})"
                    )

            # Finding 14 (§3.5, "part of the floor set"): `[requirement.evidence.recipe]` —
            # removing it, or changing its `command`, is a weakening unless relaxed.
            #
            # §3.5 puts the WHOLE `[requirement.evidence.
            # recipe]` table in the floor set, not just `command` — a successor that keeps the
            # same command but weakens `expect` (e.g. from an exact match to a substring that
            # passes more often) or drops `control_patch` (the observed-red control the recipe
            # was pinned to) slipped through here before this fix, even though either change lets
            # the SAME command re-validate a weaker claim.
            old_recipe = old_ev.get("recipe") if isinstance(old_ev.get("recipe"), dict) else None
            new_recipe = new_ev.get("recipe") if isinstance(new_ev.get("recipe"), dict) else None
            if old_recipe is not None:
                if new_recipe is None:
                    violations.append("evidence.recipe REMOVED")
                else:
                    if new_recipe.get("command") != old_recipe.get("command"):
                        violations.append(
                            f"evidence.recipe.command changed "
                            f"({old_recipe.get('command')!r} -> {new_recipe.get('command')!r})"
                        )
                    if new_recipe.get("expect") != old_recipe.get("expect"):
                        violations.append(
                            f"evidence.recipe.expect changed "
                            f"({old_recipe.get('expect')!r} -> {new_recipe.get('expect')!r})"
                        )
                    old_ctrl_patch = old_recipe.get("control_patch")
                    new_ctrl_patch = new_recipe.get("control_patch")
                    if _nonempty(old_ctrl_patch) and old_ctrl_patch != new_ctrl_patch:
                        if not _nonempty(new_ctrl_patch):
                            violations.append("evidence.recipe.control_patch REMOVED")
                        else:
                            violations.append(
                                f"evidence.recipe.control_patch changed "
                                f"({old_ctrl_patch!r} -> {new_ctrl_patch!r})"
                            )
            # §3.5 puts the WHOLE
                    # [requirement.evidence.recipe] table in the floor set, not just the three keys
                    # above — a weakening through a future key (env/cwd/timeout/…) would otherwise
                    # slip through silently. Catch any change outside the named keys.
                    _known_recipe_keys = {"command", "expect", "control_patch"}
                    _other_keys = (set(old_recipe) | set(new_recipe)) - _known_recipe_keys
                    if any(old_recipe.get(k) != new_recipe.get(k) for k in _other_keys):
                        violations.append(
                            "evidence.recipe changed in a field outside "
                            "command/expect/control_patch (the whole recipe table is in the §3.5 "
                            "floor set)"
                        )

            # Finding 5: `methods` — removing the restriction or loosening it (adding methods /
            # dropping it entirely = any method now qualifies = weaker) is a weakening.
            old_methods = set(old_ev.get("methods") or [])
            if old_methods:
                new_methods = set(new_ev.get("methods") or [])
                if not new_methods or not new_methods.issubset(old_methods):
                    violations.append(
                        f"methods restriction removed or loosened "
                        f"({sorted(old_methods)} -> {sorted(new_methods)})"
                    )

            # Finding 5: profile floor comparator dispatched by the ACTUAL profile id (never a
            # fixed default) — an unknown profile id is an ERROR, never a pass; REMOVING a
            # profile floor table entirely is itself a weakening (the floor stops being
            # evaluated at all).
            old_prof_tbl = old_ev.get("profile") if isinstance(old_ev.get("profile"), dict) else {}
            new_prof_tbl = new_ev.get("profile") if isinstance(new_ev.get("profile"), dict) else {}
            for pid, old_floor in old_prof_tbl.items():
                new_floor = new_prof_tbl.get(pid)
                pid_binding = PROFILES.get(pid)
                if pid_binding is None or "floor_not_weaker" not in pid_binding:
                    rep.error(
                        f"requirement {rid!r}: profile {pid!r} has no comparator available for "
                        f"the tightening check — incomparable is an ERROR, never a pass "
                        f"(§3.5 item 7, Finding 5)"
                    )
                    continue
                if new_floor is None:
                    violations.append(f"profile {pid!r} floor REMOVED")
                    continue
                if not pid_binding["floor_not_weaker"](old_floor, new_floor):
                    violations.append(f"profile {pid!r} floor weakened")

        # Finding 5: cross-cutting floor set — `demands`, `demands.fields`, `demands.fields_exact`.
        # Previously NEVER compared (the whole cross-cutting branch was missing), so a demands
        # weakening never even warned, let alone erred. `over` shrinking is checked ABOVE,
        # unconditionally (Finding 16: it is an identity violation, not a relaxable weakening);
        # `over` GROWING under the same id is a floor-only tightening and is never flagged here.
        old_demands = old_req.get("demands") if isinstance(old_req.get("demands"), dict) else None
        new_demands = new_req.get("demands") if isinstance(new_req.get("demands"), dict) else None
        if old_demands is not None and new_demands is not None:
            old_dm_tier = old_demands.get("min_tier")
            new_dm_tier = new_demands.get("min_tier")
            if old_dm_tier is not None:
                if new_dm_tier is None or TIER_RANK.get(new_dm_tier, -1) < TIER_RANK.get(old_dm_tier, -1):
                    violations.append(f"demands.min_tier weakened ({old_dm_tier!r} -> {new_dm_tier!r})")
            for f in ("weighted_required", "control_required"):
                if old_demands.get(f) is True and new_demands.get(f) is not True:
                    violations.append(f"demands.{f} went true -> false")

            old_fields = old_demands.get("fields") or {}
            new_fields = new_demands.get("fields") or {}
            for k, v in old_fields.items():
                if new_fields.get(k) != v:
                    violations.append(
                        f"demands.fields.{k!r} removed or changed ({v!r} -> {new_fields.get(k)!r})"
                    )
            old_fx = old_demands.get("fields_exact") or {}
            new_fx = new_demands.get("fields_exact") or {}
            for k, v in old_fx.items():
                if new_fx.get(k) != v:
                    violations.append(
                        f"demands.fields_exact.{k!r} removed or changed "
                        f"({v!r} -> {new_fx.get(k)!r})"
                    )

        if violations:
            if has_relaxed:
                rep.warn(
                    f"requirement {rid!r}: floor relaxed on purpose "
                    f"({'; '.join(violations)}) — reason: {relaxed.get('reason')!r}, "
                    f"by: {relaxed.get('by')!r} (§3.5, P12)"
                )
            else:
                rep.error(
                    f"requirement {rid!r}: floor weakened without [requirement.relaxed] "
                    f"({'; '.join(violations)}) (§3.5)"
                )

    return rep


def resolve_predecessor_chain(
    start_doc: dict, previous_paths: list | None, previous_dir: str | None,
) -> tuple[list[tuple[dict, Path]], list[str]]:
    """§3.3: "the chain is validated to its root" — resolves `start_doc`'s FULL `supersedes`
    chain, nearest-predecessor-first, back to a contract carrying no `supersedes`. The caller
    supplies the chain either as `--previous OLD1 --previous OLD2 …` (newest first — consumed in
    that order as each successive ancestor is needed) and/or `--previous-dir DIR` (each ancestor
    resolved by its own `[document].id`, used once the explicit list is exhausted). An unavailable
    ancestor is an ERROR, not a skipped link; a cycle (an id repeating in the chain) is an ERROR.
    Returns (chain, errors); resolution stops at the first failure (nothing past a broken link can
    be trusted)."""
    chain: list[tuple[dict, Path]] = []
    errors: list[str] = []

    dir_index: dict[str, Path] = {}
    if previous_dir:
        d = Path(previous_dir)
        if not d.is_dir():
            errors.append(f"--previous-dir {previous_dir!r} is not a directory")
        else:
            for f in sorted(d.glob("*.toml")):
                anc_doc, anc_err = load_toml(f)
                if anc_err or not isinstance(anc_doc, dict):
                    continue
                anc_id = (anc_doc.get("document") or {}).get("id")
                if _nonempty(anc_id) and anc_id not in dir_index:
                    dir_index[anc_id] = f

    explicit_paths = [Path(p) for p in (previous_paths or [])]
    explicit_idx = 0

    seen_ids: set[str] = set()
    start_id = (start_doc.get("document") or {}).get("id")
    if _nonempty(start_id):
        seen_ids.add(start_id)

    cur_doc = start_doc
    while True:
        supersedes = (cur_doc.get("document") or {}).get("supersedes")
        if not _nonempty(supersedes):
            break
        if supersedes in seen_ids:
            errors.append(f"predecessor chain cycle detected at id {supersedes!r} (§3.3)")
            break

        anc_path = None
        if explicit_idx < len(explicit_paths):
            anc_path = explicit_paths[explicit_idx]
            explicit_idx += 1
        elif supersedes in dir_index:
            anc_path = dir_index[supersedes]

        if anc_path is None:
            errors.append(
                f"predecessor {supersedes!r} is unavailable — supply it via --previous or "
                f"--previous-dir (§3.3: an unavailable ancestor is an error, not a skipped link)"
            )
            break

        anc_doc, anc_err = load_toml(anc_path)
        if anc_err or not isinstance(anc_doc, dict):
            errors.append(f"predecessor {supersedes!r} at {anc_path}: {anc_err or 'not a table'}")
            break
        anc_id = (anc_doc.get("document") or {}).get("id")
        if anc_id != supersedes:
            errors.append(
                f"predecessor at {anc_path} has [document].id {anc_id!r}, expected {supersedes!r} "
                f"(the chain names {supersedes!r})"
            )
            break

        chain.append((anc_doc, anc_path))
        seen_ids.add(anc_id)
        cur_doc = anc_doc

    return chain, errors


def check_contract_chain(
    doc: dict, previous_paths: list | None, previous_dir: str | None,
) -> Reporter:
    """§3.3 "the chain is validated to its root": resolves the full predecessor chain
    (`resolve_predecessor_chain`) and, for every link, validates the PREDECESSOR's own structural
    validity (`check_contract` — Finding 4: "a predecessor with an empty parties.consumer.name
    must fail its own check-contract") AND the tightening step between it and its successor
    (`check_contract_tightening`, which itself recomputes `retired_ids` as the union along the
    chain rather than trusting the file). Running this pairwise all the way to the root, rather
    than only the single nearest predecessor, is what makes `retired_ids` a recomputed proof
    instead of a trusted field."""
    rep = Reporter("chain")
    chain, chain_errors = resolve_predecessor_chain(doc, previous_paths, previous_dir)
    for e in chain_errors:
        rep.error(e)

    cur = doc
    for anc_doc, anc_path in chain:
        struct_rep = check_contract(anc_doc)
        rep.merge(struct_rep, prefix=f"[predecessor {anc_path}] ")
        rep.merge(check_contract_tightening(cur, anc_doc), prefix=f"[tightening vs {anc_path}] ")
        cur = anc_doc

    return rep


# ---------------------------------------------------------------------------------------------
# The amendment document — protocol.md §3.6
# ---------------------------------------------------------------------------------------------

def check_amendment(amendment: dict, base_contract: dict, base_contract_path: Path | None) -> Reporter:
    """`check-amendment AMEND.toml --contract BASE.toml` (§3.6)."""
    rep = Reporter("amendment")

    # The successor's phase is INHERITED from the
    # base contract — no `[[change]]` op touches `[acceptance].phase` (A5: it is requirement-scoped
    # by design), so the base's own phase IS the phase every `[change.proposed]` requirement will
    # be checked under once applied. A hardcoded "final" here made A4's new all-firm rule (§3.5)
    # unintentionally reject a `crystallizing` base's `draft` requirement in a `modify`/`tighten`
    # proposal, even though that SAME draft requirement is perfectly legal in the applied successor.
    successor_phase = (base_contract.get("acceptance") or {}).get("phase") or "final"
    if successor_phase not in PHASE_VALUES:
        successor_phase = "final"  # already reported as a shape error elsewhere; do not cascade here

    document = amendment.get("document")
    if not isinstance(document, dict):
        rep.error("[document] section missing")
        document = {}
    else:
        if document.get("protocol") != PROTOCOL_ID:
            rep.error(f"[document].protocol must be {PROTOCOL_ID!r}")
        if document.get("kind") != "amendment":
            rep.error(f"[document].kind must be 'amendment', got {document.get('kind')!r}")
        if not _nonempty(document.get("id")):
            rep.error("[document].id must be a nonempty string")
        if not _nonempty(document.get("issued_at")):
            rep.error("[document].issued_at must be a nonempty string")
        if document.get("issued_by") not in AMENDMENT_ISSUED_BY:
            rep.error(f"[document].issued_by must be one of {sorted(AMENDMENT_ISSUED_BY)}, got {document.get('issued_by')!r}")
        status = document.get("status")
        if status not in AMENDMENT_STATUSES:
            rep.error(f"[document].status must be one of {sorted(AMENDMENT_STATUSES)}, got {status!r}")
        if "from_decision" in document and not _nonempty(document.get("from_decision")):
            rep.error("[document].from_decision, if present, must be a nonempty string")

    binds = amendment.get("binds")
    bc = (binds or {}).get("contract") if isinstance(binds, dict) else None
    if not isinstance(bc, dict) or not _nonempty(bc.get("id")) or not _nonempty(bc.get("hash")):
        rep.error("[binds].contract = {id, hash} must be present (§3.6 rule 1)")
    else:
        _reject_bare_m11_wire(rep, bc.get("hash"), "contract", "[binds].contract.hash")
        base_id = (base_contract.get("document") or {}).get("id")
        base_mismatch = bc.get("id") != base_id
        if base_contract_path is not None:
            try:
                recomputed = m11.digest_file("contract", base_contract_path)
                if bc.get("hash") != recomputed:
                    base_mismatch = True
            except OSError as e:
                rep.error(f"could not recompute base contract hash: {e}")
        if base_mismatch:
            if document.get("status") != "stale":
                rep.error(
                    "[binds].contract does not match the presented BASE contract (base moved) — "
                    "[document].status must be 'stale' (§3.6 rule 1)"
                )

    for idx, fb in enumerate(amendment.get("feedback") or []):
        fctx = f"feedback[{idx}]"
        if not isinstance(fb, dict):
            rep.error(f"{fctx}: must be a table")
            continue
        if fb.get("kind") not in REQUIREMENT_FEEDBACK_KINDS:
            rep.error(f"{fctx}: kind must be one of {sorted(REQUIREMENT_FEEDBACK_KINDS)}, got {fb.get('kind')!r}")
        rid = fb.get("requirement")
        base_ids = set(requirement_by_id(base_contract))
        if fb.get("kind") != "missing" and rid not in base_ids:
            rep.error(f"{fctx}: requirement {rid!r} does not resolve to a base-contract requirement")
        if not _nonempty(fb.get("statement")):
            rep.error(f"{fctx}: statement must be a nonempty string")
        if not _nonempty(fb.get("proposed")):
            rep.error(f"{fctx}: proposed must be a nonempty string")

    base_ids = set(requirement_by_id(base_contract))
    added_ids: set[str] = set()
    for c in amendment.get("change") or []:
        if isinstance(c, dict) and c.get("op") == "add" and _nonempty(c.get("requirement")):
            added_ids.add(c["requirement"])

    for idx, c in enumerate(amendment.get("change") or []):
        cctx = f"change[{idx}]"
        if not isinstance(c, dict):
            rep.error(f"{cctx}: must be a table")
            continue
        op = c.get("op")
        if op not in CHANGE_OPS:
            rep.error(f"{cctx}: op must be one of {sorted(CHANGE_OPS)}, got {op!r}")
            continue
        rid = c.get("requirement")
        if not _nonempty(rid):
            rep.error(f"{cctx}: 'requirement' must be a nonempty string")
        elif op == "add":
            if rid in base_ids:
                rep.error(f"{cctx}: op='add' requirement id {rid!r} already exists in the base contract")
        else:
            if rid not in base_ids:
                rep.error(f"{cctx}: op={op!r} requirement id {rid!r} does not exist in the base contract")

        if op == "relax" and not _nonempty(c.get("reason")):
            rep.error(f"{cctx}: op='relax' requires a nonempty 'reason' (§3.6)")
        elif "reason" in c and not _nonempty(c.get("reason")):
            rep.error(f"{cctx}: 'reason', if present, must be a nonempty string")

        proposed = c.get("proposed")
        if op in ("add", "modify"):
            if not isinstance(proposed, dict):
                rep.error(f"{cctx}: op={op!r} requires [change.proposed] as a full [[requirement]] table")
            else:
                _check_requirement_fields(rep, f"{cctx}.proposed", proposed, base_ids | added_ids, successor_phase)
                # Finding 13 (§3.1 rule 1): "an amendment `modify` op may only change the floor
                # set" — statement/kind/over/domain are identity, not floor; changing any of them
                # via `modify` is a semantic replacement and must be an add+drop pair instead.
                if op == "modify" and _nonempty(rid):
                    base_req = requirement_by_id(base_contract).get(rid)
                    if base_req is not None:
                        for f in ("statement", "kind", "over", "domain"):
                            if f in proposed and proposed.get(f) != base_req.get(f, proposed.get(f)):
                                rep.error(
                                    f"{cctx}: op='modify' may not change {f!r} (only the floor "
                                    f"set — mandatory/waivable/evidence/demands) — a "
                                    f"{f!r} change is a semantic replacement: use add "
                                    f"(new id, replaces={rid!r}) + drop instead (§3.1 rule 1, "
                                    f"Finding 13)"
                                )
        elif op in ("tighten", "relax"):
            if not isinstance(proposed, dict):
                rep.error(f"{cctx}: op={op!r} requires [change.proposed] to carry the evidence-floor fields")
            else:
                _check_evidence_floor(rep, f"{cctx}.proposed", proposed)

    return rep


_TOML_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _toml_key(k: str) -> str:
    return k if _TOML_KEY_RE.match(k) else json.dumps(k)


def _toml_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_scalar(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{_toml_key(k)} = {_toml_scalar(vv)}" for k, vv in v.items()) + " }"
    raise TypeError(f"unsupported TOML scalar type: {type(v)}")


def _render_contract_toml(doc: dict) -> str:
    """A minimal, PURPOSE-BUILT serializer for the contract shape only (stdlib has no TOML
    writer). Used by `apply-amendment` to emit the successor contract. Every value it writes was
    validated by `_check_requirement_fields` / `check_contract` first."""
    lines: list[str] = []
    document = doc.get("document") or {}
    lines.append("[document]")
    for k in ("protocol", "minor", "kind", "id", "version", "issued_at", "issued_by", "status", "supersedes"):
        if k in document:
            lines.append(f"{k} = {_toml_scalar(document[k])}")
    for k in ("dropped", "reopened", "amendments", "retired_ids"):
        if document.get(k):
            lines.append(f"{k} = {_toml_scalar(document[k])}")
    lines.append("")

    parties = doc.get("parties") or {}
    lines.append("[parties]")
    lines.append(f"consumer = {_toml_scalar(parties.get('consumer') or {})}")
    lines.append(f"producer = {_toml_scalar(parties.get('producer') or {})}")
    # §3.4a party boundary was silently dropped by this
    # renderer — an amendment on a cross-org contract would erase its boundary declaration.
    if "boundary" in parties:
        lines.append(f"boundary = {_toml_scalar(parties['boundary'])}")
    lines.append("")
    if isinstance(parties.get("boundary_terms"), dict):
        lines.append("[parties.boundary_terms]")
        for k, v in parties["boundary_terms"].items():
            lines.append(f"{k} = {_toml_scalar(v)}")
        lines.append("")

    if isinstance(doc.get("ratification"), dict):
        lines.append("[ratification]")
        for k, v in doc["ratification"].items():
            lines.append(f"{k} = {_toml_scalar(v)}")
        lines.append("")

    subject = doc.get("subject") or {}
    lines.append("[subject]")
    for k in ("kind", "name", "description", "deliverables", "constraints", "profile"):
        if k in subject:
            lines.append(f"{k} = {_toml_scalar(subject[k])}")
    lines.append("")

    if isinstance(doc.get("policy"), dict):
        lines.append("[policy]")
        for k, v in doc["policy"].items():
            lines.append(f"{k} = {_toml_scalar(v)}")
        lines.append("")

    for req in doc.get("requirement") or []:
        lines.append("[[requirement]]")
        # `assurance_class` (the §3.7 per-requirement
        # override) was silently dropped by this renderer — an amendment on an unrelated
        # requirement would erase another requirement's class override.
        for k in ("id", "statement", "mandatory", "waivable", "domain", "clause_source",
                   "external_ref", "parent", "firmness", "kind", "over", "replaces",
                   "assurance_class"):
            if k in req:
                lines.append(f"{k} = {_toml_scalar(req[k])}")
        if isinstance(req.get("relaxed"), dict):
            lines.append("  [requirement.relaxed]")
            for k, v in req["relaxed"].items():
                lines.append(f"  {k} = {_toml_scalar(v)}")
        if isinstance(req.get("evidence"), dict):
            ev = req["evidence"]
            lines.append("  [requirement.evidence]")
            # `build_inputs_required` and `tool_qualification_required`
            # (the §3.7 class-floor evidence booleans) were silently dropped by this renderer.
            for k in ("min_tier", "weighted_required", "control_required", "recipe_required",
                       "freshness", "independence", "methods",
                       "build_inputs_required", "tool_qualification_required"):
                if k in ev:
                    lines.append(f"  {k} = {_toml_scalar(ev[k])}")
            # Finding 14: `[requirement.evidence.recipe]` — previously dropped by this renderer
            # (the amendment machinery keeps it in memory but the SERIALIZED successor never
            # wrote it out), erasing a consumer-selected recipe on an unrelated amendment.
            if isinstance(ev.get("recipe"), dict):
                lines.append("  [requirement.evidence.recipe]")
                for k in ("command", "expect", "control_patch"):
                    if k in ev["recipe"]:
                        lines.append(f"  {k} = {_toml_scalar(ev['recipe'][k])}")
            # `coverage_min` (the §3.7 structural/proof-coverage floor)
            # was silently dropped by this renderer.
            if isinstance(ev.get("coverage_min"), dict):
                lines.append("  [requirement.evidence.coverage_min]")
                for k, v in ev["coverage_min"].items():
                    lines.append(f"  {k} = {_toml_scalar(v)}")
            if isinstance(ev.get("profile"), dict):
                for pid, floor in ev["profile"].items():
                    lines.append(f"  [requirement.evidence.profile.{_toml_key(pid)}]")
                    for k, v in floor.items():
                        lines.append(f"  {k} = {_toml_scalar(v)}")
        if isinstance(req.get("demands"), dict):
            d = req["demands"]
            lines.append("  [requirement.demands]")
            for k in ("min_tier", "weighted_required", "control_required"):
                if k in d:
                    lines.append(f"  {k} = {_toml_scalar(d[k])}")
            if isinstance(d.get("fields"), dict):
                lines.append("  [requirement.demands.fields]")
                for k, v in d["fields"].items():
                    lines.append(f"  {k} = {_toml_scalar(v)}")
            if isinstance(d.get("fields_exact"), dict):
                lines.append("  [requirement.demands.fields_exact]")
                for k, v in d["fields_exact"].items():
                    lines.append(f"  {k} = {_toml_scalar(v)}")
        lines.append("")

    acceptance = doc.get("acceptance") or {}
    lines.append("[acceptance]")
    # `assurance_class` (the §3.7 contract-level
    # class) was silently dropped by this renderer — an amendment on any requirement would erase
    # the contract's own declared class; that change is a successor
    # contract's own decision, never an amendment side effect.
    for k in ("rule", "consumer_verification", "authority", "verifiers", "decision_threshold",
               "profiles_required", "stale_after", "phase", "assurance_class"):
        if k in acceptance:
            lines.append(f"{k} = {_toml_scalar(acceptance[k])}")
    lines.append("")

    if isinstance(doc.get("ext"), dict):
        lines.append("[ext]")
        for k, v in doc["ext"].items():
            lines.append(f"{k} = {_toml_scalar(v)}")

    return "\n".join(lines) + "\n"


def _render_amendment_toml(doc: dict) -> str:
    lines: list[str] = []
    document = doc.get("document") or {}
    lines.append("[document]")
    for k in ("protocol", "minor", "kind", "id", "issued_at", "issued_by", "status", "from_decision"):
        if k in document:
            lines.append(f"{k} = {_toml_scalar(document[k])}")
    lines.append("")
    lines.append("[binds]")
    lines.append(f"contract = {_toml_scalar((doc.get('binds') or {}).get('contract') or {})}")
    lines.append("")
    for fb in doc.get("feedback") or []:
        lines.append("[[feedback]]")
        for k in ("requirement", "kind", "statement", "proposed"):
            if k in fb:
                lines.append(f"{k} = {_toml_scalar(fb[k])}")
        lines.append("")
    for c in doc.get("change") or []:
        lines.append("[[change]]")
        for k in ("op", "requirement", "reason"):
            if k in c:
                lines.append(f"{k} = {_toml_scalar(c[k])}")
        if isinstance(c.get("proposed"), dict):
            lines.append("  [change.proposed]")
            for k, v in c["proposed"].items():
                if k == "evidence" and isinstance(v, dict):
                    continue  # add/modify's nested [requirement.evidence] — rare in a stub; keep flat here
                lines.append(f"  {k} = {_toml_scalar(v)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def apply_amendment_build(
    amendment: dict, base_contract: dict, new_id: str | None, authority_name: str | None,
) -> tuple[dict | None, list[str]]:
    """Builds the successor contract dict (§3.6 rule 2). Returns (new_contract, errors).

    Finding 11: `relaxed`/`reopened`/`ratification`/`amendments` are stripped from the COPIED
    base — NEVER inherited (§3.5): an old relaxation must not excuse a later, different
    weakening. Only THIS amendment's `relax` ops re-add a FRESH `[requirement.relaxed]` on their
    own target. `authority_name` (renamed from `consumer_name`) is the contract's
    `[acceptance].authority` — §3.6 rule 2 names the AUTHORITY as who accepts, not the consumer
    party name."""
    import copy
    errors: list[str] = []
    new_contract = copy.deepcopy(base_contract)
    base_doc = base_contract.get("document") or {}
    base_id = base_doc.get("id")

    document = new_contract.setdefault("document", {})
    new_version = (base_doc.get("version") or 1) + 1
    document["version"] = new_version
    document["id"] = new_id or f"{base_id}-v{new_version}"
    document["supersedes"] = base_id
    document["amendments"] = [(amendment.get("document") or {}).get("id")]
    document["status"] = "issued"
    # Finding 12 (§3.6 rule 2): "the successor is always authority-issued: issued_by='consumer',
    # status='issued', no [ratification] table — whatever the base's issued_by was, because the
    # authority's application IS the buyer's word." Previously this inherited the BASE's
    # issued_by, so a producer-ratified base produced a producer-issued, non-binding successor.
    document["issued_by"] = "consumer"
    document["issued_at"] = now_utc_iso()
    # Finding 12: `[ratification]` is a TOP-LEVEL table (`doc["ratification"]`), not
    # `document["ratification"]` — popping the wrong key left the real table in place on a
    # producer-ratified base's successor.
    new_contract.pop("ratification", None)
    document.pop("reopened", None)  # Finding 11: never inherited (§3.5)

    reqs = new_contract.get("requirement") or []
    for r in reqs:
        if isinstance(r, dict):
            r.pop("relaxed", None)  # Finding 11: never inherited — only a fresh relax op re-adds it
            # Finding 13 (§3.1 rule 1): `replaces` is transition-local — stripped when a successor
            # is derived, like `relaxed`. A freshly-added requirement (op='add') re-adds its own
            # `replaces` below, after this strip, from `[change.proposed]`.
            r.pop("replaces", None)
    by_id = {r.get("id"): r for r in reqs if isinstance(r, dict)}
    dropped: list[dict] = []

    for c in amendment.get("change") or []:
        if not isinstance(c, dict):
            continue
        op = c.get("op")
        rid = c.get("requirement")
        proposed = c.get("proposed") or {}
        if op == "add":
            new_req = dict(proposed)
            new_req.setdefault("id", rid)
            reqs.append(new_req)
            by_id[new_req.get("id")] = new_req
        elif op == "modify":
            if rid in by_id:
                idx = reqs.index(by_id[rid])
                new_req = dict(proposed)
                new_req.setdefault("id", rid)
                reqs[idx] = new_req
                by_id[rid] = new_req
            else:
                errors.append(f"modify: requirement {rid!r} not found in base contract")
        elif op == "drop":
            if rid in by_id:
                reqs.remove(by_id[rid])
                del by_id[rid]
                dropped.append({"id": rid, "reason": c.get("reason") or ""})
            else:
                errors.append(f"drop: requirement {rid!r} not found in base contract")
        elif op in ("tighten", "relax"):
            target = by_id.get(rid)
            if target is None:
                errors.append(f"{op}: requirement {rid!r} not found in base contract")
                continue
            ev = dict(target.get("evidence") or {})
            ev.update(proposed)
            target["evidence"] = ev
            if op == "relax":
                target["relaxed"] = {"reason": c.get("reason") or "", "by": authority_name or ""}

    new_contract["requirement"] = reqs
    if dropped:
        document["dropped"] = dropped

    # Finding 13: retired_ids = predecessor's retired_ids UNION this version's dropped ids —
    # keeps `apply-amendment`'s own output consistent with what `check_contract_tightening` now
    # requires.
    dropped_ids = {d["id"] for d in dropped if _nonempty(d.get("id"))}
    old_retired = set(base_doc.get("retired_ids") or [])
    new_retired = old_retired | dropped_ids
    if new_retired:
        document["retired_ids"] = sorted(new_retired)

    return new_contract, errors


def build_amendment_from_decision(decision: dict, contract: dict, contract_path: Path) -> dict:
    """`amend --from-decision AD.toml` (§3.6 rule 4): materialises a decision's
    `[[requirement_feedback]]` as a proposed amendment. `missing` feedback becomes an `add` op
    with a STUB proposed requirement the consumer must edit; every other kind becomes feedback
    only, with no [[change]] op (the consumer decides how to fold it in)."""
    decision_id = (decision.get("document") or {}).get("id")
    doc = {
        "document": {
            "protocol": PROTOCOL_ID,
            "minor": 0,
            "kind": "amendment",
            "id": f"AM-{today_utc_date()}-draft",
            "issued_at": now_utc_iso(),
            "issued_by": "consumer",
            "status": "proposed",
            "from_decision": decision_id,
        },
        "binds": {
            "contract": {
                "id": (contract.get("document") or {}).get("id"),
                "hash": m11.digest_file("contract", contract_path),
            },
        },
        "feedback": [],
        "change": [],
    }
    for idx, fb in enumerate(decision.get("requirement_feedback") or []):
        if not isinstance(fb, dict):
            continue
        doc["feedback"].append({
            "requirement": fb.get("requirement"),
            "kind": fb.get("kind"),
            "statement": fb.get("statement"),
            "proposed": fb.get("proposed"),
        })
        if fb.get("kind") == "missing":
            stub_id = fb.get("requirement") or f"R-NEW-{idx}"
            doc["change"].append({
                "op": "add",
                "requirement": stub_id,
                "reason": f"from decision {decision_id} feedback: {fb.get('statement')}",
                "proposed": {
                    "id": stub_id,
                    "statement": fb.get("proposed") or "EDIT ME",
                    "mandatory": False,
                    "waivable": True,
                    "domain": "other",
                    "clause_source": "consumer-statement",
                    "evidence": {
                        "min_tier": "T5",
                        "weighted_required": False,
                        "control_required": False,
                        "recipe_required": False,
                        "freshness": "any",
                        "independence": "none",
                    },
                },
            })
    return doc


# ---------------------------------------------------------------------------------------------
# check-package — protocol.md §4.1, run after the bound profile's package validator (check_core)
# ---------------------------------------------------------------------------------------------

def check_package(
    package: dict, contract: dict, package_path: Path, contract_path: Path, strict: bool,
    previous_contract_path: Path | None = None,
    previous_paths: list | None = None,
    previous_dir: str | None = None,
) -> tuple[Reporter, dict]:
    """Returns (Reporter, coverage_result). Coverage is ALWAYS computed and returned, even when
    structural rules fail, so the caller can always print the coverage table (§4.1 closing line).

    Finding 17: the package validator is reached ONLY through the profile binding
    (`PROFILES[profile_id]["package_validator"]`), never by calling `check_acceptance.py`
    directly by name — a profile with no validator of its own cannot be evaluated (§6.6 item 8).
    Finding 4 (last sentence): "check-package runs check-contract on the bound contract" — the
    contract's own STRUCTURAL validity is no longer assumed, it is re-proven here, and the WHOLE
    predecessor chain is validated to its root (§3.3), not merely the nearest predecessor.
    `previous_contract_path` (singular, back-compat) is treated as the first `--previous` entry
    when `previous_paths` is not itself given."""
    rep = Reporter(str(package_path))

    profile_id = package_profile_id(package)
    profile = PROFILES.get(profile_id) if profile_id is not None else None
    if profile_id is None:
        rep.error(
            "B12: [format].profile is REQUIRED (no compatibility default) — the package declares "
            "none, so no package_validator can be selected (§6.6 item 8, fail-closed)"
        )
        ca_rep = None
    elif profile is None or "package_validator" not in profile:
        rep.error(
            f"package declares profile {profile_id!r}, which has no package_validator binding "
            f"in profiles.py — a profile with no validator of its own cannot be evaluated "
            f"(§6.6 item 8, fail-closed)"
        )
        ca_rep = None
    else:
        ca_rep = _run_package_validator(profile["package_validator"], package_path, strict)
        rep.merge(ca_rep, prefix="[package validator] ")
        constraints_check = profile.get("package_constraints")
        if constraints_check is not None:
            for msg in constraints_check(package):
                rep.warn(f"{msg} (§6.6 item 6 — a package-level profile constraint; check-decision ENFORCES this as an error)")

    # Finding 4: the bound contract is itself re-validated here, not merely trusted because a
    # producer's package.contract.hash happens to recompute over it.
    contract_struct_rep = check_contract(contract)
    rep.merge(contract_struct_rep, prefix="[check-contract] ")
    supersedes = (contract.get("document") or {}).get("supersedes")
    if supersedes:
        effective_previous_paths = list(previous_paths) if previous_paths else []
        if previous_contract_path is not None:
            effective_previous_paths = [str(previous_contract_path)] + effective_previous_paths
        if not effective_previous_paths and not previous_dir:
            rep.error(
                f"the bound contract supersedes {supersedes!r} but no --previous/--previous-dir "
                f"was given to validate the chain to its root (§3.3, §3.5, §5.0, Finding 4)"
            )
        else:
            rep.merge(
                check_contract_chain(contract, effective_previous_paths, previous_dir),
                prefix="[check-contract --previous chain] ",
            )

    req_by_id = requirement_by_id(contract)

    # rule 1: [contract] present; hash recomputes; requirements_total matches.
    pkg_contract = package.get("contract")
    if not isinstance(pkg_contract, dict):
        rep.error("[contract] section missing from the package (absent = producer-only manifest, §4)")
        pkg_contract = {}
    else:
        if pkg_contract.get("id") != (contract.get("document") or {}).get("id"):
            rep.error(
                f"[contract].id ({pkg_contract.get('id')!r}) does not match the presented "
                f"contract's [document].id ({(contract.get('document') or {}).get('id')!r})"
            )
        _reject_bare_m11_wire(rep, pkg_contract.get("hash"), "contract", "[contract].hash")
        try:
            recomputed = m11.digest_file("contract", contract_path)
        except (OSError, ValueError) as e:
            rep.error(f"could not recompute contract hash: {e}")
            recomputed = None
        if recomputed is not None and pkg_contract.get("hash") != recomputed:
            rep.error(
                f"[contract].hash does not match M11('contract:', <presented contract file>) "
                f"— got {pkg_contract.get('hash')!r}, recomputed {recomputed!r} (§4.1 rule 1, P7)"
            )
        n_reqs = len(req_by_id)
        if pkg_contract.get("requirements_total") != n_reqs:
            rep.error(
                f"[contract].requirements_total ({pkg_contract.get('requirements_total')!r}) "
                f"does not equal the contract's requirement count ({n_reqs}) (§4.1 rule 1)"
            )
        cov_tbl = package.get("coverage") or {}
        if cov_tbl.get("clauses_total") != pkg_contract.get("requirements_total"):
            rep.error(
                f"[coverage].clauses_total ({cov_tbl.get('clauses_total')!r}) does not equal "
                f"[contract].requirements_total ({pkg_contract.get('requirements_total')!r}) "
                f"(§4.1 rule 1)"
            )

    # rule 4 — Finding 7: binding = (issued AND issued_by == consumer) OR ratified. A
    # producer-drafted contract that is merely `issued` (not `ratified`) is a PROPOSAL (§3.2);
    # binding on status alone (ignoring issued_by) let an unratified producer-drafted contract
    # through.
    contract_status = (contract.get("document") or {}).get("status")
    contract_issued_by = (contract.get("document") or {}).get("issued_by")
    is_binding = (
        (contract_status == "issued" and contract_issued_by == "consumer")
        or contract_status == "ratified"
    )
    if not is_binding:
        rep.error(
            f"the bound contract is not BINDING (§3.2): status={contract_status!r}, "
            f"issued_by={contract_issued_by!r} — a producer-drafted contract binds only once "
            f"ratified; a package may bind only to a BINDING contract (§4.1 rule 4, Finding 7)"
        )

    claims = package.get("claim")
    claims = [c for c in claims if isinstance(c, dict)] if isinstance(claims, list) else []

    # rule 2: every claim.clause resolves; every ITEM requirement has >= 1 claim.
    for idx, c in enumerate(claims):
        clause = c.get("clause")
        if clause is not None and clause not in req_by_id:
            rep.error(
                f"claim {c.get('id') or idx!r}: clause {clause!r} is not a requirement id of "
                f"the bound contract (§4.1 rule 2)"
            )
    for rid, req in sorted(req_by_id.items()):
        if req.get("kind", "item") == "cross-cutting":
            continue
        if not any(c.get("clause") == rid for c in claims):
            rep.error(f"requirement {rid!r}: no [[claim]] names it (omission is forbidden, §4.1 rule 2)")

    # `[[claim.evidence.inputs]].digest` (§4/§8) is a
    # PROTOCOL field the format core never validates (it has no B-rule of its own). One wire form
    # (§7): the self-describing `subject:sha-512:<hex>` — the SAME domain the field's own spec
    # comment already names — never the retired bare `sha-512:<hex>`.
    for c in claims:
        cid = c.get("id")
        for eidx, e in enumerate(evidence_list(c)):
            for iidx, i in enumerate(e.get("inputs") or []):
                if not isinstance(i, dict):
                    continue
                ictx = f"claim {cid!r} evidence[{eidx}].inputs[{iidx}]"
                _reject_bare_m11_wire(rep, i.get("digest"), "subject", f"{ictx}.digest")

    # coverage — always computed.
    cov = compute_coverage(contract, package, package_path)
    for e in cov["record_errors"]:
        rep.error(e)

    # rule 3: every mandatory requirement not computed 'satisfied' needs a [[deviation]].
    deviations = package.get("deviation")
    deviations = [d for d in deviations if isinstance(d, dict)] if isinstance(deviations, list) else []
    dev_by_req: dict[str, list[dict]] = {}
    for d in deviations:
        dev_by_req.setdefault(d.get("requirement"), []).append(d)

    for idx, d in enumerate(deviations):
        dctx = f"deviation[{idx}] (requirement {d.get('requirement')!r})"
        req_id = d.get("requirement")
        if req_id not in req_by_id:
            rep.error(f"{dctx}: 'requirement' does not resolve to a contract requirement id")
        kind = d.get("kind")
        if kind not in DEVIATION_KINDS:
            rep.error(f"{dctx}: kind must be one of {sorted(DEVIATION_KINDS)}, got {kind!r}")
        for f in ("statement", "cause", "impact", "remedy"):
            if not _nonempty(d.get(f)):
                rep.error(f"{dctx}: field {f!r} must be a nonempty string")

    for rid, req in sorted(req_by_id.items()):
        if not req.get("mandatory") or rep.unknowns:
            continue  # unresolved format validation cannot establish a missing deviation
        status = cov["requirements"].get(rid, {}).get("status")
        if status != "satisfied" and rid not in dev_by_req:
            rep.error(
                f"requirement {rid!r} is mandatory and coverage computed {status!r} (not "
                f"'satisfied'), but no [[deviation]] names it (§4.1 rule 3, P6)"
            )

    # rule 5: subject identity present (structural — check_acceptance/check_core already validate
    # the exact shape of whichever B1 certified identity kind is present — git-revision,
    # content-digest or components, "protocol identity = format identity");
    # captured_at_revision/alias freshness is evaluated inside compute_coverage and remains
    # git-revision-scoped only (§6.2 cond 7, §6.6 item 4, protocol.md §7).
    if check_core.subject_identity_kind(package.get("subject") or {}) is None:
        rep.error(
            "[subject] must carry exactly one certified identity — commit (git-revision), digest "
            "(content-digest) or components (B1) — for a package to bind to a contract "
            "(§4.1 rule 5)"
        )

    # rule 6: every profile in profiles_required appears, AND the package's OWN profile (Finding
    # 2/17) is itself one the contract requires — "a package under a different profile is
    # invalid, it is not evaluated under a looser floor".
    profiles_required = (contract.get("acceptance") or {}).get("profiles_required") or []
    fmt = package.get("format") or {}
    fillers = package.get("filler")
    fillers = [f for f in fillers if isinstance(f, dict)] if isinstance(fillers, list) else []
    filler_profiles = {f.get("profile") for f in fillers}
    for p in profiles_required:
        if fmt.get("profile") != p and p not in filler_profiles:
            rep.error(
                f"required profile {p!r} appears neither as [format].profile nor as a "
                f"[[filler]].profile (§4.1 rule 6)"
            )
    own_profile = profile_id
    if profiles_required and own_profile not in profiles_required:
        own_desc = "no [format].profile declared" if own_profile is None else repr(own_profile)
        rep.error(
            f"the package's own profile ({own_desc}) is not one the contract requires "
            f"({profiles_required!r}) — a package under a different profile is invalid, it is "
            f"not evaluated under a looser floor (§4.1 rule 6, Finding 2)"
        )
    for idx, f in enumerate(fillers):
        if not _nonempty(f.get("profile")):
            rep.error(f"filler[{idx}]: 'profile' must be a nonempty string")
        if not _nonempty(f.get("party")):
            rep.error(f"filler[{idx}]: 'party' must be a nonempty string")
        if f.get("role") not in FILLER_ROLES:
            rep.error(f"filler[{idx}]: role must be one of {sorted(FILLER_ROLES)}, got {f.get('role')!r}")

    # rule 7 — Finding 7: producer identity set; producer = "open" REQUIRES >= 1 producer filler.
    contract_producer_name = ((contract.get("parties") or {}).get("producer") or {}).get("name")
    if contract_producer_name == "open":
        if not any(f.get("role") == "producer" for f in fillers):
            rep.error(
                "the contract's producer is 'open' but the package carries no [[filler]] with "
                "role='producer' naming who produced it (§4.1 rule 7)"
            )

    # §4 — [spec].upstream_status: OPTIONAL, non-normative, carried and displayed (§10),
    # NEVER gating — shape-checked only (a warning, never an error: it never blocks acceptance).
    upstream_status = (package.get("spec") or {}).get("upstream_status")
    if upstream_status is not None and not _nonempty(upstream_status):
        rep.warn(
            "[spec].upstream_status, if present, should be a nonempty string (S4, non-normative, never gating)"
        )

    return rep, cov


# ---------------------------------------------------------------------------------------------
# decide — emit a decision SKELETON consistent with coverage. Never emits a waiver or condition.
# ---------------------------------------------------------------------------------------------

def build_decision_skeleton(
    contract: dict, package: dict, package_path: Path, contract_path: Path,
    issuer: str, mode: str | None,
) -> str:
    cov = compute_coverage(contract, package, package_path)
    req_by_id = requirement_by_id(contract)

    contract_id = (contract.get("document") or {}).get("id")
    contract_hash = m11.digest_file("contract", contract_path)
    package_hash = m11.digest_file("manifest", package_path)
    # [binds].subject carries the SAME identity form the package declares — 'commit' for a
    # git-revision subject, 'digest' for content-digest or components (§7).
    subject_bind_field, subject_bind_value = _subject_binds_field(package.get("subject") or {})

    if mode is None:
        mode = (contract.get("acceptance") or {}).get("consumer_verification") or "spot-check"

    dev_by_req: dict[str, dict] = {}
    for d in package.get("deviation") or []:
        if isinstance(d, dict) and _nonempty(d.get("requirement")):
            dev_by_req.setdefault(d["requirement"], d)

    claims_by_id = {
        c.get("id"): c for c in (package.get("claim") or []) if isinstance(c, dict) and _nonempty(c.get("id"))
    }

    basis_claim_ids: set[str] = set()
    dispositions: list[dict] = []
    for rid in sorted(req_by_id):
        r = cov["requirements"].get(rid, {})
        status = r.get("status")
        mandatory = req_by_id[rid].get("mandatory", False)
        basis = r.get("basis") or []
        basis_claim_ids.update(basis)
        disp = {"requirement": rid, "basis": basis}
        if status == "satisfied":
            disp["status"] = "satisfied"
        elif mandatory:
            disp["status"] = "unsatisfied"
        else:
            disp["status"] = "insufficient-evidence"
        dev = dev_by_req.get(rid)
        if dev is not None:
            disp["note"] = f"deviation ({dev.get('kind')}): {dev.get('statement')}"
        dispositions.append(disp)

    mandatory_statuses = {d["status"] for d in dispositions
                           if req_by_id.get(d["requirement"], {}).get("mandatory")}
    verdict = expected_verdict_from_mandatory_statuses(mandatory_statuses)
    if verdict is None:
        verdict = "rejected"  # fail-closed: an undecidable combination is never auto-accepted

    lines: list[str] = []
    lines.append("[document]")
    lines.append(f'protocol   = "{PROTOCOL_ID}"')
    lines.append("minor      = 0")
    lines.append('kind       = "decision"')
    lines.append(f'id         = "AD-{today_utc_date()}-draft"')
    lines.append(f'issued_at  = "{now_utc_iso()}"')
    lines.append(f'issuer     = "{issuer}"')
    lines.append(f'verdict    = "{verdict}"')
    contract_phase = (contract.get("acceptance") or {}).get("phase") or "final"
    lines.append(f'provisional = {"true" if contract_phase != "final" else "false"}  # from contract phase {contract_phase!r} (§3.5)')
    if verdict == "rejected":
        n = sum(1 for s in mandatory_statuses if s not in ("satisfied",))
        lines.append(
            f'note       = "skeleton: {n} mandatory requirement status(es) not satisfied — '
            f'edit waivers/conditions and re-run check-decision"'
        )
    lines.append("")
    lines.append("[binds]")
    lines.append(f'contract = {{ id = "{contract_id}", hash = "{contract_hash}" }}')
    lines.append(f'package  = {{ hash = "{package_hash}" }}')
    lines.append(f'subject  = {{ {subject_bind_field or "commit"} = "{subject_bind_value}" }}')
    lines.append("")
    lines.append("[verification]")
    lines.append(f'mode = "{mode}"')
    lines.append("")
    for cid in sorted(basis_claim_ids):
        claim = claims_by_id.get(cid, {})
        command = ((claim.get("self_verify") or {}).get("command")) or ""
        lines.append("[[verification.run]]")
        lines.append(f'claim   = "{cid}"')
        lines.append(f'command = "{command}"')
        lines.append('result  = "not-run"')
        lines.append("")
    for disp in dispositions:
        lines.append("[[disposition]]")
        lines.append(f'requirement = "{disp["requirement"]}"')
        lines.append(f'status      = "{disp["status"]}"')
        lines.append(f'basis       = {json.dumps(disp["basis"])}')
        if "note" in disp:
            lines.append(f'note        = {json.dumps(disp["note"])}')
        lines.append("")
    lines.append("[validity]")
    stale_after_duration = (contract.get("acceptance") or {}).get("stale_after")
    if is_iso8601_duration(stale_after_duration):
        issued_dt = datetime.datetime.now(datetime.timezone.utc)
        stale_date = (issued_dt + duration_to_timedelta(stale_after_duration)).strftime("%Y-%m-%d")
        lines.append(f'stale_after = "{stale_date}"  # derived from the contract stale_after '
                      f'({stale_after_duration}); approximate — see README')
    return "\n".join(lines) + "\n"


def expected_verdict_from_mandatory_statuses(statuses: set[str]) -> str | None:
    """A CONDITION-AGNOSTIC heuristic used only by `decide`'s draft skeleton (the skeleton never
    knows conditions ahead of time). Finding 10: `check_decision` no longer calls this —
    it evaluates the states.toml `[[verdict_rule]]` rows directly (`evaluate_verdict_rules`),
    which also account for the {0, some} conditions dimension this function does not. §5.1 as a
    partition over MANDATORY-disposition statuses only (optional dispositions never change the
    verdict). Returns None when no row admits the combination (fail-closed)."""
    if not statuses:
        return "accepted"
    if "unsatisfied" in statuses:
        return "rejected"
    if "not-applicable" in statuses:
        return None
    if "insufficient-evidence" in statuses:
        return "evidence-requested"
    if statuses <= {"satisfied", "satisfied-with-conditions", "waived"}:
        if statuses == {"satisfied"}:
            return "accepted"
        return "accepted-with-conditions"
    return None


def _default_states_doc() -> dict:
    """The real `states.toml`, loaded fresh (no caching — this is a CLI tool, not a hot loop).
    Used whenever a caller does not inject an explicit set of `[[verdict_rule]]` rows."""
    doc, err = load_toml(_HERE.parent / "spec" / "states.toml", allow_semicolon=True)
    return doc if not err and isinstance(doc, dict) else {}


_VALID_VERDICT_CONDITIONS = {"none", "some", "any"}


class VerdictRuleError(ValueError):
    """Raised by `load_verdict_rules` on a malformed `[[verdict_rule]]` row — Finding 11: a
    tampered/typo'd `conditions` token must be caught wherever verdict rules are loaded (the live
    `check_decision` path included), not only under the `check-states` exhaustive proof."""


def load_verdict_rules(doc: dict) -> list[dict]:
    """The `[[verdict_rule]]` rows of `doc` (typically states.toml), well-formed tables only,
    ordered by their own `row` field. Finding 10: this is the ONLY place the §5.1 table's rows
    are read — `check_decision` and `check-states`'s exhaustive proof both evaluate exactly these
    rows, never a hand-written second copy.

    Finding 11: `conditions` (states.toml's own documented vocabulary, §5.1: "none" | "some" |
    "any", or absent meaning "any") is validated HERE, fail-closed. Before this fix an unknown
    token fell through `verdict_row_matches`'s `cond == "none"` / `cond == "some"` checks to the
    trailing "matches regardless" comment — a typo'd or tampered token silently behaved as
    'any', the least restrictive case, on the live `check_decision` path (the exhaustive proof in
    `check-states` never exercises a row this malformed). Raises `VerdictRuleError` rather than
    silently dropping or coercing the row: a caller on the decision path must surface this as an
    error, not eligibility computed over a truncated rule table.

    Notes: (1) non-dict rows are dropped and the result is stable-sorted
    by `row`, so callers that inject rows (`check_decision`, the selftest) get the same normalization
    states.toml gets — a benign behavior change worth stating. (2) This raises where it used not to;
    the only non-test callers are `check_decision` and `verify_verdict_table_exhaustive` (audited
    2026-09-16), both of which handle it — no third caller hits the raise uncaught."""
    rows = doc.get("verdict_rule")
    rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    for r in rows:
        cond = r.get("conditions")
        if cond is not None and cond not in _VALID_VERDICT_CONDITIONS:
            raise VerdictRuleError(
                f"[[verdict_rule]] row {r.get('row')!r}: conditions must be one of "
                f"{sorted(_VALID_VERDICT_CONDITIONS)} (or omitted, meaning 'any'), got {cond!r}"
            )
    return sorted(rows, key=lambda r: r.get("row", 0) if isinstance(r.get("row"), int) else 0)


def verdict_row_matches(row: dict, mandatory_statuses: set[str], has_conditions: bool) -> bool:
    """§5.1: does ONE `[[verdict_rule]]` row's structured predicates match `mandatory_statuses`
    (the set of MANDATORY disposition statuses) and `has_conditions` (whether the decision carries
    >= 1 [[condition]])? Reads exactly the row's own fields (`mandatory_any`, `mandatory_all_in`,
    `mandatory_not_all`, `conditions`) — a row missing a predicate key is unconstrained on that
    axis, never silently "always true" on every axis (states.toml declares all four rows'
    predicates explicitly)."""
    if "mandatory_any" in row:
        if not (mandatory_statuses & set(row.get("mandatory_any") or [])):
            return False
    if "mandatory_all_in" in row:
        allowed = set(row.get("mandatory_all_in") or [])
        if not mandatory_statuses.issubset(allowed):
            return False
    if "mandatory_not_all" in row:
        target = row.get("mandatory_not_all")
        # "not every mandatory disposition equals this status" — vacuously FALSE (so the row does
        # NOT match) when mandatory_statuses is empty, since "all() of nothing" is vacuously true.
        if not mandatory_statuses or all(s == target for s in mandatory_statuses):
            return False
    cond = row.get("conditions")
    if cond == "none" and has_conditions:
        return False
    if cond == "some" and not has_conditions:
        return False
    # cond == "any" (or absent) matches regardless.
    return True


def evaluate_verdict_rules(rows: list[dict], mandatory_statuses: set[str], has_conditions: bool) -> str | None:
    """§5.1: first matching `[[verdict_rule]]` row wins. Returns None when no row admits the
    combination — fail-closed (an undecidable combination is never auto-accepted, Finding 10)."""
    for row in rows:
        if verdict_row_matches(row, mandatory_statuses, has_conditions):
            v = row.get("verdict")
            if v in DECISION_VERDICTS:
                return v
    return None


# ---------------------------------------------------------------------------------------------
# check-decision — protocol.md §5, §5.1, §5.2
# ---------------------------------------------------------------------------------------------

_RUN_RESULT_SEVERITY = {"pass": 0, "not-run": 1, "error": 2, "fail": 3}


def worst_run_result(results: list) -> str | None:
    """§5.0: "Conflicting runs on one claim: the worst result wins (fail > error > not-run >
    pass)." Returns None when `results` is empty (no run at all — distinct from a `not-run`
    result, which IS a run)."""
    results = [r for r in results if r in _RUN_RESULT_SEVERITY]
    if not results:
        return None
    return max(results, key=lambda r: _RUN_RESULT_SEVERITY[r])


def check_disposition_coverage_row(
    disp: dict, req: dict, cov_status: str, runs_by_claim: dict[str, list[dict]],
    verification_mode: str, package: dict, witnesses: list[str] | None = None,
) -> str | None:
    """§5.2. Returns an error message, or None if the row coheres.

    `witnesses` (Q5, §16c/§5.0: "the basis claims of R") is the set of claims the computed
    coverage names as witnesses for R (for an item R, the claims that met its floor; for a
    cross-cutting R, its candidate claims meeting every demand) — passed in by the caller, which
    already computes this as `cov["requirements"][rid]["basis"]`. The ADVERSE (worst-result) check
    ranges over `witnesses(R) ∪ cited basis`: the union is normative so the adverse rule can never
    be narrowed by citing only the favourable claim. The POSITIVE pass-run obligation
    (`every_basis_claim_passes`) stays over the cited `basis` only — unaffected by this widening."""
    status = disp.get("status")
    basis = disp.get("basis") or []
    adverse_claims = set(basis) | set(witnesses or [])

    def worst_for(cid: str) -> str | None:
        return worst_run_result([r.get("result") for r in runs_by_claim.get(cid, [])])

    def every_basis_claim_passes() -> bool:
        # Finding 8: "one passing run never covers another claim" — EVERY basis claim needs its
        # own pass (worst-result-wins when a claim has multiple runs), not just any one of them.
        if not basis:
            return False
        return all(worst_for(cid) == "pass" for cid in basis)

    def any_basis_claim_fails() -> bool:
        # Q5 (§5.0/§5.2): the adverse check ranges over witnesses(R) ∪ cited basis, never the
        # cited basis alone.
        return any(worst_for(cid) == "fail" for cid in adverse_claims)

    def all_basis_claims_are(results: set) -> bool:
        if not basis:
            return False
        for cid in basis:
            w = worst_for(cid)
            if w is None or w not in results:
                return False
        return True

    def any_basis_claim_error_or_not_run() -> bool:
        # Q5: adverse-only widening, same as any_basis_claim_fails above.
        return any(worst_for(cid) in ("error", "not-run") for cid in adverse_claims)

    # Finding 8 (§5.2): "Adverse runs bind every mode and every disposition." A consumer that
    # watched a basis claim's own recipe FAIL cannot disposition the requirement `satisfied` (or
    # `satisfied-with-conditions`) under ANY mode — including `spot-check`/`package-trusted` — and
    # cannot route around it with a condition. `error`/`not-run` under `re-execute-all` similarly
    # forecloses everything except insufficient-evidence/unsatisfied/(waivable) waived. This gate
    # runs BEFORE the per-status branches below, since it overrides all of them uniformly.
    adverse_fail = any_basis_claim_fails()
    adverse_error_not_run = verification_mode == "re-execute-all" and any_basis_claim_error_or_not_run()
    if adverse_fail:
        allowed = {"unsatisfied"} | ({"waived"} if req.get("waivable") else set())
        if status not in allowed:
            return (
                f"a [[verification.run]] on a basis claim of {req.get('id')!r} observed 'fail' "
                f"(worst-result-wins across conflicting runs) — the requirement may only be "
                f"dispositioned {sorted(allowed)} under ANY mode (including spot-check/"
                f"package-trusted), got {status!r} (§5.2, Finding 8)"
            )
    elif adverse_error_not_run:
        allowed = {"insufficient-evidence", "unsatisfied"} | ({"waived"} if req.get("waivable") else set())
        if status not in allowed:
            return (
                f"a [[verification.run]] on a basis claim of {req.get('id')!r} observed "
                f"'error'/'not-run' under mode='re-execute-all' — the requirement may only be "
                f"dispositioned {sorted(allowed)}, got {status!r} (§5.2, Finding 8)"
            )

    if status == "satisfied":
        if cov_status != "satisfied":
            return f"disposition 'satisfied' but coverage computed {cov_status!r} (§5.2)"
        needs_run = verification_mode == "re-execute-all" or (
            # §3.7: `third-party` needs a recorded run too — it is STRICTER than
            # consumer-run (independent of both sides), never a weaker substitute for it.
            (req.get("evidence") or {}).get("independence") in ("consumer-run", "third-party")
        )
        if needs_run and not every_basis_claim_passes():
            return (
                "disposition 'satisfied' requires a PASS [[verification.run]] on EVERY basis "
                "claim (worst-result-wins across conflicting runs on the same claim — one "
                "passing run never covers another claim) when mode=re-execute-all or "
                "independence=consumer-run/third-party (§5.0, §5.2, Finding 8, §3.7)"
            )
        return None

    if status == "satisfied-with-conditions":
        # §5.2: `cov(R) = satisfied` (a condition on top of a met requirement), OR `cov(R) !=
        # satisfied AND waivable = true` with a full waiver carrying code='deferred' — accepting
        # a below-floor requirement on a promise IS a time-bounded waiver, and a non-waivable
        # requirement cannot be waived by any name (Finding 3 — the reproduced bypass).
        if not disp.get("conditions"):
            return "disposition 'satisfied-with-conditions' requires >= 1 cited condition (§5.2)"
        if cov_status != "satisfied":
            if not req.get("waivable"):
                return (
                    f"disposition 'satisfied-with-conditions' on a BELOW-FLOOR, NON-WAIVABLE "
                    f"requirement ({req.get('id')!r}) is refused — accepting below floor on a "
                    f"promise is a time-bounded waiver, and a non-waivable requirement cannot "
                    f"be waived by any name (§5.2, Finding 3)"
                )
            w = disp.get("waiver")
            if not isinstance(w, dict) or not all(_nonempty(w.get(k)) for k in ("reason", "code", "authority")):
                return (
                    "disposition 'satisfied-with-conditions' on cov != 'satisfied' requires a "
                    "full [disposition.waiver] with reason/code/authority (§5.2, Finding 3)"
                )
            if w.get("code") != "deferred":
                return (
                    f"disposition 'satisfied-with-conditions' on cov != 'satisfied' requires "
                    f"[disposition.waiver].code = 'deferred', got {w.get('code')!r} (§5.2, Finding 3)"
                )
        else:
            # Finding 8: "satisfied-with-conditions needs... the same run obligations as
            # satisfied" when cov(R) = satisfied under re-execute-all/consumer-run — previously
            # ONLY the plain 'satisfied' branch required a passing run on every basis claim.
            needs_run = verification_mode == "re-execute-all" or (
                (req.get("evidence") or {}).get("independence") in ("consumer-run", "third-party")
            )
            if needs_run and not every_basis_claim_passes():
                return (
                    "disposition 'satisfied-with-conditions' on cov(R) = 'satisfied' requires a "
                    "PASS [[verification.run]] on EVERY basis claim — the same run obligations "
                    "as 'satisfied' — when mode=re-execute-all or independence=consumer-run/"
                    "third-party (§5.2, Finding 8, §3.7)"
                )
        return None

    if status == "waived":
        # Finding 2 (§5.2, protocol.md line 632): `waived` on a cov(R) = satisfied requirement is
        # permitted when there is an adverse run — a basis claim's own recipe observed 'fail' —
        # because the adverse gate above (Finding 8) means the requirement CANNOT be satisfied by
        # this evidence regardless of what static coverage computed. Only when cov(R) = satisfied
        # AND there is no adverse fail is `waived` actually meaningless: coverage already says the
        # requirement holds and nothing contradicts it, so there is nothing to waive.
        if cov_status == "satisfied" and not adverse_fail:
            return "disposition 'waived' is meaningless when coverage is already 'satisfied' (§5.2)"
        if not req.get("waivable"):
            return f"disposition 'waived' on a non-waivable requirement ({req.get('id')!r}) (§5.2, §3.1 rule 3)"
        w = disp.get("waiver")
        if not isinstance(w, dict) or not all(_nonempty(w.get(k)) for k in ("reason", "code", "authority")):
            return "disposition 'waived' requires a full [disposition.waiver] with reason, code, authority (§5.2, P4)"
        if w.get("code") not in WAIVER_CODES:
            return f"disposition.waiver.code must be one of {sorted(WAIVER_CODES)}, got {w.get('code')!r}"
        return None

    if status == "insufficient-evidence":
        if cov_status in INSUFFICIENT_COV:
            return None
        if all_basis_claims_are({"fail", "error", "not-run"}):
            return None
        return (
            f"disposition 'insufficient-evidence' requires cov in {sorted(INSUFFICIENT_COV)} or "
            f"a verification run with result in {{fail,error,not-run}} on every basis claim, "
            f"got cov={cov_status!r} (§5.2)"
        )

    if status == "unsatisfied":
        if cov_status != "satisfied":
            return None
        if any_basis_claim_fails():
            return None
        return (
            f"disposition 'unsatisfied' requires cov != 'satisfied' or a failing verification "
            f"run on a basis claim, got cov={cov_status!r} with no failing run (§5.2)"
        )

    if status == "not-applicable":
        # Q6 (§5.1/§5.2): 'not-applicable' is admissible ONLY on an OPTIONAL requirement. A
        # MANDATORY requirement is never dispositioned 'not-applicable' — it is dispositioned
        # 'waived' with [disposition.waiver].code = 'not-applicable' instead (needs
        # waivable=true + a full waiver); a NON-waivable mandatory requirement that is genuinely
        # not-applicable is a CONTRACT DEFECT routed via [[deviation]] kind='requirement-defect'
        # / [[requirement_feedback]] (§3.5), not a disposition choice here.
        if req.get("mandatory"):
            return (
                f"disposition 'not-applicable' is refused on MANDATORY requirement "
                f"{req.get('id')!r} — disposition it 'waived' with "
                f"[disposition.waiver].code = 'not-applicable' instead; a non-waivable mandatory "
                f"requirement that is genuinely not-applicable is a CONTRACT DEFECT routed via "
                f"[[deviation]] kind='requirement-defect' (§5.1, §5.2)"
            )
        devs = [
            d for d in (package.get("deviation") or [])
            if isinstance(d, dict) and d.get("requirement") == req.get("id") and d.get("kind") == "not-applicable"
        ]
        if not devs:
            return "disposition 'not-applicable' requires a [[deviation]] of kind 'not-applicable' naming this requirement (§5.2)"
        return None

    return f"disposition status {status!r} is not one of {sorted(DISPOSITION_STATUSES)}"


def check_decision(
    decision: dict, contract: dict, package: dict,
    contract_path: Path, package_path: Path,
    previous_contract_path: Path | None = None,
    previous_paths: list | None = None,
    previous_dir: str | None = None,
    verdict_rules: list[dict] | None = None,
    decision_path: Path | None = None,
) -> Reporter:
    """§5.0: "Decision validity is transitive" — `contract_path`/`package_path` are REQUIRED
    (Finding 4): a decision cannot be checked without transitively re-validating what it decided
    about. `previous_contract_path`/`previous_paths`/`previous_dir` are passed straight through to
    `check_package`'s own `check-contract` chain validation (§3.3, Finding 4) when the bound
    contract supersedes another. `verdict_rules` (Finding 10) is the `[[verdict_rule]]` row list
    §5.1 is evaluated against; None loads the real `states.toml` (a caller — the selftest's
    watched-break case — may inject a tampered list to prove the evaluator actually depends on
    it). `decision_path` (S4) is OPTIONAL and used only to resolve a `[derivation].evidence[].ref`
    that names a local file, so its digest can be recomputed and compared "where resolvable"; a
    caller with no path on disk (or an evidence entry naming a remote resource) still gets full
    shape validation, just no digest recompute."""
    rep = Reporter("decision")

    document = decision.get("document")
    if not isinstance(document, dict):
        rep.error("[document] section missing")
        document = {}
    else:
        if document.get("protocol") != PROTOCOL_ID:
            rep.error(f"[document].protocol must be {PROTOCOL_ID!r}")
        if document.get("kind") != "decision":
            rep.error(f"[document].kind must be 'decision', got {document.get('kind')!r}")
        if not _nonempty(document.get("id")):
            rep.error("[document].id must be a nonempty string")
        issued_at = document.get("issued_at")
        if not _nonempty(issued_at):
            rep.error("[document].issued_at must be a nonempty string")
        elif not is_rfc3339_datetime(issued_at):
            # Finding 6: a non-empty but unparseable issued_at must be an ERROR here — the VALID
            # path previously never checked its format at all, so a decision this malformed
            # passed check-decision and then reached the --effect ceiling math unguarded.
            rep.error(f"[document].issued_at must be RFC 3339, got {issued_at!r} (§3.2/§5.0)")
        if not _nonempty(document.get("issuer")):
            rep.error("[document].issuer must be a nonempty string")

    # §5.5 (plan choice 1) — merits: OPTIONAL, default true. false says this decision
    # renders NO merits judgment (closed for a reason outside the artifact) and REQUIRES `reason`.
    # Read early: the "missing disposition" check below (§4.1's sibling on the decision side)
    # needs it before `verdict` is otherwise read.
    merits = document.get("merits")
    if merits is None:
        merits = True
    elif not isinstance(merits, bool):
        rep.error(f"[document].merits must be a boolean, got {merits!r} (§5.5)")
        merits = True
    reason = document.get("reason")
    if merits is False and not _nonempty(reason):
        rep.error("[document].reason must be a nonempty string when merits = false (§5.5)")

    contract_authority = (contract.get("acceptance") or {}).get("authority")
    producer_names = producer_identity_set(contract, package)  # Finding 7: the WHOLE set
    issuer = document.get("issuer")
    if issuer != contract_authority:
        rep.error(
            f"issuer ({issuer!r}) must equal the contract's [acceptance].authority "
            f"({contract_authority!r}) (P5)"
        )
    if issuer is not None and issuer in producer_names:
        rep.error(
            f"issuer ({issuer!r}) must not be in the package's producer identity set "
            f"({sorted(producer_names)!r}) (P5, §4.1 rule 7, Finding 7)"
        )

    # §5.4 — derived decisions: [derivation] present -> [document].recorded_by
    # REQUIRED. issuer/authority is UNCHANGED (P5, above): the contract's named authority, never
    # the recorder. A recorder transcribes, never decides.
    derivation = decision.get("derivation")
    recorded_by = document.get("recorded_by")
    if derivation is not None:
        if not isinstance(derivation, dict):
            rep.error("[derivation] must be a table (S4)")
            derivation = {}
        if not _nonempty(recorded_by):
            rep.error(
                "[document].recorded_by must be a nonempty string when [derivation] is present "
                "— a derived decision names who transcribed it, distinct from issuer/authority "
                "(S4)"
            )
        if not _nonempty(derivation.get("authority_act")):
            rep.error(
                "[derivation].authority_act must be a nonempty string — what the external "
                "authority did (e.g. 'merge', 'approval', 'close') (S4)"
            )
        if not _nonempty(derivation.get("rule")):
            rep.error("[derivation].rule must be a nonempty string — the declared derivation rule (S4)")
        evidence = derivation.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            rep.error("[derivation].evidence must be a nonempty list of {ref, digest?, uri?} tables (S4)")
        else:
            for eidx, ev in enumerate(evidence):
                ectx = f"[derivation].evidence[{eidx}]"
                if not isinstance(ev, dict):
                    rep.error(f"{ectx}: must be a table (S4)")
                    continue
                if not _nonempty(ev.get("ref")):
                    rep.error(f"{ectx}.ref must be a nonempty string (S4)")
                for opt_field in ("digest", "uri"):
                    val = ev.get(opt_field)
                    if val is not None and not _nonempty(val):
                        rep.error(f"{ectx}.{opt_field}, if present, must be a nonempty string (S4)")
                # "check-decision validates ... evidence digests where resolvable" — a best-effort
                # local recompute when `ref` resolves to a real file next to the decision; a
                # remote/unresolvable ref is carried as declared, never silently treated as
                # verified (P9).
                digest = ev.get("digest")
                ref = ev.get("ref")
                if _nonempty(digest) and _nonempty(ref) and decision_path is not None:
                    candidate = decision_path.parent / ref
                    if candidate.is_file():
                        try:
                            recomputed = m11.digest_file("evidence-record", candidate)
                        except (OSError, ValueError):
                            recomputed = None
                        if recomputed is not None:
                            want = digest.rsplit(":", 1)[-1].lower()
                            got = recomputed.rsplit(":", 1)[-1].lower()
                            if want != got:
                                rep.error(
                                    f"{ectx}.digest does not match the recomputed digest of "
                                    f"{ref!r}: declared {digest!r}, recomputed {recomputed!r} (S4)"
                                )

        # recorded_by MAY equal the package's producer identity ONLY when the boundary is
        # cross-org AND the contract's authority is a genuine third party (neither the named
        # consumer nor any producer identity) — otherwise an ERROR: a recorder transcribes, never
        # decides, and a producer recording its own internal decision collapses that separation.
        if _nonempty(recorded_by) and recorded_by in producer_names:
            _parties = contract.get("parties") or {}
            _boundary = _parties.get("boundary") or "internal"
            _consumer_name = (_parties.get("consumer") or {}).get("name")
            _authority_is_third_party = (
                _nonempty(contract_authority)
                and contract_authority != _consumer_name
                and contract_authority not in producer_names
            )
            if _boundary != "cross-org" or not _authority_is_third_party:
                rep.error(
                    f"[document].recorded_by ({recorded_by!r}) is in the package's producer "
                    f"identity set — only legal when [parties].boundary = 'cross-org' and the "
                    f"contract's authority is a genuine third party (neither consumer nor "
                    f"producer); a recorder transcribes, never decides (S4)"
                )
    elif _nonempty(recorded_by):
        rep.warn(
            "[document].recorded_by is present but [derivation] is not — harmless, but check "
            "whether a [derivation] table was intended (S4)"
        )

    # provisional (§3.5): REQUIRED true when the bound contract's phase != final; must be absent
    # or false when phase == final.
    contract_phase = (contract.get("acceptance") or {}).get("phase") or "final"
    provisional = document.get("provisional")
    if contract_phase != "final":
        if provisional is not True:
            rep.error(
                f"[document].provisional must be true — the bound contract's phase is "
                f"{contract_phase!r}, not 'final' (§3.5)"
            )
    else:
        if provisional not in (None, False):
            rep.error(
                f"[document].provisional must be absent or false when the bound contract's "
                f"phase is 'final', got {provisional!r} (§3.5)"
            )

    # requirement_feedback (§3.5): optional, any phase.
    req_by_id_for_feedback = requirement_by_id(contract)
    for idx, fb in enumerate(decision.get("requirement_feedback") or []):
        fctx = f"requirement_feedback[{idx}]"
        if not isinstance(fb, dict):
            rep.error(f"{fctx}: must be a table")
            continue
        kind = fb.get("kind")
        if kind not in REQUIREMENT_FEEDBACK_KINDS:
            rep.error(f"{fctx}: kind must be one of {sorted(REQUIREMENT_FEEDBACK_KINDS)}, got {kind!r}")
        rid = fb.get("requirement")
        if kind != "missing" and rid not in req_by_id_for_feedback:
            rep.error(f"{fctx}: requirement {rid!r} does not resolve to a contract requirement (only kind='missing' may name a not-yet-existing id)")
        if not _nonempty(fb.get("statement")):
            rep.error(f"{fctx}: statement must be a nonempty string")
        if not _nonempty(fb.get("proposed")):
            rep.error(f"{fctx}: proposed must be a nonempty string")

    binds = decision.get("binds")
    if not isinstance(binds, dict):
        rep.error("[binds] section missing")
        binds = {}
    else:
        bc = binds.get("contract") or {}
        bp = binds.get("package") or {}
        bs = binds.get("subject") or {}
        contract_id = (contract.get("document") or {}).get("id")
        if bc.get("id") != contract_id:
            rep.error(f"[binds].contract.id ({bc.get('id')!r}) != presented contract id ({contract_id!r})")
        _reject_bare_m11_wire(rep, bc.get("hash"), "contract", "[binds].contract.hash")
        _reject_bare_m11_wire(rep, bp.get("hash"), "manifest", "[binds].package.hash")
        # Protocol identity = format identity: [binds].subject MUST carry the SAME
        # identity FORM the presented package declares — 'commit' for git-revision, 'digest' for
        # content-digest or components (B1: the aggregate `subject:` digest over components IS the
        # components identity, not a second one) — classified via check_core's own function, never
        # re-implemented (§7). Digest hex compares case-insensitively (B16); commit hex is already
        # lowercase-only by format grammar, so lower() is a harmless no-op there.
        pkg_id_field, pkg_id_value = _subject_binds_field(package.get("subject") or {})
        bs_id_field, bs_id_value = _subject_binds_field(bs)
        if pkg_id_field is None:
            rep.error(
                "[binds].subject: the presented package carries no certified subject identity "
                "(B1) to compare against (§4.1 rule 5)"
            )
        elif bs_id_field != pkg_id_field or (bs_id_value or "").lower() != (pkg_id_value or "").lower():
            rep.error(
                f"[binds].subject.{bs_id_field or pkg_id_field} ({bs_id_value!r}) != the presented "
                f"package's [subject].{pkg_id_field} ({pkg_id_value!r}) — stale (P7)"
            )
        # [binds] hashes must recompute over the PRESENTED files (§5, P7). A mismatch is staleness:
        # the exact file bytes checked here are no longer what the decision judged.
        if contract_path is not None:
            try:
                recomputed = m11.digest_file("contract", contract_path)
                if bc.get("hash") != recomputed:
                    rep.error(
                        f"[binds].contract.hash does not match M11('contract:', <presented "
                        f"contract file>) — stale (P7): got {bc.get('hash')!r}, recomputed "
                        f"{recomputed!r}"
                    )
            except OSError as e:
                rep.error(f"could not recompute contract hash: {e}")
        if package_path is not None:
            try:
                recomputed = m11.digest_file("manifest", package_path)
                if bp.get("hash") != recomputed:
                    rep.error(
                        f"[binds].package.hash does not match M11('manifest:', <presented "
                        f"package file>) — stale (P7): got {bp.get('hash')!r}, recomputed "
                        f"{recomputed!r}"
                    )
            except OSError as e:
                rep.error(f"could not recompute package hash: {e}")

    # -----------------------------------------------------------------------------------------
    # Finding 4 — decision validity is TRANSITIVE (§5.0): re-run check-contract (with
    # --previous when the bound contract supersedes another — the successor is fully validated
    # only via check-package below, which does exactly this) and the format validator +
    # check-package on the bound package. A decision whose bindings resolve to an INVALID
    # contract or package is invalid even if its own hashes match; coverage output alone never
    # establishes validity.
    # -----------------------------------------------------------------------------------------
    supersedes = (contract.get("document") or {}).get("supersedes")
    if supersedes and previous_contract_path is None and not previous_paths and not previous_dir:
        rep.error(
            f"the bound contract supersedes {supersedes!r} but no --previous/--previous-dir was "
            f"given to validate the chain to its root (§3.3, §3.5, §5.0, Finding 4)"
        )
    pkg_rep, cov = check_package(
        package, contract, package_path, contract_path, strict=False,
        previous_contract_path=previous_contract_path,
        previous_paths=previous_paths, previous_dir=previous_dir,
    )
    rep.merge(pkg_rep, prefix="[check-contract/check-package/package-validator transitively] ")

    # Finding 17: package-level profile constraints (e.g. verification/code/rust.md's `dirty` must be false)
    # (illustrative; profile vocabulary) are only WARNED by check-package (a producer may submit
    # a dirty package to see coverage);
    # a decision may never ACCEPT one, so check-decision ENFORCES the same constraint as an error.
    _decision_profile = PROFILES.get(package_profile_id(package))
    if _decision_profile is not None and _decision_profile.get("package_constraints"):
        for msg in _decision_profile["package_constraints"](package):
            rep.error(f"{msg} (§6.6 item 6, enforced at decision time, Finding 17)")

    if rep.unknowns:
        # §5.0: establish bound-package validity before judging its coverage.
        return rep

    verification = decision.get("verification")
    mode = None
    runs_by_claim: dict[str, list[dict]] = {}
    all_runs: list[dict] = []
    if not isinstance(verification, dict):
        rep.error("[verification] section missing")
    else:
        mode = verification.get("mode")
        if mode not in MODE_RANK:
            rep.error(f"[verification].mode must be one of {VERIFICATION_MODES}, got {mode!r}")
        contract_mode = (contract.get("acceptance") or {}).get("consumer_verification")
        if mode in MODE_RANK and contract_mode in MODE_RANK and MODE_RANK[mode] < MODE_RANK[contract_mode]:
            rep.error(
                f"[verification].mode ({mode!r}) is weaker than the contract's "
                f"consumer_verification ({contract_mode!r}) (§5)"
            )
        runs = verification.get("run")
        runs = [r for r in runs if isinstance(r, dict)] if isinstance(runs, list) else []
        claim_ids = {c.get("id") for c in (package.get("claim") or []) if isinstance(c, dict)}
        for idx, r in enumerate(runs):
            rctx = f"verification.run[{idx}]"
            # Finding 8: "an INCOMPLETE run is an error, not an absent run" — claim, command,
            # observed, result and at are all REQUIRED.
            for field in ("claim", "command", "observed", "at"):
                if not _nonempty(r.get(field)):
                    rep.error(
                        f"{rctx}: {field!r} must be a nonempty string — an incomplete run is an "
                        f"error, not an absent run (§5.0, Finding 8)"
                    )
            if _nonempty(r.get("claim")) and r.get("claim") not in claim_ids:
                rep.error(f"{rctx}: claim {r.get('claim')!r} does not exist in the package")
            if r.get("result") not in RUN_RESULTS:
                rep.error(f"{rctx}: result must be one of {sorted(RUN_RESULTS)}, got {r.get('result')!r}")
            runs_by_claim.setdefault(r.get("claim"), []).append(r)
            all_runs.append(r)

    req_by_id = requirement_by_id(contract)
    claim_ids = {c.get("id") for c in (package.get("claim") or []) if isinstance(c, dict)}
    all_claims = [c for c in (package.get("claim") or []) if isinstance(c, dict)]

    def associated_claims_for(rid: str, req: dict) -> set:
        """Finding 8 (basis eligibility): the claims a disposition's `basis` may legitimately
        name for a requirement whose coverage is NOT `satisfied` — everything else is an
        "unrelated claim", regardless of whether it exists somewhere else in the package."""
        kind = req.get("kind", "item")
        if kind == "cross-cutting":
            over = req.get("over")
            if over == "all":
                return {c.get("id") for c in all_claims if c.get("status") == "evidenced"}
            overset = set(over or [])
            return {
                c.get("id") for c in all_claims
                if c.get("clause") in overset and c.get("status") == "evidenced"
            }
        return {c.get("id") for c in all_claims if c.get("clause") == rid}

    dispositions = decision.get("disposition")
    dispositions = [d for d in dispositions if isinstance(d, dict)] if isinstance(dispositions, list) else []
    seen_req_disp: set[str] = set()

    for idx, d in enumerate(dispositions):
        dctx = f"disposition[{idx}]"
        rid = d.get("requirement")
        if rid not in req_by_id:
            rep.error(f"{dctx}: requirement {rid!r} does not resolve to a contract requirement")
            continue
        dctx = f"disposition (requirement {rid!r})"
        if rid in seen_req_disp:
            rep.error(f"{dctx}: duplicate disposition for this requirement (§5: exactly one per requirement)")
        seen_req_disp.add(rid)
        if d.get("status") not in DISPOSITION_STATUSES:
            rep.error(f"{dctx}: status must be one of {sorted(DISPOSITION_STATUSES)}, got {d.get('status')!r}")
            continue
        basis = d.get("basis")
        cov_status = cov["requirements"].get(rid, {}).get("status")
        if not isinstance(basis, list) or not all(isinstance(b, str) for b in basis):
            rep.error(f"{dctx}: basis must be a list of strings")
        else:
            # Finding 8: basis claims must be ELIGIBLE coverage witnesses for THIS requirement —
            # an unrelated claim (e.g. one belonging to a different requirement) is an error, not
            # merely "must exist somewhere in the package".
            if cov_status == "satisfied":
                eligible = set(cov["requirements"].get(rid, {}).get("basis") or [])
            else:
                eligible = associated_claims_for(rid, req_by_id[rid])
            for cid in basis:
                if cid not in claim_ids:
                    rep.error(f"{dctx}: basis claim {cid!r} does not exist in the package")
                elif cid not in eligible:
                    rep.error(
                        f"{dctx}: basis claim {cid!r} is not an eligible coverage witness for "
                        f"requirement {rid!r} (unrelated claim in basis, §5.0, Finding 8)"
                    )
        conds = d.get("conditions")
        if conds is not None and not (isinstance(conds, list) and all(isinstance(x, str) for x in conds)):
            rep.error(f"{dctx}: conditions, if present, must be a list of strings")

        if mode is not None:
            # Q5 (§5.0/§5.2): pass the computed coverage's witnesses(R) so the adverse check
            # ranges over witnesses(R) ∪ cited basis, never the cited basis alone.
            req_witnesses = cov["requirements"].get(rid, {}).get("basis") or []
            err = check_disposition_coverage_row(
                d, req_by_id[rid], cov_status, runs_by_claim, mode, package, witnesses=req_witnesses,
            )
            if err:
                rep.error(f"{dctx}: {err}")

    missing = set(req_by_id) - seen_req_disp
    if missing:
        if merits is False:
            # §5.5: a merits=false decision renders no per-requirement judgment; omission is
            # expected here, never a hard error (unlike the ordinary merits-bearing path, §5).
            rep.warn(
                f"missing [[disposition]] for requirement(s): {sorted(missing)} — tolerated "
                f"because merits=false (no merits judgment was made, §5.5)"
            )
        else:
            rep.error(f"missing [[disposition]] for requirement(s): {sorted(missing)} (§5)")

    # Finding 8: every [[verification.run]] must name a claim that is either a coverage witness
    # (met a floor somewhere) or cited in SOME disposition's basis — never an unrelated claim.
    all_witnesses: set = set()
    for r in cov["requirements"].values():
        all_witnesses.update(r.get("basis") or [])
    all_basis_cited: set = set()
    for d in dispositions:
        for cid in d.get("basis") or []:
            if isinstance(cid, str):
                all_basis_cited.add(cid)
    allowed_run_claims = all_witnesses | all_basis_cited
    for idx, r in enumerate(all_runs):
        cid = r.get("claim")
        if _nonempty(cid) and cid in claim_ids and cid not in allowed_run_claims:
            rep.error(
                f"verification.run naming claim {cid!r}: not a coverage witness and not cited "
                f"in any disposition's basis (§5.0, Finding 8)"
            )

    conditions = decision.get("condition")
    conditions = [c for c in conditions if isinstance(c, dict)] if isinstance(conditions, list) else []
    condition_ids: set[str] = set()
    disp_by_req = {d.get("requirement"): d for d in dispositions}
    CONDITION_ELIGIBLE_STATUSES = {"satisfied-with-conditions", "waived", "insufficient-evidence"}
    for idx, c in enumerate(conditions):
        cctx = f"condition[{idx}]"
        cid = c.get("id")
        if not _nonempty(cid):
            rep.error(f"{cctx}: 'id' must be a nonempty string")
        else:
            condition_ids.add(cid)
        rid = c.get("requirement")
        if rid not in req_by_id:
            rep.error(f"{cctx}: requirement {rid!r} does not resolve to a contract requirement")
        for f in ("statement", "discharged_by"):
            if not _nonempty(c.get(f)):
                rep.error(f"{cctx}: field {f!r} must be a nonempty string")
        # Finding 9 (§5.0a): "every condition.due ISO date, else invalid" — a malformed due date
        # makes the DECISION invalid (not merely effect-ineligible); a bare nonempty-string check
        # let `due = "nonsense"` through.
        if not is_iso_date(c.get("due")):
            rep.error(f"{cctx}: 'due' must be an ISO date (YYYY-MM-DD), got {c.get('due')!r} (§5.0a, Finding 9)")
        if c.get("owner") not in CONDITION_OWNERS:
            rep.error(f"{cctx}: owner must be one of {sorted(CONDITION_OWNERS)}, got {c.get('owner')!r}")

        # Finding 3: "Conditions bind to requirements" — both directions.
        if rid in req_by_id:
            if not req_by_id[rid].get("mandatory"):
                rep.error(
                    f"{cctx}: names OPTIONAL requirement {rid!r} — a condition on an optional "
                    f"requirement is an error (§5.1, Finding 3)"
                )
            else:
                disp = disp_by_req.get(rid)
                if disp is None or disp.get("status") not in CONDITION_ELIGIBLE_STATUSES:
                    rep.error(
                        f"{cctx}: names requirement {rid!r} whose disposition is "
                        f"{(disp.get('status') if disp else None)!r} — a condition on a "
                        f"'satisfied' (or missing) disposition is an error; conditions bind "
                        f"only to satisfied-with-conditions/waived/insufficient-evidence "
                        f"(§5.1, Finding 3)"
                    )
                elif _nonempty(cid) and cid not in (disp.get("conditions") or []):
                    rep.error(
                        f"{cctx}: names requirement {rid!r} but that disposition does not cite "
                        f"{cid!r} back in its own 'conditions' list (§5.1, Finding 3 — "
                        f"conditions bind to requirements both ways)"
                    )

    condition_by_id = {c.get("id"): c for c in conditions if _nonempty(c.get("id"))}
    for d in dispositions:
        drid = d.get("requirement")
        for cid in d.get("conditions") or []:
            if cid not in condition_ids:
                rep.error(
                    f"disposition (requirement {drid!r}) cites condition "
                    f"{cid!r}, which does not exist in [[condition]]"
                )
            else:
                # Finding 3 (§5.1): "every condition cited by a disposition must have
                # requirement == that disposition's requirement" — the ONLY direct check of
                # this, closing the cross-requirement bypass where R1's disposition cited a
                # condition C1 whose own [[condition]].requirement named a DIFFERENT
                # requirement (R5). The loop above only validated the condition's OWN named
                # requirement's disposition cites it back; it never checked every CITING
                # disposition against the condition's actual subject.
                c_req = condition_by_id[cid].get("requirement")
                if c_req != drid:
                    rep.error(
                        f"disposition (requirement {drid!r}) cites condition {cid!r}, but "
                        f"[[condition]] {cid!r}.requirement = {c_req!r} — a condition cited by "
                        f"a disposition must name THAT SAME requirement, never a different one "
                        f"(§5.1, Finding 3)"
                    )

        # Finding 3: every satisfied-with-conditions disposition AND every waived MANDATORY
        # disposition, when the decision's verdict is accepted-with-conditions, must cite >= 1
        # condition naming it. satisfied-with-conditions is already enforced verdict-agnostically
        # by check_disposition_coverage_row; 'waived' only needs its OWN remedy condition when it
        # is part of an acceptance (§5.2's closing clause) — enforced below once verdict is known.

    verdict = document.get("verdict")
    if merits is False:
        # §5.5 (plan choice 1): the closed-without-merits path REUSES the decision
        # lifecycle's existing 'lapsed' state (states.toml, `close-without-merits` transition)
        # rather than a new verdict word — DECISION_VERDICTS/[[verdict_rule]] (the 4-value,
        # disposition-driven verdict axis, §5.1) are UNCHANGED and not evaluated on this path,
        # since no merits judgment was made for them to be computed from. accepted/
        # accepted-with-conditions/rejected/evidence-requested are all disallowed: each asserts
        # exactly the judgment merits=false says never happened.
        if verdict != "lapsed":
            rep.error(
                f"[document].verdict must be 'lapsed' when merits = false — accepted, "
                f"accepted-with-conditions, rejected and evidence-requested all assert a merits "
                f"judgment that merits=false says never happened (§5.5), got {verdict!r}"
            )
        if conditions:
            rep.error(
                "verdict='lapsed' (merits=false) must not carry [[condition]] entries — no "
                "obligations arise from a decision that renders no merits judgment (§5.5)"
            )
    elif verdict not in DECISION_VERDICTS:
        rep.error(f"[document].verdict must be one of {sorted(DECISION_VERDICTS)}, got {verdict!r}")
    else:
        mandatory_statuses = {
            d.get("status") for d in dispositions
            if req_by_id.get(d.get("requirement"), {}).get("mandatory") and d.get("status") in DISPOSITION_STATUSES
        }
        has_conditions = bool(conditions)
        # Finding 10 (§5.1): the [[verdict_rule]] rows loaded from states.toml are THE executable
        # rule — evaluated here directly, never re-derived as a second Python copy of the table.
        #
        # Finding 11: re-run through `load_verdict_rules` even when the caller injected the rows
        # directly (the selftest watched-break harness does this) — that function is where the
        # `conditions` token is validated fail-closed, and the live `check_decision` path must
        # not skip that check just because it isn't loading states.toml itself this time.
        try:
            if verdict_rules is None:
                verdict_rules = load_verdict_rules(_default_states_doc())
            else:
                verdict_rules = load_verdict_rules({"verdict_rule": verdict_rules})
        except VerdictRuleError as e:
            rep.error(f"[[verdict_rule]] table is malformed, refused fail-closed: {e} (Finding 11)")
            verdict_rules = []
        expected = evaluate_verdict_rules(verdict_rules, mandatory_statuses, has_conditions)
        if expected is None:
            rep.error(
                f"no [[verdict_rule]] row (states.toml) admits this combination of mandatory "
                f"disposition statuses ({sorted(mandatory_statuses)}) and conditions="
                f"{'some' if has_conditions else 'none'} — fail-closed, refused (Finding 10)"
            )
        elif expected != verdict:
            rep.error(
                f"[document].verdict = {verdict!r} but the states.toml [[verdict_rule]] table "
                f"computes {expected!r} from the mandatory dispositions {sorted(mandatory_statuses)} "
                f"and conditions={'some' if has_conditions else 'none'} (§5.1, Finding 10)"
            )

        if verdict == "accepted":
            if conditions:
                rep.error("verdict='accepted' but [[condition]] entries are present (§5.1)")
            if any(d.get("status") == "waived" and req_by_id.get(d.get("requirement"), {}).get("mandatory")
                   for d in dispositions):
                rep.error("verdict='accepted' but a mandatory requirement is disposed 'waived' (§5.1)")
        elif verdict == "accepted-with-conditions":
            if not conditions:
                rep.error("verdict='accepted-with-conditions' requires >= 1 [[condition]] (§5.1)")
            # Finding 3 (§5.2 closing clause): "a waiver without its own remedy condition is only
            # legal under rejected/evidence-requested, never as part of an acceptance" — a
            # mandatory 'waived' disposition under accepted-with-conditions must cite its own
            # condition (the cross-requirement check above already forces any CITED condition to
            # name this same requirement; this closes the case where nothing is cited at all).
            for d in dispositions:
                drid = d.get("requirement")
                if d.get("status") == "waived" and req_by_id.get(drid, {}).get("mandatory"):
                    if not d.get("conditions"):
                        rep.error(
                            f"disposition (requirement {drid!r}) is 'waived' under "
                            f"verdict='accepted-with-conditions' and must cite >= 1 condition "
                            f"naming it — a waiver without its own remedy condition is not legal "
                            f"as part of an acceptance (§5.2, Finding 3)"
                        )
        elif verdict == "evidence-requested":
            # Q7 (§5.1 exact text): "every MANDATORY insufficient-evidence disposition cites >= 1
            # condition ... with owner='producer'" — an OPTIONAL insufficient-evidence disposition
            # cites no condition at all (never demanded here).
            insufficient_reqs = [
                d.get("requirement") for d in dispositions
                if d.get("status") == "insufficient-evidence"
                and req_by_id.get(d.get("requirement"), {}).get("mandatory")
            ]
            for rid in insufficient_reqs:
                has_producer_condition = any(
                    c.get("requirement") == rid and c.get("owner") == "producer" for c in conditions
                )
                if not has_producer_condition:
                    rep.error(
                        f"verdict='evidence-requested' requires one [[condition]] with "
                        f"owner='producer' for insufficient-evidence requirement {rid!r} (§5.1)"
                    )
        elif verdict == "rejected":
            unsatisfied = [d for d in dispositions if d.get("status") == "unsatisfied"]
            for d in unsatisfied:
                if not _nonempty(d.get("note")):
                    rep.warn(
                        f"verdict='rejected': disposition for {d.get('requirement')!r} is "
                        f"'unsatisfied' with no 'note' explaining why (§5.1 'reasons in note')"
                    )

    validity = decision.get("validity")
    if isinstance(validity, dict) and "stale_after" in validity:
        if not is_iso_date(validity.get("stale_after")):
            rep.error(f"[validity].stale_after must be an ISO date (YYYY-MM-DD), got {validity.get('stale_after')!r}")

    return rep


def check_decision_effect(
    decision: dict, contract: dict, rep: Reporter, now_date: str, allow_conditions: bool,
) -> tuple[bool, str]:
    """§5.0a / Finding 12: `check-decision --effect` — a gate that unlocks an effect (publish,
    deploy, pay, merge) may act only on a decision that is VALID (§5.0, `rep.ok()` — computed by
    the caller BEFORE this is called), CURRENT (its bindings match the presented files — already
    part of `rep`'s hash-recompute checks), UNEXPIRED (`validity.stale_after`, when present, has
    not passed `now_date`), issued under a `final`-phase contract, with `provisional` absent or
    false, and whose verdict is `accepted` — or `accepted-with-conditions` only where the CALLER's
    own policy says conditions may be outstanding (`--allow-conditions`). Fails closed: any
    missing/malformed field is treated as ineligible, never as "presumably fine". Returns
    (eligible, reason)."""
    if not rep.ok():
        return False, "decision is not VALID — check-decision reported errors or INDETERMINATE findings (§5.0)"

    document = decision.get("document") or {}
    phase = (contract.get("acceptance") or {}).get("phase") or "final"
    if phase != "final":
        return False, f"bound contract's [acceptance].phase is {phase!r}, not 'final' (§5.0a)"

    provisional = document.get("provisional")
    if provisional not in (None, False):
        return False, f"[document].provisional is {provisional!r}, not absent/false (§5.0a)"

    validity = decision.get("validity") or {}
    stale_after = validity.get("stale_after")
    contract_stale_after_dur = (contract.get("acceptance") or {}).get("stale_after")

    # Finding 9 (§5.0a): "unexpired... and it is required, and capped at issued_at + the
    # contract's stale_after, whenever the contract sets one" — an ABSENT validity.stale_after, or
    # one set past the ceiling (e.g. deleted, or hand-edited to a far-future date), previously left
    # the decision eligible forever whenever the contract itself declared an expiry.
    if is_iso8601_duration(contract_stale_after_dur):
        if stale_after is None:
            return False, (
                f"the contract sets [acceptance].stale_after = {contract_stale_after_dur!r} but "
                f"the decision's [validity].stale_after is absent — REQUIRED and capped at "
                f"issued_at + the contract's duration (§5.0a, Finding 9)"
            )
        if not is_iso_date(stale_after):
            return False, f"[validity].stale_after {stale_after!r} is not a valid ISO date (§5.0a)"
        issued_at = document.get("issued_at")
        # Finding 6: an absent or unparseable issued_at must make the decision INELIGIBLE — this
        # branch only runs when the contract sets a stale_after duration, i.e. exactly when the
        # cap this issued_at feeds is REQUIRED. The old code let `ceiling_date` fall through to
        # None on a parse failure, and the `if ceiling_date is not None` guard below then SKIPPED
        # the cap entirely — fail-open on the publish/pay/deploy gate this function exists to
        # close. There is no "skip the cap" outcome any more: either it computes, or the decision
        # is refused.
        if not _nonempty(issued_at):
            return False, (
                f"the contract sets [acceptance].stale_after = {contract_stale_after_dur!r} but "
                f"[document].issued_at is absent — required to compute the issued_at + duration "
                f"ceiling (§5.0a, Finding 6/9)"
            )
        try:
            issued_dt = datetime.datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
        except ValueError:
            return False, (
                f"[document].issued_at {issued_at!r} is not a valid RFC 3339 datetime — the "
                f"issued_at + the contract's stale_after ceiling cannot be computed, refused "
                f"fail-closed rather than skipped (§5.0a, Finding 6)"
            )
        ceiling_date = (issued_dt + duration_to_timedelta(contract_stale_after_dur)).strftime("%Y-%m-%d")
        if stale_after > ceiling_date:
            return False, (
                f"[validity].stale_after ({stale_after}) exceeds the ceiling issued_at + "
                f"the contract's stale_after duration ({ceiling_date}) — later than the "
                f"ceiling is an error, earlier is allowed (§5.0a, Finding 9)"
            )
    elif stale_after is not None and not is_iso_date(stale_after):
        return False, f"[validity].stale_after {stale_after!r} is not a valid ISO date (§5.0a)"

    if stale_after is not None and is_iso_date(stale_after) and stale_after < now_date:
        return False, f"[validity].stale_after ({stale_after}) has passed (--now {now_date}) (§5.0a, P7)"

    # Finding 9: "not lapsed (no [[condition]].due is in the past...)" — whatever the verdict,
    # a decision with a condition past its own deadline is not effect-eligible.
    conditions = decision.get("condition")
    conditions = [c for c in conditions if isinstance(c, dict)] if isinstance(conditions, list) else []
    for c in conditions:
        due = c.get("due")
        if not is_iso_date(due):
            return False, f"[[condition]] {c.get('id')!r}.due {due!r} is not a valid ISO date (§5.0a, Finding 9)"
        if due < now_date:
            return False, (
                f"[[condition]] {c.get('id')!r}.due ({due}) is before --now ({now_date}) — "
                f"lapsed (§5.0a, Finding 9)"
            )

    verdict = document.get("verdict")
    if verdict == "accepted":
        return True, "eligible: valid, current, unexpired, final phase, not provisional, accepted, no lapsed conditions (§5.0a)"
    if verdict == "accepted-with-conditions":
        if allow_conditions:
            return True, "eligible: accepted-with-conditions, --allow-conditions given, no lapsed conditions (§5.0a)"
        return False, "verdict is 'accepted-with-conditions' but --allow-conditions was not given (§5.0a)"
    return False, f"verdict is {verdict!r}, not 'accepted' (§5.0a)"


# ---------------------------------------------------------------------------------------------
# check-states / transition — states.toml (header comment: the proof obligations, restated here)
# ---------------------------------------------------------------------------------------------

_FIELD_PATH_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*(\[\])?$")


def _normalize_from(from_val) -> list[str]:
    if isinstance(from_val, str):
        return [from_val]
    if isinstance(from_val, list):
        return [f for f in from_val if isinstance(f, str)]
    return []


def check_one_machine(name: str, m: dict) -> Reporter:
    rep = Reporter(f"machine.{name}")

    roles = m.get("roles")
    if not isinstance(roles, list) or not all(_nonempty(r) for r in roles):
        rep.error("roles must be a list of nonempty strings")
        roles = []
    role_set = set(roles) | {"any", "clock"}

    states = m.get("states")
    if not isinstance(states, list) or not all(_nonempty(s) for s in states):
        rep.error("states must be a list of nonempty strings")
        return rep
    state_set = set(states)

    initial = m.get("initial")
    if initial not in state_set:
        rep.error(f"initial ({initial!r}) is not one of states")
    terminal = m.get("terminal")
    if not isinstance(terminal, list) or not all(t in state_set for t in terminal):
        rep.error("terminal must be a list of states")
        terminal = []
    terminal_set = set(terminal)

    raw_transitions = m.get("transition")
    raw_transitions = raw_transitions if isinstance(raw_transitions, list) else []

    edges: list[tuple[str, str, str]] = []   # (from, to, name)
    seen_triples: set[tuple[str, str, str | None]] = set()
    outgoing_from: set[str] = set()

    for idx, t in enumerate(raw_transitions):
        tctx = f"transition[{idx}]"
        if not isinstance(t, dict):
            rep.error(f"{tctx}: must be a table")
            continue
        name = t.get("name")
        if not _nonempty(name):
            rep.error(f"{tctx}: 'name' must be a nonempty string")
        froms = _normalize_from(t.get("from"))
        if not froms:
            rep.error(f"{tctx} ({name!r}): 'from' must be a state string or a list of state strings")
        to = t.get("to")
        if to not in state_set:
            rep.error(f"{tctx} ({name!r}): 'to' ({to!r}) is not a declared state")
        by = t.get("by")
        if by not in role_set:
            rep.error(f"{tctx} ({name!r}): 'by' ({by!r}) is not a declared role (or 'any'/'clock')")
        guard = t.get("guard")
        requires = t.get("requires")
        if requires is not None:
            if not isinstance(requires, list) or not all(isinstance(r, str) for r in requires):
                rep.error(f"{tctx} ({name!r}): 'requires' must be a list of strings")
            else:
                for r in requires:
                    if not _FIELD_PATH_RE.match(r):
                        rep.error(
                            f"{tctx} ({name!r}): requires field {r!r} does not look like a "
                            f"declared field path (shape check only)"
                        )

        for f in froms:
            if f not in state_set:
                rep.error(f"{tctx} ({name!r}): 'from' state {f!r} is not a declared state")
                continue
            triple = (f, name, guard)
            if triple in seen_triples:
                rep.error(f"{tctx}: duplicate (from={f!r}, name={name!r}, guard={guard!r})")
            seen_triples.add(triple)
            outgoing_from.add(f)
            if to in state_set:
                edges.append((f, to, name))

    # every state reachable from initial
    if initial in state_set:
        fwd: dict[str, set[str]] = {s: set() for s in state_set}
        for f, to, _n in edges:
            fwd[f].add(to)
        seen = {initial}
        frontier = [initial]
        while frontier:
            cur = frontier.pop()
            for nxt in fwd.get(cur, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
        unreachable = state_set - seen
        if unreachable:
            rep.error(f"unreachable from initial ({initial!r}): {sorted(unreachable)} (dead state)")

        # every non-terminal has an outgoing transition
        for s in sorted(state_set - terminal_set):
            if s not in outgoing_from:
                rep.error(f"non-terminal state {s!r} has no outgoing transition (dead state)")

        # a terminal reachable from EVERY state
        rev_ok: dict[str, bool] = {}
        for s in state_set:
            seen_s = {s}
            frontier = [s]
            reaches_terminal = s in terminal_set
            while frontier and not reaches_terminal:
                cur = frontier.pop()
                for nxt in fwd.get(cur, ()):
                    if nxt in terminal_set:
                        reaches_terminal = True
                        break
                    if nxt not in seen_s:
                        seen_s.add(nxt)
                        frontier.append(nxt)
            rev_ok[s] = reaches_terminal
        no_terminal = [s for s, ok in sorted(rev_ok.items()) if not ok]
        if no_terminal:
            rep.error(f"no terminal state reachable from: {no_terminal} (dead state)")

    return rep


def check_verdict_rules(doc: dict) -> Reporter:
    rep = Reporter("verdict_rule")
    rows = doc.get("verdict_rule")
    rows = rows if isinstance(rows, list) else []
    verdicts = []
    for idx, r in enumerate(rows):
        if not isinstance(r, dict):
            rep.error(f"verdict_rule[{idx}]: must be a table")
            continue
        v = r.get("verdict")
        if v not in DECISION_VERDICTS:
            rep.error(f"verdict_rule[{idx}]: verdict must be one of {sorted(DECISION_VERDICTS)}, got {v!r}")
        else:
            verdicts.append(v)
    if len(rows) != 4:
        rep.error(f"expected exactly 4 [[verdict_rule]] rows, got {len(rows)}")
    if len(set(verdicts)) != len(verdicts):
        rep.error(f"[[verdict_rule]] verdicts are not all distinct: {verdicts}")
    if set(verdicts) != DECISION_VERDICTS and len(rows) == 4:
        rep.error(f"[[verdict_rule]] does not cover exactly the 4 verdicts {sorted(DECISION_VERDICTS)}, got {sorted(set(verdicts))}")
    return rep


def _literal_verdict_ground_truth(mandatory_statuses: set[str], has_conditions: bool) -> str | None:
    """Finding 10: the INDEPENDENT §5.1 ground truth, hand-written directly
    from protocol.md's table text — deliberately NOT derived from `verdict_row_matches` /
    `evaluate_verdict_rules` (the machinery under test, which reads states.toml's ACTUAL rows).
    This is the one hardcoded copy that is allowed to exist, precisely because nothing under test
    ever consults it: `check_decision` and `decide` both read the TOML rows; this function exists
    solely so `verify_verdict_table_exhaustive` has something independent to compare against. A
    states.toml row tampered into "always true", or an `evaluate_verdict_rules` bug, disagrees
    with this somewhere in the input space and is caught here — not just "are there 4 rows"."""
    # Row order matters, first match wins — mirroring states.toml's own row order (1..4). Rows 1
    # and 2 match on "ANY mandatory disposition has this status", so a co-occurring `not-applicable`
    # does not block them (protocol.md's row text never mentions `not-applicable` at all — it
    # simply admits no row of its own, so it only becomes "undecidable" when nothing ahead of it
    # matches either, i.e. when combined only with the satisfied-family statuses in rows 3/4).
    if "unsatisfied" in mandatory_statuses:
        return "rejected"
    if "insufficient-evidence" in mandatory_statuses:
        return "evidence-requested" if has_conditions else None
    if mandatory_statuses <= {"satisfied", "satisfied-with-conditions", "waived"}:
        if not mandatory_statuses or mandatory_statuses == {"satisfied"}:
            return "accepted" if not has_conditions else None
        return "accepted-with-conditions" if has_conditions else None
    return None  # e.g. a mandatory not-applicable with no unsatisfied/insufficient-evidence


def verify_verdict_table_exhaustive(doc: dict) -> Reporter:
    """Finding 10: "the enumeration compares two copies of Python branching, ignoring
    the supplied predicates and conditions" — the OLD version of this proof never read `doc` at
    all; it compared one Python function against a second, hand-written copy of the SAME
    branching, so a states.toml row tampered into `mandatory_any = ["always true"]`-style nonsense
    went completely undetected (nothing under test ever touched the file).

    This version loads the REAL `[[verdict_rule]]` rows from `doc` (`load_verdict_rules`) and
    evaluates them through `evaluate_verdict_rules` — the SAME function `check_decision` calls —
    across the full input space: every nonempty subset of `DISPOSITION_STATUSES` as the mandatory
    set, crossed with `has_conditions ∈ {False, True}` ("0" and "some" conditions, per the spec's
    `{0, some}` split). Each point is compared against `_literal_verdict_ground_truth`, which is
    independent of the row-matching machinery under test. A tampered states.toml row disagrees
    with the ground truth somewhere in this domain and is caught here — the SAME evaluation path
    `check_decision` uses on real decisions, not a parallel one."""
    import itertools
    rep = Reporter("verdict_rule_exhaustive")
    try:
        rows = load_verdict_rules(doc)
    except VerdictRuleError as e:
        rep.error(f"[[verdict_rule]] table is malformed, refused fail-closed: {e} (Finding 11)")
        return rep
    if not rows:
        rep.error("no [[verdict_rule]] rows to evaluate (Finding 10)")
        return rep

    domain = sorted(DISPOSITION_STATUSES)
    checked = 0
    for r in range(1, len(domain) + 1):
        for combo in itertools.combinations(domain, r):
            mandatory_statuses = set(combo)
            for has_conditions in (False, True):
                actual = evaluate_verdict_rules(rows, mandatory_statuses, has_conditions)
                want = _literal_verdict_ground_truth(mandatory_statuses, has_conditions)
                checked += 1
                if actual != want:
                    rep.error(
                        f"mandatory={sorted(mandatory_statuses)} conditions="
                        f"{'some' if has_conditions else 'none'}: evaluate_verdict_rules "
                        f"(states.toml's ACTUAL rows) returned {actual!r}, the independent §5.1 "
                        f"ground truth requires {want!r} (Finding 10)"
                    )
    expected_checked = (2 ** len(domain) - 1) * 2
    if checked != expected_checked:
        rep.error(f"internal: enumerated {checked} combinations, expected {expected_checked}")
    # Empty mandatory set (no mandatory requirements at all), no conditions -> vacuously
    # 'accepted' (unreachable per §3.3's "≥ 1 mandatory requirement", but must still be definite).
    if evaluate_verdict_rules(rows, set(), False) != "accepted":
        rep.error("evaluate_verdict_rules(rows, set(), False) must be 'accepted' (vacuous case, Finding 10)")
    return rep


def check_states(doc: dict) -> dict[str, Reporter]:
    """Returns {machine_name_or_'verdict_rule': Reporter}."""
    out: dict[str, Reporter] = {}
    machine = doc.get("machine")
    if not isinstance(machine, dict):
        out["machine"] = Reporter("machine")
        out["machine"].error("[machine.*] tables missing")
        return out
    for name, m in machine.items():
        if isinstance(m, dict):
            out[name] = check_one_machine(name, m)
    out["verdict_rule"] = check_verdict_rules(doc)
    # Finding 10: the executable proof, always run as part of check-states (not merely
    # in --selftest) — evaluated against THIS doc's own `[[verdict_rule]]` rows, so a tampered row
    # in the FILE `check-states` was actually invoked on fails `check-states`.
    out["verdict_rule_exhaustive"] = verify_verdict_table_exhaustive(doc)
    return out


def find_transition(doc: dict, machine_name: str, from_state: str, name: str):
    """Returns (to_state, error). error is None on success.

    Finding 15: this is a STRUCTURAL lookup only — (machine, from_state, name) -> to_state. It
    does NOT evaluate `guard` (a prose precondition in states.toml) or `by` (the actor role); a
    caller that needs "is this transition legal for THIS actor, right now" must check `by` and
    `guard` itself. `transition` never authorises anything on its own."""
    machine = (doc.get("machine") or {}).get(machine_name)
    if not isinstance(machine, dict):
        return None, f"no such machine: {machine_name!r}"
    for t in machine.get("transition") or []:
        if not isinstance(t, dict):
            continue
        if t.get("name") != name:
            continue
        froms = _normalize_from(t.get("from"))
        if from_state in froms:
            return t.get("to"), None
    return None, f"no transition named {name!r} from state {from_state!r} in machine {machine_name!r}"


# ---------------------------------------------------------------------------------------------
# impact — protocol.md §8
# ---------------------------------------------------------------------------------------------

def _new_package_record_lookup(new_package: dict | None) -> dict:
    """Finding 14: (claim_id, evidence_index) -> record, from `--new-package` — the ONLY basis
    this tool has for judging tool/semantics continuity (record identity has no other key)."""
    lookup: dict = {}
    if not isinstance(new_package, dict):
        return lookup
    for c in new_package.get("claim") or []:
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        for idx, e in enumerate(evidence_list(c)):
            lookup[(cid, idx)] = e
    return lookup


def classify_evidence_record(
    record: dict, item_path: str | None, changed_paths: set,
    new_record: dict | None = None, new_package_given: bool = False,
) -> tuple[str, str, list]:
    """§8 item 2. Returns (class, reason, changed_inputs). Impact is only ever invoked given a
    changed artifact state, so "subject changed" is always true here — an undeclared-input record
    is therefore always `possibly-invalidated`, never `still-applicable` (§8, "undeclared inputs
    are never treated as unchanged").

    Finding 14: `still-applicable` additionally requires EVERY declared input to carry a digest
    (a path list without digests can only prove change, never continuity) AND tool/semantics
    continuity, which can only be established by comparing against `--new-package`; without it,
    continuity is UNKNOWN and the record is `possibly-invalidated`, never `still-applicable`."""
    if item_path is not None and item_path in changed_paths:
        return "definitely-invalidated", "the claim's item path changed", [item_path]

    inputs = record.get("inputs")
    inputs = [i for i in inputs if isinstance(i, dict)] if isinstance(inputs, list) else None
    if not inputs:
        return "possibly-invalidated", "no declared inputs — scope unknown, subject changed", []

    changed_by_path = [i.get("path") for i in inputs if i.get("path") in changed_paths]
    if changed_by_path:
        return "definitely-invalidated", "a declared input changed (named in --changed)", changed_by_path

    undigested = [i.get("path") for i in inputs if not _nonempty(i.get("digest"))]
    if undigested:
        return (
            "possibly-invalidated",
            f"declared input(s) without a digest can only prove change, never continuity: {undigested}",
            [],
        )

    if not new_package_given:
        return (
            "possibly-invalidated",
            "every declared input has a digest and none changed, but tool/semantics continuity "
            "is UNKNOWN without --new-package (Finding 14)",
            [],
        )
    if new_record is None:
        return (
            "possibly-invalidated",
            "record no longer present at the same position in --new-package — continuity unknown",
            [],
        )

    # Finding 11 (§8 item 2): compare EACH declared input's digest between the OLD record and the
    # SAME record in --new-package — tool/semantics equality alone is not continuity. Previously
    # this only checked that --changed didn't name the path and that the OLD digest was present;
    # the NEW package's own digest for that input was never even read.
    new_inputs = new_record.get("inputs")
    new_inputs = [i for i in new_inputs if isinstance(i, dict)] if isinstance(new_inputs, list) else []
    new_by_path = {i.get("path"): i for i in new_inputs if _nonempty(i.get("path"))}
    old_paths = {i.get("path") for i in inputs}

    changed_digests = []
    missing_paths = []
    for i in inputs:
        p = i.get("path")
        new_i = new_by_path.get(p)
        if new_i is None or not _nonempty(new_i.get("digest")):
            missing_paths.append(p)
            continue
        if i.get("digest") != new_i.get("digest"):
            changed_digests.append(p)
    extra_new_paths = [p for p in new_by_path if p not in old_paths]

    if changed_digests:
        return (
            "definitely-invalidated",
            f"a declared input's digest changed between the old package and --new-package: {changed_digests}",
            changed_digests,
        )
    if missing_paths or extra_new_paths:
        return (
            "possibly-invalidated",
            f"input digest comparison incomplete — missing on either side of the old/new "
            f"package pair: {sorted(set(missing_paths) | set(extra_new_paths))} (Finding 11)",
            [],
        )
    if record.get("tool") != new_record.get("tool") or record.get("semantics") != new_record.get("semantics"):
        return "definitely-invalidated", "tool or semantics changed (per --new-package)", []

    return (
        "still-applicable",
        "every declared input has an unchanged digest between the old package and "
        "--new-package, and tool/semantics are unchanged",
        [],
    )


def compute_impact(
    decision: dict, contract: dict, package: dict, new_commit: str, changed_paths: set,
    new_package: dict | None = None,
):
    """Returns a dict: {stale, old_commit, new_commit, records: [...], unsupported_requirements: [...],
    events: [...]}."""
    old_commit = ((decision.get("binds") or {}).get("subject") or {}).get("commit")
    # Finding 14: "Any change to the subject state — a new commit OR a changed path at the same
    # commit (a dirty tree) — makes the decision stale." Previously `stale` ignored --changed
    # when the commit was unchanged.
    stale = (old_commit != new_commit) or bool(changed_paths)
    subject_changed = stale
    new_package_given = new_package is not None
    new_lookup = _new_package_record_lookup(new_package)

    claims_by_id = {
        c.get("id"): c for c in (package.get("claim") or []) if isinstance(c, dict) and _nonempty(c.get("id"))
    }
    req_by_id = requirement_by_id(contract)
    authority = (contract.get("acceptance") or {}).get("authority")
    stale_after_dur = (contract.get("acceptance") or {}).get("stale_after")
    required_by = None
    if is_iso8601_duration(stale_after_dur):
        required_by = (
            datetime.datetime.now(datetime.timezone.utc) + duration_to_timedelta(stale_after_dur)
        ).strftime("%Y-%m-%d")

    records: list[dict] = []
    unsupported_requirements: set[str] = set()
    invalidated_claims: dict[str, dict] = {}  # claim id -> {"cls": worst class seen, "rid": requirement id}

    dispositions = decision.get("disposition") or []
    for disp in dispositions:
        if not isinstance(disp, dict) or disp.get("status") != "satisfied":
            continue
        rid = disp.get("requirement")
        for cid in disp.get("basis") or []:
            claim = claims_by_id.get(cid)
            if claim is None:
                continue
            item_path = claim.get("item")
            for idx, record in enumerate(evidence_list(claim)):
                if not subject_changed:
                    continue
                new_record = new_lookup.get((cid, idx))
                cls, reason, changed_inputs = classify_evidence_record(
                    record, item_path, changed_paths, new_record, new_package_given,
                )
                records.append({
                    "evidence_id": f"{cid}#{idx}",
                    "requirement": rid,
                    "claim": cid,
                    "class": cls,
                    "reason": reason,
                    "changed_inputs": changed_inputs,
                })
                if cls in ("definitely-invalidated", "possibly-invalidated"):
                    unsupported_requirements.add(rid)
                    prev = invalidated_claims.get(cid)
                    if prev is None or prev["cls"] != "definitely-invalidated":
                        invalidated_claims[cid] = {"cls": cls, "rid": rid}

    events: list[dict] = []
    decision_id = (decision.get("document") or {}).get("id")
    batch_id = f"impact-{decision_id}-{(new_commit or '')[:12]}"

    for cid, info in sorted(invalidated_claims.items()):
        cls, rid = info["cls"], info["rid"]
        duty_id = f"OB-{decision_id}-{cid}"
        duty = {
            "id": duty_id,
            "natural_key": f"reverify:{decision_id}:{cid}",
            "scope": (contract.get("subject") or {}).get("name") or "unknown",
            "source": (package.get("spec") or {}).get("path") or "acceptance.toml",
            "source_revision": new_commit,
            "trigger": {"kind": "subject-changed", "from": old_commit, "to": new_commit},
            "action": "re-verify",
            "target": cid,
            "retrigger": "once",
            "duty_kind": "one-time",
            "required_by": required_by or "no stated deadline",
            # Finding 14: coverage is keyed by REQUIREMENT id, not claim id — the discharge
            # predicate must name what coverage() actually takes.
            "discharge_predicate": f"coverage({rid}) via a superseding package computes 'satisfied'",
            "authority": authority,
            "created_by": "acceptance_protocol.py impact",
            "created_at": now_utc_iso(),
        }
        for r in records:
            if r["claim"] == cid:
                r["obligation_id"] = duty_id
        events.append({
            "id": f"evt-{duty_id}-mint",
            "seq": 1,
            "kind": "minted",
            "recorded_at": now_utc_iso(),
            "actor": "acceptance_protocol.py impact",
            "authority_ref": authority,
            "batch_id": batch_id,
            "payload": {"duty": duty},
        })

    events.append({
        "id": f"evt-{decision_id}-stale",
        "seq": 1,
        "kind": "stale_detected",
        "recorded_at": now_utc_iso(),
        "actor": "acceptance_protocol.py impact",
        "authority_ref": authority,
        "batch_id": batch_id,
        "payload": {"context_hash_old": old_commit, "context_hash_new": new_commit},
    })

    return {
        "stale": stale,
        "old_commit": old_commit,
        "new_commit": new_commit,
        "records": records,
        "unsupported_requirements": sorted(unsupported_requirements),
        "events": events,
    }


# ---------------------------------------------------------------------------------------------
# render — protocol.md §10
# ---------------------------------------------------------------------------------------------

def render_markdown(
    contract: dict, package: dict, decision: dict | None,
    contract_path: Path, package_path: Path, decision_path: Path | None,
) -> str:
    cov = compute_coverage(contract, package, package_path)
    req_by_id = requirement_by_id(contract)
    claims_by_clause: dict[str, list[dict]] = {}
    for c in package.get("claim") or []:
        if isinstance(c, dict):
            claims_by_clause.setdefault(c.get("clause"), []).append(c)
    dispositions_by_req: dict[str, dict] = {}
    if decision is not None:
        for d in decision.get("disposition") or []:
            if isinstance(d, dict):
                dispositions_by_req[d.get("requirement")] = d
    conditions_by_id: dict[str, dict] = {}
    if decision is not None:
        for c in decision.get("condition") or []:
            if isinstance(c, dict) and _nonempty(c.get("id")):
                conditions_by_id[c["id"]] = c

    try:
        contract_hash = m11.digest_file("contract", contract_path)
    except OSError:
        contract_hash = "?"
    try:
        package_hash = m11.digest_file("manifest", package_path)
    except OSError:
        package_hash = "?"
    decision_hash = None
    if decision_path is not None:
        try:
            decision_hash = m11.digest_file("decision", decision_path)
        except OSError:
            decision_hash = "?"

    lines: list[str] = []
    lines.append(f"# Acceptance view — {(contract.get('document') or {}).get('id')}")
    lines.append("")
    lines.append(f"- contract: `{(contract.get('document') or {}).get('id')}` — `{contract_hash}`")
    lines.append(f"- package: `{(package.get('subject') or {}).get('name')}` — `{package_hash}`")
    phase = (contract.get("acceptance") or {}).get("phase") or "final"
    lines.append(f"- phase: `{phase}`")
    upstream_status = (package.get("spec") or {}).get("upstream_status")
    if _nonempty(upstream_status):
        lines.append(f"- spec upstream status: `{upstream_status}` (non-normative, never gating)")
    if decision is not None:
        doc_ = decision.get("document") or {}
        lines.append(f"- decision: `{doc_.get('id')}` — `{decision_hash}`")
        lines.append(f"- verdict: `{doc_.get('verdict')}`")
        lines.append(f"- provisional: `{doc_.get('provisional')}`")
        if doc_.get("merits") is False:
            lines.append(f"- merits: `false` — {doc_.get('reason')}")
        if _nonempty(doc_.get("recorded_by")):
            lines.append(f"- recorded_by: `{doc_.get('recorded_by')}`")
            derivation = decision.get("derivation") or {}
            if _nonempty(derivation.get("authority_act")):
                lines.append(f"- derivation: `{derivation.get('authority_act')}` — {derivation.get('rule')}")
    lines.append("")
    header = ["id", "statement", "mandatory", "floor", "producer claims", "computed coverage"]
    if decision is not None:
        header += ["disposition", "conditions"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))

    for rid in sorted(req_by_id):
        req = req_by_id[rid]
        kind = req.get("kind", "item")
        if kind == "cross-cutting":
            over = req.get("over")
            floor = f"cross-cutting over {over}, demands {req.get('demands')}"
        else:
            ev = req.get("evidence") or {}
            floor = (
                f"min_tier={ev.get('min_tier')}, weighted_required={ev.get('weighted_required', True)}, "
                f"control_required={ev.get('control_required')}, recipe_required={ev.get('recipe_required')}"
            )
        claim_cells = []
        for c in claims_by_clause.get(rid, []):
            claim_cells.append(
                f"`{c.get('id')}` grade={c.get('grade')} band={c.get('band')} "
                f"status={c.get('status')} weight={c.get('weight')}"
            )
        cov_r = cov["requirements"].get(rid, {})
        row = [
            f"`{rid}`",
            req.get("statement", "").replace("|", "\\|"),
            str(req.get("mandatory")),
            floor,
            "; ".join(claim_cells) or "(none)",
            cov_r.get("status", "?"),
        ]
        if decision is not None:
            disp = dispositions_by_req.get(rid)
            row.append(disp.get("status") if disp else "(no disposition)")
            cond_cells = []
            for cid in (disp.get("conditions") if disp else None) or []:
                c = conditions_by_id.get(cid)
                cond_cells.append(f"`{cid}`: {c.get('statement') if c else '?'}")
            row.append("; ".join(cond_cells) or "-")
        lines.append("| " + " | ".join(row) + " |")

    if decision is not None and decision.get("requirement_feedback"):
        lines.append("")
        lines.append("## Requirement feedback (§3.5) — for the next contract version")
        lines.append("")
        for fb in decision.get("requirement_feedback") or []:
            if not isinstance(fb, dict):
                continue
            lines.append(
                f"- `{fb.get('requirement')}` [{fb.get('kind')}]: {fb.get('statement')} "
                f"— proposed: {fb.get('proposed')}"
            )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------
# CLI verbs
# ---------------------------------------------------------------------------------------------

def _print_report(rep: Reporter, ok_word: str = "PASS") -> None:
    for line in rep.lines():
        print(line)
    if rep.ok():
        n = len(rep.warnings)
        suffix = f" ({n} warning{'s' if n != 1 else ''})" if n else ""
        print(f"{ok_word} {rep.path}{suffix}")
    elif not rep.errors and rep.unknowns:
        print(f"INDETERMINATE {rep.path} ({len(rep.unknowns)} unresolved finding(s))")
    else:
        print(f"FAIL {rep.path} ({len(rep.errors)} error{'s' if len(rep.errors) != 1 else ''})")


def cmd_check_contract(args) -> int:
    path = Path(args.contract)
    doc, err = load_toml(path)
    if err:
        print(f"ERROR {path}: {err}")
        print(f"FAIL {path} (1 error)")
        return 1
    rep = check_contract(doc)
    rep.path = str(path)
    # Finding 4 (§3.3): `--previous` is repeatable (newest-first: nearest predecessor first)
    # and/or `--previous-dir DIR` (each ancestor resolved by its own [document].id) — the WHOLE
    # chain is validated to its root, not merely the nearest predecessor.
    supersedes = (doc.get("document") or {}).get("supersedes")
    previous_list = getattr(args, "previous", None) or []
    previous_dir = getattr(args, "previous_dir", None)
    if supersedes:
        if not previous_list and not previous_dir:
            rep.error(
                f"[document].supersedes = {supersedes!r} but no --previous/--previous-dir was "
                f"given to validate the chain to its root (§3.3)"
            )
        else:
            rep.merge(check_contract_chain(doc, previous_list, previous_dir), prefix="[--previous chain] ")
    elif previous_list or previous_dir:
        rep.error("--previous/--previous-dir given but [document].supersedes is absent — nothing to validate against (§3.3)")
    if args.json:
        print(json.dumps({"path": str(path), "errors": rep.errors, "warnings": rep.warnings, "ok": rep.ok()}, indent=2))
    else:
        _print_report(rep)
    return 0 if rep.ok() else 1


def cmd_check_package(args) -> int:
    package_path = Path(args.package)
    contract_path = Path(args.contract)
    package, perr = load_toml(package_path)
    contract, cerr = load_toml(contract_path)
    if perr or cerr:
        for p, e in ((package_path, perr), (contract_path, cerr)):
            if e:
                print(f"ERROR {p}: {e}")
        print(f"FAIL {package_path} (usage)")
        return 1
    previous_contract_path = Path(args.previous_contract) if getattr(args, "previous_contract", None) else None
    previous_list = getattr(args, "previous", None) or []
    previous_dir = getattr(args, "previous_dir", None)
    rep, cov = check_package(
        package, contract, package_path, contract_path, args.strict, previous_contract_path,
        previous_paths=previous_list, previous_dir=previous_dir,
    )
    rep.path = str(package_path)
    if args.json:
        print(json.dumps({
            "path": str(package_path), "errors": rep.errors, "warnings": rep.warnings, "unknowns": rep.unknowns,
            "ok": rep.ok(), "coverage": _coverage_json(cov),
        }, indent=2))
    else:
        _print_report(rep)
        print_coverage_table(cov)
    return rep.exit_code()


def _coverage_json(cov: dict) -> dict:
    return {
        "profile_id": cov["profile_id"],
        "requirements": cov["requirements"],
        "summary": cov["summary"],
        "record_errors": cov["record_errors"],
        "warnings": cov["warnings"],
    }


def cmd_coverage(args) -> int:
    package_path = Path(args.package)
    contract_path = Path(args.contract)
    package, perr = load_toml(package_path)
    contract, cerr = load_toml(contract_path)
    if perr or cerr:
        for p, e in ((package_path, perr), (contract_path, cerr)):
            if e:
                print(f"ERROR {p}: {e}")
        return 1
    cov = compute_coverage(contract, package, package_path)
    if args.json:
        print(json.dumps(_coverage_json(cov), indent=2))
    else:
        print_coverage_table(cov)
    return 1 if cov["record_errors"] else 0


def cmd_decide(args) -> int:
    package_path = Path(args.package)
    contract_path = Path(args.contract)
    package, perr = load_toml(package_path)
    contract, cerr = load_toml(contract_path)
    if perr or cerr:
        for p, e in ((package_path, perr), (contract_path, cerr)):
            if e:
                print(f"ERROR {p}: {e}")
        return 2
    text = build_decision_skeleton(contract, package, package_path, contract_path, args.issuer, args.mode)
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"wrote decision skeleton to {args.out}")
    return 0


def cmd_check_decision(args) -> int:
    decision_path = Path(args.decision)
    contract_path = Path(args.contract)
    package_path = Path(args.package)
    decision, derr = load_toml(decision_path)
    contract, cerr = load_toml(contract_path)
    package, perr = load_toml(package_path)
    if derr or cerr or perr:
        for p, e in ((decision_path, derr), (contract_path, cerr), (package_path, perr)):
            if e:
                print(f"ERROR {p}: {e}")
        return 1
    previous_contract_path = Path(args.previous_contract) if getattr(args, "previous_contract", None) else None
    previous_list = getattr(args, "previous", None) or []
    previous_dir = getattr(args, "previous_dir", None)
    rep = check_decision(
        decision, contract, package, contract_path, package_path, previous_contract_path,
        previous_paths=previous_list, previous_dir=previous_dir, decision_path=decision_path,
    )
    rep.path = str(decision_path)

    effect_eligible = None
    effect_reason = None
    if getattr(args, "effect", False):
        now_date = args.now or today_utc_date()
        effect_eligible, effect_reason = check_decision_effect(
            decision, contract, rep, now_date, args.allow_conditions,
        )

    if args.json:
        out = {"path": str(decision_path), "errors": rep.errors, "warnings": rep.warnings, "unknowns": rep.unknowns, "ok": rep.ok()}
        if effect_eligible is not None:
            out["effect_eligible"] = effect_eligible
            out["effect_reason"] = effect_reason
        print(json.dumps(out, indent=2))
    else:
        _print_report(rep)
        if effect_eligible is not None:
            print(f"{'EFFECT-ELIGIBLE' if effect_eligible else 'EFFECT-INELIGIBLE'}: {effect_reason}")

    if rep.exit_code():
        return rep.exit_code()
    if effect_eligible is not None:
        return 0 if effect_eligible else 1
    return rep.exit_code()


def cmd_check_states(args) -> int:
    path = Path(args.states) if args.states else (_HERE.parent / "spec" / "states.toml")
    doc, err = load_toml(path)
    if err:
        print(f"ERROR {path}: {err}")
        return 1
    reps = check_states(doc)
    any_error = False
    for name in sorted(reps):
        rep = reps[name]
        for line in rep.lines():
            print(line)
        if rep.ok():
            print(f"PASS {rep.path}")
        else:
            print(f"FAIL {rep.path} ({len(rep.errors)} error{'s' if len(rep.errors) != 1 else ''})")
            any_error = True
    return 1 if any_error else 0


def cmd_transition(args) -> int:
    path = Path(args.states) if args.states else (_HERE.parent / "spec" / "states.toml")
    doc, err = load_toml(path)
    if err:
        print(f"ERROR {path}: {err}")
        return 2
    to, err = find_transition(doc, args.machine, args.from_state, args.name)
    if err:
        print(f"ERROR: {err}")
        return 1
    print(to)
    return 0


def cmd_impact(args) -> int:
    decision_path = Path(args.decision)
    contract_path = Path(args.contract)
    package_path = Path(args.package)
    decision, derr = load_toml(decision_path)
    contract, cerr = load_toml(contract_path)
    package, perr = load_toml(package_path)
    if derr or cerr or perr:
        for p, e in ((decision_path, derr), (contract_path, cerr), (package_path, perr)):
            if e:
                print(f"ERROR {p}: {e}")
        return 2

    changed_paths: set[str] = set()
    if args.changed:
        changed_paths.update(args.changed)
    if args.changed_file:
        for line in Path(args.changed_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                changed_paths.add(line)

    new_package = None
    if getattr(args, "new_package", None):
        new_package_path = Path(args.new_package)
        new_package, nperr = load_toml(new_package_path)
        if nperr:
            print(f"ERROR {new_package_path}: {nperr}")
            return 2

    result = compute_impact(decision, contract, package, args.new_commit, changed_paths, new_package)

    if result["stale"]:
        print(f"decision {(decision.get('document') or {}).get('id')} -> stale "
              f"(subject commit {result['old_commit']!r} -> {result['new_commit']!r}, or a "
              f"changed path at the same commit) (P7, Finding 14)")
    else:
        print(f"decision {(decision.get('document') or {}).get('id')}: subject commit unchanged "
              f"({result['new_commit']!r})")

    print("classification:")
    for r in result["records"]:
        print(
            f"  {r['evidence_id']} (requirement {r['requirement']}, claim {r['claim']}): "
            f"{r['class']} — {r['reason']}"
            + (f" changed_inputs={r['changed_inputs']}" if r["changed_inputs"] else "")
        )
    print(f"requirements whose disposition is now unsupported: {result['unsupported_requirements']}")

    if args.out_events:
        with open(args.out_events, "w", encoding="utf-8") as f:
            for ev in result["events"]:
                f.write(json.dumps(ev) + "\n")
        print(f"wrote {len(result['events'])} event(s) to {args.out_events}")

    return 0


def cmd_render(args) -> int:
    contract_path = Path(args.contract)
    package_path = Path(args.package)
    contract, cerr = load_toml(contract_path)
    package, perr = load_toml(package_path)
    decision = None
    decision_path = None
    if args.decision:
        decision_path = Path(args.decision)
        decision, derr = load_toml(decision_path)
        if derr:
            print(f"ERROR {decision_path}: {derr}")
            return 2
    if cerr or perr:
        for p, e in ((contract_path, cerr), (package_path, perr)):
            if e:
                print(f"ERROR {p}: {e}")
        return 2
    text = render_markdown(contract, package, decision, contract_path, package_path, decision_path)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


def cmd_check_amendment(args) -> int:
    amend_path = Path(args.amendment)
    contract_path = Path(args.contract)
    amendment, aerr = load_toml(amend_path)
    base, berr = load_toml(contract_path)
    if aerr or berr:
        for p, e in ((amend_path, aerr), (contract_path, berr)):
            if e:
                print(f"ERROR {p}: {e}")
        return 1
    rep = check_amendment(amendment, base, contract_path)
    rep.path = str(amend_path)
    if args.json:
        print(json.dumps({"path": str(amend_path), "errors": rep.errors, "warnings": rep.warnings, "ok": rep.ok()}, indent=2))
    else:
        _print_report(rep)
    return 0 if rep.ok() else 1


def cmd_apply_amendment(args) -> int:
    """Finding 6: validity (does the amendment's own [binds] recompute over SOME version of the
    contract, structurally self-consistent?) is checked by `check_amendment` — that is a question
    about the DOCUMENT. Applicability (is it usable RIGHT NOW?) is a separate question checked
    HERE: status must be `proposed` (a `rejected`/`stale`/`accepted`/`superseded` amendment is
    NEVER applied, whatever its `[binds]` say), and the amendment's bound hash must equal the hash
    of `--current` (a caller-chosen file — defaults to `--contract` — useful to prove a base is
    stale before touching any files, but NOT by itself the atomicity mechanism §3.6 rule 1
    requires: "a stateless 'compare against a file the caller chose' is not this rule").

    §3.6 rule 1 (Finding 6): the consumer keeps a CURRENT POINTER — a small record
    (`--pointer PATH`, default `<contract dir>/acceptance-contract.current`, `{id, hash}`) that
    NAMES the current version, independent of any file the caller happens to pass. This command
    reads it (creating it from `--contract` on first use, and saying so), refuses UNLESS the
    amendment's `[binds].contract` equals it, and — after the successor is fully built and
    written — advances the pointer to the successor's own {id, hash} via `os.replace` (an atomic
    rename on POSIX and Windows). Two applications against the same base cannot both succeed: the
    first one to write the successor also moves the pointer, so the second one's pointer-read
    finds a different id/hash and is refused with "base is not current (pointer moved)"."""
    amend_path = Path(args.amendment)
    contract_path = Path(args.contract)
    amendment, aerr = load_toml(amend_path)
    base, berr = load_toml(contract_path)
    if aerr or berr:
        for p, e in ((amend_path, aerr), (contract_path, berr)):
            if e:
                print(f"ERROR {p}: {e}")
        return 2

    # Finding 11: §3.6 rule 2 names the AUTHORITY as who accepts (P5), not the consumer party.
    authority_name = (base.get("acceptance") or {}).get("authority")
    if not args.dry_run:
        if not args.out:
            print("usage error: --out FILE is required unless --dry-run is given", file=sys.stderr)
            return 2
        if not args.accept_by:
            print("usage error: --accept-by NAME is required unless --dry-run is given", file=sys.stderr)
            return 2
        if args.accept_by != authority_name:
            print(
                f"usage error: --accept-by {args.accept_by!r} does not equal the base contract's "
                f"[acceptance].authority ({authority_name!r}) — only the authority accepts "
                f"(§3.6 rule 2, P5)",
                file=sys.stderr,
            )
            return 2

    rep = check_amendment(amendment, base, contract_path)
    _print_report(rep, ok_word="STRUCTURE OK (valid)")
    if not rep.ok():
        return 1

    # Finding 6 — APPLICABILITY (distinct from the validity just checked above):
    amend_status = ((amendment.get("document") or {}).get("status"))
    if amend_status != "proposed":
        print(
            f"apply-amendment REFUSED: [document].status is {amend_status!r}, not 'proposed' — "
            f"a rejected/stale/accepted/superseded amendment is never applied (§3.6 rule 1, Finding 6)"
        )
        return 1

    current_path = Path(args.current) if getattr(args, "current", None) else contract_path
    bc = (amendment.get("binds") or {}).get("contract") or {}
    try:
        current_hash = m11.digest_file("contract", current_path)
    except OSError as e:
        print(f"ERROR: could not recompute --current contract hash: {e}")
        return 1
    if bc.get("hash") != current_hash:
        print(
            f"apply-amendment REFUSED: base not current — [binds].contract.hash "
            f"({bc.get('hash')!r}) does not equal the recomputed hash of --current "
            f"({current_path}) ({current_hash!r}). Application atomically verifies the "
            f"consumer's CURRENT contract hash; validating a historical base is insufficient "
            f"(§3.6 rule 1, Finding 6)"
        )
        return 1

    # Finding 6 (§3.6 rule 1) — the CURRENT POINTER, the atomicity mechanism: created from
    # --contract on first use, then read-refuse-write-advance on every application after that.
    pointer_path = Path(args.pointer) if getattr(args, "pointer", None) else (contract_path.parent / "acceptance-contract.current")
    if not pointer_path.exists():
        base_id = (base.get("document") or {}).get("id")
        try:
            pointer_path.write_text(
                json.dumps({"id": base_id, "hash": current_hash}, indent=2) + "\n", encoding="utf-8",
            )
        except OSError as e:
            print(f"ERROR: could not create --pointer {pointer_path}: {e}")
            return 1
        print(f"created current-pointer {pointer_path} from --contract (first use, §3.6 rule 1)")
        pointer_doc = {"id": base_id, "hash": current_hash}
    else:
        try:
            pointer_doc = json.loads(pointer_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"ERROR: could not read --pointer {pointer_path}: {e}")
            return 1
    if not isinstance(pointer_doc, dict) or bc.get("id") != pointer_doc.get("id") or bc.get("hash") != pointer_doc.get("hash"):
        print(
            f"apply-amendment REFUSED: base is not current (pointer moved) — the current-pointer "
            f"{pointer_path} names {pointer_doc!r}, but the amendment's [binds].contract names "
            f"{bc!r}. Two applications against the same base cannot both succeed: rebase against "
            f"the successor (§3.6 rule 1, Finding 6)"
        )
        return 1

    new_contract, build_errors = apply_amendment_build(amendment, base, args.id, authority_name)
    if build_errors:
        for e in build_errors:
            print(f"ERROR: {e}")
        return 1

    # Finding 11: the successor is FULLY validated (check-contract, not just tightening) before
    # it is ever written.
    full_rep = check_contract(new_contract)
    for line in full_rep.lines():
        print(line)
    if not full_rep.ok():
        print("apply-amendment REFUSED: the successor fails check-contract (§3.6 rule 2, Finding 11)")
        return 1

    tight_rep = check_contract_tightening(new_contract, base)
    for line in tight_rep.lines():
        print(line)
    if not tight_rep.ok():
        print("apply-amendment REFUSED: the successor fails check-contract --previous (§3.6 rule 2)")
        return 1

    text = _render_contract_toml(new_contract)

    # Validating the IN-MEMORY successor is not
    # enough — a lossy renderer can drop a field the in-memory check saw and still pass, because
    # it never re-checks what was actually WRITTEN. Re-parse the rendered text and re-run the
    # SAME two checks against the reparsed document before issuance. This catches a rendered
    # successor that fails to parse, fails check-contract, or fails the tightening rule; it does NOT
    # by itself catch a dropped OPTIONAL field that leaves a still-valid document — field
    # preservation is asserted by the round-trip fixtures (cv2-1-*) and their mutation entries.
    try:
        reparsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        print(f"apply-amendment REFUSED: the rendered successor is not valid TOML: {e} "
              f"(§3.6 rule 2 — the tool must never issue a document it cannot itself re-read)")
        return 1
    reparsed_rep = check_contract(reparsed)
    for line in reparsed_rep.lines():
        print(line)
    if not reparsed_rep.ok():
        print("apply-amendment REFUSED: the RENDERED successor fails check-contract on re-parse "
              "— the renderer dropped or corrupted a field the in-memory successor carried "
              "(§3.6 rule 2, External review finding 1)")
        return 1
    reparsed_tight_rep = check_contract_tightening(reparsed, base)
    for line in reparsed_tight_rep.lines():
        print(line)
    if not reparsed_tight_rep.ok():
        print("apply-amendment REFUSED: the RENDERED successor fails check-contract --previous "
              "on re-parse — the renderer dropped or corrupted a field the in-memory successor "
              "carried (§3.6 rule 2, External review finding 1)")
        return 1

    if args.dry_run:
        print(text)
        # Finding 6: a dry run never writes the successor, so it must never move the pointer
        # either — "Application is atomic per base" and a dry run is not an application.
    else:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
        # Finding 6 (§3.6 rule 1): "writes the successor, and advances the pointer... in that
        # order" — write first (already done above), THEN advance the pointer atomically
        # (os.replace: write to a temp file in the SAME directory, then rename over the pointer).
        new_hash = m11.digest_bytes("contract", text.encode("utf-8"))
        new_id = new_contract.get("document", {}).get("id")
        tmp_fd_path = pointer_path.parent / f".{pointer_path.name}.tmp-{os.getpid()}"
        tmp_fd_path.write_text(json.dumps({"id": new_id, "hash": new_hash}, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_fd_path, pointer_path)
        print(f"advanced current-pointer {pointer_path} -> {new_id!r} (§3.6 rule 1)")
    return 0


def cmd_amend(args) -> int:
    decision_path = Path(args.from_decision)
    contract_path = Path(args.contract)
    decision, derr = load_toml(decision_path)
    contract, cerr = load_toml(contract_path)
    if derr or cerr:
        for p, e in ((decision_path, derr), (contract_path, cerr)):
            if e:
                print(f"ERROR {p}: {e}")
        return 2
    amend_doc = build_amendment_from_decision(decision, contract, contract_path)
    text = _render_amendment_toml(amend_doc)
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"wrote amendment skeleton to {args.out}")
    return 0


# ---------------------------------------------------------------------------------------------
# `project-brief` / `assemble-package` — the worker-brief adapter's two sections. Two mechanical
# projections: a contract projects DOWN into an existing `worker-brief/v1`
# shape (no new brief format — §1); a worker's report assembles UP into a protocol package (§2).
# `fill.toml` is the ONE surface a worker hand-types (statements, grade proposal, bounds text,
# watched-fail narrative, deviation text, and an explicit weight DOWNGRADE only — §2's own
# invariant: "nothing else in the package is hand-typed").
# ---------------------------------------------------------------------------------------------

class AssembleError(Exception):
    """A structural problem in the brief/report/fill inputs that `assemble-package` refuses to
    paper over — the caller sees a plain message, not a stack trace, on the CLI path."""


# --- a small, purpose-built YAML subset --------------------------------------------------------
# window-brief/v1 is flat top-level `key: value`
# pairs, where a value is a JSON-quoted scalar, a literal block scalar (`key: |` + 2-space-indented
# lines), or a list of JSON-quoted scalars (`key:` + `  - "..."` lines). This tool reads and writes
# ONLY that shape — not a general YAML parser — because it both writes every brief it will ever
# need to read back (project-brief -> assemble-package) and the shape itself is small and fixed.

_BRIEF_FIELD_ORDER = [
    "schema", "title", "prepared", "provenance", "goal", "scope", "plan", "done_criteria",
    "oracle", "decisions_collected", "allowed_writes", "status", "note",
]


def render_window_brief_yaml(fields: dict) -> str:
    lines: list[str] = []
    for key in _BRIEF_FIELD_ORDER:
        if key not in fields:
            continue
        v = fields[key]
        if isinstance(v, list):
            lines.append(f"{key}:")
            for item in v:
                lines.append(f"  - {json.dumps(item)}")
        elif isinstance(v, str) and "\n" in v:
            lines.append(f"{key}: |")
            for l in v.split("\n"):
                lines.append("  " + l if l else "")
        else:
            lines.append(f"{key}: {json.dumps(v)}")
    return "\n".join(lines) + "\n"


_YAML_TOP_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(.*)$")


def parse_window_brief_yaml(text: str) -> dict:
    lines = text.split("\n")
    i, n = 0, len(lines)
    out: dict = {}
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = _YAML_TOP_KEY_RE.match(line)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        if rest == "|":
            i += 1
            block: list[str] = []
            while i < n and (lines[i].startswith("  ") or lines[i] == ""):
                block.append(lines[i][2:] if lines[i].startswith("  ") else "")
                i += 1
            out[key] = "\n".join(block)
        elif rest == "":
            i += 1
            items: list[str] = []
            while i < n and lines[i].startswith("  - "):
                raw = lines[i][4:]
                items.append(json.loads(raw) if raw.startswith('"') else raw)
                i += 1
            out[key] = items
        else:
            out[key] = json.loads(rest) if rest.startswith('"') else rest
            i += 1
    return out


# --- project-brief (contract -> brief, worker-brief.md §1) --------------------------------------

def resolve_recipe(contract: dict, requirement: dict, profile: dict | None) -> tuple[dict | None, str]:
    """worker-brief.md §1 `done_criteria` source order: (1) the contract's own
    `[requirement.evidence.recipe]`, the consumer's mechanical source; (2) the profile's recipe
    carrier for the requirement's pattern (a template filled with the subject's paths — see
    `profiles.rust_recipe_carrier`'s documented gap: no profile implements one yet, so this tier
    never fires today); (3) `worker-proposed` — the brief says so and the worker's `fill.toml`
    must supply {command, expect}. `recipe_required` (a bare boolean) never projects a command by
    itself, per §1's own text."""
    ev = requirement.get("evidence") or {}
    recipe = ev.get("recipe")
    if isinstance(recipe, dict) and _nonempty(recipe.get("command")) and _nonempty(recipe.get("expect")):
        return recipe, "contract"
    carrier = (profile or {}).get("recipe_carrier")
    if callable(carrier):
        got = carrier(requirement)
        if isinstance(got, dict) and _nonempty(got.get("command")) and _nonempty(got.get("expect")):
            return got, "profile"
    return None, "worker-proposed"


def _glob_root(spec: str) -> str:
    """The common filesystem root of a (possibly globbed) allowed-writes spec, e.g.
    `"iban-check/**"` -> `"iban-check"`. Used ONLY as a heuristic for which subtree's dirtiness to
    check (verification/code/rust.md §1, illustrative; profile vocabulary) — a generic stand-in for a real
    pathspec parser this adapter does not need to be."""
    spec = spec.split(",")[0].strip()
    for suffix in ("/**", "/*", "*"):
        if spec.endswith(suffix):
            return spec[: -len(suffix)]
    return spec


def _load_touch_list(value: str | None) -> tuple[str, dict[str, str]]:
    """`--allowed-writes`: either a path to a small TOML file with `writes` (str, the orchestrator's
    glob) and `[items]` (requirement id -> the touch-list's item pointer for that requirement — the
    §2 mechanical source for `[[claim]].item`), or a literal write-scope string with no touch-list
    (every requirement's item then falls back to a generic subject-based pointer, and a WARNING is
    the caller's job to surface — `cmd_project_brief` does)."""
    if not value:
        return "", {}
    p = Path(value)
    if p.is_file():
        doc = tomllib.loads(p.read_text(encoding="utf-8"))
        writes = doc.get("writes")
        writes_str = writes if isinstance(writes, str) else ", ".join(writes or [])
        items = {k: v for k, v in (doc.get("items") or {}).items() if isinstance(v, str)}
        return writes_str, items
    return value, {}


def _brief_scope_text(subject: dict, writes_str: str, items: dict[str, str]) -> str:
    lines = [
        f"subject: {subject.get('name', '')} ({subject.get('kind', '')})",
        f"allowed_writes: {writes_str or '(unspecified)'}",
    ]
    if items:
        lines.append("touch_list:")
        for rid in sorted(items, key=lambda r: (len(r), r)):
            lines.append(f"  {rid}: {items[rid]}")
    return "\n".join(lines)


_TOUCH_LIST_ITEM_RE = re.compile(r"^  (\S+): (.*)$")


def touch_list_from_scope(scope_text: str) -> dict[str, str]:
    items: dict[str, str] = {}
    in_list = False
    for line in (scope_text or "").split("\n"):
        if line.strip() == "touch_list:":
            in_list = True
            continue
        if not in_list:
            continue
        m = _TOUCH_LIST_ITEM_RE.match(line)
        if m:
            items[m.group(1)] = m.group(2)
        else:
            break
    return items


def _requirement_map(contract: dict) -> dict[str, dict]:
    return {
        r["id"]: r for r in (contract.get("requirement") or [])
        if isinstance(r, dict) and _nonempty(r.get("id"))
    }


def _requirement_plan_line(req: dict) -> str:
    rid = req["id"]
    if req.get("kind") == "cross-cutting":
        over = ", ".join(req.get("over") or [])
        return f"{rid} (cross-cutting, over {over}): {req.get('statement', '')}"
    return f"{rid}: {req.get('statement', '')}"


def _requirement_done_criteria_line(req: dict, contract: dict, profile: dict | None) -> tuple[str, str]:
    """Returns (line, recipe_source)."""
    rid = req["id"]
    if req.get("kind") == "cross-cutting":
        over = ", ".join(req.get("over") or [])
        fields = (req.get("demands") or {}).get("fields") or {}
        demand = "; ".join(f"{k} = {v!r}" for k, v in fields.items()) or "(no field demand declared)"
        return f"{rid} (cross-cutting, over {over}): demand {demand}", "cross-cutting"
    recipe, source = resolve_recipe(contract, req, profile)
    if source == "worker-proposed":
        return f"{rid}: recipe proposed by worker (fill.toml [[claim]] requirement={rid!r} [claim.recipe])", source
    return f"{rid}: `{recipe['command']}` -> expect: {recipe['expect']!r} (source: {source})", source


def build_brief_fields(
    contract: dict, contract_path: Path, allowed_writes_value: str | None, profile: dict | None,
) -> tuple[dict, list[str]]:
    """worker-brief.md §1's projection, field by field. Returns (fields, warnings)."""
    warnings: list[str] = []
    document = contract.get("document") or {}
    subject = contract.get("subject") or {}
    reqs = contract.get("requirement") or []

    writes_str, touch_items = _load_touch_list(allowed_writes_value)
    if not touch_items:
        warnings.append(
            "no touch-list supplied via --allowed-writes (a TOML file with [items] per "
            "requirement id) — every requirement's `item` falls back to a generic pointer"
        )

    plan_lines = [_requirement_plan_line(r) for r in reqs if isinstance(r, dict) and _nonempty(r.get("id"))]
    done_lines: list[str] = []
    oracle_lines: list[str] = []
    for r in reqs:
        if not isinstance(r, dict) or not _nonempty(r.get("id")):
            continue
        line, source = _requirement_done_criteria_line(r, contract, profile)
        done_lines.append(line)
        if source in ("contract", "profile"):
            recipe, _ = resolve_recipe(contract, r, profile)
            oracle_lines.append(f"{r['id']}: {recipe['command']}")
    oracle_lines.append(
        "assemble-package BRIEF.yaml REPORT_DIR --contract "
        f"{contract_path.name} --out acceptance.toml --fill fill.toml"
    )
    oracle_lines.append("python3 tools/check_acceptance.py --strict --strict-weight acceptance.toml")
    oracle_lines.append(
        f"python3 protocol_acceptance/tools/acceptance_protocol.py check-package acceptance.toml "
        f"--contract {contract_path.name} --strict"
    )

    decisions = [f"phase: {(contract.get('acceptance') or {}).get('phase', 'unknown')}"]
    for r in reqs:
        if isinstance(r, dict) and r.get("firmness") == "draft":
            decisions.append(
                f"{r['id']} is draft — the worker may propose requirement-defect deviations on it"
            )

    issued_by = document.get("issued_by")
    status_ok = document.get("status") in ("issued", "ratified")
    provenance = "owner-ruled" if (issued_by == "consumer" and status_ok) else "owner-ruled"
    if not (issued_by == "consumer" and status_ok):
        warnings.append(
            f"contract [document].status={document.get('status')!r}/issued_by={issued_by!r} is "
            "not (consumer, issued-or-ratified) — worker-brief.md §1's 'iff' does not literally "
            "hold; provenance is still recorded as owner-ruled (the brief is a machine projection, "
            "never owner-verbatim), but the caller should confirm this contract is fit to project"
        )

    fields = {
        "schema": "worker-brief/v1",
        "title": f"contract {document.get('id', '?')} -> brief ({subject.get('name', '?')})",
        "prepared": today_utc_date(),
        "provenance": provenance,
        "goal": (subject.get("description") or "").split(". ")[0].rstrip(".") + ".",
        "scope": _brief_scope_text(subject, writes_str, touch_items),
        "plan": "\n".join(plan_lines),
        "done_criteria": "\n".join(done_lines),
        "oracle": "\n".join(oracle_lines),
        "decisions_collected": decisions,
        "allowed_writes": writes_str or "(unspecified — orchestrator must supply --allowed-writes)",
        "status": "ready",
        "note": (
            f"generated by acceptance_protocol.py project-brief from {contract_path.name} — "
            "DO NOT HAND-EDIT, re-run to regenerate. Deliberately OMITS floors, hashes, the "
            "authority, disposition vocabulary and lifecycle (worker-brief.md §1)."
        ),
    }
    return fields, warnings


def _token_count(text: str) -> int:
    return len(text.split())


def cmd_project_brief(args) -> int:
    contract_path = Path(args.contract)
    contract, cerr = load_toml(contract_path)
    if cerr:
        print(f"ERROR {contract_path}: {cerr}")
        return 2
    profile_id = (contract.get("subject") or {}).get("profile")
    if not _nonempty(profile_id):
        print(f"ERROR {contract_path}: [subject].profile must be a nonempty string (§3.1 rule "
              f"7) — no compatibility default is assumed")
        return 2
    profile = PROFILES.get(profile_id)

    fields, warnings = build_brief_fields(contract, contract_path, args.allowed_writes, profile)
    brief_text = render_window_brief_yaml(fields)
    Path(args.out).write_text(brief_text, encoding="utf-8")

    contract_text = contract_path.read_text(encoding="utf-8")
    stats = {
        "lines_contract": len(contract_text.splitlines()),
        "lines_brief": len(brief_text.splitlines()),
        "tokens_contract": _token_count(contract_text),
        "tokens_brief": _token_count(brief_text),
    }
    ratio_lines = stats["lines_brief"] / stats["lines_contract"] if stats["lines_contract"] else 0.0
    ratio_tokens = stats["tokens_brief"] / stats["tokens_contract"] if stats["tokens_contract"] else 0.0
    print(
        f"[project-brief] lines: contract={stats['lines_contract']} brief={stats['lines_brief']} "
        f"(brief is {ratio_lines:.0%} of contract); "
        f"tokens (whitespace-split, an approximation): contract={stats['tokens_contract']} "
        f"brief={stats['tokens_brief']} (brief is {ratio_tokens:.0%} of contract)",
        file=sys.stderr,
    )
    for w in warnings:
        print(f"[project-brief] WARNING: {w}", file=sys.stderr)
    if args.stats:
        print(json.dumps(stats, indent=2))
    print(f"wrote {args.out}")
    return 0


# --- assemble-package (worker report -> package, worker-brief.md §2) ----------------------------

def _parse_transcript_sections(text: str) -> list[tuple[str, str]]:
    """Splits a captured transcript on its `$ <command>` marker lines into
    `[(command, output), ...]`, in order. The LAST section is the real recipe's own run; any
    earlier sections are `--version` probes captured in the SAME file (worker-brief.md §2:
    "the tool's `--version` line captured in the transcript")."""
    sections: list[tuple[str, str]] = []
    cur_cmd: str | None = None
    cur_lines: list[str] = []
    for line in text.split("\n"):
        if line.startswith("$ "):
            if cur_cmd is not None:
                sections.append((cur_cmd, "\n".join(cur_lines)))
            cur_cmd = line[2:]
            cur_lines = []
        else:
            cur_lines.append(line)
    if cur_cmd is not None:
        sections.append((cur_cmd, "\n".join(cur_lines)))
    return sections


def _load_run_transcript(report_dir: Path, run: dict) -> tuple[str, dict[str, str]]:
    transcript_rel = run.get("transcript")
    if not _nonempty(transcript_rel):
        raise AssembleError(f"run {run.get('id')!r}: manifest entry has no 'transcript'")
    path = report_dir / transcript_rel
    if not path.is_file():
        raise AssembleError(f"run {run.get('id')!r}: transcript not found: {path}")
    sections = _parse_transcript_sections(path.read_text(encoding="utf-8"))
    if not sections:
        raise AssembleError(
            f"run {run.get('id')!r}: transcript {transcript_rel} has no '$ <command>' marker — "
            "cannot mechanically separate tool-identity probes from the real run"
        )
    real_cmd, real_out = sections[-1]
    command = run.get("command") or ""
    if " ".join(real_cmd.split()) != " ".join(command.split()):
        raise AssembleError(
            f"run {run.get('id')!r}: transcript's final command {real_cmd!r} does not match the "
            f"manifest's declared command {command!r}"
        )
    probes = {" ".join(c.split()): o.strip() for c, o in sections[:-1]}
    return real_out, probes


def _git(args_: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args_], cwd=str(cwd), capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def _pq(v) -> str:
    """Quotes a value as a single-line TOML basic string/bool/int (mirrors gen_package.py's `q`,
    kept in one place now that a second caller exists)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = str(v)
    out = []
    for c in s:
        if c == "\\":
            out.append("\\\\")
        elif c == '"':
            out.append('\\"')
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        elif c == "\r":
            out.append("\\r")
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


def _kv_block(pairs: list[tuple[str, str]]) -> list[str]:
    """Renders `key = value` lines, `=`-aligned to the widest key IN THIS BLOCK — the same
    hand-alignment convention this example's generator used, computed instead of eyeballed. Every
    value must already be a fully-formatted TOML scalar STRING (see `_pq`); `None` values are
    OMITTED (an absent field, not a written null)."""
    present = [(k, v) for k, v in pairs if v is not None]
    if not present:
        return []
    width = max(len(k) for k, _ in present)
    return [f"{k.ljust(width)} = {v}" for k, v in present]


def _render_package(model: dict) -> str:
    lines: list[str] = []
    lines.append(model["header_comment"].rstrip("\n"))
    lines.append("")
    lines.append("")
    lines.append("[format]")
    lines += [l for l in _kv_block([
        ("id", _pq(model["format"]["id"])),
        ("protocol", _pq(model["format"]["protocol"])),
        ("profile", _pq(model["format"]["profile"])),
    ])]
    lines.append("")
    lines.append("[subject]")
    lines += _kv_block([
        ("name", _pq(model["subject"]["name"])),
        ("kind", _pq(model["subject"]["kind"])),
        ("commit", _pq(model["subject"]["commit"])),
        ("dirty", _pq(model["subject"]["dirty"])),
    ])
    lines.append("")
    lines.append("[contract]")
    lines += _kv_block([
        ("id", _pq(model["contract"]["id"])),
        ("hash", _pq(model["contract"]["hash"])),
        ("requirements_total", _pq(model["contract"]["requirements_total"])),
    ])
    lines.append("")
    lines.append("[spec]")
    lines += _kv_block([
        ("path", _pq(model["spec"]["path"])),
        ("version", _pq(model["spec"]["version"])),
        ("axis", _pq(model["spec"]["axis"])),
    ])
    lines.append("")
    lines.append("[coverage]")
    lines += _kv_block([
        ("clauses_total", _pq(model["coverage"]["clauses_total"])),
        ("claims_total", _pq(model["coverage"]["claims_total"])),
    ])
    lines.append("")

    for claim in model["claims"]:
        lines.append("# " + "=" * 75)
        lines.append(f"# {claim['id']} -- {claim['clause']}: {claim.get('heading', '')}")
        lines.append("# " + "=" * 75)
        lines.append("[[claim]]")
        top_pairs = [
            ("id", _pq(claim["id"])),
            ("clause", _pq(claim["clause"])),
            ("item", _pq(claim["item"])),
            ("statement", _pq(claim["statement"])),
        ]
        if claim.get("band"):
            top_pairs.append(("band", _pq(claim["band"])))
        top_pairs.append(("status", _pq(claim["status"])))
        if claim.get("weight"):
            top_pairs.append(("weight", _pq(claim["weight"])))
        if claim.get("grade"):
            top_pairs.append(("grade", _pq(claim["grade"])))
        if claim.get("clause_source"):
            top_pairs.append(("clause_source", _pq(claim["clause_source"])))
        if claim.get("bounds"):
            top_pairs.append(("bounds", _pq(claim["bounds"])))
        top_pairs.append(("captured_at_commit", _pq(claim["captured_at_commit"])))
        lines += _kv_block(top_pairs)
        if claim.get("weight_omitted_comment"):
            lines.append(f"# {claim['weight_omitted_comment']}")
        lines.append("")

        sv = claim.get("self_verify")
        if sv:
            lines.append("  [claim.self_verify]")
            for l in _kv_block([("command", _pq(sv["command"])), ("expect", _pq(sv["expect"]))]):
                lines.append("  " + l)
            lines.append("")
            wf = sv.get("watched_fail")
            if wf:
                lines.append("    [claim.self_verify.watched_fail]")
                for l in _kv_block([
                    ("of_command", _pq(wf["of_command"])), ("perturbed", _pq(wf["perturbed"])),
                    ("observed", _pq(wf["observed"])), ("date", _pq(wf["date"])),
                ]):
                    lines.append("    " + l)
                lines.append("")

        for ev in claim.get("evidence", []):
            lines.append("  [[claim.evidence]]")
            ev_pairs = [
                ("kind", _pq(ev["kind"])), ("family", _pq(ev["family"])), ("method", _pq(ev["method"])),
                ("epistemic_tier", _pq(ev["epistemic_tier"])),
            ]
            if ev.get("ref"):
                ev_pairs.append(("ref", _pq(ev["ref"])))
            ev_pairs.append(("result", _pq(ev["result"])))
            ev_pairs.append(("tool", _pq(ev["tool"])))
            if ev.get("bounds"):
                ev_pairs.append(("bounds", _pq(ev["bounds"])))
            if ev.get("semantics") is not None:
                ev_pairs.append(("semantics", _pq(ev["semantics"])))
            if ev.get("cases") is not None:
                ev_pairs.append(("cases", _pq(ev["cases"])))
            if ev.get("generator"):
                ev_pairs.append(("generator", _pq(ev["generator"])))
            ev_pairs.append(("record", _pq(ev["record"])))
            ev_pairs.append(("record_hash", _pq(ev["record_hash"])))
            ev_pairs.append(("captured_at_commit", _pq(ev["captured_at_commit"])))
            for l in _kv_block(ev_pairs):
                lines.append("  " + l)
            for path, digest in ev.get("inputs", []):
                lines.append("    [[claim.evidence.inputs]]")
                for l in _kv_block([("path", _pq(path)), ("digest", _pq(digest))]):
                    lines.append("    " + l)
            if ev.get("control"):
                lines.append("")
                lines.append("    [claim.evidence.control]")
                c = ev["control"]
                for l in _kv_block([
                    ("kind", _pq(c["kind"])), ("expectation", _pq(c["expectation"])),
                    ("observed", _pq(c["observed"])), ("of_claim", _pq(c["of_claim"])),
                ]):
                    lines.append("    " + l)
            lines.append("")
        lines.append("")

    for dev in model.get("deviations", []):
        lines.append("# " + "=" * 75)
        lines.append("[[deviation]]")
        pairs = [(k, _pq(dev[k]))
                 for k in ("requirement", "kind", "statement", "cause", "impact", "remedy", "waiver_requested")
                 if k in dev]
        lines += _kv_block(pairs)
        lines.append("")

    for filler in model.get("fillers", []):
        lines.append("[[filler]]")
        lines += _kv_block([
            ("profile", _pq(filler["profile"])), ("party", _pq(filler["party"])),
            ("role", _pq(filler["role"])),
        ])
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def assemble_package(
    brief_fields: dict, report_dir: Path, contract: dict, contract_path: Path,
    fill: dict, out_path: Path, profile: dict | None,
) -> tuple[str, list[str]]:
    """worker-brief.md §2. Returns (package_text, warnings). Raises AssembleError on a structural
    problem (missing manifest run, transcript/command mismatch, unresolvable recipe, ...)."""
    warnings: list[str] = []
    reqs = _requirement_map(contract)
    touch_items = touch_list_from_scope(brief_fields.get("scope", ""))

    manifest_path = report_dir / "manifest.toml"
    if not manifest_path.is_file():
        raise AssembleError(f"report directory has no manifest.toml: {manifest_path}")
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    report_meta = manifest.get("report") or {}
    report_commit = report_meta.get("commit")
    if not _nonempty(report_commit):
        raise AssembleError(
            "report manifest.toml: [report].commit is required (the worker-recorded execution "
            "commit) — a transcript with no recorded execution commit must be RE-RUN by the "
            "assembler (worker-brief.md §2), which this verb does not implement; supply one"
        )
    runs_by_id = {
        r["id"]: r for r in (manifest.get("run") or [])
        if isinstance(r, dict) and _nonempty(r.get("id"))
    }

    repo_root = Path(_git(["rev-parse", "--show-toplevel"], report_dir))
    subject_commit = _git(["rev-parse", "HEAD"], repo_root)
    # the write-scope glob lives in the brief's `scope` block (`_brief_scope_text`) — read back
    # out with the same small pattern `touch_list_from_scope` uses for the touch-list itself.
    m = re.search(r"allowed_writes: (\S.*)$", brief_fields.get("scope", ""), re.MULTILINE)
    glob_spec = m.group(1).strip() if m else ""
    subject_rel = _glob_root(glob_spec) or (contract.get("subject") or {}).get("name", "")
    dirty_out = _git(["status", "--short", "--", str((report_dir / subject_rel).resolve().relative_to(repo_root))], repo_root)
    dirty = bool(dirty_out.strip())

    contract_subject_profile = (contract.get("subject") or {}).get("profile")
    if not _nonempty(contract_subject_profile):
        raise AssembleError(
            "[subject].profile must be a nonempty string (§3.1 rule 7) — no compatibility "
            "default is assumed for the assembled package's [format].profile"
        )
    contract_hash = m11.digest_file("contract", contract_path)
    fmt = {
        "id": "acceptance/0",
        "protocol": PROTOCOL_ID,
        "profile": contract_subject_profile,
    }
    subject = {
        "name": (contract.get("subject") or {}).get("name", ""),
        "kind": (contract.get("subject") or {}).get("kind", ""),
        "commit": subject_commit,
        "dirty": dirty,
    }
    contract_block = {
        "id": (contract.get("document") or {}).get("id", ""),
        "hash": contract_hash,
        "requirements_total": len(contract.get("requirement") or []),
    }
    spec_block = {
        "path": os.path.relpath(contract_path, start=out_path.parent),
        "version": f"{contract_block['id']}@v{(contract.get('document') or {}).get('version', 1)}",
        "axis": f"the requirements of contract {contract_block['id']}",
    }

    subject_dir = report_dir / subject_rel

    def load_run(run_id: str) -> dict:
        run = runs_by_id.get(run_id)
        if run is None:
            raise AssembleError(f"fill.toml references unknown report run {run_id!r}")
        return run

    def build_evidence(fc: dict, ev_fill: dict, cid: str) -> dict:
        run = load_run(ev_fill["run"])
        command = run.get("command") or ""
        real_out, probes = _load_run_transcript(report_dir, run)
        class_fields = (profile or {}).get("evidence_class_fields", lambda c: None)(command)
        kind = ev_fill.get("kind") or (class_fields or {}).get("kind")
        family = ev_fill.get("family") or (class_fields or {}).get("family")
        method = ev_fill.get("method") or (class_fields or {}).get("method")
        tier = ev_fill.get("epistemic_tier") or (class_fields or {}).get("epistemic_tier")
        if not (kind and family and method and tier):
            raise AssembleError(
                f"claim {cid!r} evidence (run {ev_fill['run']!r}): command {command!r} does not "
                "mechanically classify under this profile, and fill.toml supplies no "
                "kind/family/method/epistemic_tier override"
            )
        judge = (profile or {}).get("judge_run")
        result, cases_default = judge(command, run.get("returncode", 1), real_out) if judge else ("fail", None)
        cases = ev_fill.get("cases", cases_default)
        tool_fn = (profile or {}).get("tool_string")
        tool = tool_fn(command, probes) if tool_fn else None
        if tool is None:
            raise AssembleError(f"claim {cid!r} evidence (run {ev_fill['run']!r}): no tool-string binding for this profile")
        if run.get("role") == "control" and run.get("mutation_note"):
            tool = f"{tool} ({run['mutation_note']})"
        # `record` names the file a claim's [[claim.evidence]] points reviewers at — usually the
        # SAME file `transcript` was parsed from, but a manifest run MAY declare a separate
        # `record` (worker-brief.md §2 "the transcript file"): the file captured to satisfy
        # `_load_run_transcript`'s own tool-identity-probe requirement (worker-brief.md §2's "the
        # tool's `--version` line captured in the transcript") is not always the SAME bytes as the
        # canonical evidence record a prior, marker-less capture already committed — e.g. this
        # example's `evidence/*.txt` files predate the marker convention and are re-hashed on
        # every change, so a wrapper transcript under `transcripts/` supplies the markers for
        # parsing while `record` still names the original, untouched evidence file.
        record_rel = run.get("record") or run["transcript"]
        # Typed wire form (hash-domains.md `record:`): writers MUST NOT emit the untyped legacy
        # `evidence-record:` construction (m11.py's bare `sha-512:<hex>`, read-only in 0.3.x).
        record_hash = m11.hashdomains.digest("record:", (report_dir / record_rel).read_bytes())
        input_fn = (profile or {}).get("input_set")
        inputs = []
        # A control row's command ran against a MUTATED subject that has already been restored by
        # the time assemble-package runs — digesting the current (clean) files for it would record
        # the digest of code the control did NOT actually execute against, which is worse than no
        # inputs block (worker-brief.md §2 "digests of the files the transcript's command read" —
        # the assembler cannot honestly answer that for a reverted mutation). Matches the previous
        # hand-written generator, which also recorded no `[[claim.evidence.inputs]]` on control rows.
        if run.get("role") != "control":
            for relpath in (input_fn(command, subject_dir) if input_fn else []):
                inputs.append((relpath, m11.digest_file("subject", subject_dir / relpath)))
        entry = {
            "kind": kind, "family": family, "method": method, "epistemic_tier": tier,
            "ref": ev_fill.get("ref"), "result": result, "tool": tool, "cases": cases,
            "generator": ev_fill.get("generator"), "record": record_rel, "record_hash": record_hash,
            "captured_at_commit": report_commit, "bounds": ev_fill.get("bounds"),
            "semantics": ev_fill.get("semantics"), "inputs": inputs, "control": None,
        }
        if run.get("role") == "control":
            entry["control"] = {
                "kind": "mutation", "expectation": "red",
                "observed": "red" if result == "fail" else "green",
                "of_claim": cid,
            }
        return entry

    item_claims: dict[str, dict] = {}
    cross_fcs: list[dict] = []
    order: list[str] = []

    for fc in fill.get("claim") or []:
        cid = fc["id"]
        order.append(cid)
        rid = fc["requirement"]
        req = reqs.get(rid)
        if req is None:
            raise AssembleError(f"fill.toml claim {cid!r}: requirement {rid!r} is not in the contract")
        if req.get("kind") == "cross-cutting":
            cross_fcs.append(fc)
            continue

        item = touch_items.get(rid) or f"{subject['name']} (requirement {rid})"
        recipe, source = resolve_recipe(contract, req, profile)
        if source == "worker-proposed":
            fc_recipe = fc.get("recipe")
            if not isinstance(fc_recipe, dict) or not _nonempty(fc_recipe.get("command")):
                raise AssembleError(
                    f"claim {cid!r}: requirement {rid!r}'s recipe is worker-proposed but "
                    "fill.toml has no [claim.recipe] {command, expect} for it"
                )
            command, expect = fc_recipe["command"], fc_recipe["expect"]
        else:
            command, expect = recipe["command"], recipe["expect"]

        primary_run = next(
            (r for r in runs_by_id.values() if r.get("role") == "primary" and
             " ".join((r.get("command") or "").split()) == " ".join(command.split())),
            None,
        )
        if primary_run is None:
            raise AssembleError(f"claim {cid!r}: no report run with role=primary matches command {command!r}")
        real_out, _probes = _load_run_transcript(report_dir, primary_run)
        judge = (profile or {}).get("judge_run")
        primary_result, _ = judge(command, primary_run.get("returncode", 1), real_out) if judge else ("fail", None)
        status = "evidenced" if primary_result == "pass" else "gap"

        evidence = [build_evidence(fc, ev_fill, cid) for ev_fill in fc.get("evidence") or []]

        wf = None
        wf_fill = fc.get("watched_fail")
        if isinstance(wf_fill, dict):
            wf = {
                "of_command": command, "perturbed": wf_fill["perturbed"],
                "observed": wf_fill["observed"], "date": report_meta.get("date") or today_utc_date(),
            }

        propose_weighted = status == "evidenced" and fc.get("weight") in (None, "weighted")

        claim = {
            "id": cid, "clause": rid, "item": item, "heading": (req.get("statement", "") or "")[:72],
            "statement": fc["statement"], "band": fc.get("band"), "status": status,
            "grade": fc.get("grade"), "clause_source": fc.get("clause_source"), "bounds": fc.get("bounds"),
            "captured_at_commit": report_commit,
            "weight": "weighted" if propose_weighted else None,
            "_propose_weighted": propose_weighted,
            "self_verify": {"command": command, "expect": expect, "watched_fail": wf},
            "evidence": evidence,
        }
        item_claims[cid] = claim

    for fc in cross_fcs:
        cid = fc["id"]
        rid = fc["requirement"]
        req = reqs[rid]
        over_ids = req.get("over") or []
        over_claims = [item_claims[c] for c in over_ids if c in item_claims]
        demand_fields = (req.get("demands") or {}).get("fields") or {}
        ok = bool(over_claims)
        for k, want in demand_fields.items():
            for oc in over_claims:
                got = oc.get(k)
                if not (isinstance(got, str) and got.strip().lower().startswith(str(want).strip().lower())):
                    ok = False
        status = "evidenced" if ok else "gap"
        band = fc.get("band") or ("A0" if status == "gap" else None)
        grade = fc.get("grade") or ("unspecified" if status == "gap" else None)
        claim = {
            "id": cid, "clause": rid, "item": f"cross-cutting: {', '.join(over_ids)}",
            "heading": "cross-cutting -- NOT MET" if status == "gap" else "cross-cutting",
            "statement": fc["statement"], "band": band, "status": status, "grade": grade,
            "clause_source": fc.get("clause_source"), "bounds": None,
            "captured_at_commit": report_commit, "weight": None, "_propose_weighted": False,
            "self_verify": None, "evidence": [],
            "weight_omitted_comment": (
                "weight omitted -> unweighted (W1): this row documents the gap the deviation "
                "below names; it does not itself carry the format's vouching -- the deviation "
                "carries the disclosure."
            ) if status == "gap" else None,
        }
        item_claims[cid] = claim

    claims = [item_claims[cid] for cid in order]

    deviations = []
    for dev in fill.get("deviation") or []:
        if dev.get("requirement") not in reqs:
            raise AssembleError(f"fill.toml deviation names unknown requirement {dev.get('requirement')!r}")
        deviations.append(dev)

    fillers = []
    for filler in fill.get("filler") or []:
        fillers.append({
            "profile": filler.get("profile") or fmt["profile"],
            "party": filler["party"], "role": filler["role"],
        })

    header = fill.get("header_comment") or (
        f"# GENERATED FILE — DO NOT HAND-EDIT.\n"
        f"# Produced by acceptance_protocol.py assemble-package from {report_dir.name}/manifest.toml "
        f"+ fill.toml, from a brief projected by project-brief (worker-brief.md §1/§2).\n"
        f"# Generated: {now_utc_iso()}\n"
    )

    model = {
        "header_comment": header, "format": fmt, "subject": subject, "contract": contract_block,
        "spec": spec_block,
        "coverage": {"clauses_total": len(reqs), "claims_total": len(claims)},
        "claims": claims, "deviations": deviations, "fillers": fillers,
    }

    # Pass 1: tentative weights, so `claim_weight_grants` can see what a fully-proposed package
    # would look like — a claim's weight, per worker-brief.md §2, is "assembler proposes `weighted`
    # only when every W2 condition is present" (fail-closed: never write `weighted` on faith).
    text = _render_package(model)
    out_path.write_text(text, encoding="utf-8")
    grants, _ca_rep = claim_weight_grants(out_path, claims, (profile or None))
    for claim in claims:
        if claim.get("_propose_weighted") and not grants.get(claim["id"]):
            claim["weight"] = None
            claim["weight_omitted_comment"] = (
                "weight omitted -> unweighted: assembler proposed `weighted` but the format "
                "validator did not grant it (fail-closed, worker-brief.md §2)."
            )
    final_text = _render_package(model)
    out_path.write_text(final_text, encoding="utf-8")
    return final_text, warnings


def cmd_assemble_package(args) -> int:
    brief_path = Path(args.brief)
    report_dir = Path(args.report_dir)
    contract_path = Path(args.contract)
    fill_path = Path(args.fill) if args.fill else None

    brief_fields = parse_window_brief_yaml(brief_path.read_text(encoding="utf-8"))
    contract, cerr = load_toml(contract_path)
    if cerr:
        print(f"ERROR {contract_path}: {cerr}")
        return 2
    fill = tomllib.loads(fill_path.read_text(encoding="utf-8")) if fill_path else {}
    profile_id = (contract.get("subject") or {}).get("profile")
    if not _nonempty(profile_id):
        print(f"ERROR {contract_path}: [subject].profile must be a nonempty string (§3.1 rule "
              f"7) — no compatibility default is assumed")
        return 2
    profile = PROFILES.get(profile_id)

    try:
        _text, warnings = assemble_package(
            brief_fields, report_dir, contract, contract_path, fill, Path(args.out), profile,
        )
    except AssembleError as e:
        print(f"ERROR: {e}")
        return 1
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    print(f"wrote {args.out}")
    return 0


# ---------------------------------------------------------------------------------------------
# --selftest — one chain per bound profile (moved out of this file into
# `fixtures/<profile>_chain.py`, one module per bound profile — see PROFILE_CHAINS below). Each
# chain module owns its own profile's fixture data (tempfile.TemporaryDirectory, never the repo)
# and exercises the SAME core this file implements end to end: contract -> package -> decision.
# protocol.md section numbers are cited per case name inside each chain; every rule this tool
# enforces gets one fixture that passes and one that fails on exactly that rule (worker-brief W4).
# ---------------------------------------------------------------------------------------------

# profile id -> selftest chain module name under fixtures/. Adding a profile's binding to
# profiles.py and a chain module here is the whole extension point (P11: the core itself names no
# profile) — check_core_generic.py's Class-rung scan never sees these modules, since Instance-rung
# fixture data is not a Class carrier.
PROFILE_CHAINS = {
    "acceptance/verification": "verification_chain",
    "acceptance/conformance": "conformance_chain",
    "acceptance/troubleshooting": "troubleshooting_chain",
}

# Class-rung fixture chains — not tied to one profile (protocol.md P11), so they are run
# separately from PROFILE_CHAINS and labelled "[core]" rather than a profile id. This file adds the
# first one: assurance class + spec maturity (§3.7).
CORE_CHAINS = ["assurance_class_chain"]


def run_selftest() -> int:
    import importlib

    all_cases: list[tuple[str, bool, object]] = []
    for profile_id, module_name in PROFILE_CHAINS.items():
        chain = importlib.import_module(f"fixtures.{module_name}")
        for name, ok, detail in chain.run():
            all_cases.append((f"[{profile_id}] {name}", ok, detail))
    for module_name in CORE_CHAINS:
        chain = importlib.import_module(f"fixtures.{module_name}")
        for name, ok, detail in chain.run():
            all_cases.append((f"[core] {name}", ok, detail))

    failed = [c for c in all_cases if not c[1]]
    if failed:
        for name, _ok, detail in failed:
            print(f"SELFTEST FAIL: {name}: {detail}")
        print(f"SELFTEST FAILED: {len(failed)}/{len(all_cases)} cases")
        return 99
    print(f"SELFTEST PASS: {len(all_cases)} cases")
    return 0


# ---------------------------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------------------------

def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="acceptance_protocol.py", description=__doc__)
    sub = p.add_subparsers(dest="verb", required=True)

    sp = sub.add_parser("check-contract")
    sp.add_argument("contract")
    sp.add_argument("--previous", action="append", default=None,
                     help="repeatable, newest-first: the contract's predecessor, then ITS predecessor, etc. (§3.3, Finding 4)")
    sp.add_argument("--previous-dir", default=None,
                     help="a directory of predecessor contracts, each resolved by its own [document].id (§3.3, Finding 4)")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_check_contract)

    sp = sub.add_parser("check-package")
    sp.add_argument("package")
    sp.add_argument("--contract", required=True)
    sp.add_argument("--previous-contract", default=None, help="the contract's predecessor, when it supersedes another (Finding 4, §5.0/§3.5)")
    sp.add_argument("--previous", action="append", default=None,
                     help="repeatable, newest-first: the whole predecessor chain (§3.3, Finding 4)")
    sp.add_argument("--previous-dir", default=None,
                     help="a directory of predecessor contracts, each resolved by its own [document].id (§3.3, Finding 4)")
    sp.add_argument("--strict", action="store_true")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--root", type=Path, default=None,
                     help="B6 repository root for evidence pointers when the tree has no .git (e.g. a source archive)")
    sp.set_defaults(func=cmd_check_package)

    sp = sub.add_parser("coverage")
    sp.add_argument("package")
    sp.add_argument("--contract", required=True)
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--root", type=Path, default=None,
                     help="B6 repository root for evidence pointers when the tree has no .git (e.g. a source archive)")
    sp.set_defaults(func=cmd_coverage)

    sp = sub.add_parser("decide")
    sp.add_argument("package")
    sp.add_argument("--contract", required=True)
    sp.add_argument("--issuer", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--mode", choices=VERIFICATION_MODES, default=None)
    sp.add_argument("--root", type=Path, default=None,
                     help="B6 repository root for evidence pointers when the tree has no .git (e.g. a source archive)")
    sp.set_defaults(func=cmd_decide)

    sp = sub.add_parser("check-decision")
    sp.add_argument("decision")
    sp.add_argument("--contract", required=True)
    sp.add_argument("--package", required=True)
    sp.add_argument("--previous-contract", default=None, help="the bound contract's predecessor, when it supersedes another (Finding 4, §5.0/§3.5)")
    sp.add_argument("--previous", action="append", default=None,
                     help="repeatable, newest-first: the whole predecessor chain (§3.3, Finding 4)")
    sp.add_argument("--previous-dir", default=None,
                     help="a directory of predecessor contracts, each resolved by its own [document].id (§3.3, Finding 4)")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--effect", action="store_true", help="also evaluate §5.0a effect eligibility (Finding 12); exit reflects effect eligibility, not mere validity")
    sp.add_argument("--now", default=None, help="YYYY-MM-DD; default today (UTC) — used only by --effect's unexpired check")
    sp.add_argument("--allow-conditions", action="store_true", help="--effect: accepted-with-conditions is also eligible (the gate's own policy)")
    sp.add_argument("--root", type=Path, default=None,
                     help="B6 repository root for evidence pointers when the tree has no .git (e.g. a source archive)")
    sp.set_defaults(func=cmd_check_decision)

    sp = sub.add_parser("check-states")
    sp.add_argument("states", nargs="?", default=None)
    sp.set_defaults(func=cmd_check_states)

    sp = sub.add_parser("transition")
    sp.add_argument("machine")
    sp.add_argument("from_state")
    sp.add_argument("name")
    sp.add_argument("--states", default=None)
    sp.set_defaults(func=cmd_transition)

    sp = sub.add_parser("impact")
    sp.add_argument("decision")
    sp.add_argument("--contract", required=True)
    sp.add_argument("--package", required=True)
    sp.add_argument("--new-commit", required=True)
    sp.add_argument("--changed", nargs="*", default=None)
    sp.add_argument("--changed-file", default=None)
    sp.add_argument("--new-package", default=None, help="the package at the new state, for tool/semantics continuity (Finding 14); without it, continuity is UNKNOWN and every still-changed record is possibly-invalidated")
    sp.add_argument("--out-events", default=None)
    sp.set_defaults(func=cmd_impact)

    sp = sub.add_parser("render")
    sp.add_argument("contract")
    sp.add_argument("package")
    sp.add_argument("decision", nargs="?", default=None)
    sp.add_argument("--out", default=None)
    sp.add_argument("--root", type=Path, default=None,
                     help="B6 repository root for evidence pointers when the tree has no .git (e.g. a source archive)")
    sp.set_defaults(func=cmd_render)

    sp = sub.add_parser("check-amendment")
    sp.add_argument("amendment")
    sp.add_argument("--contract", required=True)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_check_amendment)

    sp = sub.add_parser("apply-amendment")
    sp.add_argument("amendment")
    sp.add_argument("--contract", required=True)
    sp.add_argument("--current", default=None, help="a caller-chosen file to diagnose against (Finding 6); default = --contract; NOT the atomicity mechanism (see --pointer)")
    sp.add_argument("--pointer", default=None,
                     help="the current-pointer record {id, hash} (§3.6 rule 1, Finding 6); default = "
                          "<contract dir>/acceptance-contract.current; created from --contract on first use")
    sp.add_argument("--out", default=None)
    sp.add_argument("--id", default=None)
    sp.add_argument("--accept-by", default=None)
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_apply_amendment)

    sp = sub.add_parser("amend")
    sp.add_argument("--from-decision", required=True, dest="from_decision")
    sp.add_argument("--contract", required=True)
    sp.add_argument("--out", required=True)
    sp.set_defaults(func=cmd_amend)

    sp = sub.add_parser("project-brief", help="worker-brief.md §1: contract -> minimal brief (worker-brief/v1)")
    sp.add_argument("contract")
    sp.add_argument("--out", required=True)
    sp.add_argument("--allowed-writes", default=None,
                     help="a path to a small TOML file with `writes` (the orchestrator's write-scope glob) "
                          "and `[items]` (requirement id -> touch-list item pointer), or a literal write-scope string")
    sp.add_argument("--stats", action="store_true", help="also print the line/token count comparison as JSON to stdout")
    sp.set_defaults(func=cmd_project_brief)

    sp = sub.add_parser("assemble-package", help="worker-brief.md §2: a worker's report -> protocol package")
    sp.add_argument("brief")
    sp.add_argument("report_dir")
    sp.add_argument("--contract", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--fill", default=None, help="the worker's fill.toml (the semantic slice; §2)")
    sp.set_defaults(func=cmd_assemble_package)

    return p


def main(argv: list[str]) -> int:
    if "--selftest" in argv[1:]:
        if len(argv) != 2:
            print("usage: acceptance_protocol.py --selftest", file=sys.stderr)
            return 2
        return run_selftest()

    if len(argv) < 2:
        print("usage: acceptance_protocol.py VERB ...  (or --selftest)", file=sys.stderr)
        return 2

    parser = build_argparser()
    args = parser.parse_args(argv[1:])
    global _ROOT_OVERRIDE
    _ROOT_OVERRIDE = getattr(args, "root", None)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
