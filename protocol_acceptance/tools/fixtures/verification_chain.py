"""fixtures/verification_chain.py — the acceptance/verification protocol selftest chain (revision).

Moved out of acceptance_protocol.py's embedded --selftest (formerly the "# L5-owned" region;
revision fenced it there because the tool was not yet profile-neutral). This module owns the
`acceptance/verification` profile's fixture data and the case chain it drives — contract,
package, decision, amendments, tightening, coverage, states — end to end through the real
`acceptance_protocol.py` core. It is deliberately OUTSIDE the Class rung's scanned file list
(gates/check_core_generic.py's CLASS_FILES): this is Instance-rung fixture data (one profile's
vocabulary — kani/cargo/rust tokens included), not Class vocabulary, so it earns no allowlist —
it is simply not a Class carrier.

`run()` returns the raw case list `[(name, ok, detail), ...]`; the caller (acceptance_protocol.py's
`run_selftest`) aggregates this with the other bound profiles' chains and does the one print/exit.
"""
from __future__ import annotations

from acceptance_protocol import *  # noqa: F401,F403 — the whole core surface this chain drives
from acceptance_protocol import _HERE, _check_evidence_floor, _default_states_doc, _render_contract_toml  # noqa: F401 — underscore names a star-import skips


_SUBJECT_COMMIT = "deadbeef" * 5  # 40 lowercase hex chars

_CONTRACT_TOML = f"""
[document]
protocol   = "{PROTOCOL_ID}"
minor      = 0
kind       = "contract"
id         = "AC-TEST-1"
version    = 1
issued_at  = "2026-09-16T10:00:00Z"
issued_by  = "consumer"
status     = "issued"

[parties]
consumer = {{ name = "Acme Test", contact = "test@acme.example" }}
producer = {{ name = "supplier-test" }}

[subject]
kind         = "other"
name         = "component-x"
description  = "a selftest fixture, artifact-agnostic core"
deliverables = ["artifact"]
constraints  = []
profile      = "acceptance/verification"

[[requirement]]
id            = "R1"
statement     = "R1 must hold"
mandatory     = true
waivable      = false
domain        = "correctness"
clause_source = "consumer-statement"
  [requirement.evidence]
  min_tier          = "T3"
  weighted_required = true
  control_required  = true
  recipe_required   = true
  freshness         = "delivered-revision"
  independence      = "none"

[[requirement]]
id            = "R2"
statement     = "R2 must hold"
mandatory     = true
waivable      = true
domain        = "correctness"
clause_source = "consumer-statement"
  [requirement.evidence]
  min_tier          = "T3"
  weighted_required = true
  control_required  = false
  recipe_required   = false
  freshness         = "any"
  independence      = "none"

[[requirement]]
id            = "R3"
statement     = "R3 is optional and only partially covered"
mandatory     = false
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

[[requirement]]
id            = "R4"
statement     = "every evidenced claim over R1/R2 carries a control"
mandatory     = true
waivable      = false
domain        = "correctness"
clause_source = "consumer-statement"
kind          = "cross-cutting"
over          = ["R1", "R2"]
  [requirement.demands]
  control_required = true

[acceptance]
rule                  = "all-mandatory-satisfied"
consumer_verification = "spot-check"
authority             = "Acme Test / lead"
profiles_required     = ["acceptance/verification"]
stale_after            = "P90D"
"""

_PACKAGE_TOML = f"""
[format]
id      = "acceptance/0"
profile = "acceptance/verification"

[contract]
id                 = "AC-TEST-1"
hash               = "{{{{CONTRACT_HASH}}}}"
requirements_total = 4

[subject]
name   = "component-x"
kind   = "other"
commit = "{_SUBJECT_COMMIT}"
dirty  = false

[spec]
path    = "acceptance-contract.toml"
version = "AC-TEST-1@v1"
axis    = "the requirements of contract AC-TEST-1"

[coverage]
clauses_total = 4
claims_total  = 3
denominator   = "slice"
slice_note    = "Claims enumerate item requirements; cross-cutting R4 is evaluated over R1 and R2."
slice_boundary = "Item requirements R1, R2, R3; no separate claim for cross-cutting R4."

[[claim]]
id            = "C1"
clause        = "R1"
item          = "src/lib.rs::r1"
statement     = "C1 satisfies R1"
band          = "A1"
weight        = "weighted"
grade         = "test-only"
status        = "evidenced"
clause_source = "spec-document"

  [[claim.evidence]]
  kind      = "unit-test"
  family    = "dynamic"
  ref       = "test_r1"
  result    = "pass"
  tool      = "cargo test"
  record    = "evidence/c1.json"
  cases     = 3
  captured_at_commit = "{_SUBJECT_COMMIT}"

  [[claim.evidence]]
  kind      = "unit-test"
  family    = "dynamic"
  ref       = "test_r1_mutant"
  result    = "fail"
  tool      = "cargo test"
  record    = "evidence/c1-mutant.json"
  cases     = 1
  captured_at_commit = "{_SUBJECT_COMMIT}"
    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "C1"

  [claim.self_verify]
  command = "cargo test --test r1"
  expect  = "test result: ok"

    [claim.self_verify.watched_fail]
    of_command = "cargo test --test r1"
    perturbed  = "dropped the length check in decode"
    observed   = "test_r1 FAILED on a short input"
    date       = "2026-09-10"

[[claim]]
id        = "C2"
clause    = "R2"
item      = "src/lib.rs::r2"
statement = "C2 has not yet been evidenced against R2"
band      = "A0"
status    = "gap"

[[claim]]
id        = "C3"
clause    = "R3"
item      = "src/lib.rs::r3"
statement = "C3 partially covers R3"
band      = "A0"
grade     = "test-only"
status    = "partial"

  [[claim.evidence]]
  kind      = "lint"
  family    = "mechanical"
  ref       = "clippy"
  result    = "pass"
  tool      = "clippy"
  record    = "evidence/c3.json"

[[deviation]]
requirement      = "R2"
kind             = "unmet"
statement        = "R2 not yet met"
cause            = "no dynamic test written yet"
impact           = "R2's behaviour is unverified at delivery"
remedy           = "write and land the test, target next release"
waiver_requested = true
"""

_DECISION_TOML = f"""
[document]
protocol  = "{PROTOCOL_ID}"
minor     = 0
kind      = "decision"
id        = "AD-TEST-1"
issued_at = "2026-09-20T09:00:00Z"
issuer    = "Acme Test / lead"
verdict   = "accepted-with-conditions"

[binds]
contract = {{ id = "AC-TEST-1", hash = "{{{{CONTRACT_HASH}}}}" }}
package  = {{ hash = "{{{{PACKAGE_HASH}}}}" }}
subject  = {{ commit = "{_SUBJECT_COMMIT}" }}

[verification]
mode = "spot-check"

[[disposition]]
requirement = "R1"
status      = "satisfied"
basis       = ["C1"]

[[disposition]]
requirement = "R2"
status      = "waived"
basis       = []
conditions  = ["COND1"]
  [disposition.waiver]
  reason    = "bounded evidence accepted for this release"
  code      = "risk-accepted"
  authority = "Acme Test / lead"

[[disposition]]
requirement = "R3"
status      = "insufficient-evidence"
basis       = ["C3"]

[[disposition]]
requirement = "R4"
status      = "satisfied"
basis       = ["C1"]

[[condition]]
id            = "COND1"
requirement   = "R2"
statement     = "produce more evidence for R2"
due           = "2026-12-01"
owner         = "producer"
discharged_by = "a superseding package in which coverage(R2) = satisfied"

[validity]
# Finding 9: capped at issued_at (2026-09-20T09:00:00Z) + the contract's stale_after (P90D) =
# 2026-12-19 — exactly at the ceiling (earlier is allowed, later is an error).
stale_after = "2026-12-19"
"""

_STATES_TOML_DEAD = """
protocol = "acceptance-protocol/0"
minor    = 0

[machine.tiny]
roles    = ["consumer"]
states   = ["a", "b", "dead"]
initial  = "a"
terminal = ["b"]

[[machine.tiny.transition]]
name = "go"
from = "a"
to   = "b"
by   = "consumer"

[[verdict_rule]]
row = 1
mandatory_any = ["unsatisfied"]
conditions = "any"
verdict = "rejected"

[[verdict_rule]]
row = 2
mandatory_any = ["insufficient-evidence"]
conditions = "some"
verdict = "evidence-requested"

[[verdict_rule]]
row = 3
mandatory_all_in = ["satisfied", "satisfied-with-conditions", "waived"]
mandatory_not_all = "satisfied"
conditions = "some"
verdict = "accepted-with-conditions"

[[verdict_rule]]
row = 4
mandatory_all_in = ["satisfied"]
conditions = "none"
verdict = "accepted"
"""


from fixtures._support import Cases as _Cases, write as _write  # noqa: E402


def run() -> list[tuple[str, bool, object]]:
    cases = _Cases()

    with tempfile.TemporaryDirectory() as tdstr:
        td = Path(tdstr)
        (td / ".git").mkdir()  # isolated B6 repository-root marker; no real git metadata

        # Complete the native payload pointers so the GREEN fixture also passes strict format validation.
        (td / "evidence").mkdir()
        for payload in ("c1.json", "c1-mutant.json", "c3.json"):
            _write(td / "evidence", payload, '{"fixture": "protocol selftest"}\n')
        contract_path = _write(td, "acceptance-contract.toml", _CONTRACT_TOML)
        contract_hash = m11.digest_file("contract", contract_path)
        package_path = _write(td, "acceptance.toml", _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash))
        package_hash = m11.digest_file("manifest", package_path)
        decision_path = _write(
            td, "acceptance-decision.toml",
            _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace("{{PACKAGE_HASH}}", package_hash),
        )

        contract, _e = load_toml(contract_path)
        package, _e = load_toml(package_path)
        decision, _e = load_toml(decision_path)

        # --- baseline positive fixtures --------------------------------------------------
        rep_c = check_contract(contract)
        cases.check("contract-baseline-valid", rep_c.ok(), rep_c.errors)

        rep_p, cov = check_package(package, contract, package_path, contract_path, strict=False)
        cases.check("package-baseline-valid", rep_p.ok(), rep_p.errors)
        cases.check("coverage-R1-satisfied-weighted-control-recipe-freshness",
                    cov["requirements"]["R1"]["status"] == "satisfied", cov["requirements"]["R1"])
        cases.check("coverage-R2-deviation-declared-waivable",
                    cov["requirements"]["R2"]["status"] == "deviation-declared", cov["requirements"]["R2"])
        cases.check("coverage-R3-partial-below-floor",
                    cov["requirements"]["R3"]["status"] == "partial", cov["requirements"]["R3"])
        cases.check("coverage-R4-crosscutting-satisfied",
                    cov["requirements"]["R4"]["status"] == "satisfied", cov["requirements"]["R4"])
        cases.check("coverage-summary-acceptable-is-false",
                    cov["summary"]["acceptable"] is False, cov["summary"])

        rep_d = check_decision(decision, contract, package, contract_path, package_path)
        cases.check(
            "decision-baseline-accepted-with-conditions",
            rep_d.ok() and decision["document"]["verdict"] == "accepted-with-conditions",
            rep_d.errors,
        )

        # 0.3.2 correctness lens: missing spec propagation, through the actual CLI
        # (text and JSON), with the SAME complete contract/package/decision as control.
        import contextlib
        import io
        from acceptance_protocol import main as protocol_main
        from unittest.mock import patch

        def cli_result(*args):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), patch(
                "acceptance_protocol.print_coverage_table",
                side_effect=lambda cov: print_coverage_table(cov, file=output),
            ):
                code = protocol_main(["acceptance_protocol.py", *map(str, args)])
            return code, output.getvalue()

        def cli_chain(label, pp, dp, expected):
            commands = [
                ("package", ["check-package", pp, "--contract", contract_path]),
                ("decision", ["check-decision", dp, "--contract", contract_path, "--package", pp]),
                ("effect", ["check-decision", dp, "--contract", contract_path, "--package", pp,
                            "--effect", "--allow-conditions", "--now", "2026-09-28"]),
            ]
            for verb, args in commands:
                for json_args in ([], ["--json"]):
                    code, output = cli_result(*args, *json_args)
                    named = "spec.path" in output and "missing-spec.toml" in output
                    cases.check(f"correctness-1-{label}-{verb}-{'json' if json_args else 'text'}",
                                code == expected and (expected == 0 or named), (code, output))

        cli_chain("green", package_path, decision_path, 0)
        missing_path = _write(td, "missing-package.toml", package_path.read_text().replace(
            'path    = "acceptance-contract.toml"', 'path    = "missing-spec.toml"'))
        missing_pkg, _ = load_toml(missing_path)
        missing_decision_path = _write(td, "missing-decision.toml", decision_path.read_text().replace(
            package_hash, m11.digest_file("manifest", missing_path)))
        missing_format = check_core.validate(missing_path, strict=True)
        cases.check("correctness-1-missing-spec-format-INDETERMINATE",
                    check_core.verdict(missing_format) == ("INDETERMINATE", 2), missing_format.unknowns)
        cli_chain("missing-spec-red", missing_path, missing_decision_path, 2)
        missing_grants, _ = claim_weight_grants(missing_path, missing_pkg["claim"],
                                               PROFILES["acceptance/verification"])
        cases.check("correctness-1-unresolved-format-grants-no-weight", not any(missing_grants.values()),
                    missing_grants)

        # 0.3.2 correctness lens: weighted-toy carrier shape — dynamic unit-test
        # with method lean-theorem and no explicit tier; raise only R1's floor to T1.
        high_contract_path = _write(td, "high-contract.toml", _CONTRACT_TOML.replace(
            'min_tier          = "T3"', 'min_tier          = "T1"', 1))
        high_contract, _ = load_toml(high_contract_path)
        high_package_path = _write(td, "high-package.toml", package_path.read_text().replace(
            contract_hash, m11.digest_file("contract", high_contract_path)).replace(
            'kind      = "unit-test"', 'kind      = "unit-test"\n  method    = "lean-theorem"', 1))
        high_pkg, _ = load_toml(high_package_path)
        high_format = check_core.validate(high_package_path, strict=True)
        cases.check("correctness-2-inferred-tier-format-green", check_core.verdict(high_format)[1] == 0,
                    (high_format.errors, high_format.unknowns))
        high_rep, high_cov = check_package(high_pkg, high_contract, high_package_path, high_contract_path, True)
        cases.expect_fail("correctness-2-inferred-T1-dynamic-red", high_rep,
                          "requirement 'R1' is mandatory and coverage computed 'partial'")
        cases.check("correctness-2-T3-cannot-meet-T1-floor",
                    "claim tier 'T3' does not reach min_tier 'T1'" in high_cov["requirements"]["R1"]["reasons"].get("C1", ""),
                    high_cov["requirements"]["R1"])
        capped_profile = {**PROFILES["acceptance/verification"], "family_ceiling": high_format.families}
        for label, record, tier in [
            ("family-only", {"method": "lean-theorem", "family": "dynamic"}, "T3"),
            ("kind-only", {"method": "lean-theorem", "kind": "unit-test"}, "T3"),
            ("consistent-green", {"method": "unit-test", "kind": "unit-test", "family": "dynamic"}, "T3"),
            ("kernel-green", {"method": "lean-theorem", "kind": "lean-theorem", "family": "kernel"}, "T1"),
        ]:
            actual = record_tier(record, capped_profile)
            cases.check(f"correctness-2-{label}-ceiling", actual == (tier, None), actual)
        explicit_tier, explicit_error = record_tier(
            {"family": "dynamic", "epistemic_tier": "T1"}, capped_profile)
        cases.check("correctness-2-explicit-family-ceiling-red", explicit_tier is None and
                    bool(explicit_error and "family ceiling 'T3'" in explicit_error), explicit_error)

        # A record whose `kind` is capped correctly (T3, by the tier-ceiling fix above) can still
        # name a DIFFERENT, stronger `method` token literally, and a `methods` floor naming that
        # token was
        # satisfied by raw membership (§6.2 cond 4's old `(e.get("method") or e.get("kind")) in
        # methods`) with no check that the two fields agree. Reproduction: R1's floor keeps
        # min_tier = T3 (unaffected by the earlier tier-ceiling cap) but additionally requires
        # methods = ["lean-theorem"]; C1's record still declares kind = "unit-test" /
        # family = "dynamic" (a real cargo-test run) but ALSO method = "lean-theorem" — no
        # epistemic_tier declared, same carrier shape as round-1's fixture.
        for label, record, expect_conflict in [
            ("no-kind", {"method": "lean-theorem"}, False),
            ("no-method", {"kind": "unit-test"}, False),
            ("equal-tokens", {"method": "unit-test", "kind": "unit-test"}, False),
            ("conflicting-tokens", {"method": "lean-theorem", "kind": "unit-test"}, True),
        ]:
            conflict = record_kind_method_conflict(record)
            cases.check(f"correctness-2b-conflict-detect-{label}", bool(conflict) == expect_conflict, conflict)

        conflict_contract_path = _write(td, "conflict-contract.toml", _CONTRACT_TOML.replace(
            'independence      = "none"',
            'independence      = "none"\n  methods           = ["lean-theorem"]', 1))
        conflict_contract, _ = load_toml(conflict_contract_path)
        conflict_package_path = _write(td, "conflict-package.toml", package_path.read_text().replace(
            contract_hash, m11.digest_file("contract", conflict_contract_path)).replace(
            'kind      = "unit-test"', 'kind      = "unit-test"\n  method    = "lean-theorem"', 1))
        conflict_pkg, _ = load_toml(conflict_package_path)
        conflict_format = check_core.validate(conflict_package_path, strict=True)
        cases.check("correctness-2b-conflict-format-green", check_core.verdict(conflict_format)[1] == 0,
                    (conflict_format.errors, conflict_format.unknowns))
        conflict_rep, conflict_cov = check_package(
            conflict_pkg, conflict_contract, conflict_package_path, conflict_contract_path, True)
        cases.expect_fail("correctness-2b-conflicting-method-refused-red", conflict_rep,
                          "requirement 'R1' is mandatory and coverage computed 'partial'")
        cases.check("correctness-2b-conflicting-method-not-satisfied-red",
                    conflict_cov["requirements"]["R1"]["status"] != "satisfied",
                    conflict_cov["requirements"]["R1"])
        cases.check("correctness-2b-conflicting-method-named-reason-red",
                    "conflicting method" in conflict_cov["requirements"]["R1"]["reasons"].get("C1", ""),
                    conflict_cov["requirements"]["R1"])
        cases.check("correctness-2b-conflicting-method-record-error-surfaced-red",
                    any("conflicting method" in e for e in conflict_cov["record_errors"]),
                    conflict_cov["record_errors"])

        # GREEN control: the SAME `methods` floor mechanism, honestly satisfied — R1 requires
        # methods = ["unit-test"] and C1's record names ONLY kind = "unit-test" (no `method`
        # field at all, the ordinary unmodified fixture shape) — proves the fix refuses a
        # conflicting declaration without breaking a legitimate, non-conflicting one.
        consistent_contract_path = _write(td, "consistent-contract.toml", _CONTRACT_TOML.replace(
            'independence      = "none"',
            'independence      = "none"\n  methods           = ["unit-test"]', 1))
        consistent_contract, _ = load_toml(consistent_contract_path)
        consistent_package_path = _write(td, "consistent-package.toml", package_path.read_text().replace(
            contract_hash, m11.digest_file("contract", consistent_contract_path)))
        consistent_pkg, _ = load_toml(consistent_package_path)
        consistent_rep, consistent_cov = check_package(
            consistent_pkg, consistent_contract, consistent_package_path, consistent_contract_path, True)
        cases.check("correctness-2b-consistent-method-satisfies-green",
                    consistent_cov["requirements"]["R1"]["status"] == "satisfied",
                    consistent_cov["requirements"]["R1"])
        cases.check("correctness-2b-consistent-method-no-record-errors-green",
                    consistent_cov["record_errors"] == [], consistent_cov["record_errors"])

        # --- identity-wire "protocol identity = format identity" + "one wire form" ---------------
        # A package/decision pair whose subject carries B1's CONTENT-DIGEST identity, not
        # git-revision — exercising check_package rule 5 and check_decision's [binds].subject
        # comparison for the non-commit identity kinds (protocol.md §7).
        _CDIGEST_HEX = "a1" * 64
        _CDIGEST_WRONG_HEX = "b2" * 64
        cdigest_contract_text = f'''
[document]
protocol   = "{PROTOCOL_ID}"
minor      = 0
kind       = "contract"
id         = "AC-CDIGEST-1"
version    = 1
issued_at  = "2026-09-16T10:00:00Z"
issued_by  = "consumer"
status     = "issued"

[parties]
consumer = {{ name = "Acme Test", contact = "test@acme.example" }}
producer = {{ name = "supplier-test" }}

[subject]
kind         = "other"
name         = "component-digest"
description  = "a identity-wire content-digest subject fixture"
deliverables = ["artifact"]
constraints  = []
profile      = "acceptance/verification"

[[requirement]]
id            = "D1"
statement     = "D1 must hold"
mandatory     = true
waivable      = false
domain        = "correctness"
clause_source = "consumer-statement"
  [requirement.evidence]
  min_tier          = "T3"
  weighted_required = true
  control_required  = false
  recipe_required   = false
  freshness         = "any"
  independence      = "none"

[acceptance]
rule                  = "all-mandatory-satisfied"
consumer_verification = "spot-check"
authority             = "Acme Test / lead"
profiles_required     = ["acceptance/verification"]
'''
        cdigest_contract_path = _write(td, "acceptance-contract-cdigest.toml", cdigest_contract_text)
        cdigest_contract_hash = m11.digest_file("contract", cdigest_contract_path)
        cdigest_contract, _e = load_toml(cdigest_contract_path)

        cdigest_package_text = f'''
[format]
id      = "acceptance/0"
profile = "acceptance/verification"

[contract]
id                 = "AC-CDIGEST-1"
hash               = "{cdigest_contract_hash}"
requirements_total = 1

[subject]
name   = "component-digest"
kind   = "other"
digest = "subject:sha-512:{_CDIGEST_HEX}"

[spec]
path    = "acceptance-contract-cdigest.toml"
version = "AC-CDIGEST-1@v1"
axis    = "the requirements of contract AC-CDIGEST-1"

[coverage]
clauses_total = 1
claims_total  = 1

[[claim]]
id            = "CD1"
clause        = "D1"
item          = "src/lib.rs::d1"
statement     = "CD1 satisfies D1"
band          = "A1"
weight        = "weighted"
grade         = "test-only"
status        = "evidenced"
clause_source = "spec-document"

  [[claim.evidence]]
  kind      = "unit-test"
  family    = "dynamic"
  ref       = "test_d1"
  result    = "pass"
  tool      = "cargo test"
  record    = "evidence/cd1.json"
  cases     = 1

  [[claim.evidence]]
  kind      = "unit-test"
  family    = "dynamic"
  ref       = "test_d1_mutant"
  result    = "fail"
  tool      = "cargo test"
  record    = "evidence/cd1-mutant.json"
  cases     = 1
    [claim.evidence.control]
    kind        = "mutation"
    expectation = "red"
    observed    = "red"
    of_claim    = "CD1"

  [claim.self_verify]
  command = "cargo test --test d1"
  expect  = "test result: ok"

    [claim.self_verify.watched_fail]
    of_command = "cargo test --test d1"
    perturbed  = "dropped the length check in decode"
    observed   = "test_d1 FAILED on a short input"
    date       = "2026-09-10"
'''
        cdigest_package_path = _write(td, "acceptance-cdigest.toml", cdigest_package_text)
        cdigest_package_hash = m11.digest_file("manifest", cdigest_package_path)
        cdigest_package, _e = load_toml(cdigest_package_path)

        rep_cdigest_pkg, cov_cdigest = check_package(
            cdigest_package, cdigest_contract, cdigest_package_path, cdigest_contract_path, strict=False,
        )
        cases.check("identity-wire-content-digest-package-valid-PASS", rep_cdigest_pkg.ok(), rep_cdigest_pkg.errors)
        cases.check(
            "identity-wire-content-digest-coverage-D1-satisfied-PASS",
            cov_cdigest["requirements"]["D1"]["status"] == "satisfied",
            cov_cdigest["requirements"]["D1"],
        )

        cdigest_decision_ok_text = f'''
[document]
protocol  = "{PROTOCOL_ID}"
minor     = 0
kind      = "decision"
id        = "AD-CDIGEST-1"
issued_at = "2026-09-20T09:00:00Z"
issuer    = "Acme Test / lead"
verdict   = "accepted"

[binds]
contract = {{ id = "AC-CDIGEST-1", hash = "{cdigest_contract_hash}" }}
package  = {{ hash = "{cdigest_package_hash}" }}
subject  = {{ digest = "subject:sha-512:{_CDIGEST_HEX}" }}

[verification]
mode = "spot-check"

[[disposition]]
requirement = "D1"
status      = "satisfied"
basis       = ["CD1"]
'''
        cdigest_decision_ok_path = _write(td, "acceptance-decision-cdigest.toml", cdigest_decision_ok_text)
        cdigest_decision_ok, _e = load_toml(cdigest_decision_ok_path)
        rep_cdigest_decision_ok = check_decision(
            cdigest_decision_ok, cdigest_contract, cdigest_package, cdigest_contract_path, cdigest_package_path,
        )
        cases.check(
            "identity-wire-content-digest-decision-accepted-PASS",
            rep_cdigest_decision_ok.ok() and cdigest_decision_ok["document"]["verdict"] == "accepted",
            rep_cdigest_decision_ok.errors,
        )

        # mismatch: [binds].subject carries a DIFFERENT (but well-formed) content digest than the
        # presented package declares — stale (P7), not a silent pass.
        cdigest_decision_mismatch_text = cdigest_decision_ok_text.replace(
            f'digest = "subject:sha-512:{_CDIGEST_HEX}"',
            f'digest = "subject:sha-512:{_CDIGEST_WRONG_HEX}"',
        )
        cdigest_decision_mismatch_path = _write(
            td, "acceptance-decision-cdigest-mismatch.toml", cdigest_decision_mismatch_text,
        )
        cdigest_decision_mismatch, _e = load_toml(cdigest_decision_mismatch_path)
        rep_cdigest_mismatch = check_decision(
            cdigest_decision_mismatch, cdigest_contract, cdigest_package, cdigest_contract_path, cdigest_package_path,
        )
        cases.expect_fail(
            "identity-wire-content-digest-subject-mismatch-FAIL", rep_cdigest_mismatch, "[binds].subject",
        )

        # bare `sha-512:<hex>` wire form — the retired pre-lock m11.py form — on a
        # contract/package/decision hash field is an explicit ERROR naming the expected
        # self-describing form, not merely a downstream mismatch (identity-wire "one wire form").
        bare_wire = "sha-512:" + "0" * 128
        cdigest_package_bare_hash_text = cdigest_package_text.replace(
            f'hash               = "{cdigest_contract_hash}"', f'hash               = "{bare_wire}"',
        )
        cdigest_package_bare_hash_path = _write(
            td, "acceptance-cdigest-bare-hash.toml", cdigest_package_bare_hash_text,
        )
        cdigest_package_bare_hash, _e = load_toml(cdigest_package_bare_hash_path)
        rep_bare_wire, _cov_bare = check_package(
            cdigest_package_bare_hash, cdigest_contract, cdigest_package_bare_hash_path,
            cdigest_contract_path, strict=False,
        )
        cases.expect_fail(
            "identity-wire-bare-sha512-wire-form-is-error-FAIL", rep_bare_wire, "retired bare 'sha-512:<hex>' wire form",
        )

        # --- negative cases, one per rule ------------------------------------------------

        # 1. wrong contract hash — a well-formed self-describing 'contract:sha-512:<hex>' wire
        # value that simply does not recompute (revision: the old fixture used a BARE 'sha-512:<hex>'
        # value, which _reject_bare_m11_wire already flags as the retired wire form before the
        # recompute-mismatch check is ever reached — this left §4.1 rule 1's own hash-recompute
        # check mutation-untested; identity-wire-bare-sha512-wire-form-is-error-FAIL already covers the
        # bare-wire case separately).
        bogus_hash = "contract:sha-512:" + "0" * 128
        pkg1 = _write(td, "pkg-01.toml", _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
                      .replace(f'hash               = "{contract_hash}"', f'hash               = "{bogus_hash}"'))
        doc1, _e = load_toml(pkg1)
        rep1, _cov1 = check_package(doc1, contract, pkg1, contract_path, strict=False)
        cases.expect_fail("wrong-contract-hash", rep1, "does not match M11")

        # 2. requirements_total mismatch — revision: also lowers [coverage].clauses_total to the
        # SAME wrong value so it stays internally consistent with the package's own
        # requirements_total (isolating this check from the separate clauses_total-vs-
        # requirements_total check right below it in check_package, which would otherwise also
        # fire and mask a disabled requirements_total-vs-contract-count guard).
        pkg2 = _write(td, "pkg-02.toml", _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
                      .replace("requirements_total = 4", "requirements_total = 3")
                      .replace("clauses_total = 4", "clauses_total = 3"))
        doc2, _e = load_toml(pkg2)
        rep2, _cov2 = check_package(doc2, contract, pkg2, contract_path, strict=False)
        cases.expect_fail("requirements-total-mismatch", rep2, "requirement count")

        # 2b (core-lock CONFIRMATION review fold, 2026-09-24, §4.1 rule 1's fourth sub-check):
        # [coverage].clauses_total disagrees with [contract].requirements_total while
        # requirements_total itself correctly matches the contract's real count — isolated from
        # case 2 above, which deliberately keeps the two in lockstep to isolate ITS OWN check.
        # Before this case, disabling the clauses_total-vs-requirements_total guard produced ZERO
        # named failures (the packet's own proof standard is guard-disabled -> named-red).
        pkg2b = _write(td, "pkg-02b.toml", _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
                       .replace("clauses_total = 4", "clauses_total = 3"))
        doc2b, _e = load_toml(pkg2b)
        rep2b, _cov2b = check_package(doc2b, contract, pkg2b, contract_path, strict=False)
        cases.expect_fail("coverage-clauses-total-mismatch", rep2b, "does not equal")

        # 3. claim.clause not in contract
        pkg3 = _write(td, "pkg-03.toml", _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
                      .replace('clause        = "R1"', 'clause        = "R99"'))
        doc3, _e = load_toml(pkg3)
        rep3, _cov3 = check_package(doc3, contract, pkg3, contract_path, strict=False)
        cases.expect_fail("claim-clause-not-in-contract", rep3, "not a requirement id")

        # 3b (F3, §4.1 rule 2's second half): a requirement with ZERO claims at all — omission,
        # not a bad clause id. Drops C2 entirely; R2's own [[deviation]] stays (a separate rule).
        _c2_block = (
            '\n[[claim]]\nid        = "C2"\nclause    = "R2"\nitem      = "src/lib.rs::r2"\n'
            'statement = "C2 has not yet been evidenced against R2"\nband      = "A0"\n'
            'status    = "gap"\n'
        )
        assert _c2_block in _PACKAGE_TOML
        pkg3b = _write(
            td, "pkg-03b.toml",
            _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace(_c2_block, ""),
        )
        doc3b, _e = load_toml(pkg3b)
        rep3b, _cov3b = check_package(doc3b, contract, pkg3b, contract_path, strict=False)
        cases.expect_fail("requirement-with-no-claim-at-all", rep3b, "omission is forbidden")

        # 3c (F6, 2026-09-24): [[claim.evidence.inputs]].digest is
        # self-describing ('subject:sha-512:<hex>'); the retired bare form is an explicit ERROR.
        # The anchor is the LAST line of C1's first [[claim.evidence]] block (after
        # captured_at_commit, not before it) — TOML attributes any bare key=value line to the
        # most recently opened table, so inserting earlier would silently reparent
        # captured_at_commit onto the new [[claim.evidence.inputs]]] entry and break freshness.
        _c1_anchor = f'  cases     = 3\n  captured_at_commit = "{_SUBJECT_COMMIT}"\n'
        assert _c1_anchor in _PACKAGE_TOML
        _bare_input_digest = "sha-512:" + "cd" * 64
        pkg3c_bare = _write(
            td, "pkg-03c-bare.toml",
            _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace(
                _c1_anchor,
                _c1_anchor + f'  [[claim.evidence.inputs]]\n  path   = "Cargo.lock"\n  digest = "{_bare_input_digest}"\n',
            ),
        )
        doc3c_bare, _e = load_toml(pkg3c_bare)
        rep3c_bare, _cov3c_bare = check_package(doc3c_bare, contract, pkg3c_bare, contract_path, strict=False)
        cases.expect_fail("claim-evidence-inputs-digest-bare-wire-form-is-error-FAIL", rep3c_bare, "retired bare")

        _self_describing_input_digest = "subject:sha-512:" + "cd" * 64
        pkg3c_ok = _write(
            td, "pkg-03c-ok.toml",
            _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace(
                _c1_anchor,
                _c1_anchor + f'  [[claim.evidence.inputs]]\n  path   = "Cargo.lock"\n  digest = "{_self_describing_input_digest}"\n',
            ),
        )
        doc3c_ok, _e = load_toml(pkg3c_ok)
        rep3c_ok, _cov3c_ok = check_package(doc3c_ok, contract, pkg3c_ok, contract_path, strict=False)
        cases.check(
            "claim-evidence-inputs-digest-self-describing-form-ok-PASS",
            not any("inputs" in e for e in rep3c_ok.errors), rep3c_ok.errors,
        )

        # 4. mandatory unmet without deviation
        text4 = _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
        text4 = text4[:text4.index("[[deviation]]")]
        pkg4 = _write(td, "pkg-04.toml", text4)
        doc4, _e = load_toml(pkg4)
        rep4, _cov4 = check_package(doc4, contract, pkg4, contract_path, strict=False)
        cases.expect_fail("mandatory-unmet-without-deviation", rep4, "no [[deviation]] names it")

        # 4b (revision, §4.1 rule 5): no certified subject identity at all.
        text4b = _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace(
            f'commit = "{_SUBJECT_COMMIT}"\ndirty  = false\n', '',
        )
        pkg4b = _write(td, "pkg-04b.toml", text4b)
        doc4b, _e = load_toml(pkg4b)
        rep4b, _cov4b = check_package(doc4b, contract, pkg4b, contract_path, strict=False)
        cases.expect_fail("package-no-certified-subject-identity", rep4b, "certified identity")

        # 4c (revision, §4.1 rule 6): package's own profile is not one the contract requires.
        text4c = _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace(
            'profile = "acceptance/verification"', 'profile = "acceptance/conformance"',
        )
        pkg4c = _write(td, "pkg-04c.toml", text4c)
        doc4c, _e = load_toml(pkg4c)
        rep4c, _cov4c = check_package(doc4c, contract, pkg4c, contract_path, strict=False)
        cases.expect_fail("package-own-profile-not-required", rep4c, "is not one the contract requires")

        # 4c-bis (A1, WP acceptance 0.3.1 errata): the contract requires the MEANING-ONLY id
        # `acceptance/verification`; the package declares the more specific LEAF
        # `acceptance/verification/code/rust` (a real registered binding of the same validator,
        # `profiles.py`'s PROFILES table). Exact-leaf matching (§4.1 rule 6, §3.1 rule 7) refuses
        # this: a meaning-only id is satisfied only by a package declaring exactly that id, never
        # by a package declaring a leaf under it — no prefix matching at the protocol layer.
        text4cbis = _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace(
            'profile = "acceptance/verification"', 'profile = "acceptance/verification/code/rust"',
        )
        pkg4cbis = _write(td, "pkg-04c-bis.toml", text4cbis)
        doc4cbis, _e = load_toml(pkg4cbis)
        rep4cbis, _cov4cbis = check_package(doc4cbis, contract, pkg4cbis, contract_path, strict=False)
        cases.expect_fail(
            "package-leaf-profile-does-not-satisfy-meaning-only-required-profile-A1",
            rep4cbis, "is not one the contract requires",
        )

        # 4d (revision, §4.1 rule 6): a SECOND required profile the package never mentions as
        # [format].profile or any [[filler]].profile — isolated from the "own profile is
        # required" half (the package's own profile IS one of the two required here).
        contract4d_text = _CONTRACT_TOML.replace(
            'profiles_required     = ["acceptance/verification"]',
            'profiles_required     = ["acceptance/verification", "acceptance/conformance"]',
        )
        contract4d_path = _write(td, "contract-04d.toml", contract4d_text)
        contract4d_hash = m11.digest_file("contract", contract4d_path)
        contract4d, _e = load_toml(contract4d_path)
        pkg4d = _write(td, "pkg-04d.toml", _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract4d_hash))
        doc4d, _e = load_toml(pkg4d)
        rep4d, _cov4d = check_package(doc4d, contract4d, pkg4d, contract4d_path, strict=False)
        cases.expect_fail("package-required-profile-not-present", rep4d, "appears neither as")

        # 4e (core-lock CONFIRMATION review fold, 2026-09-24): the package declares NO
        # [format].profile at all — B12 (no compatibility default) must be reported as an
        # explicit error by check-package itself, never silently resolved to
        # acceptance/verification's package_validator (the removed default behavior).
        text4e = _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace(
            'profile = "acceptance/verification"\n', '',
        )
        pkg4e = _write(td, "pkg-04e.toml", text4e)
        doc4e, _e = load_toml(pkg4e)
        rep4e, _cov4e = check_package(doc4e, contract, pkg4e, contract_path, strict=False)
        cases.expect_fail("package-no-format-profile-declared-no-default-assumed", rep4e,
                           "no compatibility default")

        # 5. contract status draft
        contract5_text = _CONTRACT_TOML.replace('status     = "issued"', 'status     = "draft"')
        contract5_path = _write(td, "contract-05.toml", contract5_text)
        contract5_hash = m11.digest_file("contract", contract5_path)
        contract5, _e = load_toml(contract5_path)
        pkg5 = _write(td, "pkg-05.toml", _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract5_hash))
        doc5, _e = load_toml(pkg5)
        rep5, _cov5 = check_package(doc5, contract5, pkg5, contract5_path, strict=False)
        cases.expect_fail("contract-status-draft", rep5, "issued")

        # 6. issuer == producer
        dec6_text = (_DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
                     .replace("{{PACKAGE_HASH}}", package_hash)
                     .replace('issuer    = "Acme Test / lead"', 'issuer    = "supplier-test"'))
        dec6_path = _write(td, "dec-06.toml", dec6_text)
        doc6, _e = load_toml(dec6_path)
        rep6 = check_decision(doc6, contract, package, contract_path, package_path)
        cases.expect_fail("issuer-equals-producer", rep6, "producer")

        # 7. issuer != authority
        dec7_text = (_DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
                     .replace("{{PACKAGE_HASH}}", package_hash)
                     .replace('issuer    = "Acme Test / lead"', 'issuer    = "Someone Else"'))
        dec7_path = _write(td, "dec-07.toml", dec7_text)
        doc7, _e = load_toml(dec7_path)
        rep7 = check_decision(doc7, contract, package, contract_path, package_path)
        cases.expect_fail("issuer-not-authority", rep7, "authority")

        # 8. disposition satisfied where coverage partial
        dec8_text = (_DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
                     .replace("{{PACKAGE_HASH}}", package_hash)
                     .replace(
                         'requirement = "R3"\nstatus      = "insufficient-evidence"',
                         'requirement = "R3"\nstatus      = "satisfied"',
                     ))
        dec8_path = _write(td, "dec-08.toml", dec8_text)
        doc8, _e = load_toml(dec8_path)
        rep8 = check_decision(doc8, contract, package, contract_path, package_path)
        cases.expect_fail("disposition-satisfied-coverage-partial", rep8, "coverage computed")

        # 9. waiver on non-waivable (R3 is waivable=false)
        dec9_text = (_DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
                     .replace("{{PACKAGE_HASH}}", package_hash)
                     .replace(
                         '[[disposition]]\nrequirement = "R3"\nstatus      = "insufficient-evidence"\nbasis       = ["C3"]',
                         '[[disposition]]\nrequirement = "R3"\nstatus      = "waived"\nbasis       = ["C3"]\n'
                         '  [disposition.waiver]\n  reason    = "test"\n  code      = "risk-accepted"\n'
                         '  authority = "Acme Test / lead"',
                     ))
        dec9_path = _write(td, "dec-09.toml", dec9_text)
        doc9, _e = load_toml(dec9_path)
        rep9 = check_decision(doc9, contract, package, contract_path, package_path)
        cases.expect_fail("waiver-on-non-waivable", rep9, "non-waivable")

        # 10. accepted verdict with a waiver present (R2 stays waived)
        dec10_text = (_DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
                      .replace("{{PACKAGE_HASH}}", package_hash)
                      .replace('verdict   = "accepted-with-conditions"', 'verdict   = "accepted"'))
        dec10_path = _write(td, "dec-10.toml", dec10_text)
        doc10, _e = load_toml(dec10_path)
        rep10 = check_decision(doc10, contract, package, contract_path, package_path)
        cases.expect_fail("accepted-verdict-with-a-waiver", rep10, "accepted")

        # 11. accepted-with-conditions with zero conditions
        text11 = _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace("{{PACKAGE_HASH}}", package_hash)
        text11 = text11[:text11.index("[[condition]]")] + text11[text11.index("[validity]"):]
        dec11_path = _write(td, "dec-11.toml", text11)
        doc11, _e = load_toml(dec11_path)
        rep11 = check_decision(doc11, contract, package, contract_path, package_path)
        cases.expect_fail("accepted-with-conditions-zero-conditions", rep11, "condition")

        # 12. evidence-requested without a producer condition for the insufficient requirement
        dec12_text = (_DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
                      .replace("{{PACKAGE_HASH}}", package_hash)
                      .replace('verdict   = "accepted-with-conditions"', 'verdict   = "evidence-requested"')
                      .replace(
                          '[[disposition]]\nrequirement = "R2"\nstatus      = "waived"\nbasis       = []\n'
                          'conditions  = ["COND1"]\n'
                          '  [disposition.waiver]\n  reason    = "bounded evidence accepted for this release"\n'
                          '  code      = "risk-accepted"\n  authority = "Acme Test / lead"',
                          '[[disposition]]\nrequirement = "R2"\nstatus      = "insufficient-evidence"\nbasis       = []',
                      )
                      # drop the now-orphaned [[condition]] (it named the disposition we just
                      # removed) so this fixture isolates exactly one rule: no producer condition.
                      .replace(
                          '[[condition]]\nid            = "COND1"\nrequirement   = "R2"\n'
                          'statement     = "produce more evidence for R2"\ndue           = "2026-12-01"\n'
                          'owner         = "producer"\n'
                          'discharged_by = "a superseding package in which coverage(R2) = satisfied"\n',
                          '',
                      ))
        dec12_path = _write(td, "dec-12.toml", dec12_text)
        doc12, _e = load_toml(dec12_path)
        rep12 = check_decision(doc12, contract, package, contract_path, package_path)
        cases.expect_fail("evidence-requested-without-producer-condition", rep12, "R2")

        # 13. re-execute-all mode but no passing run on the basis
        dec13_text = (_DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
                      .replace("{{PACKAGE_HASH}}", package_hash)
                      .replace('mode = "spot-check"', 'mode = "re-execute-all"'))
        dec13_path = _write(td, "dec-13.toml", dec13_text)
        doc13, _e = load_toml(dec13_path)
        rep13 = check_decision(doc13, contract, package, contract_path, package_path)
        cases.expect_fail("re-execute-all-mode-no-passing-run", rep13, "passing")

        # 14. stale binds (package hash changed): a different package file on disk, same decision.
        pkg14_text = _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash) + "\n# mutated for staleness test\n"
        pkg14_path = _write(td, "pkg-14.toml", pkg14_text)
        doc14, _e = load_toml(pkg14_path)
        rep14 = check_decision(decision, contract, doc14, contract_path, pkg14_path)
        cases.expect_fail("stale-binds-package-hash-changed", rep14, "stale")

        # 14b (revision, P7): stale binds (CONTRACT hash changed) — the sibling check on the
        # decision's [binds].contract.hash side, no prior fixture isolated it from the package-
        # hash check right below it.
        contract14b_text = _CONTRACT_TOML + "\n# mutated for staleness test\n"
        contract14b_path = _write(td, "contract-14b.toml", contract14b_text)
        doc14b, _e = load_toml(contract14b_path)
        rep14b = check_decision(decision, doc14b, package, contract14b_path, package_path)
        cases.expect_fail("stale-binds-contract-hash-changed", rep14b, "stale")

        # --- §3.5 tightening (check-contract --previous) -----------------------------------
        def _successor_text() -> str:
            return _CONTRACT_TOML.replace(
                'id         = "AC-TEST-1"\nversion    = 1',
                'id         = "AC-TEST-1-v2"\nversion    = 2\nsupersedes = "AC-TEST-1"',
            )

        _R1_EVIDENCE_BLOCK = (
            'min_tier          = "T3"\n  weighted_required = true\n  control_required  = true\n'
            '  recipe_required   = true\n  freshness         = "delivered-revision"\n'
            '  independence      = "none"'
        )

        succ_a_doc = tomllib.loads(_successor_text())
        tight_a = check_contract_tightening(succ_a_doc, contract)
        cases.check("tightening-unchanged-chain-passes", tight_a.ok(), tight_a.errors)

        succ_b_text = _successor_text().replace(
            _R1_EVIDENCE_BLOCK, _R1_EVIDENCE_BLOCK.replace('min_tier          = "T3"', 'min_tier          = "T4"')
        )
        succ_b_doc = tomllib.loads(succ_b_text)
        tight_b = check_contract_tightening(succ_b_doc, contract)
        cases.expect_fail("tightening-weakened-min-tier-without-relaxed", tight_b, "weakened")

        succ_c_text = succ_b_text.replace(
            'clause_source = "consumer-statement"',
            'clause_source = "consumer-statement"\n  [requirement.relaxed]\n'
            '  reason = "loosening the floor for iteration 2, cheaper early checks"\n'
            # Finding 12: `relaxed.by` compares against [acceptance].authority ("Acme Test /
            # lead"), never `parties.consumer.name` ("Acme Test") as a separate identity.
            '  by     = "Acme Test / lead"',
            1,
        )
        succ_c_doc = tomllib.loads(succ_c_text)
        tight_c = check_contract_tightening(succ_c_doc, contract)
        cases.check(
            "tightening-weakened-with-relaxed-passes-with-warn",
            tight_c.ok() and any("relaxed" in w for w in tight_c.warnings),
            (tight_c.errors, tight_c.warnings),
        )

        succ_d_text = _successor_text()
        d_start = succ_d_text.index('[[requirement]]\nid            = "R3"')
        d_end = succ_d_text.index('[[requirement]]\nid            = "R4"')
        succ_d_text = succ_d_text[:d_start] + succ_d_text[d_end:]
        succ_d_doc = tomllib.loads(succ_d_text)
        tight_d = check_contract_tightening(succ_d_doc, contract)
        cases.expect_fail("tightening-dropped-requirement-unlisted", tight_d, "dropped")

        succ_e_text = _successor_text().replace(
            'stale_after            = "P90D"', 'stale_after            = "P90D"\nphase                  = "crystallizing"'
        )
        succ_e_doc = tomllib.loads(succ_e_text)
        tight_e = check_contract_tightening(succ_e_doc, contract)
        cases.expect_fail("tightening-phase-backwards-without-reopened", tight_e, "phase moved backwards")

        # --- §3.6 the amendment document -----------------------------------------------------
        amend_ok_text = f'''
[document]
protocol  = "{PROTOCOL_ID}"
minor     = 0
kind      = "amendment"
id        = "AM-TEST-1"
issued_at = "2026-09-17T09:00:00Z"
issued_by = "producer"
status    = "proposed"

[binds]
contract = {{ id = "AC-TEST-1", hash = "{contract_hash}" }}

[[change]]
op          = "tighten"
requirement = "R2"
reason      = "producer proposes to add a control now that a mutation harness exists"
  [change.proposed]
  min_tier          = "T3"
  weighted_required = true
  control_required  = true
  recipe_required   = false
  freshness         = "any"
  independence      = "none"
'''
        amend_ok_path = _write(td, "amend-ok.toml", amend_ok_text)
        amend_ok_doc, _e = load_toml(amend_ok_path)
        rep_amend_ok = check_amendment(amend_ok_doc, contract, contract_path)
        cases.check("amendment-valid-structure", rep_amend_ok.ok(), rep_amend_ok.errors)

        # amendment against a moved base: status must be 'stale', else ERROR.
        amend_stale_text = amend_ok_text.replace(f'hash = "{contract_hash}"', 'hash = "contract:sha-512:' + "1" * 128 + '"')
        amend_moved_path = _write(td, "amend-moved.toml", amend_stale_text)
        amend_moved_doc, _e = load_toml(amend_moved_path)
        rep_amend_moved = check_amendment(amend_moved_doc, contract, contract_path)
        cases.expect_fail("amendment-moved-base-without-stale-status", rep_amend_moved, "base moved")

        amend_stale_ok_text = amend_stale_text.replace('status    = "proposed"', 'status    = "stale"')
        amend_stale_ok_path = _write(td, "amend-stale-ok.toml", amend_stale_ok_text)
        amend_stale_ok_doc, _e = load_toml(amend_stale_ok_path)
        rep_amend_stale_ok = check_amendment(amend_stale_ok_doc, contract, contract_path)
        cases.check("amendment-moved-base-with-stale-status-ok", rep_amend_stale_ok.ok(), rep_amend_stale_ok.errors)

        # apply of a relax without reason fails.
        amend_relax_noreason_text = amend_ok_text.replace('op          = "tighten"', 'op          = "relax"').replace(
            'reason      = "producer proposes to add a control now that a mutation harness exists"\n', ""
        )
        amend_relax_path = _write(td, "amend-relax-noreason.toml", amend_relax_noreason_text)
        amend_relax_doc, _e = load_toml(amend_relax_path)
        rep_amend_relax = check_amendment(amend_relax_doc, contract, contract_path)
        cases.expect_fail("amendment-relax-without-reason", rep_amend_relax, "reason")

        # apply-amendment output passes check-contract --previous (and is itself a valid
        # standalone contract — §3.6 rule 3, "spec-only iterations are legal").
        new_contract, build_errors = apply_amendment_build(amend_ok_doc, contract, None, "Acme Test / lead")
        cases.check("apply-amendment-builds-successor", not build_errors, build_errors)
        if new_contract is not None:
            tight_applied = check_contract_tightening(new_contract, contract)
            cases.check("apply-amendment-output-passes-tightening", tight_applied.ok(), tight_applied.errors)
            rep_new_contract = check_contract(new_contract)
            cases.check(
                "apply-amendment-output-is-a-valid-standalone-contract",
                rep_new_contract.ok(), rep_new_contract.errors,
            )
            rendered = _render_contract_toml(new_contract)
            reparsed = tomllib.loads(rendered)
            cases.check(
                "apply-amendment-rendered-toml-reparses-and-matches",
                reparsed.get("document", {}).get("id") == new_contract["document"]["id"],
                reparsed,
            )

        # ===================================================================================
        # audit-N fixtures — one per numbered finding in the audit review.
        # audit-1 and audit-2 already appear above, inline with the coverage-core section they
        # extend; the rest follow here, grouped by finding number.
        # ===================================================================================
        import io as _io
        import contextlib as _contextlib
        import types as _types

        # --- audit-3 (Finding 3, §5.2): satisfied-with-conditions on a below-floor,
        # NON-WAIVABLE requirement is refused even with a condition cited; the SAME shape on a
        # WAIVABLE requirement, with a full [disposition.waiver] code='deferred', is accepted. ---
        req_nonwaivable = {"id": "RNW", "mandatory": True, "waivable": False, "evidence": {"independence": "none"}}
        disp_bypass = {"status": "satisfied-with-conditions", "basis": [], "conditions": ["CX"]}
        err_bypass = check_disposition_coverage_row(disp_bypass, req_nonwaivable, "partial", {}, "spot-check", {})
        cases.check(
            "audit-3-satisfied-with-conditions-bypasses-nonwaivable-FAIL",
            err_bypass is not None and "NON-WAIVABLE" in err_bypass,
            err_bypass,
        )
        req_waivable = {"id": "RW", "mandatory": True, "waivable": True, "evidence": {"independence": "none"}}
        disp_ok = {
            "status": "satisfied-with-conditions", "basis": [], "conditions": ["CX"],
            "waiver": {"reason": "x", "code": "deferred", "authority": "A"},
        }
        err_ok = check_disposition_coverage_row(disp_ok, req_waivable, "partial", {}, "spot-check", {})
        cases.check(
            "audit-3-satisfied-with-conditions-waivable-deferred-waiver-PASS",
            err_ok is None, err_ok,
        )
        # ...and the same shape WITHOUT a waiver, or with the wrong waiver code, still fails.
        disp_nowaiver = {"status": "satisfied-with-conditions", "basis": [], "conditions": ["CX"]}
        err_nowaiver = check_disposition_coverage_row(disp_nowaiver, req_waivable, "partial", {}, "spot-check", {})
        cases.check(
            "audit-3-satisfied-with-conditions-waivable-no-waiver-FAIL",
            err_nowaiver is not None, err_nowaiver,
        )

        # --- F3 (2026-09-24): 'satisfied-with-conditions' below-floor
        # requires the waiver CODE to be exactly 'deferred' — a full, otherwise-valid waiver
        # with a DIFFERENT code (e.g. 'risk-accepted') is still refused. ---
        disp_wrong_code = {
            "status": "satisfied-with-conditions", "basis": [], "conditions": ["CX"],
            "waiver": {"reason": "x", "code": "risk-accepted", "authority": "A"},
        }
        err_wrong_code = check_disposition_coverage_row(disp_wrong_code, req_waivable, "partial", {}, "spot-check", {})
        cases.check(
            "f3-satisfied-with-conditions-below-floor-waiver-code-must-be-deferred-FAIL",
            err_wrong_code is not None and "deferred" in err_wrong_code, err_wrong_code,
        )

        # --- F3 (2026-09-24): the plain 'waived' status's OWN full-waiver
        # check (§5.2, P4) — distinct from 'satisfied-with-conditions' deferred-waiver check
        # above and from "waiver-on-non-waivable" below (a WAIVABLE requirement here). A `waiver`
        # table with a VALID code but a MISSING field (`authority`) isolates this check from the
        # unconditional `code not in WAIVER_CODES` check right after it, which would otherwise
        # independently (and misleadingly) catch a fully-absent waiver table too.
        disp_waived_no_waiver = {
            "status": "waived", "basis": [], "waiver": {"reason": "x", "code": "risk-accepted"},
        }
        err_waived_no_waiver = check_disposition_coverage_row(
            disp_waived_no_waiver, req_waivable, "partial", {}, "spot-check", {},
        )
        cases.check(
            "f3-waived-requires-full-waiver-table-FAIL",
            err_waived_no_waiver is not None and "full [disposition.waiver]" in err_waived_no_waiver,
            err_waived_no_waiver,
        )

        # --- audit-4 (Finding 4, §5.0): decision validity is TRANSITIVE — a decision bound (with
        # matching hashes) to a STRUCTURALLY INVALID contract is itself invalid. ---
        contract4_text = _CONTRACT_TOML.replace(
            'consumer = { name = "Acme Test", contact = "test@acme.example" }',
            'consumer = { name = "", contact = "test@acme.example" }',
        )
        contract4_path = _write(td, "contract-audit4.toml", contract4_text)
        contract4_hash = m11.digest_file("contract", contract4_path)
        contract4, _e = load_toml(contract4_path)
        pkg4b_path = _write(td, "pkg-audit4.toml", _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract4_hash))
        doc4b, _e = load_toml(pkg4b_path)
        pkg4b_hash = m11.digest_file("manifest", pkg4b_path)
        dec4b_text = (
            _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract4_hash).replace("{{PACKAGE_HASH}}", pkg4b_hash)
        )
        dec4b_path = _write(td, "dec-audit4.toml", dec4b_text)
        doc_dec4b, _e = load_toml(dec4b_path)
        rep_audit4 = check_decision(doc_dec4b, contract4, doc4b, contract4_path, pkg4b_path)
        cases.expect_fail(
            "audit-4-decision-invalid-when-bound-contract-structurally-invalid", rep_audit4, "consumer",
        )

        # --- audit-5 (Finding 5, §3.5): the tightening rule compares the WHOLE floor set —
        # `methods` removed, cross-cutting `demands`/`over`/`fields` weakened, a profile floor
        # REMOVED, and an unknown profile id treated as an ERROR (never a pass). ---
        old_c5 = {
            "document": {"id": "AC5"},
            "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final"},
            "requirement": [
                {"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                 "evidence": {"min_tier": "T3", "methods": ["unit-test"],
                              "profile": {"acceptance/verification": {"min_grade": "test-only"}}}},
                {"id": "RC", "mandatory": True, "waivable": True, "kind": "cross-cutting", "over": ["R1"],
                 "demands": {"control_required": True, "fields": {"bounds": "bounded"}}},
            ],
        }
        new_c5_weak = {
            "document": {"id": "AC5-v2", "supersedes": "AC5"},
            "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final"},
            "requirement": [
                {"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                 "evidence": {"min_tier": "T3"}},  # methods AND profile floor both dropped
                {"id": "RC", "mandatory": True, "waivable": True, "kind": "cross-cutting", "over": ["R1"],
                 "demands": {}},  # control_required and fields both dropped
            ],
        }
        tight5 = check_contract_tightening(new_c5_weak, old_c5)
        cases.expect_fail("audit-5-methods-removed-without-relaxed", tight5, "methods")
        cases.expect_fail("audit-5-crosscutting-demands-weakened-without-relaxed", tight5, "demands")
        cases.expect_fail("audit-5-profile-floor-removed-without-relaxed", tight5, "REMOVED")

        new_c5_relaxed = {
            "document": {"id": "AC5-v2", "supersedes": "AC5"},
            "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final"},
            "requirement": [
                {"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                 "evidence": {"min_tier": "T3"},
                 "relaxed": {"reason": "cheaper early iteration", "by": "Acme"}},
                {"id": "RC", "mandatory": True, "waivable": True, "kind": "cross-cutting", "over": ["R1"],
                 "demands": {}, "relaxed": {"reason": "cheaper early iteration", "by": "Acme"}},
            ],
        }
        tight5_relaxed = check_contract_tightening(new_c5_relaxed, old_c5)
        cases.check(
            "audit-5-weakened-with-relaxed-passes-with-warn-PASS",
            tight5_relaxed.ok() and bool(tight5_relaxed.warnings),
            (tight5_relaxed.errors, tight5_relaxed.warnings),
        )

        old_c5_unknown_profile = {
            "document": {"id": "AC5U"},
            "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final"},
            "requirement": [
                {"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                 "evidence": {"min_tier": "T3", "profile": {"nonexistent-profile-id": {"x": "y"}}}},
            ],
        }
        new_c5_unknown_profile = {
            "document": {"id": "AC5U-v2", "supersedes": "AC5U"},
            "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final"},
            "requirement": [
                {"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                 "evidence": {"min_tier": "T3", "profile": {"nonexistent-profile-id": {"x": "y"}}}},
            ],
        }
        tight5_unknown = check_contract_tightening(new_c5_unknown_profile, old_c5_unknown_profile)
        cases.expect_fail("audit-5-unknown-profile-comparator-is-error", tight5_unknown, "no comparator available")

        # positive: a genuine TIGHTENING (methods narrowed to a subset) passes cleanly.
        old_c5_methods = {
            "document": {"id": "AC5M"},
            "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final"},
            "requirement": [
                {"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                 "evidence": {"min_tier": "T3", "methods": ["unit-test", "property-test"]}},
            ],
        }
        new_c5_methods_tightened = {
            "document": {"id": "AC5M-v2", "supersedes": "AC5M"},
            "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final"},
            "requirement": [
                {"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                 "evidence": {"min_tier": "T3", "methods": ["unit-test"]}},
            ],
        }
        tight5_methods_ok = check_contract_tightening(new_c5_methods_tightened, old_c5_methods)
        cases.check("audit-5-methods-narrowed-is-a-tightening-PASS", tight5_methods_ok.ok(), tight5_methods_ok.errors)

        # --- audit-6 (Finding 6, §3.6 rule 1): validity != applicability — apply-amendment
        # refuses a non-'proposed' amendment, and refuses when [binds].contract.hash != the
        # recomputed hash of --current (which defaults to --contract but may point elsewhere). ---
        amend_status_text = amend_ok_text.replace('status    = "proposed"', 'status    = "accepted"')
        amend_status_path = _write(td, "amend-audit6-status.toml", amend_status_text)
        args6a = _types.SimpleNamespace(
            amendment=str(amend_status_path), contract=str(contract_path), current=None,
            out=str(td / "out6a.toml"), id=None, accept_by="Acme Test / lead", dry_run=False,
        )
        buf6a = _io.StringIO()
        with _contextlib.redirect_stdout(buf6a):
            rc6a = cmd_apply_amendment(args6a)
        cases.check(
            "audit-6-apply-refuses-non-proposed-status-FAIL",
            rc6a == 1 and "not 'proposed'" in buf6a.getvalue(),
            buf6a.getvalue(),
        )

        other_contract_text = _CONTRACT_TOML.replace('id         = "AC-TEST-1"', 'id         = "AC-OTHER"')
        other_contract_path = _write(td, "contract-audit6-other.toml", other_contract_text)
        args6b = _types.SimpleNamespace(
            amendment=str(amend_ok_path), contract=str(contract_path), current=str(other_contract_path),
            out=str(td / "out6b.toml"), id=None, accept_by="Acme Test / lead", dry_run=False,
        )
        buf6b = _io.StringIO()
        with _contextlib.redirect_stdout(buf6b):
            rc6b = cmd_apply_amendment(args6b)
        cases.check(
            "audit-6-apply-refuses-base-not-current-FAIL",
            rc6b == 1 and "base not current" in buf6b.getvalue(),
            buf6b.getvalue(),
        )

        args6c = _types.SimpleNamespace(
            amendment=str(amend_ok_path), contract=str(contract_path), current=None,
            out=str(td / "out6c.toml"), id=None, accept_by="Acme Test / lead", dry_run=False,
        )
        buf6c = _io.StringIO()
        with _contextlib.redirect_stdout(buf6c):
            rc6c = cmd_apply_amendment(args6c)
        cases.check("audit-6-apply-succeeds-current-and-proposed-PASS", rc6c == 0, buf6c.getvalue())

        # --- audit2-6 (Finding 6, §3.6 rule 1): the CURRENT POINTER is the atomicity
        # mechanism — a stateless "compare against a file the caller chose" is NOT this rule. Two
        # sequential applications of the SAME amendment against the SAME base, with the SAME
        # --pointer, cannot both succeed: the first one moves the pointer to the successor, so the
        # second one's [binds].contract (naming the OLD base) no longer matches it. ---
        pointer26_path = td / "audit2-6-pointer.current"
        cases.check("audit2-6-pointer-absent-before-first-apply-PASS", not pointer26_path.exists(), None)
        args26a = _types.SimpleNamespace(
            amendment=str(amend_ok_path), contract=str(contract_path), current=None,
            pointer=str(pointer26_path), out=str(td / "out-audit2-6-a.toml"), id=None,
            accept_by="Acme Test / lead", dry_run=False,
        )
        buf26a = _io.StringIO()
        with _contextlib.redirect_stdout(buf26a):
            rc26a = cmd_apply_amendment(args26a)
        cases.check(
            "audit2-6-first-apply-creates-pointer-and-succeeds-PASS",
            rc26a == 0 and pointer26_path.exists() and "created current-pointer" in buf26a.getvalue(),
            buf26a.getvalue(),
        )
        pointer26_after_first = json.loads(pointer26_path.read_text(encoding="utf-8"))
        cases.check(
            "audit2-6-pointer-advanced-to-successor-id-PASS",
            pointer26_after_first.get("id") not in (None, (base_id := (contract.get("document") or {}).get("id"))),
            pointer26_after_first,
        )

        # The SAME amendment, SAME base, SAME pointer file, applied a second time — must be
        # REFUSED: the pointer has moved to the successor, so the amendment's [binds].contract
        # (still naming the ORIGINAL base) no longer matches it.
        args26b = _types.SimpleNamespace(
            amendment=str(amend_ok_path), contract=str(contract_path), current=None,
            pointer=str(pointer26_path), out=str(td / "out-audit2-6-b.toml"), id=None,
            accept_by="Acme Test / lead", dry_run=False,
        )
        buf26b = _io.StringIO()
        with _contextlib.redirect_stdout(buf26b):
            rc26b = cmd_apply_amendment(args26b)
        cases.check(
            "audit2-6-second-apply-same-base-refused-pointer-moved-FAIL",
            rc26b == 1 and "base is not current (pointer moved)" in buf26b.getvalue(),
            buf26b.getvalue(),
        )
        cases.check(
            "audit2-6-second-apply-did-not-write-successor-PASS",
            not (td / "out-audit2-6-b.toml").exists(),
            None,
        )

        # --- audit-7 (Finding 7, §4.1 rules 4/7): package binding = (issued AND
        # issued_by=consumer) OR ratified; producer='open' requires a producer filler; the
        # producer identity set includes filler producers. ---
        contract7a_text = _CONTRACT_TOML.replace('issued_by  = "consumer"', 'issued_by  = "producer"')
        contract7a_path = _write(td, "contract-audit7a.toml", contract7a_text)
        contract7a_hash = m11.digest_file("contract", contract7a_path)
        contract7a, _e = load_toml(contract7a_path)
        pkg7a_path = _write(td, "pkg-audit7a.toml", _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract7a_hash))
        doc7a, _e = load_toml(pkg7a_path)
        rep7a, _cov7a = check_package(doc7a, contract7a, pkg7a_path, contract7a_path, strict=False)
        cases.expect_fail(
            "audit-7-producer-drafted-issued-not-ratified-package-invalid-FAIL", rep7a, "not BINDING",
        )

        contract7b_text = _CONTRACT_TOML.replace('producer = { name = "supplier-test" }', 'producer = { name = "open" }')
        contract7b_path = _write(td, "contract-audit7b.toml", contract7b_text)
        contract7b_hash = m11.digest_file("contract", contract7b_path)
        contract7b, _e = load_toml(contract7b_path)
        pkg7b_text = _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract7b_hash)
        pkg7b_path = _write(td, "pkg-audit7b.toml", pkg7b_text)
        doc7b, _e = load_toml(pkg7b_path)
        rep7b, _cov7b = check_package(doc7b, contract7b, pkg7b_path, contract7b_path, strict=False)
        cases.expect_fail("audit-7-open-producer-without-filler-invalid-FAIL", rep7b, "open")

        pkg7c_text = pkg7b_text + '\n[[filler]]\nprofile = "acceptance/verification"\nparty   = "actual-producer-co"\nrole    = "producer"\n'
        pkg7c_path = _write(td, "pkg-audit7c.toml", pkg7c_text)
        doc7c, _e = load_toml(pkg7c_path)
        rep7c, _cov7c = check_package(doc7c, contract7b, pkg7c_path, contract7b_path, strict=False)
        cases.check(
            "audit-7-open-producer-with-filler-rule7-satisfied-PASS",
            not any("[[filler]] with role" in e for e in rep7c.errors),
            rep7c.errors,
        )
        pid_set = producer_identity_set(contract7b, doc7c)
        cases.check(
            "audit-7-producer-identity-set-includes-filler-PASS",
            "actual-producer-co" in pid_set,
            pid_set,
        )

        # --- audit-8 (Finding 8, §5.0): basis is constrained to eligible coverage witnesses (an
        # unrelated claim is refused); a [[verification.run]] must be COMPLETE; worst-result-wins
        # across conflicting runs on one claim. ---
        dec8a_text = (
            _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace("{{PACKAGE_HASH}}", package_hash)
            .replace(
                'requirement = "R1"\nstatus      = "satisfied"\nbasis       = ["C1"]',
                'requirement = "R1"\nstatus      = "satisfied"\nbasis       = ["C3"]',
            )
        )
        dec8a_path = _write(td, "dec-audit8a.toml", dec8a_text)
        doc8a, _e = load_toml(dec8a_path)
        rep8a = check_decision(doc8a, contract, package, contract_path, package_path)
        cases.expect_fail("audit-8-basis-unrelated-claim-refused-FAIL", rep8a, "unrelated claim")

        dec8b_text = (
            _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace("{{PACKAGE_HASH}}", package_hash)
            .replace('[verification]\nmode = "spot-check"',
                      '[verification]\nmode = "spot-check"\n\n[[verification.run]]\nclaim = "C1"\nresult = "pass"')
        )
        dec8b_path = _write(td, "dec-audit8b.toml", dec8b_text)
        doc8b, _e = load_toml(dec8b_path)
        rep8b = check_decision(doc8b, contract, package, contract_path, package_path)
        cases.expect_fail("audit-8-incomplete-verification-run-refused-FAIL", rep8b, "incomplete run")

        dec8c_text = (
            _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace("{{PACKAGE_HASH}}", package_hash)
            .replace('mode = "spot-check"', 'mode = "re-execute-all"')
            .replace(
                '[verification]\nmode = "re-execute-all"',
                '[verification]\nmode = "re-execute-all"\n\n'
                '[[verification.run]]\nclaim   = "C1"\ncommand = "cargo test"\nobserved = "ok"\nresult  = "pass"\nat = "2026-09-20T09:00:00Z"\n\n'
                '[[verification.run]]\nclaim   = "C1"\ncommand = "cargo test"\nobserved = "boom"\nresult  = "fail"\nat = "2026-09-20T09:05:00Z"',
            )
        )
        dec8c_path = _write(td, "dec-audit8c.toml", dec8c_text)
        doc8c, _e = load_toml(dec8c_path)
        rep8c = check_decision(doc8c, contract, package, contract_path, package_path)
        cases.expect_fail("audit-8-worst-result-wins-conflicting-runs-refused-FAIL", rep8c, "worst-result-wins")

        dec8d_text = (
            _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace("{{PACKAGE_HASH}}", package_hash)
            .replace('mode = "spot-check"', 'mode = "re-execute-all"')
            .replace(
                '[verification]\nmode = "re-execute-all"',
                '[verification]\nmode = "re-execute-all"\n\n'
                '[[verification.run]]\nclaim   = "C1"\ncommand = "cargo test"\nobserved = "ok"\nresult  = "pass"\nat = "2026-09-20T09:00:00Z"',
            )
        )
        dec8d_path = _write(td, "dec-audit8d.toml", dec8d_text)
        doc8d, _e = load_toml(dec8d_path)
        rep8d = check_decision(doc8d, contract, package, contract_path, package_path)
        cases.check("audit-8-single-passing-run-re-execute-all-ok-PASS", rep8d.ok(), rep8d.errors)

        # --- audit-9 (Finding 9, §6.2 cond 8): a relied-on record with NO author fails
        # independence=author-not-producer — absence does not satisfy the demand. ---
        floor_indep = {
            "min_tier": "T5", "weighted_required": False, "control_required": False,
            "recipe_required": False, "freshness": "any", "independence": "author-not-producer",
        }
        claim_no_author = {
            "id": "IA", "clause": "RX", "status": "evidenced",
            "evidence": [{"kind": "lint", "epistemic_tier": "T5", "result": "pass"}],
        }
        ok9a, reason9a = meets_item_floor(claim_no_author, floor_indep, None, "acceptance/verification", None, {"supplier-test"}, {})
        cases.check(
            "audit-9-missing-author-fails-independence-FAIL",
            ok9a is False and "no nonempty author" in (reason9a or ""),
            (ok9a, reason9a),
        )
        claim_producer_author = {
            "id": "IB", "clause": "RX", "status": "evidenced",
            "evidence": [{"kind": "lint", "epistemic_tier": "T5", "result": "pass", "author": "supplier-test"}],
        }
        ok9b, reason9b = meets_item_floor(claim_producer_author, floor_indep, None, "acceptance/verification", None, {"supplier-test"}, {})
        cases.check(
            "audit-9-producer-author-fails-independence-FAIL",
            ok9b is False and "producer identity set" in (reason9b or ""),
            (ok9b, reason9b),
        )
        claim_lab_author = {
            "id": "IC", "clause": "RX", "status": "evidenced",
            "evidence": [{"kind": "lint", "epistemic_tier": "T5", "result": "pass", "author": "Lab X"}],
        }
        ok9c, reason9c = meets_item_floor(claim_lab_author, floor_indep, None, "acceptance/verification", None, {"supplier-test"}, {})
        cases.check("audit-9-independent-lab-author-passes-PASS", ok9c is True, (ok9c, reason9c))

        # --- audit-10 (Finding 10, §6.6 item 2/§3.3): the profile floor-schema validator rejects
        # unknown keys and out-of-vocabulary tokens; `kinds` is enforced INDEPENDENTLY of
        # `families` (previously ignored unless `families` was also truthy). ---
        contract10_text = _CONTRACT_TOML.replace(
            '  independence      = "none"\n\n[[requirement]]\nid            = "R2"',
            '  independence      = "none"\n  [requirement.evidence.profile."acceptance/verification"]\n'
            '  min_grade = "typo-grade"\n  min_band  = "A999"\n  bogus_key = "x"\n\n[[requirement]]\nid            = "R2"',
            1,
        )
        rep_contract10 = check_contract(tomllib.loads(contract10_text))
        cases.expect_fail("audit-10-profile-floor-unknown-key-and-tokens-refused-FAIL", rep_contract10, "min_grade")

        _fc = PROFILES["acceptance/verification"]["floor_check"]
        claim_kinds_only = {
            "grade": "test-only", "band": "A1",
            "evidence": [{"kind": "semver-check", "family": "mechanical", "result": "pass"}],
        }
        ok10a, reason10a = _fc({"kinds": ["unit-test"]}, claim_kinds_only)  # families ABSENT
        cases.check("audit-10-kinds-enforced-without-families-FAIL", ok10a is False, (ok10a, reason10a))
        claim_kinds_matching = {
            "grade": "test-only", "band": "A1",
            "evidence": [{"kind": "unit-test", "family": "dynamic", "result": "pass"}],
        }
        ok10b, reason10b = _fc({"kinds": ["unit-test"]}, claim_kinds_matching)
        cases.check("audit-10-kinds-enforced-without-families-PASS", ok10b is True, (ok10b, reason10b))

        # --- audit-11 (Finding 11, §3.5/§3.6 rule 2): apply-amendment strips
        # relaxed/reopened/ratification/amendments from the COPIED base — an inherited
        # relaxation must never excuse a DIFFERENT, later weakening. ---
        import copy as _copy
        base11 = _copy.deepcopy(contract)
        base11["document"]["reopened"] = {"reason": "an old reopen", "by": "Acme Test / lead"}
        for r in base11["requirement"]:
            if r["id"] == "R1":
                r["relaxed"] = {"reason": "an EARLIER, unrelated relaxation", "by": "Acme Test / lead"}
        amend11_text = f'''
[document]
protocol  = "{PROTOCOL_ID}"
minor     = 0
kind      = "amendment"
id        = "AM-AUDIT-11"
issued_at = "2026-09-17T09:00:00Z"
issued_by = "consumer"
status    = "proposed"

[binds]
contract = {{ id = "AC-TEST-1", hash = "{contract_hash}" }}

[[change]]
op          = "tighten"
requirement = "R2"
reason      = "audit-11: unrelated tighten, to prove relaxed/reopened are not inherited"
  [change.proposed]
  min_tier          = "T3"
  weighted_required = true
  control_required  = true
  recipe_required   = false
  freshness         = "any"
  independence      = "none"
'''
        amend11_path = _write(td, "amend-audit11.toml", amend11_text)
        amend11_doc, _e = load_toml(amend11_path)
        new_contract11, build_errors11 = apply_amendment_build(amend11_doc, base11, None, "Acme Test / lead")
        cases.check("audit-11-apply-strips-reopened-PASS", "reopened" not in new_contract11["document"], new_contract11["document"])
        r1_new11 = next(r for r in new_contract11["requirement"] if r["id"] == "R1")
        cases.check("audit-11-apply-strips-relaxed-from-untouched-requirement-PASS", "relaxed" not in r1_new11, r1_new11)

        # --- cv2-1 (§3.6 rule 2): the renderer
        # must preserve EVERY field the checker reads, and the rendered+REPARSED successor of an
        # UNRELATED amendment (tightening R2 only) must still carry them all: contract-level
        # `assurance_class`, a per-requirement `assurance_class` override, `[requirement.evidence]
        # .{build_inputs_required, tool_qualification_required, coverage_min}`, and `[parties]
        # .{boundary, boundary_terms}`. ---
        base_cv2_1 = _copy.deepcopy(contract)
        base_cv2_1["acceptance"]["assurance_class"] = "baseline/0"
        base_cv2_1["parties"]["boundary"] = "cross-org"
        base_cv2_1["parties"]["boundary_terms"] = {"disclosure": "quarterly report", "integrity": "signed hash"}
        for r in base_cv2_1["requirement"]:
            if r["id"] == "R1":
                r["assurance_class"] = "baseline/0"
                r["evidence"]["build_inputs_required"] = True
                r["evidence"]["tool_qualification_required"] = True
                r["evidence"]["coverage_min"] = {"metric": "decision", "value": 0.5}
        amend_cv2_1_text = f'''
[document]
protocol  = "{PROTOCOL_ID}"
minor     = 0
kind      = "amendment"
id        = "AM-CV2-1"
issued_at = "2026-09-26T09:00:00Z"
issued_by = "consumer"
status    = "proposed"

[binds]
contract = {{ id = "AC-TEST-1", hash = "{contract_hash}" }}

[[change]]
op          = "tighten"
requirement = "R2"
reason      = "cv2-1: unrelated tighten, to prove the renderer preserves fields on OTHER requirements and the contract itself"
  [change.proposed]
  min_tier          = "T3"
  weighted_required = true
  control_required  = true
  recipe_required   = false
  freshness         = "any"
  independence      = "none"
'''
        amend_cv2_1_path = _write(td, "amend-cv2-1.toml", amend_cv2_1_text)
        amend_cv2_1_doc, _e = load_toml(amend_cv2_1_path)
        new_contract_cv2_1, build_errors_cv2_1 = apply_amendment_build(amend_cv2_1_doc, base_cv2_1, None, "Acme Test / lead")
        cases.check("cv2-1-apply-amendment-builds-successor", not build_errors_cv2_1, build_errors_cv2_1)
        rep_new_cv2_1 = check_contract(new_contract_cv2_1)
        cases.check("cv2-1-in-memory-successor-passes-check-contract", rep_new_cv2_1.ok(), rep_new_cv2_1.errors)
        rendered_cv2_1 = _render_contract_toml(new_contract_cv2_1)
        reparsed_cv2_1 = tomllib.loads(rendered_cv2_1)
        cases.check(
            "cv2-1-rendered-reparsed-preserves-contract-assurance-class",
            reparsed_cv2_1.get("acceptance", {}).get("assurance_class") == "baseline/0",
            reparsed_cv2_1.get("acceptance"),
        )
        cases.check(
            "cv2-1-rendered-reparsed-preserves-parties-boundary",
            reparsed_cv2_1.get("parties", {}).get("boundary") == "cross-org"
            and reparsed_cv2_1.get("parties", {}).get("boundary_terms")
            == {"disclosure": "quarterly report", "integrity": "signed hash"},
            reparsed_cv2_1.get("parties"),
        )
        r1_reparsed_cv2_1 = next(r for r in reparsed_cv2_1["requirement"] if r["id"] == "R1")
        cases.check(
            "cv2-1-rendered-reparsed-preserves-requirement-assurance-class-override",
            r1_reparsed_cv2_1.get("assurance_class") == "baseline/0",
            r1_reparsed_cv2_1,
        )
        cases.check(
            "cv2-1-rendered-reparsed-preserves-build-inputs-and-tool-qualification-required",
            r1_reparsed_cv2_1["evidence"].get("build_inputs_required") is True
            and r1_reparsed_cv2_1["evidence"].get("tool_qualification_required") is True,
            r1_reparsed_cv2_1["evidence"],
        )
        cases.check(
            "cv2-1-rendered-reparsed-preserves-coverage-min",
            r1_reparsed_cv2_1["evidence"].get("coverage_min") == {"metric": "decision", "value": 0.5},
            r1_reparsed_cv2_1["evidence"],
        )
        # The reparsed document is itself still a fully valid, tightening-compliant successor —
        # exactly the round-trip re-validation `apply-amendment` now performs before issuance.
        rep_reparsed_cv2_1 = check_contract(reparsed_cv2_1)
        cases.check("cv2-1-reparsed-successor-passes-check-contract", rep_reparsed_cv2_1.ok(), rep_reparsed_cv2_1.errors)
        tight_reparsed_cv2_1 = check_contract_tightening(reparsed_cv2_1, base_cv2_1)
        cases.check("cv2-1-reparsed-successor-passes-tightening", tight_reparsed_cv2_1.ok(), tight_reparsed_cv2_1.errors)

        # --- cv2-4 (§3.5/§3.6): check_amendment()
        # must check a `modify` proposal's firmness against the BASE contract's OWN INHERITED
        # phase, not a hardcoded "final" — a `crystallizing`/`exploratory` base's draft requirement
        # stays legal to propose a `modify` over; only a `final` base's proposal is held to A4's
        # all-firm rule. ---
        def _cv2_4_base(phase, firmness):
            return {
                "document": {"id": "AC-CV2-4", "version": 1},
                "parties": {"consumer": {"name": "Acme"}},
                "acceptance": {"phase": phase},
                "requirement": [{
                    "id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                    "statement": "s1", "domain": "correctness", "clause_source": "consumer-statement",
                    "firmness": firmness,
                    "evidence": {
                        "min_tier": "T4", "weighted_required": False, "control_required": False,
                        "recipe_required": False, "freshness": "any", "independence": "none",
                    },
                }],
            }

        def _cv2_4_modify_amendment(firmness):
            return {
                "document": {
                    "protocol": PROTOCOL_ID, "minor": 0, "kind": "amendment", "id": "AM-CV2-4",
                    "issued_at": "2026-09-26T09:00:00Z", "issued_by": "consumer", "status": "proposed",
                },
                "binds": {"contract": {"id": "AC-CV2-4", "hash": "contract:sha-512:" + "0" * 128}},
                "change": [{
                    "op": "modify", "requirement": "R1", "reason": "cv2-4: unrelated floor tweak",
                    "proposed": {
                        "id": "R1", "statement": "s1", "mandatory": True, "waivable": False,
                        "domain": "correctness", "clause_source": "consumer-statement",
                        "firmness": firmness,
                        "evidence": {
                            "min_tier": "T4", "weighted_required": False, "control_required": False,
                            "recipe_required": False, "freshness": "any", "independence": "none",
                        },
                    },
                }],
            }

        for cv2_4_phase in ("exploratory", "crystallizing"):
            base_cv2_4 = _cv2_4_base(cv2_4_phase, "draft")
            amend_cv2_4 = _cv2_4_modify_amendment("draft")
            rep_cv2_4 = check_amendment(amend_cv2_4, base_cv2_4, None)
            cases.check(
                f"cv2-4-{cv2_4_phase}-base-draft-modify-proposal-is-PASS",
                not any("firmness must not be 'draft'" in e for e in rep_cv2_4.errors),
                rep_cv2_4.errors,
            )
        base_cv2_4_final = _cv2_4_base("final", "firm")
        amend_cv2_4_final = _cv2_4_modify_amendment("draft")
        rep_cv2_4_final = check_amendment(amend_cv2_4_final, base_cv2_4_final, None)
        cases.check(
            "cv2-4-final-base-draft-modify-proposal-is-still-REJECTED",
            any("firmness must not be 'draft'" in e for e in rep_cv2_4_final.errors),
            rep_cv2_4_final.errors,
        )

        # --- audit-12 (Finding 12, §5.0a): check-decision --effect. ---
        rep_valid12 = check_decision(decision, contract, package, contract_path, package_path)
        _today12 = today_utc_date()
        eligible12a, reason12a = check_decision_effect(decision, contract, rep_valid12, _today12, True)
        cases.check("audit-12-effect-eligible-accepted-with-conditions-allowed-PASS", eligible12a is True, reason12a)
        eligible12b, reason12b = check_decision_effect(decision, contract, rep_valid12, _today12, False)
        cases.check("audit-12-effect-ineligible-conditions-not-allowed-FAIL", eligible12b is False, reason12b)
        decision_expired12 = dict(decision)
        decision_expired12["validity"] = {"stale_after": "2000-01-01"}
        eligible12c, reason12c = check_decision_effect(decision_expired12, contract, rep_valid12, _today12, True)
        cases.check(
            "audit-12-effect-ineligible-expired-FAIL",
            eligible12c is False and "passed" in reason12c, reason12c,
        )
        contract_provisional12 = _copy.deepcopy(contract)
        contract_provisional12["acceptance"]["phase"] = "exploratory"
        eligible12d, reason12d = check_decision_effect(decision, contract_provisional12, rep_valid12, _today12, True)
        cases.check("audit-12-effect-ineligible-non-final-phase-FAIL", eligible12d is False, reason12d)

        # --- audit-13 (Finding 13, §3.1 rule 1): retired ids never reused across the WHOLE
        # chain; `modify` may not change statement/kind/over/domain; `replaces` requires the old
        # id to be listed in this version's `dropped`. ---
        old13 = {
            "document": {"id": "AC13", "retired_ids": ["R0"]},
            "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final"},
            "requirement": [
                {"id": "R1", "mandatory": True, "waivable": False, "kind": "item", "statement": "s1",
                 "domain": "correctness", "evidence": {"min_tier": "T3"}},
            ],
        }
        new13_reuse = {
            "document": {"id": "AC13-v2", "supersedes": "AC13"},
            "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final"},
            "requirement": [
                {"id": "R1", "mandatory": True, "waivable": False, "kind": "item", "statement": "s1",
                 "domain": "correctness", "evidence": {"min_tier": "T3"}},
                {"id": "R0", "mandatory": True, "waivable": False, "kind": "item", "statement": "reused!",
                 "domain": "correctness", "evidence": {"min_tier": "T3"}},
            ],
        }
        tight13 = check_contract_tightening(new13_reuse, old13)
        cases.expect_fail("audit-13-retired-id-reused-across-chain-FAIL", tight13, "retired")

        new13_semantic = {
            "document": {"id": "AC13-v2", "supersedes": "AC13", "retired_ids": ["R0"]},
            "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final"},
            "requirement": [
                {"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                 "statement": "a DIFFERENT statement", "domain": "correctness",
                 "evidence": {"min_tier": "T3"}},
            ],
        }
        tight13b = check_contract_tightening(new13_semantic, old13)
        cases.expect_fail("audit-13-semantic-replacement-under-same-id-FAIL", tight13b, "semantic replacement")

        new13_floor_only = {
            "document": {"id": "AC13-v2", "supersedes": "AC13", "retired_ids": ["R0"]},
            "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final"},
            "requirement": [
                {"id": "R1", "mandatory": True, "waivable": False, "kind": "item", "statement": "s1",
                 "domain": "correctness", "evidence": {"min_tier": "T2"}},
            ],
        }
        tight13c = check_contract_tightening(new13_floor_only, old13)
        cases.check("audit-13-floor-only-revision-same-id-PASS", tight13c.ok(), tight13c.errors)

        new13_replaces_ok = {
            "document": {"id": "AC13-v2", "supersedes": "AC13",
                         "dropped": [{"id": "R1", "reason": "superseded by R1b"}],
                         "retired_ids": ["R0", "R1"]},
            "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final"},
            "requirement": [
                {"id": "R1b", "mandatory": True, "waivable": False, "kind": "item",
                 "statement": "s1 revised", "domain": "correctness",
                 "evidence": {"min_tier": "T3"}, "replaces": "R1"},
            ],
        }
        tight13d = check_contract_tightening(new13_replaces_ok, old13)
        cases.check("audit-13-replaces-linked-to-dropped-id-PASS", tight13d.ok(), tight13d.errors)

        new13_replaces_bad = {
            "document": {"id": "AC13-v2", "supersedes": "AC13", "retired_ids": ["R0"]},
            "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final"},
            "requirement": [
                {"id": "R1", "mandatory": True, "waivable": False, "kind": "item", "statement": "s1",
                 "domain": "correctness", "evidence": {"min_tier": "T3"}},
                {"id": "R1c", "mandatory": True, "waivable": False, "kind": "item",
                 "statement": "orphan replaces", "domain": "correctness",
                 "evidence": {"min_tier": "T3"}, "replaces": "R-NEVER-DROPPED"},
            ],
        }
        tight13e = check_contract_tightening(new13_replaces_bad, old13)
        cases.expect_fail("audit-13-replaces-without-dropped-linkage-FAIL", tight13e, "replaces")

        amend13_modify_text = f'''
[document]
protocol  = "{PROTOCOL_ID}"
minor     = 0
kind      = "amendment"
id        = "AM-AUDIT-13"
issued_at = "2026-09-17T09:00:00Z"
issued_by = "consumer"
status    = "proposed"

[binds]
contract = {{ id = "AC-TEST-1", hash = "{contract_hash}" }}

[[change]]
op          = "modify"
requirement = "R1"
reason      = "audit-13: attempt to change statement via modify"
  [change.proposed]
  id            = "R1"
  statement     = "a COMPLETELY different statement"
  mandatory     = true
  waivable      = false
  domain        = "correctness"
  clause_source = "consumer-statement"
  [change.proposed.evidence]
  min_tier          = "T3"
  weighted_required = true
  control_required  = true
  recipe_required   = true
  freshness         = "delivered-revision"
  independence      = "none"
'''
        amend13_modify_path = _write(td, "amend-audit13-modify.toml", amend13_modify_text)
        amend13_modify_doc, _e = load_toml(amend13_modify_path)
        rep13_modify = check_amendment(amend13_modify_doc, contract, contract_path)
        cases.expect_fail("audit-13-modify-may-not-change-statement-FAIL", rep13_modify, "op='modify'")

        amend13_modify_ok_text = amend13_modify_text.replace(
            'statement     = "a COMPLETELY different statement"', 'statement     = "R1 must hold"',
        ).replace('control_required  = true', 'control_required  = false')
        amend13_modify_ok_path = _write(td, "amend-audit13-modify-ok.toml", amend13_modify_ok_text)
        amend13_modify_ok_doc, _e = load_toml(amend13_modify_ok_path)
        rep13_modify_ok = check_amendment(amend13_modify_ok_doc, contract, contract_path)
        cases.check("audit-13-modify-floor-only-change-ok-PASS", rep13_modify_ok.ok(), rep13_modify_ok.errors)

        # --- audit-14 (Finding 14, §8 items 2/3): still-applicable requires a DIGEST on every
        # declared input AND tool/semantics continuity (only provable via --new-package); a
        # changed path at the SAME commit still makes the decision stale; the minted
        # discharge_predicate names the REQUIREMENT id, never the claim id. ---
        import copy as _copy2
        package14_undigested = _copy2.deepcopy(package)
        for c in package14_undigested["claim"]:
            if c.get("id") == "C1":
                c["evidence"][0]["inputs"] = [{"path": "src/lib.rs"}]  # no digest
        result14a = compute_impact(
            decision, contract, package14_undigested, new_commit=_SUBJECT_COMMIT,
            changed_paths={"unrelated/other.rs"},
        )
        cases.check("audit-14-changed-path-same-commit-is-stale-PASS", result14a["stale"] is True, result14a["stale"])
        c1_records14a = [r for r in result14a["records"] if r["claim"] == "C1"]
        cases.check(
            "audit-14-undigested-input-is-possibly-invalidated-FAIL",
            bool(c1_records14a) and all(r["class"] == "possibly-invalidated" for r in c1_records14a),
            c1_records14a,
        )

        package14_digested = _copy2.deepcopy(package)
        for c in package14_digested["claim"]:
            if c.get("id") == "C1":
                c["evidence"][0]["inputs"] = [{"path": "src/lib.rs", "digest": "sha-512:" + "a" * 128}]
        result14b = compute_impact(
            decision, contract, package14_digested, new_commit=_SUBJECT_COMMIT,
            changed_paths={"unrelated/other.rs"},
        )
        c1_records14b = [r for r in result14b["records"] if r["claim"] == "C1"]
        cases.check(
            "audit-14-digested-input-no-new-package-is-possibly-invalidated-FAIL",
            bool(c1_records14b) and all(r["class"] == "possibly-invalidated" for r in c1_records14b),
            c1_records14b,
        )
        duty_events14 = [ev for ev in result14b["events"] if ev["kind"] == "minted"]
        cases.check(
            "audit-14-discharge-predicate-over-requirement-id-not-claim-id-PASS",
            bool(duty_events14) and all(
                "coverage(C1)" not in ev["payload"]["duty"]["discharge_predicate"]
                and ("coverage(R1)" in ev["payload"]["duty"]["discharge_predicate"]
                     or "coverage(R4)" in ev["payload"]["duty"]["discharge_predicate"])
                for ev in duty_events14
            ),
            duty_events14,
        )

        new_pkg14 = _copy2.deepcopy(package14_digested)
        result14c = compute_impact(
            decision, contract, package14_digested, new_commit=_SUBJECT_COMMIT,
            changed_paths={"unrelated/other.rs"}, new_package=new_pkg14,
        )
        # only evidence[0] carries the declared, digested input; evidence[1] (the mutant/control
        # record) declares no inputs at all and is unconditionally possibly-invalidated — that is
        # correct and untouched by this fixture, so only evidence[0]'s classification is checked.
        c1_records14c = [r for r in result14c["records"] if r["claim"] == "C1" and r["evidence_id"].endswith("#0")]
        cases.check(
            "audit-14-digested-input-with-matching-new-package-still-applicable-PASS",
            bool(c1_records14c) and all(r["class"] == "still-applicable" for r in c1_records14c),
            c1_records14c,
        )

        # --- audit2-10 (Finding 10, §5.1): `check_decision` and `check-states` evaluate
        # the ACTUAL `[[verdict_rule]]` rows loaded from states.toml — never a second, hand-
        # written Python copy of the table. The exhaustive proof enumerates mandatory-status
        # subsets x {0, some} conditions against an INDEPENDENT literal ground truth
        # (`_literal_verdict_ground_truth`) and evaluates them through the SAME
        # `evaluate_verdict_rules` path `check_decision` uses — so a states.toml row tampered
        # into "always true" is caught, not just "4 rows exist". ---
        _states_doc_v10, _states_err_v10 = load_toml(_HERE.parent / "spec" / "states.toml")
        cases.check("audit2-10-states-toml-loads-for-verdict-proof", _states_err_v10 is None, _states_err_v10)
        rep_verdict_real = verify_verdict_table_exhaustive(_states_doc_v10 or {})
        cases.check(
            "audit2-10-verdict-table-exhaustive-proof-passes-on-real-rows-PASS",
            rep_verdict_real.ok(), rep_verdict_real.errors,
        )

        # WATCHED-BREAK: tamper row 4 (verdict='accepted') into an unconditional match — every
        # `mandatory_*`/`conditions` predicate stripped, the exact "replaced by always true"
        # attack an earlier proof used against the OLD, non-table-reading proof.
        import copy as _copy4
        tampered_rows_v10 = _copy4.deepcopy(_states_doc_v10.get("verdict_rule"))
        for _row in tampered_rows_v10:
            if _row.get("row") == 4:
                _row.pop("mandatory_all_in", None)
                _row.pop("conditions", None)
        tampered_doc_v10 = dict(_states_doc_v10)
        tampered_doc_v10["verdict_rule"] = tampered_rows_v10
        rep_verdict_tampered = verify_verdict_table_exhaustive(tampered_doc_v10)
        cases.check(
            "audit2-10-verdict-table-exhaustive-proof-catches-tampered-row-FAIL",
            not rep_verdict_tampered.ok(),
            rep_verdict_tampered.errors[:3],
        )

        # The same tampering, exercised through `check_decision` directly (not merely the audit
        # proof) — an insufficient-evidence-only decision with ZERO conditions is normally
        # undecidable (row 2 requires conditions='some'); under the tampered row 4 it wafts
        # through as 'accepted' if the decision's own verdict field claims it, proving the
        # corruption reaches real decision validation, not just check-states.
        rep_decision_real = check_decision(decision, contract, package, contract_path, package_path)
        cases.check("audit2-10-check-decision-uses-real-verdict-rows-PASS", rep_decision_real.ok(), rep_decision_real.errors)
        real_rows_v10 = load_verdict_rules(_states_doc_v10)
        expected_real = evaluate_verdict_rules(real_rows_v10, {"satisfied", "waived"}, True)
        tampered_rows_loaded_v10 = load_verdict_rules(tampered_doc_v10)
        expected_tampered = evaluate_verdict_rules(tampered_rows_loaded_v10, set(), False)
        cases.check(
            "audit2-10-tampered-row-changes-evaluator-output-on-an-undecidable-input-FAIL",
            expected_real == "accepted-with-conditions" and expected_tampered == "accepted",
            (expected_real, expected_tampered),
        )

        # --- audit-17 (Finding 17, §6.6 items 6/8): the Rust profile binding exposes
        # package_constraints (dirty must be false) — WARNED by check-package, ENFORCED (error)
        # by check-decision; both reach the validator ONLY through the profile binding. ---
        pkg17_text = _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace("dirty  = false", "dirty  = true")
        pkg17_path = _write(td, "pkg-audit17.toml", pkg17_text)
        doc17, _e = load_toml(pkg17_path)
        rep17_pkg, _cov17 = check_package(doc17, contract, pkg17_path, contract_path, strict=False)
        cases.check(
            "audit-17-dirty-package-warns-in-check-package-PASS",
            rep17_pkg.ok() and any("dirty" in w for w in rep17_pkg.warnings),
            (rep17_pkg.errors, rep17_pkg.warnings),
        )
        pkg17_hash = m11.digest_file("manifest", pkg17_path)
        dec17_text = _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace("{{PACKAGE_HASH}}", pkg17_hash)
        dec17_path = _write(td, "dec-audit17.toml", dec17_text)
        doc_dec17, _e = load_toml(dec17_path)
        rep17_dec = check_decision(doc_dec17, contract, doc17, contract_path, pkg17_path)
        cases.expect_fail("audit-17-dirty-package-refused-in-check-decision-FAIL", rep17_dec, "dirty")
        cases.check(
            "audit-17-package-validator-reached-through-binding-PASS",
            PROFILES["acceptance/verification"]["package_validator"] is CA.validate,
            None,
        )

        # --- audit-18 (Finding 18, §3.1 rule 4/§6.4): 'over' naming a cross-cutting requirement
        # is a contract error (no nesting); `fields_exact` requires the WHOLE string, not a
        # leading token. ---
        contract18_text = _CONTRACT_TOML.replace('over          = ["R1", "R2"]', 'over          = ["R1", "R2", "R4"]')
        rep_contract18 = check_contract(tomllib.loads(contract18_text))
        cases.expect_fail("audit-18-over-names-cross-cutting-requirement-FAIL", rep_contract18, "no nesting")

        demands_fe = {"fields_exact": {"scope": "whole-domain"}}
        claim_fe_exact = {"id": "IE1", "clause": "R1", "status": "evidenced", "scope": "whole-domain"}
        ok18a, reason18a = meets_demands(claim_fe_exact, demands_fe, None, {})
        cases.check("audit-18-fields-exact-matches-PASS", ok18a is True, (ok18a, reason18a))
        claim_fe_prefix_only = {"id": "IE2", "clause": "R1", "status": "evidenced", "scope": "whole-domain: extra text"}
        ok18b, reason18b = meets_demands(claim_fe_prefix_only, demands_fe, None, {})
        cases.check(
            "audit-18-fields-exact-rejects-leading-token-only-match-FAIL",
            ok18b is False and "fields_exact" in (reason18b or ""),
            (ok18b, reason18b),
        )

        # --- §6.4 core demands (revision): min_tier/weighted_required/control_required/fields had no
        # fixture calling meets_demands with a claim that actually FAILS each one (audit-18 above
        # only exercises fields_exact; coverage-R4-crosscutting-satisfied only exercises the
        # control_required POSITIVE path). ---
        demand_claim_ok = {"id": "IE3", "clause": "R1", "status": "evidenced",
                            "evidence": [{"kind": "unit-test", "result": "pass", "epistemic_tier": "T2"}]}
        ok_mt, reason_mt = meets_demands(demand_claim_ok, {"min_tier": "T2"}, None, {})
        cases.check("demands-min-tier-met-PASS", ok_mt is True, (ok_mt, reason_mt))
        ok_mt_fail, reason_mt_fail = meets_demands(demand_claim_ok, {"min_tier": "T1"}, None, {})
        cases.check(
            "demands-min-tier-not-met-FAIL", ok_mt_fail is False and "min_tier" in (reason_mt_fail or ""),
            (ok_mt_fail, reason_mt_fail),
        )
        ok_wt, reason_wt = meets_demands(demand_claim_ok, {"weighted_required": True}, None, {"IE3": True})
        cases.check("demands-weighted-required-met-PASS", ok_wt is True, (ok_wt, reason_wt))
        ok_wt_fail, reason_wt_fail = meets_demands(demand_claim_ok, {"weighted_required": True}, None, {})
        cases.check(
            "demands-weighted-required-not-met-FAIL",
            ok_wt_fail is False and "weighted_required" in (reason_wt_fail or ""), (ok_wt_fail, reason_wt_fail),
        )
        ok_ctl_fail, reason_ctl_fail = meets_demands(demand_claim_ok, {"control_required": True}, None, {})
        cases.check(
            "demands-control-required-not-met-FAIL",
            ok_ctl_fail is False and "control_required" in (reason_ctl_fail or ""), (ok_ctl_fail, reason_ctl_fail),
        )
        demand_claim_controlled = {
            "id": "IE4", "clause": "R1", "status": "evidenced",
            "evidence": [{"kind": "unit-test", "result": "pass",
                          "control": {"kind": "mutation", "expectation": "red", "observed": "red", "of_claim": "IE4"}}],
        }
        ok_ctl_ok, reason_ctl_ok = meets_demands(demand_claim_controlled, {"control_required": True}, None, {})
        cases.check("demands-control-required-met-PASS", ok_ctl_ok is True, (ok_ctl_ok, reason_ctl_ok))
        claim_field_wrong_token = {"id": "IE5", "clause": "R1", "status": "evidenced", "scope": "unbounded: note"}
        ok_field_fail, reason_field_fail = meets_demands(
            claim_field_wrong_token, {"fields": {"scope": "bounded"}}, None, {},
        )
        cases.check(
            "demands-fields-leading-token-mismatch-FAIL",
            ok_field_fail is False and "demands.fields" in (reason_field_fail or ""), (ok_field_fail, reason_field_fail),
        )

        # --- §6.4 (revision): an EMPTY candidate set never satisfies a cross-cutting requirement,
        # even with zero offenders (no prior fixture forced this — coverage-R4 always had >=1
        # evidenced candidate). ---
        req_cc_empty = {"id": "R4", "kind": "cross-cutting", "over": ["R1", "R2"], "demands": {"control_required": True}}
        status_cc_empty, basis_cc_empty, reasons_cc_empty = compute_crosscutting_status(
            req_cc_empty, [{"id": "C1", "clause": "R1", "status": "gap"}], None, set(),
        )
        cases.check(
            "crosscutting-empty-candidate-set-never-satisfies",
            status_cc_empty != "satisfied", (status_cc_empty, basis_cc_empty, reasons_cc_empty),
        )

        # --- audit-20 (Finding 20, §6.2 cond 7): freshness is FULL-LENGTH equality, and BOTH the
        # core name and the profile's alias present but UNEQUAL fails freshness, even though one
        # of them alone would have matched. ---
        floor_fresh = {
            "min_tier": "T5", "weighted_required": False, "control_required": False,
            "recipe_required": False, "freshness": "delivered-revision", "independence": "none",
        }
        claim_alias_conflict = {
            "id": "IF1", "clause": "R1", "status": "evidenced",
            "evidence": [{
                "kind": "lint", "epistemic_tier": "T5", "result": "pass",
                "captured_at_revision": _SUBJECT_COMMIT,
                "captured_at_commit": "0" * 40,
            }],
        }
        ok20a, reason20a = meets_item_floor(
            claim_alias_conflict, floor_fresh, PROFILES["acceptance/verification"],
            "acceptance/verification", _SUBJECT_COMMIT, set(), {},
        )
        cases.check(
            "audit-20-alias-conflict-fails-freshness-FAIL",
            ok20a is False and "alias" in (reason20a or ""),
            (ok20a, reason20a),
        )
        claim_abbreviated = {
            "id": "IF2", "clause": "R1", "status": "evidenced",
            "evidence": [{
                "kind": "lint", "epistemic_tier": "T5", "result": "pass",
                "captured_at_revision": _SUBJECT_COMMIT[:10],
            }],
        }
        ok20b, reason20b = meets_item_floor(
            claim_abbreviated, floor_fresh, PROFILES["acceptance/verification"],
            "acceptance/verification", _SUBJECT_COMMIT, set(), {},
        )
        cases.check("audit-20-abbreviated-revision-fails-freshness-FAIL", ok20b is False, (ok20b, reason20b))
        claim_agreeing = {
            "id": "IF3", "clause": "R1", "status": "evidenced",
            "evidence": [{
                "kind": "lint", "epistemic_tier": "T5", "result": "pass",
                "captured_at_revision": _SUBJECT_COMMIT, "captured_at_commit": _SUBJECT_COMMIT,
            }],
        }
        ok20c, reason20c = meets_item_floor(
            claim_agreeing, floor_fresh, PROFILES["acceptance/verification"],
            "acceptance/verification", _SUBJECT_COMMIT, set(), {},
        )
        cases.check("audit-20-agreeing-alias-and-core-name-passes-PASS", ok20c is True, (ok20c, reason20c))

        # --- states.toml ------------------------------------------------------------------
        real_states, serr = load_toml(_HERE.parent / "spec" / "states.toml")
        cases.check("states-real-file-loads", serr is None, serr)
        if real_states is not None:
            reps = check_states(real_states)
            cases.check(
                "states-real-file-all-pass",
                all(r.ok() for r in reps.values()),
                {k: v.errors for k, v in reps.items() if not v.ok()},
            )

        dead_doc = tomllib.loads(_STATES_TOML_DEAD)
        dead_reps = check_states(dead_doc)
        cases.check(
            "states-dead-state-detected",
            not all(r.ok() for r in dead_reps.values()),
            {k: v.errors for k, v in dead_reps.items()},
        )

        # --- transition -------------------------------------------------------------------
        to, terr = find_transition(real_states, "contract", "draft", "issue")
        cases.check("transition-legal", to == "issued" and terr is None, (to, terr))
        _to, terr2 = find_transition(real_states, "contract", "issued", "issue")
        cases.check("transition-illegal-reported", terr2 is not None, terr2)

        # --- profile/tier selftest additions (spec delta) ----------------------------------
        profile = PROFILES["acceptance/verification"]

        # indeterminate: no epistemic_tier, unknown kind -> meets NO tier floor, even the weakest.
        indeterminate_claim = {
            "id": "IX", "clause": "R1", "status": "evidenced", "weight": "weighted",
            "evidence": [{"kind": "totally-unknown-kind", "result": "pass"}],
        }
        weak_floor = {
            "min_tier": "T5", "weighted_required": True, "control_required": False,
            "recipe_required": False, "freshness": "any", "independence": "none",
        }
        ok_indet, reason_indet = meets_item_floor(
            indeterminate_claim, weak_floor, profile, "acceptance/verification", None, set(),
            {"IX": True},
        )
        cases.check(
            "indeterminate-tier-fails-even-the-weakest-floor",
            ok_indet is False and "cond 3" in (reason_indet or ""),
            (ok_indet, reason_indet),
        )

        # over-strong declared epistemic_tier -> error, and treated as indeterminate.
        overclaim_record = {"kind": "lint", "epistemic_tier": "T1", "result": "pass"}
        t, t_err = record_tier(overclaim_record, profile)
        cases.check(
            "declared-epistemic-tier-stronger-than-ceiling-is-error",
            t is None and t_err is not None and "exceeds the profile ceiling" in t_err,
            (t, t_err),
        )
        overclaim_errors = collect_tier_errors(
            [{"id": "OX", "evidence": [overclaim_record]}], profile,
        )
        cases.check(
            "declared-epistemic-tier-stronger-than-ceiling-surfaces-in-collect",
            bool(overclaim_errors),
            overclaim_errors,
        )

        # audit-2 (Finding 2, §6.2 cond 9, §4.1 rule 6): a profile floor declared for a DIFFERENT
        # profile than the package's own is NEVER MET (fail-closed) — never silently skipped, and
        # never evaluated as if it applied to this package.
        floor_other_profile = {
            "min_tier": "T5", "weighted_required": False, "control_required": False,
            "recipe_required": False, "freshness": "any", "independence": "none",
            "profile": {"some-other-profile": {"min_grade": "test-only"}},
        }
        claim_for_floor = {
            "id": "IY", "clause": "RX", "status": "evidenced", "weight": "weighted",
            "evidence": [{"kind": "lint", "epistemic_tier": "T5", "result": "pass"}],
        }
        ok_wrong_profile, reason_wrong_profile = meets_item_floor(
            claim_for_floor, floor_other_profile, profile, "acceptance/verification", None, set(),
            {"IY": True},
        )
        cases.check(
            "audit-2-profile-floor-under-different-profile-never-met-FAIL",
            ok_wrong_profile is False and "different profile" in (reason_wrong_profile or ""),
            (ok_wrong_profile, reason_wrong_profile),
        )
        floor_no_binding = {
            "min_tier": "T5", "weighted_required": False, "control_required": False,
            "recipe_required": False, "freshness": "any", "independence": "none",
            "profile": {"nonexistent-profile-id": {"min_grade": "test-only"}},
        }
        ok_no_binding, reason_no_binding = meets_item_floor(
            {**claim_for_floor, "id": "IZ"}, floor_no_binding, None, "nonexistent-profile-id",
            None, set(), {"IZ": True},
        )
        cases.check(
            "audit-2-profile-floor-missing-binding-never-met-FAIL",
            ok_no_binding is False and "no binding" in (reason_no_binding or ""),
            (ok_no_binding, reason_no_binding),
        )
        floor_matching_profile = {
            "min_tier": "T5", "weighted_required": False, "control_required": False,
            "recipe_required": False, "freshness": "any", "independence": "none",
            "profile": {"acceptance/verification": {"min_grade": "test-only"}},
        }
        claim_matching = {
            "id": "IW", "clause": "RX", "status": "evidenced", "weight": "weighted",
            "grade": "test-only", "band": "A0",
            "evidence": [{"kind": "lint", "family": "mechanical", "result": "pass"}],
        }
        ok_matching, reason_matching = meets_item_floor(
            claim_matching, floor_matching_profile, profile, "acceptance/verification", None,
            set(), {"IW": True},
        )
        cases.check(
            "audit-2-profile-floor-matching-profile-PASS",
            ok_matching is True,
            (ok_matching, reason_matching),
        )

        # audit-1 (Finding 1, §6.2 cond 2): weighted_required reads the FORMAT VALIDATOR's grant,
        # not the claim's own 'weight' string — a claim reporting weight="weighted" but pending
        # or refused by check_acceptance.py must NOT meet a weighted_required floor.
        weighted_string_floor = {
            "min_tier": "T5", "weighted_required": True, "control_required": False,
            "recipe_required": False, "freshness": "any", "independence": "none",
        }
        claim_claims_weighted = {
            "id": "IV", "clause": "RX", "status": "evidenced", "weight": "weighted",
            "evidence": [{"kind": "lint", "epistemic_tier": "T5", "result": "pass"}],
        }
        ok_ungranted, reason_ungranted = meets_item_floor(
            claim_claims_weighted, weighted_string_floor, None, "acceptance/verification", None,
            set(), {},  # empty weight_grants: NOT granted, whatever claim.weight says
        )
        cases.check(
            "audit-1-unweighted-by-validator-fails-weighted-floor-FAIL",
            ok_ungranted is False and "did not GRANT" in (reason_ungranted or ""),
            (ok_ungranted, reason_ungranted),
        )
        ok_granted, reason_granted = meets_item_floor(
            claim_claims_weighted, weighted_string_floor, None, "acceptance/verification", None,
            set(), {"IV": True},
        )
        cases.check(
            "audit-1-granted-by-validator-passes-weighted-floor-PASS",
            ok_granted is True,
            (ok_granted, reason_granted),
        )

        # ===================================================================================
        # audit2-N fixtures — 2026-09-16, one failing-then-passing
        # pair per numbered finding closed against acceptance_protocol.py / profiles.py.
        # ===================================================================================

        # --- audit2-3 (Finding 3, §5.1/§5.2): every condition CITED BY a disposition must name
        # THAT SAME requirement — the direction the audit-3 fixtures above did not check: a
        # disposition citing a condition whose OWN [[condition]].requirement names a DIFFERENT
        # requirement (the cross-requirement bypass) is refused, even when that other requirement
        # legitimately cites the same condition back. ---
        dec3_cross_text = (
            _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace("{{PACKAGE_HASH}}", package_hash)
            .replace(
                '[[disposition]]\nrequirement = "R1"\nstatus      = "satisfied"\nbasis       = ["C1"]',
                '[[disposition]]\nrequirement = "R1"\nstatus      = "satisfied-with-conditions"\n'
                'basis       = ["C1"]\nconditions  = ["COND1"]',
            )
        )
        dec3_cross_path = _write(td, "dec-audit2-3-cross.toml", dec3_cross_text)
        doc3_cross, _e = load_toml(dec3_cross_path)
        rep3_cross = check_decision(doc3_cross, contract, package, contract_path, package_path)
        cases.expect_fail(
            "audit2-3-disposition-cites-condition-of-a-different-requirement-FAIL",
            rep3_cross, "THAT SAME requirement",
        )

        dec3_ok_text = (
            _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace("{{PACKAGE_HASH}}", package_hash)
            .replace(
                '[[disposition]]\nrequirement = "R1"\nstatus      = "satisfied"\nbasis       = ["C1"]',
                '[[disposition]]\nrequirement = "R1"\nstatus      = "satisfied-with-conditions"\n'
                'basis       = ["C1"]\nconditions  = ["COND-R1"]',
            )
            .replace(
                '[[condition]]\nid            = "COND1"',
                '[[condition]]\nid            = "COND-R1"\nrequirement   = "R1"\n'
                'statement     = "a documentation follow-up"\ndue           = "2026-12-01"\n'
                'owner         = "producer"\n'
                'discharged_by = "a superseding package in which coverage(R1) = satisfied"\n\n'
                '[[condition]]\nid            = "COND1"',
            )
        )
        dec3_ok_path = _write(td, "dec-audit2-3-ok.toml", dec3_ok_text)
        doc3_ok, _e = load_toml(dec3_ok_path)
        rep3_ok = check_decision(doc3_ok, contract, package, contract_path, package_path)
        cases.check("audit2-3-disposition-cites-its-own-requirements-condition-PASS", rep3_ok.ok(), rep3_ok.errors)

        # --- audit2-4 (Finding 4, §3.3): the predecessor chain is validated to ITS ROOT — a
        # predecessor two hops back with an empty parties.consumer.name fails its OWN
        # check-contract; an unavailable ancestor is an error, never a skipped link; --previous-dir
        # resolves ancestors by [document].id; a cycle is an error. ---
        chain_root_bad_text = _CONTRACT_TOML.replace(
            'id         = "AC-TEST-1"', 'id         = "AC-CHAIN-ROOT"',
        ).replace(
            'consumer = { name = "Acme Test", contact = "test@acme.example" }',
            'consumer = { name = "", contact = "test@acme.example" }',
        )
        chain_root_bad_path = _write(td, "chain-root-bad.toml", chain_root_bad_text)

        chain_mid_text = _CONTRACT_TOML.replace(
            'id         = "AC-TEST-1"\nversion    = 1',
            'id         = "AC-CHAIN-MID"\nversion    = 2\nsupersedes = "AC-CHAIN-ROOT"',
        )
        chain_mid_path = _write(td, "chain-mid.toml", chain_mid_text)

        chain_top = _copy.deepcopy(contract)
        chain_top["document"]["id"] = "AC-CHAIN-TOP"
        chain_top["document"]["version"] = 3
        chain_top["document"]["supersedes"] = "AC-CHAIN-MID"

        rep_chain_bad = check_contract_chain(chain_top, [str(chain_mid_path), str(chain_root_bad_path)], None)
        cases.expect_fail("audit2-4-chain-root-empty-consumer-name-fails-own-check-FAIL", rep_chain_bad, "consumer")

        chain_root_ok_text = _CONTRACT_TOML.replace('id         = "AC-TEST-1"', 'id         = "AC-CHAIN-ROOT"')
        chain_root_ok_path = _write(td, "chain-root-ok.toml", chain_root_ok_text)
        rep_chain_ok = check_contract_chain(chain_top, [str(chain_mid_path), str(chain_root_ok_path)], None)
        cases.check("audit2-4-chain-to-root-all-valid-PASS", rep_chain_ok.ok(), rep_chain_ok.errors)

        rep_chain_missing = check_contract_chain(chain_top, [str(chain_mid_path)], None)
        cases.expect_fail("audit2-4-chain-missing-ancestor-is-error-FAIL", rep_chain_missing, "unavailable")

        chain_dir = td / "chain-dir"
        chain_dir.mkdir()
        _write(chain_dir, "mid.toml", chain_mid_text)
        _write(chain_dir, "root.toml", chain_root_ok_text)
        rep_chain_dir = check_contract_chain(chain_top, None, str(chain_dir))
        cases.check("audit2-4-chain-previous-dir-resolves-by-id-PASS", rep_chain_dir.ok(), rep_chain_dir.errors)

        cyc_a_text = _CONTRACT_TOML.replace(
            'id         = "AC-TEST-1"\nversion    = 1',
            'id         = "AC-CYCLE-A"\nversion    = 1\nsupersedes = "AC-CYCLE-B"',
        )
        cyc_b_text = _CONTRACT_TOML.replace(
            'id         = "AC-TEST-1"\nversion    = 1',
            'id         = "AC-CYCLE-B"\nversion    = 1\nsupersedes = "AC-CYCLE-A"',
        )
        cyc_dir = td / "cycle-dir"
        cyc_dir.mkdir()
        _write(cyc_dir, "a.toml", cyc_a_text)
        _write(cyc_dir, "b.toml", cyc_b_text)
        cyc_a_doc, _e = load_toml(cyc_dir / "a.toml")
        _, cyc_errors = resolve_predecessor_chain(cyc_a_doc, None, str(cyc_dir))
        cases.check(
            "audit2-4-chain-cycle-detected-FAIL",
            bool(cyc_errors) and any("cycle" in e for e in cyc_errors),
            cyc_errors,
        )

        # --- audit2-5 (Finding 5, §3.5/§6.6 item 7): the profile comparator treats an ABSENT
        # `families`/`kinds` as UNRESTRICTED — removing a previously-declared restriction, or
        # WIDENING it, is a weakening; `kinds` is compared symmetrically (previously not compared
        # at all); narrowing, or adding a fresh restriction, is a tightening. ---
        _fnw = PROFILES["acceptance/verification"]["floor_not_weaker"]
        cases.check(
            "audit2-5-families-removed-entirely-is-weaker-FAIL",
            _fnw({"families": ["dynamic"]}, {}) is False, None,
        )
        cases.check(
            "audit2-5-kinds-widened-is-weaker-FAIL",
            _fnw({"kinds": ["unit-test"]}, {"kinds": ["unit-test", "kani-harness"]}) is False, None,
        )
        cases.check(
            "audit2-5-families-narrowed-is-tighter-PASS",
            _fnw({"families": ["dynamic", "bmc"]}, {"families": ["dynamic"]}) is True, None,
        )
        cases.check(
            "audit2-5-kinds-added-fresh-is-tighter-PASS",
            _fnw({}, {"kinds": ["unit-test"]}) is True, None,
        )

        # --- audit2-8 (Finding 8, §5.2): adverse runs bind EVERY mode and disposition — a failing
        # basis-claim run forecloses 'satisfied' even under spot-check/package-trusted (not just
        # re-execute-all); satisfied-with-conditions carries the SAME run obligations as satisfied
        # when cov(R) = satisfied. ---
        req_adv = {"id": "RADV", "mandatory": True, "waivable": True, "evidence": {"independence": "none"}}
        disp_adv_satisfied = {"status": "satisfied", "basis": ["X"]}
        err_adv_spotcheck = check_disposition_coverage_row(
            disp_adv_satisfied, req_adv, "satisfied", {"X": [{"result": "fail"}]}, "spot-check", {},
        )
        cases.check(
            "audit2-8-failed-run-forecloses-satisfied-under-spot-check-FAIL",
            err_adv_spotcheck is not None and "fail" in err_adv_spotcheck, err_adv_spotcheck,
        )
        disp_adv_unsatisfied = {"status": "unsatisfied", "basis": ["X"]}
        err_adv_unsatisfied = check_disposition_coverage_row(
            disp_adv_unsatisfied, req_adv, "satisfied", {"X": [{"result": "fail"}]}, "spot-check", {},
        )
        cases.check("audit2-8-unsatisfied-after-failed-run-ok-PASS", err_adv_unsatisfied is None, err_adv_unsatisfied)

        disp_adv_swc = {"status": "satisfied-with-conditions", "basis": ["X"], "conditions": ["CX"]}
        err_adv_notrun_swc = check_disposition_coverage_row(
            disp_adv_swc, req_adv, "satisfied", {"X": [{"result": "not-run"}]}, "re-execute-all", {},
        )
        cases.check(
            "audit2-8-not-run-under-re-execute-all-forecloses-satisfied-with-conditions-FAIL",
            err_adv_notrun_swc is not None, err_adv_notrun_swc,
        )
        disp_adv_ie = {"status": "insufficient-evidence", "basis": ["X"]}
        err_adv_notrun_ie = check_disposition_coverage_row(
            disp_adv_ie, req_adv, "satisfied", {"X": [{"result": "not-run"}]}, "re-execute-all", {},
        )
        cases.check(
            "audit2-8-insufficient-evidence-after-not-run-re-execute-all-ok-PASS",
            err_adv_notrun_ie is None, err_adv_notrun_ie,
        )

        # --- F3 (2026-09-24): the `elif adverse_error_not_run:` branch, ISOLATED
        # from the "satisfied"/"satisfied-with-conditions" branches' own run-obligation check (which
        # would otherwise independently reject those two statuses under re-execute-all regardless of
        # this branch, masking a disabled guard). An OPTIONAL, non-waivable requirement dispositioned
        # 'not-applicable' has no run obligation of its own — only the adverse rule can block it —
        # and `witnesses` alone (no cited `basis`) is what makes the not-run claim adverse here,
        # proving the union-not-narrowed-by-citation property (§5.0) at the same time.
        req_adv_optional = {"id": "RADV3", "mandatory": False, "waivable": False, "evidence": {"independence": "none"}}
        disp_adv_na = {"status": "not-applicable", "basis": []}
        pkg_adv_na = {"deviation": [{"requirement": "RADV3", "kind": "not-applicable"}]}
        err_adv_na = check_disposition_coverage_row(
            disp_adv_na, req_adv_optional, "satisfied", {"X": [{"result": "not-run"}]}, "re-execute-all",
            pkg_adv_na, witnesses=["X"],
        )
        cases.check(
            "audit2-8-not-run-witness-forecloses-not-applicable-under-re-execute-all-FAIL",
            err_adv_na is not None and "error'/'not-run'" in err_adv_na, err_adv_na,
        )

        # --- audit2-9 (Finding 9, §5.0a): validity.stale_after is REQUIRED and CAPPED at
        # issued_at + the contract's stale_after when the contract sets one; a lapsed
        # [[condition]].due makes the decision effect-INELIGIBLE; a malformed due date is a
        # structural (not merely effect) invalidity. ---
        rep_v9 = check_decision(decision, contract, package, contract_path, package_path)
        cases.check("audit2-9-baseline-decision-valid-for-effect-tests-PASS", rep_v9.ok(), rep_v9.errors)
        today_v9 = today_utc_date()

        decision_no_stale9 = _copy.deepcopy(decision)
        decision_no_stale9["validity"] = {}
        eligible9a, reason9a = check_decision_effect(decision_no_stale9, contract, rep_v9, today_v9, True)
        cases.check(
            "audit2-9-absent-validity-stale-after-required-FAIL",
            eligible9a is False and "REQUIRED" in reason9a, reason9a,
        )

        decision_beyond_ceiling9 = _copy.deepcopy(decision)
        decision_beyond_ceiling9["validity"] = {"stale_after": "2027-06-01"}
        eligible9b, reason9b = check_decision_effect(decision_beyond_ceiling9, contract, rep_v9, today_v9, True)
        cases.check(
            "audit2-9-validity-stale-after-beyond-ceiling-FAIL",
            eligible9b is False and "ceiling" in reason9b, reason9b,
        )

        eligible9c, reason9c = check_decision_effect(decision, contract, rep_v9, today_v9, True)
        cases.check("audit2-9-validity-stale-after-within-ceiling-eligible-PASS", eligible9c is True, reason9c)

        decision_lapsed9 = _copy.deepcopy(decision)
        for c in decision_lapsed9.get("condition", []):
            c["due"] = "2020-01-01"
        eligible9d, reason9d = check_decision_effect(decision_lapsed9, contract, rep_v9, today_v9, True)
        cases.check(
            "audit2-9-lapsed-condition-ineligible-FAIL",
            eligible9d is False and "lapsed" in reason9d, reason9d,
        )

        dec9e_text = (
            _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace("{{PACKAGE_HASH}}", package_hash)
            .replace('due           = "2026-12-01"', 'due           = "nonsense"')
        )
        dec9e_path = _write(td, "dec-audit2-9e.toml", dec9e_text)
        doc9e, _e = load_toml(dec9e_path)
        rep9e = check_decision(doc9e, contract, package, contract_path, package_path)
        cases.expect_fail("audit2-9-malformed-condition-due-is-structurally-invalid-FAIL", rep9e, "ISO date")

        # --- audit2-11 (Finding 11, §8 item 2): impact compares each declared input's digest
        # between the OLD package and --new-package — a differing digest is
        # definitely-invalidated, not still-applicable (tool/semantics equality alone used to be
        # treated as sufficient). ---
        package11_old = _copy.deepcopy(package)
        package11_new = _copy.deepcopy(package)
        for c in package11_old["claim"]:
            if c.get("id") == "C1":
                c["evidence"][0]["inputs"] = [{"path": "src/lib.rs", "digest": "sha-512:" + "a" * 128}]
        for c in package11_new["claim"]:
            if c.get("id") == "C1":
                c["evidence"][0]["inputs"] = [{"path": "src/lib.rs", "digest": "sha-512:" + "b" * 128}]
        _NEW_COMMIT_11 = "2222222222222222222222222222222222222222"
        result11 = compute_impact(
            decision, contract, package11_old, new_commit=_NEW_COMMIT_11,
            changed_paths=set(), new_package=package11_new,
        )
        c1_records11 = [r for r in result11["records"] if r["claim"] == "C1" and r["evidence_id"].endswith("#0")]
        cases.check(
            "audit2-11-differing-input-digest-is-definitely-invalidated-FAIL",
            bool(c1_records11) and all(r["class"] == "definitely-invalidated" for r in c1_records11),
            c1_records11,
        )
        result11b = compute_impact(
            decision, contract, package11_old, new_commit=_NEW_COMMIT_11,
            changed_paths=set(), new_package=_copy.deepcopy(package11_old),
        )
        c1_records11b = [r for r in result11b["records"] if r["claim"] == "C1" and r["evidence_id"].endswith("#0")]
        cases.check(
            "audit2-11-matching-input-digest-still-applicable-PASS",
            bool(c1_records11b) and all(r["class"] == "still-applicable" for r in c1_records11b),
            c1_records11b,
        )

        # --- audit2-12 (Finding 12, P5, "one authority identity"): `relaxed.by` compares against
        # [acceptance].authority, never `parties.consumer.name`; apply-amendment strips the REAL
        # top-level [ratification] table and always emits issued_by='consumer'. ---
        old12 = {
            "document": {"id": "AC12"}, "parties": {"consumer": {"name": "Acme Co"}},
            "acceptance": {"phase": "final", "authority": "Acme Co / platform-lead"},
            "requirement": [{"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                              "evidence": {"min_tier": "T2"}}],
        }
        new12_consumer_by = {
            "document": {"id": "AC12-v2", "supersedes": "AC12"}, "parties": {"consumer": {"name": "Acme Co"}},
            "acceptance": {"phase": "final", "authority": "Acme Co / platform-lead"},
            "requirement": [{"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                              "evidence": {"min_tier": "T3"},  # weaker than old's T2
                              "relaxed": {"reason": "iteration 2", "by": "Acme Co"}}],  # consumer name, NOT authority
        }
        tight12a = check_contract_tightening(new12_consumer_by, old12)
        cases.expect_fail("audit2-12-relaxed-by-consumer-name-not-authority-refused-FAIL", tight12a, "weakened")

        new12_authority_by = _copy.deepcopy(new12_consumer_by)
        new12_authority_by["requirement"][0]["relaxed"]["by"] = "Acme Co / platform-lead"
        tight12b = check_contract_tightening(new12_authority_by, old12)
        cases.check("audit2-12-relaxed-by-authority-accepted-PASS", tight12b.ok(), tight12b.errors)

        base12_ratified = _copy.deepcopy(contract)
        base12_ratified["document"]["issued_by"] = "producer"
        base12_ratified["document"]["status"] = "ratified"
        base12_ratified["ratification"] = {"by": "Acme Test", "at": "2026-09-16T12:00:00Z"}
        new_contract12, errs12 = apply_amendment_build(amend_ok_doc, base12_ratified, None, "Acme Test / lead")
        cases.check(
            "audit2-12-successor-strips-top-level-ratification-and-issued-by-consumer-PASS",
            not errs12 and "ratification" not in new_contract12 and new_contract12["document"]["issued_by"] == "consumer",
            (errs12, new_contract12.get("ratification"), new_contract12["document"].get("issued_by")),
        )

        # --- audit2-13 (Finding 13, §3.1 rule 1): `replaces` is transition-local — stripped when
        # apply-amendment derives a successor, so a carried-over requirement never re-emerges
        # carrying a NOW-STALE `replaces` (which would itself be a rule-1 violation the NEXT time
        # this contract is superseded again). ---
        base13_carrying_replaces = _copy.deepcopy(contract)
        for r in base13_carrying_replaces["requirement"]:
            if r["id"] == "R1":
                r["replaces"] = "R-PRE-EXISTING"  # as if R1 was introduced replacing R-PRE-EXISTING
        new_contract13b, errs13b = apply_amendment_build(amend_ok_doc, base13_carrying_replaces, None, "Acme Test / lead")
        r1_after13 = next(r for r in new_contract13b["requirement"] if r["id"] == "R1")
        cases.check(
            "audit2-13-replaces-stripped-from-carried-over-requirement-PASS",
            "replaces" not in r1_after13, r1_after13,
        )
        # The FAIL half: a hand-authored (or pre-fix) contract that DID carry `replaces` over
        # under the same id is exactly the rule-1 violation check_contract_tightening refuses —
        # proving the tool's own output, absent the fix above, would have been rejected downstream.
        old13_bad = {
            "document": {"id": "AC13BAD"}, "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final", "authority": "Acme"},
            "requirement": [{"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                              "statement": "s1", "domain": "correctness", "evidence": {"min_tier": "T3"},
                              "replaces": "R-OLD"}],
        }
        new13_bad = {
            "document": {"id": "AC13BAD-v2", "supersedes": "AC13BAD"}, "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final", "authority": "Acme"},
            "requirement": [{"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                              "statement": "s1", "domain": "correctness", "evidence": {"min_tier": "T3"},
                              "replaces": "R-OLD"}],
        }
        tight13_bad = check_contract_tightening(new13_bad, old13_bad)
        cases.expect_fail("audit2-13-replaces-carried-over-under-same-id-refused-FAIL", tight13_bad, "replaces")

        # --- audit2-14 (Finding 14, §3.1 rule 1/§3.5): `[requirement.evidence.recipe]` is
        # validated (nonempty strings), part of the floor set (removal/change of command is a
        # weakening unless relaxed), and SURVIVES serialization through an unrelated amendment. ---
        rep_recipe_bad = Reporter("t")
        _check_evidence_floor(rep_recipe_bad, "ctx", {
            "min_tier": "T3", "control_required": False, "recipe_required": False,
            "freshness": "any", "independence": "none",
            "recipe": {"command": "", "expect": "ok"},
        })
        cases.expect_fail("audit2-14-recipe-empty-command-refused-FAIL", rep_recipe_bad, "recipe")

        rep_recipe_ok = Reporter("t")
        _check_evidence_floor(rep_recipe_ok, "ctx", {
            "min_tier": "T3", "control_required": False, "recipe_required": False,
            "freshness": "any", "independence": "none",
            "recipe": {"command": "cargo test", "expect": "ok"},
        })
        cases.check("audit2-14-recipe-valid-passes-PASS", rep_recipe_ok.ok(), rep_recipe_ok.errors)

        old14 = {
            "document": {"id": "AC14"}, "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final", "authority": "Acme"},
            "requirement": [{"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                              "evidence": {"min_tier": "T3", "recipe": {"command": "cargo test", "expect": "ok"}}}],
        }
        new14_removed = {
            "document": {"id": "AC14-v2", "supersedes": "AC14"}, "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final", "authority": "Acme"},
            "requirement": [{"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                              "evidence": {"min_tier": "T3"}}],
        }
        tight14 = check_contract_tightening(new14_removed, old14)
        cases.expect_fail("audit2-14-recipe-removed-without-relaxed-FAIL", tight14, "recipe")

        # --- F10 (§3.5): the WHOLE [requirement.evidence.recipe] table is
        # in the floor set, not just `command` — a weakened `expect` or a dropped `control_patch`
        # must also be flagged as a tightening violation. Confirmed: BEFORE this fix, both
        # `new14_expect_weakened` and `new14_control_patch_removed` below passed
        # check_contract_tightening cleanly (tight14_expect.ok() / tight14_ctrl_patch.ok() were
        # True with no [requirement.relaxed] present). ---
        new14_expect_weakened = {
            "document": {"id": "AC14-v2", "supersedes": "AC14"}, "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final", "authority": "Acme"},
            "requirement": [{"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                              "evidence": {"min_tier": "T3",
                                           "recipe": {"command": "cargo test", "expect": ""}}}],
        }
        tight14_expect = check_contract_tightening(new14_expect_weakened, old14)
        cases.expect_fail(
            "f10-recipe-expect-weakened-without-relaxed-FAIL", tight14_expect, "recipe.expect",
        )

        old14_ctrl_patch = _copy.deepcopy(old14)
        old14_ctrl_patch["requirement"][0]["evidence"]["recipe"]["control_patch"] = "revert the length check"
        new14_control_patch_removed = {
            "document": {"id": "AC14-v2", "supersedes": "AC14"}, "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final", "authority": "Acme"},
            "requirement": [{"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                              "evidence": {"min_tier": "T3",
                                           "recipe": {"command": "cargo test", "expect": "ok"}}}],
        }
        tight14_ctrl_patch = check_contract_tightening(new14_control_patch_removed, old14_ctrl_patch)
        cases.expect_fail(
            "f10-recipe-control-patch-removed-without-relaxed-FAIL",
            tight14_ctrl_patch, "control_patch",
        )

        # Follow-up recheck (2026-09-16) F10 minor: the WHOLE recipe table is in the §3.5 floor set, so
        # a change in a key OUTSIDE command/expect/control_patch (here a future `timeout`) must also
        # be flagged. Only that key differs old→new, so the catch-all is what fires. Passed cleanly
        # before the catch-all was added.
        old14_other = {
            "document": {"id": "AC14"}, "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final", "authority": "Acme"},
            "requirement": [{"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                              "evidence": {"min_tier": "T3",
                                           "recipe": {"command": "cargo test", "expect": "ok", "timeout": "300"}}}],
        }
        new14_other = {
            "document": {"id": "AC14-v2", "supersedes": "AC14"}, "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final", "authority": "Acme"},
            "requirement": [{"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                              "evidence": {"min_tier": "T3",
                                           "recipe": {"command": "cargo test", "expect": "ok", "timeout": "999"}}}],
        }
        tight14_other = check_contract_tightening(new14_other, old14_other)
        cases.expect_fail(
            "f10-recipe-other-key-changed-flagged", tight14_other, "outside",
        )

        base14 = _copy.deepcopy(contract)
        for r in base14["requirement"]:
            if r["id"] == "R1":
                r["evidence"]["recipe"] = {"command": "cargo test --test malformed", "expect": "ok"}
        new_contract14, errs14 = apply_amendment_build(amend_ok_doc, base14, None, "Acme Test / lead")
        cases.check("audit2-14-build-with-recipe-succeeds-PASS", not errs14, errs14)
        rendered14 = _render_contract_toml(new_contract14)
        reparsed14 = tomllib.loads(rendered14)
        r1_reparsed14 = next(r for r in reparsed14["requirement"] if r["id"] == "R1")
        cases.check(
            "audit2-14-recipe-survives-serialization-round-trip-PASS",
            r1_reparsed14.get("evidence", {}).get("recipe") == {"command": "cargo test --test malformed", "expect": "ok"},
            r1_reparsed14,
        )

        # --- audit2-15 (Finding 15, profiles.py): the floor-schema validator type-checks BEFORE
        # set membership — a wrong-typed value (a list where a string is expected) is a
        # validation ERROR, never a TypeError. ---
        _validate_floor = PROFILES["acceptance/verification"]["validate_floor"]
        errs15_bad = None
        crashed15 = False
        try:
            errs15_bad = _validate_floor({"min_band": ["A1"]})
        except TypeError:
            crashed15 = True
        cases.check(
            "audit2-15-wrong-typed-min-band-is-validation-error-not-crash-FAIL",
            not crashed15 and bool(errs15_bad), (crashed15, errs15_bad),
        )
        errs15_ok = _validate_floor({"min_band": "A1"})
        cases.check("audit2-15-correctly-typed-min-band-passes-PASS", errs15_ok == [], errs15_ok)

        # --- audit2-16 (Finding 16, §3.1 rule 1): `over` GROWING under the same id is a
        # floor-only tightening (allowed freely); `over` SHRINKING under the same id is a
        # semantic-replacement identity violation — an ERROR even with `[requirement.relaxed]`,
        # because the only way to drop a covered id is a NEW id (`replaces`), never same-id relax. ---
        old16 = {
            "document": {"id": "AC16"}, "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final", "authority": "Acme"},
            "requirement": [
                {"id": "R1", "mandatory": True, "waivable": False, "kind": "item", "evidence": {"min_tier": "T3"}},
                {"id": "R2", "mandatory": True, "waivable": False, "kind": "item", "evidence": {"min_tier": "T3"}},
                {"id": "RC", "mandatory": True, "waivable": True, "kind": "cross-cutting", "over": ["R1", "R2"],
                 "demands": {}},
            ],
        }
        new16_shrunk = _copy.deepcopy(old16)
        new16_shrunk["document"] = {"id": "AC16-v2", "supersedes": "AC16"}
        for r in new16_shrunk["requirement"]:
            if r["id"] == "RC":
                r["over"] = ["R1"]
        tight16a = check_contract_tightening(new16_shrunk, old16)
        cases.expect_fail("audit2-16-over-shrunk-under-same-id-refused-FAIL", tight16a, "Finding 16")

        new16_shrunk_relaxed = _copy.deepcopy(new16_shrunk)
        for r in new16_shrunk_relaxed["requirement"]:
            if r["id"] == "RC":
                r["relaxed"] = {"reason": "trying to excuse it", "by": "Acme"}
        tight16b = check_contract_tightening(new16_shrunk_relaxed, old16)
        cases.expect_fail("audit2-16-over-shrunk-not-excused-by-relaxed-FAIL", tight16b, "Finding 16")

        new16_grown = _copy.deepcopy(old16)
        new16_grown["document"] = {"id": "AC16-v3", "supersedes": "AC16"}
        for r in new16_grown["requirement"]:
            if r["id"] == "RC":
                r["over"] = ["R1", "R2"]  # unchanged; growth alone is the interesting positive case
        new16_grown["requirement"].append(
            {"id": "R3", "mandatory": False, "waivable": True, "kind": "item", "evidence": {"min_tier": "T5"}},
        )
        for r in new16_grown["requirement"]:
            if r["id"] == "RC":
                r["over"] = ["R1", "R2", "R3"]
        tight16c = check_contract_tightening(new16_grown, old16)
        cases.check("audit2-16-over-grown-under-same-id-is-tightening-PASS", tight16c.ok(), tight16c.errors)

        # --- impact: undeclared inputs classify possibly-invalidated ----------------------
        result = compute_impact(
            decision, contract, package, new_commit="1111111111111111111111111111111111111111",
            changed_paths={"unrelated/path.rs"},
        )
        c1_records = [r for r in result["records"] if r["claim"] == "C1"]
        cases.check(
            "impact-undeclared-inputs-classify-possibly-invalidated",
            bool(c1_records) and all(r["class"] == "possibly-invalidated" for r in c1_records),
            c1_records,
        )
        cases.check(
            "impact-mints-one-obligation-per-invalidated-claim",
            any(ev["kind"] == "minted" for ev in result["events"])
            and any(ev["kind"] == "stale_detected" for ev in result["events"]),
            result["events"],
        )

        # =====================================================================================
        # An earlier review (2026-09-16) closed tool-only findings F2/F3/F6/F7/F8/F10/F11.
        # Each fixture below reproduces the exact defect against the pre-fix behaviour (see the
        # PR/diff for the "before" code) and is green only because of the fix cited in its name.
        # =====================================================================================

        # --- F6 (§5.0a, check_decision / check_decision_effect): `issued_at` is
        # now validated as RFC 3339 by check_decision (a nonempty-but-garbage value is an ERROR),
        # and an unparseable issued_at makes check_decision_effect's stale_after ceiling refuse
        # the decision outright rather than silently skip the cap. Reproduction confirmed: BEFORE
        # this fix, `check-decision <d> --contract <c> --package <p> --effect --allow-conditions
        # --now 2026-09-16` on this exact mutation (garbage issued_at, far-future stale_after)
        # reported EFFECT-ELIGIBLE.
        dec_f6_text = (
            _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
            .replace("{{PACKAGE_HASH}}", package_hash)
            .replace('issued_at = "2026-09-20T09:00:00Z"', 'issued_at = "sometime"')
            .replace('stale_after = "2026-12-19"', 'stale_after = "2099-01-01"')
        )
        dec_f6_path = _write(td, "dec-f6.toml", dec_f6_text)
        doc_f6, _e = load_toml(dec_f6_path)
        rep_f6 = check_decision(doc_f6, contract, package, contract_path, package_path)
        cases.expect_fail("f6-malformed-issued-at-fails-check-decision", rep_f6, "issued_at")

        eligible_f6, reason_f6 = check_decision_effect(doc_f6, contract, rep_f6, "2026-09-16", True)
        cases.check(
            "f6-malformed-issued-at-ineligible-under-effect-via-invalid-gate",
            eligible_f6 is False, (eligible_f6, reason_f6),
        )

        # Isolates check_decision_effect's OWN ceiling logic (Finding 6's actual fail-open site)
        # from check_decision's new gate above — a synthetically "already valid" Reporter still
        # must not let the malformed issued_at compute a skipped cap.
        fake_ok_rep_f6 = Reporter("d")
        eligible_f6b, reason_f6b = check_decision_effect(doc_f6, contract, fake_ok_rep_f6, "2026-09-16", True)
        cases.check(
            "f6-ceiling-fails-closed-on-unparseable-issued-at",
            eligible_f6b is False, (eligible_f6b, reason_f6b),
        )

        # Follow-up recheck (2026-09-16) F6 minor: a date-only / offset-less issued_at is NOT an RFC
        # 3339 date-time; before the is_rfc3339_datetime tightening `fromisoformat` accepted
        # "2026-09-20" and check_decision VALIDated it — the same genus of split as F8. The
        # baseline decision's own full "…T…Z" issued_at is the positive control (still valid).
        dec_f6c_text = (
            _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
            .replace("{{PACKAGE_HASH}}", package_hash)
            .replace('issued_at = "2026-09-20T09:00:00Z"', 'issued_at = "2026-09-20"')
        )
        dec_f6c_path = _write(td, "dec-f6c.toml", dec_f6c_text)
        doc_f6c, _e = load_toml(dec_f6c_path)
        rep_f6c = check_decision(doc_f6c, contract, package, contract_path, package_path)
        cases.expect_fail("f6-date-only-issued-at-rejected-rfc3339", rep_f6c, "RFC 3339")

        # --- F8 (load_toml): the `key = val; key2 = val2` semicolon-shorthand
        # fallback is states.toml's alone (`allow_semicolon=True` only at that one call site) —
        # every OTHER protocol document must reject it as invalid TOML. Reproduction confirmed:
        # BEFORE this fix, `load_toml` retried ANY failed strict parse with the fallback for ANY
        # document, so the decision fragment below parsed cleanly instead of being refused.
        f8_semicolon_text = '[document]\nid = "AD-F8"; kind = "decision"\n'
        f8_path = _write(td, "f8-semicolon.toml", f8_semicolon_text)
        f8_doc, f8_err = load_toml(f8_path)
        cases.check(
            "f8-semicolon-shorthand-rejected-for-non-states-document",
            f8_doc is None and f8_err is not None, (f8_doc, f8_err),
        )
        f8_states_doc = _default_states_doc()
        cases.check(
            "f8-states-toml-still-loads-via-allow-semicolon",
            bool(f8_states_doc.get("machine")), sorted(f8_states_doc.keys()),
        )

        # --- F2 (§5.2 line 632, check_disposition_coverage_row): `waived` on a
        # cov(R) = satisfied requirement is accepted when a cited basis claim has an adverse
        # (failing) run — the adverse gate above (Finding 8) already lets `waived` through in
        # this situation; the unconditional "meaningless" error below it used to reject the same
        # row it was just admitted for. Reproduction confirmed: BEFORE this fix, `err_f2` here was
        # non-None ("disposition 'waived' is meaningless when coverage is already 'satisfied'").
        req_f2 = {"id": "RF2", "mandatory": True, "waivable": True, "evidence": {"independence": "none"}}
        disp_f2_waived = {
            "status": "waived", "basis": ["XF2"],
            "waiver": {
                "reason": "an adverse run contradicts the otherwise-satisfied static coverage",
                "code": "risk-accepted", "authority": "Acme Test / lead",
            },
        }
        err_f2 = check_disposition_coverage_row(
            disp_f2_waived, req_f2, "satisfied", {"XF2": [{"result": "fail"}]}, "spot-check", {},
        )
        cases.check(
            "f2-waived-accepted-on-satisfied-coverage-with-adverse-run-PASS",
            err_f2 is None, err_f2,
        )
        # Positive control: cov(R) = satisfied and NO adverse run — still genuinely meaningless.
        err_f2_no_adverse = check_disposition_coverage_row(
            disp_f2_waived, req_f2, "satisfied", {"XF2": [{"result": "pass"}]}, "spot-check", {},
        )
        cases.check(
            "f2-waived-still-meaningless-on-satisfied-coverage-without-adverse-run-FAIL",
            err_f2_no_adverse is not None and "meaningless" in err_f2_no_adverse, err_f2_no_adverse,
        )

        # --- F10 (§3.5, check_contract_tightening): tested above as
        # f10-recipe-expect-weakened-without-relaxed-FAIL and
        # f10-recipe-control-patch-removed-without-relaxed-FAIL (audit2-14 block).

        # --- F11 (§5.1, load_verdict_rules / check_decision): an unknown
        # `conditions` token in a `[[verdict_rule]]` row is now rejected FAIL-CLOSED at load —
        # on the live check_decision path, not only under check-states' exhaustive proof.
        # Reproduction confirmed: BEFORE this fix, `verdict_row_matches`'s trailing "matches
        # regardless" fallthrough meant a typo'd token silently behaved as the LEAST restrictive
        # case ('any'), and `rep_f11` below was `.ok()`.
        tampered_verdict_rules_f11 = [
            {"row": 1, "mandatory_all_in": ["satisfied"], "conditions": "none", "verdict": "accepted"},
            {"row": 2, "mandatory_all_in": ["satisfied", "satisfied-with-conditions", "waived"],
             "mandatory_not_all": "satisfied", "conditions": "sum", "verdict": "accepted-with-conditions"},
            {"row": 3, "mandatory_any": ["insufficient-evidence"], "conditions": "some",
             "verdict": "evidence-requested"},
            {"row": 4, "mandatory_any": ["unsatisfied"], "conditions": "any", "verdict": "rejected"},
        ]
        rep_f11 = check_decision(
            decision, contract, package, contract_path, package_path,
            verdict_rules=tampered_verdict_rules_f11,
        )
        cases.expect_fail(
            "f11-unknown-conditions-token-rejected-on-decision-path",
            rep_f11, "conditions must be one of",
        )
        # load_verdict_rules itself raises, fail-closed, on the same tampered table.
        raised_f11 = False
        try:
            load_verdict_rules({"verdict_rule": tampered_verdict_rules_f11})
        except VerdictRuleError:
            raised_f11 = True
        cases.check("f11-load-verdict-rules-raises-on-unknown-token", raised_f11, None)

        # --- F7/G5 (claim_weight_grants / check_acceptance.Reporter): the
        # weight-grant gate now prefers check_acceptance's structured `weight_refused`/
        # `axis_blocked` accessors over parsing its error strings; the string parse remains only
        # as a fallback for a validator binding that doesn't expose them.
        f7_package_text = """
[format]
id = "acceptance/0"

[subject]
name   = "f7-selftest"
kind   = "rust-crate"
commit = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
dirty  = false

[spec]
path    = "SPEC.md"
version = "v1"
axis    = "F7 fixture"

[coverage]
clauses_total = 1
claims_total  = 1

[[claim]]
id            = "C-WR"
clause        = "S-1"
item          = "src/lib.rs::wr"
statement     = "a claim whose weight the validator refuses outright"
band          = "A0"
weight        = "weighted"
grade         = "unspecified"
clause_source = "none"
status        = "gap"
"""
        f7_path = _write(td, "f7-package.toml", f7_package_text)
        doc_f7, _e = load_toml(f7_path)
        claims_f7 = doc_f7.get("claim") or []
        grants_f7, ca_rep_f7 = claim_weight_grants(f7_path, claims_f7)
        cases.check(
            "f7-weight-refused-claim-computed-unweighted-via-real-validator",
            grants_f7.get("C-WR") is False
            and "claim 'C-WR'" in getattr(ca_rep_f7, "weight_refused", set()),
            (grants_f7, sorted(getattr(ca_rep_f7, "weight_refused", set()) or [])),
        )

        # Proves the STRUCTURED accessor is actually consulted (not merely happening to agree
        # with the string parse): a stub validator whose error text has drifted away from the
        # literal "WEIGHT REFUSED" substring, but whose structured `weight_refused` set still
        # names the claim. BEFORE this fix (string-parse only), this claim would have been
        # silently GRANTED (fail-open on message-format drift).
        class _StubRepF7:
            def __init__(self):
                self.errors = [
                    "claim 'C-WR': grade refusal message reworded, no longer containing the old "
                    "marker string the string-parse fallback looks for",
                ]
                self.weight_refused = {"claim 'C-WR'"}
                self.axis_blocked = False
                self.pending = {}

        def _stub_validator_f7(path, strict=False, strict_weight=False):
            return _StubRepF7()

        grants_f7_stub, _rep_stub = claim_weight_grants(
            Path("/nonexistent-f7"), [{"id": "C-WR", "weight": "weighted"}],
            {"package_validator": _stub_validator_f7},
        )
        cases.check(
            "f7-structured-accessor-consulted-over-drifted-error-string",
            grants_f7_stub.get("C-WR") is False, grants_f7_stub,
        )

        # --- T2: project-brief -> W6 report -> assemble-package, full round trip -----------------
        # worker-brief.md §1/§2's own acceptance line: "a selftest round-trips a two-requirement
        # brief -> report -> package". A throwaway, self-contained git repo under THIS tempdir (git
        # init + one commit) — never the real repo — so assemble-package's git calls (subject
        # commit/dirty) resolve; no PROFILES lookup by id (a minimal inline profile binding), so
        # this exercises the core mechanism, not any one profile's vocabulary.
        with tempfile.TemporaryDirectory() as t2_tdstr:
            t2_td = Path(t2_tdstr)
            (t2_td / ".git").mkdir()  # B6 root for the assembled package
            t2_contract_text = f"""
[document]
protocol   = "{PROTOCOL_ID}"
minor      = 0
kind       = "contract"
id         = "AC-T2RT-1"
version    = 1
issued_at  = "2026-09-16T10:00:00Z"
issued_by  = "consumer"
status     = "issued"

[parties]
consumer = {{ name = "T2 Test Consumer", contact = "t2@test.example" }}
producer = {{ name = "t2-worker" }}

[subject]
kind         = "other"
name         = "t2-subject"
description  = "a two-requirement round-trip fixture."
deliverables = ["artifact"]
constraints  = []
profile      = "acceptance/verification"

[[requirement]]
id            = "R1"
statement     = "R1 must hold"
mandatory     = true
waivable      = false
domain        = "correctness"
clause_source = "consumer-statement"
  [requirement.evidence]
  min_tier          = "T3"
  weighted_required = true
  control_required  = false
  recipe_required   = true
  freshness         = "any"
  independence      = "none"

[[requirement]]
id            = "R2"
statement     = "R2 must hold"
mandatory     = true
waivable      = false
domain        = "correctness"
clause_source = "consumer-statement"
  [requirement.evidence]
  min_tier          = "T3"
  weighted_required = true
  control_required  = false
  recipe_required   = true
  freshness         = "any"
  independence      = "none"

[acceptance]
rule                  = "all-mandatory-satisfied"
consumer_verification = "spot-check"
authority             = "T2 Test Consumer / lead"
profiles_required     = []
stale_after           = "P90D"
"""
            t2_contract_path = _write(t2_td, "t2-contract.toml", t2_contract_text)
            t2_contract, t2_cerr = load_toml(t2_contract_path)

            # §1: project-brief. No profile bound (None) — a core-only fixture, no vocabulary.
            t2_brief_fields, t2_brief_warnings = build_brief_fields(
                t2_contract or {}, t2_contract_path, "subject/**", None,
            )
            t2_brief_roundtrip = parse_window_brief_yaml(render_window_brief_yaml(t2_brief_fields))
            t2_brief_has_both = (
                "R1:" in t2_brief_roundtrip.get("plan", "") and "R2:" in t2_brief_roundtrip.get("plan", "")
            )

            # W6 report directory: a throwaway self-contained git repo, never the real one.
            t2_report = t2_td / "report"
            (t2_report / "subject").mkdir(parents=True)
            (t2_report / "subject" / "marker.txt").write_text("t2 roundtrip subject placeholder\n")
            (t2_report / "transcripts").mkdir(parents=True)
            (t2_report / "transcripts" / "check1.txt").write_text("$ run-check --one\nCHECK-1: PASS\n")
            (t2_report / "transcripts" / "check2.txt").write_text("$ run-check --two\nCHECK-2: PASS\n")
            subprocess.run(["git", "init", "-q"], cwd=t2_report, check=True)
            subprocess.run(
                ["git", "-c", "user.email=t2@test.example", "-c", "user.name=T2 Test", "add", "-A"],
                cwd=t2_report, check=True,
            )
            subprocess.run(
                ["git", "-c", "user.email=t2@test.example", "-c", "user.name=T2 Test",
                 "commit", "-q", "-m", "t2 roundtrip fixture"],
                cwd=t2_report, check=True,
            )
            t2_head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=t2_report, capture_output=True, text=True, check=True,
            ).stdout.strip()
            (t2_report / "manifest.toml").write_text(f"""
[report]
commit = "{t2_head}"
date   = "2026-09-16"

[[run]]
id         = "run1"
role       = "primary"
command    = "run-check --one"
returncode = 0
transcript = "transcripts/check1.txt"

[[run]]
id         = "run2"
role       = "primary"
command    = "run-check --two"
returncode = 0
transcript = "transcripts/check2.txt"
""")

            def _t2_class_fields(cmd: str):
                return (
                    {"kind": "unit-test", "family": "dynamic", "method": "unit-test", "epistemic_tier": "T3"}
                    if cmd.startswith("run-check") else None
                )

            def _t2_judge(cmd: str, rc: int, out: str):
                return ("pass" if rc == 0 and "PASS" in out else "fail"), None

            def _t2_tool(cmd: str, probes: dict) -> str:
                return "t2-check-tool 1.0.0"

            t2_profile = {
                "evidence_class_fields": _t2_class_fields,
                "judge_run": _t2_judge,
                "tool_string": _t2_tool,
                "recipe_carrier": lambda req: None,
            }

            # §2: assemble-package. fill.toml's shape as a plain dict (the worker's semantic slice
            # only: statement/band/grade/clause_source + the worker-proposed recipe per requirement,
            # since this fixture's contract declares no [requirement.evidence.recipe] of its own).
            t2_fill = {
                "claim": [
                    {
                        "id": "T2-C1", "requirement": "R1",
                        "statement": "R1 is shown by run-check --one.",
                        "band": "A0", "grade": "test-only", "clause_source": "spec-document",
                        "recipe": {"command": "run-check --one", "expect": "CHECK-1: PASS"},
                        "watched_fail": {
                            "perturbed": "broke the R1 check on purpose",
                            "observed": "CHECK-1: FAIL",
                        },
                        "evidence": [{"run": "run1", "ref": "check1", "cases": 1}],
                    },
                    {
                        "id": "T2-C2", "requirement": "R2",
                        "statement": "R2 is shown by run-check --two.",
                        "band": "A0", "grade": "test-only", "clause_source": "spec-document",
                        "recipe": {"command": "run-check --two", "expect": "CHECK-2: PASS"},
                        "watched_fail": {
                            "perturbed": "broke the R2 check on purpose",
                            "observed": "CHECK-2: FAIL",
                        },
                        "evidence": [{"run": "run2", "ref": "check2", "cases": 1}],
                    },
                ],
                "filler": [{"profile": "acceptance/verification", "party": "t2-worker", "role": "producer"}],
            }

            t2_out = t2_td / "t2-acceptance.toml"
            try:
                assemble_package(
                    t2_brief_fields, t2_report, t2_contract, t2_contract_path, t2_fill, t2_out, t2_profile,
                )
                t2_asm_error = None
            except AssembleError as e:
                t2_asm_error = str(e)

            t2_pkg, t2_pkg_err = (load_toml(t2_out) if t2_out.is_file() else (None, "not written"))
            t2_claims = {c.get("id"): c for c in (t2_pkg.get("claim") or [])} if t2_pkg else {}
            t2_rep_c = check_contract(t2_contract) if t2_contract else None
            t2_rep_p, t2_cov = (
                check_package(t2_pkg, t2_contract, t2_out, t2_contract_path, strict=False)
                if t2_pkg and t2_contract else (None, None)
            )

            # Finding #26 (lens completeness-coherence): `assemble-package` MUST write the typed
            # `record:sha-512:<128-hex>` wire form (hash-domains.md) for a claim's own evidence
            # `record_hash`, never the untyped legacy `sha-512:<128-hex>` construction — that
            # legacy wire is read-only in 0.3.x and producers MUST NOT emit it (hash-domains.md
            # line 56).
            t2_c1_ev = (t2_claims.get("T2-C1", {}).get("evidence") or [{}])[0]
            t2_c2_ev = (t2_claims.get("T2-C2", {}).get("evidence") or [{}])[0]
            t2_c1_record_hash = t2_c1_ev.get("record_hash", "")
            t2_c2_record_hash = t2_c2_ev.get("record_hash", "")

            def _is_typed_record_hash(value: str) -> bool:
                if not value.startswith("record:sha-512:"):
                    return False
                hexpart = value[len("record:sha-512:"):]
                return len(hexpart) == 128 and all(c in "0123456789abcdef" for c in hexpart)

            t2_record_hashes_typed = (
                _is_typed_record_hash(t2_c1_record_hash) and _is_typed_record_hash(t2_c2_record_hash)
            )

            t2_ok = (
                t2_cerr is None
                and t2_brief_has_both
                and t2_asm_error is None
                and t2_pkg_err is None
                and t2_claims.get("T2-C1", {}).get("status") == "evidenced"
                and t2_claims.get("T2-C2", {}).get("status") == "evidenced"
                and t2_claims.get("T2-C1", {}).get("weight") == "weighted"
                and t2_claims.get("T2-C2", {}).get("weight") == "weighted"
                and t2_record_hashes_typed
                and t2_rep_c is not None and t2_rep_c.ok()
                and t2_rep_p is not None and t2_rep_p.ok()
                and t2_cov is not None
                and t2_cov["requirements"]["R1"]["status"] == "satisfied"
                and t2_cov["requirements"]["R2"]["status"] == "satisfied"
            )
            cases.check(
                "t2-roundtrip-two-requirement-brief-report-package",
                t2_ok,
                {
                    "contract_err": t2_cerr, "brief_warnings": t2_brief_warnings,
                    "brief_has_both": t2_brief_has_both, "asm_error": t2_asm_error,
                    "pkg_err": t2_pkg_err, "claims": t2_claims,
                    "contract_errors": getattr(t2_rep_c, "errors", None),
                    "package_errors": getattr(t2_rep_p, "errors", None),
                    "package_unknowns": getattr(t2_rep_p, "unknowns", None), "coverage": t2_cov,
                    "record_hashes_typed": t2_record_hashes_typed,
                },
            )
            # RED control: the assertion above must actually discriminate typed from untyped —
            # prove it rejects the OLD untyped legacy wire form (a bare `sha-512:<hex>`, what
            # `m11.digest_file("evidence-record", ...)` used to emit here before this fix), so a
            # regression back to the legacy construction fails this fixture rather than passing
            # silently.
            t2_legacy_form = "sha-512:" + t2_c1_record_hash.rsplit(":", 1)[-1]
            cases.check(
                "t2-roundtrip-record-hash-assertion-rejects-untyped-legacy-wire-RED-control",
                _is_typed_record_hash(t2_c1_record_hash) and not _is_typed_record_hash(t2_legacy_form),
                {"typed": t2_c1_record_hash, "legacy": t2_legacy_form},
            )

        # --- §16c fold fixtures (owner pre-agreed CANON, 2026-09-16) ----------------------------

        # --- Q5 (BLOCKER, §5.0/§5.2): the adverse (worst-result) check ranges over
        # witnesses(R) ∪ cited basis — the union is normative so a consumer cannot narrow the
        # adverse rule by citing only the favourable claim. R witnessed by C_a, C_b; C_b:fail,
        # C_a:pass; `satisfied, basis=["C_a"]` is refused even though the CITED basis all passed;
        # `waived` (waivable) is admitted through the same widened gate. ---
        req_q5 = {"id": "RQ5", "mandatory": True, "waivable": True, "evidence": {"independence": "none"}}
        runs_q5 = {"C_a": [{"result": "pass"}], "C_b": [{"result": "fail"}]}
        disp_q5_narrow = {"status": "satisfied", "basis": ["C_a"]}
        err_q5_narrow = check_disposition_coverage_row(
            disp_q5_narrow, req_q5, "satisfied", runs_q5, "spot-check", {}, witnesses=["C_a", "C_b"],
        )
        cases.check(
            "q5-adverse-union-narrow-citation-refused-FAIL",
            err_q5_narrow is not None and "fail" in err_q5_narrow, err_q5_narrow,
        )
        disp_q5_waived = {
            "status": "waived", "basis": ["C_a"],
            "waiver": {"reason": "adverse claim outside cited basis", "code": "risk-accepted", "authority": "a"},
        }
        err_q5_waived = check_disposition_coverage_row(
            disp_q5_waived, req_q5, "satisfied", runs_q5, "spot-check", {}, witnesses=["C_a", "C_b"],
        )
        cases.check("q5-adverse-union-waived-admitted-PASS", err_q5_waived is None, err_q5_waived)

        # A fail on a claim witnessing TWO requirements taints both, even when neither
        # disposition cites the failing claim in its own `basis` — only the union with
        # witnesses(R) surfaces it.
        runs_q5_shared = {
            "C_shared": [{"result": "fail"}], "C_r": [{"result": "pass"}], "C_s": [{"result": "pass"}],
        }
        req_q5_r = {"id": "RQ5R", "mandatory": True, "waivable": False, "evidence": {"independence": "none"}}
        req_q5_s = {"id": "RQ5S", "mandatory": True, "waivable": False, "evidence": {"independence": "none"}}
        err_q5_r = check_disposition_coverage_row(
            {"status": "satisfied", "basis": ["C_r"]}, req_q5_r, "satisfied", runs_q5_shared,
            "spot-check", {}, witnesses=["C_r", "C_shared"],
        )
        err_q5_s = check_disposition_coverage_row(
            {"status": "satisfied", "basis": ["C_s"]}, req_q5_s, "satisfied", runs_q5_shared,
            "spot-check", {}, witnesses=["C_s", "C_shared"],
        )
        cases.check(
            "q5-adverse-union-shared-failing-witness-taints-both-requirements-FAIL",
            err_q5_r is not None and err_q5_s is not None and "fail" in err_q5_r and "fail" in err_q5_s,
            (err_q5_r, err_q5_s),
        )

        # audit reproduction (2026-09-17, blocker-folds recheck): the adverse widening also binds
        # error/not-run under re-execute-all — an UNCITED witness with an 'error' run forecloses
        # 'satisfied' even though every CITED basis claim passed. Ranging over the cited basis alone
        # (["C_a"], all pass) would wrongly admit it; only witnesses(R) ∪ cited basis surfaces C_b.
        runs_q5_reexec = {"C_a": [{"result": "pass"}], "C_b": [{"result": "error"}]}
        err_q5_reexec = check_disposition_coverage_row(
            {"status": "satisfied", "basis": ["C_a"]}, req_q5, "satisfied", runs_q5_reexec,
            "re-execute-all", {}, witnesses=["C_a", "C_b"],
        )
        cases.check(
            "q5-adverse-union-uncited-error-under-re-execute-all-refused-FAIL",
            err_q5_reexec is not None and "error" in err_q5_reexec, err_q5_reexec,
        )

        # --- Q1 (BLOCKER, §3.5 "Projection pinning"): [subject].profile is INVARIANT across a
        # supersedes chain; [acceptance].profiles_required may only GAIN entries. ---
        old_q1 = {
            "document": {"id": "ACQ1"}, "parties": {"consumer": {"name": "Acme"}},
            "acceptance": {"phase": "final", "authority": "Acme", "profiles_required": ["acceptance/verification"]},
            "subject": {"profile": "acceptance/verification"},
            "requirement": [{"id": "R1", "mandatory": True, "waivable": False, "kind": "item",
                              "statement": "s1", "domain": "correctness", "evidence": {"min_tier": "T3"}}],
        }
        new_q1_switch = _copy.deepcopy(old_q1)
        new_q1_switch["document"] = {"id": "ACQ1-v2", "supersedes": "ACQ1"}
        new_q1_switch["subject"] = {"profile": "rust-code"}
        tight_q1_switch = check_contract_tightening(new_q1_switch, old_q1)
        cases.expect_fail("q1-projection-pinning-profile-switch-refused-FAIL", tight_q1_switch, "profile")

        new_q1_removed = _copy.deepcopy(old_q1)
        new_q1_removed["document"] = {"id": "ACQ1-v2", "supersedes": "ACQ1"}
        new_q1_removed["acceptance"]["profiles_required"] = []
        tight_q1_removed = check_contract_tightening(new_q1_removed, old_q1)
        cases.expect_fail(
            "q1-projection-pinning-profiles-required-removed-refused-FAIL", tight_q1_removed, "profiles_required",
        )

        new_q1_added = _copy.deepcopy(old_q1)
        new_q1_added["document"] = {"id": "ACQ1-v2", "supersedes": "ACQ1"}
        new_q1_added["acceptance"]["profiles_required"] = ["acceptance/verification", "rust-code"]
        tight_q1_added = check_contract_tightening(new_q1_added, old_q1)
        cases.check(
            "q1-projection-pinning-profiles-required-gained-passes-PASS",
            tight_q1_added.ok(), tight_q1_added.errors,
        )

        # --- Q6 (major, §5.1/§5.2): `not-applicable` is admissible ONLY on an OPTIONAL
        # requirement (deviation only, no waiver — the decorative ceremony is dropped); a
        # MANDATORY requirement is REFUSED 'not-applicable' outright (routes to
        # waived/code=not-applicable instead). ---
        req_q6_mandatory = {"id": "RQ6M", "mandatory": True, "waivable": True}
        err_q6_mandatory = check_disposition_coverage_row(
            {
                "status": "not-applicable", "basis": [],
                "waiver": {"reason": "r", "code": "not-applicable", "authority": "a"},
            },
            req_q6_mandatory, "gap", {}, "spot-check",
            {"deviation": [{"requirement": "RQ6M", "kind": "not-applicable"}]},
        )
        cases.check(
            "q6-not-applicable-refused-on-mandatory-requirement-FAIL",
            err_q6_mandatory is not None and "MANDATORY" in err_q6_mandatory, err_q6_mandatory,
        )

        req_q6_optional = {"id": "RQ6O", "mandatory": False, "waivable": False}
        err_q6_optional = check_disposition_coverage_row(
            {"status": "not-applicable", "basis": []},
            req_q6_optional, "gap", {}, "spot-check",
            {"deviation": [{"requirement": "RQ6O", "kind": "not-applicable"}]},
        )
        cases.check(
            "q6-not-applicable-optional-no-waiver-needed-PASS", err_q6_optional is None, err_q6_optional,
        )

        # --- Q7 (major, §5.1 exact text): every MANDATORY insufficient-evidence disposition,
        # under verdict='evidence-requested', cites >= 1 condition with owner='producer'; an
        # OPTIONAL insufficient-evidence disposition (R3, baseline) cites none. Before the fix
        # this loop was not scoped to mandatory and wrongly demanded a producer condition for R3
        # too, refusing an otherwise-valid decision. ---
        dec_q7_text = (
            _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash)
            .replace("{{PACKAGE_HASH}}", package_hash)
            .replace('verdict   = "accepted-with-conditions"', 'verdict   = "evidence-requested"')
            .replace(
                '[[disposition]]\nrequirement = "R2"\nstatus      = "waived"\nbasis       = []\n'
                'conditions  = ["COND1"]\n'
                '  [disposition.waiver]\n  reason    = "bounded evidence accepted for this release"\n'
                '  code      = "risk-accepted"\n  authority = "Acme Test / lead"',
                '[[disposition]]\nrequirement = "R2"\nstatus      = "insufficient-evidence"\nbasis       = []\n'
                'conditions  = ["COND1"]',
            )
        )
        dec_q7_path = _write(td, "dec-q7.toml", dec_q7_text)
        doc_q7, _e = load_toml(dec_q7_path)
        rep_q7 = check_decision(doc_q7, contract, package, contract_path, package_path)
        cases.check(
            "q7-optional-insufficient-evidence-needs-no-producer-condition-PASS",
            rep_q7.ok(), rep_q7.errors,
        )

        # ==================================================================================
        # revision — party boundary (§3.4a) + derived decisions (§5.4) + closed without a merits
        # decision (§5.5).
        # ==================================================================================

        def _l8_min_contract(boundary=None, boundary_terms=None):
            doc = {
                "document": {
                    "protocol": PROTOCOL_ID, "minor": 0, "kind": "contract", "id": "AC-L8-1",
                    "version": 1, "issued_at": "2026-09-24T00:00:00Z", "issued_by": "consumer",
                    "status": "issued",
                },
                "parties": {
                    "consumer": {"name": "Acme L8"},
                    "producer": {"name": "supplier-l8"},
                },
                "subject": {"kind": "other", "name": "component-l8", "profile": "acceptance/verification"},
                "acceptance": {
                    "rule": "all-mandatory-satisfied", "consumer_verification": "spot-check",
                    "authority": "Acme L8 / lead", "profiles_required": ["acceptance/verification"],
                },
                "requirement": [{
                    "id": "R1", "statement": "R1 must hold", "mandatory": True, "waivable": False,
                    "domain": "correctness", "clause_source": "consumer-statement",
                    "evidence": {
                        "min_tier": "T3", "weighted_required": True, "control_required": False,
                        "recipe_required": False, "freshness": "any", "independence": "none",
                    },
                }],
            }
            if boundary is not None:
                doc["parties"]["boundary"] = boundary
            if boundary_terms is not None:
                doc["parties"]["boundary_terms"] = boundary_terms
            return doc

        # --- §3.4a: party boundary --------------------------------------------------------
        rep_l8_internal = check_contract(_l8_min_contract())
        cases.check("l8-boundary-internal-default-PASS", rep_l8_internal.ok(), rep_l8_internal.errors)

        rep_l8_cross_missing = check_contract(_l8_min_contract(boundary="cross-org"))
        cases.expect_fail(
            "l8-boundary-cross-org-missing-disclosure-FAIL", rep_l8_cross_missing, "disclosure",
        )

        rep_l8_cross_ok = check_contract(_l8_min_contract(
            boundary="cross-org",
            boundary_terms={
                "disclosure": "evidence referenced, not fully attached",
                "integrity": "DSSE envelope, unbuilt",
            },
        ))
        cases.check("l8-boundary-cross-org-with-terms-PASS", rep_l8_cross_ok.ok(), rep_l8_cross_ok.errors)

        # --- §5.4 derived decisions / §5.5 closed-without-merits, over the baseline
        # AC-TEST-1 contract/package pair built at the top of run() ------------------------
        l8_base_dec_text = _DECISION_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace(
            "{{PACKAGE_HASH}}", package_hash,
        )
        l8_derivation_block = """
[derivation]
authority_act = "merge"
rule          = "external CI green AND 2 reviewers approved => verdict=accepted-with-conditions"
  [[derivation.evidence]]
  ref = "external CI run 123 (description only, not locally resolvable in this fixture)"
"""

        l8_dec_derived_ok_text = l8_base_dec_text.replace(
            'issuer    = "Acme Test / lead"',
            'issuer    = "Acme Test / lead"\nrecorded_by = "Acme Test / audit-recorder"',
        ) + l8_derivation_block
        l8_dec_derived_ok_path = _write(td, "dec-l8-derived-ok.toml", l8_dec_derived_ok_text)
        l8_dec_derived_ok, _e = load_toml(l8_dec_derived_ok_path)
        rep_l8_derived_ok = check_decision(
            l8_dec_derived_ok, contract, package, contract_path, package_path,
            decision_path=l8_dec_derived_ok_path,
        )
        cases.check("l8-derived-decision-valid-PASS", rep_l8_derived_ok.ok(), rep_l8_derived_ok.errors)

        l8_dec_derived_missing_text = l8_base_dec_text + l8_derivation_block
        l8_dec_derived_missing_path = _write(td, "dec-l8-derived-missing.toml", l8_dec_derived_missing_text)
        l8_dec_derived_missing, _e = load_toml(l8_dec_derived_missing_path)
        rep_l8_derived_missing = check_decision(
            l8_dec_derived_missing, contract, package, contract_path, package_path,
            decision_path=l8_dec_derived_missing_path,
        )
        cases.expect_fail(
            "l8-derived-decision-missing-recorded_by-FAIL", rep_l8_derived_missing, "recorded_by",
        )

        l8_dec_recorder_producer_text = l8_base_dec_text.replace(
            'issuer    = "Acme Test / lead"',
            'issuer    = "Acme Test / lead"\nrecorded_by = "supplier-test"',
        ) + l8_derivation_block
        l8_dec_recorder_producer_path = _write(td, "dec-l8-recorder-producer.toml", l8_dec_recorder_producer_text)
        l8_dec_recorder_producer, _e = load_toml(l8_dec_recorder_producer_path)
        rep_l8_recorder_producer = check_decision(
            l8_dec_recorder_producer, contract, package, contract_path, package_path,
            decision_path=l8_dec_recorder_producer_path,
        )
        cases.expect_fail(
            "l8-recorder-equals-producer-internal-FAIL", rep_l8_recorder_producer, "recorder transcribes",
        )

        l8_dec_lapsed_ok_text = f'''
[document]
protocol  = "{PROTOCOL_ID}"
minor     = 0
kind      = "decision"
id        = "AD-L8-MERITS-1"
issued_at = "2026-09-24T00:00:00Z"
issuer    = "Acme Test / lead"
verdict   = "lapsed"
merits    = false
reason    = "closed by the upstream project for reasons outside the delivered artifact (owner, 2026-09-24)"

[binds]
contract = {{ id = "AC-TEST-1", hash = "{contract_hash}" }}
package  = {{ hash = "{package_hash}" }}
subject  = {{ commit = "{_SUBJECT_COMMIT}" }}

[verification]
mode = "spot-check"
'''
        l8_dec_lapsed_ok_path = _write(td, "dec-l8-lapsed-ok.toml", l8_dec_lapsed_ok_text)
        l8_dec_lapsed_ok, _e = load_toml(l8_dec_lapsed_ok_path)
        rep_l8_lapsed_ok = check_decision(
            l8_dec_lapsed_ok, contract, package, contract_path, package_path,
            decision_path=l8_dec_lapsed_ok_path,
        )
        cases.check(
            "l8-lapsed-merits-false-with-reason-PASS", rep_l8_lapsed_ok.ok(), rep_l8_lapsed_ok.errors,
        )

        l8_dec_merits_rejected_text = l8_dec_lapsed_ok_text.replace(
            'verdict   = "lapsed"', 'verdict   = "rejected"',
        )
        l8_dec_merits_rejected_path = _write(td, "dec-l8-merits-rejected.toml", l8_dec_merits_rejected_text)
        l8_dec_merits_rejected, _e = load_toml(l8_dec_merits_rejected_path)
        rep_l8_merits_rejected = check_decision(
            l8_dec_merits_rejected, contract, package, contract_path, package_path,
            decision_path=l8_dec_merits_rejected_path,
        )
        cases.expect_fail(
            "l8-merits-false-with-rejected-FAIL", rep_l8_merits_rejected, "'lapsed' when merits = false",
        )

        # revision: merits = false REQUIRES [document].reason (§5.5) — no prior fixture forced this
        # branch; the PASS case above always carried a reason.
        l8_dec_merits_no_reason_text = l8_dec_lapsed_ok_text.replace(
            '\nreason    = "closed by the upstream project for reasons outside the delivered artifact (owner, 2026-09-24)"',
            '',
        )
        l8_dec_merits_no_reason_path = _write(td, "dec-l8-merits-no-reason.toml", l8_dec_merits_no_reason_text)
        l8_dec_merits_no_reason, _e = load_toml(l8_dec_merits_no_reason_path)
        rep_l8_merits_no_reason = check_decision(
            l8_dec_merits_no_reason, contract, package, contract_path, package_path,
            decision_path=l8_dec_merits_no_reason_path,
        )
        cases.expect_fail(
            "l8-merits-false-without-reason-FAIL", rep_l8_merits_no_reason,
            "reason must be a nonempty string when merits = false",
        )

        # --- §4 / S4: [spec].upstream_status — carried, displayed, never gating -----------
        l8_pkg_upstream_text = _PACKAGE_TOML.replace("{{CONTRACT_HASH}}", contract_hash).replace(
            'axis    = "the requirements of contract AC-TEST-1"',
            'axis    = "the requirements of contract AC-TEST-1"\nupstream_status = "Under Review"',
        )
        l8_pkg_upstream_path = _write(td, "acceptance-l8-upstream.toml", l8_pkg_upstream_text)
        l8_pkg_upstream, _e = load_toml(l8_pkg_upstream_path)
        rep_l8_upstream, _cov_l8_upstream = check_package(
            l8_pkg_upstream, contract, l8_pkg_upstream_path, contract_path, strict=False,
        )
        cases.check("l8-upstream-status-package-valid-PASS", rep_l8_upstream.ok(), rep_l8_upstream.errors)

        l8_rendered = render_markdown(
            contract, l8_pkg_upstream, l8_dec_lapsed_ok, contract_path, l8_pkg_upstream_path,
            l8_dec_lapsed_ok_path,
        )
        cases.check(
            "l8-upstream-status-displayed-in-render-PASS", "Under Review" in l8_rendered, l8_rendered[:600],
        )
        cases.check(
            "l8-merits-false-displayed-in-render-PASS", "merits: `false`" in l8_rendered, l8_rendered[:600],
        )

    # Replay the review's exact shipped examples; copies are isolated from both repos.
    import shutil
    repo = _HERE.parent.parent
    toy_source = repo / "publication/acceptance-format/examples/weighted-toy"
    if not toy_source.is_dir():
        toy_source = repo / "examples/weighted-toy"  # byte-copy public export layout
    for label, source in [("rust-delivery", _HERE.parent / "examples/rust-delivery"),
                          ("weighted-toy", toy_source)]:
        with tempfile.TemporaryDirectory() as example_tmp:
            example = Path(example_tmp) / label
            shutil.copytree(source, example, ignore=shutil.ignore_patterns("target", "__pycache__"))
            (example / ".git").mkdir()
            # Publication sources carry Markdown as .in; exported copies already use .md.
            if (example / "SPEC.md.in").exists():
                shutil.copyfile(example / "SPEC.md.in", example / "SPEC.md")
            cp, pp = example / "acceptance-contract.toml", example / "acceptance.toml"
            c, _ = load_toml(cp)
            pdoc, _ = load_toml(pp)
            r, cov = check_package(pdoc, c, pp, cp, strict=True)
            cases.check(f"correctness-{label}-green-control", r.ok(), (r.errors, r.unknowns))
            if label == "rust-delivery":
                dp = example / "acceptance-decision.toml"

                # The runtime one-day UTC-drift defect (make_decision.py using two different
                # timestamps for issuance and expiry) is already fixed, but nothing regression-
                # gated it — a future re-drift would pass every OTHER check silently. Run the
                # SHIPPED decision through `--effect` on a date inside its validity window, and
                # separately assert its `[validity].stale_after` equals issuance + the contract's
                # own stale_after DURATION, computed in UTC (the exact arithmetic the defect got
                # wrong) — not merely that the decision happens to still be unexpired today.
                d_clean, _e = load_toml(dp)
                dr_clean = check_decision(d_clean, c, pdoc, cp, pp)
                cases.check("correctness-3-rust-delivery-decision-valid-green", dr_clean.ok(), dr_clean.errors)
                eligible, eff_reason = check_decision_effect(d_clean, c, dr_clean, "2026-09-28", True)
                cases.check("correctness-3-rust-delivery-effect-eligible-in-window-green", eligible, eff_reason)
                issued_dt = datetime.datetime.fromisoformat(
                    d_clean["document"]["issued_at"].replace("Z", "+00:00"))
                contract_dur = c["acceptance"]["stale_after"]
                expected_expiry = (issued_dt + duration_to_timedelta(contract_dur)).date().isoformat()
                actual_expiry = d_clean["validity"]["stale_after"]
                cases.check(
                    "correctness-3-rust-delivery-expiry-equals-issuance-plus-duration-utc-green",
                    actual_expiry == expected_expiry,
                    {"issued_at": d_clean["document"]["issued_at"], "stale_after_duration": contract_dur,
                     "expected_expiry": expected_expiry, "actual_expiry": actual_expiry},
                )
                # Able-to-fail control: the exact shape of the fixed defect (an off-by-one-day
                # drift between the two dates) MUST be distinguishable from the real, correct
                # value — proving this assertion is not vacuously true.
                drifted_expiry = (issued_dt + duration_to_timedelta(contract_dur)
                                   + datetime.timedelta(days=1)).date().isoformat()
                cases.check(
                    "correctness-3-rust-delivery-expiry-one-day-drift-detectable-red",
                    drifted_expiry != actual_expiry and drifted_expiry != expected_expiry,
                    {"drifted_expiry": drifted_expiry, "actual_expiry": actual_expiry},
                )

                old_hash = m11.digest_file("manifest", pp)
                pp.write_text(pp.read_text().replace(pdoc["spec"]["path"], "missing-spec.toml", 1))
                dp.write_text(dp.read_text().replace(old_hash, m11.digest_file("manifest", pp)))
                pdoc, _ = load_toml(pp)
                d, _ = load_toml(dp)
                r, cov = check_package(pdoc, c, pp, cp, strict=True)
                dr = check_decision(d, c, pdoc, cp, pp)
                for verb, result in [("package", r), ("decision", dr)]:
                    cases.check(f"correctness-rust-missing-spec-{verb}-red",
                                result.exit_code() == 2 and any("spec.path" in u and
                                "missing-spec.toml" in u for u in result.unknowns),
                                (result.errors, result.unknowns))
                eligible, reason = check_decision_effect(d, c, dr, "2026-09-28", True)
                cases.check("correctness-rust-missing-spec-effect-blocked", not eligible and
                            "INDETERMINATE" in reason and not any(cov["weight_grants"].values()), reason)
            else:
                old_hash = m11.digest_file("contract", cp)
                cp.write_text(cp.read_text().replace('min_tier = "T3"', 'min_tier = "T1"'))
                text = pp.read_text().replace(old_hash, m11.digest_file("contract", cp))
                text = re.sub(r'(?m)^([ \t]*)method\s*=.*$', r'\1method = "lean-theorem"', text)
                text = re.sub(r'(?m)^[ \t]*epistemic_tier\s*=.*\n', '', text)
                pp.write_text(text)
                c, _ = load_toml(cp)
                pdoc, _ = load_toml(pp)
                cases.check("correctness-weighted-toy-review-shape", all(
                    e.get("kind") == "unit-test" and e.get("family") == "dynamic" and
                    e.get("method") == "lean-theorem" and "epistemic_tier" not in e
                    for e in pdoc["claim"][0]["evidence"]), pdoc["claim"][0]["evidence"])
                fr = check_core.validate(pp, strict=True)
                cases.check("correctness-weighted-toy-format-green", check_core.verdict(fr)[1] == 0,
                            (fr.errors, fr.unknowns))
                r, cov = check_package(pdoc, c, pp, cp, strict=True)
                cases.expect_fail("correctness-weighted-toy-T1-red", r,
                                  "requirement 'S-1' is mandatory and coverage computed 'partial'")
                cases.check("correctness-weighted-toy-T3-floor-reason", any(
                    "claim tier 'T3' does not reach min_tier 'T1'" in reason
                    for reason in cov["requirements"]["S-1"]["reasons"].values()), cov["requirements"])

    return cases.items
# L5-owned: end

