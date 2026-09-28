"""Verification meaning: species, ladder, control policy and record declarations."""
from __future__ import annotations

BANDS = {"A0", "A1", "A2", "A3", "A3.5", "A4"}


KIND_REGISTRY = {
    "kani-harness": {
        "family": "bmc",
        "extra": {"bounds": "str-nonempty", "semantics": "str-any"},
    },
    "lean-theorem": {
        "family": "kernel",
        "extra": {"axioms": "list", "semantics": "str-nonempty"},
    },
    "flux-refinement": {
        "family": "smt-refinement",
        "extra": {"bounds": "str-nonempty", "semantics": "str-nonempty"},
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


SYMBOLIC_DOMAIN_FAMILIES = {"bmc", "kernel", "smt-refinement"}


FREEDOM_WORDS = ("panic", "crash", "freedom", "ub")


MUTATION_ONLY = {"mutation"}                    # A3/A4, and oracle-bearing A1


MUTATION_OR_ABLATION = {"mutation", "ablation"}  # A2 (memory safety / unsafe surface)


CARRIER_FAMILIES_FOR_BAND = {
    "A4": {"kernel"},
    "A3": {"bmc"},
    "A2": {"bmc", "dynamic"},
    "A1": {"dynamic"},  # only consulted for the oracle-bearing-A1 case
}


DYNAMIC_FREEDOM_KINDS = {"miri", "fuzz"}


DYNAMIC_ORACLE_KINDS = {"unit-test", "property-test"}


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

    # per-band control-kind whitelist (mirrors the engine's audit, which requires kind=="mutation"
    # for its controls-check): `planted-twin` proves the pipeline can reject AT ALL — a
    # satisfiability/pipeline (acknowledgment-witness) signal — never that THIS claim's own oracle
    # catches a mutation of THIS impl/theorem. It NEVER satisfies a band-lift gate, at any band. It
    # may still be recorded (disclosure evidence), it just doesn't count here.
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
        # a functional (oracle-bearing) claim resting on dynamic evidence ALONE needs a control
        # to reach A1 (assurance-bands.md rule 4); no-oracle species (kani-harness zero-annotation
        # panic-freedom, mechanical hygiene, miri/fuzz freedom) reach A1 without one.
        if has_oracle_dynamic and not (has_kani or has_mechanical or has_freedom_dynamic):
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
            statement = (claim.get("statement") or "").lower()
            if not any(w in statement for w in FREEDOM_WORDS):
                rep.warn(
                    f"{ctx}: dynamic-only evidence at band A1 but statement doesn't read as a "
                    f"freedom claim (no 'panic'/'crash'/'freedom'/'UB')"
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


LADDER = {"ladder_id": "acceptance/verification/A", "tokens": ["A0", "A1", "A2", "A3", "A3.5", "A4"],
          "control_free_ceiling": {"default": "A0", "kani-harness": "A1", "mechanical": "A1", "miri": "A1", "fuzz": "A1", "flux-refinement": "A3.5"}}
FAMILIES = {"kernel": "T1", "bmc": "T2", "smt-refinement": "T2", "dynamic": "T3", "mechanical": "T4", "judgment": "T5"}
KINDS = {k: {**v, "extra_required": list(v["extra"])} for k, v in KIND_REGISTRY.items()}
OPTIONAL_RECORD_FIELDS = {"cover_only": bool, "cover_satisfied": int, "cover_total": int}

def check(doc, ctx):
    from check_core import Finding, Reporter, _check_field
    rep = Reporter(str(ctx.path))
    pending = []
    for claim in doc.get("claim", []):
        if not isinstance(claim, dict):
            continue
        label = f"claim {claim.get('id')!r}"
        evs = [e for e in claim.get("evidence", []) if isinstance(e, dict)] if isinstance(claim.get("evidence", []), list) else []
        all_evs = evs
        if claim.get("weight") == "weighted":
            claim = {**claim, "evidence": [e for e in evs if e.get("kind") != "acceptance-claim"]}
            evs = claim["evidence"]
            check_recipe_requirements(rep, label, claim)
            check_grade_companions(rep, label, claim)
            if claim.get("grade") in GRADES_REQUIRING_SELF_VERIFY and not _has_watched_fail_witness(claim):
                pending.append(Finding("pending", "no watched-fail witness (W2.5, P2) — needs a [claim.self_verify.watched_fail] table, an observed-red control naming this claim, or (not-covered) a positive_control", claim.get("id")))
            if not evs and all_evs:
                rep.error(f"{label}: B8: reference-only claim is never weight-bearing")
        for eidx, ev in enumerate(all_evs):
            control = ev.get("control")
            if isinstance(control, dict):
                ck = control.get("kind")
                if ck not in CONTROL_KIND_VALUES:
                    rep.error(f"{label} evidence[{eidx}]: control.kind must be one of {sorted(CONTROL_KIND_VALUES)}, got {ck!r}")
        if claim.get("band") == "A3.5":
            rep.warn(f"{label}: reserved band — tool not adopted")
        if claim.get("weight") == "weighted" and claim.get("grade") == "contract" and evs:
            fams = {e.get("family") for e in evs}
            if not (fams & SYMBOLIC_DOMAIN_FAMILIES):
                rep.error(f"{label}: WEIGHT REFUSED: grade 'contract' requires a SYMBOLIC domain (0.1-DRAFT §0.5), but every evidence record on this claim is of family {sorted(f for f in fams if f)} — none of {sorted(SYMBOLIC_DOMAIN_FAMILIES)}. Evidence that enumerates values witnesses points, not sets: §0.5 says a test is never `contract`. Either the claim is `probe`/`test-only`, or it needs evidence that reasons over the domain")
        effective_band = claim.get("band", LADDER["tokens"][0])
        if claim.get("status") == "evidenced" and effective_band in BANDS and evs and not any(e.get("family") == "reference" for e in evs):
            check_band_reachability(rep, label, {**claim, "band": effective_band}, evs)
        for e in evs:
            if "cover_only" in e and not isinstance(e["cover_only"], bool):
                rep.error(f"B9: {label}: cover_only must be a bool")
            for key in ("cover_satisfied", "cover_total"):
                if key in e: _check_field(rep, label, e, key, "int-nonneg")
            if ("cover_satisfied" in e) != ("cover_total" in e):
                rep.error(f"B9: {label}: cover_satisfied / cover_total must be a pair")
            if all(type(e.get(k)) is int for k in ("cover_satisfied", "cover_total")) and e["cover_satisfied"] > e["cover_total"]:
                rep.error(f"B9: {label}: cover_satisfied exceeds cover_total")
    def owner(message):
        return next((c.get("id") for c in doc.get("claim", []) if isinstance(c, dict) and message.startswith(f"claim {c.get('id')!r}")), None)
    return [Finding("error", m, owner(m)) for m in rep.errors] + [Finding("warning", m) for m in rep.warnings] + pending


from check_core import (_is_nonempty_str, _watched_fail_block_is_valid, _is_weighted, _is_phrase)
from acceptance_grammar import (GRADES_REQUIRING_RECIPE as GRADES_REQUIRING_SELF_VERIFY,
    GRADES_REQUIRING_BOUNDS, bounds_token, has_bounds_tail, is_scope_locator, SCOPE_REF_EXPECTATION)
CONTROL_KIND_VALUES = {"mutation", "ablation", "planted-twin"}

def _has_watched_fail_witness(claim: dict) -> bool:
    """0.1-DRAFT §4.1 (P2): has this claim's recipe been watched to fail? Any ONE of three,
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

def _is_valid_claim_bounds(v) -> bool:
    return bounds_token(v) is not None

def check_grade_companions(rep: Reporter, ctx: str, claim: dict) -> None:
    """0.1-DRAFT.md §1/§5: mandatory claim-level companion fields keyed by `grade`, distinct from
    self_verify (handled in check_self_verify). No-ops for grades that don't require any of
    these, and for a missing/invalid grade (already reported elsewhere)."""
    grade = claim.get("grade")

    if grade in GRADES_REQUIRING_BOUNDS:
        bounds = claim.get("bounds")
        if not _is_valid_claim_bounds(bounds):
            rep.error(
                f"{ctx}: grade {grade!r} requires a claim-level 'bounds' field, a nonempty "
                f"string starting with 'bounded' or 'unbounded' (0.1-DRAFT §5), got {bounds!r}"
            )
        elif not has_bounds_tail(bounds):
            # 0.1-DRAFT §5: the token alone is not a declaration. §5 requires "plus free text
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
                f"(0.1-DRAFT §1)"
            )
        elif not is_scope_locator(scope_ref):
            # `out-of-scope` weight attaches to "the producer declared this, HERE" and to
            # nothing else, so the "here" has to be somewhere a reader can go. Free prose
            # ("nonsense", "we decided not to") records nothing and carried weight until
            # 2026-08-25 (round 2, finding 3).
            rep.error(
                f"{ctx}: WEIGHT REFUSED: scope_ref must be a LOCATOR — {SCOPE_REF_EXPECTATION} "
                f"— not free prose. `out-of-scope` weight attaches to 'the producer declared "
                f"this, here', so a reader must be able to go there (0.1-DRAFT §1/§7.1), got "
                f"{scope_ref!r}"
            )

    if grade == "unspecified" and claim.get("clause_source") != "none":
        rep.warn(
            f"{ctx}: grade = 'unspecified' SHOULD carry clause_source = 'none' (0.1-DRAFT §1). "
            f"Not an error: this grade is never weight-eligible (W3)"
        )

def check_recipe_requirements(rep, ctx, claim):
    grade = claim.get("grade")
    sv = claim.get("self_verify")
    if grade in GRADES_REQUIRING_SELF_VERIFY:
        if not isinstance(sv, dict):
            rep.error(
                f"{ctx}: grade {grade!r} requires a [claim.self_verify] table with a nonempty "
                f"'command' (0.1-DRAFT §1/§3)"
            )
            return
        if not _is_nonempty_str(sv.get("command")):
            rep.error(
                f"{ctx}: grade {grade!r} requires self_verify.command to be a nonempty string "
                f"(0.1-DRAFT §1/§3)"
            )

    if not isinstance(sv, dict): return
    # 0.1-DRAFT.md §4: grade = "not-covered" REQUIRES a nonempty positive_control, unconditionally
    # (not just when the command looks like an absence check) — a grep zero is a claim about the
    # pattern, not the code.
    if grade == "not-covered":
        pc = sv.get("positive_control")
        if not _is_nonempty_str(pc):
            rep.error(
                f"{ctx}: grade = 'not-covered' requires a nonempty self_verify.positive_control "
                f"(0.1-DRAFT §4)"
            )
        elif not _is_phrase(pc):
            # positive_control is a weighted-tier obligation AND this grade's §4.1 witness, so a
            # single token satisfying it was a phrase match earning weight -- the one thing §4.1
            # says may never happen. Same shape floor as watched_fail.perturbed/observed, and the
            # same honest limit: it cannot tell a real control from a plausible sentence.
            rep.error(
                f"{ctx}: self_verify.positive_control must NAME the input or target the same "
                f"command demonstrably matches — a single token is not a control (0.1-DRAFT §4), "
                f"got {pc!r}"
            )

