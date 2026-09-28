"""Fixtures for tools/profiles/troubleshooting.py -- one valid case plus one red case per
PROFILE.md constraint/required field, reusing the class fixture harness (workspace/evaluate/result/
diagnostic) core_cases.py already provides rather than duplicating it. Consumed by
troubleshooting.py's `--selftest` (gated, tools/gates/check_formats_selftests.py) and by
troubleshooting_mutations.py's guard-disable audit (mirrors r3_mutations.py; that script is NOT
gated).

The 0.1.0 revision adds: outcome_criterion (row 2),
scenario_source (row 14), C-T7 (row 3), diagnoser.digest/held_out (row 8), blinding.committed_at
(row 7), isolation attestation + A0 cap for model-seat/human (row 20), the record-schema extension
of C-T5 (row 4), the status/shortfall closed-set extension of C-T5 (row 13), C-T6's
never-discharges extension (row 12), and C-T2's fail-closed INDETERMINATE (row 11).
"""
import copy
import json
import sys

import check_core as C
import hashdomains as H
from .core_cases import diagnostic, evaluate, result, workspace

CASES: list[tuple[str, str, str, "callable"]] = []

# The declared row schema (troubleshooting.py `_open_record_rows`): a JSON object with a `rows`
# list, each row {fault_class, id, outcome}. This is the SAME shape the real harness
# (troubleshooting_blind.py) and the profile's own example evidence/results.json now use -- one
# row schema, not a fixture-only dialect.
TS_RECORD_ROWS = [
    {"fault_class": "fixture-fault", "id": "s1", "outcome": "isolate_fault_domain"},
    {"fault_class": "fixture-fault", "id": "s2", "outcome": "isolate_fault_domain"},
]
TS_RECORD_BYTES = (json.dumps({"rows": TS_RECORD_ROWS}) + "\n").encode()
TS_RECORD_HASH = H.digest("record:", TS_RECORD_BYTES)


def _other_evidence(kind, family, tier):
    """A well-formed, non-blind-diagnosis evidence record -- for C-T6/C-T7/C-T2 fixtures that need
    evidence present but not of kind='blind-diagnosis'."""
    return {
        "kind": kind, "family": family, "ref": "x", "result": "pass", "tool": "t@0",
        "record": "ts-record.json", "record_hash": TS_RECORD_HASH, "epistemic_tier": tier,
    }


def base() -> dict:
    return {
        "format": {"id": "acceptance/0", "profile": "acceptance/troubleshooting"},
        "subject": {"name": "fixture-tool", "kind": "tool", "commit": "0" * 40, "dirty": False},
        "spec": {"path": "SPEC.md", "version": "v1"},
        "coverage": {"clauses_total": 1, "claims_total": 1},
        "diagnostics": {
            "privacy": "no personal data",
            "retention": "repo lifetime",
            "sampling": "100% (every scenario)",
        },
        "claim": [{
            "id": "TS-1",
            "clause": "fixture-fault",
            "item": "fixture::diagnose",
            "statement": "diagnoser isolates the fixture fault (A0)",
            "fault_class": "fixture-fault",
            "outcome": "isolate_fault_domain",
            "outcome_criterion": {"granularity": "fixture-domain", "grading": "exact-set"},
            "scenario_source": {"rule": "fixture:: every named scenario", "population": 2},
            "scenarios": ["s1", "s2"],
            "status": "evidenced",
            "grade": "ungraded",
            "evidence": [{
                "kind": "blind-diagnosis",
                "family": "injected-diagnosis",
                "ref": "fixture::diagnoser",
                "result": "pass",
                "tool": "fixture@0",
                "record": "ts-record.json",
                "record_hash": TS_RECORD_HASH,
                "epistemic_tier": "T3",
                "held_out": False,
                "diagnoser": {
                    "kind": "deterministic",
                    "id": "fixture_diagnoser",
                    "digest": "sha256:" + "a" * 64,
                },
                "blinding": {
                    "truth_hash": "sha256:" + "0" * 64,
                    "visible_evidence": ["fixture output"],
                    "committed_at": "0" * 40,
                },
                "results": {"s1": "isolate_fault_domain", "s2": "isolate_fault_domain"},
            }],
        }],
    }


def add(name, change=lambda d: None, verdict="FAIL", substring="", setup=None):
    def execute():
        with workspace() as root:
            (root / "ts-record.json").write_bytes(TS_RECORD_BYTES)
            d = base()
            change(d)
            if setup:
                setup(d, root)
            rep = evaluate(d, root)
            actual, messages = result(rep)
            expected = (verdict, 1 if verdict == "FAIL" else 2 if verdict == "INDETERMINATE" else 0)
            assert actual == expected, (actual, messages)
            if substring:
                assert substring in messages, (substring, messages)
    CASES.append((name, verdict, substring, execute))


def claim0(**fields):
    return lambda d: d["claim"][0].update(fields)


def ev0(**fields):
    return lambda d: d["claim"][0]["evidence"][0].update(fields)


def diagnoser0(**fields):
    return lambda d: d["claim"][0]["evidence"][0]["diagnoser"].update(fields)


def blinding0(**fields):
    return lambda d: d["claim"][0]["evidence"][0]["blinding"].update(fields)


def results0(**fields):
    return lambda d: d["claim"][0]["evidence"][0]["results"].update(fields)


def combine(*fns):
    def change(d):
        for fn in fns:
            fn(d)
    return change


# --- the valid case -------------------------------------------------------------------------

add("green-base", verdict="PASS")

# --- R-T-FIELDS: fault_class / outcome on every claim ----------------------------------------

add("rt-fields-fault-class-missing", claim0(fault_class=""),
    substring="R-T-FIELDS: fault_class")
add("rt-fields-outcome-invalid", claim0(outcome="guess"),
    substring="R-T-FIELDS: outcome must be one of")

# --- C-T1: gap rule, both directions ----------------------------------------------------------

add("ct1-scenarios-empty-non-gap", claim0(scenarios=[]), substring="C-T1")
add("ct1-scenarios-duplicate", claim0(scenarios=["s1", "s1"]), substring="C-T1")
add("ct1-gap-with-scenarios",
    claim0(status="gap", scenarios=["s1"], evidence=[]),
    substring="C-T1")
add("ct1-scenarios-non-string-entry", claim0(scenarios=["s1", 123]), substring="C-T1")

# --- C-T5 (status): the closed status set, and shortfall only on partial ----------------------

add("ct5-status-unknown", claim0(status="satisfied"), substring="C-T5")
add("ct5-shortfall-on-evidenced", claim0(shortfall=["s1"]), substring="C-T5")

# --- C-T6: diagnostic-structure-only evidence cannot back an outcome above 'detect', and can
# never discharge (status='evidenced') a claim on its own even at 'detect' -------------------

add("ct6-struct-ceiling",
    combine(claim0(outcome="isolate_fault_domain"),
            ev0(kind="diagnostic-structure-check", family="diagnostic-structure")),
    substring="C-T6")
add("ct6-struct-detect-evidenced",
    combine(claim0(outcome="detect"),
            ev0(kind="diagnostic-structure-check", family="diagnostic-structure")),
    substring="C-T6")

# --- inherited from check_core: an unregistered evidence kind is refused ("logging exists" is
# not a kind, PROFILE.md "Closed vocabularies") -- no module-specific guard, so no mutation entry.

add("rt-kind-unknown", ev0(kind="logging-exists", family="diagnostic-structure"),
    substring="unknown evidence kind")

# --- C-T7 (new, row 3): a non-gap claim above 'detect' needs a blind-diagnosis record ----------

add("ct7-telemetry-only",
    combine(claim0(outcome="isolate_fault_domain"),
            lambda d: d["claim"][0].update(
                evidence=[_other_evidence("telemetry-completeness-check", "telemetry-completeness", "T3")])),
    verdict="INDETERMINATE", substring="C-T7")
add("ct7-structure-plus-telemetry",
    combine(claim0(outcome="isolate_fault_domain"),
            lambda d: d["claim"][0].update(evidence=[
                _other_evidence("diagnostic-structure-check", "diagnostic-structure", "T4"),
                _other_evidence("telemetry-completeness-check", "telemetry-completeness", "T3"),
            ])),
    verdict="INDETERMINATE", substring="C-T7")
add("ct7-no-evidence", claim0(outcome="isolate_fault_domain", evidence=[]),
    substring="C-T7")

# --- C-T2 (row 11): not in force -- fail closed, never silently trusted -----------------------

add("ct2-telemetry-not-in-force",
    combine(claim0(outcome="detect"),
            lambda d: d["claim"][0].update(
                evidence=[_other_evidence("telemetry-completeness-check", "telemetry-completeness", "T3")])),
    verdict="INDETERMINATE", substring="C-T2 not in force")

# --- R-T-OUTCOME-CRITERION (row 2) -------------------------------------------------------------

add("rt-outcome-criterion-missing", lambda d: d["claim"][0].pop("outcome_criterion"),
    substring="R-T-OUTCOME-CRITERION")
add("rt-outcome-criterion-bad-grading",
    lambda d: d["claim"][0]["outcome_criterion"].update(grading="top-k"),
    substring="R-T-OUTCOME-CRITERION")

# --- R-T-SCENARIO-SOURCE (row 14) --------------------------------------------------------------

add("rt-scenario-source-missing", lambda d: d["claim"][0].pop("scenario_source"),
    substring="R-T-SCENARIO-SOURCE")
add("rt-scenario-source-population-too-small",
    lambda d: d["claim"][0]["scenario_source"].update(population=1),
    substring="R-T-SCENARIO-SOURCE")

# --- R-T-DIAGNOSER: blind-diagnosis evidence names a diagnoser, a digest and held_out ----------

add("rt-diagnoser-missing", lambda d: d["claim"][0]["evidence"][0].pop("diagnoser"),
    substring="R-T-DIAGNOSER")
add("rt-diagnoser-bad-kind", diagnoser0(kind="ai"),
    substring="R-T-DIAGNOSER")
add("rt-diagnoser-digest-missing", lambda d: d["claim"][0]["evidence"][0]["diagnoser"].pop("digest"),
    substring="R-T-DIAGNOSER")
add("rt-diagnoser-digest-bad", diagnoser0(digest="not-a-hash"),
    substring="R-T-DIAGNOSER")
add("rt-held-out-missing", lambda d: d["claim"][0]["evidence"][0].pop("held_out"),
    substring="R-T-DIAGNOSER")
add("rt-held-out-bad-type", ev0(held_out="false"),
    substring="R-T-DIAGNOSER")

# --- R-T-ISOLATION (row 20): model-seat/human diagnosers need isolation, and are capped at A0 --

add("rt-isolation-missing", diagnoser0(kind="model-seat"),
    substring="R-T-ISOLATION")
add("rt-isolation-band-capped",
    combine(claim0(band="A1"),
            diagnoser0(kind="human", isolation={"digest": "sha256:" + "b" * 64, "tools": ["shell"]})),
    substring="R-T-ISOLATION")
add("rt-isolation-satisfied",
    diagnoser0(kind="model-seat", isolation={"digest": "sha256:" + "c" * 64, "tools": ["read-only packet"]}),
    verdict="PASS")

# --- R-T-BLINDING: the sealed-truth blinding record ---------------------------------------------

add("rt-blinding-missing", lambda d: d["claim"][0]["evidence"][0].pop("blinding"),
    substring="R-T-BLINDING")
add("rt-blinding-bad-hash", blinding0(truth_hash="deadbeef"),
    substring="R-T-BLINDING")
add("rt-blinding-empty-visible", blinding0(visible_evidence=[]),
    substring="R-T-BLINDING")
add("rt-blinding-committed-at-missing",
    lambda d: d["claim"][0]["evidence"][0]["blinding"].pop("committed_at"),
    substring="R-T-BLINDING")
add("rt-blinding-committed-at-bad", blinding0(committed_at="short"),
    substring="R-T-BLINDING")

# --- C-T5: anti-cherry-pick coverage + shortfall coherence -------------------------------------


def _record_with_s2_detect(d, root):
    """s2's own TRUE outcome (per the record) is 'detect', matching these fixtures' results0(s2=
    "detect") -- so the row-4 record-schema comparison stays silent and the ORIGINAL coverage
    self-consistency check (this section) is the one exclusive guard each of these cases proves."""
    rows = [
        {"fault_class": "fixture-fault", "id": "s1", "outcome": "isolate_fault_domain"},
        {"fault_class": "fixture-fault", "id": "s2", "outcome": "detect"},
    ]
    raw = (json.dumps({"rows": rows}) + "\n").encode()
    (root / "ts-record.json").write_bytes(raw)
    d["claim"][0]["evidence"][0]["record_hash"] = H.digest("record:", raw)


add("ct5-coverage-missing", lambda d: d["claim"][0]["evidence"][0]["results"].pop("s2"),
    substring="C-T5")
add("ct5-coverage-extra", results0(s3="detect"), substring="C-T5")
add("ct5-evidenced-shortfall", results0(s2="detect"), substring="C-T5",
    setup=_record_with_s2_detect)
add("ct5-partial-missing-shortfall-field",
    combine(results0(s2="detect"), claim0(status="partial")),
    substring="C-T5", setup=_record_with_s2_detect)
add("ct5-partial-shortfall-wrong",
    combine(results0(s2="detect"), claim0(status="partial", shortfall=["wrong-id"])),
    substring="C-T5", setup=_record_with_s2_detect)
add("ct5-partial-no-shortfall-needed", claim0(status="partial", shortfall=[]),
    substring="C-T5")
add("ct5-partial-correct",
    combine(results0(s2="detect"), claim0(status="partial", shortfall=["s2"])),
    verdict="PASS", setup=_record_with_s2_detect)

# --- C-T5 (row 4): checked against the hash-bound record, not just the producer's own tables ---

add("ct5-record-scenarios-mismatch",
    lambda d: (
        d["claim"][0].update(scenarios=["s1", "s9"]),
        d["claim"][0]["evidence"][0].update(
            results={"s1": "isolate_fault_domain", "s9": "isolate_fault_domain"}),
    ),
    substring="C-T5")
add("ct5-record-outcome-mismatch",
    combine(results0(s2="detect"), claim0(status="partial", shortfall=["s2"])),
    substring="C-T5")


def _duplicate_fault_class_claim(d):
    second = copy.deepcopy(d["claim"][0])
    second["id"] = "TS-2"
    d["claim"].append(second)
    d["coverage"]["claims_total"] = 2


add("ct5-record-fault-class-duplicate", _duplicate_fault_class_claim, substring="C-T5")

# --- C-T4: control gate above the control-free ceiling -----------------------------------------

add("ct4-band-no-control", claim0(band="A1"), substring="C-T4")
add("ct4-band-planted-twin-no-lift",
    combine(claim0(band="A1"),
            ev0(control={"kind": "planted-twin", "of_claim": "TS-1",
                         "expectation": "red", "observed": "red"})),
    substring="C-T4")
add("ct4-band-ablation-satisfied",
    combine(claim0(band="A1"),
            ev0(control={"kind": "ablation", "of_claim": "TS-1",
                         "expectation": "red", "observed": "red"})),
    verdict="PASS")

# --- R-T-DIAG: the [diagnostics] table ----------------------------------------------------------

add("rt-diagnostics-missing-table", lambda d: d.pop("diagnostics"), substring="R-T-DIAG")
add("rt-diagnostics-missing-key", lambda d: d["diagnostics"].pop("privacy"), substring="R-T-DIAG")
add("rt-diagnostics-empty-value", lambda d: d["diagnostics"].update(retention=""),
    substring="R-T-DIAG")


def run() -> int:
    failed = []
    for name, verdict, substring, operation in CASES:
        try:
            operation()
        except Exception as exc:
            failed.append(name)
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"PASS {name}: expected {verdict}" + (f"; contains {substring!r}" if substring else ""))
    print(f"troubleshooting: {len(CASES)} fixtures, {len(failed)} failures")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
