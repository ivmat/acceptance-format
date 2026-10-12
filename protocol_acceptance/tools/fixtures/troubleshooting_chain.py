"""fixtures/troubleshooting_chain.py — the acceptance/troubleshooting protocol selftest chain
(revision).

Minimal specification -> package -> decision chain for the `acceptance/troubleshooting` profile, newly
bound in `profiles.py` by this change. One PASS case (the whole chain, end to end) and one
FAIL case (the same package, judged against a specification whose `acceptance/troubleshooting` profile
floor — `min_outcome`, a floor concept this profile alone has (no `grade` field exists in this
meaning) — the package's own claim cannot reach, §6.2 cond 9).

The package fixture is the real, checked-in format example
(`format_acceptance/profiles/troubleshooting/examples/valid.acceptance.toml`), copied byte-for-byte
into a fresh tempdir alongside its companion spec/evidence files.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from acceptance_protocol import PROTOCOL_ID, check_specification, check_decision, check_package, load_toml
from fixtures._support import Cases, write

import m11

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_EXAMPLE_DIR = _REPO_ROOT / "format_acceptance" / "profiles" / "troubleshooting" / "examples"

_SUBJECT_COMMIT = "0" * 40  # the example's own zero commit
_REQUIREMENT_ID = "example-fault"  # the example claim's `clause`


def _specification_toml(specification_id: str, min_outcome: str) -> str:
    return f'''
[document]
protocol   = "{PROTOCOL_ID}"
minor      = 0
kind       = "specification"
id         = "{specification_id}"
version    = 1
issued_at  = "2026-09-24T10:00:00Z"
issued_by  = "consumer"
status     = "issued"

[parties]
consumer = {{ name = "Acme Troubleshooting", contact = "ts@acme.example" }}
producer = {{ name = "producer-ts" }}

[subject]
kind         = "other"
name         = "example-troubleshooting-subject"
description  = "acceptance/troubleshooting protocol selftest fixture (revision)"
deliverables = ["artifact"]
constraints  = []
profile      = "acceptance/troubleshooting"

[[requirement]]
id            = "{_REQUIREMENT_ID}"
statement     = "{_REQUIREMENT_ID} must be diagnosable"
mandatory     = true
waivable      = false
domain        = "correctness"
clause_source = "consumer-statement"
  [requirement.evidence]
  min_tier          = "T3"
  weighted_required = false
  control_required  = false
  recipe_required   = false
  freshness         = "any"
  independence      = "none"
  [requirement.evidence.profile."acceptance/troubleshooting"]
  min_outcome = "{min_outcome}"

[acceptance]
rule                  = "all-mandatory-satisfied"
consumer_verification = "spot-check"
authority             = "Acme Troubleshooting / lead"
profiles_required     = ["acceptance/troubleshooting"]
stale_after           = "P90D"
'''


def _write_package(td: Path, specification_id: str, specification_hash: str) -> Path:
    shutil.copy(_EXAMPLE_DIR / "valid.acceptance.toml", td / "acceptance.toml")
    shutil.copy(_EXAMPLE_DIR / "SPEC.md", td / "SPEC.md")
    shutil.copytree(_EXAMPLE_DIR / "evidence", td / "evidence")
    package_path = td / "acceptance.toml"
    text = package_path.read_text()
    marker = 'profile = "acceptance/troubleshooting"\n'
    assert marker in text, "troubleshooting example's [format] block changed shape"
    text = text.replace(
        marker,
        marker + "\n[specification]\n"
        f'id = "{specification_id}"\nhash = "{specification_hash}"\nrequirements_total = 1\n',
    )
    package_path.write_text(text)
    return package_path


def run() -> list[tuple[str, bool, object]]:
    cases = Cases()

    # --- PASS: the whole chain, end to end, with a profile floor the claim meets -------------
    # The C-T5 record-schema check (row 4) opens the evidence's `record` pointer via the core's
    # own repository-root resolution, which needs a `.git` ancestor: give the tempdir an isolated
    # marker rather than borrowing the enclosing checkout's, which a source archive does not have.
    with tempfile.TemporaryDirectory() as tdstr:
        td = Path(tdstr)
        (td / ".git").mkdir()  # isolated B6 repository-root marker; no real git metadata
        specification_id = "AC-TEST-TS-1"
        specification_path = write(td, "acceptance-specification.toml", _specification_toml(specification_id, "isolate_fault_domain"))
        specification_hash = m11.digest_file("specification", specification_path)
        package_path = _write_package(td, specification_id, specification_hash)
        package_hash = m11.digest_file("manifest", package_path)

        specification, _e = load_toml(specification_path)
        package, _e2 = load_toml(package_path)

        rep_c = check_specification(specification)
        cases.check("specification-baseline-valid", rep_c.ok(), rep_c.errors)

        rep_p, cov = check_package(package, specification, package_path, specification_path, strict=False)
        cases.check("package-baseline-valid", rep_p.ok(), rep_p.errors)
        cases.check(
            "coverage-example-fault-satisfied-min_outcome-met",
            cov["requirements"][_REQUIREMENT_ID]["status"] == "satisfied",
            cov["requirements"][_REQUIREMENT_ID],
        )
        cases.check("summary-acceptable-is-true", cov["summary"]["acceptable"] is True, cov["summary"])

        decision_toml = f'''
[document]
protocol  = "{PROTOCOL_ID}"
minor     = 0
kind      = "decision"
id        = "AD-TEST-TS-1"
issued_at = "2026-09-24T11:00:00Z"
issuer    = "Acme Troubleshooting / lead"
verdict   = "accepted"

[binds]
specification = {{ id = "{specification_id}", hash = "{specification_hash}" }}
package  = {{ hash = "{package_hash}" }}
subject  = {{ commit = "{_SUBJECT_COMMIT}" }}

[verification]
mode = "spot-check"

[[disposition]]
requirement = "{_REQUIREMENT_ID}"
status      = "satisfied"
basis       = ["TS-EX-1"]
'''
        decision_path = write(td, "acceptance-decision.toml", decision_toml)
        decision, _e3 = load_toml(decision_path)
        rep_d = check_decision(decision, specification, package, specification_path, package_path)
        cases.check(
            "decision-baseline-accepted",
            rep_d.ok() and decision["document"]["verdict"] == "accepted",
            rep_d.errors,
        )

    # --- FAIL: same package, a profile floor (§6.2 cond 9) the claim's outcome cannot reach ----
    with tempfile.TemporaryDirectory() as tdstr:
        td = Path(tdstr)
        (td / ".git").mkdir()  # isolated B6 repository-root marker; no real git metadata
        specification_id = "AC-TEST-TS-FLOOR-1"
        # TS-EX-1's outcome is "isolate_fault_domain" (rank 1 of 4); "identify_root_cause" (rank 3,
        # the ladder's top) is a real, higher token from the SAME closed OUTCOMES vocabulary the
        # format meaning module owns — not an invented one.
        specification_path = write(td, "acceptance-specification.toml", _specification_toml(specification_id, "identify_root_cause"))
        specification_hash = m11.digest_file("specification", specification_path)
        package_path = _write_package(td, specification_id, specification_hash)

        specification, _e = load_toml(specification_path)
        package, _e2 = load_toml(package_path)

        rep_p, cov = check_package(package, specification, package_path, specification_path, strict=False)
        cases.check(
            "coverage-example-fault-partial-min_outcome-not-met",
            cov["requirements"][_REQUIREMENT_ID]["status"] == "partial",
            cov["requirements"][_REQUIREMENT_ID],
        )
        reason = cov["requirements"][_REQUIREMENT_ID]["reasons"].get("TS-EX-1", "")
        cases.check(
            "coverage-floor-reason-names-the-profile",
            "profile floor not met for 'acceptance/troubleshooting'" in reason,
            reason,
        )
        cases.check("summary-acceptable-is-false-on-floor-fail", cov["summary"]["acceptable"] is False, cov["summary"])

    return cases.items


if __name__ == "__main__":
    import sys

    items = run()
    failed = [c for c in items if not c[1]]
    for name, _ok, detail in failed:
        print(f"SELFTEST FAIL: {name}: {detail}")
    print(f"{'SELFTEST FAILED' if failed else 'SELFTEST PASS'}: {len(items) - len(failed)}/{len(items)} cases")
    sys.exit(99 if failed else 0)
