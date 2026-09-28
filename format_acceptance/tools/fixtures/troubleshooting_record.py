#!/usr/bin/env python3
"""Generate the first real acceptance/troubleshooting record over the blind-diagnosis evidence.

Reads tools/fixtures/troubleshooting_evidence/results.json (the blind-diagnosis harness output,
troubleshooting_blind.py: `{subject_commit, dirty, diagnoser_digest, rows}`) and writes
examples/troubleshooting/validator.acceptance.toml: two claims, one per fault class the harness
exercised against the acceptance validator itself (subject = this repo's format_acceptance/tools).

Row 10 (independent review): refuses to generate from a dirty subject (results.json's own
`dirty` flag, snapshotted by the harness BEFORE it wrote any evidence output -- see
troubleshooting_blind.py's module docstring) and refuses when the current HEAD differs from the
commit the harness measured (the evidence would be stale relative to what git now shows).

Each row's own `outcome` (written directly by the harness -- GRADE_TO_OUTCOME already applied) is
copied into the claim's `evidence.results` table verbatim; since `results.json` IS the record this
claim's evidence points at (row 4: the module's C-T5 extension opens the same file under the same
declared row schema, `{fault_class, id, outcome}` rows), the two can never silently drift.

blinding.truth_hash: this record's own sealed-truth commitment is the sha256 of the CONCATENATION
of every cited scenario's own per-scenario truth_hash (results.json rows), each formatted
"<scenario id>:<truth_hash>\\n" and sorted by scenario id before joining -- so the record's single
hash is reproducible from results.json alone and changes if any cited scenario's sealed truth
would (same construction troubleshooting_blind.combined_hash uses for its own verifier).

blinding.committed_at (row 7) is set to subject_commit: the commit the harness measured, which (by
the refusal above) is also the current HEAD at generation time -- the commit that will carry this
run's evidence files once they are committed alongside this generated record.

held_out = false (row 8): honestly declared -- FC1 and FC2 were not held out from the diagnoser's
own authors.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
FORMAT_ACCEPTANCE = TOOLS.parent
PROTOCOL = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
import hashdomains as H  # noqa: E402

RESULTS = TOOLS / "fixtures/troubleshooting_evidence/results.json"
OUT_DIR = FORMAT_ACCEPTANCE / "examples/troubleshooting"
OUT_PATH = OUT_DIR / "validator.acceptance.toml"
SPEC_PATH = OUT_DIR / "VALIDATOR-SPEC.md"
INVENTORY_PATH = OUT_DIR / "VALIDATOR-SPEC.inventory.toml"

RECORD_REL = "../../tools/fixtures/troubleshooting_evidence/results.json"
SPEC_REL = "VALIDATOR-SPEC.md"
INVENTORY_REL = "VALIDATOR-SPEC.inventory.toml"

OUTCOME = "isolate_fault_domain"
OUTCOME_RANK = {"detect": 0, "isolate_fault_domain": 1,
                "reconstruct_causal_sequence": 2, "identify_root_cause": 3}

VISIBLE_EVIDENCE = {
    "validator-regression": ["selftest FAIL lines"],
    "malformed-record": ["validator CLI output"],
}
DIAGNOSER_ID = {
    "validator-regression": "diagnose_fc1",
    "malformed-record": "diagnose_fc2",
}
CLAIM_ID = {
    "validator-regression": "TS-VALIDATOR-FC1",
    "malformed-record": "TS-VALIDATOR-FC2",
}
# row 2: the granularity outcome_criterion names -- what "exact-set" is matched over.
GRANULARITY = {
    "validator-regression": "rule-group",
    "malformed-record": "field",
}
# row 14: the generator rule + population each fault class's scenarios are measured against
# (VALIDATOR-SPEC.md states these in prose; this is the same claim, machine-readable).
SCENARIO_SOURCE_RULE = {
    "validator-regression": (
        "every fixtures/r3_mutations.MUTATIONS entry whose guarded source file is rooted under "
        "format_acceptance/tools/ (VALIDATOR-SPEC.md #validator-regression)"),
    "malformed-record": (
        "tools/fixtures/troubleshooting_blind.FC2_FAULTS -- six hand-selected required-field "
        "mutations, one per major manifest table (VALIDATOR-SPEC.md #malformed-record)"),
}
# row 9: FC1's restated subject -- the selftest suite localizing a disabled guard by CASE NAME,
# not the validator's own runtime diagnostics (a diagnoser over rule ids is a later improvement).
STATEMENT_SUBJECT = {
    "validator-regression": (
        "the selftest suite localizes a disabled validator guard by case name (subject: the "
        "validator's tools/ source plus its own selftest suite, not the validator's runtime "
        "diagnostics)"),
    "malformed-record": (
        "blind diagnosis isolates the fault domain of malformed-record scenarios from validator "
        "CLI output alone"),
}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=PROTOCOL, capture_output=True, text=True,
                           check=True).stdout.strip()


def _sealed_truth_hash(rows: list[dict]) -> str:
    combined = "".join(f"{row['id']}:{row['truth_hash']}\n" for row in sorted(rows, key=lambda r: r["id"]))
    return "sha256:" + hashlib.sha256(combined.encode()).hexdigest()


def _toml_str(s: str) -> str:
    return json.dumps(s)


def _toml_list(items: list[str]) -> str:
    return "[" + ", ".join(_toml_str(x) for x in items) + "]"


def _build_claim(fault_class: str, rows: list[dict], diagnoser_digest: str, committed_at: str) -> str:
    rows = sorted(rows, key=lambda r: r["id"])
    scenarios = [r["id"] for r in rows]
    results = {r["id"]: r["outcome"] for r in rows}
    shortfall = sorted(sid for sid, reached in results.items()
                        if OUTCOME_RANK.get(reached, -1) < OUTCOME_RANK[OUTCOME])
    status = "partial" if shortfall else "evidenced"
    truth_hash = _sealed_truth_hash(rows)
    diagnoser_id = DIAGNOSER_ID[fault_class]
    visible = VISIBLE_EVIDENCE[fault_class]
    cid = CLAIM_ID[fault_class]

    lines = []
    lines.append("[[claim]]")
    lines.append(f'id          = {_toml_str(cid)}')
    lines.append(f'clause      = {_toml_str(fault_class)}')
    lines.append(f'item        = {_toml_str("format_acceptance/tools :: blind diagnosis of " + fault_class + " mutations")}')
    partial_note = (f" ({len(shortfall)} of {len(scenarios)} scenarios reach only detect, not "
                     f"isolate_fault_domain)") if shortfall else f" (all {len(scenarios)} scenarios reach isolate_fault_domain)"
    lines.append(f'statement   = {_toml_str(STATEMENT_SUBJECT[fault_class] + " (floor band A0)" + partial_note)}')
    lines.append(f'fault_class = {_toml_str(fault_class)}')
    lines.append(f'outcome     = {_toml_str(OUTCOME)}')
    # Inline tables, not [claim.outcome_criterion]/[claim.scenario_source] section headers: a TOML
    # table-header switches which table subsequent bare `key = value` lines belong to, which would
    # silently swallow 'scenarios'/'status'/'grade' below into the wrong table.
    criterion = f'{{ granularity = {_toml_str(GRANULARITY[fault_class])}, grading = "exact-set" }}'
    lines.append(f'outcome_criterion = {criterion}')
    source = (f'{{ rule = {_toml_str(SCENARIO_SOURCE_RULE[fault_class])}, '
              f'population = {len(scenarios)} }}')
    lines.append(f'scenario_source = {source}')
    lines.append(f'scenarios   = {_toml_list(scenarios)}')
    lines.append(f'status      = {_toml_str(status)}')
    lines.append('grade       = "ungraded"')
    if shortfall:
        shortfall_names = ", ".join(shortfall)
        if fault_class == "validator-regression":
            cause = ("TS-3 shared-substring fixtures blur localization "
                     "(troubleshooting profile section 10)")
        else:
            cause = ("exact-set grading (row 2, independent review) now requires the "
                     "predicted field set to equal the true one exactly; a diagnoser guess that "
                     "merely CONTAINS the true field no longer counts as 'isolated' -- "
                     "fc2-claim-evidence-removed is here after that regrade (finding 2)")
        gap_note = (f"{len(shortfall)} of {len(scenarios)} scenarios ({shortfall_names}) reach "
                    f"only detect, not isolate_fault_domain -- {cause}")
        lines.append(f'shortfall   = {_toml_list(shortfall)}')
        lines.append(f'gaps        = {_toml_list([gap_note])}')
    lines.append("")
    lines.append("  [[claim.evidence]]")
    lines.append(f'  kind           = "blind-diagnosis"')
    lines.append(f'  family         = "injected-diagnosis"')
    lines.append(f'  ref            = {_toml_str("troubleshooting_blind." + diagnoser_id)}')
    lines.append(f'  result         = "pass"')
    lines.append(f'  tool           = "troubleshooting_blind.py"')
    lines.append(f'  record         = {_toml_str(RECORD_REL)}')
    lines.append(f'  record_hash    = {_toml_str(H.digest("record:", RESULTS.read_bytes()))}')
    lines.append(f'  epistemic_tier = "T3"')
    lines.append(f'  held_out       = false')
    lines.append("")
    lines.append("    [claim.evidence.diagnoser]")
    lines.append('    kind   = "deterministic"')
    lines.append(f'    id     = {_toml_str(diagnoser_id)}')
    lines.append(f'    digest = {_toml_str(diagnoser_digest)}')
    lines.append("")
    lines.append("    [claim.evidence.blinding]")
    lines.append(f'    truth_hash       = {_toml_str(truth_hash)}')
    lines.append(f'    visible_evidence = {_toml_list(visible)}')
    lines.append(f'    committed_at     = {_toml_str(committed_at)}')
    lines.append("")
    lines.append("    [claim.evidence.results]")
    for sid in scenarios:
        lines.append(f'    {json.dumps(sid)} = {_toml_str(results[sid])}')
    return "\n".join(lines)


def main() -> int:
    data = json.loads(RESULTS.read_text())
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        print("FATAL: results.json must be {subject_commit, dirty, diagnoser_digest, rows: [...]}"
              " -- re-run tools/fixtures/troubleshooting_blind.py", file=sys.stderr)
        return 1
    rows = data["rows"]
    harness_commit = data.get("subject_commit")
    harness_dirty = data.get("dirty")
    diagnoser_digest = data.get("diagnoser_digest")
    if harness_dirty:
        print("FATAL: results.json recorded dirty=true at harness-run time -- refuse to generate "
              "a record from a dirty subject. Commit, then re-run "
              "tools/fixtures/troubleshooting_blind.py on the clean commit.", file=sys.stderr)
        return 1
    if not isinstance(harness_commit, str) or len(harness_commit) != 40:
        print(f"FATAL: results.json subject_commit is not a 40-hex commit: {harness_commit!r}",
              file=sys.stderr)
        return 1
    commit = _git("rev-parse", "HEAD")
    if commit != harness_commit:
        print(f"FATAL: current HEAD {commit[:12]} differs from the harness-run commit "
              f"{harness_commit[:12]} recorded in results.json -- the evidence may be stale "
              f"relative to the current tree. Re-run tools/fixtures/troubleshooting_blind.py on "
              f"the current commit.", file=sys.stderr)
        return 1
    if not isinstance(diagnoser_digest, str) or not diagnoser_digest.startswith("sha256:"):
        print(f"FATAL: results.json diagnoser_digest is malformed: {diagnoser_digest!r}", file=sys.stderr)
        return 1

    fc1 = [r for r in rows if r["fault_class"] == "validator-regression"]
    fc2 = [r for r in rows if r["fault_class"] == "malformed-record"]
    if not fc1 or not fc2:
        print("FATAL: results.json is missing one of the two fault classes", file=sys.stderr)
        return 1

    dirty = harness_dirty  # false, by the refusal above

    header = f"""# acceptance/troubleshooting -- the first real record (0.1.0 revision).
# Generated by tools/fixtures/troubleshooting_record.py from
# tools/fixtures/troubleshooting_evidence/results.json (the blind-diagnosis harness,
# tools/fixtures/troubleshooting_blind.py). Subject: this repo's own acceptance validator
# (format_acceptance/tools). No band -- floor A0, control-free.

[format]
id      = "acceptance/0"
profile = "acceptance/troubleshooting"

[subject]
name   = "format_acceptance-validator"
kind   = "tool"
commit = {_toml_str(commit)}
dirty  = {"true" if dirty else "false"}

[spec]
path             = {_toml_str(SPEC_REL)}
version          = "v1"
inventory        = {_toml_str(INVENTORY_REL)}
inventory_digest = {_toml_str(H.digest("inventory:", INVENTORY_PATH.read_bytes()))}

[coverage]
clauses_total = 2
claims_total  = 2

[diagnostics]
privacy   = "no personal data"
retention = "repo lifetime"
sampling  = "100% (every scenario)"

"""
    body = "\n\n".join([
        _build_claim("validator-regression", fc1, diagnoser_digest, harness_commit),
        _build_claim("malformed-record", fc2, diagnoser_digest, harness_commit),
    ])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(header + body + "\n")
    print(f"wrote {OUT_PATH} ({len(fc1)} FC1 scenarios, {len(fc2)} FC2 scenarios; "
          f"subject commit {commit[:12]}, dirty={dirty})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
