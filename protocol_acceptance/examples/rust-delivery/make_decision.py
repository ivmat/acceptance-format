#!/usr/bin/env python3
"""make_decision.py — produces `acceptance-decision.toml`, the CONSUMER's decision (protocol.md
§5), by ACTUALLY RE-RUNNING every basis claim's `self_verify.command` against the delivered crate
and recording the real observed tail — this is the "re-execute-all" verification mode the contract
demands (`[acceptance].consumer_verification = "re-execute-all"`), not a rubber stamp.

Pure stdlib, python3.11+. Imports `protocol_acceptance/tools/m11.py` (hashing) and
`protocol_acceptance/tools/acceptance_protocol.py` (`compute_coverage`, so this script's basis-claim choices
are computed by the SAME reference function `check-decision` will use to check them against,
rather than a hand-typed duplicate that could drift) — both pure-stdlib themselves.

DO NOT HAND-EDIT the generated acceptance-decision.toml — re-run this script (after re-running
gen_package.py, if the crate or contract changed).
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CRATE_DIR = SCRIPT_DIR / "iban-check"
CONTRACT_PATH = SCRIPT_DIR / "acceptance-contract.toml"
PACKAGE_PATH = SCRIPT_DIR / "acceptance.toml"
DECISION_OUT = SCRIPT_DIR / "acceptance-decision.toml"

# Same pin as gen_package.py's CARGO_TARGET_DIR: re-execution runs under the crate's own directory
# regardless of the calling shell/worker's own CARGO_TARGET_DIR, so no machine-local target-dir
# name can reach a persisted [[verification.run]].observed tail (README "Transcript normalization").
CARGO_TARGET_DIR = CRATE_DIR / "target"

TOOLS_DIR = SCRIPT_DIR.parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))
import m11  # noqa: E402
import acceptance_protocol as AP  # noqa: E402

ISSUER = "Acme Payments Ltd / platform-lead"
DECISION_ID = "AD-2026-0001"


def q(s: str) -> str:
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


def load_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def tail(text: str, n: int = 6) -> str:
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return " | ".join(lines[-n:])


def normalize_transcript(text: str, repo_root: Path) -> str:
    """Apply the package's disclosed, pre-hash path normalization to decision observations."""
    text = text.replace(str(CRATE_DIR), "<crate>")
    text = text.replace(str(repo_root), "<repo>")
    text = re.sub(
        r"/" r"Users/[^/\s]+/\.rustup/toolchains/([^/\s]+)/",
        r"<rustup>/\1/",
        text,
    )
    text = re.sub(re.escape(str(Path.home())) + r"(?=/|$)", "~", text)
    return re.sub(r"/" r"Users/([^/\s]+)/", r"<users>/\1/", text)


def main(argv: list[str]) -> int:
    if not PACKAGE_PATH.is_file():
        print(f"error: {PACKAGE_PATH} does not exist — run gen_package.py first", file=sys.stderr)
        return 2

    contract = load_toml(CONTRACT_PATH)
    package = load_toml(PACKAGE_PATH)
    repo_root = Path(subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=str(SCRIPT_DIR),
        capture_output=True, text=True, check=True,
    ).stdout.strip())

    contract_hash = m11.digest_file("contract", CONTRACT_PATH)
    package_hash = m11.digest_file("manifest", PACKAGE_PATH)
    subject_commit = package["subject"]["commit"]
    contract_id = contract["document"]["id"]

    cov = AP.compute_coverage(contract, package, PACKAGE_PATH)
    print("[make_decision] coverage:")
    AP.print_coverage_table(cov)

    claims_by_id = {c["id"]: c for c in package.get("claim", []) if isinstance(c, dict) and "id" in c}
    req_by_id = AP.requirement_by_id(contract)

    # ------------------------------------------------------------------
    # RE-EXECUTE every basis claim's self_verify.command for real (re-execute-all mode).
    # ------------------------------------------------------------------
    all_basis_ids: set[str] = set()
    for rid, r in cov["requirements"].items():
        all_basis_ids.update(r["basis"])

    runs: list[dict] = []
    for cid in sorted(all_basis_ids):
        claim = claims_by_id[cid]
        sv = claim.get("self_verify") or {}
        command = sv.get("command")
        expect = sv.get("expect")
        print(f"[make_decision] re-executing {cid}: {command}")
        # Kani's own proof (IB-003) genuinely takes several minutes; everything else is fast.
        timeout = 1200 if "kani" in command else 120
        try:
            env = {**os.environ, "CARGO_TARGET_DIR": str(CARGO_TARGET_DIR)}
            proc = subprocess.run(
                command, shell=True, cwd=str(CRATE_DIR),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout,
                env=env,
            )
            output = proc.stdout
            passed = proc.returncode == 0 and (expect in output)
            result = "pass" if passed else "fail"
        except subprocess.TimeoutExpired as e:
            output = (e.stdout or "") if isinstance(e.stdout, str) else ""
            result = "error"
        observed = tail(normalize_transcript(output, repo_root), 6)
        runs.append({
            "claim": cid,
            "command": command,
            "observed": observed,
            "result": result,
            "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        print(f"[make_decision]   -> {result}")

    runs_by_claim: dict[str, list[dict]] = {}
    for r in runs:
        runs_by_claim.setdefault(r["claim"], []).append(r)

    # ------------------------------------------------------------------
    # Dispositions — one per requirement, mandatory and optional.
    # ------------------------------------------------------------------
    dispositions: list[dict] = []
    for rid in sorted(req_by_id):
        req = req_by_id[rid]
        r = cov["requirements"].get(rid, {})
        status = r["status"]
        basis = r["basis"]
        if rid == "R5":
            dispositions.append({
                "requirement": "R5",
                "status": "waived",
                "basis": [],
                "conditions": ["C1"],
                "note": "unbounded verification not yet available; bounded evidence accepted for this release under condition C1",
                "waiver": {
                    "reason": "bounded verification (dynamic samples for R1/R2, a 20-byte Kani proof for R3) accepted for this release; an unbounded argument is due before v2",
                    "code": "deferred",
                    "authority": ISSUER,
                },
            })
        elif status == "satisfied":
            all_pass = bool(basis) and all(
                any(run["result"] == "pass" for run in runs_by_claim.get(cid, []))
                for cid in basis
            )
            dispositions.append({
                "requirement": rid,
                "status": "satisfied" if all_pass else "insufficient-evidence",
                "basis": basis,
            })
        else:
            mandatory = bool(req.get("mandatory"))
            dispositions.append({
                "requirement": rid,
                "status": "unsatisfied" if mandatory else "insufficient-evidence",
                "basis": basis,
                "note": f"coverage computed {status!r}",
            })

    mandatory_statuses = {
        d["status"] for d in dispositions if req_by_id.get(d["requirement"], {}).get("mandatory")
    }
    verdict = AP.expected_verdict_from_mandatory_statuses(mandatory_statuses)
    if verdict is None:
        print(f"[make_decision] FATAL: no verdict rule admits mandatory statuses {mandatory_statuses}", file=sys.stderr)
        return 1
    print(f"[make_decision] verdict: {verdict} (from mandatory statuses {sorted(mandatory_statuses)})")

    # ------------------------------------------------------------------
    # Render acceptance-decision.toml
    # ------------------------------------------------------------------
    issued_dt = datetime.datetime.now(datetime.timezone.utc)
    issued_at = issued_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_after_date = (issued_dt + AP.duration_to_timedelta(
        contract["acceptance"]["stale_after"]
    )).date().isoformat()

    lines: list[str] = []
    lines.append("# GENERATED FILE — DO NOT HAND-EDIT. Produced by make_decision.py, which RE-EXECUTED")
    lines.append("# every basis claim's self_verify.command for real (re-execute-all mode) and recorded the")
    lines.append("# actual observed tail below, rather than trusting the package's own say-so about itself.")
    lines.append("")
    lines.append("[document]")
    lines.append('protocol   = "acceptance-protocol/0"')
    lines.append("minor      = 0")
    lines.append('kind       = "decision"')
    lines.append(f"id         = {q(DECISION_ID)}")
    lines.append(f"issued_at  = {q(issued_at)}")
    lines.append(f"issuer     = {q(ISSUER)}")
    lines.append(f"verdict    = {q(verdict)}")
    lines.append("# provisional omitted: the bound contract's [acceptance].phase = \"final\",")
    lines.append("# so provisional must be absent or false (protocol.md §3.5) — omitted here.")
    lines.append("")
    lines.append("[binds]")
    lines.append(f'contract = {{ id = {q(contract_id)}, hash = {q(contract_hash)} }}')
    lines.append(f'package  = {{ hash = {q(package_hash)} }}')
    lines.append(f'subject  = {{ commit = {q(subject_commit)} }}')
    lines.append("")
    lines.append("[verification]")
    lines.append('mode = "re-execute-all"')
    lines.append("")
    for r in runs:
        lines.append("[[verification.run]]")
        lines.append(f'claim    = {q(r["claim"])}')
        lines.append(f'command  = {q(r["command"])}')
        lines.append(f'observed = {q(r["observed"])}')
        lines.append(f'result   = {q(r["result"])}')
        lines.append(f'at       = {q(r["at"])}')
        lines.append("")
    for d in dispositions:
        lines.append("[[disposition]]")
        lines.append(f'requirement = {q(d["requirement"])}')
        lines.append(f'status      = {q(d["status"])}')
        lines.append(f'basis       = [{", ".join(q(b) for b in d["basis"])}]')
        if "conditions" in d:
            lines.append(f'conditions  = [{", ".join(q(c) for c in d["conditions"])}]')
        if "note" in d:
            lines.append(f'note        = {q(d["note"])}')
        if "waiver" in d:
            lines.append("  [disposition.waiver]")
            lines.append(f'  reason    = {q(d["waiver"]["reason"])}')
            lines.append(f'  code      = {q(d["waiver"]["code"])}')
            lines.append(f'  authority = {q(d["waiver"]["authority"])}')
        lines.append("")
    lines.append("[[condition]]")
    lines.append('id            = "C1"')
    lines.append('requirement   = "R5"')
    lines.append(f'statement     = {q("Deliver an unbounded (or substantially extended-bound) verification argument for R1, R2 and R3 — a Lean/Aeneas extraction, or a Kani proof at or near the crate real 34-byte maximum, whichever lands first.")}')
    lines.append('due           = "2026-11-30"')
    lines.append('owner         = "producer"')
    lines.append(f'discharged_by = {q("a superseding package in which coverage(R5) = satisfied")}')
    lines.append("")
    lines.append("[validity]")
    lines.append(f"stale_after = {q(stale_after_date)}")
    lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    DECISION_OUT.write_text(text)
    print(f"[make_decision] wrote {DECISION_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
