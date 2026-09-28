"""fixtures/conformance_chain.py — the acceptance/conformance protocol selftest chain (revision).

Minimal contract -> package -> decision chain for the `acceptance/conformance` profile, newly
bound in `profiles.py` by this change (protocol.md §6.6 item 8 was, until now, "the honest
state of every non-verification profile" — no package validator of its own). One PASS case (the
whole chain, end to end) and one FAIL case (the SAME package, judged against a contract whose
`acceptance/conformance` profile floor the package's own claim cannot reach — §6.2 cond 9).

The package fixture is the real, checked-in format example
(`format_acceptance/profiles/conformance/examples/valid/`), copied byte-for-byte into a fresh
tempdir alongside its companion spec/applicability files — not hand-written from scratch, so this
chain exercises a package the format side already treats as its own valid example, not a
protocol-only invention that might drift from what `check_core` actually accepts.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from acceptance_protocol import PROTOCOL_ID, check_contract, check_decision, check_package, load_toml
from fixtures._support import Cases, write

import m11

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_EXAMPLE_DIR = _REPO_ROOT / "format_acceptance" / "profiles" / "conformance" / "examples" / "valid"

# The example's five clauses, and the [requirement.evidence].min_tier each needs to admit its
# claim's evidence kind (EWF-1/EWF-5: kani-harness, tier ceiling T2; the rest carry no evidence, so
# their tier floor is irrelevant to whether they satisfy — only EWF-1 is MANDATORY here).
_CLAUSES = [("EWF-1", "T2"), ("EWF-2", "T5"), ("EWF-3", "T5"), ("EWF-4", "T5"), ("EWF-5", "T2")]

_SUBJECT_COMMIT = "0" * 40  # the example's own zero commit


def _requirement_block(clause_id: str, min_tier: str, *, mandatory: bool, profile_floor: str | None) -> str:
    floor = ""
    if profile_floor is not None:
        floor = f'''
  [requirement.evidence.profile."acceptance/conformance"]
  min_grade = "{profile_floor}"
'''
    return f'''
[[requirement]]
id            = "{clause_id}"
statement     = "{clause_id} must hold"
mandatory     = {"true" if mandatory else "false"}
waivable      = true
domain        = "correctness"
clause_source = "consumer-statement"
  [requirement.evidence]
  min_tier          = "{min_tier}"
  weighted_required = false
  control_required  = false
  recipe_required   = false
  freshness         = "any"
  independence      = "none"
{floor}'''


def _contract_toml(contract_id: str, ewf1_floor: str | None) -> str:
    reqs = "".join(
        _requirement_block(cid, tier, mandatory=(cid == "EWF-1"), profile_floor=(ewf1_floor if cid == "EWF-1" else None))
        for cid, tier in _CLAUSES
    )
    return f'''
[document]
protocol   = "{PROTOCOL_ID}"
minor      = 0
kind       = "contract"
id         = "{contract_id}"
version    = 1
issued_at  = "2026-09-24T10:00:00Z"
issued_by  = "consumer"
status     = "issued"

[parties]
consumer = {{ name = "Acme Conformance", contact = "conf@acme.example" }}
producer = {{ name = "supplier-conf" }}

[subject]
kind         = "other"
name         = "example-wire-decoder"
description  = "acceptance/conformance protocol selftest fixture (revision)"
deliverables = ["artifact"]
constraints  = []
profile      = "acceptance/conformance"
{reqs}
[acceptance]
rule                  = "all-mandatory-satisfied"
consumer_verification = "spot-check"
authority             = "Acme Conformance / lead"
profiles_required     = ["acceptance/conformance"]
stale_after           = "P90D"
'''


def _write_package(td: Path, contract_id: str, contract_hash: str) -> Path:
    for name in ("acceptance.toml", "standard.clauses.toml", "applicability.toml"):
        shutil.copy(_EXAMPLE_DIR / name, td / name)
    package_path = td / "acceptance.toml"
    text = package_path.read_text()
    marker = 'kind_registry = ["rust-crate", "rust-workspace"]\n'
    assert marker in text, "conformance example's [format] block changed shape"
    text = text.replace(
        marker,
        marker + "\n[contract]\n"
        f'id = "{contract_id}"\nhash = "{contract_hash}"\nrequirements_total = {len(_CLAUSES)}\n',
    )
    package_path.write_text(text)
    return package_path


def run() -> list[tuple[str, bool, object]]:
    cases = Cases()

    # --- PASS: the whole chain, end to end, with a profile floor the claim meets -------------
    with tempfile.TemporaryDirectory() as tdstr:
        td = Path(tdstr)
        (td / ".git").mkdir()  # isolated B6 repository-root marker; no real git metadata
        contract_id = "AC-TEST-CONF-1"
        contract_path = write(td, "acceptance-contract.toml", _contract_toml(contract_id, "ungraded"))
        contract_hash = m11.digest_file("contract", contract_path)
        package_path = _write_package(td, contract_id, contract_hash)
        package_hash = m11.digest_file("manifest", package_path)

        contract, _e = load_toml(contract_path)
        package, _e2 = load_toml(package_path)

        rep_c = check_contract(contract)
        cases.check("contract-baseline-valid", rep_c.ok(), rep_c.errors)

        rep_p, cov = check_package(package, contract, package_path, contract_path, strict=False)
        cases.check("package-baseline-valid", rep_p.ok(), rep_p.errors)
        cases.check(
            "coverage-EWF-1-satisfied-min_grade-ungraded-met",
            cov["requirements"]["EWF-1"]["status"] == "satisfied",
            cov["requirements"]["EWF-1"],
        )
        cases.check("summary-acceptable-is-true", cov["summary"]["acceptable"] is True, cov["summary"])

        decision_toml = f'''
[document]
protocol  = "{PROTOCOL_ID}"
minor     = 0
kind      = "decision"
id        = "AD-TEST-CONF-1"
issued_at = "2026-09-24T11:00:00Z"
issuer    = "Acme Conformance / lead"
verdict   = "accepted"

[binds]
contract = {{ id = "{contract_id}", hash = "{contract_hash}" }}
package  = {{ hash = "{package_hash}" }}
subject  = {{ commit = "{_SUBJECT_COMMIT}" }}

[verification]
mode = "spot-check"

[[disposition]]
requirement = "EWF-1"
status      = "satisfied"
basis       = ["CONF/EWF-1"]

[[disposition]]
requirement = "EWF-2"
status      = "insufficient-evidence"
basis       = []

[[disposition]]
requirement = "EWF-3"
status      = "insufficient-evidence"
basis       = []

[[disposition]]
requirement = "EWF-4"
status      = "insufficient-evidence"
basis       = []

[[disposition]]
requirement = "EWF-5"
status      = "satisfied"
basis       = ["CONF/EWF-5"]
'''
        decision_path = write(td, "acceptance-decision.toml", decision_toml)
        decision, _e3 = load_toml(decision_path)
        rep_d = check_decision(decision, contract, package, contract_path, package_path)
        cases.check(
            "decision-baseline-accepted",
            rep_d.ok() and decision["document"]["verdict"] == "accepted",
            rep_d.errors,
        )

    # --- FAIL: same package, a profile floor (§6.2 cond 9) the claim's grade cannot reach -----
    with tempfile.TemporaryDirectory() as tdstr:
        td = Path(tdstr)
        (td / ".git").mkdir()  # isolated B6 repository-root marker; no real git metadata
        contract_id = "AC-TEST-CONF-FLOOR-1"
        # CONF/EWF-1's grade is "ungraded" (rank 0); "mechanical" (rank 2) is a real, higher grade
        # token from the SAME shared vocabulary (acceptance_grammar.GRADES) — not an invented one.
        contract_path = write(td, "acceptance-contract.toml", _contract_toml(contract_id, "mechanical"))
        contract_hash = m11.digest_file("contract", contract_path)
        package_path = _write_package(td, contract_id, contract_hash)

        contract, _e = load_toml(contract_path)
        package, _e2 = load_toml(package_path)

        rep_p, cov = check_package(package, contract, package_path, contract_path, strict=False)
        cases.check(
            "coverage-EWF-1-partial-min_grade-mechanical-not-met",
            cov["requirements"]["EWF-1"]["status"] == "partial",
            cov["requirements"]["EWF-1"],
        )
        reason = cov["requirements"]["EWF-1"]["reasons"].get("CONF/EWF-1", "")
        cases.check(
            "coverage-EWF-1-floor-reason-names-the-profile",
            "profile floor not met for 'acceptance/conformance'" in reason,
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
