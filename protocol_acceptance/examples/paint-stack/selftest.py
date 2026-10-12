#!/usr/bin/env python3
"""Check saved evidence, all three protocol triples, scoped rendering and failure controls."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from stack_support import ROOT, REPO, CRATES, DECISION_IDS, ISSUERS, PRODUCERS, STORE, load, paths
sys.path.insert(0, str(REPO / "format_acceptance/tools"))
import hashdomains

TOOL = REPO / "protocol_acceptance/tools/acceptance_protocol.py"
NOT_COVERED = "not covered (trusted as the base, not checked): build-tool, language, platform, verification-tool"
ASSURANCE = "The label combines no assurance levels across the stack. Each element was accepted at its own floor; no failure bound for the whole stack follows."


def run(command, expected=0):
    result = subprocess.run([sys.executable, *map(str, command)], cwd=REPO,
                            capture_output=True, text=True, timeout=180)
    output = result.stdout + result.stderr
    if result.returncode != expected:
        raise RuntimeError(f"{command}: exit {result.returncode}, expected {expected}\n{output}")
    return output


def options(commit, repo=REPO, store=STORE):
    return ["--root", repo, "--store", "ochre-accepted=" + str(store), "--tree", commit + "=" + str(repo)]


def decision_command(crate="paint-app", repo=REPO, store=STORE):
    sp, pp, dp = [repo / p.relative_to(REPO) for p in paths(crate)]
    commit = load(pp)["subject"]["commit"]
    return [TOOL, "check-decision", dp, "--spec", sp, "--package", pp, *options(commit, repo, store)]


def check_snapshot(manifests):
    for manifest in manifests:
        for tool in ("check_acceptance.py", "check_core.py"):
            run([REPO / "format_acceptance/tools" / tool, "--strict", "--strict-weight", "--root", REPO, manifest])
    for crate in CRATES:
        sp, pp, _ = paths(crate)
        opts = options(load(pp)["subject"]["commit"])
        run([TOOL, "check-spec", sp])
        run([TOOL, "check-package", pp, "--spec", sp, *opts])
        run([TOOL, "coverage", pp, "--spec", sp, "--root", REPO])
        run(decision_command(crate))
    sp, pp, dp = paths("paint-app")
    rendered = run([TOOL, "render", sp, pp, dp, *options(load(pp)["subject"]["commit"])])
    expected = ["stack accepted over inv-cargo for runtime at " + load(dp)["document"]["issued_at"],
                NOT_COVERED, "accepted by Ochre Raster / maintainer, Studio Ochre / tools-lead under their own specifications",
                "raster-draw: declared binding: build-time-copy", "geom-math: declared binding: build-time-copy", ASSURANCE]
    assert rendered.strip().splitlines()[-6:] == expected, rendered
    print("PASS paint-stack snapshot: 12 strict format checks + 12 protocol checks + decision render")
    return "\n".join(expected)


def chain_controls():
    # Copies leave both the source tree and stored decisions untouched.
    with tempfile.TemporaryDirectory(prefix="paint-chain-") as temp:
        repo = Path(temp)
        sample = repo / ROOT.relative_to(REPO)
        shutil.copytree(ROOT, sample, symlinks=True,
                        ignore=shutil.ignore_patterns("target", "__pycache__", ".selftest-*"))
        store = sample / "store/ochre-accepted"
        child = store / "D_gm1.toml"
        original = child.read_bytes()
        child.unlink()
        output = run(decision_command(repo=repo, store=store), expected=1)
        assert "geom-math" in output and "pinned child not found" in output, output
        child.write_bytes(original)
        source = sample / "geom-math/src/lib.rs"
        original = source.read_bytes()
        changed = bytearray(original)
        changed[0] ^= 1
        source.write_bytes(changed)
        output = run(decision_command(repo=repo, store=store), expected=1)
        assert "geom-math" in output and "digest mismatch" in output, output
        source.write_bytes(original)
        # Only the child's window has elapsed; do not edit its hash-pinned decision.
        expiry = datetime.date.fromisoformat(load(child)["validity"]["stale_after"]) + datetime.timedelta(days=1)
        assert expiry < datetime.date.fromisoformat(load(paths("paint-app")[2])["validity"]["stale_after"])
        output = run([*decision_command(repo=repo, store=store), "--effect", "--now", str(expiry), "--json"], expected=1)
        result = json.loads(output)
        assert result["ok"] and not result["effect_eligible"], output
        assert "D_gm1.toml" in result["effect_reason"] and "stale_after" in result["effect_reason"] and "has passed" in result["effect_reason"], output
    print("PASS paint-stack chain controls: missing D_gm1 names geom-math; source byte names geom-math/digest; expired D_gm1 historically valid, effect-ineligible")


def walkthrough_controls():
    with tempfile.TemporaryDirectory(prefix="paint-walkthrough-") as temp:
        root = Path(temp)
        (root / "bin").mkdir()
        shutil.copyfile(ROOT / "run_example.sh", root / "run_example.sh")
        shim = f'''#!{sys.executable}
import os
from pathlib import Path
p = Path(os.environ["PAINT_TEST_COUNTER"])
n = int(p.read_text()) + 1
p.write_text(str(n))
raise SystemExit(37 if n == int(os.environ["PAINT_TEST_FAIL_AT"]) else 0)
'''
        for name in ("python3", "cargo"):
            path = root / "bin" / name
            path.write_text(shim)
            path.chmod(0o755)
        for fail_at in range(31):  # all 30 external stages, plus success
            counter = root / "counter"
            counter.write_text("0")
            env = dict(os.environ, PATH=str(root / "bin") + os.pathsep + os.environ["PATH"],
                       PAINT_TEST_COUNTER=str(counter), PAINT_TEST_FAIL_AT=str(fail_at))
            result = subprocess.run(["bash", str(root / "run_example.sh")], env=env,
                                    capture_output=True, text=True, timeout=30)
            assert result.returncode == (37 if fail_at else 0), (fail_at, result)
            assert int(counter.read_text()) == (fail_at or 30), (fail_at, counter.read_text())


def main():
    manifests = [ROOT / crate / "acceptance.toml" for crate in CRATES] + [paths(crate)[1] for crate in CRATES]
    rendered = check_snapshot(manifests)
    package = load(paths("paint-app")[1])
    mapping = {c["id"]: c["clause"] for c in package["claim"]}
    assert mapping == {"PA-001": "R4", "PA-002": "R1", "PA-003": "R2", "PA-004": "R3", "PA-005": "R5"}
    records = set()
    for crate in CRATES:
        sp, pp, dp = paths(crate)
        spec, pkg, decision = load(sp), load(pp), load(dp)
        assert spec["parties"]["producer"]["name"] == PRODUCERS[crate]
        assert decision["document"]["issuer"] == ISSUERS[crate] != PRODUCERS[crate]
        assert decision["document"]["id"] == DECISION_IDS[crate]
        assert decision["document"]["verdict"] == "accepted"
        assert all(r["result"] == "pass" for r in decision["verification"]["run"])
        assert dp.read_bytes() == (STORE / (DECISION_IDS[crate] + ".toml")).read_bytes()
        assert {d["requirement"]: d["basis"] for d in decision["disposition"] if "basis" in d} == {c["clause"]: [c["id"]] for c in pkg["claim"]}
        assert not re.search(r"/(?:Users|home)/", dp.read_text())
    assert {p.name for p in STORE.iterdir()} == {d + ".toml" for d in DECISION_IDS.values()}
    assert [r["chain"]["relations"] for r in load(paths("paint-app")[0])["requirement"] if r.get("kind") == "chain"] == [["runtime"]]
    assert all(i["source"] == "lockfile" for i in package["dependency_inventory"])
    for path in manifests:
        manifest = load(path)
        assert manifest["subject"]["commit"] == package["subject"]["commit"]
        for claim in manifest["claim"]:
            for record in claim["evidence"]:
                data = (path.parent / record["record"]).read_bytes()
                assert hashdomains.digest("record:", data) == record["record_hash"]
                assert not re.search(rb"/(?:Users|home)/", data)
                records.add(record["record_hash"])
                for field, domain in (("inputs", "subject:"), ("build_inputs", "artifact:")):
                    for item in record.get(field, []):
                        assert hashdomains.digest(domain, (path.parent / item["path"]).read_bytes()) == item["digest"], f"input digest mismatch: {path.parent / item['path']}"
    chain_controls()
    walkthrough_controls()
    print(f"PASS paint-stack selftest: three decisions, {len(records)} record hashes, identities, path hygiene; 31 walkthrough cases")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
