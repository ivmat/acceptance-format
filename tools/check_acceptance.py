#!/usr/bin/env python3
"""check_acceptance.py — the oracle for the acceptance/0 manifest format.

Pure stdlib, python3.11+ (uses tomllib).

Usage:
    check_acceptance.py [--strict] [--strict-weight] FILE [FILE...]   validate manifests
    check_acceptance.py --selftest                                   run embedded fixtures

Exit codes (core.md §8.3, the validator's tri-state contract): 0 = valid (every checked
file passes, warnings allowed), 1 = invalid (a structural obligation is violated in at least one
file), 2 = indeterminate (no file is invalid, but at least one cannot be decided -- an unprofiled
method/kind, or `shape = "bundle"`) OR a usage error (bad CLI invocation, before any file is
read). `invalid` and `indeterminate` are reported as distinct FAIL/INDETERMINATE lines per file
even though a CLI usage error shares exit code 2 with `indeterminate` for an unrelated reason
(the two are orthogonal: a usage error means no file was ever validated at all).

See spec/format.md, spec/evidence-types.md, spec/assurance-bands.md — this
validator implements those documents; on any disagreement, the spec wins and
this file has a bug.
"""

from __future__ import annotations

import hashlib
import re
import sys
import tempfile
import tomllib
from pathlib import Path

# The rules that must mean the same thing in BOTH representations live in one module, imported
# by this checker and by check_ledger.py. the round-3 review probe found the reason: `out-of-scope`
# had drifted to two different rules, and the Markdown copy granted weight where this one
# refused it. See tools/acceptance_grammar.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import m11  # noqa: E402 — the shared M11 content-hash helper (spec/format.md, ratified 2026-08-28)
from acceptance_grammar import (  # noqa: E402
    CLAUSE_SOURCES as _G_CLAUSE_SOURCES,
    CLAUSE_SOURCES_UNWEIGHTABLE,
    GRADES as _G_GRADES,
    GRADES_REQUIRING_BOUNDS as _G_GRADES_REQUIRING_BOUNDS,
    GRADES_REQUIRING_RECIPE as _G_GRADES_REQUIRING_RECIPE,
    SCOPE_REF_EXPECTATION,
    STATUSES as _G_STATUSES,
    STATUSES_NO_CHECK,
    UNWEIGHTABLE_GRADES as _G_UNWEIGHTABLE_GRADES,
    bounds_token,
    has_bounds_tail,
    is_iso_date,
    is_phrase as _is_phrase,
    is_scope_locator,
    strip_witness_metadata,
    status_grade_incoherence,
)

# --------------------------------------------------------------------------
# Registries (spec/evidence-types.md, spec/assurance-bands.md)
# --------------------------------------------------------------------------

# CS-12 (format.md): five non-code artifact classes joined the registry. `[subject].kind` is a
# distinct field from `[[claim.evidence]].kind` (the registry column below, demoted to a hint by
# CS-2) -- the two share a name and nothing else. CS-13: a token outside this set is NOT a hard
# `invalid` -- it is `indeterminate` (the format does not know whether it names a real,
# undeclared artifact class or a typo), handled in check_subject via Reporter.indet().
SUBJECT_KINDS = {
    "rust-crate", "rust-workspace", "doc", "tool", "other",
    "ml-model", "dataset", "spec", "design", "agent-output",
}
BANDS = {"A0", "A1", "A2", "A3", "A3.5", "A4"}
# CS-10 (format.md): `[format].shape` -- REQUIRED from this revision. `bundle` ships as a shape
# with no validator behind it yet (CS-11): a manifest declaring it is `indeterminate` as a whole.
SHAPE_VALUES = {"single-file", "bundle"}
# CS-1 (evidence-types.md): the closed, core, artifact-agnostic epistemic-tier vocabulary.
EPISTEMIC_TIERS = {"T1", "T2", "T3", "T4", "T5"}
# CS-2/CS-3: the FV profile's `method -> epistemic_tier` table (evidence-types.md's registry
# table). `method` and `kind` coincide in spelling for this one shipped profile -- a convenience,
# not a rule (CS-2 explicitly forbids the validator from resolving `method` FROM `kind`, so this
# map is keyed on `method` tokens and is never consulted via a record's `kind` field).
METHOD_EPISTEMIC_TIER = {
    "lean-theorem": "T1",
    "kani-harness": "T2",
    "flux-refinement": "T2",
    "unit-test": "T3",
    "property-test": "T3",
    "fuzz": "T3",
    "miri": "T3",
    "lint": "T4",
    "semver-check": "T4",
    "dep-audit": "T4",
    "human-review": "T5",
    "llm-review": "T5",
}


def _tier_rank(tier: str) -> int:
    """T1 (kernel-checked) is the STRONGEST and T5 (human judgment) the weakest, so the numeral
    runs opposite to strength: a LOWER rank is a STRONGER claim.

    The profile's pinned tier is a CEILING, not an equality (ADR-002: "a record's declared
    `epistemic_tier` may never EXCEED what the profile's table assigns to its `method`"). The
    validator required exact equality until 2026-08-28, which refused an honest deflation --
    a producer marking a kani-harness record `T3` because the harness only samples the space
    is under-claiming, and an anti-overclaim format that refuses under-claims is enforcing the
    wrong direction. Over-claiming (declaring a tier the method does not earn) stays an error."""
    return int(tier[1:])
# core.md §7.3 (P4, ADOPTED 2026-08-25): `blocked` — the tool cannot reach the item at all,
# which demands a different action from a reader than "nobody has done it yet". This list was
# stale for a day: the spec adopted the status and the validator rejected every manifest that
# used it, so the TOML representation could not express what the Markdown one could.
STATUSES = _G_STATUSES

# core.md §7.2 (P3, ADOPTED): an item that ranges over a second list. DECLARATIVE — a claim is
# a predicate row because it says `item_kind = "predicate"`, never because a checker read its
# prose and guessed.
ITEM_KIND_VALUES = {"item", "predicate"}
# NOT `re.IGNORECASE` (2026-08-28, common-subset ruling): the flag compiled into the emitted
# schema as a leading `(?i)` group, Python-only syntax invalid in ECMA-262. Case-insensitivity on
# the "of" word is preserved anyway (no shipped fixture relies on it — every `covered` value in
# the corpus uses the `N/M` form — but the spec text doesn't rule "N Of M" out), via explicit
# character classes rather than the flag, so the pattern stays in the Python ∩ ECMA-262 subset.
COVERED_FRACTION_RE = re.compile(r"^\s*(\d+)\s*(?:/|\s+[oO][fF]\s+)\s*(\d+)\s*$")
RESULTS = {"pass", "fail", "unsupported"}
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

# CS-16 self-location SHAPES (format.md, "pinning to `validator_sha` is the only real stability
# guarantee"). Until 2026-08-28 these five fields were checked for nonemptiness ONLY, so a
# manifest declaring `validator_sha = "also-not-a-sha"` and `generated_at = "not-a-date"` passed
# --strict --strict-weight -- the format's own claimed stability anchor was a free-text field.
# Shape only, and deliberately so: that the named sha IDENTIFIES the validator actually run is a
# binding check this revision does not ship (booked in maintainers/VALIDATOR-TODO.md).
#
# 7..40 hex: a git object name, full or abbreviated. The floor is 7 because that is git's own
# default abbreviation length; shorter is not an identity anyone can resolve.
SELF_LOCATION_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
# ISO-8601 UTC, the `Z` form, seconds precision -- one spelling, matched exactly, because a
# timestamp a reader has to guess the timezone of is not a location.
GENERATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

# field-type tags:
#   "str-nonempty" -> must be present, a str, len > 0
#   "str-any"      -> must be present, a str (may be "")
#   "list"         -> must be present, a list (may be empty)
#   "int-pos"      -> must be present, an int (not bool), >= 1

KIND_REGISTRY = {
    "kani-harness": {
        "family": "bmc",
        "extra": {"bounds": "bounds-token", "semantics": "str-any"},
    },
    "lean-theorem": {
        "family": "kernel",
        "extra": {"axioms": "list", "semantics": "str-nonempty"},
    },
    "flux-refinement": {
        "family": "smt-refinement",
        "extra": {"bounds": "bounds-token", "semantics": "str-nonempty"},
        "warn_reserved": True,
    },
    "unit-test": {
        "family": "dynamic",
        "extra": {"cases": "int-pos"},
    },
    "property-test": {
        "family": "dynamic",
        "extra": {"cases": "int-pos", "generator": "str-nonempty"},
    },
    "fuzz": {
        "family": "dynamic",
        "extra": {"corpus_size": "int-pos", "duration": "str-nonempty"},
    },
    "miri": {
        "family": "dynamic",
        "extra": {"semantics": "str-nonempty"},
    },
    "lint": {
        "family": "mechanical",
        "extra": {},
    },
    "semver-check": {
        "family": "mechanical",
        "extra": {"baseline": "str-nonempty"},
    },
    "dep-audit": {
        "family": "mechanical",
        "extra": {"db_version": "str-nonempty"},
    },
    "human-review": {
        "family": "judgment",
        "extra": {"reviewer": "str-nonempty"},
    },
    "llm-review": {
        "family": "judgment",
        "extra": {"reviewer": "str-nonempty"},
    },
}

# core.md §0.5, `symbolic domain`: "inputs the checker reasons over as SETS rather than
# enumerating as values... `contract` requires one; tests witness points, so a test is never
# `contract`." These are the families that reason over sets, per `evidence-types.md`: `bmc`
# (Kani, symbolic inputs), `kernel` (Lean, universally quantified), `smt-refinement` (Flux,
# "unbounded-smt"). `dynamic` witnesses points, `mechanical` has no behavioural oracle, and
# `judgment` is a person.
#
# The sentence was normative from the day §0.5 was written and enforced NOWHERE, and it was in
# neither table of OBLIGATIONS.md -- so the inventory's own completeness claim was false for it.
# Found by a cold reader in their first hour, which is roughly how long it should have taken.
SYMBOLIC_DOMAIN_FAMILIES = {"bmc", "kernel", "smt-refinement"}

UNIVERSAL_EVIDENCE_FIELDS = ["kind", "family", "ref", "result", "tool", "record"]
RESERVED_TRUST_FIELDS = ("alpha", "beta", "lr")
FREEDOM_WORDS = ("panic", "crash", "freedom", "ub")

# The `control` block (assurance-bands.md rule 6 / evidence-types.md "Control block") is
# FAMILY-AGNOSTIC (corrected 2026-08-22): it is an optional sub-table any evidence record may
# carry — `family` on the record already says what was perturbed (kernel = mutated Lean theorem,
# bmc = mutated Kani harness, dynamic = cargo-mutants/stryker, mechanical = seeded-bad gate
# fixture); the control block itself carries {kind, expectation, observed, of_claim} and is
# orthogonal to family. Mirrors a pre-existing internal receipt format's control block 1:1.
CONTROL_KIND_VALUES = {"mutation", "ablation", "planted-twin"}
CONTROL_EXPECTATION_VALUES = {"red", "green", "sat"}

# Per-band control-kind whitelist for the BAND-LIFT gate (assurance-bands.md rule 6, tightened
# 2026-08-22 — mirrors a pre-existing internal system's audit, which requires kind=="mutation" for
# its controls-check). `planted-twin` is never in either set: it proves the pipeline can reject at
# all (a satisfiability/pipeline signal, a pre-existing internal system's separate
# acknowledgment-witness role), never that THIS claim's own oracle catches a mutation of THIS
# impl/theorem. It may still be recorded in a manifest as disclosure/satisfiability evidence — it
# just never lifts a band.
MUTATION_ONLY = {"mutation"}                    # A3/A4, and oracle-bearing A1
MUTATION_OR_ABLATION = {"mutation", "ablation"}  # A2 (memory safety / unsafe surface)

# Carrier-family compatibility for the BAND-LIFT gate (tightened 2026-08-22, F2): a band-lifting
# control's CARRIER record (the evidence record the `control` block sits on) must be species-
# compatible with the band being lifted — a `human-review` (judgment-family) record carrying
# control{mutation,red,red,of_claim} must NOT be able to satisfy an A3/A4 gate; that would defeat
# the point of a mechanical control. `judgment` is deliberately absent from every set below.
CARRIER_FAMILIES_FOR_BAND = {
    "A4": {"kernel"},
    "A3": {"bmc"},
    "A2": {"bmc", "dynamic"},
    "A1": {"dynamic"},  # only consulted for the oracle-bearing-A1 case
}

# Dynamic kinds with no postcondition oracle to mutate — freedom-shaped, exempt from the A1 control
# requirement (assurance-bands.md rule 4/6).
DYNAMIC_FREEDOM_KINDS = {"miri", "fuzz"}

# Dynamic kinds that ARE oracle-bearing (a functional assertion, not just "did it crash") — these
# require a matching control to reach A1 when no other (kani-harness/mechanical/freedom-dynamic)
# species is also present (assurance-bands.md rule 4).
DYNAMIC_ORACLE_KINDS = {"unit-test", "property-test"}

# core.md §1: `grade` is a REQUIRED claim field (tightened 2026-08-25 from the pre-freeze
# OPTIONAL M6 tag) — the closed nine-token vocabulary. A missing or out-of-vocabulary grade is an
# error naming core.md §1.
WEIGHT_VALUES = {"weighted", "unweighted"}
# core.md §1: grades with no deciding machinery can never carry weight.
UNWEIGHTABLE_GRADES = _G_UNWEIGHTABLE_GRADES


def _is_weighted(claim: dict) -> bool:
    """core.md W1: weight is explicit and DEFAULTS TO ABSENT. A claim that does
    not claim weight is unweighted, and the format promises nothing about it --
    the format never vouches by silence."""
    return claim.get("weight") == "weighted"
CLAIM_GRADE_VALUES = _G_GRADES

# core.md §1/§3: grades that assert a check was, or was not, performed — every one of these
# REQUIRES a [claim.self_verify] table with a nonempty `command`.
GRADES_REQUIRING_SELF_VERIFY = _G_GRADES_REQUIRING_RECIPE

# core.md §5: grades that require a claim-level `bounds` field ("bounded"/"unbounded" prefix
# + free text) — reading a bounded proof as unbounded is the overclaim 0.1 refuses to allow silent.
GRADES_REQUIRING_BOUNDS = _G_GRADES_REQUIRING_BOUNDS

# coverage-ledger.md §6: where the claim's clause text came from. "test-name" is self-referential
# (the clause and its evidence are the same artifact) — recorded, not forbidden, but warned on.
CLAUSE_SOURCE_VALUES = _G_CLAUSE_SOURCES

# coverage-ledger.md §3: the [claim.self_verify] sub-table's allowed keys — strict (new table, no
# legacy producers to tolerate unknown keys from).
# core.md §4.1 (P2, adopted 2026-08-25): `watched_fail` names what was perturbed, what was
# observed, and when -- the witness that the recipe CAN report the claim false.
SELF_VERIFY_FIELDS = {"command", "expect", "precondition", "positive_control", "watched_fail",
                      "expect_stream"}
# core.md §8.2: which stream `--execute` matches `expect` against. stdout by default.
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
        # core.md §8.3 (CS-20): the tri-state contract's third state. Something the validator
        # cannot decide -- an unresolved extension, an unprofiled `method`/`kind`, or
        # `shape = "bundle"` -- not a structural violation (`invalid`) and never silently `valid`.
        self.indeterminate: list[str] = []
        # core.md §8.1: transitional weight refusals, keyed by claim context. A refused claim
        # is NOT counted weighted; the reasons are counted and itemised so the remediation
        # backlog stays visible instead of vanishing into a tier that promises nothing.
        self.strict_weight = strict_weight
        self.pending: dict[str, list[str]] = {}

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def indet(self, msg: str) -> None:
        """core.md §8.3 (CS-20): register an `indeterminate` case. Distinct from both `error`
        (a known structural violation) and `warn` (advisory, does not affect exit state) --
        `indeterminate` has its own exit code and is never silently treated as passable."""
        self.indeterminate.append(msg)

    def weight_pending(self, ctx: str, reason: str) -> None:
        self.pending.setdefault(ctx, []).append(reason)
        msg = f"{ctx}: WEIGHT REFUSED (transitional): {reason} (core.md §8.1)"
        if self.strict_weight:
            self.errors.append(msg)
        else:
            self.warnings.append(msg)

    def state(self) -> str:
        """core.md §8.3's tri-state: `invalid` | `indeterminate` | `valid`. A file that is BOTH
        (an `indeterminate` case sits alongside an unrelated structural violation) reports
        `invalid` -- a known-bad file must never be reported under the weaker "cannot decide"
        state merely because it also happens to touch something the validator doesn't understand
        yet; that would let a real violation hide behind an indeterminate case. This priority
        (invalid beats indeterminate beats valid) is this checker's own resolution of an ordering
        the spec text states per-obligation but not as a total order across obligations."""
        if self.errors:
            return "invalid"
        if self.indeterminate:
            return "indeterminate"
        return "valid"

    def ok(self) -> bool:
        """True only for `state() == "valid"` -- core.md §8.3: "indeterminate is non-accepting
        and its exit is nonzero, unconditionally... a warning beside PASS is not permitted."."""
        return self.state() == "valid"

    def lines(self) -> list[str]:
        out = [f"ERROR {self.path}: {m}" for m in self.errors]
        out += [f"INDET {self.path}: {m}" for m in self.indeterminate]
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
    elif tag == "bounds-token":
        # core.md §5's bounded/unbounded two-token rule, extended to evidence-record `bounds`
        # (format.md's schema comment: "boundedness declaration; 'unbounded' is an explicit
        # claim" -- a rule the KIND_REGISTRY never actually enforced). Unlike the CLAIM-level
        # `bounds` field (GRADES_REQUIRING_BOUNDS), the free-text tail naming the actual limit is
        # OPTIONAL here -- the token alone (`bounded` / `unbounded`) is what KIND_REGISTRY
        # requires; a fuller declaration is welcome but not mandatory at this granularity.
        if not _is_nonempty_str(v):
            rep.error(f"{ctx}: field '{field}' must be a nonempty string")
        elif bounds_token(v) is None:
            rep.error(
                f"{ctx}: field '{field}' must start with the token 'bounded' or 'unbounded' "
                f"(core.md §5's boundedness declaration, extended to evidence records), got "
                f"{v!r}"
            )
    else:  # pragma: no cover — internal registry bug
        rep.error(f"{ctx}: internal validator bug — unknown tag '{tag}' for '{field}'")


# --------------------------------------------------------------------------
# Section checks
# --------------------------------------------------------------------------

def check_format(rep: Reporter, doc: dict) -> bool:
    """Returns `illustrative` (CS-21) -- False on any early return, since an unparseable
    [format] section cannot be read as a teaching example either."""
    fmt = doc.get("format")
    if not isinstance(fmt, dict):
        rep.error("[format] section missing")
        return False
    if fmt.get("id") != "acceptance/0":
        rep.error(f"[format].id must be \"acceptance/0\", got {fmt.get('id')!r}")

    # CS-10/CS-11: `shape` is REQUIRED from this revision. `bundle` ships with no validator
    # behind it yet -- unconditionally `indeterminate` for the file as a whole (format.md
    # "`shape` — single-file vs bundle"), not a hard `invalid` and not a silent `valid`.
    shape = fmt.get("shape")
    if shape not in SHAPE_VALUES:
        rep.error(f"[format].shape must be one of {sorted(SHAPE_VALUES)}, got {shape!r}")
    elif shape == "bundle":
        rep.indet(
            "[format].shape = 'bundle' -- bundle validation has not shipped; this manifest is "
            "validated only as far as its own file reaches (format.md CS-11)"
        )

    # CS-16: `[format]` self-location. REQUIRED, hard error on absence -- illustrative (CS-21/22)
    # does NOT exempt required-field presence, only binding/watched-fail/tier-coherence.
    for f in ("spec_id", "spec_sha", "validator_sha", "generated_by", "generated_at"):
        if not _is_nonempty_str(fmt.get(f)):
            rep.error(
                f"[format].{f} must be a nonempty string (REQUIRED self-location field, "
                f"core.md §0.6 / format.md)"
            )

    # ...and the two SHAPED ones are checked for shape, not just presence. `format.md` says
    # pinning to `validator_sha` is "the only real stability guarantee" the format offers; a
    # nonemptiness test cannot tell a sha from a sentence, so that guarantee rested on the
    # producer's good manners until 2026-08-28.
    for f in ("spec_sha", "validator_sha"):
        v = fmt.get(f)
        if _is_nonempty_str(v) and not SELF_LOCATION_SHA_RE.match(v):
            rep.error(
                f"[format].{f} must be 7-40 lowercase hex characters (a git object name, full "
                f"or abbreviated), got {v!r} — a self-location field that is not an identity "
                f"pins nothing (format.md, CS-16)"
            )
    generated_at = fmt.get("generated_at")
    if _is_nonempty_str(generated_at) and not GENERATED_AT_RE.match(generated_at):
        rep.error(
            f"[format].generated_at must be ISO-8601 UTC of the form "
            f"'YYYY-MM-DDTHH:MM:SSZ', got {generated_at!r} (format.md, CS-16)"
        )

    # CS-21: `illustrative` -- OPTIONAL, defaults to false.
    illustrative = fmt.get("illustrative", False)
    if not isinstance(illustrative, bool):
        rep.error(
            f"[format].illustrative must be a bool (or omitted, meaning false), got "
            f"{illustrative!r}"
        )
        return False
    return illustrative


def check_subject(rep: Reporter, doc: dict) -> None:
    subj = doc.get("subject")
    if not isinstance(subj, dict):
        rep.error("[subject] section missing")
        return
    if not _is_nonempty_str(subj.get("name")):
        rep.error("[subject].name must be a nonempty string")
    kind = subj.get("kind")
    if not _is_nonempty_str(kind):
        rep.error(f"[subject].kind must be a nonempty string, got {kind!r}")
    elif kind not in SUBJECT_KINDS:
        # CS-13: fail-closed, per-profile registry. An unknown token is neither silently accepted
        # nor a hard `invalid` -- the format cannot tell a real, undeclared artifact class from a
        # typo, and says so structurally (format.md "a fail-closed registry").
        rep.indet(
            f"[subject].kind {kind!r} is not in the known registry {sorted(SUBJECT_KINDS)} and "
            f"no profile declares it -- indeterminate, not invalid (format.md kind-registry rule)"
        )
    commit = subj.get("commit")
    if not isinstance(commit, str) or not COMMIT_RE.match(commit):
        rep.error(f"[subject].commit must be 40 lowercase hex chars, got {commit!r}")
    if not isinstance(subj.get("dirty"), bool):
        rep.error(f"[subject].dirty must be a bool, got {subj.get('dirty')!r}")

    # design rule 4a (evidence-subject binding, dimensional fix): [subject].subject_hash is an
    # OPTIONAL M11 content-hash of the subject artifact, distinct from `commit` above -- `commit`
    # is a git-domain identity (SHA-1, over the repository tree) and is NEVER compared against an
    # M11 hash (a different algorithm over a different object is a category error, not a stronger
    # check). Where declared, it MUST be well-formed; every [[claim.evidence]] record naming a
    # `subject_hash` is checked against it in check_evidence_record, below.
    subj_hash = subj.get("subject_hash")
    if subj_hash is not None and not m11.is_well_formed(subj_hash):
        rep.error(
            f"[subject].subject_hash must be the self-describing form 'sha-512:<128-hex>' "
            f"(or omitted), got {subj_hash!r}"
        )

    # F-3 (audit fix, RULED): [subject].record_root -- OPTIONAL. The base path every `record`
    # pointer on this manifest resolves against, instead of the manifest file's own directory.
    # Absent = manifest-relative (unchanged behaviour). Shape only checked here (a nonempty
    # string, absolute or manifest-relative); the actual resolution happens in validate(), which
    # threads the resolved base_dir into check_claims/check_evidence_record.
    record_root = subj.get("record_root")
    if record_root is not None and not _is_nonempty_str(record_root):
        rep.error(
            f"[subject].record_root must be a nonempty string (or omitted), got {record_root!r}"
        )

    # [subject].repo -- OPTIONAL, not validator-interpreted (format.md "[subject].record_root");
    # context for a reader alongside `commit`/`record_root`, nothing more.
    repo = subj.get("repo")
    if repo is not None and not _is_nonempty_str(repo):
        rep.error(f"[subject].repo must be a nonempty string (or omitted), got {repo!r}")


def check_spec(rep: Reporter, doc: dict, any_weighted: bool = False) -> None:
    spec = doc.get("spec")
    if not isinstance(spec, dict):
        rep.error("[spec] section missing")
        return
    if not _is_nonempty_str(spec.get("path")):
        rep.error("[spec].path must be a nonempty string")
    if not _is_nonempty_str(spec.get("version")):
        rep.error("[spec].version must be a nonempty string")

    # core.md §6: [spec].axis is REQUIRED — a prose statement of what the item list
    # enumerates (tightened 2026-08-25 from the pre-freeze OPTIONAL field). [spec].external
    # (normative references not in the tree) stays optional.
    # core.md W2.4: axis is required only to EARN WEIGHT. A manifest with no
    # weighted claims may omit it -- nothing is being vouched for.
    if any_weighted and not _is_nonempty_str(spec.get("axis")):
        rep.error(
            "WEIGHT REFUSED: [spec].axis must be a nonempty string when any claim "
            "claims weight (core.md §6/W2)"
        )
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


def check_evidence_record(
    rep: Reporter, ctx: str, ev: dict, base_dir: Path, strict: bool,
    illustrative: bool = False, weighted: bool = False, subject_hash: str | None = None,
) -> None:
    # universal fields (result is an enum, checked separately below)
    for f in ("kind", "family", "ref", "tool", "record"):
        if not _is_nonempty_str(ev.get(f)):
            rep.error(f"{ctx}: universal field '{f}' must be a nonempty string")

    result = ev.get("result")
    if result not in RESULTS:
        rep.error(f"{ctx}: result must be one of {sorted(RESULTS)}, got {result!r}")

    kind = ev.get("kind")
    reg = KIND_REGISTRY.get(kind)
    if reg is None:
        rep.error(f"{ctx}: unknown evidence kind {kind!r} (not in the registry — evidence-types.md)")
    else:
        expected_family = reg["family"]
        if ev.get("family") != expected_family:
            rep.error(
                f"{ctx}: kind/family mismatch — kind {kind!r} requires family "
                f"{expected_family!r}, got {ev.get('family')!r}"
            )
        if reg.get("warn_reserved"):
            rep.warn(f"{ctx}: reserved kind — tool not adopted ({kind})")
        for field, tag in reg["extra"].items():
            _check_field(rep, ctx, ev, field, tag)

    # the `control` block (assurance-bands.md rule 6 / evidence-types.md "Control block") is
    # family-agnostic — ANY evidence record MAY carry one, regardless of its own kind/family
    # (kernel = mutated Lean theorem, bmc = mutated Kani harness, dynamic = cargo-mutants/stryker,
    # mechanical = seeded-bad gate fixture; the family lives on the record, not the control).
    control = ev.get("control")
    if control is not None:
        if not isinstance(control, dict):
            rep.error(f"{ctx}: 'control' must be a table (kind/expectation/observed/of_claim)")
        else:
            ck = control.get("kind")
            if ck not in CONTROL_KIND_VALUES:
                rep.error(
                    f"{ctx}: control.kind must be one of {sorted(CONTROL_KIND_VALUES)}, "
                    f"got {ck!r}"
                )
            cexp = control.get("expectation")
            if cexp not in CONTROL_EXPECTATION_VALUES:
                rep.error(
                    f"{ctx}: control.expectation must be one of "
                    f"{sorted(CONTROL_EXPECTATION_VALUES)}, got {cexp!r}"
                )
            cobs = control.get("observed")
            if cobs not in CONTROL_EXPECTATION_VALUES:
                # `observed` closed against the SAME token set as `expectation`: both name a
                # position on one closed axis (red | green | sat), and a free-text `observed`
                # value could never be compared against `expectation` for the literal-red
                # equality the band-lift gate and the F4 contradiction guard both depend on.
                rep.error(
                    f"{ctx}: control.observed must be one of "
                    f"{sorted(CONTROL_EXPECTATION_VALUES)}, got {cobs!r}"
                )
            if not _is_nonempty_str(control.get("of_claim")):
                rep.error(f"{ctx}: control.of_claim must be a nonempty string")

            # CS-23, the F4 contradiction guard (evidence-types.md "Control block" /
            # assurance-bands.md rule 6): a record cannot simultaneously claim its own check
            # passed (result = "pass") and that a mutation of the thing it checks was observed
            # red BY THIS SAME RECORD -- an observed-red mutation control describes a DIFFERENT
            # run (the mutant run) than the one `result` describes (the baseline run). Additive:
            # it does not replace or loosen any existing control-block rule.
            if ck == "mutation" and control.get("observed") == "red" and result == "pass":
                rep.error(
                    f"{ctx}: contradiction — control.kind == 'mutation' and control.observed == "
                    f"'red' implies this record's own result must not be 'pass' (an observed-red "
                    f"mutation control is a property of the mutant run, not the baseline run "
                    f"'result' describes; evidence-types.md 'Control block', F4)"
                )

    # CS-1/CS-2 (evidence-types.md): `method` (open, profile-defined) and `epistemic_tier`
    # (closed T1-T5) are REQUIRED AT FREEZE, TRANSITIONAL in this revision (no ledger reads them
    # yet beyond CS-4's coherence rule, below) -- an omission draws a WARN (not an error) naming
    # the field the frozen format will require (ruled 2026-08-28; the transition itself, and the
    # ratchet to a hard error at freeze, stay booked in maintainers/VALIDATOR-TODO.md — this is
    # only the validator closing the "an omission today draws neither an error nor a warning" gap
    # evidence-types.md used to disclose). Where a record DOES declare either field, both are
    # fully validated exactly as before. CS-3: where `method` names a token the shipped FV profile
    # knows, the profile-pinned tier is a CEILING on `epistemic_tier` — a producer never gets to
    # self-assign a stronger tier than the method earns, and a WEAKER declared tier is accepted
    # (conservative deflation is honest). Where `method` names a token with no
    # profile entry, the record's epistemic_tier is `indeterminate`, not silently accepted and not
    # a hard `invalid` (evidence-types.md, CS-3).
    method = ev.get("method")
    if method is None:
        rep.warn(
            f"{ctx}: 'method' is omitted — required at freeze, transitional this revision "
            f"(evidence-types.md CS-1/CS-2)"
        )
    elif not _is_nonempty_str(method):
        rep.error(f"{ctx}: method must be a nonempty string, got {method!r}")
    etier = ev.get("epistemic_tier")
    if etier is None:
        rep.warn(
            f"{ctx}: 'epistemic_tier' is omitted — required at freeze, transitional this "
            f"revision (evidence-types.md CS-1/CS-2)"
        )
    if etier is not None:
        if etier not in EPISTEMIC_TIERS:
            rep.error(
                f"{ctx}: epistemic_tier must be one of {sorted(EPISTEMIC_TIERS)}, got {etier!r}"
            )
        elif _is_nonempty_str(method):
            pinned = METHOD_EPISTEMIC_TIER.get(method)
            if pinned is None:
                rep.indet(
                    f"{ctx}: method {method!r} has no profile entry — its epistemic_tier is "
                    f"indeterminate (evidence-types.md CS-3)"
                )
            elif _tier_rank(etier) < _tier_rank(pinned):
                rep.error(
                    f"{ctx}: epistemic_tier {etier!r} is STRONGER than the FV profile's "
                    f"method → epistemic_tier table allows (method {method!r} is pinned to "
                    f"{pinned!r}) — the pinned tier is a CEILING: a producer may not self-assign "
                    f"a stronger tier than the method earns (evidence-types.md CS-3, ADR-002)"
                )

    # optional mutation-testing data fields (evidence-types.md "Control block"): DATA and GAPS,
    # never a score, and not tied to any particular kind — a dynamic mutation-testing record
    # (cargo-mutants/stryker) is the usual carrier, but nothing enforces that narrowly here.
    for field, tag in (("mutants_total", "int-pos"), ("mutants_caught", "int-nonneg")):
        if field in ev:
            _check_field(rep, ctx, ev, field, tag)

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

    # record pointer resolution
    record = ev.get("record")
    if _is_nonempty_str(record):
        target = (base_dir / record)
        if not target.exists():
            msg = f"{ctx}: record pointer does not exist: {record}"
            if strict:
                rep.error(msg)
            else:
                rep.warn(msg)

    # M11 (format.md "Content-hashing (M11)", ratified 2026-08-28) -- `record_hash`: the
    # evidence-record-domain content-hash of the file `record` points at, self-describing
    # ("sha-512:<128-hex>"). REQUIRED on a WEIGHTED claim's evidence (evidence-types.md, P9);
    # OPTIONAL on unweighted. A present-but-mismatched value is ALWAYS an error -- a detected
    # falsehood, not an absence. `illustrative` manifests stay shape-only: neither the
    # recomputation nor the required-on-weighted obligation fires against one (CS-21/22), since a
    # teaching example's `record` pointers are routinely fixture-only or absent.
    record_hash = ev.get("record_hash")
    if record_hash is not None:
        if not m11.is_well_formed(record_hash):
            rep.error(
                f"{ctx}: record_hash must be the self-describing form 'sha-512:<128-hex>', "
                f"got {record_hash!r}"
            )
        elif not illustrative and _is_nonempty_str(record):
            target = (base_dir / record)
            if target.is_file():
                actual = m11.digest_file("evidence-record", target)
                if actual != record_hash:
                    rep.error(
                        f"{ctx}: record_hash MISMATCH -- declared {record_hash!r}, actual "
                        f"{actual!r} (the record changed after it was cited, or the hash is "
                        f"wrong; format.md 'Content-hashing (M11)')"
                    )
            # a missing/non-file record target is already reported above ("record pointer does
            # not exist") -- not double-reported here as an unrecomputable hash.
    elif weighted and not illustrative:
        rep.error(
            f"{ctx}: record_hash is REQUIRED on a weighted claim's evidence (evidence-types.md, "
            f"P9) -- always-reference, never inline"
        )

    # design rule 4a (evidence-subject binding, dimensional fix) -- `subject_hash`: which
    # subject-content this record's `result` was actually computed against, in the same
    # self-describing M11 form. Where present, MUST equal [subject].subject_hash exactly; a
    # mismatch is a hard error, unconditionally. [subject].subject_hash is itself OPTIONAL in
    # this revision -- absent, there is nothing to check a record's subject_hash against, and the
    # check does not fire. Skipped on an illustrative manifest, same as record_hash above (CS-8 is
    # explicitly named in CS-21/22 as one of the checks illustrative manifests do not owe).
    ev_subject_hash = ev.get("subject_hash")
    if ev_subject_hash is not None:
        if not m11.is_well_formed(ev_subject_hash):
            rep.error(
                f"{ctx}: subject_hash must be the self-describing form 'sha-512:<128-hex>', "
                f"got {ev_subject_hash!r}"
            )
        elif not illustrative and subject_hash is not None and ev_subject_hash != subject_hash:
            rep.error(
                f"{ctx}: evidence-subject binding MISMATCH -- subject_hash {ev_subject_hash!r} "
                f"does not equal [subject].subject_hash {subject_hash!r} (format.md design rule "
                f"4a; [subject].commit is a separate git-domain identity and is never compared "
                f"against an M11 hash)"
            )

    # P3 (evidence-types.md "Control block", design ruled 2026-08-29): `captured_at_commit` --
    # OPTIONAL per-record PROVENANCE DISCLOSURE naming the git commit at which this record's
    # transcript was captured. It formalizes, as a real field, the ad hoc workaround this format
    # already tolerated (naming the actual capture commit inside the free-text `tool` field plus a
    # disclosure comment -- format.md's "Partial re-certification"). DISCLOSURE ONLY: it is NEVER a
    # second validity key -- content identity stays exactly where design rule 4a already put it
    # (subject_hash, above); nothing here compares captured_at_commit against anything or lets it
    # gate a record's admissibility. Shape only, reusing the same git-object-name pattern the
    # `[format]` self-location shas use (CS-16: 7-40 lowercase hex, git's own abbreviation floor).
    # A malformed value is a hard error, unconditionally -- the same fail-closed treatment
    # record_hash/subject_hash's own malformed-shape branches get, above: a disclosure that cannot
    # be understood is worse than no disclosure.
    captured_at_commit = ev.get("captured_at_commit")
    if captured_at_commit is not None:
        if (
            not isinstance(captured_at_commit, str)
            or not SELF_LOCATION_SHA_RE.match(captured_at_commit)
        ):
            rep.error(
                f"{ctx}: captured_at_commit must be 7-40 lowercase hex characters (a git object "
                f"name, full or abbreviated), got {captured_at_commit!r} (evidence-types.md "
                f"'Control block', P3)"
            )


def _band_reachable(band: str, passing: list[dict]) -> bool:
    kinds = {e.get("kind") for e in passing}
    families = {e.get("family") for e in passing}
    if band == "A4":
        return "lean-theorem" in kinds
    if band == "A3.5":
        return "flux-refinement" in kinds
    if band == "A3":
        return "kani-harness" in kinds
    if band == "A2":
        return bool(kinds & {"kani-harness", "miri"})
    if band == "A1":
        return "kani-harness" in kinds or "mechanical" in families or "dynamic" in families
    if band == "A0":
        return len(passing) >= 1
    return False  # pragma: no cover — band already validated against BANDS


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


def _control_lifts_band(
    e: dict, cid: str, allowed_kinds: set[str], allowed_carrier_families: set[str]
) -> bool:
    """A control LIFTS a band only when ALL of: it names THIS claim, its kind is in the per-band
    whitelist, its CARRIER record's family is species-compatible with the band (F2 — a
    judgment-family carrier, e.g. `human-review`, is never compatible with anything), and it is a
    literal observed-RED (F1 — `observed == expectation` alone is a weaker "behaved as predicted"
    notion: a green/green or sat/sat control behaved as predicted too, but proves nothing about
    THIS claim's oracle catching a bug, so it never lifts a band; only a literal red does)."""
    control = e.get("control")
    if not isinstance(control, dict):
        return False
    if control.get("of_claim") != cid:
        return False
    if control.get("kind") not in allowed_kinds:
        return False
    if e.get("family") not in allowed_carrier_families:
        return False
    return control.get("expectation") == "red" and control.get("observed") == "red"


def _reads_as_freedom_claim(claim: dict) -> bool:
    """Does this claim read as a FREEDOM / no-oracle claim (panic-freedom, crash-freedom,
    UB-freedom) rather than a functional one?

    THE ONE RECOGNIZER, deliberately. `assurance-bands.md`'s A1 row splits on claim CHARACTER --
    "yes for oracle-bearing dynamic; no for no-oracle hygiene/freedom" -- and until 2026-08-28 the
    codebase had that split in two places with two different rules: rule 4's advisory warning read
    the claim's own statement (FREEDOM_WORDS), while the control gate read the EVIDENCE SPECIES and
    exempted any claim carrying a passing `kani-harness`, whatever the claim said. A cold review
    passed a functional Kani `probe` at A1 with no control at all through the second one. A tool
    is not a claim character: the same harness proves panic-freedom in one row and a functional
    postcondition in the next -- which is exactly what band A3 is for -- so the exemption belongs
    to the claim, not to the tool, and there is now one function both call.

    A SHAPE FLOOR AND NOTHING MORE, same as `is_phrase`: it reads the producer's own wording and
    cannot tell a genuine freedom claim from a functional one phrased with the word "panic". That
    residual is why the recognizer only ever chooses between an ERROR and an advisory WARN here,
    never between valid and invalid on its own."""
    statement = (claim.get("statement") or "").lower()
    return any(w in statement for w in FREEDOM_WORDS)


def _check_control_gate(rep: Reporter, ctx: str, claim: dict, evidence: list[dict]) -> bool:
    """assurance-bands.md rule 6: oracle-bearing claims (A2/A3/A4, functional A1) need >=1
    observed-red control whose `of_claim` names THIS claim, whose `kind` is on the per-band
    whitelist, and whose CARRIER record is species-compatible with the band; else they're capped
    at A0. Returns True iff such a control was found (used by check_band_reachability, F3, to
    suppress the function-contracts warning when a red mutation control already backs the claim).

    Species reachability (kani-harness/lean-theorem/... setting the band ceiling) is judged from
    the record's own `result`; control validity does not depend on the record's own `result` (a
    kernel-family control record for a REJECTED mutated theorem legitimately has
    `result = "fail"` — the mutated proof did not typecheck, which IS the observed-red)."""
    cid = claim.get("id")
    band = claim.get("band")
    passing = [e for e in evidence if e.get("result") == "pass"]
    families = {e.get("family") for e in passing}
    kinds = {e.get("kind") for e in passing}

    # per-band control-kind whitelist (mirrors a pre-existing internal system's audit, which
    # requires kind=="mutation" for its controls-check): `planted-twin` proves the pipeline can
    # reject AT ALL — a satisfiability/pipeline (acknowledgment-witness) signal — never that THIS
    # claim's own oracle catches a mutation of THIS impl/theorem. It NEVER satisfies a band-lift
    # gate, at any band. It may still be recorded (disclosure evidence), it just doesn't count
    # here.
    requires_control = False
    allowed_kinds: set[str] = set()
    allowed_carrier_families: set[str] = set()
    if band in ("A3", "A4"):
        requires_control = True
        allowed_kinds = MUTATION_ONLY  # observed-red mutation of the impl/theorem — nothing else
        allowed_carrier_families = CARRIER_FAMILIES_FOR_BAND[band]
    elif band == "A2":
        requires_control = True
        allowed_kinds = MUTATION_OR_ABLATION  # mutation/ablation on the unsafe surface
        allowed_carrier_families = CARRIER_FAMILIES_FOR_BAND["A2"]
    elif band == "A1":
        has_kani = "kani-harness" in kinds
        has_mechanical = "mechanical" in families
        has_freedom_dynamic = bool(kinds & DYNAMIC_FREEDOM_KINDS)
        has_oracle_dynamic = bool(kinds & DYNAMIC_ORACLE_KINDS)
        # assurance-bands.md's one-sentence gate: "an ORACLE-BEARING claim (A2/A3/A4, and
        # functional A1) cannot exceed A0 without an observed-red control". At A1 that is a split
        # on claim CHARACTER, and the two no-control paths rule 4 names are:
        #
        #   * NO-ORACLE SPECIES, exempt by the species itself, whatever the claim says --
        #     `mechanical` hygiene (a lint has no behavioural oracle at all) and `miri`/`fuzz`
        #     (rule 4 names them: "there is no postcondition oracle to mutate"). A functional
        #     claim resting on one of these still gets the rule-4 advisory warn below.
        #   * A FREEDOM CLAIM, exempt by what the claim says. This is where `kani-harness` sits:
        #     the A1 species column reads "panic/UB-freedom", which is a claim character, not a
        #     tool. A zero-annotation harness proving panic-freedom needs no control (there is no
        #     postcondition to mutate); the SAME tool asserting a functional postcondition is
        #     oracle-bearing and does.
        #
        # Until 2026-08-28 any passing kani-harness defeated this gate outright, so a functional
        # Kani `probe` at A1 with no control passed --strict-weight (cold review, finding 5). The
        # exemption is now conditioned on the claim reading as a freedom claim, via the SAME
        # recognizer rule 4's advisory warning uses -- one recognizer, not two.
        kani_exempts = has_kani and _reads_as_freedom_claim(claim)
        no_oracle_species = has_mechanical or has_freedom_dynamic
        if (has_oracle_dynamic or has_kani) and not (kani_exempts or no_oracle_species):
            requires_control = True
            allowed_kinds = MUTATION_ONLY
            allowed_carrier_families = CARRIER_FAMILIES_FOR_BAND["A1"]

    has_control = requires_control and any(
        _control_lifts_band(e, cid, allowed_kinds, allowed_carrier_families) for e in evidence
    )

    if requires_control and not has_control:
        rep.error(
            f"{ctx}: band {band!r} is oracle-bearing and requires >=1 observed-red control "
            f"(control.kind must be one of {sorted(allowed_kinds)} — a 'planted-twin' never "
            f"satisfies this gate) whose of_claim names this claim; none found — capped at A0 "
            f"without one (assurance-bands.md rule 6)"
        )

    # F2: call out an otherwise-valid control (right claim, right kind, literal red) that sits on
    # a carrier record whose family the band doesn't accept — the "none found" error above is
    # enough to fail the gate, but this names the actionable reason instead of leaving the author
    # to guess (assurance-bands.md rule 6, carrier-family compatibility).
    if requires_control:
        for e in evidence:
            control = e.get("control")
            if not isinstance(control, dict):
                continue
            if control.get("of_claim") != cid:
                continue
            if control.get("kind") not in allowed_kinds:
                continue
            if control.get("expectation") != "red" or control.get("observed") != "red":
                continue
            if e.get("family") not in allowed_carrier_families:
                rep.error(
                    f"{ctx}: control's carrier family {e.get('family')!r} is not "
                    f"species-compatible with band {band!r} (needs carrier family in "
                    f"{sorted(allowed_carrier_families)}) — a control's carrier must match the "
                    f"band's species (never judgment) or it does not band-lift (assurance-bands.md "
                    f"rule 6)"
                )

    return has_control


def check_band_reachability(rep: Reporter, ctx: str, claim: dict, evidence: list[dict]) -> None:
    band = claim.get("band")
    passing = [e for e in evidence if e.get("result") == "pass"]

    if not _band_reachable(band, passing):
        rep.error(
            f"{ctx}: band {band!r} is not reachable by any passing evidence "
            f"(band overstatement — assurance-bands.md rule 2)"
        )

    has_lift_control = _check_control_gate(rep, ctx, claim, evidence)

    families = {e.get("family") for e in passing}
    kinds = {e.get("kind") for e in passing}

    if families and families == {"judgment"}:
        if band != "A0":
            rep.error(
                f"{ctx}: all evidence is judgment-family — band must be A0, got {band!r} "
                f"(evidence-types.md judgment rule)"
            )
    elif families and families == {"dynamic"}:
        if band not in {"A0", "A1"}:
            rep.error(
                f"{ctx}: all evidence is dynamic-family — band must be A0 or A1, got {band!r} "
                f"(assurance-bands.md rule 4)"
            )
        elif band == "A1":
            # assurance-bands.md rule 4's OTHER legitimate A1 path: an oracle-bearing dynamic
            # record backed by a mechanically-verified observed-red mutation control (kind ==
            # "mutation", of_claim naming THIS claim, carrier family "dynamic") reaches A1 without
            # the claim needing to read as a freedom claim at all -- that is exactly what
            # `has_lift_control` (computed by `_check_control_gate` above, same function the
            # control-gate ERROR uses) already proves when true. Only fall back to the
            # freedom-word heuristic when no such control was found, so an oracle-bearing claim
            # with no qualifying control (already flagged by the ERROR above) or a genuine
            # no-oracle freedom claim still gets judged on its wording.
            if not has_lift_control:
                if not _reads_as_freedom_claim(claim):
                    rep.warn(
                        f"{ctx}: dynamic-only evidence at band A1 but statement doesn't read as a "
                        f"freedom claim (no 'panic'/'crash'/'freedom'/'UB'), and no rule-4 "
                        f"observed-red mutation control backs it either (assurance-bands.md rule 4)"
                    )

    # F3 (tightened 2026-08-22): der's real A3 claims are legitimately assertion-style Kani
    # harnesses (no `-Z function-contracts`) backed by a red mutation control — that is NOT a
    # band overstatement (assurance-bands.md's A3 species text now says so explicitly), so this
    # warning fires ONLY when the flag is absent AND no red mutation control already backs the
    # claim. A claim with a valid band-lift control has already proven its oracle is non-vacuous
    # by the strongest available means; the flag-based heuristic becomes redundant.
    if band == "A3" and "kani-harness" in kinds and not has_lift_control:
        kani_semantics = [
            e.get("semantics", "") for e in passing if e.get("kind") == "kani-harness"
        ]
        if not any("function-contracts" in (s or "") for s in kani_semantics):
            rep.warn(
                f"{ctx}: band A3 kani-harness evidence semantics does not contain "
                f"'function-contracts', and no red mutation control backs the claim"
            )


def check_watched_fail_block(rep: Reporter, ctx: str, sv: dict) -> None:
    """core.md §4.1, structured (review round-2, finding 2). `watched_fail` was any nonempty
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
            f"is not a witness (core.md §4.1). Got {wf!r}"
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
                f"{ctx}: [claim.self_verify.watched_fail] requires {k!r} (core.md §4.1)"
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
                f"statement (core.md §4.1), got {wf[k]!r}"
            )
    date = wf.get("date")
    if isinstance(date, str) and not is_iso_date(date):
        rep.error(
            f"{ctx}: watched_fail.date must be an ISO date (YYYY-MM-DD) — 'when' is part of the "
            f"witness because a recipe watched to fail last year may not discriminate today "
            f"(core.md §4.1), got {date!r}"
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
                f"about this one (core.md §4.1; the of_claim rule). of_command={of_cmd!r}, "
                f"command={cmd!r}"
            )
    elif isinstance(of_cmd, str) and cmd is None:
        rep.error(
            f"{ctx}: watched_fail.of_command names a command, but this claim's self_verify "
            f"declares none to bind it to (core.md §4.1)"
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


def _has_watched_fail_witness(claim: dict) -> bool:
    """core.md §4.1 (P2): has this claim's recipe been watched to fail? Any ONE of three,
    reusing machinery the format already has rather than inventing a fourth:
      1. self_verify.watched_fail  -- a table naming what was perturbed, what was observed,
         when, and which command it was watched against;
      2. an observed-red control block on one of this claim's own evidence records
         (expectation == observed == "red" AND control.of_claim == this claim's id);
      3. self_verify.positive_control -- the absence-check instance of the same requirement,
         and ONLY on `not-covered` (§4.1 witness 3: on a `contract` row, showing a command can
         match some input says nothing about whether it would notice a broken implementation).
    A planted-twin never qualifies: it shows the pipeline can reject at all, not that THIS
    oracle catches a mutation of THIS item (assurance-bands.md rule 6)."""
    sv = claim.get("self_verify")
    if isinstance(sv, dict):
        if _watched_fail_block_is_valid(sv):
            return True
        if claim.get("grade") == "not-covered" and _is_nonempty_str(sv.get("positive_control")):
            return True
    cid = claim.get("id")
    evs = claim.get("evidence")
    if isinstance(evs, list):
        for ev in evs:
            if not isinstance(ev, dict):
                continue
            ctrl = ev.get("control")
            if not isinstance(ctrl, dict):
                continue
            if ctrl.get("kind") == "planted-twin":
                continue
            if (ctrl.get("expectation") == "red" and ctrl.get("observed") == "red"
                    and ctrl.get("of_claim") == cid):
                return True
    return False


def check_self_verify(rep: Reporter, ctx: str, claim: dict) -> None:
    """core.md §1/§3/§4: [claim.self_verify] — a consumer-side recipe, not evidence.
    REQUIRED (with a nonempty `command`) whenever `grade` is one of GRADES_REQUIRING_SELF_VERIFY;
    optional otherwise but structurally validated when present. Permitted on
    status = 'gap'/'parked' (0.1's one widening over the pre-freeze 'gap/parked claims carry no
    evidence' rule) — this function never looks at `claim.evidence`, so it cannot trip that
    check."""
    grade = claim.get("grade")
    sv = claim.get("self_verify")

    if grade in GRADES_REQUIRING_SELF_VERIFY:
        if not isinstance(sv, dict):
            rep.error(
                f"{ctx}: grade {grade!r} requires a [claim.self_verify] table with a nonempty "
                f"'command' (core.md §1/§3)"
            )
            return
        if not _is_nonempty_str(sv.get("command")):
            rep.error(
                f"{ctx}: grade {grade!r} requires self_verify.command to be a nonempty string "
                f"(core.md §1/§3)"
            )

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
            f"(core.md §8.2)"
        )

    check_watched_fail_block(rep, ctx, sv)

    # core.md §3 rule 2: `command` present => `expect` is required (a harness name alone is
    # not a recipe; "what green means" has to be written).
    if _is_nonempty_str(sv.get("command")) and not _is_nonempty_str(sv.get("expect")):
        rep.error(
            f"{ctx}: self_verify.command is present, so self_verify.expect is required and "
            f"must be nonempty (core.md §3)"
        )

    # core.md §4: grade = "not-covered" REQUIRES a nonempty positive_control, unconditionally
    # (not just when the command looks like an absence check) — a grep zero is a claim about the
    # pattern, not the code.
    if grade == "not-covered":
        pc = sv.get("positive_control")
        if not _is_nonempty_str(pc):
            rep.error(
                f"{ctx}: grade = 'not-covered' requires a nonempty self_verify.positive_control "
                f"(core.md §4)"
            )
        elif not _is_phrase(pc):
            # positive_control is a weighted-tier obligation AND this grade's §4.1 witness, so a
            # single token satisfying it was a phrase match earning weight -- the one thing §4.1
            # says may never happen. Same shape floor as watched_fail.perturbed/observed, and the
            # same honest limit: it cannot tell a real control from a plausible sentence.
            rep.error(
                f"{ctx}: self_verify.positive_control must NAME the input or target the same "
                f"command demonstrably matches — a single token is not a control (core.md §4), "
                f"got {pc!r}"
            )


def _is_valid_claim_bounds(v) -> bool:
    return bounds_token(v) is not None


def _check_contract_scope_coverage(
    rep: Reporter, ctx: str, claim: dict, qualifying: list[dict]
) -> None:
    """CS-4 conjunct 2 (core.md §2): a weighted `contract` claim needs qualifying evidence whose
    "declared scope (`bounds`, §5) covers the claim's declared domain".

    INTERIM AND STRUCTURAL, this revision — say what it decides and what it does not:

    * DECIDED, and refused: an `unbounded` claim whose only qualifying (passing, T1/T2) evidence
      records declare `bounded`. Containment fails on the tokens alone, with no free text to read:
      the claim says "the entire input domain", every record backing it says "a proper subset"
      (§5's two definitions), and no pair of free-text tails can make a subset into the whole. That
      is a DETECTED FALSEHOOD, not an absence, so it is a hard error rather than a §8.1
      weight-pending refusal — the same treatment a mismatched `record_hash` gets, for the same
      reason: the manifest stated something and its own evidence contradicts it.
    * DECIDED, and satisfied: any qualifying record declaring `unbounded`. An evidence scope
      covering the whole domain covers every claim domain inside it, bounded or unbounded.
    * NOT DECIDED, and said so: everything else — a `bounded` claim against `bounded` evidence
      (does `unwind=16, input<=12B` cover "inputs up to 8 bytes"? that is a comparison of free-text
      tails, and §5 is explicit that whether a stated limit is the REAL limit is reviewer work),
      and qualifying records that declare no `bounds` at all (`lean-theorem` requires `axioms` and
      `semantics`, not `bounds`). Both draw a transitional WARN naming the case as undecidable in
      this revision rather than a silent pass. Comparable structured domains — the machinery that
      would actually decide containment — are booked as a freeze obligation in
      `maintainers/VALIDATOR-TODO.md`; a checker that guessed at containment from prose would be
      inventing the answer, which is worse than naming the gap.

    The honest residual, stated: a producer can still write `bounds = "unbounded: all byte
    strings"` on the CLAIM and `bounds = "unbounded: all byte strings"` on a record that in fact
    ranged over one byte. This checks declarations against declarations. It closes the case where
    the two declarations visibly disagree, which is the one a document can decide."""
    claim_tok = bounds_token(claim.get("bounds"))
    if claim_tok is None:
        # A `contract` claim with no parseable claim-level bounds is already a hard error from
        # check_grade_companions (§5). Nothing to compare against; don't restate it.
        return

    ev_tokens = {bounds_token(ev.get("bounds")) for ev in qualifying}

    if "unbounded" in ev_tokens:
        return  # decided, and covered

    if claim_tok == "unbounded" and "bounded" in ev_tokens:
        rep.error(
            f"{ctx}: WEIGHT REFUSED: grade 'contract' with claim bounds "
            f"{claim.get('bounds')!r} (token 'unbounded' — the item's ENTIRE input domain, §5), "
            f"but every qualifying T1/T2 evidence record declares 'bounded' — a proper subset "
            f"of that domain. Bounded evidence cannot cover an unbounded claim, and reading a "
            f"bounded proof as unbounded is the classic overclaim §5 names. Either the claim is "
            f"`bounded` (say what the limit is), or it needs evidence that ranges over the whole "
            f"domain (core.md §2's scope-coverage conjunct)"
        )
        return

    undeclared = sum(1 for t in ev_tokens if t is None)
    reason = (
        "no qualifying evidence record declares `bounds` at all"
        if undeclared and len(ev_tokens) == 1
        else f"claim bounds token {claim_tok!r} against evidence token(s) "
             f"{sorted(t for t in ev_tokens if t)}, whose free-text tails this revision cannot "
             f"compare"
    )
    rep.warn(
        f"{ctx}: grade 'contract' scope coverage is UNDECIDABLE THIS REVISION — {reason}. The "
        f"claim is NOT refused on this ground and it is NOT confirmed covered: structural "
        f"containment is decided only between the `bounded`/`unbounded` tokens today (core.md "
        f"§2). Comparable structured domains are booked at freeze "
        f"(maintainers/VALIDATOR-TODO.md); until then this conjunct is reviewer work"
    )


def check_grade_companions(rep: Reporter, ctx: str, claim: dict) -> None:
    """core.md §1/§5: mandatory claim-level companion fields keyed by `grade`, distinct from
    self_verify (handled in check_self_verify). No-ops for grades that don't require any of
    these, and for a missing/invalid grade (already reported elsewhere)."""
    grade = claim.get("grade")

    if grade in GRADES_REQUIRING_BOUNDS:
        bounds = claim.get("bounds")
        if not _is_valid_claim_bounds(bounds):
            rep.error(
                f"{ctx}: grade {grade!r} requires a claim-level 'bounds' field, a nonempty "
                f"string starting with 'bounded' or 'unbounded' (core.md §5), got {bounds!r}"
            )
        elif not has_bounds_tail(bounds):
            # core.md §5: the token alone is not a declaration. §5 requires "plus free text
            # stating the actual limit", and the whole "canonical FOR INPUTS UP TO 16 BYTES"
            # argument rests on that text existing -- but nothing checked it, so `bounds =
            # "bounded"` satisfied a section that spends a page on why it must not.
            rep.error(
                f"{ctx}: WEIGHT REFUSED: bounds = {bounds!r} states which of the two tokens "
                f"applies and nothing about WHAT THE CHECK RANGED OVER. §5 requires the token "
                f"plus free text naming the actual limit (an unwind bound, a buffer size, a "
                f"monomorphic instantiation, or -- for 'unbounded' -- the domain it is complete "
                f"over). Shape only: that the stated limit is the REAL one is reviewer work"
            )

    if grade == "inspection-argued" and not _is_nonempty_str(claim.get("doc_ref")):
        rep.warn(
            f"{ctx}: grade = 'inspection-argued' SHOULD carry a nonempty claim-level 'doc_ref' "
            f"-- there is nothing to run, so the cited argument is all a reader has. Not an error: "
            f"this grade is never weight-eligible and W3 puts no obligations on unweighted claims"
        )

    if grade == "out-of-scope":
        scope_ref = claim.get("scope_ref")
        if not _is_nonempty_str(scope_ref):
            rep.error(
                f"{ctx}: grade = 'out-of-scope' requires a nonempty claim-level 'scope_ref' "
                f"(core.md §1)"
            )
        elif not is_scope_locator(scope_ref):
            # `out-of-scope` weight attaches to "the producer declared this, HERE" and to
            # nothing else, so the "here" has to be somewhere a reader can go. Free prose
            # ("nonsense", "we decided not to") records nothing and carried weight until
            # 2026-08-25 (review round-2, finding 3).
            rep.error(
                f"{ctx}: WEIGHT REFUSED: scope_ref must be a LOCATOR — {SCOPE_REF_EXPECTATION} "
                f"— not free prose. `out-of-scope` weight attaches to 'the producer declared "
                f"this, here', so a reader must be able to go there (core.md §1/§7.1), got "
                f"{scope_ref!r}"
            )

    if grade == "unspecified" and claim.get("clause_source") != "none":
        rep.warn(
            f"{ctx}: grade = 'unspecified' SHOULD carry clause_source = 'none' (core.md §1). "
            f"Not an error: this grade is never weight-eligible (W3)"
        )


def check_claims(
    rep: Reporter, doc: dict, base_dir: Path, strict: bool, illustrative: bool = False,
    subject_hash: str | None = None,
) -> list[dict]:
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
        cid = claim.get("id")
        ctx = f"claim {cid!r}" if _is_nonempty_str(cid) else ctx0

        # core.md §8.1 membership invariant (S4, review round-2 finding 4). `weight-pending` is
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
        if band not in BANDS:
            rep.error(f"{ctx}: band must be one of {sorted(BANDS)}, got {band!r}")
        elif band == "A3.5":
            rep.warn(f"{ctx}: reserved band — tool not adopted")

        # core.md §1/§2: `grade` is a REQUIRED claim field (tightened 2026-08-25 from the
        # pre-freeze OPTIONAL M6 tag) — the single largest break from the pre-freeze schema.
        grade = claim.get("grade")
        weight = claim.get("weight")
        if weight is not None and weight not in WEIGHT_VALUES:
            rep.error(
                f"{ctx}: weight must be one of {sorted(WEIGHT_VALUES)} (or omitted, "
                f"meaning unweighted), got {weight!r} (core.md W1)"
            )
        if _is_weighted(claim):
            if grade is None:
                rep.error(
                    f"{ctx}: WEIGHT REFUSED: a weighted claim requires 'grade' (core.md W2)"
                )
            elif grade in UNWEIGHTABLE_GRADES:
                rep.error(
                    f"{ctx}: WEIGHT REFUSED: grade {grade!r} has no deciding machinery and is "
                    f"never weight-eligible (core.md §1/W2)"
                )
            cs = claim.get("clause_source")
            if cs is None:
                # core.md W2.3 (P1, ADOPTED 2026-08-25): a weighted claim must record where
                # its clause text came from. Absence is indistinguishable from the two values
                # reserved to mean unweightable, and W1's rule is that the format never vouches
                # by silence. Transitional per §8.1: refused into weight-pending, an ERROR under
                # --strict-weight. Held until the end of this claim (see errors_before).
                pending_reasons.append("clause_source not recorded (W2.3, P1)")
            # core.md §4.1 / W2.5 (P2, ADOPTED 2026-08-25): a weighted recipe must carry a
            # witness that it CAN report the claim false. Applies to every grade that asserts a
            # check was performed; `out-of-scope` has no recipe and so has nothing to fail.
            # CS-22: NOT enforced against an `illustrative` manifest (a teaching example, not a
            # certificate).
            if (grade in GRADES_REQUIRING_SELF_VERIFY and not illustrative
                    and not _has_watched_fail_witness(claim)):
                pending_reasons.append(
                    "no watched-fail witness (W2.5, P2) — needs a "
                    "[claim.self_verify.watched_fail] table, an observed-red control naming "
                    "this claim, or (not-covered) a positive_control"
                )
            if cs in CLAUSE_SOURCES_UNWEIGHTABLE:
                rep.error(
                    f"{ctx}: WEIGHT REFUSED: clause_source {cs!r} is reserved to mean unweightable "
                    f"by design -- a clause read off its own evidence cannot be falsified "
                    f"(core.md W2)"
                )
        if grade is not None and grade not in CLAIM_GRADE_VALUES:
            rep.error(
                f"{ctx}: grade must be one of {sorted(CLAIM_GRADE_VALUES)}, got {grade!r} "
                f"(core.md §1)"
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
            check_grade_companions(rep, ctx, claim)
        else:
            rep.n_unweighted = getattr(rep, "n_unweighted", 0) + 1

        status = claim.get("status")
        if status not in STATUSES:
            rep.error(f"{ctx}: status must be one of {sorted(STATUSES)}, got {status!r}")

        if status == "parked" and not _is_nonempty_str(claim.get("parked_reason")):
            rep.error(f"{ctx}: status = 'parked' requires a nonempty 'parked_reason'")

        # core.md §7.3 (P4, ADOPTED): `blocked` is an escalation, and the escalation is only
        # greppable if it names what blocks it.
        if status == "blocked" and not _is_nonempty_str(claim.get("blocked_by")):
            rep.error(
                f"{ctx}: status = 'blocked' requires a nonempty 'blocked_by' naming what blocks "
                f"it — without it an escalation reads as a backlog entry (core.md §7.3)"
            )

        # core.md §7.1: status x grade coherence. ERROR on a claim that claims weight -- a
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

        # core.md §7.2 (P3, ADOPTED): a predicate item ranges over a second list, and its
        # honest status is a fraction. Declared, never inferred.
        item_kind = claim.get("item_kind")
        if item_kind is not None and item_kind not in ITEM_KIND_VALUES:
            rep.error(
                f"{ctx}: item_kind must be one of {sorted(ITEM_KIND_VALUES)} (or omitted, "
                f"meaning 'item'), got {item_kind!r} (core.md §7.2)"
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
                              f"(core.md §7.2)")
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
            check_evidence_record(
                rep, ectx, ev, base_dir, strict,
                illustrative=illustrative, weighted=_is_weighted(claim), subject_hash=subject_hash,
            )

        # a non-table [[claim.evidence]] entry is already reported above ("must be a table") --
        # every downstream consumer (control-mismatch, band-reachability) assumes each evidence
        # item is a dict and calls .get() on it without guarding, so it must see a filtered,
        # dict-only list, never the raw one (bug found via selftest coverage work, 2026-08-25:
        # an evidence array containing a bare string crashed validate() with AttributeError
        # instead of reporting a clean error).
        valid_evidence = [ev for ev in evidence if isinstance(ev, dict)]

        # §0.5/§1 (N1): `contract` requires a symbolic domain, so a weighted `contract` claim whose
        # evidence is ENTIRELY non-symbolic is refused. The canonical shape is a unit test carrying
        # a `contract` grade: it witnesses the points it enumerates and says nothing about the set,
        # which is the overclaim §1 exists to catch, and it validated cleanly until 2026-08-26.
        #
        # Scoped deliberately: only `contract`, and only when evidence records exist. §0.5 makes
        # the symbolic-domain demand of `contract` ALONE — it says nothing requiring `mechanical`
        # to carry mechanical-family evidence, and inventing that rule here would be the checker
        # legislating rather than enforcing.
        if _is_weighted(claim) and grade == "contract" and valid_evidence:
            # Passing-only: a NON-passing symbolic record (e.g. a `sorry`/failed Lean theorem) must
            # not satisfy the symbolic-domain demand — else a weighted `contract` whose only passing
            # evidence is a unit test launders the exact overclaim §0.5 exists to catch. Mirrors
            # check_band_reachability's `passing` filter. (soundness fix, 2026-08-27 red-team F1)
            fams = {ev.get("family") for ev in valid_evidence if ev.get("result") == "pass"}
            if not (fams & SYMBOLIC_DOMAIN_FAMILIES):
                rep.error(
                    f"{ctx}: WEIGHT REFUSED: grade 'contract' requires a SYMBOLIC domain "
                    f"(core.md §0.5), but every evidence record on this claim is of family "
                    f"{sorted(f for f in fams if f)} — none of "
                    f"{sorted(SYMBOLIC_DOMAIN_FAMILIES)}. Evidence that enumerates values "
                    f"witnesses points, not sets: §0.5 says a test is never `contract`. Either "
                    f"the claim is `probe`/`test-only`, or it needs evidence that reasons over "
                    f"the domain"
                )

        # CS-4 (core.md §2): the epistemic_tier/grade coherence rule, in its TWO conjuncts.
        #
        # Conjunct 1, the family/tier fragment: `contract` requires >=1 PASSING evidence record
        # whose `epistemic_tier` is T1/T2 — a plain existence check. Transitional per the SAME
        # §8.1 ratchet as W2.3/W2.5 (clause_source, watched-fail): a brand-new field no existing
        # producer has populated yet is refused into weight-pending, not silently accepted and not
        # an unconditional hard error on day one — an ERROR only under --strict-weight. CS-22: not
        # enforced against an `illustrative` manifest.
        #
        # Conjunct 2, SCOPE COVERAGE, is checked below in `_check_contract_scope_coverage`. It was
        # not checked at all until 2026-08-28, and the comment that stood here asserted it was
        # "already covered by ... the claim's own `bounds` field" — which is false, and false in
        # the direction this format exists to catch. Requiring the CLAIM to declare boundedness
        # says nothing about whether the EVIDENCE ranged over what the claim declares: a cold
        # review passed a weighted `contract` whose claim read `bounds = "unbounded: all byte
        # strings"` against Kani evidence bounded to one byte. Both halves of §2 are required, and
        # only one of them was there.
        qualifying = [
            ev for ev in valid_evidence
            if ev.get("result") == "pass" and ev.get("epistemic_tier") in ("T1", "T2")
        ]
        if _is_weighted(claim) and grade == "contract" and not illustrative:
            if not qualifying:
                pending_reasons.append(
                    "epistemic_tier/grade coherence not satisfied (core.md §2, CS-4) — needs at "
                    "least one PASSING evidence record with epistemic_tier in {T1, T2}"
                )
            else:
                # Only reached when conjunct 1 holds: with no qualifying record there is nothing
                # to compare the claim's domain against, and the refusal above already fires.
                _check_contract_scope_coverage(rep, ctx, claim, qualifying)

        # F4 (tightened 2026-08-22): runs for EVERY status, not just "evidenced" — a `partial`
        # claim's mis-pointed control is just as much a band-overstatement-by-proxy risk as an
        # evidenced one's, and this check used to be reachable only via check_band_reachability,
        # which never ran for partial/gap/parked claims.
        check_control_of_claim_mismatch(rep, ctx, claim, valid_evidence)

        if status == "evidenced" and band in BANDS and evidence:
            check_band_reachability(rep, ctx, claim, valid_evidence)

        # --- §8.1 membership, decided LAST (S4) ------------------------------------------
        # Pending means "was fine until the rules changed on 2026-08-25". A claim that raised
        # any error of its own is refused outright and is counted in NEITHER tier: it is not
        # weighted (the errors say so) and it is not pending (it broke a pre-adoption rule).
        if _is_weighted(claim):
            raised_own_error = len(rep.errors) > errors_before
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


def validate(path: Path, strict: bool, strict_weight: bool = False) -> Reporter:
    rep = Reporter(str(path), strict_weight=strict_weight)
    try:
        raw = path.read_bytes()
    except OSError as e:
        rep.error(f"cannot read file: {e}")
        return rep
    try:
        doc = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as e:
        rep.error(f"TOML parse error: {e}")
        return rep
    except UnicodeDecodeError as e:
        rep.error(f"not valid UTF-8: {e}")
        return rep

    illustrative = check_format(rep, doc)
    rep.illustrative = illustrative
    check_subject(rep, doc)
    _claims_for_weight = doc.get("claim") or []
    any_weighted = isinstance(_claims_for_weight, list) and any(
        isinstance(c, dict) and _is_weighted(c) for c in _claims_for_weight
    )
    check_spec(rep, doc, any_weighted)
    # core.md §0.6 / CS-22: an `illustrative` manifest stays shape-only -- record-pointer
    # existence (the `--strict` flag) is one of the things NOT enforced against it, even when the
    # gate runs `--strict` on everything else.
    effective_strict = strict and not illustrative
    subj = doc.get("subject")
    subject_hash = subj.get("subject_hash") if isinstance(subj, dict) else None
    # F-3 (audit fix, RULED): [subject].record_root -- when declared (and well-shaped; a
    # malformed value is already reported by check_subject above and simply falls back to the
    # manifest-relative default here rather than compounding the error), every `record` pointer
    # on this manifest resolves against it instead of the manifest file's own directory. Absolute
    # record_root is used as-is; a relative one resolves against the manifest's own directory --
    # the same directory it would otherwise default to.
    record_root = subj.get("record_root") if isinstance(subj, dict) else None
    base_dir = path.parent
    if _is_nonempty_str(record_root):
        rr = Path(record_root)
        base_dir = rr if rr.is_absolute() else (path.parent / rr)
    claims = check_claims(rep, doc, base_dir, effective_strict, illustrative, subject_hash)
    check_coverage(rep, doc, claims)
    return rep


# --------------------------------------------------------------------------
# Selftest fixtures
# --------------------------------------------------------------------------

GOOD_FIXTURE = """
[format]
id = "acceptance/0"
shape         = "single-file"
spec_id       = "acceptance-format"
spec_sha      = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
validator_sha = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
generated_by  = "check_acceptance.py@selftest"
generated_at  = "2026-08-27T00:00:00Z"

[subject]
name   = "selftest-lib"
kind   = "rust-crate"
commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
dirty  = false

[spec]
path    = "SPEC.md"
version = "v1"
axis    = "public API surface of selftest-lib"

[coverage]
clauses_total = 7
claims_total  = 7

[[claim]]
id        = "G-001"
clause    = "S-1"
item      = "src/lib.rs::a"
statement = "a never panics"
band      = "A1"
grade     = "probe"
bounds    = "bounded: unwind=8"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "check_a_no_panic"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-a.json"

  [claim.self_verify]
  command = "cargo kani --harness check_a_no_panic"
  expect  = "VERIFICATION:- SUCCESSFUL"

[[claim]]
id        = "G-002"
clause    = "S-2"
item      = "src/lib.rs::b"
statement = "b is memory safe in its unsafe block"
band      = "A2"
grade     = "probe"
bounds    = "bounded: unwind=8"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_b_memsafe"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-b.json"

  # bmc-family ABLATION control (A2 whitelist = mutation OR ablation, assurance-bands.md rule 6,
  # tightened 2026-08-22): the harness's bounds-check precondition is removed and the SAME
  # unsafe-block property must now break (observed red).
  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_b_memsafe (ablated: bounds-check precondition removed)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-b-control.json"

    [claim.evidence.control]
    kind        = "ablation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-002"

  [claim.self_verify]
  command = "cargo kani --harness verify_b_memsafe"
  expect  = "VERIFICATION:- SUCCESSFUL"

[[claim]]
id        = "G-003"
clause    = "S-3"
item      = "src/lib.rs::c"
statement = "c meets its function contract"
band      = "A3"
grade     = "contract"
bounds    = "unbounded (function-contracts, symbolic domain)"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c.json"

  # bmc-family mutation control: the SAME harness re-run against a mutated impl, which must
  # now fail (observed red) — der's real mechanism for its Kani contract controls.
  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract (mutant: off-by-one in c)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f + cargo-mutants@25.x"
  bounds    = "bounded: unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c-mutants.json"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-003"

  [claim.self_verify]
  command = "cargo kani --harness verify_c_contract"
  expect  = "VERIFICATION:- SUCCESSFUL"

[[claim]]
id        = "G-004"
clause    = "S-4"
item      = "src/lib.rs::d"
statement = "d matches its foundational spec"
band      = "A4"
grade     = "contract"
bounds    = "unbounded (Lean kernel)"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff"
  result    = "pass"
  tool      = "lean4@4.x-pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d.lean"

  # kernel-family mutation control: the theorem source is mutated and re-checked; the kernel
  # must REJECT it (typecheck fails, observed red) — der's real Lean-lid mutation controls.
  [[claim.evidence]]
  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff (mutant: flipped comparison)"
  result    = "fail"
  tool      = "lean4@4.x-pinned + lean-mutate@pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d-mutants.lean"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-004"

  [claim.self_verify]
  command = "lake env lean lean/D.lean"
  expect  = "no errors"

[[claim]]
id        = "G-005"
clause    = "S-5"
item      = "src/lib.rs::e"
statement = "e was reviewed"
band      = "A0"
grade     = "inspection-argued"
doc_ref   = "docs/e-review.md"
status    = "evidenced"

  [[claim.evidence]]
  kind     = "human-review"
  family   = "judgment"
  ref      = "e-review"
  result   = "pass"
  tool     = "manual"
  reviewer = "reviewer-a"
  record   = "evidence/does-not-exist-e.txt"

[[claim]]
id        = "G-006"
clause    = "S-6"
item      = "src/lib.rs::f"
statement = "f timing behavior"
band      = "A0"
grade     = "not-covered"
status    = "gap"

  [claim.self_verify]
  command = "grep -rn 'timing_budget' src/"
  expect  = "no output"
  positive_control = "grep -rn 'panic' src/ matches multiple lines"

[[claim]]
id        = "G-007"
clause    = "S-7"
item      = "src/lib.rs::g"
statement = "g contract, tool unsupported"
band      = "A3"
grade     = "not-covered"
status    = "parked"
parked_reason = "kani unsupported_construct — tool change needed"

  [claim.self_verify]
  command = "cargo kani --harness verify_g_contract"
  expect  = "VERIFICATION:- SUCCESSFUL"
  positive_control = "grep -rn 'unsupported_construct' target/kani-log matches"
"""


# --------------------------------------------------------------------------
# Standalone control-gate fixtures (assurance-bands.md rule 6) — isolated single-claim
# manifests, distinct from GOOD_FIXTURE's bundled coverage, per the four scenarios the
# control gate must draw a hard line around.
# --------------------------------------------------------------------------

# P9 (evidence-types.md): record_hash is REQUIRED on a weighted claim's evidence. A placeholder
# is safe for fixtures built through _mini_manifest below: they reference fictitious `record`
# paths ("does-not-exist-*") almost universally, and check_evidence_record only recomputes the
# hash when the pointed-to file actually exists on disk -- it never does for these fixtures, so
# the placeholder satisfies the presence obligation without ever being compared against real
# bytes. Fixtures that exercise record_hash behaviour directly (match/mismatch) set their own
# value and are excluded via the "record_hash" presence check in _mini_manifest, below.
_DUMMY_RECORD_HASH = "sha-512:" + "0" * 128


def _inject_dummy_record_hash(text: str) -> str:
    def _repl(m: re.Match) -> str:
        return f'{m.group(0)}\n{m.group(1)}record_hash = "{_DUMMY_RECORD_HASH}"'

    return re.sub(r'(?m)^(\s*)record\s*=\s*"[^"]*"\s*$', _repl, text)


def _mini_manifest(claim_toml: str, auto_record_hash: bool = True) -> str:
    # core.md W1: weight defaults to ABSENT, and the mandatory anti-overclaim
    # machinery only fires on claims that CLAIM weight. These fixtures exist to
    # exercise that machinery, so a claim that does not say otherwise is made
    # weighted here. Fixtures for the unweighted tier declare it explicitly.
    if "weight" not in claim_toml:
        m = re.search(r'(?m)^grade\s*=\s*"([^"]+)"', claim_toml)
        cs = re.search(r'(?m)^clause_source\s*=\s*"([^"]+)"', claim_toml)
        unweightable = (
            (m and m.group(1) in UNWEIGHTABLE_GRADES)
            or (cs and cs.group(1) in CLAUSE_SOURCES_UNWEIGHTABLE)
        )
        tier = "unweighted" if unweightable else "weighted"
        claim_toml = re.sub(r"(?m)^(\[\[claim\]\])$",
                            r'\1\nweight    = "%s"' % tier, claim_toml, count=1)
        is_weighted = (tier == "weighted")
    else:
        is_weighted = bool(re.search(r'(?m)^weight\s*=\s*"weighted"', claim_toml))
    # auto_record_hash=False: for fixtures that deliberately exercise the ABSENT-on-weighted (P9)
    # or illustrative-skip (CS-21/22) behaviour, where the whole point is that no record_hash is
    # injected.
    if auto_record_hash and is_weighted and "record_hash" not in claim_toml:
        claim_toml = _inject_dummy_record_hash(claim_toml)
    return f"""
[format]
id = "acceptance/0"
shape         = "single-file"
spec_id       = "acceptance-format"
spec_sha      = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
validator_sha = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
generated_by  = "check_acceptance.py@selftest"
generated_at  = "2026-08-27T00:00:00Z"

[subject]
name   = "selftest-lib"
kind   = "rust-crate"
commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
dirty  = false

[spec]
path    = "SPEC.md"
version = "v1"
axis    = "public API surface of selftest-lib"

[coverage]
clauses_total = 1
claims_total  = 1

{claim_toml}
"""


_A3_CLAIM_WITH_CONTROL = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::c"
statement = "c meets its function contract"
band      = "A3"
grade     = "contract"
bounds    = "unbounded (function-contracts, symbolic domain)"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c.json"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract (mutant: off-by-one in c)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f + cargo-mutants@25.x"
  bounds    = "bounded: unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c-mutants.json"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C-001"

  [claim.self_verify]
  command = "cargo kani --harness verify_c_contract"
  expect  = "VERIFICATION:- SUCCESSFUL"
"""

# der's real, previously-impossible case: a KERNEL-family control (a mutated Lean theorem the
# kernel rejects) lifting an A4 claim — see der's Lean-lid mutation controls, STATUS 2026-08-22.
_A4_CLAIM_WITH_KERNEL_CONTROL = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "lean/D.lean"
statement = "d matches its foundational spec"
band      = "A4"
grade     = "contract"
bounds    = "unbounded (Lean kernel)"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff"
  result    = "pass"
  tool      = "lean4@4.x-pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d.lean"

  [[claim.evidence]]
  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff (mutant: flipped comparison)"
  result    = "fail"
  tool      = "lean4@4.x-pinned + lean-mutate@pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d-mutant.lean"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C-001"

  [claim.self_verify]
  command = "lake env lean lean/D.lean"
  expect  = "no errors"
"""

_A1_HYGIENE_NO_CONTROL_CLAIM = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::a"
statement = "a never panics"
band      = "A1"
grade     = "probe"
bounds    = "bounded: unwind=8"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "check_a_no_panic"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-a.json"

  [claim.self_verify]
  command = "cargo kani --harness check_a_no_panic"
  expect  = "VERIFICATION:- SUCCESSFUL"
"""

# per-band control-kind whitelist (assurance-bands.md rule 6, tightened 2026-08-22): A2 accepts
# mutation OR ablation, never planted-twin. Base fixture uses ablation (must PASS); the
# planted-twin variant below (same shape, control.kind swapped) must FAIL.
_A2_CLAIM_WITH_ABLATION_CONTROL = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::b"
statement = "b is memory safe in its unsafe block"
band      = "A2"
grade     = "contract"
bounds    = "bounded: unwind=8"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_b_memsafe"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-b.json"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_b_memsafe (ablated: bounds-check precondition removed)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-b-control.json"

    [claim.evidence.control]
    kind        = "ablation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C-001"

  [claim.self_verify]
  command = "cargo kani --harness verify_b_memsafe"
  expect  = "VERIFICATION:- SUCCESSFUL"
"""

# F3 (tightened 2026-08-22): der's real A3 module claims are assertion-style Kani harnesses — a
# zero-annotation harness with an internal assert, NOT `-Z function-contracts` — backed by a red
# bmc mutation control. That is not an under-claim; the widened A3 species text in
# assurance-bands.md says so. `record` points at "acceptance.toml" (the manifest's own generated
# file, guaranteed to exist alongside itself) so this fixture can be checked with --strict too.
_DER_SHAPED_A3_ASSERTION_CLAIM = """
[[claim]]
id        = "K-integer"
clause    = "PM/integer"
item      = "der-verified/src/integer.rs"
statement = "decode rejects non-minimal INTEGER encodings"
band      = "A3"
grade     = "contract"
clause_source = "external-standard"
bounds    = "bounded: unwind=16, input<=12B"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  method    = "kani-harness"
  epistemic_tier = "T2"
  ref       = "integer::verify_rejects_nonminimal"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=16, input<=12B"
  semantics = ""
  record    = "evidence/does-not-exist-k-integer.json"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  method    = "kani-harness"
  epistemic_tier = "T2"
  ref       = "integer::verify_rejects_nonminimal (mutant: dropped padding check)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f + cargo-mutants@25.x"
  bounds    = "bounded: unwind=16, input<=12B"
  semantics = ""
  record    = "evidence/does-not-exist-k-integer-mutants.json"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "K-integer"

  [claim.self_verify]
  command = "cargo kani --harness integer::verify_rejects_nonminimal"
  expect  = "VERIFICATION:- SUCCESSFUL"
"""

# F4 (tightened 2026-08-22): a `partial` claim's control can be mis-pointed at a DIFFERENT
# existing claim too — this must be caught even though `partial` never asserts its band is
# reached (check_control_of_claim_mismatch now runs for every status).
_PARTIAL_CLAIM_WITH_MISPOINTED_CONTROL = """
[format]
id = "acceptance/0"
shape         = "single-file"
spec_id       = "acceptance-format"
spec_sha      = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
validator_sha = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
generated_by  = "check_acceptance.py@selftest"
generated_at  = "2026-08-27T00:00:00Z"

[subject]
name   = "selftest-lib"
kind   = "rust-crate"
commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
dirty  = false

[spec]
path    = "SPEC.md"
version = "v1"
axis    = "public API surface of selftest-lib"

[coverage]
clauses_total = 2
claims_total  = 2

[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::c"
statement = "c partially meets its contract"
band      = "A3"
grade     = "test-only"
status    = "partial"

  [[claim.evidence]]
  kind   = "unit-test"
  family = "dynamic"
  ref    = "c::tests"
  result = "pass"
  tool   = "rustc@1.79-pinned"
  cases  = 3
  record = "evidence/does-not-exist.log"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C-002"

  [claim.self_verify]
  command = "cargo test c"
  expect  = "test result: ok"

[[claim]]
id        = "C-002"
clause    = "S-2"
item      = "src/lib.rs::d"
statement = "d is unrelated"
band      = "A0"
grade     = "ungraded"
status    = "gap"
"""


# core.md fixtures — clause_source / self_verify / spec.axis+external /
# coverage.denominator+slice_note (denominator/slice_note/clause_source="test-name" are
# CLAIM-CLASSES-AWAITING-WEIGHT.md EXPERIMENTAL fields: parseable, shape-checked, not meaning-enforced).

_GAP_CLAIM_WITH_SELF_VERIFY = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::h"
statement = "h has no evidence yet"
band      = "A0"
grade     = "not-covered"
status    = "gap"

  [claim.self_verify]
  command = "grep -rn 'h_impl' src/"
  expect  = "no output"
  positive_control = "grep -rn 'g_impl' src/ matches 3 lines"
"""

# core.md §1/§7.1: `out-of-scope` says the producer deliberately does not claim the item, so
# its status is one of the no-check statuses and it has no recipe. `scope_ref` is a LOCATOR.
_OUT_OF_SCOPE_CLAIM = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::h"
statement = "h is deliberately not implemented"
band      = "A0"
grade     = "out-of-scope"
scope_ref = "docs/scope.md#a"
status    = "gap"
"""

_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::h"
statement = "h is not implemented"
band      = "A0"
status    = "gap"
grade     = "not-covered"

  [claim.self_verify]
  command = "grep -rn 'h_impl' src/"
  expect  = "no output"
"""

_CLAIM_SELF_VERIFY_COMMAND_NO_EXPECT = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::h"
statement = "h self-verify recipe"
band      = "A0"
grade     = "not-covered"
status    = "gap"

  [claim.self_verify]
  positive_control = "grep -rn 'g_impl' src/ matches 3 lines"
  command = "cargo test h"
"""


# --------------------------------------------------------------------------
# Enforcement-site coverage fixtures (external-review finding, 2026-08-25): 47
# of the file's 83 rep.error/rep.warn/rep.weight_pending call sites never
# fired in any prior selftest fixture -- the fixtures asserted only the
# passing direction, so "a check nobody watched fail is untested" applied to
# nearly half the validator. Each fixture below exists to fire ONE named
# site; confirmed red-before/green-after by instrumentation, not by reading.
# --------------------------------------------------------------------------

# a dynamic-only (unit-test) claim -- reused (via targeted .replace()) to
# fire the "cases" int-pos check, a missing universal evidence field, an
# invalid `result` enum value, and the A2-band dynamic-only-species error.
_UNIT_TEST_DYNAMIC_CLAIM = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::t"
statement = "t behavior is tested"
band      = "A1"
grade     = "test-only"
status    = "evidenced"

  [[claim.evidence]]
  kind   = "unit-test"
  family = "dynamic"
  ref    = "t::tests"
  result = "pass"
  tool   = "rustc@1.79-pinned"
  cases  = 3
  record = "evidence/does-not-exist-t.log"

  [claim.self_verify]
  command = "cargo test t"
  expect  = "test result: ok"
"""

# freedom-shaped (miri) dynamic-only evidence at A1 with a statement that
# doesn't read as a freedom claim -- fires the A1 dynamic-only advisory warn
# without tripping the A1 control-gate (miri is DYNAMIC_FREEDOM_KINDS).
_MIRI_A1_NO_FREEDOM_WORDS_CLAIM = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::u"
statement = "u returns the correct value"
band      = "A1"
grade     = "mechanical"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "miri"
  family    = "dynamic"
  ref       = "miri_u"
  result    = "pass"
  tool      = "miri@nightly-pinned"
  semantics = "stacked-borrows"
  record    = "evidence/does-not-exist-u.log"

  [claim.self_verify]
  command = "cargo miri test u"
  expect  = "test result: ok"
"""

# assurance-bands.md rule 4's OTHER legitimate A1 path: oracle-bearing (unit-test) dynamic
# evidence backed by a matching observed-red mutation control -- the statement deliberately
# reads as a plain behavioural claim (no freedom words), because the rule-4 evidence shape,
# not the wording, is what should suppress the advisory warn.
_A1_RULE4_CONTROL_CLAIM = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::t"
statement = "t behavior is tested"
band      = "A1"
grade     = "test-only"
status    = "evidenced"

  [[claim.evidence]]
  kind   = "unit-test"
  family = "dynamic"
  ref    = "t::tests"
  result = "pass"
  tool   = "rustc@1.79-pinned"
  cases  = 3
  record = "evidence/does-not-exist-t.log"

  [[claim.evidence]]
  kind   = "unit-test"
  family = "dynamic"
  ref    = "t::tests (mutant: off-by-one in t)"
  result = "fail"
  tool   = "rustc@1.79-pinned + cargo-mutants@25.x"
  cases  = 3
  record = "evidence/does-not-exist-t-mutants.log"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C-001"

  [claim.self_verify]
  command = "cargo test t"
  expect  = "test result: ok"
"""

# flux-refinement (reserved kind) at the reserved A3.5 band -- fires BOTH
# reserved-kind and reserved-band advisory warns on a manifest that
# otherwise validates cleanly (KIND_REGISTRY's flux-refinement is
# warn_reserved; A3.5 is BANDS' only reserved band).
_FLUX_REFINEMENT_A35_CLAIM = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::r"
statement = "r meets its refinement type"
band      = "A3.5"
grade     = "probe"
bounds    = "bounded: refinement domain"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "flux-refinement"
  family    = "smt-refinement"
  ref       = "verify_r_refinement"
  result    = "pass"
  tool      = "flux@pinned"
  bounds    = "unbounded: refinement domain: i32"
  semantics = "liquid types"
  record    = "evidence/does-not-exist-r.json"

  [claim.self_verify]
  command = "cargo flux --harness verify_r_refinement"
  expect  = "flux: verified"
"""

# grade not in GRADES_REQUIRING_SELF_VERIFY (so check_self_verify does not
# early-return before the type check), self_verify given as a bare string
# instead of a table -- fires the "[claim.self_verify] must be a table"
# branch. weight is forced explicitly (rather than left to _mini_manifest's
# auto-detection) so check_self_verify -- gated on _is_weighted -- runs at
# all despite "ungraded" being an UNWEIGHTABLE_GRADES member.
_UNGRADED_CLAIM_BAD_SELF_VERIFY_TYPE = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::v"
statement = "v has no decided grade yet"
band      = "A0"
grade     = "ungraded"
weight    = "weighted"
status    = "gap"
self_verify = "oops"
"""

# a weighted claim graded "inspection-argued" with no doc_ref -- fires the
# doc_ref advisory warn (check_grade_companions only runs for weighted
# claims, so the grade must be forced weighted explicitly here; this also
# fires the WEIGHT REFUSED "no deciding machinery" error, already covered
# elsewhere, alongside it).
_WEIGHTED_INSPECTION_ARGUED_NO_DOC_REF = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::w"
statement = "w was reviewed"
band      = "A0"
grade     = "inspection-argued"
weight    = "weighted"
status    = "gap"
"""

# a weighted claim graded "unspecified" with no clause_source = "none" --
# fires the clause_source advisory warn, same weighted-forcing rationale as
# the inspection-argued fixture above.
_WEIGHTED_UNSPECIFIED_NO_CLAUSE_SOURCE_NONE = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::x"
statement = "x behavior is unspecified"
band      = "A0"
grade     = "unspecified"
weight    = "weighted"
status    = "gap"
"""

# an explicit, out-of-vocabulary `weight` value -- fires the weight-enum
# check (distinct from `weight` simply being absent, which means unweighted
# and is never an error).
_CLAIM_BAD_WEIGHT_VALUE = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::y"
statement = "y has a bogus weight value"
band      = "A0"
grade     = "ungraded"
weight    = "bogus"
status    = "gap"
"""

# top-level `claim` present but not an array of tables -- fires the
# "[[claim]] entries must form an array of tables" branch. A full standalone
# manifest (not a _mini_manifest fragment): _mini_manifest always builds a
# well-formed [[claim]] array itself.
_CLAIM_NOT_ARRAY_MANIFEST = """
claim = "oops"

[format]
id = "acceptance/0"
shape         = "single-file"
spec_id       = "acceptance-format"
spec_sha      = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
validator_sha = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
generated_by  = "check_acceptance.py@selftest"
generated_at  = "2026-08-27T00:00:00Z"

[subject]
name   = "selftest-lib"
kind   = "rust-crate"
commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
dirty  = false

[spec]
path    = "SPEC.md"
version = "v1"
axis    = "public API surface of selftest-lib"

[coverage]
clauses_total = 1
claims_total  = 0
"""

# claim.evidence present but not a list (a bare string) -- fires the
# "[[claim.evidence]] must be an array of tables" branch.
_CLAIM_EVIDENCE_NOT_ARRAY = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::z"
statement = "z has malformed evidence field"
band      = "A0"
grade     = "ungraded"
status    = "gap"
evidence  = "oops"
"""

# claim.evidence is a list, but one entry is not a table -- fires the
# per-entry "must be a table" branch. status = "gap" (not "evidenced") so
# this never reaches check_band_reachability, which -- unlike
# check_control_of_claim_mismatch -- historically had no defensive
# isinstance guard of its own; see the check_claims fix (2026-08-25) that
# now filters non-dict evidence entries once, upstream of both consumers.
_CLAIM_EVIDENCE_ENTRY_NOT_TABLE = """
[[claim]]
id        = "C-001"
clause    = "S-1"
item      = "src/lib.rs::z2"
statement = "z2 has a malformed evidence entry"
band      = "A0"
grade     = "ungraded"
status    = "gap"
evidence  = ["oops"]
"""


def _run_case(name: str, toml_text: str, expect_pass: bool, expect_substr: str | None = None,
              strict_weight: bool = False, expect_state: str | None = None) -> str | None:
    """Returns None on success, or a failure description string. `expect_state` (CS-20):
    "invalid" (the default when `expect_pass` is False) or "indeterminate" -- asserts
    `rep.state()` exactly, and looks for `expect_substr` in the matching message bucket
    (`rep.errors` for "invalid", `rep.indeterminate` for "indeterminate")."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "acceptance.toml"
        p.write_text(toml_text)
        rep = validate(p, strict=False, strict_weight=strict_weight)
        passed = rep.ok()
        if expect_pass:
            if not passed:
                return f"{name}: expected PASS, got errors: {rep.errors}, indeterminate: {rep.indeterminate}"
            return None
        else:
            if passed:
                return f"{name}: expected FAIL, but validation passed"
            state = expect_state or "invalid"
            if rep.state() != state:
                return (
                    f"{name}: expected state {state!r}, got {rep.state()!r} "
                    f"(errors: {rep.errors!r}, indeterminate: {rep.indeterminate!r})"
                )
            bucket = rep.errors if state == "invalid" else rep.indeterminate
            all_msgs = " | ".join(bucket)
            if expect_substr and expect_substr not in all_msgs:
                return (
                    f"{name}: failed, but not for the expected reason — wanted substring "
                    f"{expect_substr!r} in {state} messages {bucket!r}"
                )
            return None


def selftest() -> int:
    failures: list[str] = []
    count = 0

    count += 1
    r = _run_case("good fixture", GOOD_FIXTURE, expect_pass=True)
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A3 claim with a matching observed-red bmc mutation control",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A4 claim with a matching observed-red KERNEL mutation control "
        "(family-agnostic control — der's real Lean-lid case, previously impossible)",
        _mini_manifest(_A4_CLAIM_WITH_KERNEL_CONTROL),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A1 hygiene claim with no control",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A2 claim with an ablation control PASSES (per-band whitelist)",
        _mini_manifest(_A2_CLAIM_WITH_ABLATION_CONTROL),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A2 claim with ONLY a planted-twin control FAILS (per-band whitelist — "
        "planted-twin never satisfies the band-lift gate)",
        _mini_manifest(_A2_CLAIM_WITH_ABLATION_CONTROL.replace(
            'kind        = "ablation"', 'kind        = "planted-twin"'
        )),
        expect_pass=False,
        expect_substr="requires >=1 observed-red control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: dangling control.of_claim (phantom claim id) is an error",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'of_claim    = "C-001"', 'of_claim    = "A-999"'
        )),
        expect_pass=False,
        expect_substr="does not match any claim id in this manifest",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A3 claim with no control",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            """
  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract (mutant: off-by-one in c)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f + cargo-mutants@25.x"
  bounds    = "bounded: unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c-mutants.json"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C-001"
""",
            "",
        )),
        expect_pass=False,
        expect_substr="requires >=1 observed-red control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: A4 claim with no control",
        _mini_manifest(_A4_CLAIM_WITH_KERNEL_CONTROL.replace(
            """
  [[claim.evidence]]
  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff (mutant: flipped comparison)"
  result    = "fail"
  tool      = "lean4@4.x-pinned + lean-mutate@pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d-mutant.lean"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C-001"
""",
            "",
        )),
        expect_pass=False,
        expect_substr="requires >=1 observed-red control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: control whose of_claim names a different claim doesn't lift this one",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'of_claim    = "C-001"', 'of_claim    = "SOME-OTHER-CLAIM"'
        )),
        expect_pass=False,
        expect_substr="does not name this claim",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: control that observed the WRONG thing (observed != expectation) "
        "doesn't satisfy the gate",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'observed    = "red"', 'observed    = "green"'
        )),
        expect_pass=False,
        expect_substr="requires >=1 observed-red control",
    )
    if r:
        failures.append(r)

    # F1 (tightened 2026-08-22): observed==expectation alone is NOT enough to band-lift — a
    # green/green (or sat/sat) control "behaved as predicted" but is not a literal red, so it must
    # NOT lift A3/A4. Only a genuine bad_case substitution proves this (a naive observed==red-only
    # check would already reject green/red or red/green; these are the ones that used to slip
    # through because expectation==observed was true).
    count += 1
    r = _run_case(
        "standalone: green/green mutation control does NOT lift A3 (behaved-as-predicted != "
        "band-lifting red)",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'expectation = "red"\n    observed    = "red"',
            'expectation = "green"\n    observed    = "green"',
        )),
        expect_pass=False,
        expect_substr="requires >=1 observed-red control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: sat/sat mutation control does NOT lift A4 (behaved-as-predicted != "
        "band-lifting red)",
        _mini_manifest(_A4_CLAIM_WITH_KERNEL_CONTROL.replace(
            'expectation = "red"\n    observed    = "red"',
            'expectation = "sat"\n    observed    = "sat"',
        )),
        expect_pass=False,
        expect_substr="requires >=1 observed-red control",
    )
    if r:
        failures.append(r)

    # F2 (tightened 2026-08-22): a band-lifting control's CARRIER record must be species-
    # compatible with the band — (i) a bmc carrier can't lift A4 (needs kernel); (ii) a
    # judgment-family carrier (human-review) can't lift ANYTHING (never in any allowed set).
    count += 1
    r = _run_case(
        "standalone (F2-i): a bmc-carrier mutation control under an A4 claim does NOT lift it "
        "(A4 needs a kernel-family carrier)",
        _mini_manifest(_A4_CLAIM_WITH_KERNEL_CONTROL.replace(
            """  [[claim.evidence]]
  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff (mutant: flipped comparison)"
  result    = "fail"
  tool      = "lean4@4.x-pinned + lean-mutate@pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d-mutant.lean"
""",
            """  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_d_bmc (mutant: off-by-one)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=16"
  semantics = ""
  record    = "evidence/does-not-exist-d-mutant.json"
""",
        )),
        expect_pass=False,
        expect_substr="not species-compatible with band",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone (F2-ii): a human-review record carrying a control under A3 does NOT lift it "
        "(judgment is never a valid carrier family)",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            """  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract (mutant: off-by-one in c)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f + cargo-mutants@25.x"
  bounds    = "bounded: unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c-mutants.json"
""",
            """  [[claim.evidence]]
  kind     = "human-review"
  family   = "judgment"
  ref      = "c-mutant-review"
  result   = "pass"
  tool     = "manual"
  reviewer = "reviewer-a"
  record   = "evidence/does-not-exist-c-review.txt"
""",
        )),
        expect_pass=False,
        expect_substr="not species-compatible with band",
    )
    if r:
        failures.append(r)

    # F3 (tightened 2026-08-22): a der-shaped A3 claim — an assertion-style Kani harness (no
    # `-Z function-contracts`), backed by a red bmc mutation control — validates cleanly, WITH
    # ZERO WARNINGS, under --strict.
    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        # this is the one fixture that actually needs its `record` pointers to RESOLVE (it
        # asserts ZERO WARNINGS under real --strict) -- write two backing files and give each
        # evidence entry its true record_hash, rather than relying on _mini_manifest's
        # placeholder injection (which is only safe when the pointer is fictitious).
        _evdir = Path(_td) / "evidence"
        _evdir.mkdir()
        _ev0 = _evdir / "k-integer.json"
        _ev0.write_text('{"result": "pass"}\n')
        _ev1 = _evdir / "k-integer-mutants.json"
        _ev1.write_text('{"result": "fail"}\n')
        _claim_text = (
            _DER_SHAPED_A3_ASSERTION_CLAIM
            .replace(
                'record    = "evidence/does-not-exist-k-integer.json"',
                'record    = "evidence/k-integer.json"\n'
                f'  record_hash = "{m11.digest_file("evidence-record", _ev0)}"',
            )
            .replace(
                'record    = "evidence/does-not-exist-k-integer-mutants.json"',
                'record    = "evidence/k-integer-mutants.json"\n'
                f'  record_hash = "{m11.digest_file("evidence-record", _ev1)}"',
            )
        )
        _p.write_text(_mini_manifest(_claim_text))
        _rep = validate(_p, strict=True)
        if not _rep.ok():
            failures.append(
                f"der-shaped A3 (assertion harness + red mutation control): expected PASS "
                f"--strict, got errors: {_rep.errors}"
            )
        else:
            # Exactly ONE warning, and it is named rather than tolerated: this claim is
            # `bounded`/`bounded` (claim `unwind=16, input<=12B`, harness the same), which
            # core.md §2's scope-coverage conjunct cannot decide structurally in this revision
            # — comparing two free-text tails is reviewer work, and the checker says so instead
            # of passing silently (2026-08-28). Any OTHER warning is still a failure here.
            _scope_warns = [w for w in _rep.warnings if "UNDECIDABLE THIS REVISION" in w]
            _other = [w for w in _rep.warnings if "UNDECIDABLE THIS REVISION" not in w]
            if len(_scope_warns) != 1 or _other:
                failures.append(
                    f"der-shaped A3 (assertion harness + red mutation control): expected exactly "
                    f"one scope-coverage-undecidable warning under --strict and nothing else, "
                    f"got: {_rep.warnings}"
                )

    # F4 (tightened 2026-08-22): the of_claim-mismatch check now runs for `partial` claims too.
    count += 1
    r = _run_case(
        "standalone: a `partial` claim carrying a mis-pointed control FAILS "
        "(check now runs for every status, not just 'evidenced')",
        _PARTIAL_CLAIM_WITH_MISPOINTED_CONTROL,
        expect_pass=False,
        expect_substr="does not name this claim",
    )
    if r:
        failures.append(r)

    # core.md §1/§2: `grade` is now REQUIRED, closed nine-token vocabulary. The base fixture
    # carries grade = "probe" (self_verify + bounds already present); these tests swap that value
    # (and, where the target grade needs different companions, add them) to exercise every token.
    count += 1
    r = _run_case(
        "standalone: claim with grade = 'contract' passes (same companions as 'probe' — "
        "core.md §1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "contract"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with an invalid grade value FAILS (core.md §1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "bogus"'
        )),
        expect_pass=False,
        expect_substr="grade must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim missing grade entirely FAILS (core.md §1, tightened from optional "
        "to required — the single largest break from the pre-freeze schema)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace('grade     = "probe"\n', '')),
        expect_pass=False,
        expect_substr="requires 'grade'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'ungraded' passes with no companion fields at all "
        "(core.md §1 — always legal, never strong)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "ungraded"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'test-only' passes (self_verify already present, no "
        "bounds required — core.md §1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "test-only"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'mechanical' passes (self_verify already present — "
        "core.md §1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "mechanical"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'inspection-argued' and a doc_ref passes, no "
        "self_verify needed (core.md §1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"',
            'grade     = "inspection-argued"\ndoc_ref   = "docs/a-review.md"',
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade = 'inspection-argued' with NO doc_ref PASSES with a warning -- never weight-eligible, so W3 imposes no obligation",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "inspection-argued"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'not-covered', self_verify.command + positive_control "
        "passes (core.md §1/§4)",
        # core.md §7.1 (2026-08-25): `not-covered` and `out-of-scope` assert that nothing
        # checked the item, so they cohere only with the statuses that assert no check
        # succeeded. These four cases used to hang off the EVIDENCED A1 hygiene claim, which is
        # the incoherent pairing the §7.1 table now refuses -- the fixtures were written before
        # the rule and are re-based here, not exempted from it.
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'expect  = "no output"',
            'expect  = "no output"\n'
            '  positive_control = "grep -rn \'impl\' src/ matches multiple lines"',
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'not-covered' and self_verify.command but NO "
        "positive_control FAILS (core.md §4 — now unconditional on this grade)",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL),
        expect_pass=False,
        expect_substr="requires a nonempty self_verify.positive_control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'out-of-scope' and a scope_ref passes (core.md §1)",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'out-of-scope' and NO scope_ref FAILS (core.md §1)",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM.replace(
            'scope_ref = "docs/scope.md#a"\n', ""
        )),
        expect_pass=False,
        expect_substr="requires a nonempty claim-level 'scope_ref'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: claim with grade = 'unspecified' and clause_source = 'none' passes "
        "(core.md §1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"',
            'grade     = "unspecified"\nclause_source = "none"',
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade = 'unspecified' with NO clause_source PASSES with a warning -- never weight-eligible (W3)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'grade     = "probe"', 'grade     = "unspecified"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade in {contract, probe} without a claim-level bounds field FAILS "
        "(core.md §5)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'bounds    = "bounded: unwind=8"\n', ''
        )),
        expect_pass=False,
        expect_substr="requires a claim-level 'bounds'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade = 'probe' with a bounds value not starting with "
        "'bounded'/'unbounded' FAILS (core.md §5)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'bounds    = "bounded: unwind=8"', 'bounds    = "unwind=8 only"'
        )),
        expect_pass=False,
        expect_substr="requires a claim-level 'bounds'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade = 'probe' with bounds = 'bounded: ...' exact lowercase PASSES "
        "(core.md §5) -- positive control for the 2026-08-28 exact-lowercase tightening: the "
        "common case must keep working, not just the rejected one below",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade = 'probe' with bounds = 'Bounded: ...' (capitalized token) FAILS "
        "-- tightened 2026-08-28 to EXACT lowercase (core.md §5): the leading bounded/unbounded "
        "token used to be matched case-insensitively, which the emitted JSON Schema could only "
        "express as a Python-only inline flag group invalid in ECMA-262; the validator's own "
        "check was tightened to exact lowercase to match the common-subset schema pattern, so a "
        "case variant is now refused on both sides in step",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'bounds    = "bounded: unwind=8"', 'bounds    = "Bounded: unwind=8"'
        )),
        expect_pass=False,
        expect_substr="requires a claim-level 'bounds'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade in {contract, probe, test-only, mechanical, not-covered} without "
        "self_verify at all FAILS (core.md §1/§3)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            """
  [claim.self_verify]
  command = "cargo kani --harness check_a_no_panic"
  expect  = "VERIFICATION:- SUCCESSFUL"
""",
            "",
        )),
        expect_pass=False,
        expect_substr="requires a [claim.self_verify] table",
    )
    if r:
        failures.append(r)

    # coverage-ledger.md §6: clause_source — invalid value fails, "test-name" warns (not an
    # error), a valid non-warning value passes silently.
    count += 1
    r = _run_case(
        "standalone: claim with an invalid clause_source value FAILS (coverage-ledger.md §6)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'status    = "evidenced"', 'status    = "evidenced"\nclause_source = "bogus"'
        )),
        expect_pass=False,
        expect_substr="clause_source must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'status    = "evidenced"', 'status    = "evidenced"\nclause_source = "test-name"'
        )))
        _rep = validate(_p, strict=False)
        if not _rep.ok():
            failures.append(
                f"clause_source = 'test-name': expected PASS, got errors: {_rep.errors}"
            )
        elif not any("test-name" in w and "same artifact" in w for w in _rep.warnings):
            failures.append(
                f"clause_source = 'test-name': expected a WARNING naming the self-referential "
                f"clause/evidence artifact, got: {_rep.warnings}"
            )

    count += 1
    r = _run_case(
        "standalone: claim with clause_source = 'doc-comment' passes with no warning "
        "(coverage-ledger.md §6)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'status    = "evidenced"', 'status    = "evidenced"\nclause_source = "doc-comment"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # coverage-ledger.md §3: [claim.self_verify] — unknown key is an error (strict, new table).
    count += 1
    r = _run_case(
        "standalone: self_verify with an unknown key FAILS (coverage-ledger.md §3, strict table)",
        _mini_manifest(_CLAIM_SELF_VERIFY_COMMAND_NO_EXPECT.replace(
            'command = "cargo test h"',
            'command = "cargo test h"\n  expect  = "ok"\n  bogus_key = "x"',
        )),
        expect_pass=False,
        expect_substr="unknown field",
    )
    if r:
        failures.append(r)

    # coverage-ledger.md §3: command present => expect is required and nonempty.
    count += 1
    r = _run_case(
        "standalone: self_verify.command without expect FAILS (coverage-ledger.md §3)",
        _mini_manifest(_CLAIM_SELF_VERIFY_COMMAND_NO_EXPECT),
        expect_pass=False,
        expect_substr="self_verify.expect is required",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: self_verify.command with expect PASSES (coverage-ledger.md §3)",
        _mini_manifest(_CLAIM_SELF_VERIFY_COMMAND_NO_EXPECT.replace(
            'command = "cargo test h"', 'command = "cargo test h"\n  expect  = "ok"',
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # coverage-ledger.md §4: grade = "not-covered" with self_verify.command requires a nonempty
    # positive_control.
    count += 1
    r = _run_case(
        "standalone: grade = 'not-covered' with self_verify.command and NO positive_control "
        "FAILS (coverage-ledger.md §4)",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL),
        expect_pass=False,
        expect_substr="requires a nonempty self_verify.positive_control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: grade = 'not-covered' with self_verify.command AND positive_control PASSES "
        "(coverage-ledger.md §4)",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'expect  = "no output"',
            'expect  = "no output"\n  positive_control = "grep -rn \'impl\' src/ matches"',
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # coverage-ledger.md §3: self_verify IS permitted on status = "gap"/"parked" — the one
    # widening this facet makes over format.md's "gap/parked claims carry no evidence" rule; it
    # must not trip that check (which only looks at claim.evidence).
    count += 1
    r = _run_case(
        "standalone: self_verify on a 'gap' claim PASSES (coverage-ledger.md §3, permitted "
        "widening — self_verify is a recipe, not evidence)",
        _mini_manifest(_GAP_CLAIM_WITH_SELF_VERIFY),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: self_verify on a 'parked' claim PASSES (coverage-ledger.md §3)",
        _mini_manifest(
            _GAP_CLAIM_WITH_SELF_VERIFY.replace(
                'status    = "gap"',
                'status    = "parked"\nparked_reason = "tool change needed"',
            )
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # core.md §6: [spec].axis is now REQUIRED; [spec].external stays optional and
    # type-checked. _mini_manifest already carries a valid default axis, so these tests
    # target-replace that line rather than blindly inserting a second one.
    count += 1
    r = _run_case(
        "standalone: [spec].external present and well-typed passes alongside the required "
        "axis (core.md §6)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'axis    = "public API surface of selftest-lib"',
            'axis    = "public API surface of selftest-lib"\n'
            'external = ["ITU-T X.690 (2021)"]',
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: [spec].axis empty string FAILS (core.md §6)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'axis    = "public API surface of selftest-lib"', 'axis    = ""',
        ),
        expect_pass=False,
        expect_substr="[spec].axis must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: [spec].axis missing entirely FAILS (core.md §6, tightened from "
        "optional to required)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'axis    = "public API surface of selftest-lib"\n', '',
        ),
        expect_pass=False,
        expect_substr="[spec].axis must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: [spec].external not a list FAILS (core.md §6)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'axis    = "public API surface of selftest-lib"',
            'axis    = "public API surface of selftest-lib"\nexternal = "RFC 5280"',
        ),
        expect_pass=False,
        expect_substr="[spec].external must be a list of nonempty strings",
    )
    if r:
        failures.append(r)

    # CLAIM-CLASSES-AWAITING-WEIGHT.md C1: [coverage].denominator / slice_note — EXPERIMENTAL, parseable and
    # shape-checked, meaning not enforced.
    count += 1
    r = _run_case(
        "standalone: [coverage].denominator = 'slice' without slice_note FAILS "
        "(CLAIM-CLASSES-AWAITING-WEIGHT.md C1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            "claims_total  = 1", 'claims_total  = 1\ndenominator = "slice"',
        ),
        expect_pass=False,
        expect_substr="denominator = 'slice' requires a nonempty 'slice_note'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: [coverage].denominator = 'slice' WITH slice_note PASSES "
        "(CLAIM-CLASSES-AWAITING-WEIGHT.md C1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            "claims_total  = 1",
            'claims_total  = 1\ndenominator = "slice"\nslice_note = "sampled subset only"',
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: [coverage].denominator = 'complete' PASSES (CLAIM-CLASSES-AWAITING-WEIGHT.md C1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            "claims_total  = 1", 'claims_total  = 1\ndenominator = "complete"',
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "standalone: [coverage].denominator with an invalid value FAILS (CLAIM-CLASSES-AWAITING-WEIGHT.md C1)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            "claims_total  = 1", 'claims_total  = 1\ndenominator = "bogus"',
        ),
        expect_pass=False,
        expect_substr="[coverage].denominator must be one of",
    )
    if r:
        failures.append(r)

    # CLAIM-CLASSES-AWAITING-WEIGHT.md C1: a valid denominator value PASSES but carries an EXPERIMENTAL warning
    # naming CLAIM-CLASSES-AWAITING-WEIGHT.md — presence is parseable, meaning is not enforced.
    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            "claims_total  = 1", 'claims_total  = 1\ndenominator = "complete"',
        ))
        _rep = validate(_p, strict=False)
        if not _rep.ok():
            failures.append(
                f"[coverage].denominator EXPERIMENTAL warning: expected PASS, got errors: "
                f"{_rep.errors}"
            )
        elif not any(
            "EXPERIMENTAL" in w and "CLAIM-CLASSES-AWAITING-WEIGHT.md" in w for w in _rep.warnings
        ):
            failures.append(
                f"[coverage].denominator EXPERIMENTAL warning: expected a warning naming "
                f"CLAIM-CLASSES-AWAITING-WEIGHT.md, got: {_rep.warnings}"
            )

    # ======================================================================
    # Enforcement-site coverage fixtures (external-review finding, 2026-08-25).
    # Each block below is named for the ONE previously-dead site it fires;
    # see the fixture constants above this function for the manifests used.
    # ======================================================================

    # -- _check_field generic branches (registry-driven per-kind extra fields) --

    count += 1
    r = _run_case(
        "coverage: kani-harness evidence.bounds present but empty string fires the "
        "bounds-token branch of _check_field (distinct from the field being absent)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            '  bounds    = "bounded: unwind=8"', '  bounds    = ""'
        )),
        expect_pass=False,
        expect_substr="field 'bounds' must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: kani-harness evidence.semantics (str-any) given a non-string value "
        "fires the str-any type branch of _check_field",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'semantics = ""', 'semantics = 123'
        )),
        expect_pass=False,
        expect_substr="field 'semantics' must be a string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: lean-theorem evidence.axioms (list) given a non-list value fires the "
        "list type branch of _check_field",
        _mini_manifest(_A4_CLAIM_WITH_KERNEL_CONTROL.replace(
            'result    = "pass"\n  tool      = "lean4@4.x-pinned"\n  axioms    = []',
            'result    = "pass"\n  tool      = "lean4@4.x-pinned"\n  axioms    = "not-a-list"',
        )),
        expect_pass=False,
        expect_substr="field 'axioms' must be a list",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: unit-test evidence.cases (int-pos) given 0 fires the int-pos branch "
        "of _check_field",
        _mini_manifest(_UNIT_TEST_DYNAMIC_CLAIM.replace('cases  = 3', 'cases  = 0')),
        expect_pass=False,
        expect_substr="field 'cases' must be an integer >= 1",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: evidence.mutants_caught (int-nonneg) given a negative value fires the "
        "int-nonneg branch of _check_field (result='fail' so the separate "
        ">=1-observed-red-mutant check does not also fire)",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'record    = "evidence/does-not-exist-c-mutants.json"',
            'record    = "evidence/does-not-exist-c-mutants.json"\n  mutants_caught = -1',
        )),
        expect_pass=False,
        expect_substr="field 'mutants_caught' must be an integer >= 0",
    )
    if r:
        failures.append(r)

    # NOTE (dead code, not fixture-closable): _check_field's `else` branch ("internal
    # validator bug — unknown tag") is unreachable through any TOML input. Every call site
    # passes a tag from the closed set {str-nonempty, str-any, list, int-pos, int-nonneg},
    # all handled above; the tag values come from KIND_REGISTRY and the two hardcoded
    # mutants_total/mutants_caught calls, none of which is user-controlled. Left in place
    # per instructions (not deleted, not papered over) — recorded here as a genuine
    # unreachable site, not a fixture gap.

    # -- universal evidence fields, result enum, band-species warns --

    count += 1
    r = _run_case(
        "coverage: evidence missing a universal field ('tool') fires the universal-field "
        "nonempty-string check (distinct from any per-kind registry field)",
        _mini_manifest(_UNIT_TEST_DYNAMIC_CLAIM.replace('tool   = "rustc@1.79-pinned"\n', '')),
        expect_pass=False,
        expect_substr="universal field 'tool' must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: evidence.result given a value outside {pass,fail,unsupported} fires "
        "the result-enum check",
        _mini_manifest(_UNIT_TEST_DYNAMIC_CLAIM.replace('result = "pass"', 'result = "bogus"')),
        expect_pass=False,
        expect_substr="result must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: an A2 claim resting on dynamic-only evidence fires the "
        "dynamic-family band-A0/A1-only error (A2 is neither)",
        _mini_manifest(_UNIT_TEST_DYNAMIC_CLAIM.replace('band      = "A1"', 'band      = "A2"')),
        expect_pass=False,
        expect_substr="all evidence is dynamic-family — band must be A0 or A1, got",
    )
    if r:
        failures.append(r)

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_MIRI_A1_NO_FREEDOM_WORDS_CLAIM))
        _rep = validate(_p, strict=False)
        if not _rep.ok():
            failures.append(
                f"A1 dynamic-only (miri), statement doesn't read as freedom claim: "
                f"expected PASS, got errors: {_rep.errors}"
            )
        elif not any("doesn't read as a" in w and "freedom claim" in w for w in _rep.warnings):
            failures.append(
                f"A1 dynamic-only (miri), statement doesn't read as freedom claim: "
                f"expected the freedom-claim advisory warning, got: {_rep.warnings}"
            )

    # assurance-bands.md rule 4's other legitimate A1 path (oracle-bearing dynamic evidence +
    # matching observed-red mutation control) must suppress the freedom-wording advisory warn
    # entirely -- the statement never mentions panic/crash/freedom/UB, so a PASS with no such
    # warning is only possible if the heuristic recognises the evidence shape, not the wording.
    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_A1_RULE4_CONTROL_CLAIM))
        _rep = validate(_p, strict=False)
        if not _rep.ok():
            failures.append(
                f"A1 rule-4 path (oracle-bearing dynamic + observed-red mutation control): "
                f"expected PASS, got errors: {_rep.errors}"
            )
        elif any("doesn't read as a" in w and "freedom claim" in w for w in _rep.warnings):
            failures.append(
                f"A1 rule-4 path (oracle-bearing dynamic + observed-red mutation control): "
                f"expected the freedom-claim advisory warning to be suppressed, got: "
                f"{_rep.warnings}"
            )

    # Contrast case: the SAME oracle-bearing dynamic species as the rule-4 fixture above, but
    # with no control at all -- outside the rule-4 shape entirely. This is capped at A0 by the
    # control gate (a separate ERROR, assurance-bands.md rule 6) AND the freedom-wording
    # advisory warn still fires, because the fallback heuristic is exactly what should be
    # judging a claim with no qualifying control.
    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_UNIT_TEST_DYNAMIC_CLAIM))
        _rep = validate(_p, strict=False)
        if _rep.ok():
            failures.append(
                "A1 dynamic-only, oracle-bearing, no control at all: expected FAIL "
                "(control-gate error), got PASS"
            )
        elif not any("requires >=1 observed-red control" in e for e in _rep.errors):
            failures.append(
                "A1 dynamic-only, oracle-bearing, no control at all: expected the control-gate "
                f"error, got errors: {_rep.errors}"
            )
        elif not any("doesn't read as a" in w and "freedom claim" in w for w in _rep.warnings):
            failures.append(
                "A1 dynamic-only, oracle-bearing, no control at all: expected the "
                f"freedom-claim advisory warning too, got: {_rep.warnings}"
            )

    # A mutation control that ran but observed GREEN (the mutant survived / the oracle did not
    # catch it) does not satisfy rule 4/6 -- only a literal red/red control band-lifts. The
    # freedom-wording advisory warn must still fire (the rule-4 shape is not satisfied).
    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_A1_RULE4_CONTROL_CLAIM.replace(
            'observed    = "red"', 'observed    = "green"',
        )))
        _rep = validate(_p, strict=False)
        if _rep.ok():
            failures.append(
                "A1 mutation control with observed=green: expected FAIL (control does not "
                "band-lift), got PASS"
            )
        elif not any("requires >=1 observed-red control" in e for e in _rep.errors):
            failures.append(
                "A1 mutation control with observed=green: expected the control-gate error, "
                f"got errors: {_rep.errors}"
            )
        elif not any("doesn't read as a" in w and "freedom claim" in w for w in _rep.warnings):
            failures.append(
                "A1 mutation control with observed=green: expected the freedom-claim advisory "
                f"warning too, got: {_rep.warnings}"
            )

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_FLUX_REFINEMENT_A35_CLAIM))
        _rep = validate(_p, strict=False)
        if not _rep.ok():
            failures.append(
                f"flux-refinement evidence at reserved band A3.5: expected PASS, got "
                f"errors: {_rep.errors}"
            )
        else:
            if not any("reserved kind" in w and "flux-refinement" in w for w in _rep.warnings):
                failures.append(
                    f"flux-refinement evidence: expected the reserved-kind warning, got: "
                    f"{_rep.warnings}"
                )
            if not any("reserved band" in w for w in _rep.warnings):
                failures.append(
                    f"band A3.5: expected the reserved-band warning, got: {_rep.warnings}"
                )

    # -- control block structural fields --

    count += 1
    r = _run_case(
        "coverage: evidence.control given a non-table value fires the "
        "\"'control' must be a table\" check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'record    = "evidence/does-not-exist-a.json"',
            'record    = "evidence/does-not-exist-a.json"\n  control   = "bogus"',
        )),
        expect_pass=False,
        expect_substr="'control' must be a table",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: control.kind given a value outside CONTROL_KIND_VALUES fires the "
        "control.kind-enum check",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'kind        = "mutation"', 'kind        = "bogus-kind"'
        )),
        expect_pass=False,
        expect_substr="control.kind must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: control.expectation given a value outside CONTROL_EXPECTATION_VALUES "
        "fires the control.expectation-enum check",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'expectation = "red"', 'expectation = "bogus"'
        )),
        expect_pass=False,
        expect_substr="control.expectation must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: control.observed given an empty string fires the control.observed-enum "
        "check (closed against the same set as control.expectation)",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'observed    = "red"', 'observed    = ""'
        )),
        expect_pass=False,
        expect_substr="control.observed must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: control.observed given a value outside CONTROL_EXPECTATION_VALUES "
        "fires the control.observed-enum check",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'observed    = "red"', 'observed    = "bogus"'
        )),
        expect_pass=False,
        expect_substr="control.observed must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: control.of_claim given an empty string fires the control.of_claim "
        "nonempty-string check (distinct from a nonempty-but-dangling of_claim)",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'of_claim    = "C-001"', 'of_claim    = ""'
        )),
        expect_pass=False,
        expect_substr="control.of_claim must be a nonempty string",
    )
    if r:
        failures.append(r)

    # -- mutants_caught / result='pass' cross-field check --

    count += 1
    r = _run_case(
        "coverage: a mutation-testing record with result='pass' and mutants_caught=0 "
        "fires the >=1-observed-red-mutant check",
        _mini_manifest(_A3_CLAIM_WITH_CONTROL.replace(
            'record    = "evidence/does-not-exist-c.json"',
            'record    = "evidence/does-not-exist-c.json"\n  mutants_caught = 0',
        )),
        expect_pass=False,
        expect_substr="must show >=1 observed-red mutant",
    )
    if r:
        failures.append(r)

    # -- record pointer resolution under --strict --

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM))
        _rep = validate(_p, strict=True)
        if _rep.ok():
            failures.append(
                "record pointer does not exist, --strict: expected FAIL, validation passed"
            )
        elif not any("record pointer does not exist" in e for e in _rep.errors):
            failures.append(
                f"record pointer does not exist, --strict: expected an ERROR (not a "
                f"warning) naming the missing record, got errors: {_rep.errors}, "
                f"warnings: {_rep.warnings}"
            )

    # -- self_verify structural checks --

    count += 1
    r = _run_case(
        "coverage: self_verify.command present but empty on a grade requiring "
        "self_verify fires the command-nonempty check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'command = "cargo kani --harness check_a_no_panic"', 'command = ""'
        )),
        expect_pass=False,
        expect_substr="requires self_verify.command to be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: self_verify given as a non-table value, on a grade that does NOT "
        "require self_verify, fires the \"must be a table\" branch",
        _mini_manifest(_UNGRADED_CLAIM_BAD_SELF_VERIFY_TYPE),
        expect_pass=False,
        expect_substr="[claim.self_verify] must be a table",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: a self_verify field given a non-string value fires the "
        "self_verify.{field} must-be-a-string check",
        _mini_manifest(_CLAIM_SELF_VERIFY_COMMAND_NO_EXPECT.replace(
            'command = "cargo test h"',
            'command = "cargo test h"\n  expect  = "ok"\n  precondition = 42',
        )),
        expect_pass=False,
        expect_substr="self_verify.precondition must be a string",
    )
    if r:
        failures.append(r)

    # -- grade-companion advisory warnings (require an explicitly weighted claim: --
    # -- check_grade_companions only runs for weighted claims, and both grades below --
    # -- are members of UNWEIGHTABLE_GRADES, which _mini_manifest would otherwise --
    # -- auto-mark unweighted) --

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_WEIGHTED_INSPECTION_ARGUED_NO_DOC_REF))
        _rep = validate(_p, strict=False)
        if not any("no deciding machinery" in e for e in _rep.errors):
            failures.append(
                f"weighted grade='inspection-argued': expected the WEIGHT REFUSED "
                f"'no deciding machinery' error too, got errors: {_rep.errors}"
            )
        if not any("SHOULD carry a nonempty claim-level 'doc_ref'" in w for w in _rep.warnings):
            failures.append(
                f"weighted grade='inspection-argued' with no doc_ref: expected the "
                f"doc_ref advisory warning, got: {_rep.warnings}"
            )

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_WEIGHTED_UNSPECIFIED_NO_CLAUSE_SOURCE_NONE))
        _rep = validate(_p, strict=False)
        if not any("no deciding machinery" in e for e in _rep.errors):
            failures.append(
                f"weighted grade='unspecified': expected the WEIGHT REFUSED "
                f"'no deciding machinery' error too, got errors: {_rep.errors}"
            )
        if not any("SHOULD carry clause_source = 'none'" in w for w in _rep.warnings):
            failures.append(
                f"weighted grade='unspecified' with no clause_source='none': expected "
                f"the clause_source advisory warning, got: {_rep.warnings}"
            )

    # -- weight / clause_source hard errors --

    count += 1
    r = _run_case(
        "coverage: an explicit, out-of-vocabulary claim.weight value fires the "
        "weight-enum check",
        _mini_manifest(_CLAIM_BAD_WEIGHT_VALUE),
        expect_pass=False,
        expect_substr="weight must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: a weighted claim with clause_source='test-name' fires the WEIGHT "
        "REFUSED reserved-clause_source error (distinct from the advisory 'test-name' "
        "warning both grades share)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'status    = "evidenced"',
            'status    = "evidenced"\nweight    = "weighted"\nclause_source = "test-name"',
        )),
        expect_pass=False,
        expect_substr="reserved to mean unweightable by design",
    )
    if r:
        failures.append(r)

    # -- claim / evidence structural checks --

    count += 1
    r = _run_case(
        "coverage: top-level `claim` present but not an array of tables fires the "
        "\"[[claim]] entries must form an array of tables\" check",
        _CLAIM_NOT_ARRAY_MANIFEST,
        expect_pass=False,
        expect_substr="[[claim]] entries must form an array of tables",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: a claim missing a required top-level field ('clause') fires the "
        "claim-field nonempty-string check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace('clause    = "S-1"\n', '')),
        expect_pass=False,
        expect_substr="field 'clause' must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: claim.band given a value outside BANDS fires the band-enum check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'band      = "A1"', 'band      = "A9"'
        )),
        expect_pass=False,
        expect_substr="band must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: claim.status given a value outside STATUSES fires the status-enum "
        "check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            'status    = "evidenced"', 'status    = "bogus"'
        )),
        expect_pass=False,
        expect_substr="status must be one of",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: claim.evidence present but not a list (a bare string) fires the "
        "\"[[claim.evidence]] must be an array of tables\" check",
        _mini_manifest(_CLAIM_EVIDENCE_NOT_ARRAY),
        expect_pass=False,
        expect_substr="[[claim.evidence]] must be an array of tables",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: claim.evidence is a list but one entry is not a table -- fires the "
        "per-entry \"must be a table\" check without crashing check_control_of_claim_mismatch "
        "/ check_band_reachability on the non-dict entry (bug found and fixed 2026-08-25: "
        "both used to assume every evidence item was a dict)",
        _mini_manifest(_CLAIM_EVIDENCE_ENTRY_NOT_TABLE),
        expect_pass=False,
        expect_substr="evidence[0]: must be a table",
    )
    if r:
        failures.append(r)

    # -- [format] / [subject] / [spec] / [coverage] section and field checks --

    count += 1
    r = _run_case(
        "coverage: manifest with no [format] section at all fires the "
        "\"[format] section missing\" check",
        re.sub(r"(?s)\[format\].*?\n\n", "", _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM), count=1),
        expect_pass=False,
        expect_substr="[format] section missing",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: manifest with no [subject] section at all fires the "
        "\"[subject] section missing\" check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            '[subject]\nname   = "selftest-lib"\nkind   = "rust-crate"\n'
            'commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"\ndirty  = false\n\n',
            '',
        ),
        expect_pass=False,
        expect_substr="[subject] section missing",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [subject].name empty fires the subject-name nonempty-string check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'name   = "selftest-lib"', 'name   = ""'
        ),
        expect_pass=False,
        expect_substr="[subject].name must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [subject].kind given a value outside SUBJECT_KINDS fires the fail-closed "
        "kind-registry check as INDETERMINATE, not invalid (CS-13)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'kind   = "rust-crate"', 'kind   = "bogus-kind"'
        ),
        expect_pass=False,
        expect_state="indeterminate",
        expect_substr="is not in the known registry",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [subject].dirty given a non-bool value fires the subject-dirty "
        "type check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'dirty  = false', 'dirty  = "false"'
        ),
        expect_pass=False,
        expect_substr="[subject].dirty must be a bool",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: manifest with no [spec] section at all fires the "
        "\"[spec] section missing\" check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            '[spec]\npath    = "SPEC.md"\nversion = "v1"\n'
            'axis    = "public API surface of selftest-lib"\n\n',
            '',
        ),
        expect_pass=False,
        expect_substr="[spec] section missing",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [spec].path empty fires the spec-path nonempty-string check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'path    = "SPEC.md"', 'path    = ""'
        ),
        expect_pass=False,
        expect_substr="[spec].path must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [spec].version empty fires the spec-version nonempty-string check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'version = "v1"', 'version = ""'
        ),
        expect_pass=False,
        expect_substr="[spec].version must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: manifest with no [coverage] section at all fires the "
        "\"[coverage] section missing\" check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            '[coverage]\nclauses_total = 1\nclaims_total  = 1\n\n', ''
        ),
        expect_pass=False,
        expect_substr="[coverage] section missing",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [coverage].clauses_total < 1 fires the clauses_total range check",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'clauses_total = 1', 'clauses_total = 0'
        ),
        expect_pass=False,
        expect_substr="[coverage].clauses_total must be an integer >= 1",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "coverage: [coverage].claims_total given a non-integer value fires the "
        "claims_total type check (distinct from a valid-but-mismatched integer)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'claims_total  = 1', 'claims_total  = "one"'
        ),
        expect_pass=False,
        expect_substr="[coverage].claims_total must be an integer,",
    )
    if r:
        failures.append(r)

    # -- validate()'s own file-level error paths --

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "does-not-exist.toml"
        _rep = validate(_p, strict=False)
        if _rep.ok():
            failures.append("validate() on a nonexistent path: expected FAIL, passed")
        elif not any("cannot read file" in e for e in _rep.errors):
            failures.append(
                f"validate() on a nonexistent path: expected 'cannot read file', got: "
                f"{_rep.errors}"
            )

    count += 1
    r = _run_case(
        "coverage: a file that is not valid TOML fires the TOML-parse-error check",
        "this is not [valid = toml at all {{{",
        expect_pass=False,
        expect_substr="TOML parse error",
    )
    if r:
        failures.append(r)

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_bytes(b"\xff\xfe\x00not valid utf-8")
        _rep = validate(_p, strict=False)
        if _rep.ok():
            failures.append("validate() on non-UTF-8 bytes: expected FAIL, passed")
        elif not any("not valid UTF-8" in e for e in _rep.errors):
            failures.append(
                f"validate() on non-UTF-8 bytes: expected 'not valid UTF-8', got: "
                f"{_rep.errors}"
            )

    bad_cases = [
        (
            "bad format id",
            GOOD_FIXTURE.replace('id = "acceptance/0"', 'id = "acceptance/1"'),
            "acceptance/0",
        ),
        (
            "bad commit",
            GOOD_FIXTURE.replace(
                'commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"', 'commit = "deadbeef"'
            ),
            "commit",
        ),
        (
            "claims_total mismatch",
            GOOD_FIXTURE.replace("claims_total  = 7", "claims_total  = 8"),
            "claims_total",
        ),
        (
            "duplicate claim id",
            GOOD_FIXTURE.replace('id        = "G-002"', 'id        = "G-001"'),
            "duplicate",
        ),
        (
            "evidenced claim with no evidence",
            GOOD_FIXTURE.replace(
                """  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "check_a_no_panic"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-a.json"
""",
                "",
            ),
            "requires at least one evidence entry",
        ),
        (
            "gap claim with evidence",
            GOOD_FIXTURE.replace(
                """status    = "gap"
""",
                """status    = "gap"

  [[claim.evidence]]
  kind     = "human-review"
  family   = "judgment"
  ref      = "f-review"
  result   = "pass"
  tool     = "manual"
  reviewer = "reviewer-a"
  record   = "evidence/does-not-exist-f.txt"
""",
            ),
            "must have NO evidence entries",
        ),
        (
            "parked without parked_reason",
            GOOD_FIXTURE.replace(
                'parked_reason = "kani unsupported_construct — tool change needed"\n', ""
            ),
            "parked_reason",
        ),
        (
            "unknown evidence kind",
            GOOD_FIXTURE.replace('kind      = "kani-harness"\n  family    = "bmc"\n  ref       = "check_a_no_panic"',
                                  'kind      = "made-up-kind"\n  family    = "bmc"\n  ref       = "check_a_no_panic"'),
            "unknown evidence kind",
        ),
        (
            "kind/family mismatch",
            GOOD_FIXTURE.replace(
                'kind      = "kani-harness"\n  family    = "bmc"\n  ref       = "check_a_no_panic"',
                'kind      = "kani-harness"\n  family    = "dynamic"\n  ref       = "check_a_no_panic"',
            ),
            "kind/family mismatch",
        ),
        (
            "missing per-kind required field (kani-harness without bounds)",
            GOOD_FIXTURE.replace('  bounds    = "bounded: unwind=8"\n', ""),
            "missing required field 'bounds'",
        ),
        (
            "lr without calibration",
            GOOD_FIXTURE.replace(
                '  record    = "evidence/does-not-exist-a.json"\n',
                '  record    = "evidence/does-not-exist-a.json"\n  lr        = 3.5\n',
            ),
            "calibration",
        ),
        (
            "judgment-only evidence with band A2",
            GOOD_FIXTURE.replace(
                'id        = "G-005"\nclause    = "S-5"\nitem      = "src/lib.rs::e"\nstatement = "e was reviewed"\nband      = "A0"',
                'id        = "G-005"\nclause    = "S-5"\nitem      = "src/lib.rs::e"\nstatement = "e was reviewed"\nband      = "A2"',
            ),
            "band must be A0",
        ),
        (
            "A4 claim with only bmc evidence",
            GOOD_FIXTURE.replace(
                """  kind      = "lean-theorem"
  family    = "kernel"
  ref       = "Lib.D.decode_iff"
  result    = "pass"
  tool      = "lean4@4.x-pinned"
  axioms    = []
  semantics = "lean-toolchain pins in-tree"
  record    = "evidence/does-not-exist-d.lean"
""",
                """  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_d_bmc"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-d.json"
""",
            ),
            "not reachable by any passing evidence",
        ),
        (
            "A3 claim with no control",
            GOOD_FIXTURE.replace(
                """
  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_c_contract (mutant: off-by-one in c)"
  result    = "fail"
  tool      = "kani@d4df833c8f8f + cargo-mutants@25.x"
  bounds    = "bounded: unwind=16"
  semantics = "-Z function-contracts"
  record    = "evidence/does-not-exist-c-mutants.json"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-003"
""",
                "",
            ),
            "requires >=1 observed-red control",
        ),
        (
            "control whose of_claim names a different claim can't lift the claim it's attached to",
            GOOD_FIXTURE.replace(
                '    of_claim    = "G-003"',
                '    of_claim    = "G-002"',
            ),
            "does not name this claim",
        ),
        (
            "control with observed != expectation doesn't satisfy the gate (bmc-family)",
            GOOD_FIXTURE.replace(
                """    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-003"
""",
                """    kind        = "mutation"
    expectation = "red"
    observed    = "green"
    of_claim    = "G-003"
""",
            ),
            "requires >=1 observed-red control",
        ),
        (
            "A2 claim with only a planted-twin control MUST FAIL (per-band whitelist, "
            "assurance-bands.md rule 6: A2 = mutation|ablation only, tightened 2026-08-22)",
            GOOD_FIXTURE.replace(
                """    kind        = "ablation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-002"
""",
                """    kind        = "planted-twin"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-002"
""",
            ),
            "requires >=1 observed-red control",
        ),
        (
            "A3 claim whose only control is a planted-twin MUST FAIL (planted-twin never "
            "satisfies the band-lift gate, at any band)",
            GOOD_FIXTURE.replace(
                """    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-003"
""",
                """    kind        = "planted-twin"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-003"
""",
            ),
            "requires >=1 observed-red control",
        ),
        (
            "A4 claim whose only control is a planted-twin MUST FAIL (planted-twin never "
            "satisfies the band-lift gate, at any band)",
            GOOD_FIXTURE.replace(
                """    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-004"
""",
                """    kind        = "planted-twin"
    expectation = "red"
    observed    = "red"
    of_claim    = "G-004"
""",
            ),
            "requires >=1 observed-red control",
        ),
        (
            "control.of_claim naming a claim id that does not exist anywhere in the manifest "
            "(phantom claim) is an error",
            GOOD_FIXTURE.replace(
                '    of_claim    = "G-003"',
                '    of_claim    = "A-999"',
            ),
            "does not match any claim id in this manifest",
        ),
    ]

    for name, text, substr in bad_cases:
        count += 1
        r = _run_case(name, text, expect_pass=False, expect_substr=substr)
        if r:
            failures.append(r)

    # ------------------------------------------------------------------
    # core.md W2.3 / W2.5 (P1, P2 -- ADOPTED 2026-08-25). Asserted under --strict-weight so
    # they are hard errors in the fixture; all three fail on the pre-adoption validator, which
    # granted weight to every one of these claims.
    # ------------------------------------------------------------------
    count += 1
    r = _run_case(
        "P1: weighted claim with NO clause_source is refused weight (--strict-weight)",
        _mini_manifest(_DER_SHAPED_A3_ASSERTION_CLAIM.replace(
            'clause_source = "external-standard"\n', "")),
        expect_pass=False,
        expect_substr="clause_source not recorded",
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "P2: weighted claim with no watched-fail witness is refused weight (--strict-weight)",
        # Strip ONLY the control block. The old pattern ran to end-of-string and took the
        # [claim.self_verify] table with it, so the claim ALSO broke a pre-adoption rule --
        # which, under the §8.1 membership invariant (S4), is now an outright refusal rather
        # than a pending one. The fixture has to isolate the P2 defect to assert P2.
        # ...and the band drops to A0 with the control, because A3 is control-gated: leaving it
        # at A3 substitutes an assurance-bands error for the P2 refusal being asserted.
        _mini_manifest(re.sub(
            r"(?m)^    \[claim\.evidence\.control\]\n(?:    \w.*\n)*", "",
            _DER_SHAPED_A3_ASSERTION_CLAIM).replace('band      = "A3"', 'band      = "A0"')),
        expect_pass=False,
        expect_substr="no watched-fail witness",
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "P1+P2 both satisfied: the golden A3 claim keeps its weight under --strict-weight",
        _mini_manifest(_DER_SHAPED_A3_ASSERTION_CLAIM),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    # ----------------------------------------------------------------------
    # review round-2 (2026-08-25). Every fixture below passed clean, WEIGHTED, on the code of
    # the same morning; each was watched red against it before its fix landed. They are the
    # TOML half of a parity gap: the Markdown checker refused all of these and the TOML
    # validator did not, which made the manifest representation the weaker of the two.
    # ----------------------------------------------------------------------

    # Finding 2: `watched_fail` was ANY nonempty string, so a phrase satisfied a weighted-tier
    # obligation -- the one thing §4.1 says may never happen.
    _WF_CLAIM = """
[[claim]]
id        = "W-1"
clause    = "S-1"
item      = "src/lib.rs::a"
statement = "a rejects non-minimal encodings"
band      = "A0"
grade     = "probe"
bounds    = "bounded: unwind=8"
status    = "evidenced"
weight    = "weighted"
clause_source = "spec-document"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "check_a"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-wf.json"

  [claim.self_verify]
  command = "cargo kani --harness check_a"
  expect  = "VERIFICATION:- SUCCESSFUL"
"""
    _WF_GOOD_BLOCK = """
    [claim.self_verify.watched_fail]
    of_command = "cargo kani --harness check_a"
    perturbed  = "deleted the minimality check in decode"
    observed   = "check_a FAILED on the padding assertion"
    date       = "2026-08-25"
"""
    count += 1
    r = _run_case(
        "R2-2: watched_fail as a free-text string is refused (a phrase is not a witness)",
        _mini_manifest(_WF_CLAIM + '  watched_fail = "x"\n'),
        expect_pass=False,
        expect_substr="must be a [claim.self_verify.watched_fail] TABLE",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-2: a fully-formed watched_fail table satisfies W2.5 and keeps the claim weighted",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-2: watched_fail.perturbed must be a statement, not a token",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            'perturbed  = "deleted the minimality check in decode"', 'perturbed  = "x"')),
        expect_pass=False,
        expect_substr="a single token is not a statement",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-2: watched_fail.of_command must name THIS claim's own command",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            'of_command = "cargo kani --harness check_a"',
            'of_command = "cargo kani --harness check_b"')),
        expect_pass=False,
        expect_substr="does not equal this claim's own self_verify.command",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-2: watched_fail.date must be an ISO date -- 'when' is part of the witness",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            'date       = "2026-08-25"', 'date       = "recently"')),
        expect_pass=False,
        expect_substr="must be an ISO date",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-2: a watched_fail table missing a required field is refused",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            '    date       = "2026-08-25"\n', "")),
        expect_pass=False,
        expect_substr="requires 'date'",
    )
    if r:
        failures.append(r)

    # A MALFORMED witness must not satisfy the requirement it fails to meet. Asserted directly
    # on the predicate, because at the file level such a claim is refused outright (§8.1
    # membership: it breaks a rule, so it is not on the backlog) and the pending reason is not
    # emitted -- which is correct, and is why the message-matching harness cannot state this.
    count += 1
    _sv_bad = {"command": "cargo kani --harness check_a",
               "watched_fail": {"of_command": "cargo kani --harness check_a",
                                "perturbed": "deleted the minimality check",
                                "observed": "check_a FAILED", "date": "recently"}}
    _sv_good = {"command": "cargo kani --harness check_a",
                "watched_fail": {"of_command": "cargo kani --harness check_a",
                                 "perturbed": "deleted the minimality check",
                                 "observed": "check_a FAILED", "date": "2026-08-25"}}
    if _watched_fail_block_is_valid(_sv_bad) or not _watched_fail_block_is_valid(_sv_good):
        failures.append(
            "R2-2: a malformed watched_fail table must not count as a witness (and a "
            "well-formed one must)"
        )
        print("SELFTEST FAIL: R2-2-malformed-witness-is-not-a-witness", file=sys.stderr)

    # Finding 2 (parity): §4.1 witness 3 is scoped to `not-covered`. A positive_control on a
    # `contract` row shows the command CAN match some input; it says nothing about whether the
    # proof would notice a broken implementation.
    count += 1
    r = _run_case(
        "R2-2: positive_control does not witness a non-not-covered grade (§4.1 witness 3)",
        _mini_manifest(_WF_CLAIM.replace(
            'expect  = "VERIFICATION:- SUCCESSFUL"',
            'expect  = "VERIFICATION:- SUCCESSFUL"\n'
            '  positive_control = "the same harness against a known-bad fixture"')),
        expect_pass=False,
        expect_substr="no watched-fail witness",
        strict_weight=True,
    )
    if r:
        failures.append(r)

    # Findings 3 and 5: §7.1 status x grade x weight coherence, absent from TOML entirely.
    count += 1
    r = _run_case(
        "R2-5: status = 'gap' + grade = 'contract' + weighted is INCOHERENT",
        _mini_manifest(_WF_CLAIM.replace('grade     = "probe"', 'grade     = "contract"')
                       .replace('status    = "evidenced"', 'status    = "gap"')
                       + _WF_GOOD_BLOCK),
        expect_pass=False,
        expect_substr="cannot be a gap and a proof at the same time",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-3: status = 'partial' + grade = 'not-covered' + weighted is INCOHERENT",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'status    = "gap"', 'status    = "partial"'
        ).replace(
            'expect  = "no output"',
            'expect  = "no output"\n  positive_control = "the same grep against src/b.rs hits"',
        )),
        expect_pass=False,
        expect_substr="does not cohere with grade 'not-covered'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-3: an UNWEIGHTED incoherent pair warns and does not error (P5 stays DEFERRED)",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'grade     = "not-covered"', 'grade     = "probe"'
        ).replace(
            'status    = "gap"',
            'status    = "parked"\nparked_reason = "tool change needed"\n'
            'weight    = "unweighted"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-3: out-of-scope scope_ref must be a locator, not free prose",
        _mini_manifest(_OUT_OF_SCOPE_CLAIM.replace(
            'scope_ref = "docs/scope.md#a"', 'scope_ref = "nonsense"')),
        expect_pass=False,
        expect_substr="scope_ref must be a LOCATOR",
    )
    if r:
        failures.append(r)

    # Finding 4: the §8.1 membership invariant. `FAIL 2 errors` alongside `pending: 1` said the
    # row was on a backlog meaning "fine until the rules changed", which it was not.
    count += 1
    _adv7 = _WF_CLAIM.replace('grade     = "probe"', 'grade     = "contract"') \
                     .replace('bounds    = "bounded: unwind=8"\n', "") \
                     .replace('clause_source = "spec-document"\n', "") \
                     .replace('  [claim.self_verify]\n'
                              '  command = "cargo kani --harness check_a"\n'
                              '  expect  = "VERIFICATION:- SUCCESSFUL"\n', "")
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "adv7.toml"
        _p.write_text(_mini_manifest(_adv7), encoding="utf-8")
        _rep = validate(_p, strict=False)
        n_pending_adv7 = getattr(_rep, "n_pending", 0)
        if _rep.ok() or n_pending_adv7 != 0:
            failures.append(
                f"R2-4: a claim breaking pre-adoption rules must not be weight-pending — "
                f"got ok={_rep.ok()} pending={n_pending_adv7}"
            )
            print("SELFTEST FAIL: R2-4-broken-row-is-not-weight-pending", file=sys.stderr)
        # Positive control: fixing the pre-adoption defects DOES put it on the backlog.
        _p2 = Path(_td) / "adv7fixed.toml"
        _p2.write_text(_mini_manifest(_WF_CLAIM), encoding="utf-8")
        _rep2 = validate(_p2, strict=False)
        if not _rep2.ok() or getattr(_rep2, "n_pending", 0) != 1:
            failures.append(
                f"R2-4 positive control: a row lacking only P1/P2 machinery must be pending — "
                f"got ok={_rep2.ok()} pending={getattr(_rep2, 'n_pending', 0)}"
            )
            print("SELFTEST FAIL: R2-4-positive-control", file=sys.stderr)

    # Finding 6: P3 and P4 mechanically adopted in TOML.
    def _predicate_claim(extra: str) -> str:
        # Claim-level fields must sit ABOVE the [claim.self_verify] table or TOML nests them
        # inside it.
        return _WF_CLAIM.replace(
            'clause_source = "spec-document"',
            'clause_source = "spec-document"\nitem_kind = "predicate"\n' + extra,
        ) + _WF_GOOD_BLOCK

    count += 1
    r = _run_case(
        "R2-6: a weighted predicate row with no fraction is refused weight (§7.2)",
        _mini_manifest(_predicate_claim("")),
        expect_pass=False,
        expect_substr="'over' (what the predicate ranges over) is missing",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-6: a predicate row with over + covered passes (§7.2)",
        _mini_manifest(_predicate_claim(
            'over      = "the 33 production harnesses in module X"\ncovered   = "4/33"')),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-6: a predicate fraction whose numerator exceeds its denominator is refused",
        _mini_manifest(_predicate_claim(
            'over      = "the 33 production harnesses"\ncovered   = "40/33"')),
        expect_pass=False,
        expect_substr="numerator exceeds its denominator",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-6: status = 'blocked' is a valid status (P4 adopted), and requires blocked_by",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'status    = "gap"', 'status    = "blocked"'
        ).replace(
            'expect  = "no output"',
            'expect  = "no output"\n  positive_control = "the same grep against src/b.rs hits"',
        )),
        expect_pass=False,
        expect_substr="requires a nonempty 'blocked_by'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-6: status = 'blocked' with blocked_by passes (P4 adopted)",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'status    = "gap"',
            'status    = "blocked"\nblocked_by = "kani 0.67 cannot quantify over a generic T"'
        ).replace(
            'expect  = "no output"',
            'expect  = "no output"\n  positive_control = "the same grep against src/b.rs hits"',
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # N1 (cold reader, 2026-08-26) — his exact fixture: a unit test carrying a `contract` grade.
    # §0.5 has said "a test is never contract" since it was written; nothing enforced it.
    _N1_CLAIM = """
[[claim]]
id        = "N1-1"
clause    = "S-1"
item      = "src/lib.rs::a"
statement = "a decides the rule"
band      = "A1"
grade     = "contract"
bounds    = "unbounded: all inputs"
status    = "evidenced"
weight    = "weighted"
clause_source = "spec-document"

  [[claim.evidence]]
  kind      = "unit-test"
  family    = "dynamic"
  ref       = "tests::a_decides"
  result    = "pass"
  tool      = "cargo@1.97"
  cases     = 2
  record    = "evidence/does-not-exist-n1.log"

  [claim.self_verify]
  command = "cargo test a_decides"
  expect  = "test result: ok"

    [claim.self_verify.watched_fail]
    of_command = "cargo test a_decides"
    perturbed  = "deleted the minimality check in decode"
    observed   = "a_decides failed on the padding assertion"
    date       = "2026-08-26"
"""
    count += 1
    r = _run_case(
        "N1: a weighted `contract` backed only by dynamic-family evidence is refused (§0.5)",
        _mini_manifest(_N1_CLAIM),
        expect_pass=False,
        expect_substr="requires a SYMBOLIC domain",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "N1 positive control: the same claim graded `test-only` is fine",
        _mini_manifest(_N1_CLAIM.replace('grade     = "contract"', 'grade     = "test-only"')
                                .replace('bounds    = "unbounded: all inputs"\n', "")
                                .replace('band      = "A1"', 'band      = "A0"')),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "N1 positive control: `contract` on bmc-family evidence keeps its weight",
        # Claim bounds match the harness's: the base fixture says `unbounded: all inputs` while
        # the kani record below says `bounded: unwind=8`, which core.md §2's scope-coverage
        # conjunct now REFUSES outright (an unbounded claim cannot rest on bounded evidence
        # alone). This fixture is a positive control for the SYMBOLIC-DOMAIN guard, so it must
        # not depend on a scope overclaim to make its point (2026-08-28).
        #
        # Band A0, not the base fixture's A1: this fixture is about the SYMBOLIC-DOMAIN guard, and
        # a FUNCTIONAL claim ("a decides the rule") backed by a passing kani-harness with no
        # observed-red control is capped at A0 by assurance-bands.md's control gate (the A1
        # kani bypass, closed 2026-08-28). Keeping it at A1 would make this positive control
        # depend on the very hole the gate now refuses.
        _mini_manifest(_N1_CLAIM.replace('band      = "A1"', 'band      = "A0"')
                                .replace('bounds    = "unbounded: all inputs"',
                                         'bounds    = "bounded: unwind=8"')
                                .replace('kind      = "unit-test"', 'kind      = "kani-harness"')
                                .replace('family    = "dynamic"', 'family    = "bmc"')
                                .replace('  cases     = 2\n',
                                         '  bounds    = "bounded: unwind=8"\n  semantics = ""\n'
                                         '  method    = "kani-harness"\n'
                                         '  epistemic_tier = "T2"\n')),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    # CS-4 conjunct 2, SCOPE COVERAGE (core.md §2; cold review finding 1, closed 2026-08-28).
    # The reviewer's own probe: a weighted `contract` claiming `unbounded: all byte strings`
    # backed by Kani evidence bounded to one byte, which passed --strict-weight because the
    # conjunct was never checked. `_SCOPE_BASE` is a bmc `contract` claim at band A0 (the band
    # axis is irrelevant to this rule and A0 keeps the control gate out of the way).
    _SCOPE_BASE = (
        _N1_CLAIM.replace('band      = "A1"', 'band      = "A0"')
                 .replace('kind      = "unit-test"', 'kind      = "kani-harness"')
                 .replace('family    = "dynamic"', 'family    = "bmc"')
                 .replace('  cases     = 2\n',
                          '  bounds    = "bounded: single byte, unwind=2"\n  semantics = ""\n'
                          '  method    = "kani-harness"\n  epistemic_tier = "T2"\n')
    )

    count += 1
    r = _run_case(
        "CS-4 scope coverage: an UNBOUNDED `contract` claim whose only qualifying T1/T2 evidence "
        "is BOUNDED is refused (the cold reviewer's own probe — bounded evidence cannot cover an "
        "unbounded claim)",
        _mini_manifest(_SCOPE_BASE.replace(
            'bounds    = "unbounded: all inputs"',
            'bounds    = "unbounded: all byte strings"',
        )),
        expect_pass=False,
        expect_substr="every qualifying T1/T2 evidence record declares 'bounded'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-4 scope coverage: the SAME claim declared `bounded` is accepted — the rule refuses "
        "the mismatch, not the evidence (undecidable-tail WARN, not an error)",
        _mini_manifest(_SCOPE_BASE.replace(
            'bounds    = "unbounded: all inputs"',
            'bounds    = "bounded: single byte, unwind=2"',
        )),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    # ...and the DECIDED-COVERED direction, asserted on the absence of the undecidable warning as
    # well as on the absence of errors. `expect_pass` alone cannot tell "covered" from "we could
    # not tell", because both exit clean -- and that indistinguishability is exactly how this
    # conjunct went unchecked.
    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_SCOPE_BASE.replace(
            'bounds    = "unbounded: all inputs"',
            'bounds    = "unbounded: all byte strings"',
        ).replace(
            '  bounds    = "bounded: single byte, unwind=2"\n',
            '  bounds    = "unbounded: symbolic byte string, no unwind bound"\n',
        )))
        _rep = validate(_p, strict=False, strict_weight=True)
        if not _rep.ok():
            failures.append(
                f"CS-4 scope coverage, decided-covered: an unbounded claim backed by an "
                f"UNBOUNDED qualifying record must pass, got errors: {_rep.errors}"
            )
        elif any("UNDECIDABLE THIS REVISION" in w for w in _rep.warnings):
            failures.append(
                f"CS-4 scope coverage, decided-covered: evidence over the whole domain DECIDES "
                f"the conjunct — it must not draw the undecidable warn, got: {_rep.warnings}"
            )

    # The two UNDECIDABLE cases must SAY they are undecidable, not pass silently. Asserted on the
    # warning text, because "no error" is exactly the outcome a silent pass also produces — which
    # is how this conjunct went unchecked for a full revision behind a comment claiming otherwise.
    for _name, _text, _needle in (
        (
            "bounded claim vs bounded evidence (free-text tails)",
            _SCOPE_BASE.replace(
                'bounds    = "unbounded: all inputs"',
                'bounds    = "bounded: inputs up to 8 bytes"',
            ),
            "whose free-text tails this revision cannot compare",
        ),
        (
            "qualifying evidence declaring no bounds at all (a lean-theorem record)",
            _SCOPE_BASE.replace('kind      = "kani-harness"', 'kind      = "lean-theorem"')
                       .replace('family    = "bmc"', 'family    = "kernel"')
                       .replace('  bounds    = "bounded: single byte, unwind=2"\n', '')
                       .replace('  semantics = ""\n',
                                '  axioms    = []\n  semantics = "lean-toolchain pins in-tree"\n')
                       .replace('  method    = "kani-harness"\n  epistemic_tier = "T2"\n',
                                '  method    = "lean-theorem"\n  epistemic_tier = "T1"\n'),
            "no qualifying evidence record declares `bounds` at all",
        ),
    ):
        count += 1
        with tempfile.TemporaryDirectory() as _td:
            _p = Path(_td) / "acceptance.toml"
            _p.write_text(_mini_manifest(_text))
            _rep = validate(_p, strict=False, strict_weight=True)
            if not _rep.ok():
                failures.append(
                    f"CS-4 scope coverage, undecidable ({_name}): expected PASS, got errors: "
                    f"{_rep.errors}"
                )
            elif not any(
                "UNDECIDABLE THIS REVISION" in w and _needle in w for w in _rep.warnings
            ):
                failures.append(
                    f"CS-4 scope coverage, undecidable ({_name}): expected the "
                    f"undecidable-this-revision WARN naming the case, got: {_rep.warnings}"
                )

    # assurance-bands.md rule 4/6, the A1 kani bypass (cold review finding 5, closed 2026-08-28).
    # A passing `kani-harness` used to defeat the A1 control gate outright, whatever the claim
    # said, so a FUNCTIONAL Kani probe at A1 with no control passed --strict-weight. The exemption
    # is now conditioned on the claim reading as a freedom claim. Four fixtures, both directions
    # on both axes (claim character x control presence).
    _A1_KANI_FUNCTIONAL_CLAIM = (
        _N1_CLAIM.replace('grade     = "contract"', 'grade     = "probe"')
                 .replace('kind      = "unit-test"', 'kind      = "kani-harness"')
                 .replace('family    = "dynamic"', 'family    = "bmc"')
                 .replace('  cases     = 2\n',
                          '  bounds    = "bounded: unwind=8"\n  semantics = ""\n'
                          '  method    = "kani-harness"\n  epistemic_tier = "T2"\n')
    )

    count += 1
    r = _run_case(
        "A1 kani bypass: a FUNCTIONAL claim at A1 with a passing kani-harness and NO observed-red "
        "control is capped at A0 — the tool does not decide the claim's character",
        _mini_manifest(_A1_KANI_FUNCTIONAL_CLAIM),
        expect_pass=False,
        expect_substr="band 'A1' is oracle-bearing and requires >=1 observed-red control",
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "A1 kani bypass, direction 2: the SAME evidence under a FREEDOM claim reaches A1 with no "
        "control (a zero-annotation panic-freedom harness has no postcondition to mutate)",
        _mini_manifest(_A1_KANI_FUNCTIONAL_CLAIM.replace(
            'statement = "a decides the rule"', 'statement = "a never panics on any input"'
        )),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "A1 kani bypass, direction 3: the functional claim reaches A1 once a real observed-red "
        "mutation control on a dynamic carrier backs it (rule 4's other legitimate path)",
        _mini_manifest(_A1_KANI_FUNCTIONAL_CLAIM + """
  [[claim.evidence]]
  kind      = "unit-test"
  family    = "dynamic"
  ref       = "tests::a_decides (cargo-mutants over the suite)"
  result    = "fail"
  tool      = "cargo-mutants@25.x"
  cases     = 2
  record    = "evidence/does-not-exist-n1-mutants.log"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "N1-1"
"""),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "A1 kani bypass, direction 4: dropping the band to A0 is the other honest fix — the gate "
        "caps the claim, it does not forbid the evidence",
        _mini_manifest(_A1_KANI_FUNCTIONAL_CLAIM.replace(
            'band      = "A1"', 'band      = "A0"'
        )),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R6-1: an annotation with a colon separator is still metadata",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            'observed   = "check_a FAILED on the padding assertion"',
            'observed   = "bug, observed: 2026-08-25"')),
        expect_pass=False,
        expect_substr="a single token is not a statement",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R6-1: a date in the MIDDLE of a description is not metadata and must not be stripped",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            'observed   = "check_a FAILED on the padding assertion"',
            'observed   = "failure on 2026-08-25 after harness mutation"')),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R5-1: `bounded` is a TOKEN, not a prefix — `boundedness:...` is refused",
        _mini_manifest(_WF_CLAIM.replace(
            'bounds    = "bounded: unwind=8"', 'bounds    = "boundedness:unwind=8"')
            + _WF_GOOD_BLOCK),
        expect_pass=False,
        expect_substr="starting with 'bounded' or 'unbounded'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R5-2: a date annotation inside `observed` does not satisfy the phrase floor",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK.replace(
            'observed   = "check_a FAILED on the padding assertion"',
            'observed   = "y, observed 2026-08-25"')),
        expect_pass=False,
        expect_substr="a single token is not a statement",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R3-3c: a bounds token with no stated limit is refused (§5 requires the limit text)",
        _mini_manifest(_WF_CLAIM.replace(
            'bounds    = "bounded: unwind=8"', 'bounds    = "bounded"') + _WF_GOOD_BLOCK),
        expect_pass=False,
        expect_substr="nothing about WHAT THE CHECK RANGED OVER",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R3-3c positive control: a single-token limit like `unwind=8` is a real limit and passes",
        _mini_manifest(_WF_CLAIM + _WF_GOOD_BLOCK),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-11: positive_control must be a statement, not a token (§4 is a weighted-tier "
        "obligation, so a phrase match earning it is the one thing §4.1 forbids)",
        _mini_manifest(_NOT_COVERED_CLAIM_WITH_SELF_VERIFY_NO_CONTROL.replace(
            'expect  = "no output"', 'expect  = "no output"\n  positive_control = "x"')),
        expect_pass=False,
        expect_substr="a single token is not a control",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "R2-6: status = 'blocked' forbids evidence entries, exactly like gap/parked",
        _mini_manifest(_WF_CLAIM.replace('grade     = "probe"', 'grade     = "not-covered"')
                       .replace('bounds    = "bounded: unwind=8"\n', "")
                       .replace('status    = "evidenced"',
                                'status    = "blocked"\nblocked_by = "the tool cannot reach it"')
                       + _WF_GOOD_BLOCK),
        expect_pass=False,
        expect_substr="must have NO evidence entries",
    )
    if r:
        failures.append(r)

    # ------------------------------------------------------------------------------------------
    # CS-11/CS-16/CS-21/CS-22/CS-23 (applied change-set, folded into spec text 2026-08-27)
    # ------------------------------------------------------------------------------------------

    count += 1
    r = _run_case(
        "CS-11: shape = 'bundle' is INDETERMINATE for the whole file, unconditionally",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'shape         = "single-file"', 'shape         = "bundle"'
        ),
        expect_pass=False,
        expect_state="indeterminate",
        expect_substr="bundle validation has not shipped",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-16: [format].spec_id absent is a hard error, not a warning",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'spec_id       = "acceptance-format"\n', ""
        ),
        expect_pass=False,
        expect_substr="[format].spec_id must be a nonempty string",
    )
    if r:
        failures.append(r)

    # CS-16 self-location SHAPES (2026-08-28 soundness fix): the three shaped fields are checked
    # for shape, not just nonemptiness. Both directions, per field: a shaped value passes (the
    # base fixture already carries compliant values -- 40 hex, `...T00:00:00Z`) and every
    # non-shaped spelling the old nonemptiness test admitted is now refused.
    count += 1
    r = _run_case(
        "CS-16: validator_sha that is not a sha is refused (the format's own claimed stability "
        "anchor used to accept any nonempty string)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'validator_sha = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"',
            'validator_sha = "also-not-a-sha"',
        ),
        expect_pass=False,
        expect_substr="[format].validator_sha must be 7-40 lowercase hex characters",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-16: spec_sha that is not a sha is refused",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'spec_sha      = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"',
            'spec_sha      = "HEAD"',
        ),
        expect_pass=False,
        expect_substr="[format].spec_sha must be 7-40 lowercase hex characters",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-16: an UPPERCASE or over-long sha is refused (one spelling, matched exactly)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'validator_sha = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"',
            'validator_sha = "ABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD"',
        ),
        expect_pass=False,
        expect_substr="[format].validator_sha must be 7-40 lowercase hex characters",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-16: a 7-hex ABBREVIATED sha is accepted (git's own default abbreviation length)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'validator_sha = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"',
            'validator_sha = "abcdefa"',
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-16: a 6-hex sha is too short to resolve an identity and is refused",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'validator_sha = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"',
            'validator_sha = "abcdef"',
        ),
        expect_pass=False,
        expect_substr="[format].validator_sha must be 7-40 lowercase hex characters",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-16: generated_at that is not an ISO-8601 UTC timestamp is refused",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'generated_at  = "2026-08-27T00:00:00Z"', 'generated_at  = "not-a-date"'
        ),
        expect_pass=False,
        expect_substr="[format].generated_at must be ISO-8601 UTC",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-16: a date with no time, and a local-time timestamp with no 'Z', are both refused "
        "(a timestamp whose timezone a reader must guess is not a location)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'generated_at  = "2026-08-27T00:00:00Z"', 'generated_at  = "2026-08-27T00:00:00"'
        ),
        expect_pass=False,
        expect_substr="[format].generated_at must be ISO-8601 UTC",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-10: [format].shape absent is a hard error",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'shape         = "single-file"\n', ""
        ),
        expect_pass=False,
        expect_substr="[format].shape must be one of",
    )
    if r:
        failures.append(r)

    # CS-4: a weighted `contract` claim's own epistemic_tier/grade coherence obligation --
    # transitional, same §8.1 ratchet as W2.3/W2.5.
    # Band A0 for the same reason as the N1 bmc positive control above: this claim is functional
    # and carries no observed-red control, so A1 is not available to it (assurance-bands.md rule
    # 6). CS-4 is a grade/tier rule and is independent of the band axis (core.md §2).
    _CS4_BMC_CONTRACT_CLAIM = (
        _N1_CLAIM.replace('band      = "A1"', 'band      = "A0"')
                 .replace('kind      = "unit-test"', 'kind      = "kani-harness"')
                 .replace('family    = "dynamic"', 'family    = "bmc"')
                 .replace('  cases     = 2\n', '  bounds    = "bounded: unwind=8"\n  semantics = ""\n')
    )

    count += 1
    r = _run_case(
        "CS-4: a weighted `contract` claim with no qualifying epistemic_tier is weight-pending "
        "(a warning, not refused) by default",
        _mini_manifest(_CS4_BMC_CONTRACT_CLAIM),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-4: the same claim is refused weight under --strict-weight",
        _mini_manifest(_CS4_BMC_CONTRACT_CLAIM),
        expect_pass=False,
        expect_substr="epistemic_tier/grade coherence not satisfied",
        strict_weight=True,
    )
    if r:
        failures.append(r)

    # CS-1/CS-2 (evidence-types.md, ruled 2026-08-28): an evidence record that omits `method`
    # or `epistemic_tier` now draws a WARN (not an error) naming the omitted field -- the record
    # stays admissible, but a producer is told the field the frozen format will require is
    # missing. Band A0 keeps this isolated from the control-gate/species machinery above.
    _METHOD_TIER_OMITTED_CLAIM = _UNIT_TEST_DYNAMIC_CLAIM.replace(
        'band      = "A1"', 'band      = "A0"',
    )
    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_METHOD_TIER_OMITTED_CLAIM))
        _rep = validate(_p, strict=False)
        if not _rep.ok():
            failures.append(
                f"method/epistemic_tier omitted: expected PASS, got errors: {_rep.errors}"
            )
        else:
            if not any("'method' is omitted" in w and "CS-1/CS-2" in w for w in _rep.warnings):
                failures.append(
                    f"method/epistemic_tier omitted: expected the 'method' omission warn, "
                    f"got: {_rep.warnings}"
                )
            if not any(
                "'epistemic_tier' is omitted" in w and "CS-1/CS-2" in w for w in _rep.warnings
            ):
                failures.append(
                    f"method/epistemic_tier omitted: expected the 'epistemic_tier' omission "
                    f"warn, got: {_rep.warnings}"
                )

    # Same claim, both fields DECLARED: validation stays exactly as before (no omission warn,
    # and CS-3's profile-pinned-tier check still applies -- "unit-test" pins to "T3").
    _METHOD_TIER_DECLARED_CLAIM = _METHOD_TIER_OMITTED_CLAIM.replace(
        '  kind   = "unit-test"\n  family = "dynamic"\n',
        '  kind   = "unit-test"\n  family = "dynamic"\n  method = "unit-test"\n'
        '  epistemic_tier = "T3"\n',
    )
    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(_mini_manifest(_METHOD_TIER_DECLARED_CLAIM))
        _rep = validate(_p, strict=False)
        if not _rep.ok():
            failures.append(
                f"method/epistemic_tier declared: expected PASS, got errors: {_rep.errors}"
            )
        elif any("is omitted" in w and "CS-1/CS-2" in w for w in _rep.warnings):
            failures.append(
                f"method/epistemic_tier declared: expected no omission warn, got: "
                f"{_rep.warnings}"
            )

    # CS-3, both directions (2026-08-28): the profile-pinned tier is a CEILING, not an equality
    # (ADR-002: a declared tier "may never EXCEED what the profile's table assigns"). T1 is the
    # STRONGEST tier and T5 the weakest, so the numeral runs opposite to strength.
    count += 1
    r = _run_case(
        "CS-3: a declared epistemic_tier STRONGER than the method's pinned tier is refused "
        "(method 'unit-test' pins T3; the record claims T1)",
        _mini_manifest(_METHOD_TIER_DECLARED_CLAIM.replace(
            '  epistemic_tier = "T3"\n', '  epistemic_tier = "T1"\n'
        )),
        expect_pass=False,
        expect_substr="is STRONGER than the FV profile's method → epistemic_tier table allows",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-3: a declared epistemic_tier WEAKER than the pinned tier is ACCEPTED — conservative "
        "deflation is honest, and an anti-overclaim format must not enforce the underclaim "
        "direction (method 'unit-test' pins T3; the record claims T5)",
        _mini_manifest(_METHOD_TIER_DECLARED_CLAIM.replace(
            '  epistemic_tier = "T3"\n', '  epistemic_tier = "T5"\n'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-3: one rung stronger is still refused — the ceiling is not a two-rung tolerance "
        "(method 'unit-test' pins T3; the record claims T2)",
        _mini_manifest(_METHOD_TIER_DECLARED_CLAIM.replace(
            '  epistemic_tier = "T3"\n', '  epistemic_tier = "T2"\n'
        )),
        expect_pass=False,
        expect_substr="is STRONGER than the FV profile's method → epistemic_tier table allows",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-3: one rung weaker is accepted (method 'unit-test' pins T3; the record claims T4)",
        _mini_manifest(_METHOD_TIER_DECLARED_CLAIM.replace(
            '  epistemic_tier = "T3"\n', '  epistemic_tier = "T4"\n'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # CS-21/CS-22: `illustrative = true` suppresses the watched-fail-witness (§4.1) and
    # epistemic_tier/grade-coherence (CS-4) pending obligations -- both still absent here -- but
    # NOT required-field presence (self-location, shape, closed vocabularies stay enforced).
    _ILLUSTRATIVE_CLAIM_NO_WITNESS = re.sub(
        r"(?m)\n    \[claim\.self_verify\.watched_fail\]\n(?:    \w.*\n)*", "",
        _CS4_BMC_CONTRACT_CLAIM,
    )
    count += 1
    r = _run_case(
        "CS-21/CS-22: illustrative = true keeps a claim missing BOTH the watched-fail witness "
        "and epistemic_tier weighted, even under --strict-weight",
        _mini_manifest(_ILLUSTRATIVE_CLAIM_NO_WITNESS).replace(
            'generated_at  = "2026-08-27T00:00:00Z"',
            'generated_at  = "2026-08-27T00:00:00Z"\nillustrative  = true',
        ),
        expect_pass=True,
        strict_weight=True,
    )
    if r:
        failures.append(r)

    # illustrative does NOT waive required-field presence (self-location stays enforced).
    count += 1
    r = _run_case(
        "CS-21/CS-22: illustrative = true does not waive [format] self-location fields",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            'generated_at  = "2026-08-27T00:00:00Z"',
            'generated_at  = "2026-08-27T00:00:00Z"\nillustrative  = true',
        ).replace('spec_id       = "acceptance-format"\n', ""),
        expect_pass=False,
        expect_substr="[format].spec_id must be a nonempty string",
    )
    if r:
        failures.append(r)

    # CS-23: the F4 contradiction guard -- a record cannot claim its own result = "pass" AND
    # carry an observed-red mutation control (that observed-red describes a DIFFERENT run).
    _F4_CONTRADICTION_CLAIM = """
[[claim]]
id        = "F4-1"
clause    = "S-1"
item      = "src/lib.rs::e"
statement = "e is memory safe in its unsafe block"
band      = "A2"
grade     = "contract"
bounds    = "bounded: unwind=8"
status    = "evidenced"

  [[claim.evidence]]
  kind      = "kani-harness"
  family    = "bmc"
  ref       = "verify_e (mutant: removed bounds check)"
  result    = "pass"
  tool      = "kani@d4df833c8f8f"
  bounds    = "bounded: unwind=8"
  semantics = ""
  record    = "evidence/does-not-exist-f4.json"

    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "F4-1"

  [claim.self_verify]
  command = "cargo kani --harness verify_e"
  expect  = "VERIFICATION:- SUCCESSFUL"
"""
    count += 1
    r = _run_case(
        "CS-23: result = 'pass' with an observed-red mutation control on the SAME record is "
        "self-contradictory",
        _mini_manifest(_F4_CONTRADICTION_CLAIM),
        expect_pass=False,
        expect_substr="contradiction",
    )
    if r:
        failures.append(r)

    # Part 4(f): the bounded/unbounded two-token rule, extended to evidence-record `bounds`
    # (format.md's KIND_REGISTRY) -- a limit alone ("unwind=8") is no longer a boundedness
    # declaration at the evidence-record granularity either, exactly as it already was not at
    # the claim level (core.md §5).
    count += 1
    r = _run_case(
        "evidence-record bounds without a bounded/unbounded token is refused (extends §5)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            '  bounds    = "bounded: unwind=8"', '  bounds    = "unwind=8"'
        )),
        expect_pass=False,
        expect_substr="must start with the token 'bounded' or 'unbounded'",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "evidence-record bounds with the bare token and no tail is fine (tail is OPTIONAL here, "
        "unlike the claim-level field)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            '  bounds    = "bounded: unwind=8"', '  bounds    = "bounded"'
        )),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # --------------------------------------------------------------------
    # M11 (ratified 2026-08-28) -- record_hash: match / mismatch / malformed / missing-on-weighted
    # --------------------------------------------------------------------

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _evdir = Path(_td) / "evidence"
        _evdir.mkdir()
        _evfile = _evdir / "a.json"
        _evfile.write_text('{"result": "pass"}\n')
        _claim = _A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            '  record    = "evidence/does-not-exist-a.json"',
            '  record    = "evidence/a.json"\n'
            f'  record_hash = "{m11.digest_file("evidence-record", _evfile)}"',
        )
        _p.write_text(_mini_manifest(_claim))
        _rep = validate(_p, strict=False)
        if not _rep.ok():
            failures.append(
                f"M11 record_hash MATCH: expected PASS, got errors: {_rep.errors}, "
                f"indeterminate: {_rep.indeterminate}"
            )

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "acceptance.toml"
        _evdir = Path(_td) / "evidence"
        _evdir.mkdir()
        _evfile = _evdir / "a.json"
        _evfile.write_text('{"result": "pass"}\n')
        _claim = _A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            '  record    = "evidence/does-not-exist-a.json"',
            '  record    = "evidence/a.json"\n'
            f'  record_hash = "sha-512:{"0" * 128}"',
        )
        _p.write_text(_mini_manifest(_claim))
        _rep = validate(_p, strict=False)
        if _rep.ok() or not any("record_hash MISMATCH" in e for e in _rep.errors):
            failures.append(
                f"M11 record_hash MISMATCH: expected an error naming the mismatch, got "
                f"errors: {_rep.errors}"
            )

    count += 1
    r = _run_case(
        "M11 record_hash malformed shape (not 'sha-512:<128-hex>') is refused",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            '  record    = "evidence/does-not-exist-a.json"',
            '  record    = "evidence/does-not-exist-a.json"\n  record_hash = "abc123"',
        )),
        expect_pass=False,
        expect_substr="record_hash must be the self-describing form",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "M11 record_hash ABSENT on a weighted claim's evidence is refused (evidence-types.md, P9)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM, auto_record_hash=False),
        expect_pass=False,
        expect_substr="record_hash is REQUIRED on a weighted claim's evidence",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "M11 record_hash ABSENT on an UNWEIGHTED claim's evidence stays a note, not an error "
        "(evidence-types.md, P9: optional on unweighted)",
        _mini_manifest(
            _A1_HYGIENE_NO_CONTROL_CLAIM.replace(
                '[[claim]]', '[[claim]]\nweight    = "unweighted"', 1
            ),
            auto_record_hash=False,
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "M11 record_hash: an illustrative manifest skips both recomputation and the "
        "required-on-weighted obligation (CS-21/22 -- shape-only)",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM, auto_record_hash=False).replace(
            "id = \"acceptance/0\"", "id = \"acceptance/0\"\nillustrative = true", 1
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    # --------------------------------------------------------------------
    # Design rule 4a, dimensional fix (CS-8) -- subject_hash: match / mismatch / absent
    # --------------------------------------------------------------------

    _HASH_A = "sha-512:" + "a" * 128
    _HASH_B = "sha-512:" + "b" * 128

    def _with_subject_hash(manifest_text: str, value: str | None) -> str:
        if value is None:
            return manifest_text
        return manifest_text.replace(
            "dirty  = false\n", f'dirty  = false\nsubject_hash = "{value}"\n', 1
        )

    def _with_evidence_subject_hash(claim_toml: str, value: str) -> str:
        return claim_toml.replace(
            '  record    = "evidence/does-not-exist-a.json"',
            '  record    = "evidence/does-not-exist-a.json"\n'
            f'  subject_hash = "{value}"',
        )

    count += 1
    r = _run_case(
        "CS-8 subject_hash MATCH: [subject].subject_hash equals the evidence record's "
        "subject_hash -- validates cleanly",
        _with_subject_hash(
            _mini_manifest(_with_evidence_subject_hash(_A1_HYGIENE_NO_CONTROL_CLAIM, _HASH_A)),
            _HASH_A,
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-8 subject_hash MISMATCH: a hard error, unconditionally (format.md design rule 4a)",
        _with_subject_hash(
            _mini_manifest(_with_evidence_subject_hash(_A1_HYGIENE_NO_CONTROL_CLAIM, _HASH_A)),
            _HASH_B,
        ),
        expect_pass=False,
        expect_substr="evidence-subject binding MISMATCH",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-8 subject_hash ABSENT on [subject]: an evidence record's own subject_hash has "
        "nothing to be checked against -- allowed in 0.1 (the field is OPTIONAL on [subject])",
        _mini_manifest(_with_evidence_subject_hash(_A1_HYGIENE_NO_CONTROL_CLAIM, _HASH_A)),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-8 [subject].subject_hash malformed shape is refused",
        _with_subject_hash(_mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM), "not-a-hash"),
        expect_pass=False,
        expect_substr="[subject].subject_hash must be the self-describing form",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-8 evidence subject_hash malformed shape is refused",
        _mini_manifest(_with_evidence_subject_hash(_A1_HYGIENE_NO_CONTROL_CLAIM, "not-a-hash")),
        expect_pass=False,
        expect_substr="subject_hash must be the self-describing form",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "CS-8: [subject].commit (git-domain) is never compared against an M11 hash -- a "
        "mismatched subject_hash still fires even though commit is untouched",
        _with_subject_hash(
            _mini_manifest(_with_evidence_subject_hash(_A1_HYGIENE_NO_CONTROL_CLAIM, _HASH_B)),
            _HASH_A,
        ),
        expect_pass=False,
        expect_substr="evidence-subject binding MISMATCH",
    )
    if r:
        failures.append(r)

    # --------------------------------------------------------------------
    # P3 (evidence-types.md "Control block", design ruled 2026-08-29) -- captured_at_commit:
    # OPTIONAL per-record provenance disclosure, shape only, never a second validity key. Exercised
    # on the control-carrying record of _A1_RULE4_CONTROL_CLAIM, since the stale-control policy this
    # field exists to support is a control-block concern -- the field itself is a plain per-record
    # string and behaves identically on a non-control record.
    # --------------------------------------------------------------------

    def _with_control_captured_at_commit(claim_toml: str, value: str) -> str:
        return claim_toml.replace(
            '  record = "evidence/does-not-exist-t-mutants.log"',
            '  record = "evidence/does-not-exist-t-mutants.log"\n'
            f'  captured_at_commit = "{value}"',
        )

    count += 1
    r = _run_case(
        "P3 captured_at_commit ABSENT: disclosure is optional, the base fixture validates "
        "cleanly with no mention of the field",
        _mini_manifest(_A1_RULE4_CONTROL_CLAIM),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "P3 captured_at_commit, full 40-hex sha: a well-shaped value is accepted (shape check "
        "only -- see the REGRESSION fixture below for the validity claim itself)",
        _mini_manifest(
            _with_control_captured_at_commit(
                _A1_RULE4_CONTROL_CLAIM, "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
            )
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "P3 captured_at_commit, 7-hex ABBREVIATED sha (git's own default abbreviation length): "
        "accepted, same floor CS-16's self-location shas use",
        _mini_manifest(
            _with_control_captured_at_commit(_A1_RULE4_CONTROL_CLAIM, "abcdefa")
        ),
        expect_pass=True,
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "P3 captured_at_commit that is not a plausible git commit id is refused (a disclosure "
        "that cannot be understood is worse than no disclosure)",
        _mini_manifest(
            _with_control_captured_at_commit(_A1_RULE4_CONTROL_CLAIM, "yesterday")
        ),
        expect_pass=False,
        expect_substr="captured_at_commit must be 7-40 lowercase hex characters",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "P3 captured_at_commit that is too short (6 hex) to resolve an identity is refused, "
        "same floor as CS-16's self-location shas",
        _mini_manifest(
            _with_control_captured_at_commit(_A1_RULE4_CONTROL_CLAIM, "abcdef")
        ),
        expect_pass=False,
        expect_substr="captured_at_commit must be 7-40 lowercase hex characters",
    )
    if r:
        failures.append(r)

    # P3 REGRESSION -- the ruled boundary itself: captured_at_commit can never rescue a stale
    # subject_hash. A fresh-looking, well-shaped captured_at_commit sitting right beside a
    # MISMATCHED subject_hash must still fail with the same evidence-subject binding error CS-8
    # already raises with no captured_at_commit present at all -- proving the validator never
    # reads captured_at_commit as an alternate or fallback validity signal (evidence-types.md
    # "Control block": "captured_at_commit is never consulted to validate ... a record").
    def _with_hygiene_captured_at_commit(claim_toml: str, value: str) -> str:
        return claim_toml.replace(
            '  record    = "evidence/does-not-exist-a.json"',
            '  record    = "evidence/does-not-exist-a.json"\n'
            f'  captured_at_commit = "{value}"',
        )

    count += 1
    r = _run_case(
        "P3 REGRESSION: a fresh-looking captured_at_commit does not rescue a MISMATCHED "
        "subject_hash -- the binding error still fires exactly as it would with no "
        "captured_at_commit present (evidence-types.md 'Control block')",
        _with_subject_hash(
            _mini_manifest(
                _with_hygiene_captured_at_commit(
                    _with_evidence_subject_hash(_A1_HYGIENE_NO_CONTROL_CLAIM, _HASH_A),
                    "abcdefabcdefabcdefabcdefabcdefabcdefabcd",
                )
            ),
            _HASH_B,
        ),
        expect_pass=False,
        expect_substr="evidence-subject binding MISMATCH",
    )
    if r:
        failures.append(r)

    # --------------------------------------------------------------------
    # F-1 (audit fix, RULED) -- the `subject:` M11 domain: single-file compute + compare; mismatch
    # --------------------------------------------------------------------

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _sf = Path(_td) / "subject-file-a.bin"
        _sf.write_bytes(b"the subject artifact's own raw bytes, case a\n")
        _computed = m11.digest_file("subject", _sf)
        _expected = "sha-512:" + hashlib.sha512(b"subject:" + _sf.read_bytes()).hexdigest()
        if not m11.is_well_formed(_computed) or _computed != _expected:
            failures.append(
                f"F-1 subject: domain COMPUTE: m11.digest_file('subject', ...) = {_computed!r}, "
                f"expected {_expected!r} (well-formed: {m11.is_well_formed(_computed)}) -- domain "
                f"separation must match a direct sha512(b'subject:' || bytes) computation"
            )

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _sf_a = Path(_td) / "subject-file-a.bin"
        _sf_b = Path(_td) / "subject-file-b.bin"
        _sf_a.write_bytes(b"subject content A\n")
        _sf_b.write_bytes(b"subject content B\n")
        _hash_a = m11.digest_file("subject", _sf_a)
        _hash_b = m11.digest_file("subject", _sf_b)
        if _hash_a == _hash_b:
            failures.append(
                "F-1 subject: domain COMPARE: two different subject files produced the same "
                f"subject_hash ({_hash_a!r}) -- domain-separated hashing must distinguish them"
            )

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _sf = Path(_td) / "subject-file.bin"
        _sf.write_bytes(b"a single-file subject, hashed end to end\n")
        _real_subject_hash = m11.digest_file("subject", _sf)
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(
            _with_subject_hash(
                _mini_manifest(
                    _with_evidence_subject_hash(_A1_HYGIENE_NO_CONTROL_CLAIM, _real_subject_hash)
                ),
                _real_subject_hash,
            )
        )
        _rep = validate(_p, strict=False)
        if not _rep.ok():
            failures.append(
                "F-1 subject: domain END-TO-END MATCH: a real computed subject_hash, declared on "
                "both [subject] and the evidence record, should validate cleanly -- got errors: "
                f"{_rep.errors}"
            )

    count += 1
    with tempfile.TemporaryDirectory() as _td:
        _sf_a = Path(_td) / "subject-file-a.bin"
        _sf_b = Path(_td) / "subject-file-b.bin"
        _sf_a.write_bytes(b"the real, currently-certified subject\n")
        _sf_b.write_bytes(b"a different subject content entirely\n")
        _hash_a = m11.digest_file("subject", _sf_a)
        _hash_b = m11.digest_file("subject", _sf_b)
        _p = Path(_td) / "acceptance.toml"
        _p.write_text(
            _with_subject_hash(
                _mini_manifest(
                    _with_evidence_subject_hash(_A1_HYGIENE_NO_CONTROL_CLAIM, _hash_b)
                ),
                _hash_a,
            )
        )
        _rep = validate(_p, strict=False)
        if _rep.ok() or not any("evidence-subject binding MISMATCH" in e for e in _rep.errors):
            failures.append(
                "F-1 subject: domain END-TO-END MISMATCH: an evidence record's subject_hash "
                "computed from a DIFFERENT real file than [subject].subject_hash should be a "
                f"hard error, got errors: {_rep.errors}"
            )

    count += 1
    try:
        m11.digest_bytes("subject", b"must not raise -- subject is not a RESERVED domain")
    except ValueError as e:
        failures.append(
            f"F-1 subject: domain must NOT be RESERVED (unlike 'claim') -- digest_bytes raised {e!r}"
        )

    # --------------------------------------------------------------------
    # F-3 (audit fix, RULED) -- [subject].record_root: records resolve; missing record; absent
    # record_root (unchanged behaviour)
    # --------------------------------------------------------------------

    def _rr_claim(record_value: str) -> str:
        return _A1_HYGIENE_NO_CONTROL_CLAIM.replace(
            '[[claim]]', '[[claim]]\nweight    = "unweighted"', 1
        ).replace('  record    = "evidence/does-not-exist-a.json"',
                   f'  record    = "{record_value}"')

    count += 1
    with tempfile.TemporaryDirectory() as _manifest_dir, \
         tempfile.TemporaryDirectory() as _subject_dir:
        _evdir = Path(_subject_dir) / "evidence"
        _evdir.mkdir()
        (_evdir / "rr-test.json").write_text('{"result": "pass"}\n')
        _p = Path(_manifest_dir) / "acceptance.toml"
        _text = _mini_manifest(_rr_claim("evidence/rr-test.json"), auto_record_hash=False)
        _text = _text.replace(
            "dirty  = false\n", f'dirty  = false\nrecord_root = "{_subject_dir}"\n', 1
        )
        _p.write_text(_text)
        _rep = validate(_p, strict=True)
        if not _rep.ok():
            failures.append(
                "F-3 record_root (absolute) RESOLVES: a record pointer that exists only under "
                f"record_root, not beside the manifest, should validate cleanly -- got errors: "
                f"{_rep.errors}, warnings: {_rep.warnings}"
            )

    count += 1
    with tempfile.TemporaryDirectory() as _manifest_dir, \
         tempfile.TemporaryDirectory() as _subject_dir:
        # deliberately do NOT create evidence/rr-missing.json anywhere
        _p = Path(_manifest_dir) / "acceptance.toml"
        _text = _mini_manifest(_rr_claim("evidence/rr-missing.json"), auto_record_hash=False)
        _text = _text.replace(
            "dirty  = false\n", f'dirty  = false\nrecord_root = "{_subject_dir}"\n', 1
        )
        _p.write_text(_text)
        _rep = validate(_p, strict=True)
        if _rep.ok() or not any(
            "record pointer does not exist: evidence/rr-missing.json" in e for e in _rep.errors
        ):
            failures.append(
                "F-3 record_root (absolute) MISSING record: a record pointer absent under "
                f"record_root should be a strict-mode error -- got errors: {_rep.errors}"
            )

    count += 1
    with tempfile.TemporaryDirectory() as _manifest_dir, \
         tempfile.TemporaryDirectory() as _subject_dir:
        # the evidence file exists ONLY under _subject_dir; with no record_root declared, the
        # pointer must still resolve manifest-relative (unchanged behaviour) and therefore fail.
        _evdir = Path(_subject_dir) / "evidence"
        _evdir.mkdir()
        (_evdir / "rr-elsewhere.json").write_text('{"result": "pass"}\n')
        _p = Path(_manifest_dir) / "acceptance.toml"
        _p.write_text(_mini_manifest(_rr_claim("evidence/rr-elsewhere.json"), auto_record_hash=False))
        _rep = validate(_p, strict=True)
        if _rep.ok() or not any(
            "record pointer does not exist: evidence/rr-elsewhere.json" in e for e in _rep.errors
        ):
            failures.append(
                "F-3 record_root ABSENT: unchanged behaviour means resolution stays "
                "manifest-relative -- a file that exists only under a separate directory should "
                f"still be reported missing, got errors: {_rep.errors}"
            )

    count += 1
    with tempfile.TemporaryDirectory() as _manifest_dir:
        # a RELATIVE record_root resolves against the manifest's own directory, same as `record`
        # itself defaults to.
        _subject_subdir = Path(_manifest_dir) / "subject-repo"
        (_subject_subdir / "evidence").mkdir(parents=True)
        (_subject_subdir / "evidence" / "rr-rel.json").write_text('{"result": "pass"}\n')
        _p = Path(_manifest_dir) / "acceptance.toml"
        _text = _mini_manifest(_rr_claim("evidence/rr-rel.json"), auto_record_hash=False)
        _text = _text.replace(
            "dirty  = false\n", 'dirty  = false\nrecord_root = "subject-repo"\n', 1
        )
        _p.write_text(_text)
        _rep = validate(_p, strict=True)
        if not _rep.ok():
            failures.append(
                "F-3 record_root (manifest-relative) RESOLVES: a relative record_root should "
                f"resolve against the manifest's own directory -- got errors: {_rep.errors}, "
                f"warnings: {_rep.warnings}"
            )

    count += 1
    r = _run_case(
        "F-3 [subject].record_root malformed (non-string) is refused",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            "dirty  = false\n", "dirty  = false\nrecord_root = 7\n", 1
        ),
        expect_pass=False,
        expect_substr="[subject].record_root must be a nonempty string",
    )
    if r:
        failures.append(r)

    count += 1
    r = _run_case(
        "F-3 [subject].repo malformed (non-string) is refused",
        _mini_manifest(_A1_HYGIENE_NO_CONTROL_CLAIM).replace(
            "dirty  = false\n", "dirty  = false\nrepo = 7\n", 1
        ),
        expect_pass=False,
        expect_substr="[subject].repo must be a nonempty string",
    )
    if r:
        failures.append(r)

    if failures:
        for f in failures:
            print(f"SELFTEST FAIL: {f}", file=sys.stderr)
        print(f"SELFTEST FAILED: {len(failures)}/{count} cases", file=sys.stderr)
        return 1

    print(f"SELFTEST PASS: {count} fixtures")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args:
        print("usage: check_acceptance.py [--strict] [--strict-weight] FILE [FILE...]",
              file=sys.stderr)
        print("       check_acceptance.py --selftest", file=sys.stderr)
        return 2

    if "--selftest" in args:
        if len(args) != 1:
            print("usage: check_acceptance.py --selftest", file=sys.stderr)
            return 2
        return selftest()

    strict = False
    strict_weight = False
    files = []
    for a in args:
        if a == "--strict":
            strict = True
        elif a == "--strict-weight":
            # core.md §8.1's ratchet: transitional weight refusals become hard errors.
            strict_weight = True
        elif a.startswith("--"):
            print(f"usage error: unknown option {a!r}", file=sys.stderr)
            return 2
        else:
            files.append(a)

    if not files:
        print("usage error: no FILE arguments given", file=sys.stderr)
        return 2

    # core.md §8.3 (CS-20): tri-state contract, `invalid` (1) and `indeterminate` (2) are
    # distinct, non-accepting exit codes. Across multiple files, the worst state wins in the
    # SAME priority order Reporter.state() uses per-file: any `invalid` file makes the whole run
    # exit 1 regardless of indeterminate files elsewhere; only if none is `invalid` does any
    # `indeterminate` file make the run exit 2.
    worst = "valid"
    for f in files:
        path = Path(f)
        if not path.is_file():
            print(f"ERROR {f}: not a file")
            worst = "invalid"
            continue
        rep = validate(path, strict, strict_weight=strict_weight)
        for line in rep.lines():
            print(line)
        nw = getattr(rep, "n_weighted", 0)
        nu = getattr(rep, "n_unweighted", 0)
        npd = getattr(rep, "n_pending", 0)
        pend = f", weight-pending: {npd}" if npd else ""
        state = rep.state()
        # CS-22: an illustrative manifest's PASS/valid line MUST be labelled as such -- an
        # unlabelled illustrative pass reads exactly like a certified one.
        tag = " ILLUSTRATIVE" if getattr(rep, "illustrative", False) else ""
        if state == "valid":
            n_warn = len(rep.warnings)
            suffix = f" ({n_warn} warning{'s' if n_warn != 1 else ''})" if n_warn else ""
            # core.md W5: state the tier mix; never make a consumer infer it.
            print(f"PASS{tag} {f}{suffix} [weighted: {nw}, unweighted: {nu}{pend}]")
        elif state == "indeterminate":
            n_indet = len(rep.indeterminate)
            print(f"INDETERMINATE{tag} {f} ({n_indet} case"
                  f"{'s' if n_indet != 1 else ''}) [weighted: {nw}, unweighted: {nu}{pend}]")
            if worst != "invalid":
                worst = "indeterminate"
        else:
            print(f"FAIL{tag} {f} ({len(rep.errors)} error"
                  f"{'s' if len(rep.errors) != 1 else ''}) "
                  f"[weighted: {nw}, unweighted: {nu}{pend}]")
            worst = "invalid"

    return {"valid": 0, "invalid": 1, "indeterminate": 2}[worst]


if __name__ == "__main__":
    sys.exit(main(sys.argv))
