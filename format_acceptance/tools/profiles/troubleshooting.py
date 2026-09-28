#!/usr/bin/env python3
"""Troubleshooting meaning: acceptance/troubleshooting (revision T7 to 0.1.0).

Implements `profiles/troubleshooting/PROFILE.md` 0.1.0: for each declared fault class, the
evidence an artifact retains or exposes at run time is sufficient to reach the declared diagnostic
outcome. Composed by check_core.dispatch when [format].profile is "acceptance/troubleshooting" or a
suffix under it; this module owns the meaning half only (protocol.md §6.6 item 8) -- no binding for
`/tool` exists yet (bindings/tool.py), so a suffixed leaf is INDETERMINATE unless --meaning-only is
requested (see profiles/troubleshooting/PROFILE.md "Admissibility check").

0.1.0 defines its own closed vocabulary.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from profiles import verification

MEANING = "acceptance/troubleshooting"
SUFFIXES = {"", "/tool"}

# PROFILE.md "Closed vocabularies": closed, ordered ladder. A higher outcome
# implies every lower one.
OUTCOMES = ("detect", "isolate_fault_domain", "reconstruct_causal_sequence", "identify_root_cause")

# This profile's own three families (PROFILE.md "Closed vocabularies"), mapped onto the core's
# T1..T5 ordinal using the SAME tier tokens acceptance/verification already closes.
FAMILIES = {
    "injected-diagnosis": "T3",
    "telemetry-completeness": "T3",
    "diagnostic-structure": "T4",
}

# Three evidence kinds, one per family (PROFILE.md "Closed vocabularies"). No extra required
# fields beyond the universal ones (kind/family/ref/result/tool/record): the diagnoser/blinding/
# results/held_out shape is meaning-specific and checked below, not through the KINDS extra-field
# registry (those are nested tables, and _check_field only validates scalar fields).
KINDS = {
    "blind-diagnosis": {"family": "injected-diagnosis", "extra": {}},
    "telemetry-completeness-check": {"family": "telemetry-completeness", "extra": {}},
    "diagnostic-structure-check": {"family": "diagnostic-structure", "extra": {}},
}

# Reused by reference (as conformance.py reuses verification's), not a second ladder registry:
# assurance-bands.md's A0-A4 apply unchanged, and no kind in this profile earns a control-free
# ceiling above A0 (PROFILE.md "Closed vocabularies" / "Assurance bands").
LADDER = verification.LADDER

DIAGNOSER_KINDS = {"deterministic", "human", "model-seat"}
# 0.1.0 closes the isolation-attestation gap (row 20): a diagnoser that is not a fixed, checkable
# piece of code needs its own working-context attested, since nothing else records what it could
# see.
ISOLATED_DIAGNOSER_KINDS = {"human", "model-seat"}
TRUTH_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
STATUSES = ("gap", "evidenced", "partial")
# 0.1.0 row 2: the only grading token this format admits in this pass -- a closed enum of one, so
# a future top-k/threshold grading needs its own document edit, not a silent new string.
GRADINGS = ("exact-set",)


def _nonempty_str(v) -> bool:
    return isinstance(v, str) and bool(v)


def _evs(claim: dict) -> list[dict]:
    evidence = claim.get("evidence", [])
    return [e for e in evidence if isinstance(e, dict)] if isinstance(evidence, list) else []


def _check_fields(add_error, cid, label, claim):
    """PROFILE.md 'Required fields over the core': fault_class and outcome on every claim."""
    if not _nonempty_str(claim.get("fault_class")):
        add_error(cid, f"{label}: R-T-FIELDS: fault_class must be a nonempty string")
    if claim.get("outcome") not in OUTCOMES:
        add_error(cid, f"{label}: R-T-FIELDS: outcome must be one of {OUTCOMES}, "
                        f"got {claim.get('outcome')!r}")


def _check_scenarios(add_error, cid, label, claim):
    """C-T1 (gap rule): a fault class with no exercised scenario MUST be status='gap'; a non-gap
    claim's scenarios are the bounds -- a non-empty list of unique, nonempty-string ids (row 18:
    type-checked before set() ever sees the value, so a malformed entry is a finding, not a
    crash)."""
    status = claim.get("status")
    scenarios = claim.get("scenarios")
    if status == "gap":
        if scenarios not in (None, []):
            add_error(cid, f"{label}: C-T1: status='gap' claims a fault class with no exercised "
                            f"scenario; 'scenarios' must be empty or absent, got {scenarios!r}")
        return
    if not isinstance(scenarios, list) or not scenarios:
        add_error(cid, f"{label}: C-T1: 'scenarios' must be a non-empty list of unique ids unless "
                        f"status='gap' (a fault class with no exercised scenario MUST be "
                        f"status='gap'), got {scenarios!r}")
        return
    if not all(isinstance(s, str) and s for s in scenarios):
        add_error(cid, f"{label}: C-T1: every 'scenarios' entry must be a nonempty string, "
                        f"got {scenarios!r}")
        return
    if len(set(scenarios)) != len(scenarios):
        add_error(cid, f"{label}: C-T1: 'scenarios' must be unique ids, got duplicates in "
                        f"{scenarios!r}")


def _check_status(add_error, cid, label, claim):
    """Row 13 (C-T5 extension): the module lists every status it admits and rules each --
    'shortfall' is only meaningful, and only permitted, on a status='partial' claim."""
    status = claim.get("status")
    if status not in STATUSES:
        add_error(cid, f"{label}: C-T5: status must be one of {STATUSES}, got {status!r}")
        return
    if status != "partial" and claim.get("shortfall") is not None:
        add_error(cid, f"{label}: C-T5: 'shortfall' is only permitted when status='partial', "
                        f"got status={status!r} with shortfall={claim.get('shortfall')!r}")


def _check_struct_ceiling(add_error, cid, label, claim, evs):
    """C-T6 (row 12 extension): a claim discharged ONLY by diagnostic-structure evidence (T4,
    static correlation/schema checks) cannot back an outcome above 'detect' -- structure alone
    shows the fields exist, not that a diagnosis was reached -- AND can never discharge ANY claim
    (status='evidenced') at any outcome, since a static check is not a diagnosis; it only supports
    another family's evidence (PROFILE.md 'Closed vocabularies', family/tier ceiling table)."""
    if not evs:
        return
    families_used = {e.get("family") for e in evs}
    if families_used != {"diagnostic-structure"}:
        return
    outcome = claim.get("outcome")
    if outcome in OUTCOMES and OUTCOMES.index(outcome) > OUTCOMES.index("detect"):
        add_error(cid, f"{label}: C-T6: evidence is diagnostic-structure only (T4, static "
                        f"correlation/schema checks) and cannot back an outcome above 'detect', "
                        f"got outcome {outcome!r}")
    if claim.get("status") == "evidenced":
        add_error(cid, f"{label}: C-T6: evidence is diagnostic-structure only (T4, static "
                        f"correlation/schema checks) and can never discharge a claim "
                        f"(status='evidenced') on its own -- it only supports another family's "
                        f"evidence")


def _check_blind_diagnosis_required(add_error, cid, label, claim, evs):
    """C-T7 (row 3, new): a non-gap claim whose outcome is above 'detect' MUST carry at least one
    blind-diagnosis evidence record -- other families may support that record but never discharge
    the claim on their own."""
    status = claim.get("status")
    outcome = claim.get("outcome")
    if status == "gap" or outcome not in OUTCOMES:
        return
    if OUTCOMES.index(outcome) <= OUTCOMES.index("detect"):
        return
    if not any(e.get("kind") == "blind-diagnosis" for e in evs):
        add_error(cid, f"{label}: C-T7: a non-gap claim with outcome {outcome!r} (above 'detect') "
                        f"MUST carry at least one 'blind-diagnosis' evidence record; other "
                        f"families support, never discharge")


def _check_outcome_criterion(add_error, cid, label, claim):
    """Row 2: outcome_criterion = {granularity, grading} is required on every claim; 0.1.0 admits
    only grading='exact-set' (FC2's 'key in predicted' leniency is withdrawn)."""
    oc = claim.get("outcome_criterion")
    if not isinstance(oc, dict) or not _nonempty_str(oc.get("granularity")):
        add_error(cid, f"{label}: R-T-OUTCOME-CRITERION: outcome_criterion = "
                        f"{{granularity, grading}} is required, got {oc!r}")
        return
    if oc.get("grading") not in GRADINGS:
        add_error(cid, f"{label}: R-T-OUTCOME-CRITERION: outcome_criterion.grading must be one "
                        f"of {GRADINGS} (the only token 0.1.0 admits), got {oc.get('grading')!r}")


def _check_scenario_source(add_error, cid, label, claim):
    """Row 14: scenario_source = {rule, population} is required -- the generator rule and the
    population count a claim's 'scenarios' is measured against, so coverage is a count out of a
    stated population, not whatever the producer happened to run."""
    ss = claim.get("scenario_source")
    if (not isinstance(ss, dict) or not _nonempty_str(ss.get("rule"))
            or not isinstance(ss.get("population"), int) or isinstance(ss.get("population"), bool)
            or ss.get("population") <= 0):
        add_error(cid, f"{label}: R-T-SCENARIO-SOURCE: scenario_source = {{rule, population}} is "
                        f"required (rule: nonempty string, population: positive int), got {ss!r}")
        return
    scenarios = claim.get("scenarios")
    if isinstance(scenarios, list) and ss["population"] < len(scenarios):
        add_error(cid, f"{label}: R-T-SCENARIO-SOURCE: scenario_source.population "
                        f"({ss['population']}) must be >= the number of exercised scenarios "
                        f"({len(scenarios)})")


def _check_diagnoser(add_error, cid, ectx, ev):
    """PROFILE.md 'Required fields over the core': every blind-diagnosis evidence record names a
    diagnoser kind and identity, plus (row 8) a digest of the diagnoser's own code/prompt and
    (row 8) whether the run was held out."""
    diagnoser = ev.get("diagnoser")
    if (not isinstance(diagnoser, dict) or diagnoser.get("kind") not in DIAGNOSER_KINDS
            or not _nonempty_str(diagnoser.get("id"))):
        add_error(cid, f"{ectx}: R-T-DIAGNOSER: blind-diagnosis evidence requires "
                        f"diagnoser = {{kind in {sorted(DIAGNOSER_KINDS)}, id}}, got {diagnoser!r}")
        diagnoser = diagnoser if isinstance(diagnoser, dict) else {}
    digest = diagnoser.get("digest")
    if not isinstance(digest, str) or not TRUTH_HASH_RE.match(digest):
        add_error(cid, f"{ectx}: R-T-DIAGNOSER: diagnoser.digest must be 'sha256:<64hex>' (a hash "
                        f"of the diagnoser's own code or prompt), got {digest!r}")
    held_out = ev.get("held_out")
    if not isinstance(held_out, bool):
        add_error(cid, f"{ectx}: R-T-DIAGNOSER: blind-diagnosis evidence requires a bool "
                        f"'held_out' field (true|false), got {held_out!r}")


def _check_isolation(add_error, cid, label, ectx, claim, ev):
    """Row 20: a model-seat or human diagnoser needs its own working context attested (packet or
    working-directory digest, plus the tools it could use), and -- since no isolation check exists
    in this format yet -- is capped at the control-free ceiling (A0) regardless of what it
    attests."""
    diagnoser = ev.get("diagnoser")
    kind = diagnoser.get("kind") if isinstance(diagnoser, dict) else None
    if kind not in ISOLATED_DIAGNOSER_KINDS:
        return
    isolation = diagnoser.get("isolation")
    if (not isinstance(isolation, dict) or not _nonempty_str(isolation.get("digest"))
            or not isinstance(isolation.get("tools"), list) or not isolation.get("tools")
            or not all(_nonempty_str(t) for t in isolation.get("tools"))):
        add_error(cid, f"{ectx}: R-T-ISOLATION: diagnoser kind {kind!r} requires "
                        f"diagnoser.isolation = {{digest, tools}} (a packet or working-directory "
                        f"digest and the list of tools it could use), got {isolation!r}")
    band = claim.get("band")
    tokens = LADDER["tokens"]
    if band not in (None, tokens[0]):
        add_error(cid, f"{label}: R-T-ISOLATION: diagnoser kind {kind!r} is capped at "
                        f"{tokens[0]!r} until an isolation check exists in this format, "
                        f"got band {band!r}")


def _check_blinding(add_error, cid, ectx, ev):
    """PROFILE.md 'Required fields over the core': the blinding record -- the sealed-truth hash
    committed before the diagnosis runs, the list of evidence the diagnoser was permitted to see,
    and (row 7) the commit that carried the sealed hashes before the run."""
    blinding = ev.get("blinding")
    if not isinstance(blinding, dict):
        add_error(cid, f"{ectx}: R-T-BLINDING: blind-diagnosis evidence requires a 'blinding' table")
        return
    truth_hash = blinding.get("truth_hash")
    if not isinstance(truth_hash, str) or not TRUTH_HASH_RE.match(truth_hash):
        add_error(cid, f"{ectx}: R-T-BLINDING: blinding.truth_hash must be 'sha256:<64hex>', "
                        f"got {truth_hash!r}")
    visible = blinding.get("visible_evidence")
    if not isinstance(visible, list) or not visible or not all(_nonempty_str(x) for x in visible):
        add_error(cid, f"{ectx}: R-T-BLINDING: blinding.visible_evidence must be a non-empty list "
                        f"of strings, got {visible!r}")
    committed_at = blinding.get("committed_at")
    if not isinstance(committed_at, str) or not COMMIT_RE.match(committed_at):
        add_error(cid, f"{ectx}: R-T-BLINDING: blinding.committed_at must be 40 lowercase hex "
                        f"chars (the commit that carried the sealed hashes before the run), "
                        f"got {committed_at!r}")


def _open_record_rows(ctx, pointer, label):
    """Row 4: open the hash-bound `record` pointer (already digest-verified at the core level by
    B16's check_record_hashes) under this profile's own declared row schema: a JSON object with a
    `rows` list, each row {fault_class, id, outcome} (nonempty strings). Returns (rows, errors);
    rows is None when the pointer, the bytes or the shape do not resolve -- the caller reports
    `errors` and skips the coverage comparison rather than crashing."""
    from check_core import Context as _Context, Reporter as _Reporter, _resolve_pointer
    shim = _Reporter(str(ctx.path))
    shim.context = _Context(ctx.path, ctx.root)
    shim.unknowns = []
    target = _resolve_pointer(shim, pointer, label)
    if target is None:
        return None, (shim.errors or [f"{label}: cannot resolve record pointer"])
    try:
        raw = target.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return None, [f"{label}: unreadable or unparsable record: {exc}"]
    if not (isinstance(data, dict) and isinstance(data.get("rows"), list)):
        return None, [f"{label}: record must be a JSON object with a 'rows' list "
                       f"(declared row schema)"]
    rows = []
    for i, row in enumerate(data["rows"]):
        if not (isinstance(row, dict) and _nonempty_str(row.get("fault_class"))
                and _nonempty_str(row.get("id")) and _nonempty_str(row.get("outcome"))):
            return None, [f"{label}: record row[{i}] must be "
                           f"{{fault_class, id, outcome}} (nonempty strings), got {row!r}"]
        rows.append(row)
    return rows, []


def _check_record_schema(add_error, cid, label, ectx, claim, ev, ctx, record_owners):
    """Row 4: the anti-cherry-pick rule checked against the hashed evidence file itself, not just
    the producer's own inline tables. `scenarios` MUST equal every record row of this claim's
    fault_class; `results` MUST equal what those rows give; a fault_class is claimed by exactly one
    claim per record."""
    record_ptr = ev.get("record")
    if not _nonempty_str(record_ptr):
        return  # core B6 already flags a missing/invalid record pointer
    rows, errors = _open_record_rows(ctx, record_ptr, f"{ectx}.record")
    if rows is None:
        for msg in errors:
            add_error(cid, f"{label}: C-T5: {msg}")
        return

    fault_class = claim.get("fault_class")
    matching = [r for r in rows if r.get("fault_class") == fault_class]
    record_ids = {r["id"] for r in matching}
    scenarios = claim.get("scenarios")
    if isinstance(scenarios, list) and all(isinstance(s, str) for s in scenarios):
        scenario_ids = set(scenarios)
        if scenario_ids != record_ids:
            missing = sorted(record_ids - scenario_ids)
            extra = sorted(scenario_ids - record_ids)
            add_error(cid, f"{label}: C-T5: claim.scenarios must equal every record row of "
                            f"fault_class {fault_class!r} (missing {missing}, extra {extra})")

    results = ev.get("results")
    if isinstance(results, dict):
        for row in matching:
            rid, expected = row["id"], row["outcome"]
            if rid in results and results[rid] != expected:
                add_error(cid, f"{label}: C-T5: evidence.results[{rid!r}] = {results[rid]!r} "
                                f"does not match the record's own outcome {expected!r} for "
                                f"that scenario")

    key = (ev.get("record_hash"), fault_class)
    if key[0] is not None and fault_class is not None:
        if key in record_owners and record_owners[key] != cid:
            add_error(cid, f"{label}: C-T5: fault_class {fault_class!r} is already claimed by "
                            f"{record_owners[key]!r} against the same record -- a fault_class "
                            f"appears in exactly one claim per record")
        else:
            record_owners.setdefault(key, cid)


def _check_coverage_and_shortfall(add_error, cid, label, ectx, claim, ev):
    """C-T5 (anti-cherry-pick, a design decision 2026-09-24): a blind-diagnosis evidence record's
    'results' table covers EXACTLY the claim's scenarios; status='evidenced' requires every
    scenario to reach at least the claimed outcome; otherwise status MUST be 'partial' with
    'shortfall' exactly matching the scenarios that fell short of the outcome (row 18: shortfall is
    type-checked before sorted() ever sees it)."""
    scenarios = claim.get("scenarios")
    outcome = claim.get("outcome")
    results = ev.get("results")
    if not isinstance(results, dict):
        add_error(cid, f"{ectx}: C-T5: blind-diagnosis evidence requires a 'results' table "
                        f"covering exactly the claim's scenarios, got {results!r}")
        return
    if not isinstance(scenarios, list):
        return  # already reported by _check_scenarios
    try:
        scenario_ids, result_ids = set(scenarios), set(results)
    except TypeError:
        return  # already reported by _check_scenarios (unhashable entries)
    if result_ids != scenario_ids:
        missing, extra = sorted(scenario_ids - result_ids), sorted(result_ids - scenario_ids)
        add_error(cid, f"{ectx}: C-T5: evidence.results must cover EXACTLY the claim's scenarios "
                        f"(missing {missing}, extra {extra})")
        return
    if outcome not in OUTCOMES:
        return  # already reported by _check_fields
    below = sorted(
        sid for sid, reached in results.items()
        if reached not in OUTCOMES or OUTCOMES.index(reached) < OUTCOMES.index(outcome)
    )
    status = claim.get("status")
    if status == "evidenced":
        if below:
            add_error(cid, f"{label}: C-T5: status='evidenced' requires every scenario to reach "
                            f">= {outcome!r}; shortfall {below}")
    elif status == "partial":
        shortfall = claim.get("shortfall")
        if not below:
            add_error(cid, f"{label}: C-T5: status='partial' but every scenario reached "
                            f">= {outcome!r} (no shortfall) -- use status='evidenced'")
        elif not isinstance(shortfall, list) or not all(isinstance(s, str) and s for s in shortfall):
            add_error(cid, f"{label}: C-T5: status='partial' requires 'shortfall' to be a list "
                            f"of nonempty strings, got {shortfall!r}")
        elif sorted(shortfall) != below:
            add_error(cid, f"{label}: C-T5: status='partial' requires 'shortfall' to exactly "
                            f"match the scenarios below the outcome, expected {below}, "
                            f"got {shortfall!r}")


def _check_control_gate(add_error, cid, label, claim, evs):
    """C-T4: a band above the control-free ceiling A0 requires a core control block with
    kind='ablation', observed='red', expectation='red', of_claim naming this claim.
    kind='planted-twin' never lifts (PROFILE.md 'Required fields over the core', a design decision
    2026-09-24). 0.1.0 redefines what a satisfying ablation control looks like at the harness
    level (row 1: no-fault + wrong-scenario-swap, replacing the evidence-stripped run that could
    never fail) -- the format-level shape checked here is unchanged."""
    band = claim.get("band")
    tokens = LADDER["tokens"]
    if band not in tokens or band == tokens[0]:
        return
    has_ablation = any(
        isinstance(e.get("control"), dict)
        and e["control"].get("kind") == "ablation"
        and e["control"].get("of_claim") == cid
        and e["control"].get("observed") == "red"
        and e["control"].get("expectation") == "red"
        for e in evs
    )
    if not has_ablation:
        add_error(cid, f"{label}: C-T4: band {band!r} exceeds the control-free ceiling "
                        f"{tokens[0]!r} and requires a core control block with kind='ablation', "
                        f"observed='red', expectation='red', of_claim naming this claim "
                        f"(kind='planted-twin' never lifts)")


def _check_diagnostics_table(add_error, doc):
    """PROFILE.md 'Required fields over the core': a [diagnostics] table declaring privacy,
    retention and sampling."""
    diagnostics = doc.get("diagnostics")
    if not isinstance(diagnostics, dict):
        add_error(None, "R-T-DIAG: [diagnostics] table is required (privacy, retention, sampling)")
        return
    for key in ("privacy", "retention", "sampling"):
        if not _nonempty_str(diagnostics.get(key)):
            add_error(None, f"R-T-DIAG: [diagnostics].{key} must be a nonempty string")


def _check_telemetry_not_in_force(add_indeterminate, cid, label, evs):
    """C-T2/C-T3 (row 11): neither mechanism exists yet in this pass. Fail closed: a claim citing
    telemetry-completeness-check evidence is INDETERMINATE, not silently trusted at the family
    ceiling."""
    if any(e.get("kind") == "telemetry-completeness-check" for e in evs):
        add_indeterminate(cid, f"{label}: C-T2 not in force in 0.1.0: telemetry-completeness-check "
                                f"evidence cannot be checked yet (no completeness mechanism)")


def check(doc, ctx):
    from check_core import Finding
    findings: list[Finding] = []

    def add_error(cid, message):
        findings.append(Finding("error", message, cid))

    def add_indeterminate(cid, message):
        findings.append(Finding("indeterminate", message, cid))

    _check_diagnostics_table(add_error, doc)

    record_owners: dict = {}
    claims = doc.get("claim", [])
    for claim in claims if isinstance(claims, list) else []:
        if not isinstance(claim, dict):
            continue
        cid = claim.get("id")
        label = f"claim {cid!r}"
        evs = _evs(claim)

        _check_fields(add_error, cid, label, claim)
        _check_scenarios(add_error, cid, label, claim)
        _check_status(add_error, cid, label, claim)
        _check_struct_ceiling(add_error, cid, label, claim, evs)
        _check_blind_diagnosis_required(add_error, cid, label, claim, evs)
        _check_outcome_criterion(add_error, cid, label, claim)
        _check_scenario_source(add_error, cid, label, claim)
        _check_control_gate(add_error, cid, label, claim, evs)
        _check_telemetry_not_in_force(add_indeterminate, cid, label, evs)

        for eidx, ev in enumerate(evs):
            ectx = f"{label} evidence[{eidx}]"
            if ev.get("kind") != "blind-diagnosis":
                continue
            _check_diagnoser(add_error, cid, ectx, ev)
            _check_isolation(add_error, cid, label, ectx, claim, ev)
            _check_blinding(add_error, cid, ectx, ev)
            _check_coverage_and_shortfall(add_error, cid, label, ectx, claim, ev)
            _check_record_schema(add_error, cid, label, ectx, claim, ev, ctx, record_owners)

    return findings


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run embedded able-to-fail fixtures")
    args = parser.parse_args()
    if not args.selftest:
        parser.error("only --selftest is supported here; validate manifests via check_core.py "
                      "(this module composes into its dispatch, it is not a standalone CLI)")
    from fixtures.troubleshooting_cases import run
    sys.exit(run())
