#!/usr/bin/env python3
"""Issue a consumer decision only after re-executing every basis recipe for real."""
from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stack_support import ROOT, REPO, CRATES, DECISION_IDS, ISSUERS, STORE, load, paths, save
from transcripts import normalize
sys.path.insert(0, str(REPO / "protocol_acceptance/tools"))
import acceptance_protocol as AP
import chain


def decide(crate):
    sp, pp, dp = paths(crate)
    spec, package = load(sp), load(pp)
    commit = package["subject"]["commit"]
    AP._ROOT_OVERRIDE = REPO
    context = chain.Invocation(AP, {"ochre-accepted": STORE}, {commit: REPO}, REPO)
    cov = AP.compute_coverage(spec, package, pp)
    issued = AP.now_utc_iso()
    if any(r.get("kind") == "chain" for r in spec["requirement"]):
        chain.merge_coverage(cov, context.evaluate(spec, package, pp, issued))
    AP.print_coverage_table(cov)
    if not cov["summary"]["acceptable"] or cov["record_errors"] or cov.get("chain", {}).get("errors") or cov.get("chain", {}).get("unknowns"):
        raise RuntimeError(f"{crate}: coverage is not acceptable")
    basis = sorted({cid for req in cov["requirements"].values() for cid in req["basis"]})
    claims = {c["id"]: c for c in package["claim"]}
    runs = []
    for cid in basis:
        recipe = claims[cid]["self_verify"]
        print(f"[make_decision] {crate}: re-executing {cid}: {recipe['command']}", flush=True)
        proc = subprocess.run(recipe["command"], shell=True, cwd=pp.parent,
                              env=dict(os.environ, CARGO_NET_OFFLINE="true"),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=300)
        output = normalize(proc.stdout)
        if proc.returncode or recipe["expect"] not in output:
            print(output)
            raise RuntimeError(f"{crate}/{cid}: real re-execution failed; no decision issued")
        runs.append(dict(claim=cid, command=recipe["command"], result="pass",
                         observed=" | ".join(output.strip().splitlines()[-6:]), at=AP.now_utc_iso()))
    # Snapshot time must include all completed verification runs.
    issued = AP.now_utc_iso()
    if "chain" in cov:
        chain.merge_coverage(cov, context.evaluate(spec, package, pp, issued))
        if not cov["summary"]["acceptable"] or cov["chain"]["errors"] or cov["chain"]["unknowns"]:
            raise RuntimeError(f"{crate}: chain became unacceptable during verification")
    dispositions = []
    for req in spec["requirement"]:
        rid = req["id"]
        result = cov["requirements"][rid]
        if result["status"] != "satisfied":
            raise RuntimeError(f"{crate}/{rid}: unsatisfied requirement")
        row = dict(requirement=rid, status="satisfied")
        if req.get("kind") == "chain":
            for field, status in (("chain_basis", "satisfied"), ("chain_boundary", "boundary"), ("chain_gaps", "gap")):
                row[field] = sorted(r["dependency"] for r in cov["chain"]["rows"] if r["requirement"] == rid and r["status"] == status)
        else:
            row["basis"] = result["basis"]
        dispositions.append(row)
    decision = dict(
        document=dict(protocol=AP.PROTOCOL_ID, minor=0, kind="decision", id=DECISION_IDS[crate],
                      issued_at=issued, issuer=ISSUERS[crate], verdict="accepted"),
        binds=dict(specification=dict(id=spec["document"]["id"], hash=AP.m11.digest_file("specification", sp), path=sp.relative_to(REPO).as_posix()),
                   package=dict(hash=AP.m11.digest_file("manifest", pp), path=pp.relative_to(REPO).as_posix()),
                   subject={k: package["subject"][k] for k in ("commit", "path")}),
        verification=dict(mode="re-execute-all", run=runs), disposition=dispositions,
        validity=dict(stale_after=(datetime.date.fromisoformat(issued[:10]) + datetime.timedelta(days=30 if crate == "geom-math" else 180)).isoformat()))
    if "chain" in cov:
        decision["chain_evaluation"] = cov["chain"]["snapshot"]
        decision["chain_element"] = cov["chain"]["rows"]
    rep = AP.check_decision(decision, spec, package, sp, pp, decision_path=dp, chain_context=context)
    if not rep.ok():
        raise RuntimeError(f"{crate}: check-decision failed: {rep.errors}; {rep.unknowns}")
    save(dp, decision)
    save(STORE / (DECISION_IDS[crate] + ".toml"), decision)
    print(f"[make_decision] {DECISION_IDS[crate]}: accepted (re-execute-all)", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crate", choices=CRATES, default="paint-app")
    decide(parser.parse_args().crate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
